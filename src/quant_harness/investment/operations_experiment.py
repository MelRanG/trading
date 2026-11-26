"""Team-neutral frozen A/B contract; adapters execute only after Factory budget.

Current executable adapter: unchanged daily stock rules against the same frozen
Task3 prices, cost and risk contract. Other team schemas are accepted for future
adapters, but an unimplemented evaluator is never reported as executed.
"""
from pathlib import Path
import hashlib,json,os,fcntl
import pandas as pd
from .research import digest,replay_targets,metrics
from .equities import settings,stock_targets,normalize_chart
from .operations_data import encode_prices,decode_prices
from quant_harness.alpha_research_factory import register_review_proposal,reserve_review_experiment,record_review_experiment
TEAMS=('information','company','quant','portfolio','execution','review','research')


def worker_hash(root):
    paths=['operations_experiment.py','equities.py','research.py']
    return digest({p:hashlib.sha256((Path(root)/'src/quant_harness/investment'/p).read_bytes()).hexdigest() for p in paths})


def validate_contract(contract):
    required={'team','adapter','snapshot_hash','baseline','challenger','model_version','prompt_version','strategy_version','period','metrics','budget','stop_conditions','promotion_conditions'}
    if not required<=contract.keys() or any(not contract[k] for k in required):raise ValueError('incomplete common experiment contract')
    if contract['team'] not in TEAMS or contract['baseline']==contract['challenger']:raise ValueError('invalid common experiment pair')
    if contract['budget']!={'experiments':1,'parameter_search':0}:raise ValueError('unregistered search budget')
    if contract['promotion_conditions']!=['independent Forward','human approval']:raise ValueError('promotion authority forbidden')
    return digest(contract)


def strategy_adapter(root,snapshot,contract,directory):
    from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec
    if contract['adapter']!='STOCK_DAILY_FROZEN_V1':raise ValueError('adapter not implemented')
    if digest(snapshot)!=contract['snapshot_hash']:raise ValueError('snapshot hash mismatch')
    cfg=settings(root);market=snapshot['market'];prices=decode_prices(snapshot['prices']);symbols=cfg[market]['seed_symbols']
    if any(prices[s]['meta']['instrumentType']!='EQUITY' for s in symbols):raise ValueError('non-equity strategy input')
    # Session dates and cutoff are frozen inside the snapshot; no API or clock.
    frames={s:v['frame'].assign(date=lambda f:pd.to_datetime(f.timestamp,utc=True).dt.tz_convert('America/New_York' if market=='US' else 'Asia/Seoul').dt.tz_localize(None).dt.normalize()).set_index('date') for s,v in prices.items()}
    close=pd.DataFrame({s:frames[s].close for s in symbols}).sort_index().dropna()
    close=close[close.index<=pd.Timestamp(snapshot['last_complete_date'])]
    dates=close.index[cfg['trend_sessions']:]
    if len(dates)<60:raise ValueError('insufficient common input')
    panel={'close':close,'open':pd.DataFrame({s:frames[s].open for s in symbols}).reindex(close.index),
           'adv20_d1':pd.DataFrame({s:frames[s].value_approx.rolling(20,min_periods=20).mean().shift(1) for s in symbols}).reindex(close.index)}
    assumptions=cfg['US_execution_assumptions'] if market=='US' else cfg['execution_assumptions']
    spec=ExecutionSpec(**{k:v for k,v in assumptions.items() if k!='minimum_order_nav_fraction'},minimum_order_notional_krw=cfg[market]['initial_capital']*assumptions['minimum_order_nav_fraction'])
    out={};directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    for name in (contract['baseline'],contract['challenger']):
        if name not in cfg['strategies']:raise ValueError('unregistered strategy')
        targets=stock_targets(close,cfg,name).set_index('date').reindex(dates).reset_index()
        nav,fills,_=replay_targets(panel,dates,targets,cfg[market]['initial_capital'],spec)
        row=metrics(nav,fills,cfg[market]['initial_capital']);row['currency']=cfg[market]['currency'];row['cost_in_account_currency']=row.pop('cost_krw')
        nav.to_csv(directory/(name+'_nav.csv'),index=False);fills.to_csv(directory/(name+'_fills.csv'),index=False)
        out[name]=row
    result={'status':'FORWARD_REQUIRED','cases':len(dates),'independent_forward_cases':0,'input_hash':digest(snapshot),'worker_hash':worker_hash(root),
            'team':contract['team'],'paired_metrics':out,'period':[str(dates[0].date()),str(dates[-1].date())],
            'evidence_class':'REUSED_HISTORICAL_DIAGNOSTIC_CURRENT_SURVIVOR_UNIVERSE','promotion_status':'NOT_ELIGIBLE',
            'limitations':['Current survivor seeds, not historical point-in-time membership','Repeated historical tail is not independent holdout','Dividend and total-return conventions not harmonized','No automatic selection or promotion'],
            'model_tokens':0,'api_calls':0}
    return result


def execute_common(root,warehouse,snapshot,contract):
    root=Path(root);fingerprint=validate_contract(contract)
    if digest(snapshot)!=contract['snapshot_hash']:raise ValueError('snapshot/contract mismatch')
    if contract['adapter']!='STOCK_DAILY_FROZEN_V1':return {'status':'NOT_IMPLEMENTED','team':contract['team']}
    folder=root/'runtime/task5/experiments'/fingerprint;folder.mkdir(parents=True,exist_ok=True)
    frozen={'contract':contract,'snapshot':snapshot}
    source=folder/'input.json'
    if source.exists() and json.loads(source.read_text())!=frozen:raise ValueError('immutable input conflict')
    if not source.exists():source.write_text(json.dumps(frozen,allow_nan=False))
    proposal={'problem_evidence':{'common_contract_hash':fingerprint,'snapshot_hash':digest(snapshot)},'target':'strategy',
              'expected_effect':'Compare already registered stock rules under identical frozen prices and costs; no presumed improvement.',
              'falsification':'No stable net advantage on independent Forward and regime evidence.',
              'champion':contract['baseline'],'challenger':contract['challenger'],'input_hash':digest(snapshot),'budget':contract['budget'],
              'stop_conditions':contract['stop_conditions'],'evaluation_metric':contract['metrics'],'minimum_cases':12,
              'split':'PROCESS_DIAGNOSTIC_ONLY','worker_hash':worker_hash(root)}
    attempt=register_review_proposal(root,proposal)
    with (folder/'.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        reserve_review_experiment(root,attempt)
        cache=folder/'result.json'
        if cache.exists():
            result=json.loads(cache.read_text())
            if result['worker_hash']!=worker_hash(root) or result['input_hash']!=digest(snapshot):raise ValueError('cached worker/input changed')
        else:
            result=strategy_adapter(root,snapshot,contract,folder)
            temp=cache.with_suffix('.tmp');temp.write_text(json.dumps(result,allow_nan=False));
            with temp.open() as f:os.fsync(f.fileno())
            temp.replace(cache)
        registered=record_review_experiment(root,attempt,result)
        receipt={'contract_hash':fingerprint,'factory_attempt':attempt,'factory_result':registered,'result':result}
        warehouse.store.put('ops_common_experiment',receipt)
        return receipt


def import_us_snapshot(root):
    """Import archived Task3 responses; never refresh the historical experiment."""
    folder=Path(root)/'runtime/task3/us/final';plan=json.loads((folder/'comparison/preregistration.json').read_text())
    cfg=settings(root);prices={}
    hashes={**plan.get('source_hashes',{})}
    # Task3 raw price receipt files name their exact source hash. Require one
    # response per registered seed, and retain original receipt timestamps.
    for receipt_path in (folder/'prices').glob('*.receipt.json'):
        receipt=json.loads(receipt_path.read_text());raw=folder/'prices'/(receipt['source_hash']+'.raw')
        if not raw.exists():continue
        payload=json.loads(raw.read_bytes());symbol=payload['chart']['result'][0]['meta']['symbol']
        if symbol not in cfg['US']['seed_symbols']:continue
        if hashlib.sha256(raw.read_bytes()).hexdigest()!=receipt['source_hash']:raise ValueError('archived raw hash mismatch')
        frame,meta=normalize_chart(payload,symbol)
        if symbol in prices:raise ValueError('ambiguous archived source')
        prices[symbol]={'frame':frame,'meta':meta,'receipt':receipt}
    if set(prices)!=set(cfg['US']['seed_symbols']):raise ValueError('incomplete archived seeds')
    expected=digest({s:v['receipt']['source_hash'] for s,v in prices.items()})
    # Original plan included benchmark/index too. Verify complete source mapping.
    all_hashes={}
    for p in (folder/'prices').glob('*.receipt.json'):
        r=json.loads(p.read_text());raw=folder/'prices'/(r['source_hash']+'.raw')
        if raw.exists():all_hashes[json.loads(raw.read_bytes())['chart']['result'][0]['meta']['symbol']]=r['source_hash']
    if digest(all_hashes)!=plan['input_hash']:raise ValueError('Task3 frozen input provenance mismatch')
    return {'market':'US','prices':encode_prices(prices),'last_complete_date':'2026-11-11','origin_plan_hash':digest(plan),'survivorship_verified':False}

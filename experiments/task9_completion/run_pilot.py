"""Seal all A/B/C decisions before evaluating the fixed historical interval."""
from pathlib import Path
import sys,json,hashlib,shutil
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));sys.path.insert(0,str(Path(__file__).parent))
from replay import fixed_hold,performance,ExecutionSpec
from quant_harness.investment.research import digest
from quant_harness.investment.store import Store
B=R/'runtime/task9_completion';W=Path('/home/ansy/app/quant-diligence/task9-completion-work');out=B/'results';out.mkdir(exist_ok=True)
qualification=json.loads((B/'qualified/manifest.json').read_text());policy=json.loads((Path(__file__).parent/'bounded_pilot_contract_v2.json').read_text());store=Store('postgresql://quant_task9_history@127.0.0.1:55432/quant_task3_task9_history','TASK9_HISTORICAL_ONLY')
originals={};seals=[];expected_hash=None
for mode in ('A','B','C'):
 x=json.loads((W/(mode+'.json')).read_text());inp=json.loads((B/'research_inputs'/('common_'+mode+'.json')).read_text());input_hash=hashlib.sha256(json.dumps(inp,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 if expected_hash is None:expected_hash=input_hash
 assert input_hash==expected_hash and x['session_input_hash']==input_hash,'same-session identity mismatch'
 assert {(r['market'],r['symbol']) for r in x['decisions']}=={(q['market'],q['symbol']) for q in qualification['qualified']}
 for d in x['decisions']:
  assert d['action'] in ('PROBE','WAIT','REJECT') and 0<=d['weight']<=.025
  assert d['weight']==0 if d['action']!='PROBE' else d['weight']>0
 record={'mode':mode,'input_hash':input_hash,'candidate_fingerprint':digest(x),'decision':x,'evidence':'PRE_EVALUATION_HISTORICAL_RECONSTRUCTION','no_forward':True,'policy_hash':digest(policy)};identity=store.put('completion_decision_seal',record);seals.append({'mode':mode,'record_id':identity,'decision_hash':digest(x),'input_hash':input_hash});originals[mode]=x
 folder=B/'research_outputs';folder.mkdir(exist_ok=True)
 for suffix in ('.json','.request.json','.raw.txt'):shutil.copy2(W/(mode+suffix),folder/(mode+suffix))
(B/'decision_seals.json').write_text(json.dumps(seals,indent=2))
# No future performance arithmetic executes above this point.
results=[];worker_hash=hashlib.sha256((Path(__file__).parent/'replay.py').read_bytes()).hexdigest()
for q in qualification['qualified']:
 market=q['market'];symbol=q['symbol'];initial=10000000 if market=='KR' else 100000;frame=pd.read_csv(B/'qualified'/(market+'_raw_prices.csv'),index_col='date');dates=q['session_dates'][1:]
 if market=='KR':
  benchmark=pd.read_csv(B/'selected/INDEX_KS11.csv',index_col='date')
  patch=json.loads((B/'benchmark_patch/close_patch.json').read_text())
  assert patch['date']=='2022-01-03' and patch['metric']=='KOSPI_PRICE_INDEX_CLOSE'
  if patch['date'] not in benchmark.index:
   # Observed closing value from two dated publications. No invented OHLC.
   benchmark.loc[patch['date'],'raw_close']=patch['value']
 else:
  from quant_harness.investment.equities import normalize_chart
  bf,_=normalize_chart(json.loads((B/'us/^GSPC/yahoo.json').read_text()),'^GSPC');bf['date']=pd.to_datetime(bf.timestamp,utc=True).dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d');benchmark=bf.set_index('date')
 benchmark=benchmark.rename(columns={'raw_open':'open_reference','raw_close':'close_reference'})
 benchmark['open']=benchmark.open_reference;benchmark['close']=benchmark.close_reference
 c=policy['costs'][market];spec=ExecutionSpec(c['buy_fee_bps'],c['sell_fee_bps'],c['half_spread_bps'],c['impact_bps_at_1pct_adv'],c['max_impact_bps'],c['max_participation'],initial*.001)
 for mode in ('A','B','C','EQUAL_QUALIFIED_PROBE'):
  decision=next((d for d in originals.get(mode,{}).get('decisions',[]) if d['market']==market),None);weight=.025 if mode=='EQUAL_QUALIFIED_PROBE' else float(decision['weight'])
  account,fills,intents,detail=fixed_hold(frame,symbol,dates,weight,initial,spec);detail['symbol']=symbol;metric=performance(account,fills,detail,frame,benchmark,dates,initial)
  # This is checked before storing any fill. A D-1 target is not a guarantee
  # on actual next-open exposure. Controls have their own preregistered20% cap.
  if weight>0:
   first_nav=float(account.nav_krw.iloc[0]);open_exposure=detail['quantity']*float(fills.reference_open_krw.iloc[0])/min(float(initial),first_nav)
   cap=.2 if mode=='EQUAL_QUALIFIED_PROBE' else .025
   if open_exposure>cap:raise ValueError('next-open postcost exposure exceeds registered cap; do not store fills')
  folder=out/(market+'_'+mode);folder.mkdir(exist_ok=True);account.to_csv(folder/'nav_engine_legacy_column_names.csv',index=False);fills.to_csv(folder/'fills_engine_legacy_column_names.csv',index=False);intents.to_csv(folder/'unfilled_intents.csv',index=False)
  fill_records=[]
  for fill in fills.to_dict('records'):
   fill={**fill,'date':str(fill['date']),'currency':q['currency'],'client_order_id':digest({'session_input_hash':expected_hash,'market':market,'mode':mode,'symbol':symbol,'side':fill['side'],'date':str(fill['date'])})};store.put('completion_historical_fill',fill);fill_records.append(fill)
  result={'market':market,'currency':q['currency'],'symbol':symbol,'mode':mode,'entry':q['entry'],'exit':q['exit'],'holding_sessions':63,'initial_capital':initial,'target_weight':weight,'decision':decision,'detail':detail,'metrics':metric,'input_hash':expected_hash,'worker_hash':worker_hash,'quality':'BOUNDED_HISTORICAL_RECONSTRUCTION_PARTIAL_SOURCE_COVERAGE_NOT_CAUSAL_ALPHA','legacy_field_names':'_krw fields in reused generic arithmetic represent this account currency; accounts never combined','source_notes':q,'fills':fill_records,'auto_promotion':False};p=folder/'result.json'
  if p.exists():assert json.loads(p.read_text())==result,'Frozen output differs; new version required'
  else:p.write_text(json.dumps(result,indent=2,default=str))
  store.put('completion_historical_result',result);results.append(result);print(market,mode,symbol,weight,metric['fills'],metric['net_return'],flush=True)
(B/'results/summary.json').write_text(json.dumps(results,indent=2,default=str))
# The original Store cannot round-trip IEEE negative zero through JSONB.
# Preserve V1 and append canonical local V2 instead of mutating shared storage.
import subprocess
subprocess.run([sys.executable,str(Path(__file__).parent/'finalize_ledger.py')],check=True)

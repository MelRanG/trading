"""Separate exploratory Shadow lifecycle, using existing broker-free Paper.

The single operating CLI may observe these explicitly registered accounts only.
Research permission never changes the official portfolio/Paper eligibility policy.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib
import psycopg
from .store import Store
from .review_jobs import Queue
from .research import digest
from .discovery import instant,now
from .stockpaper import execute,reconcile,seal
from .opportunity import number
from .operations_data import strict_rows,ZONES
from .equities import settings,load_environment

DDL='''CREATE TABLE IF NOT EXISTS exploration_budget(day date,stage text,calls integer NOT NULL DEFAULT0,PRIMARY KEY(day,stage));'''.replace('DEFAULT0','DEFAULT 0')

def research_store(root):
    cfg=json.loads((Path(root)/'config/task8b_exploration.json').read_text())
    if cfg['mode']!='EXPLORATORY_SHADOW_ONLY' or cfg['live_execution_allowed'] or cfg['automatic_promotion']:raise ValueError('exploration authority boundary')
    store=Store('postgresql://quant_task8b_research@127.0.0.1:55432/'+cfg['research_database'],'TASK8B_RESEARCH_ONLY')
    with psycopg.connect(store.url) as conn:conn.execute(DDL)
    return store,cfg


def account_store(cfg,market):
    expected='quant_task3_task8b_explore_'+market.lower()
    if cfg['market_accounts'][market]!=expected:raise ValueError('only separate exploration accounts allowed')
    return Store('postgresql://quant_task8b_explore_'+market.lower()+'@127.0.0.1:55432/'+expected,'TASK8B_EXPLORATION_'+market)


def reserve(store,stage,total_limit,stage_limit):
    with psycopg.connect(store.url) as conn:
        # One DB row serializes the global daily reservation before provider I/O.
        conn.execute("INSERT INTO exploration_budget VALUES(CURRENT_DATE,'TOTAL',0) ON CONFLICT DO NOTHING")
        total=conn.execute("SELECT calls FROM exploration_budget WHERE day=CURRENT_DATE AND stage='TOTAL' FOR UPDATE").fetchone()[0]
        conn.execute('INSERT INTO exploration_budget VALUES(CURRENT_DATE,%s,0) ON CONFLICT DO NOTHING',(stage,))
        used=conn.execute('SELECT calls FROM exploration_budget WHERE day=CURRENT_DATE AND stage=%s FOR UPDATE',(stage,)).fetchone()[0]
        if total>=total_limit or used>=stage_limit:raise ValueError('exploration provider budget exhausted')
        conn.execute("UPDATE exploration_budget SET calls=calls+1 WHERE day=CURRENT_DATE AND stage IN ('TOTAL',%s)",(stage,))


def provider_call(root,store,cfg,client,stage,path,query,stage_limit=1):
    reserve(store,stage,cfg['daily_provider_calls'],stage_limit)
    payload=client._request('GET',path,query=query);raw=json.dumps(payload,sort_keys=True).encode();fingerprint=hashlib.sha256(raw).hexdigest();folder=Path(root)/'runtime/task8b/forward/raw';folder.mkdir(parents=True,exist_ok=True);dest=folder/(fingerprint+'.json')
    if not dest.exists():dest.write_bytes(raw)
    receipt={'source_hash':fingerprint,'available_at':now(),'path':str(dest.relative_to(root)),'stage':stage};store.put('exploration_api_receipt',receipt);return payload,receipt


def official_sessions(market,current):
    with psycopg.connect('postgresql://quant_ops@127.0.0.1:55432/quant_task3_ops',options='-c default_transaction_read_only=on') as conn:
        rows=conn.execute('SELECT day,opening,closing,source_hash FROM ops_session WHERE market=%s AND observed_at<=%s ORDER BY opening',(market,current)).fetchall()
    return [{'day':str(r[0]),'opening':r[1].isoformat(),'closing':r[2].isoformat(),'source_hash':r[3]} for r in rows]


def quote_events(raw,receipt,market,names,session,sealed_at,current):
    native={s.split('.')[0] if market=='KR' else s:s for s in names};currency='USD' if market=='US' else 'KRW';events={}
    for row in raw['result']:
        if row['symbol'] not in native:raise ValueError('unrequested quote identity')
        symbol=native[row['symbol']];t=instant(row['timestamp']);a=instant(receipt['available_at'])
        if row['currency']!=currency or not instant(sealed_at)<t<=a<=instant(current) or (instant(current)-t).total_seconds()>60:raise ValueError('future/stale/preseal quote or currency mismatch')
        if not instant(session['opening'])<=t<=instant(session['closing']):raise ValueError('outside verified regular session')
        price=float(row['lastPrice'])
        if not number(price) or price<=0:raise ValueError('invalid quote')
        if symbol in events:raise ValueError('duplicate quote')
        events[symbol]={'symbol':symbol,'asset_type':'ETF' if symbol in ('SPY','069500.KS') else 'EQUITY','currency':currency,'price':price,'event_at':row['timestamp'],'available_at':receipt['available_at'],'session_open':session['opening'],'session_close':session['closing'],'source':'TOSS_STOCK_QUOTE_OBSERVED','source_hash':receipt['source_hash']}
    if set(events)!=set(names):raise ValueError('incomplete quote set')
    return events


def checkpoint_result(entry,marks,session_count,checkpoints):
    """Only observed labels mature; count may be None if official chain missing."""
    if not marks or session_count is None:return {'status':'PENDING','reason':'NO_OBSERVED_MARK_OR_VERIFIED_SESSION_CHAIN'}
    if any(not m.get('corporate_actions_verified',False) for m in marks):return {'status':'PENDING','reason':'CORPORATE_ACTIONS_NOT_INDEPENDENTLY_VERIFIED','price_marks_observed':len(marks)}
    labels={}
    for count in checkpoints:
        eligible=[m for m in marks if m['completed_sessions']==count]
        if not eligible:labels[str(count)]={'status':'PENDING','reason':'EXACT_CHECKPOINT_MARK_NOT_OBSERVED'};continue
        row=eligible[0];labels[str(count)]={'status':'MATURE','net_return':row['nav']/entry['initial_capital']-1,'benchmark_return':row['benchmark_price']/entry['benchmark_entry']['price']-1,'mdd':min(m['nav']/max(entry['initial_capital'],max(x['nav'] for x in marks if x['completed_sessions']<=m['completed_sessions']))-1 for m in marks if m['completed_sessions']<=count),'cost_status':'Entry costs included; open checkpoint not liquidated. Exit cost appears only in actual synthetic Paper exit ledger; benchmark price-only gross' }
    return {'status':'PARTIAL_OR_MATURE' if any(v['status']=='MATURE' for v in labels.values()) else 'PENDING','labels':labels}


def _count_sessions(market,entered,closed):
    with psycopg.connect('postgresql://quant_ops@127.0.0.1:55432/quant_task3_ops',options='-c default_transaction_read_only=on') as conn:
        days=[r[0] for r in conn.execute('SELECT day FROM ops_session WHERE market=%s AND closing>%s AND closing<=%s ORDER BY closing',(market,entered,closed)).fetchall()]
        for a,b in zip(days,days[1:]):
            if not conn.execute('SELECT 1 FROM ops_session_edge WHERE market=%s AND prior_day=%s AND next_day=%s',(market,a,b)).fetchone():return None
    return len(days) if days else 0


def run_tick(root,*,client=None,current=None):
    root=Path(root);store,cfg=research_store(root)
    if not cfg['enabled']:return {'status':'DISABLED'}
    from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
    load_environment(root);client=client or TossOpenApiClient();clock=current or now();result=[];queue=Queue(store)
    with store.lock():
        with psycopg.connect(store.url) as conn:plans=conn.execute("SELECT r.record_id,r.payload FROM investment_record r LEFT JOIN investment_run s ON s.run_id=r.record_id WHERE r.kind='exploration_plan' AND COALESCE(s.status,'ACTIVE')<>'SUPERSEDED_UNFILLED' ORDER BY r.created_at").fetchall()
        for plan_id,plan in plans:
            market=plan['market'];account=account_store(cfg,market);sessions=official_sessions(market,clock);regular=next((s for s in sessions if instant(s['opening'])<=instant(clock)<instant(s['closing'])),None)
            identity=plan['paper_decision_id'];decision=account.get(identity)
            with psycopg.connect(account.url) as conn:
                complete=conn.execute('SELECT 1 FROM stock_nav WHERE decision_id=%s',(identity,)).fetchone();ok=reconcile(conn)
            if not ok:
                result.append({'market':market,'status':'HOLD_ONLY','reason':'RECONCILIATION_FAILED'});continue
            try:
                if not complete:
                    if decision['contract_hash']!=digest(settings(root)) or plan['exploration_policy_hash']!=digest(cfg) or plan.get('worker_hash')!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():raise ValueError('frozen exploration policy changed; reseal required')
                    if instant(clock)>instant(decision['sealed_at'])+timedelta(hours=settings(root)['decision_lifetime_hours']):
                        store.put('exploration_expiry',{'plan_id':plan_id,'reason':'UNFILLED_EXPIRED_NO_FORCED_RESEAL'});account.state(identity,'EXPIRED');result.append({'market':market,'status':'EXPIRED','orders':0});continue
                    if not regular:result.append({'market':market,'status':'WAIT_NEXT_REGULAR_PRICE','orders':0});continue
                    names=sorted(set(plan['weights'])|{plan['benchmark']});native=[s.split('.')[0] if market=='KR' else s for s in names]
                    raw,receipt=provider_call(root,store,cfg,client,'ENTRY_'+market,client.endpoint_map.quote_path,{'symbols':','.join(native)},cfg['maximum_entry_attempts_per_market_day']);events=quote_events(raw,receipt,market,names,regular,decision['sealed_at'],current or now())
                    sectors=plan.get('sectors') or {c['ticker']:c['sector'] for c in store.get(plan['catalog_id'])['candidates']}
                    exposure_guard(decision,events,cfg,settings(root),sectors)
                    outcome=execute(account,root,identity,[events[s] for s in plan['weights']],current or now())
                    if outcome['status']!='COMPLETE':result.append({'market':market,'status':outcome['status']});continue
                    entry={'plan_id':plan_id,'paper_decision_id':identity,'entered_at':max(e['event_at'] for s,e in events.items() if s in plan['weights']),'benchmark_entry':events[plan['benchmark']],'initial_capital':settings(root)[market]['initial_capital'],'outcome':outcome,'new_forward':True};entry_id=store.put('exploration_entry',entry,plan_id+':entry');result.append({'market':market,'status':'ENTERED_EXPLORATORY_ONLY','entry_id':entry_id})
                else:
                    # Recover a lost postfill receipt using immutable quote evidence,
                    # never reprice or fabricate benchmark execution.
                    with psycopg.connect(store.url) as conn:exists=conn.execute('SELECT record_id FROM investment_record WHERE record_id=%s',(plan_id+':entry',)).fetchone()
                    if not exists:
                        with psycopg.connect(account.url) as conn:nav=conn.execute('SELECT event_hash FROM stock_nav WHERE decision_id=%s',(identity,)).fetchone()
                        original_events=account.get(nav[0])['events'];source_hash=original_events[0]['source_hash']
                        with psycopg.connect(store.url) as conn:receipts=[r[0] for r in conn.execute("SELECT payload FROM investment_record WHERE kind='exploration_api_receipt' AND payload->>'source_hash'=%s",(source_hash,)).fetchall()]
                        if not receipts:raise ValueError('committed fill lacks benchmark source receipt; no invented recovery')
                        receipt=receipts[0];raw=json.loads((root/receipt['path']).read_text());session={'opening':original_events[0]['session_open'],'closing':original_events[0]['session_close']};names=sorted(set(plan['weights'])|{plan['benchmark']});events=quote_events(raw,receipt,market,names,session,decision['sealed_at'],receipt['available_at'])
                        if digest(sorted([events[s] for s in plan['weights']],key=lambda e:e['symbol']))!=digest(sorted(original_events,key=lambda e:e['symbol'])):raise ValueError('recovered quote evidence differs from committed fill')
                        outcome=account.get(identity+':outcome');entry={'plan_id':plan_id,'paper_decision_id':identity,'entered_at':max(e['event_at'] for s,e in events.items() if s in plan['weights']),'benchmark_entry':events[plan['benchmark']],'initial_capital':settings(root)[market]['initial_capital'],'outcome':outcome,'new_forward':True};store.put('exploration_entry',entry,plan_id+':entry');result.append({'market':market,'status':'POSTCOMMIT_ENTRY_RECOVERED_NO_NEW_FILL'})
                entry=store.get(plan_id+':entry')
                with psycopg.connect(store.url) as conn:
                    closed=conn.execute('SELECT record_id FROM investment_record WHERE record_id=%s',(plan_id+':closed',)).fetchone()
                    prior_marks=[r[0] for r in conn.execute("SELECT payload FROM investment_record WHERE kind='exploration_mark' AND payload->>'plan_id'=%s ORDER BY created_at",(plan_id,)).fetchall()]
                if closed:result.append({'market':market,'status':'CLOSED','record_id':closed[0]});continue
                if prior_marks and max(m['completed_sessions'] for m in prior_marks)>=max(cfg['holding_checkpoints_sessions']):
                    result.append(exit_tick(root,store,cfg,client,account,plan_id,plan,entry,regular,prior_marks[-1],current));continue
                completed=[s for s in sessions if instant(s['closing'])+timedelta(minutes=5)<=instant(clock) and instant(s['closing'])>instant(entry['entered_at'])]
                if not completed:continue
                session=completed[-1];mark_key=plan_id+':mark:'+session['day']
                with psycopg.connect(store.url) as conn:already=conn.execute('SELECT record_id FROM investment_record WHERE record_id=%s',(mark_key,)).fetchone()
                if already:continue
                count=_count_sessions(market,entry['entered_at'],session['closing'])
                if count is None:raise ValueError('missing verified official session chain')
                with psycopg.connect(account.url) as conn:
                    positions=dict(conn.execute('SELECT symbol,quantity FROM stock_position WHERE quantity>0').fetchall());cash=float(conn.execute('SELECT cash FROM stock_account').fetchone()[0]);last_fill=conn.execute('SELECT max(created_at) FROM stock_fill').fetchone()[0]
                if last_fill and last_fill>instant(session['closing']):raise ValueError('cannot reconstruct prefill historical position mark')
                prices={};refs=[]
                for symbol in sorted(set(positions)|{plan['benchmark']}):
                    native=symbol.split('.')[0] if market=='KR' else symbol;raw,receipt=provider_call(root,store,cfg,client,'MARK_'+market+'_'+symbol+'_'+session['day'],client.endpoint_map.candles_path,{'symbol':native,'interval':'1d','count':2,'before':session['closing'],'adjusted':'false'});frame=strict_rows(raw,symbol,'USD' if market=='US' else 'KRW',ZONES[market],session['day'])
                    if frame.date.iloc[-1]!=session['day']:raise ValueError('missing exact completed-session mark')
                    prices[symbol]=float(frame.close.iloc[-1]);refs.append(receipt)
                with psycopg.connect(store.url) as conn:clearances=[r[0] for r in conn.execute("SELECT payload FROM investment_record WHERE kind='exploration_ca_clearance' AND payload->>'plan_id'=%s",(plan_id,)).fetchall()]
                ca_verified=any(c.get('through_session','')>=session['day'] and c.get('source_class') in ('OFFICIAL_CORPORATE_ACTION_OBSERVATION','PIT_ADJUSTMENT_RECONCILIATION') and c.get('source_hash') and instant(c['available_at'])<=instant(current or now()) for c in clearances)
                mark={'plan_id':plan_id,'session':session['day'],'completed_sessions':count,'available_at':now(),'nav':cash+sum(float(q)*prices[s] for s,q in positions.items()),'cash':cash,'positions':{s:str(q) for s,q in positions.items()},'benchmark_price':prices[plan['benchmark']],'source_hashes':[r['source_hash'] for r in refs],'dividends_and_splits':'UNRECONCILED_ACTIONS_BLOCK_NEW_MARKS_IF_EVIDENCE_FOUND','return_basis':'PRICE_RETURN_NOT_TOTAL_RETURN','corporate_actions_verified':ca_verified};store.put('exploration_mark',mark,mark_key)
                with psycopg.connect(store.url) as conn:marks=[r[0] for r in conn.execute("SELECT payload FROM investment_record WHERE kind='exploration_mark' AND payload->>'plan_id'=%s ORDER BY created_at",(plan_id,)).fetchall()]
                scores=checkpoint_result(entry,marks,count,cfg['holding_checkpoints_sessions']);store.put('exploration_checkpoint',{'plan_id':plan_id,'session':session['day'],'evaluation':scores});queue.observe(plan_id,digest(mark))
                if count>=max(cfg['holding_checkpoints_sessions']):queue.enqueue('EXPLORATION_EXIT_DUE',{'plan_id':plan_id,'completed_sessions':count,'reason':'REGISTERED_MAX_HOLDING_REACHED'})
                result.append({'market':market,'status':'MARKED','sessions':count,'checkpoint_status':scores['status']})
            except Exception as exc:
                result.append({'market':market,'status':'HOLD_ONLY_OR_PENDING','reason':str(exc)[:180],'error_type':type(exc).__name__})
        receipt={'at':clock,'scope':'EXPLORATORY_SHADOW_ONLY','markets':result,'model_calls':0,'broker_orders':0};store.put('exploration_tick',receipt);folder=root/'runtime/task8b/forward';folder.mkdir(parents=True,exist_ok=True);(folder/'latest.json').write_text(json.dumps(receipt,indent=2,default=str));return receipt


def exit_tick(root,store,cfg,client,account,plan_id,plan,entry,regular,last_mark,current=None):
    """Registered horizon exit using the same isolated ledger, never an LLM order."""
    if plan['exploration_policy_hash']!=digest(cfg) or plan.get('worker_hash')!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():raise ValueError('registered exit policy/code changed; explicit review required')
    if not regular:return {'market':plan['market'],'status':'WAIT_EXIT_REGULAR_SESSION'}
    market=plan['market'];key=plan_id+':exit_plan'
    with psycopg.connect(store.url) as conn:prior=conn.execute('SELECT record_id FROM investment_record WHERE record_id=%s',(key,)).fetchone()
    if prior:exit_plan=store.get(key)
    else:
        prices={};marks={};adv={};receipts=[]
        for symbol in plan['weights']:
            native=symbol.split('.')[0] if market=='KR' else symbol;raw,receipt=provider_call(root,store,cfg,client,'EXIT_ADV_'+market+'_'+symbol,client.endpoint_map.candles_path,{'symbol':native,'interval':'1d','count':20,'before':regular['opening'],'adjusted':'false'});frame=strict_rows(raw,symbol,'USD' if market=='US' else 'KRW',ZONES[market],last_mark['session'])
            if len(frame)<20 or frame.date.iloc[-1]!=last_mark['session']:raise ValueError('fresh completed exit liquidity unavailable')
            marks[symbol]=float(frame.close.iloc[-1]);adv[symbol]=float((frame.close*frame.volume).mean());prices[symbol]={'meta':{'instrumentType':'EQUITY'}};receipts.append(receipt)
        analysis={'status':'CANDIDATES','weights':{},'execution_eligible':True,'prior_marks':marks,'adv20_d1':adv,'strategy_id':'TASK8B_REGISTERED_HORIZON_EXIT','input_hash':digest({'plan':plan_id,'marks':receipts}),'reason':'REGISTERED_126_SESSION_EXIT'}
        identity,payload=seal(account,root,market,analysis,prices,plan['catalog_id']);exit_plan={'paper_decision_id':identity,'plan_id':plan_id,'reason':'REGISTERED_HORIZON_EXIT','source_hash':digest(receipts)};store.put('exploration_exit_plan',exit_plan,key)
    identity=exit_plan['paper_decision_id'];decision=account.get(identity)
    with psycopg.connect(account.url) as conn:committed=conn.execute('SELECT 1 FROM stock_nav WHERE decision_id=%s',(identity,)).fetchone()
    if committed:
        # Existing Paper resumes its committed transaction before fresh I/O.
        outcome=execute(account,root,identity,[],current or now());store.put('exploration_closed',{'plan_id':plan_id,'exit_id':identity,'outcome':outcome,'price_only_dividend_scope':True},plan_id+':closed');return {'market':market,'status':'CLOSED_RECOVERED'}
    names=sorted(set(plan['weights'])|{plan['benchmark']});native=[s.split('.')[0] if market=='KR' else s for s in names];raw,receipt=provider_call(root,store,cfg,client,'EXIT_'+market,client.endpoint_map.quote_path,{'symbols':','.join(native)},cfg['maximum_entry_attempts_per_market_day']);events=quote_events(raw,receipt,market,names,regular,decision['sealed_at'],current or now())
    outcome=execute(account,root,identity,[events[s] for s in plan['weights']],current or now())
    if outcome['status']=='COMPLETE':
        store.put('exploration_closed',{'plan_id':plan_id,'exit_id':identity,'outcome':outcome,'benchmark_exit':events[plan['benchmark']],'net_return':float(outcome['nav'])/entry['initial_capital']-1,'benchmark_price_return':events[plan['benchmark']]['price']/entry['benchmark_entry']['price']-1,'price_only_dividend_scope':True},plan_id+':closed')
        return {'market':market,'status':'CLOSED','net_return':float(outcome['nav'])/entry['initial_capital']-1}
    return {'market':market,'status':outcome['status']}


def exposure_guard(decision,events,cfg,paper_cfg,sectors):
    """Conservative post-cost exposure upper bound before an atomic Paper buy.

    The existing Paper's80/20caps do not replace the exploration30/5caps.
    This bound uses that unchanged executor's maximum impact and fee formula.
    """
    if decision['opening_positions']:raise ValueError('initial exploration probe expects an empty account')
    market=decision['market'];cost=paper_cfg['US_execution_assumptions'] if market=='US' else paper_cfg['execution_assumptions']
    slippage=(cost['half_spread_bps']+cost['max_impact_bps'])/10000;fee=cost['buy_fee_bps']/10000
    notional={i['symbol']:float(i['delta_quantity'])*events[i['symbol']]['price'] for i in decision['intents']}
    if any(not number(v) or v<0 for v in notional.values()):raise ValueError('nonfinite probe value')
    nav_lower=float(decision['opening_cash'])-sum(notional.values())*(slippage+(1+slippage)*fee)
    if nav_lower<=0:raise ValueError('insufficient postcost cash')
    weights={s:v/nav_lower for s,v in notional.items()}
    if sum(weights.values())>cfg['gross_cap'] or any(w>cfg['single_name_cap'] for w in weights.values()):raise ValueError('exploration postcost gross/name cap')
    if set(weights)-sectors.keys():raise ValueError('missing frozen sector map')
    if any(sum(w for s,w in weights.items() if sectors[s]==sector)>cfg['sector_cap'] for sector in set(sectors.values())):raise ValueError('exploration postcost sector cap')
    return weights

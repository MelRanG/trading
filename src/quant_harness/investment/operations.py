"""One resumable KR/US operating tick above unchanged stock strategy/ledger.

The operation lock is connection-scoped. A crash releases it; immutable stage
receipts and decision/session links prevent a restarted process making a second
judgment after a committed seal/fill. No broker write functions are imported.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
import json
import time
import psycopg
from psycopg.rows import dict_row
from .operations_data import Warehouse,ZONES,phase,collect_toss,encode_prices,bounded_client
from .equities import settings,load_environment,us_catalog,kr_catalog,analyze_stocks,market_news
from .stockpaper import seal,execute,reconcile
from .store import Store
from .discovery import now,instant,company_discover
from .research import digest


def latest_completed(calendar,current):
    eligible=[r for r in calendar['sessions'] if instant(r['closing'])+timedelta(minutes=5)<=instant(current)]
    if not eligible:raise ValueError('no verified completed session')
    return max(eligible,key=lambda r:r['day'])


def quote_events(warehouse,client,market,symbols,session,budget):
    if not symbols:return []
    names={(s.split('.')[0] if market=='KR' else s):s for s in symbols}
    raw,receipt=warehouse.call(client,market,client.endpoint_map.quote_path,{'symbols':','.join(names)},budget)
    rows=raw['result'];currency=settings(warehouse.root)[market]['currency'];events=[]
    for row in rows:
        if row['symbol'] not in names or row['currency']!=currency:raise ValueError('quote identity/currency')
        events.append({'symbol':names[row['symbol']],'asset_type':'EQUITY','currency':currency,'price':row['lastPrice'],
          'event_at':row['timestamp'],'available_at':receipt['available_at'],'session_open':session['opening'],
          'session_close':session['closing'],'source':'TOSS_STOCK_QUOTE_OBSERVED','source_hash':receipt['source_hash']})
    if len(events)!=len(symbols) or len({e['symbol'] for e in events})!=len(symbols):raise ValueError('incomplete quotes')
    return events


def decision_for_session(url,market,day):
    """Recover even if killed after seal commit but before operation checkpoint."""
    with psycopg.connect(url,row_factory=dict_row,options='-c default_transaction_read_only=on') as conn:
        rows=conn.execute("SELECT r.record_id,r.payload FROM investment_record r JOIN investment_run s ON s.run_id=r.record_id WHERE r.kind='stock_decision' AND s.status NOT IN ('EXPIRED','INVALIDATED_VERSION','CONFIG_CHANGED') ORDER BY r.created_at DESC").fetchall()
        pending=conn.execute("SELECT run_id FROM investment_run WHERE status='DECIDED' ORDER BY updated_at LIMIT 1").fetchone()
    if pending:return pending['run_id']
    for row in rows:
        if instant(row['payload']['sealed_at']).astimezone(ZoneInfo(ZONES[market])).date().isoformat()==day:return row['record_id']
    return None



def recover_session(warehouse,store,market,day):
    """A decision may be sealed on Friday for Monday: use its assigned session,
    never equate the seal's wall-clock date with the execution-session identity.
    """
    link=warehouse.lookup('decision:'+market+':'+day)
    manifest=warehouse.lookup('manifest:'+market+':'+day)
    excluded=('EXPIRED','INVALIDATED_VERSION','CONFIG_CHANGED')
    with psycopg.connect(store.url) as conn:
        if link:
            state=conn.execute('SELECT status FROM investment_run WHERE run_id=%s',(link['decision_id'],)).fetchone()
            if state and state[0] not in excluded:return link['decision_id']
        if manifest:
            analysis=store.get(manifest['quant_id'])
            row=conn.execute("SELECT r.record_id FROM investment_record r JOIN investment_run s ON s.run_id=r.record_id WHERE r.kind='stock_decision' AND r.payload->'analysis'=%s::jsonb AND s.status NOT IN ('EXPIRED','INVALIDATED_VERSION','CONFIG_CHANGED') ORDER BY r.created_at DESC LIMIT 1",(json.dumps(analysis),)).fetchone()
            if row:return row[0]
    return decision_for_session(store.url,market,day)

def mark_account(warehouse,source_url,market,session,prices):
    """Persist actual ledger-at-close marks, never mark a future/intraday close.

    A session with fills created after its close cannot use today's account state.
    Those historical marks stay missing; no reconstructed positions are invented.
    """
    key='mark:'+market+':'+session['day']
    if warehouse.lookup(key):return warehouse.lookup(key)
    with psycopg.connect(source_url,options='-c default_transaction_read_only=on') as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        account=conn.execute('SELECT cash FROM stock_account').fetchone()
        if not account:return None
        if conn.execute('SELECT 1 FROM stock_fill WHERE created_at>%s LIMIT 1',(session['closing'],)).fetchone():return None
        positions=dict(conn.execute('SELECT symbol,quantity FROM stock_position WHERE quantity>0').fetchall())
        fills=conn.execute('SELECT client_order_id,cash_delta FROM stock_fill ORDER BY client_order_id').fetchall()
    for symbol in positions:
        if symbol not in prices or prices[symbol]['frame'].date.iloc[-1]!=session['day']:return None
        frame=prices[symbol]['frame']
        # New splits need explicit corporate-action processing before quantities
        # can be reconciled. Never apply adjusted prices to unadjusted shares.
        if len(frame)>1 and abs(float(frame.adjustment_factor.iloc[-1]/frame.adjustment_factor.iloc[-2])-1)>.001:
            raise ValueError('corporate action requires reconciliation')
    nav=float(account[0])+sum(float(q)*float(prices[s]['frame'].raw_close.iloc[-1]) for s,q in positions.items())
    benchmark=settings(warehouse.root)[market]['benchmark'];item=prices.get(benchmark)
    label={'market':market,'session':session['day'],'nav':nav,'observed_at':now(),'calendar_hash':digest(session),
           'source_hash':digest({'prices':{s:v['receipt'] for s,v in prices.items()},'fills':fills}),
           'benchmark':float(item['frame'].raw_close.iloc[-1]) if item else None,
           'return_convention':'PAPER_LEDGER_PRICE_RETURN_TRANSACTION_COSTS_INCLUDED_DIVIDEND_CASH_NOT_MODELED',
           'sector':None}
    warehouse.point(key,'ops_account_mark',label);return label


def labels_for(warehouse,source_url,decision_id):
    with psycopg.connect(source_url,row_factory=dict_row,options='-c default_transaction_read_only=on') as conn:
        decision=conn.execute('SELECT payload FROM investment_record WHERE record_id=%s',(decision_id,)).fetchone()['payload']
        nav=conn.execute('SELECT nav,created_at FROM stock_nav WHERE decision_id=%s',(decision_id,)).fetchone()
    if not nav:return None
    market=decision['market'];entry=nav['created_at'].astimezone(ZoneInfo(ZONES[market])).date().isoformat()
    with psycopg.connect(warehouse.url) as conn:
        sessions=conn.execute('SELECT day FROM ops_session WHERE market=%s AND day>=%s ORDER BY day',(market,entry)).fetchall()
        edges={(a.isoformat(),b.isoformat()) for a,b in conn.execute('SELECT prior_day,next_day FROM ops_session_edge WHERE market=%s',(market,)).fetchall()}
    days=[r[0].isoformat() for r in sessions]
    if entry not in days:return None
    # Missing official adjacency after an outage must not compress 5 sessions
    # into fewer known dates. Keep only the verified contiguous prefix.
    for i,(a,b) in enumerate(zip(days,days[1:])):
        if (a,b) not in edges:
            days=days[:i+1];break
    marks={d:warehouse.lookup('mark:'+market+':'+d) for d in days}
    # Entry starts at committed fill NAV, later points are observed close NAV.
    path={entry:float(nav['nav'])};observed={entry:nav['created_at'].isoformat()};bench={}
    for day,mark in marks.items():
        if not mark:continue
        if day!=entry:path[day]=mark['nav'];observed[day]=mark['observed_at']
        # The entry NAV is intraday fill NAV. A closing benchmark quote would
        # start at a different time and produce spurious excess return.
        if day!=entry and mark.get('benchmark') is not None:bench[day]=mark['benchmark']
    return {'decision_id':decision_id,'calendar_verified':True,'entry_session':entry,'sessions':days,
        'available_at':now(),'observed_at_by_session':observed,'nav':path,'benchmark':bench,
        'source_hash':digest({'marks':marks,'entry_nav':str(nav['nav'])}),'evidence_class':'ACTUAL_FORWARD_PAPER_PRICE_ONLY',
        'forecast_actuals':{},'counterfactuals':{},'limitations':['No invented numerical forecasts','Sector unavailable','Synchronized benchmark at intraday entry unavailable; excess return unscorable','Account continuation includes subsequent approved decisions, not isolated thesis attribution','Dividends not credited to Paper ledger','Entry NAV is fill NAV, subsequent marks are close NAV']}


def review_market(warehouse,url,review_url,market):
    from .review import Source
    from .review_engine import run_cycle
    results=[]
    for identity in Source(url).decisions()[-20:]:
        try:
            labels=labels_for(warehouse,url,identity)
            label_hash=digest(labels) if labels else 'PENDING'
            # availability clocks do not cause a repeated evaluation every tick.
            semantic={k:v for k,v in (labels or {}).items() if k!='available_at'}
            key='review:'+identity+':'+digest(semantic)
            prior=warehouse.lookup(key)
            if prior:results.append(prior);continue
            result=run_cycle(warehouse.root,url,review_url,identity,labels=labels)
            receipt={'decision_id':identity,'proposal_status':result['proposal_status'],'outcome_status':result['outcome_status'],
                     'label_hash':label_hash,'market':market,'at':now()}
            warehouse.point(key,'ops_review_receipt',receipt);results.append(receipt)
        except Exception as exc:
            results.append({'decision_id':identity,'status':'REVIEW_FAILED_OR_BLOCKED','error_type':type(exc).__name__})
    return results


def market_tick(warehouse,client,cfg,market,source_url,review_url):
    contract=settings(warehouse.root);budget=cfg['provider_daily_calls'][market]
    calendar=warehouse.calendar(client,market,budget);current=now();mode,active=phase(calendar['sessions'],current)
    completed=latest_completed(calendar,current)
    pinned=warehouse.lookup('policy:'+market)
    if pinned and pinned['contract_hash']!=digest(contract):raise ValueError('registered strategy configuration changed; explicit approval required')
    if not pinned:warehouse.point('policy:'+market,'ops_policy_pin',{'contract_hash':digest(contract),'observed_at':now()})
    warehouse.watch(market,contract[market]['seed_symbols'],contract[market]['benchmark'],cfg['maximum_watch'][market])
    folder=warehouse.root/'runtime/task5'/market;folder.mkdir(parents=True,exist_ok=True)
    catalog=warehouse.lookup('catalog:'+market)
    if not catalog or instant(current)-instant(catalog['ops_observed_at'])>timedelta(hours=cfg['catalog_ttl_hours']):
        warehouse.reserve('CATALOG_'+market,2)
        try:
            catalog=us_catalog(folder/'catalog') if market=='US' else kr_catalog(folder/'catalog')
            if not catalog['rows']:raise ValueError('empty catalog')
            catalog['ops_observed_at']=now();warehouse.point('catalog:'+market,'ops_catalog',catalog)
            warehouse.discover(market,catalog,cfg['discovery_batch'],cfg['maximum_watch'][market])
        except Exception:
            warehouse.failure('CATALOG_'+market);raise
    store=Store(source_url,market+'_STOCKS')
    # Every tick reconciles even when closed; account mismatch blocks this market.
    with psycopg.connect(source_url) as conn:
        from .stockpaper import initialize
        initialize(store,contract,market)
        if not reconcile(conn):
            conn.execute("UPDATE stock_account SET status='HOLD_ONLY'")
            raise ValueError('ledger mismatch HOLD_ONLY')
    symbols=contract[market]['seed_symbols']+[contract[market]['benchmark']]
    snapshot=warehouse.lookup('inputs:'+market+':'+completed['day'])
    if snapshot:
        from .operations_data import decode_prices
        prices=decode_prices(snapshot['prices'])
    else:
        prices=collect_toss(warehouse,client,market,symbols,completed,budget)
        snapshot={'prices':encode_prices(prices),'session':completed,'observed_at':now(),'historical_membership_verified':False}
        warehouse.point('inputs:'+market+':'+completed['day'],'ops_frozen_inputs',snapshot)
    qualification_key='qualification:'+market+':'+completed['day']
    qualification=warehouse.lookup(qualification_key)
    if not qualification:
        with psycopg.connect(warehouse.url) as conn:
            candidate=conn.execute("SELECT symbol FROM ops_watch WHERE market=%s AND role='RESEARCH_UNQUALIFIED' ORDER BY observed_at,symbol LIMIT 1",(market,)).fetchone()
        if candidate:
            try:
                researched=collect_toss(warehouse,client,market,[candidate[0]],completed,budget)
                qualification={'symbol':candidate[0],'status':'DATA_QUALIFIED_RESEARCH_ONLY','snapshot_hash':digest(encode_prices(researched)),'execution_eligible':False,'at':now()}
                with psycopg.connect(warehouse.url) as conn:conn.execute("UPDATE ops_watch SET role='RESEARCH_QUALIFIED' WHERE market=%s AND symbol=%s",(market,candidate[0]))
            except Exception as exc:
                qualification={'symbol':candidate[0],'status':'DATA_INSUFFICIENT','error_type':type(exc).__name__,'execution_eligible':False,'at':now()}
            warehouse.point(qualification_key,'ops_research_qualification',qualification)
    if qualification and qualification['status']=='DATA_INSUFFICIENT':
        with psycopg.connect(warehouse.url) as conn:
            conn.execute("UPDATE ops_watch SET role='RESEARCH_DATA_BLOCKED' WHERE market=%s AND symbol=%s AND role='RESEARCH_UNQUALIFIED'",(market,qualification['symbol']))
    mark=mark_account(warehouse,source_url,market,completed,prices)
    result={'market':market,'phase':mode,'last_complete_session':completed['day'],'price_symbols':len(prices),'research_qualification':qualification,'mark_status':'SAVED' if mark else 'UNAVAILABLE_LEDGER_AT_CLOSE'}
    # Select the next known regular session after the last completed one. Analysis
    # may run before open, but execution only sees a later regular price event.
    next_rows=[r for r in calendar['sessions'] if instant(r['opening'])>instant(completed['closing'])]
    next_session=min(next_rows,key=lambda r:r['opening']) if next_rows else None
    if not next_session:raise ValueError('next official session unavailable')
    with psycopg.connect(source_url,options='-c default_transaction_read_only=on') as conn:
        pending=conn.execute("SELECT run_id FROM investment_run WHERE status='DECIDED' ORDER BY updated_at LIMIT 1").fetchone()
    if pending:
        old=store.get(pending[0])
        if instant(now())>instant(old['sealed_at'])+timedelta(hours=contract['decision_lifetime_hours']):
            store.put('stock_expiry_followup',{'decision_id':pending[0],'at':now(),'reason':'EXPIRED_UNFILLED_DECISION_NO_NEW_ORDER'})
            store.state(pending[0],'EXPIRED')
        else:
            from .stockpaper import algorithm_fingerprint
            if old.get('algorithm_hash')!=algorithm_fingerprint():execute(store,warehouse.root,pending[0],[])
    identity=recover_session(warehouse,store,market,next_session['day'])
    if not identity:
        quant=analyze_stocks(prices,contract,market)
        listed={r['symbol'] for r in catalog['rows'] if r.get('common_stock_verified')} if market=='US' else {r['stock_code']+'.KS' for r in catalog['rows']}
        if any(s not in listed for s in contract[market]['seed_symbols']):raise ValueError('strategy listing not verified')
        if not quant['execution_eligible']:raise ValueError('quant inputs not eligible')
        catalog_id=store.put('stock_universe_observation',catalog)
        quant_id=store.put('stock_quant_analysis',quant)
        evidence_key='evidence:'+market+':'+next_session['day'];evidence=warehouse.lookup(evidence_key)
        if not evidence:
            warehouse.reserve('RSS_'+market,2)
            records,receipts=market_news(folder/'news',market)
            evidence={'records':records,'receipts':receipts,'observed_at':now()}
            warehouse.point(evidence_key,'ops_evidence',evidence)
        evidence_id=store.put('stock_evidence_collection',evidence)
        company_key='company:'+market+':'+next_session['day']
        company=warehouse.lookup(company_key)
        if not company:
            try:
                warehouse.reserve('LLM_'+market,cfg['company_model_calls_per_market_day'])
                company=company_discover(evidence['records'][:12],now(),skills='catalyst')
                usage={'input_tokens':0,'output_tokens':0,'cached_input_tokens':0}
                for line in company.get('events','').splitlines():
                    try:event=json.loads(line)
                    except ValueError:continue
                    for k,v in event.get('usage',{}).items():
                        if k in usage:usage[k]+=v
                company['measured_usage']=usage
                company['hard_token_budget_enforced']=False
                if usage['input_tokens']+usage['output_tokens']>cfg['company_token_budget_per_call']:
                    company.update(status='ABSTAIN',reason='MEASURED_TOKEN_BUDGET_EXCEEDED',candidates=[])
                    warehouse.failure('LLM_'+market,True)
                warehouse.point(company_key,'ops_company_analysis',company)
            except Exception as exc:
                company={'status':'ABSTAIN','reason':'LLM_FAILED_OR_BUDGET_RESERVED','error_type':type(exc).__name__,'candidates':[]}
                warehouse.point(company_key,'ops_company_analysis',company)
        company_id=store.put('stock_company_analysis',company)
        warehouse.point('manifest:'+market+':'+next_session['day'],'ops_preseal_manifest',{'quant_id':quant_id,'company_id':company_id,'evidence_id':evidence_id,'catalog_id':catalog_id,'ops_snapshot_hash':digest(snapshot)})
        with store.lock():identity,decision=seal(store,warehouse.root,market,quant,prices,catalog_id)
        store.put('stock_decision_lineage',{'decision_id':identity,'quant_id':quant_id,'company_id':company_id,'evidence_id':evidence_id,'catalog_id':catalog_id,
          'company_execution':'SHADOW_UNTIL_VERIFIED_RULE_AND_PIT_INPUTS','etf_trading_allowed':False,'ops_snapshot_hash':digest(snapshot)},identity+':lineage')
    decision=store.get(identity)
    try:store.get(identity+':lineage')
    except ValueError:
        manifest=warehouse.lookup('manifest:'+market+':'+next_session['day'])
        if not manifest:raise ValueError('sealed decision missing lineage and frozen preseal manifest')
        store.put('stock_decision_lineage',{'decision_id':identity,**manifest,'company_execution':'SHADOW_UNTIL_VERIFIED_RULE_AND_PIT_INPUTS','etf_trading_allowed':False},identity+':lineage')
    # Repair a lost post-seal checkpoint without changing the decision itself.
    warehouse.point('decision:'+market+':'+next_session['day'],'ops_decision_link',{'decision_id':identity,'session':next_session['day'],'market':market})
    with psycopg.connect(source_url,options='-c default_transaction_read_only=on') as conn:
        accounted=conn.execute('SELECT 1 FROM stock_nav WHERE decision_id=%s',(identity,)).fetchone()
    if not accounted and not decision['intents'] and decision['opening_positions']:
        outcome={'status':'NO_REBALANCE_HOLDING','reason':'NO_ORDER_INTENTS; close NAV recorded separately'}
        store.state(identity,'HOLD_NO_REBALANCE',outcome)
    elif accounted or (not decision['intents'] and not decision['opening_positions']):
        outcome=execute(store,warehouse.root,identity,[])
    elif mode=='REGULAR':
        symbols=sorted(set(decision['opening_positions'])|{i['symbol'] for i in decision['intents']})
        events=quote_events(warehouse,client,market,symbols,active,budget)
        store.put('stock_quote_collection',{'decision_id':identity,'events':events})
        outcome=execute(store,warehouse.root,identity,events)
    else:outcome={'status':'WAITING_NEXT_PRICE_EVENT'}
    result.update(decision_id=identity,paper_status=outcome['status'],reviews=review_market(warehouse,source_url,review_url,market),broker_mutation_calls=0)
    return result


def tick(root,ops_url,sources,review_url):
    load_environment(root);root=Path(root);cfg=json.loads((root/'config/task5_operations.json').read_text())
    if cfg['live_execution_allowed'] or cfg['automatic_promotion']:raise ValueError('research/Paper scope required')
    warehouse=Warehouse(ops_url,root);started=time.monotonic();results=[]
    from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
    with warehouse.store.lock():
        for market in cfg['markets']:
            try:result=market_tick(warehouse,bounded_client(warehouse,market,cfg['provider_daily_wire_calls'][market]),cfg,market,sources[market],review_url)
            except Exception as exc:
                result={'market':market,'status':'HOLD_ONLY_OR_ABSTAIN','error_type':type(exc).__name__,'reason':str(exc)[:160] if isinstance(exc,ValueError) else 'PROVIDER_OR_DATABASE_FAILURE','at':now()}
            if 'reviews' not in result:
                try:result['reviews']=review_market(warehouse,sources[market],review_url,market)
                except Exception as exc:result['review_status']='FAILED_'+type(exc).__name__
            warehouse.store.put('ops_tick_market',result);results.append(result)
        from .operations_backup import due_backup
        from .operations_experiment import execute_common,worker_hash
        request=warehouse.lookup('experiment:pending')
        experiment=None
        retry_key='experiment:attempted:'+datetime.now(timezone.utc).date().isoformat()
        if request and not warehouse.lookup(retry_key):
            try:
                if request['worker_hash']!=worker_hash(root):raise ValueError('registered worker changed; explicit follow-up required')
                experiment=execute_common(root,warehouse,request['snapshot'],request['contract'])
            except Exception as exc:
                experiment={'status':'BLOCKED','error_type':type(exc).__name__,'reason':str(exc)[:120] if isinstance(exc,ValueError) else 'WORKER_FAILURE'}
            warehouse.point(retry_key,'ops_experiment_retry',{**experiment,'receipt_type':'DAILY_EXPERIMENT_RETRY','attempted_on_utc':datetime.now(timezone.utc).date().isoformat()})
        try:backup_receipt=due_backup(warehouse,cfg['backup_interval_hours'])
        except Exception as exc:backup_receipt={'status':'BACKUP_FAILED','error_type':type(exc).__name__}
        with psycopg.connect(ops_url) as conn:
            size=conn.execute('SELECT pg_database_size(current_database())').fetchone()[0]
            budgets=conn.execute('SELECT provider,calls,failures FROM ops_budget WHERE day=CURRENT_DATE ORDER BY provider').fetchall()
            models=conn.execute("SELECT payload FROM investment_record WHERE kind='ops_company_analysis' AND created_at::date=CURRENT_DATE").fetchall()
            usage={k:sum(r[0].get('measured_usage',{}).get(k,0) for r in models) for k in ('input_tokens','output_tokens','cached_input_tokens')}
            model_failures=sum(r[0].get('status')=='FAILED' for r in models)
        receipt={'at':now(),'experiment':experiment,'backup':backup_receipt,'markets':results,'elapsed_seconds':time.monotonic()-started,'database_bytes':size,'provider_request_reservations':budgets,'measured_model_usage':usage,'model_failures':model_failures,'model_money_cost':None,'hard_model_token_cap':False,
                 'llm_status':'DAILY_CALL_LIMIT_MEASURED_TOKEN_CEILING_NO_HARD_CLI_CAP','broker_mutation_calls':0}
        warehouse.store.put('ops_tick',receipt)
        path=root/'runtime/task5/latest_tick.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(receipt,indent=2,default=str))
        return receipt

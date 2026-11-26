"""Only the registered Task8 isolated accounts may accept portfolio proposals."""
from pathlib import Path
import json,hashlib,re
from urllib.parse import urlsplit
from .decision import instant
from .research import digest
from .stockpaper import seal


def seal_shadow(store,root,decision,prices,catalog_id):
    root=Path(root);cfg=json.loads((root/'config/task8_portfolio.json').read_text());payload={k:v for k,v in decision.items() if k!='decision_hash'}
    if decision['decision_hash']!=digest(payload) or decision['policy_hash']!=digest(cfg):raise ValueError('immutable portfolio contract mismatch')
    market=decision['market']
    if urlsplit(store.url).path!='/'+cfg['market_accounts'][market]:raise ValueError('registered isolated Shadow account required')
    if decision['execution_authority']!='SHADOW_ONLY' or decision['live_execution_allowed'] or decision['currency']!=cfg['account_currencies'][market]:raise ValueError('Shadow authority or currency mismatch')
    targets=decision['weights'];marks={};adv={}
    for symbol in targets:
        row=prices[symbol]
        if not re.fullmatch('[0-9a-f]{64}',row.get('source_hash','')):raise ValueError('price source hash required')
        if instant(row['available_at'])>instant(decision['at']) or instant(row['session_close'])>instant(row['available_at']):raise ValueError('postdecision or incomplete-session price data')
        if (instant(decision['at'])-instant(row['session_close'])).total_seconds()>cfg['max_evidence_age_hours']*3600:raise ValueError('stale completed price session')
        frame=row['frame']
        marks[symbol]=float(frame.raw_close.iloc[-1]);adv[symbol]=float((frame.raw_close*frame.volume).tail(20).mean())
    analysis={'status':'CANDIDATES' if decision['status']=='TARGETS' else 'ABSTAIN','weights':targets,'execution_eligible':decision['status']=='TARGETS','prior_marks':marks,'adv20_d1':adv,'strategy_id':'TASK8_SHADOW_V1','input_hash':decision['input_hash'],'reason':decision['status'],'portfolio_hash':decision['decision_hash'],'portfolio_policy_hash':decision['policy_hash'],'portfolio_algorithm_hash':hashlib.sha256((Path(__file__).parent/'decision.py').read_bytes()).hexdigest(),'portfolio_bridge_hash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    return seal(store,root,market,analysis,prices,catalog_id)


def observe_shadow_accounts(root):
    """Daily cash observations; non-cash accounts require new verified marks.

    No fill is forced, old prices never mark new holdings, and calendar dates
    are not represented as official trading sessions.
    """
    from datetime import datetime,timezone
    from zoneinfo import ZoneInfo
    import psycopg
    from .store import Store
    from .stockpaper import reconcile
    root=Path(root);cfg=json.loads((root/'config/task8_portfolio.json').read_text())
    research=Store('postgresql://quant_task8_research@127.0.0.1:55432/'+cfg['research_database'],'TASK8_RESEARCH_ONLY');now=datetime.now(timezone.utc);rows=[]
    for market,database in cfg['market_accounts'].items():
        url='postgresql://quant_task8_shadow_'+market.lower()+'@127.0.0.1:55432/'+database
        local_day=now.astimezone(ZoneInfo('America/New_York' if market=='US' else 'Asia/Seoul')).date().isoformat();identity='task8-shadow-observation-'+market+'-'+local_day
        with psycopg.connect(research.url) as conn:prior=conn.execute('SELECT record_id FROM investment_record WHERE record_id=%s',(identity,)).fetchone()
        if prior:rows.append({'market':market,'status':'ALREADY_OBSERVED','record_id':identity});continue
        with psycopg.connect(url) as conn:
            cash,currency=conn.execute('SELECT cash,currency FROM stock_account').fetchone();ok=reconcile(conn);positions=dict(conn.execute('SELECT symbol,quantity FROM stock_position WHERE quantity>0').fetchall())
        payload={'market':market,'currency':currency,'observed_at':now.isoformat(),'calendar_date_local':local_day,'official_trading_session':'NOT_ASSIGNED','cash':str(cash),'positions':{s:str(v) for s,v in positions.items()},'nav':str(cash) if ok and not positions else None,'status':'HOLD_ONLY' if not ok else 'PENDING_FRESH_MARKS' if positions else 'CASH_OBSERVED','orders':0}
        research.put('task8_shadow_observation',payload,identity);rows.append({'record_id':identity,**payload})
    return rows


def execute_shadow(store,root,identity,events,current=None):
    """Changed policy/code invalidates pending fills; committed NAV stays recoverable."""
    import psycopg
    from .stockpaper import execute
    cfg=json.loads((Path(root)/'config/task8_portfolio.json').read_text());decision=store.get(identity)
    if urlsplit(store.url).path!='/'+cfg['market_accounts'][decision['market']]:raise ValueError('registered isolated Shadow account required')
    with psycopg.connect(store.url) as conn:
        complete=conn.execute('SELECT 1 FROM stock_nav WHERE decision_id=%s',(identity,)).fetchone()
        state=conn.execute('SELECT status FROM investment_run WHERE run_id=%s',(identity,)).fetchone()
    if complete:return execute(store,root,identity,events,current)
    analysis=decision['analysis']
    changed=analysis.get('portfolio_policy_hash')!=digest(cfg) or analysis.get('portfolio_algorithm_hash')!=hashlib.sha256((Path(__file__).parent/'decision.py').read_bytes()).hexdigest() or analysis.get('portfolio_bridge_hash')!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if changed or (state and state[0]=='INVALIDATED_VERSION'):
        result={'status':'HOLD_ONLY','reason':'TASK8_POLICY_OR_CODE_CHANGED_RESEAL_REQUIRED','orders':0}
        store.put('task8_pending_version_veto',{'decision_id':identity,**result});store.state(identity,'INVALIDATED_VERSION',result);return result
    return execute(store,root,identity,events,current)

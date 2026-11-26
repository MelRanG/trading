"""Currency-separated individual-stock Paper ledger with atomic fill + NAV.

The legacy singleton KRW/ETF adapter is deliberately not used for USD stocks.
This ledger never calls broker mutation endpoints.
"""
from decimal import Decimal, ROUND_FLOOR
from datetime import datetime,timezone,timedelta
import json
import psycopg
from psycopg.rows import dict_row
from .research import digest
from .discovery import instant,now
from .equities import settings

DDL='''
CREATE TABLE IF NOT EXISTS stock_account (id integer PRIMARY KEY CHECK(id=1), market text NOT NULL,currency text NOT NULL,
 initial numeric NOT NULL CHECK(initial>0),cash numeric NOT NULL CHECK(cash>=0),status text NOT NULL);
CREATE TABLE IF NOT EXISTS stock_position (symbol text PRIMARY KEY,quantity numeric NOT NULL CHECK(quantity>=0));
CREATE TABLE IF NOT EXISTS stock_fill (client_order_id text PRIMARY KEY,decision_id text NOT NULL,symbol text NOT NULL,side text NOT NULL,
 quantity numeric NOT NULL CHECK(quantity>0),price numeric NOT NULL CHECK(price>0),fee numeric NOT NULL CHECK(fee>=0),cash_delta numeric NOT NULL,
 event_hash text NOT NULL,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS stock_nav (decision_id text PRIMARY KEY,cash numeric NOT NULL,positions_value numeric NOT NULL,nav numeric NOT NULL,
 event_hash text NOT NULL,status text NOT NULL,created_at timestamptz NOT NULL DEFAULT now());
'''


def algorithm_fingerprint():
    from pathlib import Path
    import hashlib
    return digest({name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('stockpaper.py','equities.py')})


def dec(x):
    v=Decimal(str(x))
    if not v.is_finite():raise ValueError('nonfinite amount')
    return v


def initialize(store,cfg,market):
    from quant_harness.v72_integration_ready.live_safety import LIVE_BUILD_CAPABILITY,CURRENT_RELEASE_LIVE_AUTHORITY
    if LIVE_BUILD_CAPABILITY or CURRENT_RELEASE_LIVE_AUTHORITY:raise ValueError('Live hardlock')
    with psycopg.connect(store.url) as conn:
        conn.execute(DDL)
        conn.execute("INSERT INTO stock_account VALUES (1,%s,%s,%s,%s,'ACTIVE') ON CONFLICT DO NOTHING",(market,cfg[market]['currency'],cfg[market]['initial_capital'],cfg[market]['initial_capital']))
        row=conn.execute('SELECT market,currency FROM stock_account').fetchone()
        if row!=(market,cfg[market]['currency']):raise ValueError('currency/market isolation mismatch')


def seal(store,root,market,analysis,prices,catalog_id):
    cfg=settings(root);initialize(store,cfg,market)
    with psycopg.connect(store.url) as conn:
        if conn.execute("SELECT 1 FROM investment_run WHERE status='DECIDED' LIMIT 1").fetchone():raise ValueError('pending stock decision; resume it')
        cash=conn.execute('SELECT cash FROM stock_account').fetchone()[0]
        positions=dict(conn.execute('SELECT symbol,quantity FROM stock_position WHERE quantity>0').fetchall())
    marks=dict(analysis['prior_marks'])
    # analysis candidates are already D-1, with an explicit price-data freshness gate.
    targets=analysis['weights'] if analysis['status']=='CANDIDATES' else {}
    eligible=analysis.get('execution_eligible',False)
    if not eligible and positions:raise ValueError('cannot silently flatten a data-abstention account')
    nav=cash+sum(q*dec(marks[s]) for s,q in positions.items())
    intents=[]
    if eligible:
        for symbol in sorted(set(targets)|set(positions)):
            if symbol not in marks or prices[symbol]['meta'].get('instrumentType')!='EQUITY':raise ValueError('ETF or unknown stock prohibited')
            quantity=(nav*dec(targets.get(symbol,0))/dec(marks[symbol])).to_integral_value(rounding=ROUND_FLOOR)
            delta=quantity-positions.get(symbol,Decimal(0))
            if delta:intents.append({'symbol':symbol,'target_quantity':str(quantity),'delta_quantity':str(delta),'adv20_d1':analysis['adv20_d1'][symbol]})
    algorithm_hash=algorithm_fingerprint()
    payload={'algorithm_hash':algorithm_hash,'market':market,'currency':cfg[market]['currency'],'strategy_id':analysis['strategy_id'],'contract_hash':digest(cfg),
             'sealed_at':now(),'input_hash':analysis['input_hash'],'catalog_id':catalog_id,'analysis':analysis,
             'opening_cash':str(cash),'opening_positions':{s:str(q) for s,q in positions.items()},'prior_marks':marks,
             'weights':targets,'intents':intents,'eligible':eligible,'asset_type':'EQUITY','live_execution_allowed':False}
    identity=store.put('stock_decision',payload)
    store.state(identity,'DECIDED' if intents else 'NO_TRADE',{'reason':analysis['reason']})
    return identity,payload


def reconcile(conn):
    from psycopg.rows import tuple_row
    with conn.cursor(row_factory=tuple_row) as cur:
        initial,cash=cur.execute('SELECT initial,cash FROM stock_account FOR UPDATE').fetchone()
        ledger_cash=cur.execute('SELECT COALESCE(sum(cash_delta),0) FROM stock_fill').fetchone()[0]
        if abs(initial+ledger_cash-cash)>Decimal('0.000000001'):return False
        positions=dict(cur.execute('SELECT symbol,quantity FROM stock_position').fetchall())
        filled=dict(cur.execute("SELECT symbol,sum(CASE WHEN side='BUY' THEN quantity ELSE -quantity END) FROM stock_fill GROUP BY symbol").fetchall())
        return all(positions.get(s,0)==filled.get(s,0) for s in set(positions)|set(filled))


def execute(store,root,identity,events,current=None):
    cfg=settings(root);current=current or now()
    with store.lock():
        decision=store.get(identity)
        initialize(store,cfg,decision['market'])
        # Completed accounting remains recoverable across software revisions;
        # version changes only veto NEW fills.
        with psycopg.connect(store.url,row_factory=dict_row) as recovered_conn:
            completed=recovered_conn.execute('SELECT * FROM stock_nav WHERE decision_id=%s',(identity,)).fetchone()
            if completed:
                if not reconcile(recovered_conn):
                    recovered_conn.execute("UPDATE stock_account SET status='HOLD_ONLY'")
                    return {'status':'HOLD_ONLY','reason':'LEDGER_RECONCILIATION_FAILED'}
                recovered={**dict(completed),'idempotent':True}
                store.state(identity,completed['status'],recovered)
                return recovered
        if decision['contract_hash']!=digest(cfg):raise ValueError('stock contract changed')
        if decision.get('algorithm_hash')!=algorithm_fingerprint():
            outcome={'status':'HOLD_ONLY','reason':'ALGORITHM_VERSION_CHANGED_RESEAL_REQUIRED','broker_mutation_calls':0}
            store.put('stock_version_invalidation',{'decision_id':identity,**outcome})
            store.state(identity,'INVALIDATED_VERSION',outcome)
            return outcome
        initialize(store,cfg,decision['market'])
        event_id=store.put('stock_quote_events',{'decision_id':identity,'events':events})
        with psycopg.connect(store.url,row_factory=dict_row) as conn:
            # All fill/cash/position/NAV writes share one transaction.
            account=conn.execute('SELECT * FROM stock_account FOR UPDATE').fetchone()
            existing=conn.execute('SELECT * FROM stock_nav WHERE decision_id=%s',(identity,)).fetchone()
            if account['status']!='ACTIVE' or not reconcile(conn):
                conn.execute("UPDATE stock_account SET status='HOLD_ONLY'")
                return {'status':'HOLD_ONLY','reason':'LEDGER_RECONCILIATION_FAILED'}
            if existing:return {**dict(existing),'status':existing['status'],'idempotent':True}
            held={r['symbol']:r['quantity'] for r in conn.execute('SELECT * FROM stock_position')}
            if decision['opening_positions']!={s:str(q) for s,q in held.items() if q} or dec(decision['opening_cash'])!=account['cash']:
                raise ValueError('stock account changed after sealing')
            if not decision['intents']:
                if any(held.values()):raise ValueError('held positions need fresh valuation events')
                conn.execute('INSERT INTO stock_nav VALUES (%s,%s,0,%s,%s,%s,now())',(identity,account['cash'],account['cash'],event_id,'NO_TRADE'))
                outcome={'status':'NO_TRADE','nav':str(account['cash']),'currency':decision['currency'],'reason':decision['analysis']['reason']}
            else:
                by_symbol={x['symbol']:x for x in events}
                symbols=set(held)|{i['symbol'] for i in decision['intents']}
                if set(by_symbol)!=symbols or len(events)!=len(by_symbol):raise ValueError('incomplete/duplicate quote set')
                if instant(current)>instant(decision['sealed_at'])+timedelta(hours=cfg['decision_lifetime_hours']):raise ValueError('stock decision expired')
                for symbol,event in by_symbol.items():
                    if event['asset_type']!='EQUITY' or event['currency']!=decision['currency'] or event['source'] not in ('YAHOO_CHART_OBSERVED','TOSS_STOCK_QUOTE_OBSERVED'):raise ValueError('stock quote contract mismatch')
                    t,a=instant(event['event_at']),instant(event['available_at'])
                    if not instant(decision['sealed_at'])<t<=a<=instant(current) or (instant(current)-t).total_seconds()>60:raise ValueError('future/stale/predecision quote')
                    if not instant(event['session_open'])<=t<=instant(event['session_close']):raise ValueError('outside observed regular session')
                    if dec(event['price'])<=0:raise ValueError('nonpositive quote')
                market=decision['market'];assumptions=cfg['US_execution_assumptions'] if market=='US' else cfg['execution_assumptions']
                cash=account['cash'];nav=cash+sum(q*dec(by_symbol[s]['price']) for s,q in held.items())
                desired=dict(held)
                for i in decision['intents']:desired[i['symbol']]=dec(i['target_quantity'])
                exposure={s:q*dec(by_symbol[s]['price'])/nav for s,q in desired.items() if q}
                if sum(exposure.values())>dec(cfg['gross_cap']) or any(v>dec(cfg['single_name_cap']) for v in exposure.values()):raise ValueError('gap exposure limit')
                for i in sorted(decision['intents'],key=lambda i:(dec(i['delta_quantity'])>0,i['symbol'])):
                    symbol=i['symbol'];delta=dec(i['delta_quantity']);qty=abs(delta);reference=dec(by_symbol[symbol]['price']);adv=dec(i['adv20_d1'])
                    if adv<=0 or qty*reference>adv*dec(assumptions['max_participation_of_d1_adv']):raise ValueError('stock liquidity limit')
                    if qty*reference<nav*dec(assumptions['minimum_order_nav_fraction']):continue
                    side='BUY' if delta>0 else 'SELL'
                    impact=min(dec(assumptions['max_impact_bps']),dec(assumptions['impact_bps_at_1pct_adv'])*(qty*reference/adv)/Decimal('0.01'))
                    bps=dec(assumptions['half_spread_bps'])+impact
                    price=reference*(1+(1 if side=='BUY' else -1)*bps/10000)
                    fee=qty*price*dec(assumptions['buy_fee_bps'] if side=='BUY' else assumptions['sell_fee_bps'])/10000
                    cash_delta=-(qty*price+fee) if side=='BUY' else qty*price-fee
                    if cash+cash_delta<0 or held.get(symbol,0)+delta<0:raise ValueError('negative stock balance')
                    client_id=digest({'decision':identity,'symbol':symbol,'side':side})
                    conn.execute('INSERT INTO stock_fill(client_order_id,decision_id,symbol,side,quantity,price,fee,cash_delta,event_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',(client_id,identity,symbol,side,qty,price,fee,cash_delta,event_id))
                    cash+=cash_delta;held[symbol]=held.get(symbol,0)+delta
                    conn.execute('INSERT INTO stock_position VALUES (%s,%s) ON CONFLICT (symbol) DO UPDATE SET quantity=EXCLUDED.quantity',(symbol,held[symbol]))
                conn.execute('UPDATE stock_account SET cash=%s',(cash,))
                if not reconcile(conn):raise ValueError('postfill stock reconciliation failed')
                value=sum((q*dec(by_symbol[s]['price']) for s,q in held.items()),Decimal(0))
                final_nav=cash+value
                if value/final_nav>dec(cfg['gross_cap']) or any(q*dec(by_symbol[s]['price'])/final_nav>dec(cfg['single_name_cap']) for s,q in held.items() if q):
                    raise ValueError('postcost exposure limit; transaction rolled back')
                conn.execute("INSERT INTO stock_nav VALUES (%s,%s,%s,%s,%s,'COMPLETE',now())",(identity,cash,value,cash+value,event_id))
                outcome={'executed_algorithm_hash':algorithm_fingerprint(),'status':'COMPLETE','nav':str(cash+value),'currency':decision['currency'],'synthetic_paper_fills':True,'event_id':event_id}
        store.put('stock_execution_outcome',outcome,identity+':outcome')
        store.state(identity,outcome['status'],outcome)
        return outcome

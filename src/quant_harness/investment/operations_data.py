"""Bounded observed data, immutable snapshots, official market sessions.

No broker mutation endpoints. Historical backfills retain their actual observation
clock. Revisions are quarantined, never silently substituted into sealed inputs.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import math
import time
import pandas as pd
import psycopg
from .research import digest
from .store import Store
from .discovery import instant, now

DDL = '''
CREATE TABLE IF NOT EXISTS ops_session (
 market text, day date, opening timestamptz NOT NULL, closing timestamptz NOT NULL,
 source_hash text NOT NULL, observed_at timestamptz NOT NULL,
 PRIMARY KEY(market,day));
CREATE TABLE IF NOT EXISTS ops_session_edge (market text, prior_day date, next_day date, source_hash text NOT NULL, PRIMARY KEY(market,prior_day,next_day));
CREATE TABLE IF NOT EXISTS ops_pointer (name text PRIMARY KEY, record_id text NOT NULL REFERENCES investment_record(record_id));
CREATE TABLE IF NOT EXISTS ops_budget (day date, provider text, calls integer NOT NULL DEFAULT 0,
 failures integer NOT NULL DEFAULT 0, blocked_until timestamptz, PRIMARY KEY(day,provider));
CREATE TABLE IF NOT EXISTS ops_watch (market text, symbol text, role text, observed_at timestamptz,
 PRIMARY KEY(market,symbol));
'''
ZONES={'US':'America/New_York','KR':'Asia/Seoul'}


def parse_calendar(payload, market):
    """US dates follow New York regular open, including KST cross-date/DST."""
    result=payload['result']; rows=[]
    for key in ('previousBusinessDay','today','nextBusinessDay'):
        day=result.get(key) or {}
        venue=day if market=='US' else day.get('integrated',day.get('krx',{}))
        regular=venue.get('regularMarket') or {}
        if not regular.get('startTime') or not regular.get('endTime'):continue
        opening,closing=instant(regular['startTime']),instant(regular['endTime'])
        if not opening<closing or (closing-opening).total_seconds()>86400:raise ValueError('invalid official session')
        phases={}
        for label in ('preMarket','regularMarket','afterMarket','dayMarket'):
            event=venue.get(label) or {}
            if event.get('startTime') and event.get('endTime'):
                phases[label]=[instant(event['startTime']).isoformat(),instant(event['endTime']).isoformat()]
        rows.append({'market':market,'day':opening.astimezone(ZoneInfo(ZONES[market])).date().isoformat(),
                     'opening':opening.isoformat(),'closing':closing.isoformat(),'phases':phases})
    if not rows:raise ValueError('no official sessions')
    unique={r['day']:r for r in rows}
    if any(r!=unique[r['day']] for r in rows):raise ValueError('calendar conflict')
    return sorted(unique.values(),key=lambda r:r['day'])


def phase(sessions, current):
    at=instant(current)
    for row in sessions:
        if instant(row['opening'])<=at<instant(row['closing']):return 'REGULAR',row
        for name,(start,end) in row.get('phases',{}).items():
            if instant(start)<=at<instant(end):return name.upper(),row
    return 'CLOSED',None


class Warehouse:
    def __init__(self,url,root):
        self.store=Store(url,'TASK5_OPERATIONS_ONLY');self.url=url;self.root=Path(root)
        with psycopg.connect(url) as conn:conn.execute(DDL)

    def point(self,name,kind,payload):
        identity=self.store.put(kind,payload)
        with psycopg.connect(self.url) as conn:
            conn.execute('INSERT INTO ops_pointer VALUES (%s,%s) ON CONFLICT(name) DO UPDATE SET record_id=EXCLUDED.record_id',(name,identity))
        return identity

    def lookup(self,name):
        with psycopg.connect(self.url) as conn:row=conn.execute('SELECT record_id FROM ops_pointer WHERE name=%s',(name,)).fetchone()
        return self.store.get(row[0]) if row else None

    def raw(self,payload,kind):
        encoded=json.dumps(payload,sort_keys=True,allow_nan=False,default=str).encode();identity=digest(payload)
        path=self.root/'runtime/task5/raw'/kind/(identity+'.json');path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists() and path.read_bytes()!=encoded:raise ValueError('immutable raw conflict')
        if not path.exists():
            with path.open('xb') as handle:handle.write(encoded)
        return {'source_hash':identity,'path':str(path.relative_to(self.root)),'bytes':len(encoded),'available_at':now()}

    def reserve(self,provider,limit):
        """Reserve before I/O. Failures consume budget, including crashed calls."""
        with psycopg.connect(self.url) as conn:
            conn.execute('INSERT INTO ops_budget(day,provider) VALUES (CURRENT_DATE,%s) ON CONFLICT DO NOTHING',(provider,))
            row=conn.execute('SELECT calls,blocked_until FROM ops_budget WHERE day=CURRENT_DATE AND provider=%s FOR UPDATE',(provider,)).fetchone()
            if row[0]>=limit or (row[1] and row[1]>datetime.now(timezone.utc)):raise ValueError('provider budget/circuit open')
            conn.execute('UPDATE ops_budget SET calls=calls+1 WHERE day=CURRENT_DATE AND provider=%s',(provider,))

    def failure(self,provider,permanent=False):
        with psycopg.connect(self.url) as conn:
            conn.execute("UPDATE ops_budget SET failures=failures+1,blocked_until=now()+(CASE WHEN %s THEN interval '24 hours' ELSE interval '2 minutes' END) WHERE day=CURRENT_DATE AND provider=%s",(permanent,provider))

    def call(self,client,market,path,query=None,limit=100):
        provider='TOSS_'+market;self.reserve(provider,limit)
        started=time.monotonic()
        try:
            result=client._request('GET',path,query=query)
            receipt=self.raw(result,'toss');receipt.update(provider=provider,elapsed_seconds=time.monotonic()-started)
            self.store.put('ops_api_receipt',receipt)
            return result,receipt
        except Exception as exc:
            self.failure(provider,'403' in str(exc) or '401' in str(exc))
            self.store.put('ops_api_failure',{'provider':provider,'error_type':type(exc).__name__,'at':now(),'elapsed_seconds':time.monotonic()-started})
            raise

    def calendar(self,client,market,limit):
        key='calendar:'+market;prior=self.lookup(key)
        if prior and (instant(now())-instant(prior['available_at'])).total_seconds()<1800:
            with psycopg.connect(self.url) as conn:
                for a,b in zip(prior['sessions'],prior['sessions'][1:]):
                    conn.execute('INSERT INTO ops_session_edge VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING',(market,a['day'],b['day'],prior['source_hash']))
            return prior
        raw,receipt=self.call(client,market,'/api/v1/market-calendar/'+market,limit=limit)
        rows=parse_calendar(raw,market)
        with psycopg.connect(self.url) as conn:
            for row in rows:
                previous=conn.execute('SELECT opening,closing FROM ops_session WHERE market=%s AND day=%s',(market,row['day'])).fetchone()
                if previous and previous!=(instant(row['opening']),instant(row['closing'])):raise ValueError('session revision requires explicit review')
                conn.execute('INSERT INTO ops_session VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                             (market,row['day'],row['opening'],row['closing'],receipt['source_hash'],receipt['available_at']))
            for prior,following in zip(rows,rows[1:]):
                conn.execute('INSERT INTO ops_session_edge VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING',(market,prior['day'],following['day'],receipt['source_hash']))
        snapshot={**receipt,'market':market,'sessions':rows}
        self.point(key,'ops_calendar',snapshot);return snapshot

    def watch(self,market,seeds,benchmark,maximum):
        if len(seeds)+1>maximum:raise ValueError('watch budget too small')
        with psycopg.connect(self.url) as conn:
            for symbol in seeds+[benchmark]:
                conn.execute('INSERT INTO ops_watch VALUES (%s,%s,%s,now()) ON CONFLICT DO NOTHING',(market,symbol,'STRATEGY' if symbol in seeds else 'BENCHMARK_ONLY'))
            return conn.execute('SELECT symbol,role FROM ops_watch WHERE market=%s ORDER BY role,symbol LIMIT %s',(market,maximum)).fetchall()

    def discover(self,market,catalog,limit,maximum):
        """Metadata-only rotation; new listings never enter an approved strategy."""
        prior=self.lookup('scan:'+market) or {'cursor':0}
        rows=catalog['rows'];start=prior['cursor']%max(len(rows),1);selected=rows[start:start+limit]
        with psycopg.connect(self.url) as conn:
            count=conn.execute('SELECT count(*) FROM ops_watch WHERE market=%s',(market,)).fetchone()[0]
            for row in selected:
                symbol=row.get('symbol') if market=='US' else row['stock_code']+'.KS'
                if market=='US' and not row.get('common_stock_verified'):continue
                if count>=maximum:break
                result=conn.execute("INSERT INTO ops_watch VALUES (%s,%s,'RESEARCH_UNQUALIFIED',now()) ON CONFLICT DO NOTHING RETURNING symbol",(market,symbol)).fetchone()
                count+=bool(result)
        self.point('scan:'+market,'ops_discovery_cursor',{'cursor':start+len(selected),'catalog_hash':digest(catalog),'observed_at':now(),'execution_eligible':False})
        return len(selected)


def encode_prices(prices):
    return {s:{'meta':v['meta'],'receipt':v['receipt'],'frame':json.loads(v['frame'].to_json(orient='records'))} for s,v in prices.items()}


def decode_prices(snapshot):
    return {s:{**v,'frame':pd.DataFrame(v['frame'])} for s,v in snapshot.items()}


def strict_rows(payload,symbol,currency,zone,latest):
    rows=payload.get('result')
    if isinstance(rows,dict):rows=rows.get('candles')
    if not isinstance(rows,list) or not rows:raise ValueError('missing candles')
    normalized=[]
    for row in rows:
        if row.get('currency')!=currency:raise ValueError('candle currency')
        timestamp=instant(row['timestamp']);day=timestamp.astimezone(ZoneInfo(zone)).date().isoformat()
        if day>latest:continue
        values=[float(row[k]) for k in ('openPrice','highPrice','lowPrice','closePrice','volume')]
        o,h,l,c,v=values
        if not all(math.isfinite(x) for x in values) or min(o,h,l,c)<=0 or v<0 or h<max(o,l,c) or l>min(o,h,c):raise ValueError('invalid candle geometry')
        normalized.append({'date':day,'symbol':symbol,'timestamp':day+'T00:00:00'+('-05:00' if zone=='America/New_York' else '+09:00'),
                           'open':o,'high':h,'low':l,'close':c,'volume':v,'value_approx':c*v})
    frame=pd.DataFrame(normalized).sort_values('date')
    if frame.empty or frame.date.duplicated().any():raise ValueError('empty/duplicate candles')
    return frame


def collect_toss(warehouse,client,market,symbols,session,limit):
    """200 bars on bootstrap, 8 on increment. Adjusted alpha + raw execution marks.

    Adjusted history revisions are blocked rather than applied retroactively.
    Corporate-action cash entitlement remains unverified: not a total-return feed.
    """
    from .equities import settings
    from quant_harness.v87_actual_data_ingestion.engine import ProviderBatch,_validate_batch,_load_config
    cfg=_load_config(warehouse.root);currency=settings(warehouse.root)[market]['currency'];items={}
    for symbol in symbols:
        prior=warehouse.lookup('price:'+market+':'+symbol)
        count=8 if prior else 200
        native=symbol.split('.')[0] if market=='KR' else symbol
        pair=[];receipts=[]
        for adjusted in ('true','false'):
            payload,receipt=warehouse.call(client,market,client.endpoint_map.candles_path,
                {'symbol':native,'interval':'1d','count':count,'before':session['closing'],'adjusted':adjusted},limit)
            pair.append(strict_rows(payload,symbol,currency,ZONES[market],session['day']));receipts.append(receipt)
            time.sleep(.25)
        frame,raw=pair
        if list(frame.date)!=list(raw.date):raise ValueError('adjusted/raw date mismatch')
        for field in ('open','high','low','close'):frame['raw_'+field]=raw[field].values
        frame['adjustment_factor']=frame.close/frame.raw_close
        # Same source observation must describe one internally consistent scale.
        if any(((frame[field]/frame['raw_'+field])-frame.adjustment_factor).abs().gt(.02).any() for field in ('open','high','low')):raise ValueError('price-scale conflict')
        # Reuse V87 numeric/schema gate, with explicit internal numeric symbol.
        records=frame.assign(ticker='000001')[['date','ticker','open','high','low','close','volume','value_approx']].to_dict('records')
        _validate_batch(ProviderBatch('TOSS_EQUITY','000001',tuple(records),True,'toss_openapi_1d_adjusted',receipts[-1]['available_at'],{}),cfg)
        if prior:
            old=pd.DataFrame(prior['frame']);shared=old.set_index('date').index.intersection(frame.set_index('date').index)
            if len(shared)<1:raise ValueError('incremental gap: no overlap; explicit backfill required')
            for day in shared:
                a=old.set_index('date').loc[day];b=frame.set_index('date').loc[day]
                if any(abs(float(a[k])-float(b[k]))>max(.00001,abs(float(a[k]))*1e-6) for k in ('open','high','low','close','volume','raw_close')):
                    warehouse.store.put('ops_quarantine',{'symbol':symbol,'day':day,'previous_hash':digest(prior),'receipts':receipts,'reason':'REVISION_REQUIRES_APPROVAL'})
                    raise ValueError('price revision quarantined')
            frame=pd.concat([old[~old.date.isin(frame.date)],frame],ignore_index=True).sort_values('date')
        if len(frame)<130 or frame.date.iloc[-1]!=session['day']:raise ValueError('incomplete/stale price history')
        receipt={'symbol':symbol,'source':'TOSS_ADJUSTED_AND_RAW_OBSERVED','source_hash':digest(receipts),'available_at':receipts[-1]['available_at'],
                 'raw_receipts':receipts,'history_is_new_forward':False,'dividend_entitlements_verified':False,'v87_gate':'PASSED','revision_gate':'PASSED'}
        meta={'symbol':symbol,'instrumentType':'ETF' if symbol in ('SPY','069500.KS') else 'EQUITY','currency':currency,
              'currentTradingPeriod':{'regular':{'start':int(instant(session['opening']).timestamp()),'end':int(instant(session['closing']).timestamp())}}}
        item={'frame':frame,'meta':meta,'receipt':receipt};items[symbol]=item
        warehouse.point('price:'+market+':'+symbol,'ops_price_snapshot',encode_prices({symbol:item})[symbol])
    return items


def bounded_client(warehouse,market,wire_limit):
    """Count real HTTP attempts, OAuth included; existing client handles 429 retries.

    Store status and public quota headers only. Never archive token response,
    request headers, credential bodies, or account data.
    """
    from urllib.parse import urlsplit
    from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
    def transport(request,timeout):
        warehouse.reserve('WIRE_'+market,wire_limit)
        previous=getattr(warehouse,'last_wire_at',0)
        time.sleep(max(0,1.05-(time.monotonic()-previous)))
        warehouse.last_wire_at=time.monotonic();started=time.monotonic()
        status,headers,body=TossOpenApiClient._default_transport(request,timeout)
        public={k:v for k,v in headers.items() if k.lower() in ('x-ratelimit-limit','x-ratelimit-remaining','x-ratelimit-reset','retry-after')}
        warehouse.store.put('ops_http_attempt',{'market':market,'method':request.method,'path':urlsplit(request.full_url).path,
            'status':status,'quota_headers':public,'at':now(),'elapsed_seconds':time.monotonic()-started})
        if status>=400:warehouse.failure('WIRE_'+market,status in (401,403))
        return status,headers,body
    return TossOpenApiClient(transport=transport)

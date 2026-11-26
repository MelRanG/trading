"""Bounded official-release observation in the existing single operating tick.

This worker can append research outcomes only. It imports no broker or strategy
mutation code. Incomplete release identity/time/table evidence remains pending.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from html.parser import HTMLParser
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlparse,urljoin
import hashlib,json,re
import psycopg
from .store import Store
from .review_jobs import Queue
from .decision import instant
from .company_forecast import score_forecast

INDEX={'NVDA':'https://nvidianews.nvidia.com/news','CRWV':'https://investors.coreweave.com/news/default.aspx'}
# No guessed future document URL; only matching official listing anchors.
WORDS={'NVDA':r'third.quarter.*(?:fiscal.)?2027','CRWV':r'fourth.quarter.*2026'}
ISSUER_HOSTS={'NVDA':{'investor.nvidia.com','nvidianews.nvidia.com'},'CRWV':{'investors.coreweave.com'}}
PERIODS={'NVDA':'2026-10-25','CRWV':'2026-12-31'}

class Document(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.text=[];self.published=None;self.tables=[];self.table=None;self.row=None;self.cell=None;self.drop=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','style'):self.drop+=1
        if tag=='a' and a.get('href'):self.links.append(a['href'])
        if tag=='meta' and a.get('property',a.get('name','')) in ('article:published_time','datePublished'):self.published=a.get('content')
        if tag=='table':self.table=[]
        if tag=='tr' and self.table is not None:self.row=[]
        if tag in ('td','th') and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if not self.drop and data.strip():self.text.append(data.strip())
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.drop=max(0,self.drop-1)
        if tag in ('td','th') and self.cell is not None:self.row.append(' '.join(self.cell).strip());self.cell=None
        if tag=='tr' and self.row is not None:self.table.append(self.row);self.row=None
        if tag=='table' and self.table is not None:self.tables.append(self.table);self.table=None


def parse_release(raw,ticker,url,observed_at):
    if urlparse(url).hostname not in ISSUER_HOSTS[ticker]:raise ValueError('issuer source identity mismatch')
    doc=Document();doc.feed(raw.decode('utf-8',errors='strict'));text=' '.join(doc.text);period=PERIODS[ticker]
    if not re.search(WORDS[ticker],text,re.I):raise ValueError('release quarter identity unverified')
    if not doc.published:raise ValueError('precise official release timestamp unavailable')
    released=instant(doc.published)
    if released>instant(observed_at):raise ValueError('future release timestamp')
    date=datetime.fromisoformat(period);display=date.strftime('%B')+r'\s+'+str(date.day)+r',?\s+'+str(date.year)
    value=None
    if not re.search(r'in millions',text,re.I):raise ValueError('reported currency scale unverified')
    for table in doc.tables:
        # Require first date-bearing column to match target period, then same-column revenue.
        headers=' '.join(' '.join(row) for row in table[:8])
        durations=re.findall(r'(three months ended|quarter ended|(?:twelve months|year|nine months|six months) ended)',headers,re.I)
        if not durations or durations[0].lower() not in ('three months ended','quarter ended'):continue
        dates=re.findall(r'[A-Z][a-z]+\s+\d{1,2},?\s+20\d\d',headers)
        if not dates or not re.fullmatch(display,dates[0]):continue
        for row in table:
            cells=[x.strip() for x in row if x.strip() and x.strip()!='$']
            if cells and re.fullmatch(r'(?:total\s+)?revenue(?:s)?',cells[0],re.I) and len(cells)>1:
                number=cells[1].replace(',','').replace('$','').strip()
                if re.fullmatch(r'\d+(?:\.\d+)?',number):value=float(number);break
        if value is not None:break
    if value is None:raise ValueError('matching period/revenue table unavailable')
    return {'ticker':ticker,'metric':'quarterly_revenue','period_end':period,'unit':'USD_million','actual':value,'released_at':released.isoformat(),'observed_at':observed_at,'source_id':url,'source_class':'OFFICIAL_ISSUER','verification_status':'VERIFIED','source_sha256':hashlib.sha256(raw).hexdigest()}


def fetch(root,url,allowed):
    if urlparse(url).scheme!='https' or urlparse(url).hostname not in allowed:raise ValueError('official source allowlist')
    class IssuerRedirect(HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if urlparse(newurl).scheme!='https' or urlparse(newurl).hostname not in allowed:raise ValueError('official redirect host not allowed: '+str(urlparse(newurl).hostname))
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    raw_response=build_opener(IssuerRedirect()).open(Request(url,headers={'User-Agent':'QuantHarness bounded company research'}),timeout=15)
    if urlparse(raw_response.url).hostname not in allowed:raise ValueError('redirected outside official issuer')
    raw=raw_response.read(3_000_001)
    if len(raw)>3_000_000:raise ValueError('official response exceeds budget')
    digest=hashlib.sha256(raw).hexdigest();folder=Path(root)/'runtime/task8/releases';folder.mkdir(parents=True,exist_ok=True);path=folder/(digest+'.html')
    if not path.exists():path.write_bytes(raw)
    meta=folder/(digest+'.meta.json')
    if not meta.exists():meta.write_text(json.dumps({'url':url,'sha256':digest,'observed_at':datetime.now(timezone.utc).isoformat(),'path':str(path.relative_to(root))}))
    return raw,json.loads(meta.read_text())


def run_tick(root,*,fetcher=fetch,current=None):
    root=Path(root);cfg=json.loads((root/'config/task8_portfolio.json').read_text());policy=cfg['outcome_observation']
    if not policy['enabled']:return {'status':'DISABLED'}
    supplied_current=current
    current=current or datetime.now(timezone.utc).isoformat();url='postgresql://quant_task8_research@127.0.0.1:55432/'+cfg['research_database'];store=Store(url,'TASK8_RESEARCH_ONLY');queue=Queue(store);url=store.url
    with store.lock():
        with psycopg.connect(url) as conn:
            previous=conn.execute("SELECT payload FROM investment_record WHERE kind='company_observation_reservation' ORDER BY created_at DESC LIMIT 1").fetchone()
        if previous and instant(current)-instant(previous[0]['at'])<timedelta(hours=policy['minimum_interval_hours']):return {'status':'NOT_DUE','requests':0}
        # Reserve before any I/O; crashes and failed requests do not create a retry storm.
        reservation=store.put('company_observation_reservation',{'at':current,'max_requests':policy['maximum_requests_per_tick']})
        with psycopg.connect(url) as conn:forecasts=conn.execute("SELECT record_id,payload FROM investment_record WHERE kind='imported_task7_forecast'").fetchall()
        output=[];calls=0
        for ticker in sorted({f['ticker'] for _,f in forecasts}):
            try:
                if calls>=policy['maximum_requests_per_tick']:raise ValueError('daily observation budget exhausted')
                calls+=1;raw,receipt=fetcher(root,INDEX[ticker],policy['url_hosts']);store.put('company_release_receipt',receipt)
                parser=Document();parser.feed(raw.decode('utf-8',errors='replace'))
                links=sorted({urljoin(INDEX[ticker],u) for u in parser.links if re.search(WORDS[ticker],u,re.I)})
                if not links:output.append({'ticker':ticker,'status':'PENDING','reason':'NO_MATCHING_OFFICIAL_RELEASE_LINK'});continue
                if calls>=policy['maximum_requests_per_tick']:raise ValueError('daily observation budget exhausted')
                calls+=1;raw,receipt=fetcher(root,links[0],policy['url_hosts']);store.put('company_release_receipt',receipt)
                label=parse_release(raw,ticker,links[0],receipt['observed_at']);label_id=store.put('official_company_label',label)
                scores=[]
                for identity,forecast in forecasts:
                    if forecast['ticker']!=ticker:continue
                    evaluation_at=supplied_current or datetime.now(timezone.utc).isoformat()
                    try:result=score_forecast(forecast,label,evaluation_at)
                    except ValueError as exc:result={'status':'PENDING_EVIDENCE','reason':str(exc)}
                    score_id=store.put('company_forecast_score',{'forecast_id':identity,'label_id':label_id,'score':result,'guidance_comparison':forecast.get('guidance_comparison','NOT_CLASSIFIED'),'interpretation':'Forecast error is not an automatic trading error or promotion'})
                    if result['status']=='MATURE':
                        queue.observe(identity,label_id)
                        breached=not result['interval_covered']
                        event={'version':'TASK9_RESEARCH_REQUEST_V1','event':'FORECAST_OUTSIDE_REGISTERED_INTERVAL' if breached else 'FORECAST_OBSERVED_WITHIN_INTERVAL','forecast_id':identity,'label_id':label_id,'score_id':score_id,'requested_research':'FORECAST_AND_THESIS_REVIEW' if breached else 'NO_FORCED_CHANGE','reason':'Revenue interval comparison only; other prose falsification conditions remain unparsed','cause':'UNDETERMINED_NOT_AUTOMATIC_TRADING_ERROR','budget_status':'UNALLOCATED_TASK9','automatic_strategy_change':False}
                        event_id=store.put('task9_research_request',event)
                        queue.enqueue('TASK9_RESEARCH_REQUEST',{'request_id':event_id})
                    scores.append({'forecast_id':identity,'score_id':score_id,'status':result['status']})
                output.append({'ticker':ticker,'status':'OBSERVED','scores':scores})
            except Exception as exc:output.append({'ticker':ticker,'status':'PENDING_EVIDENCE','reason':str(exc)[:160],'error_type':type(exc).__name__})
        result={'at':current,'reservation_id':reservation,'status':'OBSERVATION_TICK_COMPLETE','requests':calls,'companies':output,'model_calls':0,'orders':0,'database':cfg['research_database']};store.put('company_observation_tick',result)
        path=root/'runtime/task8/latest_observation.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2));return result

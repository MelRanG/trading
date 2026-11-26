"""Bounded source feasibility probe, existing OpenDART client; never fetches prices."""
from pathlib import Path
import sys,json,hashlib,datetime,time,os,io,zipfile,re
from urllib.request import Request,urlopen
from urllib.error import HTTPError
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
from quant_harness.investment.company_outcomes import Document
load_environment(R);B=R/'runtime/task13_b0';plan=json.loads((B/'plan.json').read_text());assert hashlib.sha256((B/'plan.json').read_bytes()).hexdigest()==(B/'plan.sha256').read_text()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2));os.replace(tmp,p)
def request(name,url,kind='HTTP',public=None,headers=None):
 folder=B/'sources'/name;folder.mkdir(parents=True,exist_ok=True);meta=folder/'receipt.json';rawp=folder/'original.bin'
 if meta.exists():
  d=json.loads(meta.read_text())
  if d.get('status')=='SAVED':assert rawp.exists() and hashlib.sha256(rawp.read_bytes()).hexdigest()==d['sha256'],'REVISION_OR_CORRUPTION';return rawp.read_bytes()
  return None
 count=sum(len(json.loads(p.read_text()).get('attempts',[])) for p in (B/'sources').glob('*/receipt.json'))
 if count>=plan['network_limit']:raise RuntimeError('NETWORK_BUDGET_EXHAUSTED')
 d={'source':public or url,'kind':kind,'requested_at':now(),'status':'RESERVED','attempts':[],'historical_observation':False,'revision_gate':'No previous B0 snapshot. Preserve bytes, immutable SHA on reuse; not admitted to operating V87 price ingestion.'};dump(meta,d)
 for attempt in range(2):
  if count>=plan['network_limit']:break
  item={'at':now()};d['attempts'].append(item);dump(meta,d);count+=1;start=time.monotonic();body=None
  try:
   with urlopen(Request(url,headers=headers or {'User-Agent':'QuantHarness feasibility research/1.0'}),timeout=20) as s:
    body=s.read(plan['max_response_bytes']+1);item.update(http=s.status);d.update(content_type=s.headers.get('Content-Type'),last_modified=s.headers.get('Last-Modified'))
   if len(body)>plan['max_response_bytes']:raise ValueError('RESPONSE_SIZE_LIMIT')
   rawp.write_bytes(body);d.update(status='SAVED',bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),observed_at=now());item['status']='SAVED'
  except HTTPError as e:
   body=e.read(1000);item.update(http=e.code,status='HTTP_ERROR');(folder/'error_excerpt.bin').write_bytes(body)
  except Exception as e:item.update(status=type(e).__name__)
  item['elapsed_seconds']=time.monotonic()-start;dump(meta,d)
  if d['status']=='SAVED':return body
  if item.get('http') in [401,403,404,429] or item['status']=='ValueError':break
  if attempt==0:time.sleep(1)
 d['status']='FAILED';dump(meta,d);return None
counter=0
# Existing official client transport, secret never written in receipt/error.
def transport(req,timeout):
 global counter
 from urllib.parse import urlparse,parse_qs
 q=parse_qs(urlparse(req.full_url).query);q.pop('crtfc_key',None);endpoint=urlparse(req.full_url).path.split('/')[-1];public={'endpoint':endpoint,'params':q};name='dart_'+hashlib.sha256(json.dumps(public,sort_keys=True).encode()).hexdigest()[:16]
 raw=request(name,req.full_url,'DART',public,dict(req.header_items()))
 if raw is None:raise RuntimeError('DART_TRANSPORT_FAILURE')
 return 200,{},raw
c=OpenDartClient(transport=transport)
# Access check independent of which issuer later performs well.
identity=os.getenv('SEC_USER_AGENT') or os.getenv('EDGAR_IDENTITY') or 'ansy tpdud285@naver.com'
for name,url in [('SEC_MSFT','https://data.sec.gov/submissions/CIK0000789019.json'),('SEC_PEP','https://data.sec.gov/submissions/CIK0000077476.json'),('SEC_ARCHIVE','https://www.sec.gov/Archives/edgar/data/77476/000007747624000054/q320248-kxexhibit991.htm')]:
 request(name,url,'SEC',headers={'User-Agent':identity,'Accept':'application/json,text/html'})
 time.sleep(.4)
urls=[('MSFT_2024Q3','https://www.microsoft.com/en-us/Investor/earnings/FY-2025-Q1/press-release-webcast'),('MSFT_2024Q4','https://www.microsoft.com/en-us/Investor/earnings/FY-2025-Q2/press-release-webcast'),('PEP_2024Q3','https://investors.pepsico.com/docs/pepsico-5v9wci20/media/Files/investors/q3-2024-earnings-release.pdf')]
for name,url in urls:request(name,url,'OFFICIAL_IR')
# Lists retain correction filings and exact receipt identity; selected by pre-frozen period and chronological rule.
cat=json.loads((R/'runtime/task8b/discovery/kr_catalog.json').read_text())['rows'];selected=[];summaries=[]
for symbol,corp,year,mode in [(x['symbol'],x['corp_code'],x['year'],'earnings') for x in plan['earnings_sample']['KR']]+[(x['symbol'],next(r['corp_code'] for r in cat if r['stock_code']==x['symbol']),2024,'contract') for x in plan['contract_sample']]:
 params={'corp_code':corp,'bgn_de':f'{year}0401' if mode=='earnings' else '20240101','end_de':f'{year}0630' if mode=='earnings' else '20240630','page_count':100,'page_no':1,'last_reprt_at':'N','sort':'date','sort_mth':'asc'};rows=[];total=0;error=None
 try:
  for page in [1,2]:
   params['page_no']=page;payload=c._request('list.json',params);rows+=payload.get('list',[]);total=payload.get('total_count',0)
   if page>=payload.get('total_page',1):break
 except Exception as e:error=type(e).__name__
 summaries.append({'symbol':symbol,'year':year,'mode':mode,'rows':len(rows),'total_count':total,'complete':len(rows)==total and error is None,'error':error,'filings':rows})
 if mode=='earnings':matches=[x for x in rows if x['report_nm'].strip().startswith('분기보고서') and f'{year}.03' in x['report_nm']]
 else:matches=[x for x in rows if '단일판매' in x['report_nm'] and '계약체결' in x['report_nm'] and not x['report_nm'].startswith('[')][:2]
 if not matches:selected.append({'symbol':symbol,'year':year,'mode':mode,'status':'NO_MATCH_OR_ACCESS_FAILURE'});continue
 for item in matches[:1] if mode=='earnings' else matches:
  accession=item['rcept_no'];row={'symbol':symbol,'year':year,'mode':mode,'filing':item,'correction_headings':[x for x in rows if '[' in x['report_nm'] and (('분기보고서' in x['report_nm']) if mode=='earnings' else '단일판매' in x['report_nm'])]}
  try:
   raw=c._request('document.xml',{'rcept_no':accession},binary=True);row['source_sha256']=hashlib.sha256(raw).hexdigest();folder=B/'documents'/accession;folder.mkdir(parents=True,exist_ok=True)
   # Original bytes already preserved in content receipt. No second ZIP copy.
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    xmls=[n for n in z.namelist() if n.lower().endswith('.xml')];assert xmls
    for n in xmls:
     data=z.read(n);assert len(data)<30000000;txt=data.decode('utf-8',errors='strict');(folder/Path(n).name).write_text(txt)
   row.update(status='ORIGINAL_FETCHED',xml_files=xmls)
  except Exception as e:row.update(status='ORIGINAL_FAILED',error=type(e).__name__)
  selected.append(row)
dump(B/'dart_lists.json',summaries);dump(B/'events.json',selected)
print(json.dumps({'selected':[(x['symbol'],x['year'],x['mode'],x['status']) for x in selected],'requests':sum(len(json.loads(p.read_text()).get('attempts',[])) for p in (B/'sources').glob('*/receipt.json'))},ensure_ascii=False))

from common import *
import io,re
sys.path.insert(0,'/home/ansy/app/quant-diligence/task6-quanta-env/lib/python3.12/site-packages')
from pypdf import PdfReader
from quant_harness.investment.equities import fetch,load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R)
f=B/'discovery';f.mkdir(exist_ok=True)
u='https://www.spglobal.com/spdji/en/documents/indexnews/announcements/20260306-1482263/1482263_march2026rebalance1546.pdf'
p=f/'sp_march.pdf'
if not p.exists():
 try:
  raw,r=fetch(u,f/'raw');p.write_bytes(raw);dump(f/'sp_receipt.json',{'published':'2026-03-06','url':u,'receipt':r,'hash':sha(p)})
 except Exception as exc:
  dump(f/'sp_http_failure.json',{'url':u,'error_type':type(exc).__name__,'status':'HTTP403_NO_BYPASS'})
if p.exists():t='\n'.join(x.extract_text() or '' for x in PdfReader(str(p)).pages)
else:
 t='2026-03-06 official S&P announcement, web-accessed pages0-1: VRT Vertiv Industrials; LITE Lumentum Technology; COHR Coherent Technology; SATS EchoStar Communication; MTCH Match Group Communication; MOH Molina Healthcare; LW Lamb Weston Staples; PAYC Paycom Industrials. First four S&P500 additions, last four removals, effective2026-03-23.'
 dump(f/'sp_web_extract.json',{'url':u,'published':'2026-03-06','retrieval':'web tool official PDF lines31-38','text':t,'quality':'PARTIAL_WEB_EXTRACT_NOT_RAW_PDF'})
 p=f/'sp_web_extract.json'
(f/'sp_march.txt').write_text(t)
# A dated corporate-change group PLUS a prior broad sector sample, not future winners.
new=[('VRT','Vertiv','Industrials'),('LITE','Lumentum','Technology'),('COHR','Coherent','Technology'),('SATS','EchoStar','Communication'),('MTCH','Match Group','Communication'),('PAYC','Paycom','Industrials'),('MOH','Molina Healthcare','Healthcare'),('LW','Lamb Weston','Staples')]
assert all(s in t for s,_,_ in new),'verify exact announcement names'
old=json.loads((R/'runtime/task9_1/cohorts/2025-06-30/US.json').read_text())
us=[{'symbol':s,'name':n,'sector':sec,'market':'US','published':'2026-03-06','discovery':'Dated index additions/removals: corporate/reclassification change, not endorsement','source_hash':sha(p)} for s,n,sec in new]
for x in old:
 if x['symbol'] not in {y['symbol'] for y in us}:us.append({**x,'discovery':'Dated broad2025 Russell sector cohort, survivor bias partial; not new discovery claim'})
freeze(f/'US.json',us[:35]);print('US',len(us[:35]),flush=True)
c=OpenDartClient();seen={}
# Fixed broad interval and six pages, then source-independent hash order (not first filings).
for page in range(1,7):
 p=f/f'dart_q1_{page}.json'
 if p.exists():z=json.loads(p.read_text())
 else:
  z=c._request('list.json',{'bgn_de':'20260501','end_de':'20260514','pblntf_ty':'A','page_count':100,'page_no':page,'sort':'date','sort_mth':'asc','last_reprt_at':'N'});dump(p,z)
 for x in z.get('list',[]):
  if x['corp_cls']!='Y' or not x.get('stock_code') or '분기보고서' not in x['report_nm'] or '[' in x['report_nm']:continue
  if any(w in x['corp_name'] for w in ['리츠','스팩','기업인수','투자회사']):continue
  seen[x['stock_code']]={**x,'source_hash':sha(p)}
 # Pagination complete, no extra empty requests.
 if page>=int(z.get('total_page',page)):break
rows=sorted(seen.values(),key=lambda x:hashlib.sha256(('TASK93|'+x['stock_code']).encode()).hexdigest())
kr=[{'symbol':x['stock_code']+'.KS','name':x['corp_name'],'corp_code':x['corp_code'],'market':'KR','sector':'UNVERIFIED_PENDING_BUSINESS_SOURCE','accession':x['rcept_no'],'published':x['rcept_dt'],'source_hash':x['source_hash'],'discovery':'bounded dated Q1business-report search, deterministic hash sample, not submission-order topN','report':x['report_nm']} for x in rows[:35]]
freeze(f/'KR.json',kr);dump(f/'coverage.json',{'US_candidates':len(us[:35]),'KR_candidates':len(kr),'KR_dated_listed_reports_seen':len(seen),'full_exchange_universe':False,'source_pages':page,'KR_sampling_bias':'bounded reporting window/pages; prior reports and financials-only businesses underrepresented','no_future_outcome_filter':True});print('KR',len(kr),'datedseen',len(seen),flush=True)

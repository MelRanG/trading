from common import *
import io,re,zipfile
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'/home/ansy/app/quant-diligence/task6-quanta-env/lib/python3.12/site-packages')
sys.path.insert(0,str(R/'experiments/task9_historical'))
from original_parser import text_and_identity
from pypdf import PdfReader
from quant_harness.investment.equities import fetch,load_environment
from quant_harness.investment.company_outcomes import Document
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);c=OpenDartClient()
plans=[('2024-11-29','SMCI','2024-11-05','https://ir.supermicro.com/news/news-details/2024/Supermicro-Announces-an-Update-from-the-Independent-Special-Committee-and-First-Quarter-Fiscal-Year-2025-Preliminary-Financial-Information/default.aspx','Preliminary First Quarter'),('2024-11-29','SMCI_update','2024-11-18','https://ir.supermicro.com/news/news-details/2024/Supermicro-Announces-Appointment-of-BDO-USA-as-Independent-Auditor-and-Filing-of-Compliance-Plan-with-Nasdaq/default.aspx','SAN JOSE'),('2024-11-29','CVNA','2024-10-30','https://investors.carvana.com/~/media/Files/C/Carvana-IR/documents/cvna-earning-release-q3-2024.pdf',''),('2024-11-29','PR','2024-11-06','https://permianres.com/permian-resources-announces-strong-third-quarter-2024-results-and-increased-full-year-guidance/','MIDLAND'),('2024-11-29','FIX','2024-10-24','https://investors.comfortsystemsusa.com/node/17331/pdf',''),('2024-11-29','CRH','2024-11-07','https://www.crh.com/wp-content/uploads/2025/09/crh-plc-q3-2024-results-announcement_458080.pdf',''),('2025-06-30','SMMT','2025-05-01','https://www.smmttx.com/wp-content/uploads/2025/05/Q1-2025-Earnings-Deck-_-FINAL.pdf',''),('2025-06-30','SFM','2025-04-30','https://investors.sprouts.com/news/news-details/2025/Sprouts-Farmers-Market-Inc--Reports-First-Quarter-2025-Results/default.aspx','First Quarter Highlights'),('2025-06-30','AUR','2025-05-08','https://ir.aurora.tech/news-events/press-releases/detail/120/aurora-announces-first-quarter-2025-results','PITTSBURGH'),('2025-06-30','BAM','2025-05-06','https://bam.brookfield.com/sites/brookfield-bam-v2/files/brookfield-bam-v2/events-news/2025-q1-bam-press-release.pdf',''),('2025-06-30','FLUT','2025-05-07','https://flutter.com/media/vjubgbfn/q1-2025-earnings-release-website.pdf','')]
freeze(B/'primary_source_plan.json',plans)
def us(plan):
 date,s,pub,url,anchor=plan;f=B/'deep'/date/s;f.mkdir(parents=True,exist_ok=True)
 if (f/'packet.json').exists():return
 try:
  raw,r=fetch(url,f/'raw');(f/'original.bin').write_bytes(raw)
  if raw.startswith(b'%PDF'):text='\n'.join(p.extract_text(extraction_mode='layout') or '' for p in PdfReader(io.BytesIO(raw)).pages)
  else:d=Document();d.feed(raw.decode());text='\n'.join(d.text)
  (f/'original.txt').write_text(text);start=max(0,text.find(anchor)) if anchor else 0;piece=text[start:start+9500]
  if s in ['SFM','SMCI_update','AUR']:piece=piece.split('Forward-Looking Statements')[0]
  assert len(piece)>500,'INADEQUATE_TEXT';dump(f/'packet.json',{'symbol':s,'source_url':url,'published':pub,'original_sha256':sha(f/'original.bin'),'text':piece,'quality':'PARTIAL_DATED_PRIMARY_NOT_ARCHIVAL_RECEIPT','status':'SAVED'})
 except Exception as e:dump(f/'packet.json',{'symbol':s,'source_url':url,'published':pub,'status':'FAILED','error_type':type(e).__name__})
 print(date,s,json.loads((f/'packet.json').read_text())['status'],flush=True)
def kr(task):
 date,x=task;s=x['symbol'];f=B/'deep'/date/s;f.mkdir(parents=True,exist_ok=True)
 if (f/'packet.json').exists():return
 src=B/'inputs'/date/s;original=src/'original.txt'
 try:
  if original.exists():raw=(src/'original.zip').read_bytes();text=original.read_text()
  else:
   raw=c._request('document.xml',{'rcept_no':x['accession']},binary=True);z=zipfile.ZipFile(io.BytesIO(raw));text='\n'.join(text_and_identity(z.read(n))[0] for n in z.namelist() if n.lower().endswith('.xml'));(src/'original.zip').write_bytes(raw);original.write_text(text)
  p=f/'accounts.json'
  if p.exists():api=json.loads(p.read_text())
  else:api=c._request('fnlttSinglAcntAll.json',{'corp_code':x['corp_code'],'bsns_year':date[:4],'reprt_code':'11014' if date[:4]=='2024' else '11013','fs_div':'CFS'});dump(p,api)
  rows=api.get('list',[]);matched=bool(rows) and all(v['rcept_no']==x['accession'] for v in rows)
  needles=['Revenue','ProfitLoss','OperatingIncomeLoss','CashFlowsFromUsedInOperating','CashAndCashEquivalent','Assets','Liabilities','Equity','Borrowing','Debt']
  facts=[{k:v.get(k) for k in ['account_id','account_nm','sj_div','thstrm_amount','thstrm_add_amount','frmtrm_amount','frmtrm_add_amount','currency']} for v in rows if any(n in v.get('account_id','') for n in needles)][:25] if matched else []
  parts=[]
  for pattern,length in [(r'II\. 사업의 내용',1900),(r'1\. 요약재무정보',1500),(r'연결 현금흐름표',1000)]:
   ms=list(re.finditer(pattern,text))
   if ms:parts.append(text[ms[-1].start():ms[-1].start()+length])
  dump(f/'packet.json',{'symbol':s,'source_url':'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+x['accession'],'published':x['source_published'],'original_sha256':sha(src/'original.zip'),'API_matches_original':matched,'facts':facts,'text':'\n'.join(parts),'quarter_units':'KRW API; thstrm_amount single quarter; thstrm_add_amount YTD. Original excerpts units may million KRW. No arbitrary annualization.','quality':'PARTIAL_ORIGINAL_ACCESSION','status':'SAVED'})
 except Exception as e:dump(f/'packet.json',{'symbol':s,'status':'FAILED','error_type':type(e).__name__})
 print(date,s,json.loads((f/'packet.json').read_text())['status'],flush=True)
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(us,plans))
tasks=[(date,x) for date in ['2024-11-29','2025-06-30'] for x in json.loads((B/'screens'/date/'KR.json').read_text())['deep']]
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(kr,tasks))

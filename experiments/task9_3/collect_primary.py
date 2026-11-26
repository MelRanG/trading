from common import *
import io,re,zipfile
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'/home/ansy/app/quant-diligence/task6-quanta-env/lib/python3.12/site-packages');sys.path.insert(0,str(R/'experiments/task9_historical'))
from pypdf import PdfReader
from original_parser import text_and_identity
from quant_harness.investment.equities import fetch,load_environment
from quant_harness.investment.company_outcomes import Document
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);c=OpenDartClient();W=Path('/home/ansy/app/quant-diligence/task9-3-work')
plans=[('VRT','2026-04-22','https://investors.vertiv.com/news/news-details/2026/Vertiv-Reports-Strong-First-Quarter-with-Diluted-EPS-Growth-of-136-Adjusted-Diluted-EPS-Growth-of-83-Raises-Full-Year-Guidance/default.aspx'),('MOH','2026-04-22','https://investors.molinahealthcare.com/static-files/e869243a-80f6-4f6a-9f29-0e4a46fa6440'),('SFM','2026-04-29','https://investors.sprouts.com/news/news-details/2026/Sprouts-Farmers-Market-Inc--Reports-First-Quarter-2026-Results/default.aspx'),('BAM','2026-05-08','https://bam.brookfield.com/sites/brookfield-bam-v2/files/BAM-IR-Master/Press-Releases/2026/Q1-26-BAM-Press-Release.pdf'),('FLUT','2026-05-06','https://flutter.com/media/ek1iky22/flutter-q1-2026-earnings-release.pdf')]
freeze(B/'primary_plan_initial.json',plans)
def us(plan):
 s,pub,url=plan;f=B/'primary'/s/pub;f.mkdir(parents=True,exist_ok=True)
 if (f/'receipt.json').exists():return
 try:
  raw,r=fetch(url,f/'raw');(f/'original.bin').write_bytes(raw)
  if raw.startswith(b'%PDF'):t='\n'.join(p.extract_text(extraction_mode='layout') or '' for p in PdfReader(io.BytesIO(raw)).pages)
  else:
   d=Document();d.feed(raw.decode());t='\n'.join(d.text)
  (f/'original.txt').write_text(t);assert len(t)>1500,'INADEQUATE_PRIMARY_TEXT'
  dump(f/'receipt.json',{'status':'SAVED','symbol':s,'published':pub,'url':url,'raw_sha256':sha(f/'original.bin'),'text_sha256':sha(f/'original.txt'),'receipt':r});print(s,pub,'PRIMARY',len(t),flush=True)
 except Exception as e:dump(f/'receipt.json',{'status':'FAILED','symbol':s,'published':pub,'url':url,'error_type':type(e).__name__});print(s,'FAILED',type(e).__name__,flush=True)
def kr(x):
 s=x['symbol'];item=next(r for r in json.loads((B/'discovery/KR.json').read_text()) if r['symbol']==s);f=B/'primary'/s/item['published'];f.mkdir(parents=True,exist_ok=True)
 if (f/'receipt.json').exists():return
 try:
  raw=c._request('document.xml',{'rcept_no':item['accession']},binary=True);(f/'original.zip').write_bytes(raw);z=zipfile.ZipFile(io.BytesIO(raw));parts=[text_and_identity(z.read(n)) for n in z.namelist() if n.lower().endswith('.xml')];t='\n'.join(a[0] for a in parts);(f/'original.txt').write_text(t);dump(f/'receipt.json',{'status':'SAVED','symbol':s,'published':item['published'],'accession':item['accession'],'raw_sha256':sha(f/'original.zip'),'text_sha256':sha(f/'original.txt'),'identities':[a[1] for a in parts]});print(s,'ORIGINAL',len(t),flush=True)
 except Exception as e:dump(f/'receipt.json',{'status':'FAILED','symbol':s,'error_type':type(e).__name__});print(s,'FAILED',type(e).__name__,flush=True)
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(us,plans))
if (W/'discover_KR_v2.json').exists():
 with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(kr,json.loads((W/'discover_KR_v2.json').read_text())['deep']))

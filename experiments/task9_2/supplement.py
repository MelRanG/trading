from common import *
import io,re,json
sys.path.insert(0,'/home/ansy/app/quant-diligence/task6-quanta-env/lib/python3.12/site-packages')
from pypdf import PdfReader
from quant_harness.investment.equities import fetch
from quant_harness.investment.company_outcomes import Document
plans=[('DECK','2026-10-22','https://ir.deckers.com/news-events/press-releases/detail/666/deckers-brands-reports-second-quarter-fiscal-year-2027-financial-results'),('KTG_Q3','2026-11-05','https://en.ktng.com/attach/download/c5d60fb8-6e19-42df-9dff-7933f5373b0b'),('SAMYANG_LIST','2026-11-06','https://www.samyangfoods.com/kor/ir/list.do')]
for name,date,url in plans:
 f=B/'sources'/name;f.mkdir(parents=True,exist_ok=True)
 if (f/'receipt.json').exists():continue
 try:
  raw,r=fetch(url,f/'raw');(f/'original.bin').write_bytes(raw)
  if raw.startswith(b'%PDF'):text='\n'.join(p.extract_text(extraction_mode='layout') or '' for p in PdfReader(io.BytesIO(raw)).pages)
  else:d=Document();d.feed(raw.decode());text='\n'.join(d.text)
  (f/'original.txt').write_text(text);dump(f/'receipt.json',{'status':'SAVED','published':date,'url':url,'raw_sha256':sha(f/'original.bin'),'text_sha256':sha(f/'original.txt'),'receipt':r});print(name,'SAVED',len(text),flush=True)
 except Exception as e:dump(f/'receipt.json',{'status':'FAILED','error_type':type(e).__name__,'url':url});print(name,'FAILED',type(e).__name__,flush=True)

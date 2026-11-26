from common import *
import io,re
sys.path.insert(0,'/home/ansy/app/quant-diligence/task6-quanta-env/lib/python3.12/site-packages')
from pypdf import PdfReader
from quant_harness.investment.equities import fetch
from quant_harness.investment.company_outcomes import Document
f=B/'sources/US_ETN_PDF';f.mkdir(parents=True,exist_ok=True);u='https://www.eaton.com/content/dam/eaton/company/investor-relations/quarterly-earnings/filings/2026/q1/q1-2026-earnings-complete.pdf'
if not (f/'receipt.json').exists():
 try:
  raw,r=fetch(u,f/'raw');(f/'original.bin').write_bytes(raw);t='\n'.join(x.extract_text(extraction_mode='layout') or '' for x in PdfReader(io.BytesIO(raw)).pages);(f/'original.txt').write_text(t);(f/'normalized.txt').write_text('\n'.join(re.sub(r'[ \t\xa0]+',' ',s).strip() for s in t.splitlines() if s.strip()));dump(f/'receipt.json',{'id':'US_ETN_PDF','market':'US','published_claimed':'2026-05-05','kind':'primary','url':u,'status':'DOWNLOADED_NEEDS_ARTICLE_PUBLICATION_REVIEW','raw_sha256':sha(f/'original.bin'),'text_sha256':sha(f/'normalized.txt'),'receipt':r});print('ETN_PDF_DOWNLOADED',flush=True)
 except Exception as e:dump(f/'receipt.json',{'id':'US_ETN_PDF','market':'US','published_claimed':'2026-05-05','kind':'primary','url':u,'status':'FAILED','error_type':type(e).__name__});print('ETN_PDF_FAILED',type(e).__name__,flush=True)
f=B/'sources/KR_FOOD';raw=(f/'original.bin').read_bytes()
try:t=raw.decode('utf-8');encoding='UTF8'
except UnicodeDecodeError:t=raw.decode('cp949');encoding='CP949'
d=Document();d.feed(t);s='\n'.join(d.text);(f/'decoded_v2.txt').write_text(s);(f/'normalized_v2.txt').write_text('\n'.join(re.sub(r'[ \t\xa0]+',' ',line).strip() for line in s.splitlines() if line.strip()));freeze(f/'decode_repair.json',{'encoding':encoding,'raw_sha256':sha(f/'original.bin'),'new_text_hash':sha(f/'normalized_v2.txt'),'initial_replacement_decoded_text_preserved':True});print('KR_FOOD_DECODE',encoding)

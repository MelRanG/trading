from protocol import *
research_seal()
import io,re
from concurrent.futures import ThreadPoolExecutor
from quant_harness.investment.equities import fetch,load_environment
from quant_harness.investment.company_outcomes import Document
from quant_harness.v72_integration_ready.opendart import OpenDartClient
sys.path.insert(0,'/home/ansy/app/quant-diligence/task6-quanta-env/lib/python3.12/site-packages')
from pypdf import PdfReader
plans=[('ITA_OCC','2026-10-27','https://www.miaxglobal.com/sites/default/files/alert-files/ITA_Split_60055.pdf'),('AIR_Q4','2026-07-21','https://www.aarcorp.com/en/newsroom/press-releases/2026/aar-reports-fourth-quarter-and-fiscal-year-2026-results/'),('ETN_Q3','2026-11-03','https://www.eaton.com/content/dam/eaton/company/investor-relations/quarterly-earnings/filings/2026/q3/q3-2026-earnings-complete.pdf'),('GEV_Q3','2026-10-28','https://docs.publicnow.com/viewDoc?filename=242073%5CEXT%5CD4D477F09E949CE164BDD4070633C6AE2C6A1F33_2BD263575899A703D100CD3D05A719D40F76607A.PDF')]
freeze(B/'evaluation_source_plan.json',plans)
def run(row):
 ident,pub,url=row;f=B/'actuals'/ident;f.mkdir(parents=True,exist_ok=True)
 if (f/'receipt.json').exists():return
 try:
  raw,r=fetch(url,f/'raw');(f/'original.bin').write_bytes(raw)
  if raw.startswith(b'%PDF'):t='\n'.join(x.extract_text(extraction_mode='layout') or '' for x in PdfReader(io.BytesIO(raw)).pages)
  else:d=Document();d.feed(raw.decode('utf-8',errors='replace'));t='\n'.join(d.text)
  t='\n'.join(re.sub(r'[ \t\xa0]+',' ',s).strip() for s in t.splitlines() if s.strip());(f/'normalized.txt').write_text(t);assert len(t)>500
  dump(f/'receipt.json',{'status':'DOWNLOADED_DATE_REVIEW','published':pub,'url':url,'sha256':sha(f/'original.bin'),'text_sha256':sha(f/'normalized.txt'),'receipt':r});print(ident,len(t),flush=True)
 except Exception as e:dump(f/'receipt.json',{'status':'FAILED','error':type(e).__name__,'url':url,'published':pub});print(ident,type(e).__name__,flush=True)
with ThreadPoolExecutor(max_workers=3) as p:list(p.map(run,plans))
load_environment(R);dc=OpenDartClient();deep=json.loads((B/'deep_packets_v2.json').read_text())
for s in ['010120.KS','003230.KS','281820.KS']:
 x=next(x for x in deep if x['symbol']==s);f=B/'actuals'/s;f.mkdir(exist_ok=True);p=f/'accounts_Q3.json'
 if not p.exists():dump(p,dc._request('fnlttSinglAcntAll.json',{'corp_code':x['corp_code'],'bsns_year':'2026','reprt_code':'11014','fs_div':'CFS'}))
 print(s,'DART',json.loads(p.read_text()).get('status'),flush=True)

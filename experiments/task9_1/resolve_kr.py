"""Resolve missing share-class rows from original public reports, not amended APIs."""
from common import *
import io,zipfile,re
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(R/'experiments/task9_historical'))
from original_parser import text_and_identity
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);c=OpenDartClient()
def original(t):
 date,x=t;f=B/'inputs'/date/x['symbol'];p=f/'original.txt'
 if not p.exists():
  raw=c._request('document.xml',{'rcept_no':x['accession']},binary=True);(f/'original.zip').write_bytes(raw);z=zipfile.ZipFile(io.BytesIO(raw));text='\n'.join(text_and_identity(z.read(n))[0] for n in z.namelist() if n.lower().endswith('.xml'));p.write_text(text)
 text=p.read_text();matches=list(re.finditer(r'(?:주식의 총수|발행주식의 총수)',text));parts=[]
 for m in matches[-6:]:parts.append(text[max(0,m.start()-80):m.start()+1700])
 dump(f/'share_excerpts.json',{'accession':x['accession'],'published':x['source_published'],'sha256':sha(f/'original.zip'),'excerpts':parts})
 print(date,x['symbol'],'ORIGINAL',len(text),flush=True)
tasks=[]
for date in ['2024-11-29','2025-06-30']:
 for x in json.loads((B/'cohorts'/date/'KR_mainboard_v2.json').read_text()):
  f=B/'inputs'/date/x['symbol'];s=json.loads((f/'summary.json').read_text())
  if s.get('status')!='PRICE_ELIGIBLE':continue
  z=json.loads((f/'shares.json').read_text());valid=[v for v in z.get('list',[]) if v.get('rcept_no','9999')[:8]<=date.replace('-','') and (v.get('se','') in ['보통주','보통주식'] or '의결권 있는' in v.get('se',''))]
  def num(v):
   try:return int(v.replace(',',''))
   except:return 0
  shares=sum(num(v.get('istc_totqy','')) for v in valid)
  if shares:
   s.update(dated_report_shares=shares,dated_share_accessions=[v['rcept_no'] for v in valid],cap_proxy=shares*s['last_close'],size_status='PASS_DATED_REPORTED_SHARES_PROXY' if shares*s['last_close']>=500e9 else 'FAIL_SIZE')
   freeze(f/'summary_v2.json',s)
  else:tasks.append((date,x))
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(original,tasks))

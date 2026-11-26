"""Only previously selected issuers, historical prices and action original."""
from pathlib import Path
import sys,json,hashlib,zipfile,io
from urllib.request import Request,urlopen
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));sys.path.insert(0,str(R/'experiments/task9_historical'))
from quant_harness.investment.equities import load_environment,fetch
from quant_harness.v72_integration_ready.opendart import OpenDartClient
from original_parser import text_and_identity
load_environment(R);c=OpenDartClient();B=R/'runtime/task9_completion/selected';B.mkdir(exist_ok=True)
for accession in ['20211025000107','20220224901224']:
 folder=B/accession;folder.mkdir(exist_ok=True)
 if (folder/'receipt.json').exists():continue
 r={'provider':'OPENDART_ORIGINAL','accession':accession,'observed_at':datetime.now(timezone.utc).isoformat()}
 try:
  raw=c._request('document.xml',{'rcept_no':accession},binary=True);(folder/'original.zip').write_bytes(raw);z=zipfile.ZipFile(io.BytesIO(raw));texts=[]
  for n in z.namelist():
   if n.endswith('.xml'):t,meta=text_and_identity(z.read(n));texts.append(t)
  (folder/'original.txt').write_text('\n'.join(texts));r.update(status='SAVED',sha256=hashlib.sha256(raw).hexdigest())
 except Exception as e:r.update(status='FAILED',error_type=type(e).__name__)
 (folder/'receipt.json').write_text(json.dumps(r,indent=2));print(accession,r['status'],flush=True)
# Original-report cohort unchanged. Correct dated security venue from original reports.
for symbol in ['115610.KQ','950170.KQ','248070.KS','^KS11']:
 name=symbol.replace('^','INDEX_');p=B/(name+'.receipt.json')
 if p.exists():continue
 r={'symbol':symbol,'at':datetime.now(timezone.utc).isoformat(),'intended_scope':'SELECTED_COHORT_PRICE_CROSSCHECK'}
 try:
  raw,receipt=fetch('https://query1.finance.yahoo.com/v8/finance/chart/'+symbol.replace('^','%5E')+'?interval=1d&period1=1612137600&period2=1648771200&events=div%2Csplits',B/'raw');(B/(name+'.json')).write_bytes(raw);r.update(status='SAVED',receipt=receipt)
 except Exception as e:r.update(status='FAILED',error_type=type(e).__name__)
 p.write_text(json.dumps(r,indent=2));print(symbol,r['status'],flush=True)

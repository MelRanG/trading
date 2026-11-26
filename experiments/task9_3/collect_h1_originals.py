from common import *
import zipfile,io
sys.path.insert(0,str(R/'experiments/task9_historical'))
from original_parser import text_and_identity
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);c=OpenDartClient()
for p in (B/'updates').glob('*/accounts_H1.json'):
 z=json.loads(p.read_text());receipts=sorted({r['rcept_no'] for r in z.get('list',[])})
 if len(receipts)!=1:continue
 r=receipts[0];f=B/'primary'/p.parent.name/r[:8];f.mkdir(parents=True,exist_ok=True)
 if (f/'receipt.json').exists():continue
 try:
  raw=c._request('document.xml',{'rcept_no':r},binary=True);(f/'original.zip').write_bytes(raw);a=zipfile.ZipFile(io.BytesIO(raw));docs=[text_and_identity(a.read(n)) for n in a.namelist() if n.endswith('.xml')];t='\n'.join(x[0] for x in docs);(f/'original.txt').write_text(t);dump(f/'receipt.json',{'status':'SAVED','symbol':p.parent.name,'published':r[:8],'accession':r,'raw_sha256':sha(f/'original.zip'),'text_sha256':sha(f/'original.txt'),'identities':[x[1] for x in docs]});print(p.parent.name,r,'H1_ORIGINAL',len(t),flush=True)
 except Exception as e:dump(f/'receipt.json',{'status':'FAILED','symbol':p.parent.name,'published':r[:8],'error_type':type(e).__name__});print(p.parent.name,'FAILED',type(e).__name__,flush=True)

from protocol import *
research_seal()
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
import zipfile,io
sys.path.insert(0,str(R/'experiments/task9_historical'))
from original_parser import text_and_identity
load_environment(R);dc=OpenDartClient();deep=json.loads((B/'deep_packets_v2.json').read_text())
for s,date in [('010120.KS','20261021'),('003230.KS','20261106')]:
 x=next(x for x in deep if x['symbol']==s);f=B/'actuals'/s;p=f/'preliminary_list.json'
 if not p.exists():dump(p,dc._request('list.json',{'corp_code':x['corp_code'],'bgn_de':date,'end_de':date,'page_count':100}))
 z=json.loads(p.read_text());print(s,[(r['rcept_no'],r['report_nm']) for r in z.get('list',[])],flush=True)
 for r in z.get('list',[]):
  if '영업' not in r['report_nm'] or '잠정' not in r['report_nm']:continue
  q=f/(r['rcept_no']+'.zip')
  if not q.exists():q.write_bytes(dc._request('document.xml',{'rcept_no':r['rcept_no']},binary=True))
  zf=zipfile.ZipFile(io.BytesIO(q.read_bytes()));t='\n'.join(text_and_identity(zf.read(n))[0] for n in zf.namelist() if n.lower().endswith('.xml'));q.with_suffix('.txt').write_text(t)

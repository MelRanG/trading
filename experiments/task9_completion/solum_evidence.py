from pathlib import Path
import sys,json,zipfile,io,hashlib
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));sys.path.insert(0,str(R/'experiments/task9_historical'))
from quant_harness.investment.equities import load_environment,fetch
from quant_harness.v72_integration_ready.opendart import OpenDartClient
from original_parser import text_and_identity
load_environment(R);c=OpenDartClient();B=R/'runtime/task9_completion/selected';out=B/'solum_action_audit';out.mkdir(exist_ok=True)
for name,endpoint,params,binary in [('annual_2021','document.xml',{'rcept_no':'20220321000896'},True),('dividends_2021','alotMatter.json',{'corp_code':'01159233','bsns_year':'2021','reprt_code':'11011'},False)]:
 p=out/(name+('.zip' if binary else '.json'));meta=out/(name+'.receipt.json')
 if p.exists():continue
 receipt={'endpoint':endpoint,'public_params':params,'observed_at':datetime.now(timezone.utc).isoformat(),'purpose':'EVALUATOR_ONLY_CORPORATE_ACTION_AUDIT_NOT_RESEARCH_FORECAST_INPUT'}
 try:
  data=c._request(endpoint,params,binary=binary);raw=data if binary else json.dumps(data,sort_keys=True,ensure_ascii=False).encode();p.write_bytes(raw);receipt.update(status='SAVED',sha256=hashlib.sha256(raw).hexdigest())
  if binary:
   z=zipfile.ZipFile(io.BytesIO(raw));texts=[]
   for member in z.namelist():
    if member.endswith('.xml'):t,m=text_and_identity(z.read(member));texts.append(t)
   (out/(name+'.txt')).write_text('\n'.join(texts))
 except Exception as e:receipt.update(status='FAILED',error_type=type(e).__name__)
 meta.write_text(json.dumps(receipt,indent=2));print(name,receipt['status'])
# Dated original broker research is used ONLY to corroborate historical ticker identity.
p=out/'dated_ticker_source.receipt.json'
if not p.exists():
 try:
  raw,r=fetch('https://www.eugenefn.com/common/files/amail/20210531_248070_kyoungkt_627.pdf',out/'ticker_raw');(out/'dated_ticker_source.pdf').write_bytes(raw);p.write_text(json.dumps({'status':'SAVED',**r},indent=2));print('dated_ticker_source SAVED')
 except Exception as e:p.write_text(json.dumps({'status':'FAILED','error_type':type(e).__name__}));print('dated_ticker_source FAILED')

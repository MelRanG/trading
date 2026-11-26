from pathlib import Path
import sys,json,hashlib
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment,fetch
from quant_harness.investment.company_outcomes import Document
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);dart=OpenDartClient();b=R/'runtime/task8b/fundamentals';cases=json.loads((b/'cases.json').read_text())
extra={'HRMY':'https://ir.harmonybiosciences.com/news-releases/news-release-details/harmony-biosciences-reports-q3-financial-results-track-achieve','AMKR':'https://ir.amkor.com/static-files/f3bab1a5-97b1-42fe-a1d8-c2f293d2cef2','BE':'https://investor.bloomenergy.com/press-releases/press-release-details/2026/Bloom-Energy-Reports-Record-Third-Quarter-2026-Financial-Results-and-Raises-Full-Year-2026-Guidance/default.aspx'}
for c in cases:
 if any(s.get('source_id','').endswith('_SUPPLEMENT') for s in c['sources']):continue
 if c['ticker'] in extra:
  symbol=c['ticker'];sid=symbol+'_SUPPLEMENT'
  try:
   raw,receipt=fetch(extra[symbol],b/symbol/'supplement',limit=3_000_000)
   if raw.startswith(b'%PDF'):
    path=b/symbol/'supplement/source.pdf';path.write_bytes(raw)
    import subprocess
    subprocess.run(['pdftotext','-layout',str(path),str(path.with_suffix('.txt'))],check=True);text=path.with_suffix('.txt').read_text()
   else:
    d=Document();d.feed(raw.decode('utf-8',errors='replace'));text='\n'.join(d.text)
   c['sources'].append({'source_id':sid,'url':extra[symbol],'text':text[:60000],'receipt':receipt,'source_class':'OFFICIAL_COMPANY_RELEASE'})
  except Exception as exc:c['sources'].append({'source_id':sid,'status':'FAILED','error_type':type(exc).__name__,'url':extra[symbol]})
 if c['ticker']=='068760.KQ':
  identity=next(s['data'] for s in c['sources'] if s['source_id'].endswith('_identity'));params={'corp_code':identity['corp_code'],'bsns_year':'2026','reprt_code':'11012','fs_div':'OFS'};result=dart._request('fnlttSinglAcntAll.json',params);raw=json.dumps(result,ensure_ascii=False,sort_keys=True).encode();(b/'068760.KS/q2_OFS.json').write_bytes(raw);c['sources'].append({'source_id':'068760_q2_OFS','data':result,'receipt':{'source_hash':hashlib.sha256(raw).hexdigest(),'available_at':datetime.now(timezone.utc).isoformat(),'public_params':params,'status':result['status']},'source_class':'OFFICIAL_REGULATORY_API_OFS_NOT_CFS'})
(b/'cases_supplemented.json').write_text(json.dumps(cases,indent=2,ensure_ascii=False));print(json.dumps([{'ticker':c['ticker'],'success':sum(s.get('status')!='FAILED' and s.get('receipt',{}).get('status','000')=='000' for s in c['sources'])} for c in cases],indent=2))

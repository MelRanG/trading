from pathlib import Path
import sys,json,hashlib
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);client=OpenDartClient();b=R/'runtime/task8b';packet=json.loads((b/'research_packet.json').read_text())
for c in packet['cases']:
 if c['market']!='KR':continue
 identity=next(s['data'] for s in c['sources'] if s['source_id'].endswith('_identity'));params={'corp_code':identity['corp_code'],'bsns_year':'2026','reprt_code':'11014','fs_div':'OFS' if c['ticker']=='068760.KQ' else 'CFS'};p=b/'fundamentals'/(c['ticker']+'_q3.json');meta=p.with_suffix('.receipt.json')
 if p.exists():data=json.loads(p.read_text());receipt=json.loads(meta.read_text())
 else:
  data=client._request('fnlttSinglAcntAll.json',params);raw=json.dumps(data,sort_keys=True,ensure_ascii=False).encode();p.write_bytes(raw);receipt={'source_hash':hashlib.sha256(raw).hexdigest(),'available_at':datetime.now(timezone.utc).isoformat(),'public_params':params,'status':data.get('status'),'provider':'OFFICIAL_OPENDART'};meta.write_text(json.dumps(receipt))
 c['sources'].append({'source_id':c['ticker']+'_Q3_CURRENT','data':data,'receipt':receipt,'source_class':'OFFICIAL_REGULATORY_QUARTER_API'})
(b/'research_packet_v2.json').write_text(json.dumps(packet,indent=2,ensure_ascii=False));print(json.dumps({c['ticker']:c['sources'][-1]['receipt']['status'] for c in packet['cases'] if c['market']=='KR'},indent=2))

"""Documented public SAMPLE API only; ten index rows prove market date, not universe."""
from pathlib import Path
from urllib.request import Request,urlopen
from datetime import date,timedelta,datetime,timezone
import re,json,hashlib,time
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_completion';out=B/'sessions';out.mkdir(exist_ok=True)
plan={'source':'Official public documented sample KOSPI-series endpoint; no production key or endpoint','source_document':str((B/'access/krx_detail_0.raw').relative_to(R)),'first_candidate_date':'2021-11-30','holding_sessions':63,'entry':'First official observed active session after2021-11-30','exit':'First official session after63 completed holding sessions including entry','request_cap':90,'request_spacing_seconds':.4,'scope':'Only10sample index rows, not full universe or substitute KOSPI benchmark; source current retrieval proves historical date condition'}
p=out/'contract.json'
if p.exists():assert json.loads(p.read_text())==plan
else:p.write_text(json.dumps(plan,indent=2))
html=(B/'access/krx_detail_0.raw').read_text();key=re.search(r'name="AUTH_KEY" value="([^"]+)"',html).group(1);d=date(2021,11,30);active=[];records=[]
while len(active)<65:
 if d.weekday()>=5:d+=timedelta(days=1);continue
 day=d.strftime('%Y%m%d');p=out/(day+'.json');rawp=out/(day+'.raw.json')
 if not p.exists():
  if len(list(out.glob('*.raw.json')))>=plan['request_cap']:raise ValueError('Session audit source budget')
  url='https://data-dbg.krx.co.kr/svc/sample/apis/idx/kospi_dd_trd?basDd='+day
  with urlopen(Request(url,headers={'AUTH_KEY':key,'User-Agent':'QuantHarness documented sample/1.0'}),timeout=20) as s:raw=s.read(1000000)
  if key.encode() in raw:raise ValueError('Auth echoed')
  payload=json.loads(raw)
  if 'OutBlock_1' not in payload:raise ValueError('Not an index data response')
  rows=payload['OutBlock_1']
  if any(r.get('BAS_DD')!=day for r in rows):raise ValueError('Sample ignores requested date')
  r={'day':d.isoformat(),'status':'OBSERVED_ACTIVE_EXCHANGE_DATE' if rows else 'NO_MARKET_ROWS','source_hash':hashlib.sha256(raw).hexdigest(),'url':url,'observed_at':datetime.now(timezone.utc).isoformat(),'sample_rows':len(rows),'scope':'Official dated10-index sample, not stock-listing proof'};rawp.write_bytes(raw);p.write_text(json.dumps(r,indent=2));time.sleep(plan['request_spacing_seconds'])
 r=json.loads(p.read_text());records.append(r)
 if r['sample_rows']:active.append(r)
 print(d,r['status'],len(active),flush=True);d+=timedelta(days=1)
result={'active':active,'queried':records,'asof':active[0],'entry':active[1],'holding':active[1:64],'exit':active[64],'price_benchmark':'Not present in10sample indices; separately query actual KOSPI index'};(out/'manifest.json').write_text(json.dumps(result,indent=2));print('READY',active[1]['day'],active[64]['day'],flush=True)

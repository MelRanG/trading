"""Bounded primary-source snapshots for autonomously selected companies."""
from pathlib import Path
import json,hashlib,sys,re
from urllib.request import Request,urlopen
from datetime import datetime,timezone
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
from quant_harness.investment.operations_data import strict_rows,ZONES
sources={
'NVDA': [('NVDA_IR','https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Second-Quarter-Fiscal-2027/','2026-08-26')],
'CRWV': [('CRWV_IR','https://investors.coreweave.com/news/news-details/2026/CoreWeave-Reports-Strong-Third-Quarter-2026-Results/default.aspx','2026-11-10'),('CRWV_SEC','https://www.sec.gov/Archives/edgar/data/1769628/000176962826000461/coreweave3q26earningspress.htm','2026-11-10')]}
class Text(HTMLParser):
 def __init__(self):super().__init__();self.drop=0;self.parts=[]
 def handle_starttag(self,tag,attrs):
  if tag in ['script','style']:self.drop+=1
 def handle_endtag(self,tag):
  if tag in ['script','style']:self.drop=max(0,self.drop-1)
 def handle_data(self,data):
  if not self.drop and data.strip():self.parts.append(data.strip())
load_environment(ROOT);client=TossOpenApiClient();out=ROOT/'runtime/task7/company';out.mkdir(exist_ok=True);discovery=json.loads((ROOT/'runtime/task7/leads/discovery_final.json').read_text());cases=[]
for selected in discovery['deep_cases']:
 symbol=selected['ticker'];case={**selected,'observed_at':datetime.now(timezone.utc).isoformat(),'sources':[],'prices':None,'consensus':'NOT_AVAILABLE; guidance is not sell-side consensus','forecast_status':'PENDING_FUTURE_RELEASE','trade_authority':'NONE'}
 for sid,url,published in sources[symbol]:
  record={'source_id':sid,'url':url,'published_date':published,'source_class':'PRIMARY_COMPANY_RELEASE' if '_IR' in sid else 'OFFICIAL_SEC_EXHIBIT'}
  try:
   raw=urlopen(Request(url,headers={'User-Agent':'ansy research identity (research contact configured locally)'}),timeout=25).read(3_000_000);h=hashlib.sha256(raw).hexdigest();(out/(sid+'.raw.html')).write_bytes(raw);parser=Text();parser.feed(raw.decode('utf-8',errors='replace'));text='\n'.join(parser.parts)
   # Use issuer's main body, preserve the complete original separately.
   start=text.find('Revenue of $96.2') if symbol=='NVDA' else text.find('Disciplined Growth at Scale')
   if start<0:start=0
   body=text[start:];(out/(sid+'.txt')).write_text(body);record.update(status='SAVED',available_at=datetime.now(timezone.utc).isoformat(),sha256=h,text=body[:36000])
  except Exception as e:record.update(status='FAILED',reason=str(e),error_type=type(e).__name__)
  case['sources'].append(record)
 try:
  payload=client._request('GET',client.endpoint_map.candles_path,query={'symbol':symbol,'interval':'1d','count':50,'adjusted':'true'});raw=json.dumps(payload,sort_keys=True).encode();h=hashlib.sha256(raw).hexdigest();(out/(symbol+'_prices.raw.json')).write_bytes(raw);frame=strict_rows(payload,symbol,'USD',ZONES['US'],'2026-11-12');last=frame.iloc[-1];frame.to_csv(out/(symbol+'_prices.csv'),index=False);case['prices']={'status':'VERIFIED_BOUNDED_DAILY_SNAPSHOT','source':'TOSS_ADJUSTED_DAILY','source_hash':h,'available_at':datetime.now(timezone.utc).isoformat(),'last_complete_session':str(last.date),'close':float(last.close),'currency':'USD','not_current_intraday_quote':True,'corporate_actions_independently_certified':False}
 except Exception as e:case['prices']={'status':'FAILED','reason':str(e)}
 cases.append(case);print(symbol,[(x['source_id'],x['status']) for x in case['sources']],case['prices']['status'],flush=True)
packet={'version':'TASK7_COMPANY_INPUT_V1','selection':'Original Vibe autonomous broad scan, then listing eligibility resolution. NVDA prior ticker; CRWV new. No user-specified company.','cases':cases,'instructions':'Only supplied source facts; cite source IDs. Forecast not guidance repetition. Numeric base/bull/bear with explicit assumptions; identify FCF/capital needs and falsification. Missing inputs/consensus means abstain. No immediate stock orders.'}
(out/'packet.json').write_text(json.dumps(packet,indent=2,ensure_ascii=False));(out/'packet_hash.json').write_text(json.dumps({'sha256':hashlib.sha256((out/'packet.json').read_bytes()).hexdigest()},indent=2))

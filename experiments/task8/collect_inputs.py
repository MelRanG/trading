"""At most4 public/readonly provider calls; raw receipts retain actual first observation."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys,psycopg
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.investment.operations_data import parse_calendar,strict_rows,ZONES
from quant_harness.investment.operations import latest_completed
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
b=R/'runtime/task8/market';b.mkdir(exist_ok=True);out=b/'inputs.json'
if out.exists():print('FROZEN_INPUTS_EXIST_NO_REDOWNLOAD');raise SystemExit(0)
load_environment(R);client=TossOpenApiClient();receipts=[]
def call(name,path,query=None):
 existing=b/(name+'.json')
 if existing.exists():
  raw=json.loads(existing.read_bytes());receipt={'path':str(existing.relative_to(R)),'source_hash':hashlib.sha256(existing.read_bytes()).hexdigest(),'available_at':datetime.fromtimestamp(existing.stat().st_mtime,timezone.utc).isoformat(),'reused_snapshot':True};receipts.append(receipt);return raw,receipt
 raw=client._request('GET',path,query=query);encoded=json.dumps(raw,sort_keys=True).encode();p=b/(name+'.json');p.write_bytes(encoded);receipt={'path':str(p.relative_to(R)),'source_hash':hashlib.sha256(encoded).hexdigest(),'available_at':datetime.now(timezone.utc).isoformat()};receipts.append(receipt);return raw,receipt
calendar,receipt=call('calendar','/api/v1/market-calendar/US');sessions=parse_calendar(calendar,'US');
try:completed=latest_completed({'sessions':sessions},receipt['available_at'])
except ValueError:
 # Reuse a previously observed OFFICIAL session, never infer a missing trading day.
 with psycopg.connect('postgresql://quant_ops@127.0.0.1:55432/quant_task3_ops',options='-c default_transaction_read_only=on') as conn:
  row=conn.execute("SELECT day,opening,closing,source_hash,observed_at FROM ops_session WHERE market='US' AND closing<%s AND observed_at<=%s ORDER BY closing DESC LIMIT 1",(receipt['available_at'],receipt['available_at'])).fetchone()
 if not row:raise ValueError('no verified completed session in provider or existing immutable session store')
 completed={'market':'US','day':str(row[0]),'opening':row[1].isoformat(),'closing':row[2].isoformat(),'source_hash':row[3],'observed_at':row[4].isoformat(),'reused_official_session':True}
prices={}
for symbol in ['NVDA','CRWV']:
 try:
  payload,receipt=call(symbol+'_candles',client.endpoint_map.candles_path,{'symbol':symbol,'interval':'1d','count':140,'adjusted':'true'});frame=strict_rows(payload,symbol,'USD',ZONES['US'],completed['day']);frame.to_csv(b/(symbol+'.csv'),index=False);prices[symbol]={'rows':len(frame),'last_completed':str(frame.date.iloc[-1]),'meta':{'instrumentType':'EQUITY'},'receipt':receipt}
 except Exception as exc:prices[symbol]={'status':'ABSTAIN','error_type':type(exc).__name__}
try:
 quotes,receipt=call('quotes',client.endpoint_map.quote_path,{'symbols':'NVDA,CRWV'});quote_quality={'status':'OBSERVED','source_hash':receipt['source_hash'],'available_at':receipt['available_at'],'row_fields':[sorted(x) for x in quotes.get('result',[])],'spread_status':'UNVERIFIED_UNLESS_TIMESTAMPED_BID_AND_ASK_PRESENT'}
except Exception as exc:quote_quality={'status':'UNAVAILABLE','error_type':type(exc).__name__}
result={'sessions':sessions,'completed':completed,'prices':prices,'quote_quality':quote_quality,'receipts':receipts,'calls':len(receipts),'corporate_action_certification':'NOT_INDEPENDENTLY_CERTIFIED_RESEARCH_ONLY'};out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

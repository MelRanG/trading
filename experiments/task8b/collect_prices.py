"""Selective US/KR price capture; existing official sessions and raw snapshots reused."""
from pathlib import Path
from datetime import datetime,timezone
import json,sys,hashlib,psycopg
import pandas as pd
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.investment.operations_data import strict_rows,ZONES
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
b=R/'runtime/task8b/prices';b.mkdir(exist_ok=True);out=b/'manifest.json'
if out.exists():print('USE_FROZEN_PRICE_INPUTS');raise SystemExit(0)
cases=json.loads((R/'runtime/task8b/fundamentals/cases.json').read_text());load_environment(R);client=TossOpenApiClient();clock=datetime.now(timezone.utc);sessions={};items={};requests=0
with psycopg.connect('postgresql://quant_ops@127.0.0.1:55432/quant_task3_ops',options='-c default_transaction_read_only=on') as conn:
 for market in ['US','KR']:
  rows=conn.execute('SELECT day,opening,closing,source_hash,observed_at FROM ops_session WHERE market=%s AND observed_at<=%s ORDER BY opening',(market,clock)).fetchall()
  completed=[x for x in rows if x[2]<clock]
  if not completed:raise ValueError('no previously observed official completed session '+market)
  last=completed[-1];sessions[market]={'completed':{'day':str(last[0]),'opening':last[1].isoformat(),'closing':last[2].isoformat(),'source_hash':last[3],'observed_at':last[4].isoformat()},'sessions':[{'day':str(x[0]),'opening':x[1].isoformat(),'closing':x[2].isoformat(),'source_hash':x[3]} for x in rows[-6:]]}
 for market,symbol in [(x['market'],x['ticker']) for x in cases]+[('US','SPY'),('KR','069500.KS')]:
  row=conn.execute("SELECT r.payload FROM ops_pointer p JOIN investment_record r ON r.record_id=p.record_id WHERE p.name=%s",('price:'+market+':'+symbol,)).fetchone()
  if row:
   data=row[0];frame=pd.DataFrame(data['frame'])
   if frame.date.iloc[-1]==sessions[market]['completed']['day']:
    frame.to_csv(b/(symbol+'.csv'),index=False);items[symbol]={'market':market,'source':'REUSED_IMMUTABLE_TASK5_PRICE','receipt':data['receipt'],'meta':data['meta'],'raw_verified':True,'rows':len(frame),'as_of':frame.date.iloc[-1]}
for market,symbol in [(x['market'],x['ticker']) for x in cases]+[('US','SPY'),('KR','069500.KS')]:
 if symbol in items:continue
 native=symbol.split('.')[0] if market=='KR' else symbol
 try:
  requests+=1;payload=client._request('GET',client.endpoint_map.candles_path,query={'symbol':native,'interval':'1d','count':200,'before':sessions[market]['completed']['closing'],'adjusted':'true'});encoded=json.dumps(payload,sort_keys=True).encode();(b/(symbol+'.raw.json')).write_bytes(encoded);at=datetime.now(timezone.utc).isoformat();frame=strict_rows(payload,symbol,'USD' if market=='US' else 'KRW',ZONES[market],sessions[market]['completed']['day']);frame.to_csv(b/(symbol+'.csv'),index=False)
  if frame.date.iloc[-1]!=sessions[market]['completed']['day']:raise ValueError('stale history')
  from quant_harness.v87_actual_data_ingestion.engine import ProviderBatch,_validate_batch,_load_config,_revision_audit
  records=frame.assign(ticker='000001')[['date','ticker','open','high','low','close','volume','value_approx']].to_dict('records');normalized=_validate_batch(ProviderBatch('TOSS_EQUITY','000001',tuple(records),True,'toss_openapi_1d_adjusted',at,{}),_load_config(R));revision=_revision_audit(normalized,b/(symbol+'.never_canonical.csv'),_load_config(R))
  items[symbol]={'market':market,'receipt':{'source_hash':hashlib.sha256(encoded).hexdigest(),'available_at':at},'meta':{'instrumentType':'ETF' if symbol in ['SPY','069500.KS'] else 'EQUITY'},'raw_verified':False,'as_of':frame.date.iloc[-1],'rows':len(frame),'v87_gate':'PASSED','revision_gate':revision,'canonical_replaced':False}
 except Exception as exc:items[symbol]={'market':market,'status':'RESEARCH_INCOMPLETE','error_type':type(exc).__name__}
try:
 requests+=1;raw=client._request('GET',client.endpoint_map.quote_path,query={'symbols':','.join(c['ticker'].split('.')[0] if c['market']=='KR' else c['ticker'] for c in cases)});encoded=json.dumps(raw,sort_keys=True).encode();(b/'quotes_initial.json').write_bytes(encoded);quotes={'data':raw,'available_at':datetime.now(timezone.utc).isoformat(),'source_hash':hashlib.sha256(encoded).hexdigest(),'spread':'NO_VERIFIED_BID_ASK'}
except Exception as exc:quotes={'status':'FAILED','error_type':type(exc).__name__}
result={'sessions':sessions,'items':items,'quotes':quotes,'provider_requests':requests,'new_history_is_forward_evidence':False,'point_in_time_universe':'Current observed common-equity metadata; historical survivorship membership not reconstructed'};out.write_text(json.dumps(result,indent=2,default=str));print(json.dumps({'requests':requests,'items':{s:{k:v.get(k) for k in ['as_of','rows','status','error_type','raw_verified']} for s,v in items.items()}},indent=2))

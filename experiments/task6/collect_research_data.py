"""Trusted host-only bounded GET collector. No model or broker mutation calls."""
from pathlib import Path
import sys,json,time,hashlib
from datetime import datetime,timedelta,timezone
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.equities import load_environment,us_catalog,kr_catalog
from quant_harness.investment.operations_data import parse_calendar,strict_rows,ZONES
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
from quant_harness.v87_actual_data_ingestion.engine import ProviderBatch,_validate_batch,_load_config
load_environment(ROOT);contract=json.loads((Path(__file__).parent/'research_contract.json').read_text());out=ROOT/'runtime/task6/data';out.mkdir(parents=True,exist_ok=True)
(rawdir:=out/'raw').mkdir(exist_ok=True);(accepted:=out/'accepted').mkdir(exist_ok=True)
receiptfile=out/'requests.jsonl';calls=len(receiptfile.read_text().splitlines()) if receiptfile.exists() else 0
client=TossOpenApiClient();quality=_load_config(ROOT)


def request(market,path,query=None):
 global calls
 if calls>=contract['data_request_budget']:raise ValueError('data budget exhausted')
 calls+=1;start=time.monotonic();record={'sequence':calls,'market':market,'path':path,'query':query,'at':datetime.now(timezone.utc).isoformat(),'status':'RESERVED'}
 with receiptfile.open('a') as f:f.write(json.dumps(record)+'\n')
 time.sleep(contract['data_spacing_seconds'])
 payload=client._request('GET',path,query=query);encoded=json.dumps(payload,sort_keys=True).encode();h=hashlib.sha256(encoded).hexdigest();target=rawdir/(h+'.json')
 if not target.exists():target.write_bytes(encoded)
 record.update(status='SAVED',source_hash=h,available_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start)
 with (out/'receipts.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
 return payload,record

manifest={'contract_hash':hashlib.sha256((Path(__file__).parent/'research_contract.json').read_bytes()).hexdigest(),'markets':{},'observed_at':datetime.now(timezone.utc).isoformat(),'PIT_membership_verified':False}
for market in ('US','KR'):
 cal,cal_receipt=request(market,'/api/v1/market-calendar/'+market);sessions=parse_calendar(cal,market);current=datetime.now(timezone.utc)
 eligible=[r for r in sessions if datetime.fromisoformat(r['closing'])+timedelta(minutes=5)<current]
 if not eligible:raise ValueError('no completed official session')
 last=max(eligible,key=lambda x:x['day']);catalog=us_catalog(rawdir) if market=='US' else kr_catalog(rawdir)
 (out/(market+'_catalog.json')).write_text(json.dumps(catalog));listed={r['symbol'] for r in catalog['rows'] if r.get('common_stock_verified')} if market=='US' else {r['stock_code']+'.KS' for r in catalog['rows']}
 marketrows={}
 for symbol in contract[market]+[contract['benchmarks'][market]]:
  target=accepted/(symbol+'.csv');meta=accepted/(symbol+'.receipt.json')
  if target.exists() and meta.exists():marketrows[symbol]=json.loads(meta.read_text());continue
  receipts=[]
  try:
   if symbol in contract[market] and symbol not in listed:raise ValueError('current listing not verified')
   cursor=last['closing'];frames=[];oldest=None
   for page in range(contract['history_pages']):
    payload,receipt=request(market,client.endpoint_map.candles_path,{'symbol':symbol.split('.')[0] if market=='KR' else symbol,'interval':'1d','count':200,'before':cursor,'adjusted':'true'})
    receipts.append(receipt);frame=strict_rows(payload,symbol,'USD' if market=='US' else 'KRW',ZONES[market],last['day'])
    if oldest and frame.date.iloc[0]>=oldest:raise ValueError('pagination stalled')
    oldest=frame.date.iloc[0];frames.append(frame)
    cursor=payload.get('result',{}).get('nextBefore')
    if not cursor:break
    if len(frame)<190:break
   joined=pd.concat(frames).sort_values('date');duplicates=joined[joined.date.duplicated(False)]
   for day,g in duplicates.groupby('date'):
    if len(g[['open','high','low','close','volume']].drop_duplicates())>1:raise ValueError('revision within pagination')
   joined=joined.drop_duplicates('date');records=joined.assign(ticker='000001')[['date','ticker','open','high','low','close','volume','value_approx']].to_dict('records')
   _validate_batch(ProviderBatch('TOSS_EQUITY','000001',tuple(records),True,'toss_openapi_1d_adjusted',receipts[-1]['available_at'],{}),quality)
   if len(joined)<700 or joined.date.iloc[-1]!=last['day']:raise ValueError('history/freshness insufficient')
   joined.to_csv(target,index=False);item={'status':'ACCEPTED','symbol':symbol,'rows':len(joined),'start':joined.date.iloc[0],'end':joined.date.iloc[-1],'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'receipts':receipts,'v87_gate':'PASSED','pagination_contract':'PROVIDER_NEXT_BEFORE','adjusted_ohlc_provider_claim_not_independent_corporate_action_certification':True}
   meta.write_text(json.dumps(item,indent=2));marketrows[symbol]=item
  except Exception as exc:
   item={'status':'FAILED','symbol':symbol,'error_type':type(exc).__name__,'reason':str(exc)[:180],'receipts':receipts};marketrows[symbol]=item
   (out/(symbol+'.failure.json')).write_text(json.dumps(item,indent=2))
  print(market,symbol,marketrows[symbol]['status'],flush=True)
 manifest['markets'][market]={'session':last,'calendar_receipt':cal_receipt,'symbols':marketrows}
 (out/'manifest.partial.json').write_text(json.dumps(manifest,indent=2))
(out/'manifest.json').write_text(json.dumps(manifest,indent=2));print('DONE',calls,flush=True)

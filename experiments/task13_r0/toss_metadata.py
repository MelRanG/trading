"""Documented bulk metadata, GET only; actual HTTP attempts counted inclOAuth."""
from pathlib import Path
import json,time,datetime,hashlib,fcntl
from urllib.parse import urlencode
from network import B,Network,CircuitOpen
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
R=Path(__file__).resolve().parents[2];load_environment(R);last=0

def transport(req,timeout):
 global last
 # Never log request headers/body. OAuth responses are never archived.
 time.sleep(max(0,1-(time.monotonic()-last)));last=time.monotonic()
 ledger=B/'requests.jsonl'
 with (B/'.request.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);count=len(ledger.read_text().splitlines()) if ledger.exists() else 0
  if count>=500:raise CircuitOpen('GLOBAL_REQUEST_BUDGET_500')
  with ledger.open('a') as f:f.write(json.dumps({'id':count+1,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host':'openapi.tossinvest.com','path':req.full_url.split('?')[0],'category':'toss_OAUTH' if req.method=='POST' else 'toss_bulk_metadata','method':req.method,'status':'RESERVED'})+'\n')
 status,headers,raw=TossOpenApiClient._default_transport(req,timeout)
 with (B/'toss_response_status.jsonl').open('a') as f:f.write(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':status,'path':req.full_url.split('?')[0],'rate_headers':{k:v for k,v in headers.items() if any(s in k.lower() for s in ['ratelimit','rate-limit','retry-after'])}})+'\n')
 if status in [401,403,429]:raise CircuitOpen('TOSS_AUTH_OR_LIMIT_'+str(status))
 return status,headers,raw
client=TossOpenApiClient(transport=transport);cache=B/'toss_metadata';cache.mkdir(exist_ok=True)
def get(path,query):
 key=hashlib.sha256(json.dumps([path,query],sort_keys=True).encode()).hexdigest();p=cache/(key+'.json');r=cache/(key+'.receipt.json')
 if p.exists():
  d=json.loads(r.read_text());assert hashlib.sha256(p.read_bytes()).hexdigest()==d['source_hash'];return json.loads(p.read_text()),d
 raw=client._request('GET',path,query=query);enc=json.dumps(raw,sort_keys=True).encode();p.write_bytes(enc);d={'path':str(p.relative_to(R)),'source_hash':hashlib.sha256(enc).hexdigest(),'available_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'provider':'TOSS_OFFICIAL_GET','endpoint':path,'query':query};r.write_text(json.dumps(d,indent=2));return raw,d
def main():
 md=json.loads((B/'universe_metadata.json').read_text());out={'markets':{},'delisted':{},'errors':[]}
 for board in ['KOSPI','KOSDAQ']:
  try:
   # Listing snapshot is light metadata; no full-market price history.
   x,listing_receipt=get('/api/v1/stocks/all',{'market':board,'status':'ACTIVE','securityType':'STOCK','commonShare':'true'});ls=x['result'];assert isinstance(ls,list);codes=[r['symbol'] for r in ls if r.get('isCommonShare') is True]
   rows=[];receipts=[listing_receipt]
   for i in range(0,len(codes),200):
    chunk=codes[i:i+200];info,ir=get('/api/v1/stocks',{'symbols':','.join(chunk)});quotes,qr=get('/api/v1/prices',{'symbols':','.join(chunk)});receipts.extend([ir,qr]);im={r['symbol']:r for r in info['result']};qm={r['symbol']:r for r in quotes['result']}
    for code in chunk:
     a=im.get(code);q=qm.get(code)
     if not a or not q:continue
     value=q.get('price',q);price=value.get('lastPrice');shares=a.get('sharesOutstanding')
     if price is None or shares is None:continue
     rows.append({**a,'latest_price':float(price),'current_cap_KRW':float(price)*float(shares),'cap_timestamp':q.get('timestamp',qr['available_at']),'current_size_not_PIT':True})
   out['markets'][board]={'rows':rows,'receipts':receipts,'current_meta_not_historical_universe':True};print(board,'META',len(rows),flush=True)
   x,r=get('/api/v1/stocks/all',{'market':board,'status':'DELISTED','securityType':'STOCK','commonShare':'true'});out['delisted'][board]={'rows':x['result'],'receipt':r,'not_complete_historical_delisting_tape':True};print(board,'DELISTED_META',len(x['result']),flush=True)
  except Exception as e:out['errors'].append({'board':board,'error':type(e).__name__+':'+str(e)[:150]});print(board,'FAILED',out['errors'][-1]['error'],flush=True);break
  (B/'toss_universe_metadata.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 (B/'toss_universe_metadata.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()

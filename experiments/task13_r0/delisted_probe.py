"""Small actual delisted-history feasibility test, never map stale tickers silently."""
import json
from pathlib import Path
from toss_metadata import get,B
from collect import collect
from network import Network
x=json.loads((B/'extra_identity.json').read_text());codes=[r['symbol'] for board in x['delisted'].values() for r in board['rows']]
raw,receipt=get('/api/v1/stocks',{'symbols':','.join(codes)});rows=raw['result'];eligible=sorted([r for r in rows if r.get('delistDate') and '2017-01-01'<=r['delistDate']<='2026-11-13' and r.get('listDate') and r['listDate']<'2020-01-01' and r.get('status')=='DELISTED'],key=lambda r:(r['delistDate'],r['symbol']))
selected=eligible[:5];(B/'delisted_plan.json').write_text(json.dumps({'selection':'Earliest eligible delistdates; before Yahoo history lookup, no returnbased selection','all_metadata_count':len(rows),'candidates':selected,'receipt':receipt,'KR_metadata_delisted_count':0,'complete_historical_universe':False},ensure_ascii=False,indent=2)+'\n');n=Network();results=[]
for r in selected:
 a={'market':'US','symbol':r['symbol'],'role':'DELISTED_HISTORY_PROBE','list_date_toss':r['listDate'],'delist_date':r['delistDate'],'isin':r.get('isinCode'),'PIT_membership':'HISTORICAL_IDENTITY_PARTIAL_NO_COMPLETE_MEMBERSHIP'}
 try:results.append(collect(a,n))
 except Exception as e:results.append({'symbol':a['symbol'],'status':'FAILED_NO_MAPPING_OR_PRICE_REPAIR','reason':type(e).__name__+':'+str(e)[:120]})
(B/'delisted_result.json').write_text(json.dumps(results,indent=2)+'\n');print(results)

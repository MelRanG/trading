from pathlib import Path
import json
from toss_metadata import get,B
assets=json.loads((B/'universe.json').read_text());out={'US':{},'delisted':{},'errors':[]}
try:
 us=[r['symbol'] for r in assets if r['market']=='US'];x,r=get('/api/v1/stocks',{'symbols':','.join(us)});out['US']={'rows':x['result'],'receipt':r};print('US_IDENTITY',len(x['result']),flush=True)
 for market in ['NYSE','NASDAQ']:
  x,r=get('/api/v1/stocks/all',{'market':market,'status':'DELISTED','securityType':'STOCK','commonShare':'true'});out['delisted'][market]={'rows':x['result'],'receipt':r,'complete_history_verified':False};print('DELISTED',market,len(x['result']),flush=True)
 for market in ['US','KR']:
  x,r=get('/api/v1/market-calendar/'+market,{});out['calendar_'+market]={'result':x,'receipt':r,'coverage':'CURRENT_SESSIONS_ONLY_NOT_2017_2026_CALENDAR'}
except Exception as e:out['errors'].append({'error':type(e).__name__+':'+str(e)[:200]})
(B/'extra_identity.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')

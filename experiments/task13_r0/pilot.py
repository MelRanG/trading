from pathlib import Path
import json,datetime,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));from network import Network,B
from urllib.parse import quote
n=Network();start=int(datetime.datetime(2017,1,1,tzinfo=datetime.timezone.utc).timestamp());end=int(datetime.datetime(2026,11,14,tzinfo=datetime.timezone.utc).timestamp());rows=[]
for symbol in ['AAPL','MSFT','XOM','JPM','AMAT','005930.KS','000660.KS','005380.KS','035420.KS','247540.KQ']:
 try:
  url='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(symbol,safe='')+f'?interval=1d&period1={start}&period2={end}&events=div%2Csplits';raw,receipt=n.get(url);z=json.loads(raw)['chart']['result'][0];assert z['meta']['symbol'].upper()==symbol.upper();rows.append({'symbol':symbol,'status':'RAW_SAVED_PENDING_QUALITY','bars':len(z['timestamp']),'first':min(z['timestamp']),'last':max(z['timestamp']),'receipt':receipt});print(symbol,rows[-1]['status'],rows[-1]['bars'],flush=True)
 except Exception as exc:rows.append({'symbol':symbol,'status':'FAILED','error':type(exc).__name__+':'+str(exc)[:150]});print(symbol,rows[-1]['error'],flush=True)
 (B/'pilot.json').write_text(json.dumps(rows,indent=2))

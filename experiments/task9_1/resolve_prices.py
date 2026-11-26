from common import *
from quant_harness.investment.equities import fetch
import ast,pandas as pd
symbols=sorted({x['symbol'] for d in ['2024-11-29','2025-06-30'] for x in json.loads((B/'screens'/d/'KR.json').read_text())['deep']})
for s in symbols:
 f=B/'third_source'/s;f.mkdir(parents=True,exist_ok=True)
 if (f/'bars.csv').exists():continue
 raw,r=fetch('https://api.finance.naver.com/siseJson.naver?symbol='+s.split('.')[0]+'&requestType=1&startTime=20241128&endTime=20260712&timeframe=day',f/'raw');(f/'body.txt').write_bytes(raw);data=ast.literal_eval(raw.decode().strip());rows=[{'date':pd.Timestamp(str(v[0])).date().isoformat(),'open':v[1],'high':v[2],'low':v[3],'close':v[4],'volume':v[5]} for v in data[1:]];pd.DataFrame(rows).to_csv(f/'bars.csv',index=False);freeze(f/'receipt.json',{'source':r,'raw_sha256':sha(f/'body.txt'),'status':'SAVED','provider':'NAVER_PUBLIC_PRICE_VERIFICATION_NOT_AUTHENTICATED_EXCHANGE_ORIGINAL'});print(s,len(rows),flush=True)

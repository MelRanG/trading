from pathlib import Path
import json,io
from urllib.parse import urljoin
from lxml import html
import pandas as pd
from network import Network,B
n=Network();p=B/'universe_metadata.json';data=json.loads(p.read_text());(B/'metadata_initial_schema_failures.json').write_text(json.dumps(data['errors'],indent=2))
for name,product in [('IVV','239726'),('IJH','239763')]:
 try:
  r=next(json.loads(q.read_text()) for q in (B/'http').glob('*/receipt.json') if 'ishares' in json.loads(q.read_text())['url'] and product in json.loads(q.read_text())['url']);doc=html.fromstring(Path(r['path']).read_bytes());link=next(v for v in doc.xpath('//a/@href') if 'latest-holdings.csv' in v);raw,receipt=n.get(urljoin(r['url'],link),'universe_metadata');text=raw.decode('utf-8-sig');lines=text.splitlines();i=next(i for i,l in enumerate(lines) if l.startswith('Ticker,') or l.startswith('"Ticker",'));f=pd.read_csv(io.StringIO('\n'.join(lines[i:])));assert {'Ticker','Sector','Asset Class'}.issubset(f.columns);f=f[f['Asset Class'].eq('Equity')];data['sources'][name]={'rows':f.fillna('').to_dict('records'),'receipt':receipt,'authority':'CURRENT_FUND_HOLDINGS_NOT_HISTORICAL_MEMBER_OR_CAP','discovered_link':link};print(name,len(f),flush=True)
 except Exception as e:data['errors'].append({'source':name+'_RECOVERY','error':type(e).__name__+':'+str(e)[:160]});print(name,type(e).__name__,flush=True)
for url in ['https://developers.tossinvest.com/llms.txt','https://openapi.tossinvest.com/openapi-docs/latest/openapi.json']:
 try:
  raw,r=n.get(url,'provider_documentation');fn='toss_llms.txt' if 'llms' in url else 'toss_openapi.json';(B/fn).write_bytes(raw);print(fn,len(raw),flush=True)
 except Exception as e:print('DOC_FAIL',type(e).__name__,str(e)[:120])
p.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str)+'\n')

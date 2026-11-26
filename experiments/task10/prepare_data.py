from common import *
import pandas as pd,numpy as np
E=Path('/home/ansy/app/quant-diligence')
for m in ['US','KR']:
 folders=[B/'tape'/m,B/'prefix'/m]
 for p in folders:p.mkdir(parents=True,exist_ok=True)
 rows=[]
 for a in json.loads((B/'universe.json').read_text()):
  if a['market']!=m:continue
  p=B/'data'/a['symbol']/'resolved.csv';d=pd.read_csv(p);d['date']=pd.to_datetime(d.date);d=d.set_index('date').sort_index();q=json.loads(p.with_name('resolution.json').read_text());assert q['V87']['passed'];assert len(d.loc[:'2026-05-15'])==200
  d.to_csv(B/'tape'/m/(a['alias']+'.csv'));d.loc[:'2026-05-15'].to_csv(B/'prefix'/m/(a['alias']+'.csv'));rows.append({'alias':a['alias'],'symbol':a['symbol'],'start':str(d.index.min().date()),'prefix_valid':int(d.loc[:'2026-05-15'].close.notna().sum()),'prefix_hash':sha(B/'prefix'/m/(a['alias']+'.csv')),'tape_hash':sha(B/'tape'/m/(a['alias']+'.csv')),'role':a['role']})
 freeze(B/('dataset_'+m+'.json'),rows)
print('DATA_READY')

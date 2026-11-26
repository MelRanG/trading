from pathlib import Path
import pandas as pd,json
R=Path('/repo');S=R/'runtime/task13_r0';out=Path('/work');assets=json.loads((S/'native_manifest/assets.json').read_text())
for m in ['US','KR']:
 maps={x['symbol']:x['native_alias'] for x in json.loads((S/'native'/(m+'_private_mapping.json')).read_text())};parts=[]
 for a in assets:
  if a['market']!=m:continue
  f=pd.read_csv(R/a['adjusted_path'],index_col='date',parse_dates=True);mask=pd.read_csv(R/a['eligibility_path'],index_col='date',parse_dates=True).eligible;f=f.reindex(mask.index).where(mask,axis=0).loc['2022-07-01':'2024-12-31'];f['return']=f.close.pct_change(fill_method=None);f.columns=['$'+c for c in f.columns];f['instrument']=maps[a['symbol']];f.index.name='datetime';parts.append(f.set_index('instrument',append=True))
 pd.concat(parts).sort_index().to_hdf(out/(m+'_train.h5'),key='data')

from pathlib import Path
import json,pandas as pd
src=Path('/data');target=Path('/work/data');target.mkdir(exist_ok=True)
frames=[]
for path in sorted(src.glob('*.csv')):
 if 'BENCHMARK' in path.stem or not path.stem.startswith('US'):continue
 frame=pd.read_csv(path,parse_dates=['date']).set_index('date');frame.index.name='datetime';frame['instrument']=path.stem;frame=frame.set_index('instrument',append=True)
 frame=frame.rename(columns={k:'$'+k for k in ('open','high','low','close','volume')})
 frame['$return']=frame['$close'].groupby(level='instrument').pct_change(fill_method=None)
 frames.append(frame[['$open','$high','$low','$close','$volume','$return']])
combined=pd.concat(frames).sort_index();combined.to_hdf(target/'daily_pv.h5',key='data');(target/'README.md').write_text((src/'README.json').read_text())
print({'rows':len(combined),'instruments':combined.index.get_level_values('instrument').nunique(),'max_date':str(combined.index.get_level_values('datetime').max())})

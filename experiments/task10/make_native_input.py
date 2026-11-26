from common import *
import pandas as pd
E=Path('/home/ansy/app/quant-diligence')
for engine in ['quanta','rd']:
 work=E/('task10-'+engine+'-work');(work/'data').mkdir(parents=True,exist_ok=True);(work/'home').mkdir(exist_ok=True);rows=[]
 for p in (B/'prefix/US').glob('US[0-9]*.csv'):
  f=pd.read_csv(p,parse_dates=['date']).set_index('date').iloc[:100];g=f[['open','high','low','close','volume']].rename(columns=lambda c:'$'+c);g['$return']=g['$close'].pct_change(fill_method=None);g.index.name='datetime';g['instrument']=p.stem;rows.append(g.set_index('instrument',append=True))
 pd.concat(rows).sort_index().to_csv(work/'data/train.csv')
 freeze(work/'context.json',{'asof':'2026-05-15','target':C['label'],'training_source':'First100 of200local sessions; pricesaftertrainingpartitionnotmounted. AnonymousUS38. CurrentcohortnotPITcertified.','evaluation':'remaining80prefixsessions, sixsessionpurge, originalshared5-sessionrebalance/cost/risk; feedbacklateronlysamecutoffactualmeasurements','instruction':'One causal <=63lookback economical volume/price signal, no candidategrids, futuredata, inventednumbers or returns. modelGRU16 CPU only. No externalfiles. No validatedfundamentals ormacrofields available; do notfabricate.'})

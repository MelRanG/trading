from components import *
from replay_factory import preregister,open_store
from weekly_review import weekly
review=json.loads((B/'first_trigger.json').read_text());m=review['market'];day=review['asof'];fs=frames(m,day);dates=trading_dates(frames(m),m);v=preregister(m,day,review['snapshot'],review,dates);freeze(B/'first_experiment.json',v)
# Archive original controller before replacing working training context.
root=E/'task10-quanta-work';backup=B/'native/quanta/initial_controller';shutil.copytree(root,backup,ignore=shutil.ignore_patterns('home','data','*.log'),dirs_exist_ok=True)
rows=[]
for s,f in fs.items():
 if 'BENCHMARK' in s:continue
 fit=f.iloc[:-86];g=fit[['open','high','low','close','volume']].rename(columns=lambda c:'$'+c);g['$return']=g['$close'].pct_change(fill_method=None);g.index.name='datetime';g['instrument']=s;rows.append(g.set_index('instrument',append=True))
pd.concat(rows).sort_index().to_csv(root/'data/train_mutation.csv')
context={'asof':day,'factory_attempt':v['attempt']['attempt_id'],'Review':{k:review[k] for k in ['status','rolling20_active','rolling_mature5session_IC','prior_mature_IC','fees_to_date','cause']},'target':C['label'],'training':'Only fit prefix, last80sessionvalidationexcluded fromdatafile; nofutureperiodprices.','instruction':'Investigate failure using original mutation, do not optimizeknownfinal6m. One<=63lookbackfactor, no grids. Lowercost/robust mechanism, notforcedchanges.'}
freeze(B/'mutation_context.json',context);dump(root/'context.json',context)
# Official proposal/reservation precedes generated candidate or training.
print('FACTORY_RESERVED',v['attempt']['attempt_id'],v['processing_day'],flush=True)

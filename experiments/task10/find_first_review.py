from measure import measure
from weekly_review import weekly
from shared import *
m='US';fs=frames(m);scores=pd.read_csv(B/'signals'/m/'combined_initial.csv',index_col=0,parse_dates=True);ds=trading_dates(fs,m);ds=ds[(ds>=C['entry'])&(ds<=C['end'])];bad=0
for i in range(4,len(ds),5):
 day=ds[i];prefix={s:f.loc[:day] for s,f in fs.items()};metric,nav,fills,intents,ledger,journal,ics=measure(scores,prefix,m,C['entry'],day);review,bad=weekly(m,day,prefix,scores,nav,fills,intents,bad);freeze(B/'pilot_reviews'/(str(day.date())+'.json'),review);print(str(day.date()),review['status'],review['rolling20_active'],review['rolling_mature5session_IC'],flush=True)
 if review['status']=='RESEARCH':freeze(B/'first_trigger.json',review);print('NATURAL_TRIGGER_FROZEN',str(day.date()),flush=True);break
else:freeze(B/'no_US_trigger.json',{'status':'NO_NATURAL_RESEARCH_TRIGGER','sessions':len(ds),'no_forced_experiment':True})

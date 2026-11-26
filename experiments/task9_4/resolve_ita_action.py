from protocol import *
import pandas as pd
research_seal();f=B/'evaluator_only/ITA';source=B/'actuals/ITA_OCC/normalized.txt';t=source.read_text();assert 'November 5, 2026' in t and '3 for 1' in t and '60055' in t
q=json.loads((f/'quality.json').read_text());events=list(q['events']['splits'].values());assert len(events)==1 and events[0]['numerator']/events[0]['denominator']==3
assert pd.Timestamp(events[0]['date'],unit='s',tz='UTC').date().isoformat()=='2026-11-05'
y=pd.read_csv(f/'yahoo.csv').set_index('date');tt=pd.read_csv(f/'toss.csv').set_index('date');rows=[];proof=[]
for d in y.index:
 factor=3 if d<'2026-11-05' else 1;row={'date':d};pr={'date':d,'Yahoo_split_adjustment_reversed':factor}
 for field in ['open','close']:
  vals={'YAHOO':float(y.loc[d,field])*factor}
  if d in tt.index:vals['TOSS']=float(tt.loc[d,field])
  row[field],pr[field]=choose_observation(vals)
 rows.append(row);proof.append(pr)
pd.DataFrame(rows).to_csv(f/'bars_v2.csv',index=False)
freeze(f/'resolution_v2.json',{'version':'CORPORATE_ACTION_SOURCE_RECONCILIATION_V2','original_quality_preserved':sha(f/'quality.json'),'source_path':str(source.relative_to(R)),'source_hash':sha(source),'issuer_action_notice':'OCC60055viaMIAXexchange;Oct27notice,Nov5exdate;CUSIP464288760','action':{'date':'2026-11-05','quantity_multiplier':3},'rule':'OriginalYahooOHLCsplit-adjustedhistorically; reverseonlydeclared3for1beforeexdate tocompareTossnominal; then multiplyheldshares3fromexdate. No extrapolation ornewcandidate. Same0.5%agreement. Priceonly excludesalldistributions.','proof':proof,'no_model_or_strategy_change':True,'missing_open':int(pd.DataFrame(rows).open.isna().sum()),'missing_close':int(pd.DataFrame(rows).close.isna().sum())})
print('ITA actionresolved',len(rows))

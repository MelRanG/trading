"""POST HOC component attribution, never candidate selection or another adoption."""
from components import *
from measure import measure
rows=[]
for m in ['US','KR']:
 case=json.loads((B/'accounts'/m/'summary.json').read_text())['research_event']
 if not case or case['local_status']!='REPLAY_ADOPTED':continue
 fs=frames(m);folder=B/'signals'/m;initial=pd.read_csv(folder/'combined_initial.csv',index_col=0,parse_dates=True);oldq=pd.read_csv(folder/'quanta_initial.csv',index_col=0,parse_dates=True);oldrd=pd.read_csv(folder/'rd_initial.csv',index_col=0,parse_dates=True);newq=pd.read_csv(folder/'quanta_candidate.csv',index_col=0,parse_dates=True);newrd=predict(case['rd_model_stage'],m,fs);start=pd.Timestamp(case['decision_day'])
 for name,newscore in [('Q_MUTATION_ONLY',target_scores(newq,oldrd)),('RD_RETRAIN_ONLY',target_scores(oldq,newrd))]:
  scores=initial.copy();mask=scores.index>=start;scores.loc[mask,:]=newscore.reindex(index=scores.index[mask],columns=scores.columns);metric,nav,fills,*_=measure(scores,fs,m,C['entry'],C['end']);out=B/'evaluation/ablations';out.mkdir(exist_ok=True);nav.to_csv(out/(m+'_'+name+'_nav.csv'),index=False);fills.to_csv(out/(m+'_'+name+'_fills.csv'),index=False);rows.append({'market':m,'arm':name,'metrics':metric,'classification':'POST_HOC_ATTRIBUTION_NO_SELECTION_NO_NEW_FACTORY_EXPERIMENT','known_US_final_before_analysis':True,'initial_version_and_activation_same':True})
freeze(B/'evaluation/ablation.json',rows);print([(r['arm'],r['metrics']['return_pct']) for r in rows])

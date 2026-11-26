from protocol import *
import pandas as pd,importlib.util
research_seal();sp=importlib.util.spec_from_file_location('static_old',R/'experiments/task9_value/evaluate.py');ev=importlib.util.module_from_spec(sp);sp.loader.exec_module(ev)
rows=[]
for m,idx in [('US','^GSPC'),('KR','^KS11')]:
 p=R/'runtime/task9_3/model_outputs'/(m+'_2026-05-15.json');d=json.loads(p.read_text());names=d['selection_top3'];f=pd.read_csv(B/'evaluator_only'/idx/'bars.csv');f['date']=pd.to_datetime(f.date);f=f.set_index('date').sort_index();entry=pd.Timestamp('2026-05-18');ds=f.index[(f.index>=entry)&(f.index<=pd.Timestamp('2026-11-13'))];ix=f.loc[ds,'close']/float(f.loc[entry,'open']);ix.loc[entry-pd.Timedelta(seconds=1)]=1.;ix=ix.sort_index();paths={};provenance=[];miss=[]
 for s in names:
  parent=R/'runtime/task9_3/evaluator_only'/s;price=parent/('bars_v2.csv' if (parent/'bars_v2.csv').exists() else 'bars.csv');z=pd.read_csv(price);z['date']=pd.to_datetime(z.date);z=z.set_index('date');assert entry in z.index and ds[-1] in z.index;v=z.close.reindex(ds)/float(z.loc[entry,'open']);miss.append(int(v.isna().sum()));v=v.dropna();v.loc[entry-pd.Timedelta(seconds=1)]=1.;paths[s]=v.sort_index();provenance.append({'symbol':s,'source_path':str(price.relative_to(R)),'sha256':sha(price)})
 result,_=ev.mix(paths,{s:1/3 for s in names},ix,6 if m=='US' else 6.5,6 if m=='US' else 26.5)
 if any(miss):result.update(mdd_observed_marks=None,sharpe_rf0_diagnostic=None)
 new=next(x for x in json.loads((B/'evaluation_v2/portfolios.json').read_text()) if x['market']==m and x['horizon']=='6m')
 rows.append({'market':m,'old_initial_top3':names,'original_research_hash':sha(p),'old_frozen_price_provenance':provenance,'old_static_initial_top3_result':result,'Task94_new_static_gross':new['gross_price_return'],'Task94_new_static_net':new['net_price_return'],'observed_net_difference':new['net_price_return']-result['net_price_return'],'not_paired_AB':True,'not_original_dynamic_Task93_policy_performance':True,'meaning':'Descriptiveoldinitialtop3staticcontrol, usingalreadystoredTask93prices;no extraassetselectionorpriceAPI. Inputs/candidateopportunities/researchbudgetdiffer;knownpriorresults;notindependentimprovement.'})
freeze(B/'evaluation_v2/task93_descriptive_comparison.json',rows);print([(r['market'],r['old_static_initial_top3_result']['net_price_return'],r['Task94_new_static_net']) for r in rows])

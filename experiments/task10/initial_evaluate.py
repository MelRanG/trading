from components import *
from measure import measure
import shutil
strategy={}
for m in ['US','KR']:
 fs=frames(m);q=factor('initial_full',m,fs,E/'task10-quanta-work/initial/factor.py');rd=predict('initial',m,fs);prefix_rd=pd.read_csv(B/'models/initial'/m/'validation_predictions.csv',parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0].unstack('instrument');pd.testing.assert_series_equal(rd.stack().reindex(prefix_rd.stack().index),prefix_rd.stack(),check_names=False,rtol=1e-6,atol=1e-7);causal_prefix=predict('initial',m,frames(m,'2026-05-15'),tag='initial_prefix_causality');pd.testing.assert_frame_equal(rd.reindex(index=causal_prefix.index,columns=causal_prefix.columns),causal_prefix,check_names=False,rtol=1e-6,atol=1e-7);initialq=pd.read_csv(B/('quanta_initial_prefix_'+m+'.csv'),parse_dates=[0],index_col=0);pd.testing.assert_frame_equal(q.reindex(index=initialq.index,columns=initialq.columns),initialq,check_names=False,rtol=1e-10,atol=1e-10)
 scores=target_scores(q,rd);p=B/'signals'/m;p.mkdir(parents=True,exist_ok=True);q.to_csv(p/'quanta_initial.csv');rd.to_csv(p/'rd_initial.csv');scores.to_csv(p/'combined_initial.csv');prefix=frames(m,'2026-05-15');start=next(iter(prefix.values())).index[-80];metrics,*rest=measure(scores,prefix,m,start,'2026-05-15');freeze(B/'initial_validation'/(m+'.json'),metrics);strategy[m]={'asof':'2026-05-15','effective':'2026-05-18','initial_signal_hash':sha(p/'combined_initial.csv'),'quanta_code_hash':sha(E/'task10-quanta-work/initial/factor.py'),'rd_code_hash':sha(E/'task10-rd-work/model.py'),'rd_training':json.loads((B/'models/initial'/m/'training.json').read_text()),'prefix_metadata_hash':sha(B/('dataset_'+m+'.json')),'validation_hash':sha(B/'initial_validation'/(m+'.json')),'economic_efficacy':'UNPROVEN_RESEARCH_CANDIDATE_NOT_INVESTMENT_APPROVAL','future_predictions':'Frozencode/modelappliedtofuturefeaturesbyofflineinference, neverusedtofit; prefixinvariancepassed'}
 print('INITIAL_VALIDATION',m,metrics['return_pct'],metrics['IC'],flush=True)
freeze(B/'initial_strategy_seal.json',{'contract_hash':sha(Path(__file__).parent/'contract.json'),'strategies':strategy,'initial_equal_static_adaptive':True,'no_future_performance_used_for_parameter_selection':True,'known_history_limits':'Task6-9.4alreadyknown, currentcohortnotPITmembership; statisticalalphaunproven'})
# Feedback reads actual preMay15validation only, never full sixmonth outcome.
f=E/'task10-quanta-work/initial/metrics.json';freeze(f,json.loads((B/'initial_validation/US.json').read_text()))
for engine in ['quanta','rd']:
 out=B/'native'/engine;out.mkdir(parents=True,exist_ok=True)
 for p in (E/('task10-'+engine+'-work')).glob('*.json'):shutil.copyfile(p,out/p.name)
 if engine=='quanta':shutil.copytree(E/'task10-quanta-work/initial',out/'initial',dirs_exist_ok=True)
 else:shutil.copyfile(E/'task10-rd-work/model.py',out/'model.py')

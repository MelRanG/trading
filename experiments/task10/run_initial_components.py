from components import *
for m in ['US','KR']:
 fs=frames(m,'2026-05-15');q=factor('initial_prefix',m,fs,E/'task10-quanta-work/initial/factor.py');q.to_csv(B/('quanta_initial_prefix_'+m+'.csv'))
 print(m,'NATIVE_Q_PREFIX_VALID',q.shape,flush=True);v=train_model('initial',m,fs);print(m,'NATIVE_RD_TRAINED',v['outer_mse'],flush=True)

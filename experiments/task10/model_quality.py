from components import *
rows=[];similarity=[]
for m in ['US','KR']:
 fs=frames(m);target=labels(fs);case=json.loads((B/'accounts'/m/'summary.json').read_text())['research_event'];old=pd.read_csv(B/'signals'/m/'rd_initial.csv',index_col=0,parse_dates=True);new=predict(case['rd_model_stage'],m,fs) if case else None;dates=target.index[:-6]
 for period,mask in [('pre_initial_validation',dates<='2026-05-15'),('post_entry',dates>='2026-05-15'),('post_research',dates>=pd.Timestamp(case['source_asof']) if case else dates>='2099-01-01')]:
  ds=dates[mask]
  if period=='pre_initial_validation':ds=ds[ds<=next(iter(fs.values())).loc[:C['asof']].index[-7]]
  for name,p in [('initial_model',old),('retrained_model',new)]:
   if p is None:continue
   if name=='retrained_model' and period!='post_research':continue
   a=p.reindex(index=ds,columns=target.columns).stack();b=target.reindex(index=ds).stack().reindex(a.index);valid=a.notna()&b.notna();err=a[valid]-b[valid];ics=rank_ic(p,fs,ds[-1]+pd.Timedelta(days=20),ds[0]) if len(ds) else [];ics=[v for v in ics if v['date']<=str(ds[-1].date())];rows.append({'market':m,'period':period,'model':name,'rows':int(valid.sum()),'MSE':float((err**2).mean()) if len(err) else None,'MAE':float(err.abs().mean()) if len(err) else None,'mean_RankIC':float(np.mean([r['IC'] for r in ics])) if ics else None,'source_asof':case['source_asof'] if name=='retrained_model' else C['asof'],'retrained_policy_applied':bool(case and case['local_status']=='REPLAY_ADOPTED') if name=='retrained_model' else True,'pre_initial_validation_is_development':period=='pre_initial_validation','retrained_pre_source_dates_not_presented_as_operational_predictions':True})
 q=pd.read_csv(B/'signals'/m/'quanta_initial.csv',index_col=0,parse_dates=True);mom=pd.DataFrame({s:f.close.pct_change(63,fill_method=None) for s,f in fs.items() if 'BENCHMARK' not in s});qnew_path=B/'signals'/m/'quanta_candidate.csv';qnew=pd.read_csv(qnew_path,index_col=0,parse_dates=True) if qnew_path.exists() else None
 for desc,a,b in [('initial_quanta_vs_MOM63',q,mom),('candidate_quanta_vs_initial',qnew,q)]:
  if a is None:continue
  cs=[]
  for d in a.index[a.index>=C['asof']]:
   x=a.loc[d];y=b.reindex(index=[d],columns=x.index).loc[d];valid=x.notna()&y.notna()
   if valid.sum()>8 and x[valid].nunique()>1 and y[valid].nunique()>1:cs.append(float(x[valid].rank().corr(y[valid].rank())))
  similarity.append({'market':m,'pair':desc,'mean_daily_score_rank_correlation':float(np.mean(cs)) if cs else None,'scope':'Descriptiveallhistoricalreplay; notamethodforcandidateadmissionornovelalphaproof'})
freeze(B/'evaluation/model_quality_v2.json',rows);freeze(B/'evaluation/alpha_similarity.json',similarity)

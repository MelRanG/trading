"""Bounded read-only evaluation of five frozen candidates. No LLM/train/PnL."""
from pathlib import Path
import json,hashlib,datetime,sys
import pandas as pd,numpy as np
from stats_eval import block_mean,holm,residual,corr
R=Path(__file__).resolve().parents[2];B=Path('/work') if R==Path('/repo') else R/'runtime/task14';S=R/'runtime/task13';B.mkdir(exist_ok=True)
C=json.loads((Path(__file__).parent/'contract.json').read_text());OLD=json.loads((S/'diagnostics/initial_diagnostics.json').read_text());sys.path[:0]=[str(R/'src'),str(R/'experiments/task12')]
from evaluation import signal_statistics
from qlib.contrib.eva.alpha import calc_ic

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
 return x

def dump(n,x):(B/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
def daily(g):
 rows=[];contrib=[]
 for d,z in g.dropna(subset=['score','target']).groupby(level='datetime'):
  z=z.copy()
  if len(z)<8 or z.score.nunique()<2:continue
  q=z.sort_values('score',kind='stable');k=max(1,len(q)//5);top=q.iloc[-k:];bottom=q.iloc[:k];row={'date':d,'IC':corr(z.score,z.target),'RankIC':corr(z.score,z.target,True),'top_mean':top.target.mean(),'bottom_mean':bottom.target.mean(),'spread':top.target.mean()-bottom.target.mean(),'top_median':top.target.median(),'bottom_median':bottom.target.median(),'median_spread':top.target.median()-bottom.target.median(),'universe_mean':z.target.mean(),'universe_median':z.target.median(),'names':len(z),'top_k':k,'label_max':z.target.max(),'label_min':z.target.min()}
  for j in range(5):
   a=z.sort_values('score',kind='stable').iloc[(len(z)*j)//5:(len(z)*(j+1))//5];row['quintile'+str(j+1)+'_mean']=a.target.mean();row['quintile'+str(j+1)+'_median']=a.target.median()
  rows.append(row)
  for part,sign in [(top,1),(bottom,-1)]:
   for (_,s),v in part.iterrows():contrib.append({'date':d,'instrument':s,'leg':'top' if sign==1 else 'bottom','target':v.target,'weighted_contribution':sign*v.target/k})
 return pd.DataFrame(rows).set_index('date').sort_index(),pd.DataFrame(contrib)

def summary(frame,calendar,H):
 result={}
 for col in ['IC','RankIC','spread','median_spread','top_mean','bottom_mean']:
  result[col]=block_mean(frame[col].reindex(calendar),H)
 result['RankIC_block2H']=block_mean(frame.RankIC.reindex(calendar),2*H)
 return result

# All source fingerprints first, before new statistics.
manifest=json.loads((S/'artifact_manifest.json').read_text());bad=[x['path'] for x in manifest['files'] if sha(R/x['path'])!=x['sha256']];assert not bad,bad
handoff=json.loads((S/'task14_handoff.json').read_text());seal=json.loads((S/'candidate_seal.json').read_text());assert sha(S/'contract.json')==handoff['contract_hash'];assert sha(S/'candidate_seal.json')==handoff['candidate_seal_hash']
for c in handoff['candidates']:
 assert hashlib.sha256(json.dumps(c['binding'],sort_keys=True).encode()).hexdigest()==c['candidate_fingerprint']
 path=next(x['source'] for x in seal['candidates'] if x['id']==c['id']);p=Path(path);p=(Path('/home/ansy/app/quant-diligence/vibe-original/agent')/p.relative_to('/home/ansy/app/quant-diligence/vibe-original/agent')) if p.is_absolute() and str(p).startswith('/home/ansy/app/quant-diligence') else R/p;assert sha(p)==c['binding']['code_hash']
 ip=S/'adjusted_inputs'/(c['market']+'.csv') if c['id']=='RD_SMALL' else S/'nominal_inputs'/c['market']/'panel.csv';assert sha(ip)==c['binding']['input_hash']
 if c['id']=='RD_SMALL':assert sha(S/'models'/c['market']/'model.pth')==c['binding']['checkpoint_hash']
dump('input_seal_check.json',{'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'Task13_files_verified':len(manifest['files']),'Task13_manifest_hash':sha(S/'artifact_manifest.json'),'candidate_market_fingerprints':len(handoff['candidates']),'contract_hash':sha(Path(__file__).parent/'contract.json'),'old_source_modified':False,'source_reference':'Task13 contract sources retain backfill observations/PIT limits'})
results={};audit=[];increment=[];primaries=[];secondary=[];all_subgroups=[];top_contributions=[];all_daily=[];index_checks=[]
for market in ['US','KR']:
 f=pd.read_csv(S/'nominal_inputs'/market/'panel.csv',parse_dates=['datetime']).set_index(['datetime','instrument']);assert not f.index.has_duplicates;op=f.open.unstack();cl=f.close.unstack();vol=f.volume.unstack();ds=op.index;calendar=ds[ds>='2026-01-01'];Y=op.shift(-21)/op.shift(-1)-1
 for j in range(1,22):Y=Y.where((op>0).shift(-j,fill_value=False))
 eligible=(np.isfinite(f[['open','high','low','close','volume']]).all(axis=1)&(f[['open','high','low','close','volume']]>0).all(axis=1)).unstack();mom=cl/cl.shift(20)-1;gmap={}
 # Interval reference from one frozen index source, never splice an index price path.
 index_series=[]
 for p in [R/'runtime/task9_1/evaluator_only/2025-06-30'/('^GSPC' if market=='US' else '^KS11')/'bars.csv',R/'runtime/task10/evaluation'/(market+'_index.csv')]:index_series.append((p,pd.read_csv(p,index_col='date',parse_dates=True)))
 overlap=index_series[0][1].index.intersection(index_series[1][1].index);rel=(index_series[0][1].loc[overlap,'open']/index_series[1][1].loc[overlap,'open']-1).abs();index_checks.append({'market':market,'overlap_dates':len(overlap),'max_open_relative_difference':rel.max(),'source_hashes':[{str(p.relative_to(R)):sha(p)} for p,_ in index_series]})
 bench={};bench_source={}
 for d in calendar:
  i=ds.get_loc(d)
  if i+21>=len(ds):continue
  a,b=ds[i+1],ds[i+21]
  for p,v in index_series:
   # Require every intermediate market date so endpoints do not conceal a gap.
   zz=v.open.reindex(ds[i+1:i+22])
   if zz.notna().all() and (zz>0).all():bench[d]=v.at[b,'open']/v.at[a,'open']-1;bench_source[d]=str(p.relative_to(R));break
 rgname='US_SPY_PROXY_2022_2026' if market=='US' else 'LEGACY_KS11';reg=pd.read_csv(R/'runtime/task12'/(rgname+'_regimes.csv'),index_col='date',parse_dates=True)
 for cid in ['V_ROC20','V_LOWVAR20','Q0','Q1']:
  key=cid+'_'+market;g=pd.read_csv(S/'diagnostics'/(key+'_paired.csv'),parse_dates=['datetime']).set_index(['datetime','instrument']).sort_index();assert not g.index.has_duplicates
  # Independently reconstruct raw source+strict mask+target alignment, retain original direction.
  raw=pd.read_csv(S/'calculations'/cid/('nominal_'+market)/'scores.csv',parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0].unstack();w=63 if cid[0]=='Q' else 21 if cid=='V_ROC20' else 20;mask=eligible.rolling(w,min_periods=w).sum().eq(w);expected=raw.where(mask).where(pd.Series(np.arange(len(ds))>=w,index=ds),axis=0).stack(future_stack=True).loc[g.index];target=Y.stack(future_stack=True).loc[g.index]
  np.testing.assert_allclose(g.score,expected,equal_nan=True,atol=1e-12);np.testing.assert_allclose(g.target,target,equal_nan=True,atol=1e-12)
  if cid=='V_ROC20':np.testing.assert_allclose(raw, -cl.shift(20)/cl,equal_nan=True)
  if cid=='V_LOWVAR20':np.testing.assert_allclose(raw,-cl.rolling(20,min_periods=20).std(ddof=1)/cl,equal_nan=True)
  sf=g.score.unstack();tf=g.target.unstack();independent=daily(g);d,con=independent;old=next(x for x in OLD['nominal_candidates'] if x['id']==cid and x['market']==market);common=signal_statistics(sf,tf,native_ic=calc_ic)
  assert np.isclose(d.IC.mean(),old['IC'],atol=1e-12) and np.isclose(d.RankIC.mean(),old['RankIC'],atol=1e-12) and np.isclose(d.spread.mean(),old['mean_top_minus_bottom_return'],atol=1e-12)
  assert np.isclose(common['RankIC'].mean(),d.RankIC.mean())
  audit.append({'id':cid,'market':market,'scores_labels_and_metrics':'MATCH','rows':len(g.dropna()),'dates':len(d),'mature_missing_label_cells':old['mature_window_missing_label_cells'],'immature_cells':old['immature_label_cells'],'Quanta_partial_window_mask_verified':cid[0]=='Q','no_recalculation_of_native_controller':True})
  d['index_return']=pd.Series(bench);d['top_index_excess']=d.top_mean-d.index_return;d['bottom_index_excess']=d.bottom_mean-d.index_return
  # Common index subtraction must not change cross-sectional covariance/rank/spread.
  excess=g.copy();excess['target']=excess.target-excess.index.get_level_values(0).map(pd.Series(bench));ed,_=daily(excess);cross=d.index.intersection(ed.index);assert np.allclose(d.loc[cross,'RankIC'],ed.loc[cross,'RankIC'])
  entry={'primary':summary(d,calendar,20),'rows':len(g.dropna()),'dates':len(d),'quintiles':{c:float(d[c].mean()) for c in d if c.startswith('quintile')},'market_relative':{'labelled_dates':len(cross),'top_mean_excess':d.top_index_excess.mean(),'bottom_mean_excess':d.bottom_index_excess.mean(),'IC_invariant_to_common_index_subtraction':True,'benchmark_kind':'PRICE_INDEX_OPEN_TO_OPEN_NOT_TR','source_per_signal':bench_source},'distribution':g.dropna().describe().to_dict()}
  primaries.append({'test':key,'p':entry['primary']['RankIC']['p_positive'],'effect':'mean RankIC>0'})
  # Symbol/date diagnostics are posthoc attribution, never replace original candidate.
  names=con.groupby('instrument').weighted_contribution.sum()/len(d);ordered=names.abs().sort_values(ascending=False);greatdates=d.spread.abs().nlargest(5).index;risks=[]
  for k in [1,3]:
   removed=ordered.index[:k];ng=g.drop(index=removed,level='instrument');nd,_=daily(ng);risks.append({'remove_top_abs_contribution_names':k,'removed':removed.tolist(),'RankIC':nd.RankIC.mean(),'spread':nd.spread.mean(),'dates':len(nd),'posthoc_not_new_strategy':True})
  risks.append({'remove_top_abs_spread_dates':5,'removed':[str(x.date()) for x in greatdates],'RankIC':d.drop(index=greatdates).RankIC.mean(),'spread':d.drop(index=greatdates).spread.mean(),'posthoc_not_new_strategy':True})
  entry['sensitivity']=risks;entry['top_contributions']=[{'instrument':s,'mean_spread_contribution':names[s]} for s in ordered.index[:5]];entry['top_abs_spread_dates']=[{'date':str(x.date()),'spread':d.loc[x,'spread'],'top_mean':d.loc[x,'top_mean'],'bottom_mean':d.loc[x,'bottom_mean']} for x in greatdates]
  con['id']=cid;con['market']=market;top_contributions.append(con)
  # Frozen classifications; expose unknown coverage instead of reclassifying/stitching.
  for name in ['AS_OF_REGIME','EX_POST_REGIME','AS_OF_HIGH_VOL']:
   tags=reg[name].reindex(d.index).fillna('NO_REGIME_DATA');series=reg[name].astype(str);group=series.ne(series.shift()).cumsum()
   for label,part in d.groupby(tags,sort=False):
    runs=group.reindex(part.index).dropna().unique();intervals=[]
    for run in runs:
     rr=part.index[group.reindex(part.index)==run]
     if len(rr):intervals.append((int(ds.searchsorted(rr.min())),int(ds.searchsorted(rr.max()))+20))
    merged=[]
    for a,b in sorted(intervals):
     if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
     else:merged.append((a,b))
    all_subgroups.append({'id':cid,'market':market,'source':rgname,'axis':name,'group':str(label),'dates':len(part),'paired_names_mean':part.names.mean(),'raw_regime_runs':len(runs),'nonoverlap_label_extended_episodes':len(merged),'RankIC':part.RankIC.mean(),'spread':part.spread.mean(),'generalization':'INSUFFICIENT_EVIDENCE'})
  for freq in ['M','2Q']:
   # Calendar months/halves, fixed before results; 2Q period anchors quarters so use explicit half below.
   tags=d.index.to_period('M').astype(str) if freq=='M' else [str(x.year)+('H1' if x.month<=6 else 'H2') for x in d.index]
   for tag,part in d.groupby(tags):all_subgroups.append({'id':cid,'market':market,'axis':'month' if freq=='M' else 'half','group':tag,'dates':len(part),'RankIC':part.RankIC.mean(),'spread':part.spread.mean()})
  if market=='KR':
   for name,a,b in C['stability']['March']:
    part=d.loc[a:b];all_subgroups.append({'id':cid,'market':market,'axis':'March_signal_window','group':name,'dates':len(part),'RankIC':part.RankIC.mean(),'spread':part.spread.mean(),'note':'H20 outcome can cross regime boundaries; diagnostic not independent episodes'})
  gmap[cid]=g;results[key]=entry;dd=d.copy();dd['id']=cid;dd['market']=market;all_daily.append(dd.reset_index())
 # Quanta incremental information vs same-day simple momentum, exact same eligible names/labels.
 for cid in ['Q0','Q1']:
  g=gmap[cid].copy();g['baseline']=mom.stack(future_stack=True).reindex(g.index);g=g.dropna();extra=[]
  for day,z in g.groupby(level=0):
   if len(z)<8:continue
   sx=z.score.rank(pct=True).to_numpy();bx=z.baseline.rank(pct=True).to_numpy()*(1 if cid=='Q1' else -1);yy=z.target.to_numpy();yr=z.target.rank(pct=True).to_numpy();rx,beta=residual(sx,bx);ry,_=residual(yr,bx);k=max(1,len(z)//5);order=np.argsort(rx,kind='stable');extra.append({'date':day,'partial_rank':corr(rx,ry),'residual_rankIC':corr(rx,yr,True),'residual_spread':yy[order[-k:]].mean()-yy[order[:k]].mean(),'score_baseline_rank_correlation':corr(sx,bx),'residual_variance_fraction':np.var(rx)/np.var(sx) if np.var(sx)>0 else None,'baseline_RankIC':corr(bx,yr),'original_RankIC':corr(sx,yr),'names':len(z)})
  e=pd.DataFrame(extra).set_index('date');r={'id':cid,'market':market,'partial_rank':block_mean(e.partial_rank.reindex(calendar),20),'residual_rankIC':block_mean(e.residual_rankIC.reindex(calendar),20),'residual_spread':block_mean(e.residual_spread.reindex(calendar),20),'mean_rank_corr':e.score_baseline_rank_correlation.mean(),'mean_residual_variance_fraction':e.residual_variance_fraction.mean(),'baseline_RankIC_same_mask':e.baseline_RankIC.mean(),'original_RankIC_same_mask':e.original_RankIC.mean(),'half_partial_rank':e.groupby([str(t.year)+('H1' if t.month<=6 else 'H2') for t in e.index]).partial_rank.mean().to_dict(),'purpose':'DESCRIPTIVE_PROJECTION_ONLY_NOT_NEW_ALPHA_OR_FITTED_PORTFOLIO'};increment.append(r);secondary.append({'test':cid+'_'+market+'_partial','p':r['partial_rank']['p_positive']});e.to_csv(B/(cid+'_'+market+'_increment_daily.csv'))
 # RD compares identical prediction and truth rows only, separate2025 source-adjusted track.
 models={n:pd.read_csv(S/'models'/market/(n+'_paired.csv'),parse_dates=['datetime']).set_index(['datetime','instrument']).sort_index() for n in ['RD_SMALL','ZERO','QLIB_RIDGE','QLIB_TREE']};p=models['RD_SMALL'];ad=pd.read_csv(S/'adjusted_inputs'/(market+'.csv'),parse_dates=['datetime']).set_index(['datetime','instrument']);ao=ad.open.unstack();ay=ao.shift(-6)/ao.shift(-1)-1
 for j in range(1,7):ay=ay.where((ao>0).shift(-j,fill_value=False))
 np.testing.assert_allclose(p.target,ay.stack(future_stack=True).reindex(p.index));modeldaily={};modelsummary={};pdaily,pc=daily(p.rename(columns={'prediction':'score'}));modelcalendar=ao.index[(ao.index>=p.index.get_level_values(0).min())&(ao.index<=p.index.get_level_values(0).max())]
 for name,z in models.items():
  assert z.index.equals(p.index);np.testing.assert_allclose(z.target,p.target);err=z.prediction-z.target;se=err**2;ae=err.abs();dd=pd.DataFrame({'squared_error':se,'absolute_error':ae,'bias':err}).groupby(level=0).mean();old=OLD['model_adjusted_track'][market][name];assert np.isclose(se.mean(),old['mse'])
  lossdiff=(models['ZERO'].prediction-p.target)**2-se;ridgegap=(models['QLIB_RIDGE'].prediction-p.target)**2-se
  modelsummary[name]={'MSE':se.mean(),'MAE':ae.mean(),'bias':err.mean(),'mean_prediction':z.prediction.mean(),'mean_target':z.target.mean(),'prediction_std':z.prediction.std(),'prediction_q01':z.prediction.quantile(.01),'prediction_q99':z.prediction.quantile(.99),'prediction_min':z.prediction.min(),'prediction_max':z.prediction.max(),'rows':len(z),'dates':len(dd),'MSE_gain_vs_zero':block_mean(lossdiff.groupby(level=0).mean().reindex(modelcalendar),5),'MSE_gain_vs_Ridge':block_mean(ridgegap.groupby(level=0).mean().reindex(modelcalendar),5)}
  if name=='RD_SMALL':primaries.append({'test':'RD_SMALL_'+market,'p':modelsummary[name]['MSE_gain_vs_zero']['p_positive'],'effect':'zero minus RD mean daily squared loss>0'});secondary.append({'test':'RD_SMALL_'+market+'_vs_Ridge','p':modelsummary[name]['MSE_gain_vs_Ridge']['p_positive']})
  dd['model']=name;dd['market']=market;modeldaily[name]=dd
 partial=[]
 for day,z in p.groupby(level=0):
  ridge=models['QLIB_RIDGE'].loc[z.index].prediction;rx,_=residual(z.prediction.to_numpy(),ridge.to_numpy());ry,_=residual(z.target.rank(pct=True),ridge.rank(pct=True));partial.append({'date':day,'prediction_corr':corr(z.prediction,ridge),'rank_corr':corr(z.prediction,ridge,True),'residual_rankIC':corr(rx,z.target,True),'residual_variance_fraction':np.var(rx)/np.var(z.prediction),'mean_difference':(z.prediction-ridge).mean()})
 md=pd.DataFrame(partial).set_index('date');modelsummary['RD_vs_Ridge_information']={'mean_prediction_corr':md.prediction_corr.mean(),'mean_rank_corr':md.rank_corr.mean(),'mean_residual_variance_fraction':md.residual_variance_fraction.mean(),'residual_rankIC':block_mean(md.residual_rankIC.reindex(modelcalendar),5),'mean_prediction_shift':md.mean_difference.mean()};modelsummary['RankIC_RD']=block_mean(pdaily.RankIC.reindex(modelcalendar),5);modelsummary['training_reference']=OLD['model_adjusted_track'][market]['training'];results['RD_SMALL_'+market]=modelsummary
 pd.concat(modeldaily.values()).to_csv(B/('RD_'+market+'_loss_daily.csv'));md.to_csv(B/('RD_'+market+'_increment_daily.csv'));audit.append({'id':'RD_SMALL','market':market,'score_label_metric_and_checkpoint':'MATCH','rows':len(p),'dates':len(pdaily),'MSE_recomputed_without_training':True})
 for tag,part in pdaily.groupby(pdaily.index.to_period('M').astype(str)):all_subgroups.append({'id':'RD_SMALL','market':market,'axis':'month_adjusted2025','group':tag,'dates':len(part),'RankIC':part.RankIC.mean(),'spread':part.spread.mean()})
 for axis in ['AS_OF_REGIME','EX_POST_REGIME','AS_OF_HIGH_VOL']:
  for tag,part in pdaily.groupby(reg[axis].reindex(pdaily.index).fillna('NO_REGIME_DATA')):all_subgroups.append({'id':'RD_SMALL','market':market,'axis':axis,'source':rgname,'group':str(tag),'dates':len(part),'RankIC':part.RankIC.mean(),'spread':part.spread.mean(),'generalization':'INSUFFICIENT_EVIDENCE'})
# Preserve missing proposal slots and acknowledge prior campaign selection cannot be reset.
ps=[r['p'] for r in primaries]+[1.]*8;adj=holm(ps)
for r,a in zip(primaries,adj):r['holm18_p']=a;r['pass05']=a<.05
for r,a in zip(secondary,holm([r['p'] for r in secondary])):r['holm6_p']=a;r['exploratory_only']=True
pd.concat(all_daily,ignore_index=True).to_csv(B/'factor_daily.csv',index=False);pd.concat(top_contributions,ignore_index=True).to_csv(B/'factor_tail_contributions.csv',index=False);pd.DataFrame(all_subgroups).to_csv(B/'stability.csv',index=False)
dump('audit.json',{'checks':audit,'index_snapshot_overlap':index_checks,'original_results_modified':False,'provenance':'Existing Task13 raw/native causality evidence reused; only independent arithmetic/mask/hash checks repeated','regime_sources':'Task12 frozen US_SPY_PROXY_2022_2026 and LEGACY_KS11; missing coverage explicit'})
dump('validation.json',{'contract_hash':sha(Path(__file__).parent/'contract.json'),'scope':'EXPOSED_HISTORY_SIGNAL_VALIDATION_NOT_INDEPENDENT_HOLDOUT','candidates':results,'incremental':increment,'primary_tests':primaries,'secondary_increment_tests':secondary,'unexecuted_p1_slots':8,'old_trial_history':'Task13 nine proposals plus priorTask6~13 exposures; earlier adaptive family not numerically reconstructable, Holm18 does not confer independent confirmation','PBO_DSR_CPCV':'N/A_NO_FULL_STRATEGY_TRIAL_RETURN_MATRIX_OR_UNEXPOSED_SPLITS','resource':{'LLM_calls':0,'external_requests':0,'training':0,'new_candidates':0}})
print('AUDIT_PASS',len(audit),'PRIMARY_PASSES',sum(r['pass05'] for r in primaries),'RESULTS',len(results))

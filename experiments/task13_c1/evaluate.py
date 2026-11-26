"""Single trusted H5 evaluation. Atomic reservation prevents a second query."""
from pathlib import Path
import sys, json, time, traceback, numpy as np, pandas as pd
from scipy.stats import rankdata
from common import R, B, S, sha, write, now, read_before, bool_col, loaded, reserve
from factor import labels, forward_valid
sys.path.insert(0,str(R/'experiments/task14'))
from stats_eval import block_mean, holm, residual, corr
COLUMNS=['signal','REV5','MOM20','LOWVOL20','beta']


def partial_rank(array, extra_beta=False, rev_only=False):
    # array columns: signal, REV5, MOM20, LOWVOL20, beta, outcome.
    ranks=rankdata(array,method='average',axis=0)
    z=ranks[:,1:2] if rev_only else ranks[:,1:4]
    if extra_beta:z=ranks[:,1:5]
    x,_=residual(ranks[:,0],z);y,_=residual(ranks[:,-1],z)
    full=np.var(ranks[:,0]);remaining=float(np.var(x)/full) if full>0 else 0.
    return corr(x,y),remaining


def run():
    start=time.process_time();wall=time.monotonic();seal=json.loads((B/'seal.json').read_text())
    for p,h in seal['code_hashes'].items():assert sha(R/p)==h,'CODE_CHANGED '+p
    for p,h in seal['artifacts'].items():assert sha(B/p)==h,'FROZEN_ARTIFACT_CHANGED '+p
    for p,h in json.loads((B/'input_hashes.json').read_text()).items():assert sha(R/p)==h,'INPUT_CHANGED '+p
    assert json.loads((B/'phase_a_gate.json').read_text())['pass']
    reserve(B/'evaluation_attempt.json')
    try:
        evaluate(seal,start,wall)
    except BaseException as exc:
        write('evaluation_attempt.json',{'status':'INVALID_EVALUATION','at':now(),'error':type(exc).__name__,'detail':str(exc),'traceback':traceback.format_exc(),'rerun_forbidden_without_user_repair_authorization':True})
        write('completion.json',{'technical':'INVALID_EVALUATION','decision':'INVALID_EVALUATION','Task15':False,'reason':str(exc)})
        raise


def evaluate(seal,start,wall):
    contract=json.loads((B/'contract.json').read_text());assets=json.loads((S/'native_manifest/assets.json').read_text());assets={a['symbol']:a for a in assets if a['market']=='US' and a['cohort']=='CORE'}
    features=pd.read_csv(B/'features.csv.gz',parse_dates=['date']);assert set(features.symbol)==set(assets)
    indexdir=S/'accepted/US/^GSPC';market=read_before(indexdir/'quote.csv');days=market.index;mg=bool_col(read_before(indexdir/'quality_mask.csv').reindex(days))
    my=labels(market.open,mg,5);exits=pd.Series(days,index=days).shift(-6);targets=[];checks=[]
    for symbol,a in assets.items():
        price,g=loaded(a,days);target=labels(price.open,g,5).where(forward_valid(mg));ix=(days>='2023-04-03')&exits.le('2024-12-31');target=target.loc[ix]
        for d in target.dropna().index[:1]:
            i=days.get_loc(d);oracle=price.open.iloc[i+6]/price.open.iloc[i+1]-1;assert abs(target.loc[d]-oracle)<1e-13
            checks.append({'symbol':symbol,'signal':d.date().isoformat(),'entry':days[i+1].date().isoformat(),'exit':days[i+6].date().isoformat(),'entry_open':float(price.open.iloc[i+1]),'exit_open':float(price.open.iloc[i+6]),'H5':float(oracle)})
        targets.append(pd.DataFrame({'date':target.index,'symbol':symbol,'H5':target.to_numpy()}))
    paired=features.merge(pd.concat(targets,ignore_index=True),on=['date','symbol'],validate='one_to_one')
    good=np.isfinite(paired[COLUMNS+['sigma','H5']]).all(axis=1)&paired.label_path_eligible
    paired=paired.loc[good].sort_values(['date','symbol'],kind='stable');counts=paired.groupby('date').size();validdates=counts[counts>=50].index;paired=paired[paired.date.isin(validdates)]
    gate=json.loads((B/'phase_a_gate.json').read_text())['US'];assert len(validdates)==gate['valid_signal_dates'];assert len(paired)==gate['valid_symbol_dates']
    assert paired.groupby('date').size().min()>=50
    groups=[];daily=[];contributions={s:0. for s in assets};groupcontrib=[]
    for day,g in paired.groupby('date',sort=True):
        ar=g[COLUMNS+['H5']].to_numpy(float);ranks=rankdata(ar,method='average',axis=0);n=len(ar);k=n//5
        primary,frac=partial_rank(ar);revonly,_=partial_rank(ar,rev_only=True);withbeta,_=partial_rank(ar,extra_beta=True)
        row={'date':day,'names':n,'partial_RankIC':primary,'partial_REV5_only':revonly,'partial_with_beta':withbeta,'residual_signal_variance_fraction':frac,'market_relative_RankIC':corr(ranks[:,0],rankdata(ar[:,-1]-float(my.loc[day])))}
        for j,c in enumerate(COLUMNS):
            row[c+'_RankIC']=corr(ranks[:,j],ranks[:,-1]);row[c+'_IC']=corr(ar[:,j],ar[:,-1])
            if j:row['overlap_'+c]=corr(ranks[:,0],ranks[:,j])
        order=np.argsort(ar[:,0],kind='stable');bottom=order[:k];top=order[-k:];ys=ar[:,-1]
        row.update({'top_mean':float(ys[top].mean()),'bottom_mean':float(ys[bottom].mean()),'top_median':float(np.median(ys[top])),'bottom_median':float(np.median(ys[bottom])),'spread':float(ys[top].mean()-ys[bottom].mean()),'baseline_REV5_spread':float(ys[np.argsort(ar[:,1],kind='stable')[-k:]].mean()-ys[np.argsort(ar[:,1],kind='stable')[:k]].mean())})
        names=g.symbol.to_numpy();cs=np.zeros(n);cs[top]=ys[top]/k;cs[bottom]=-ys[bottom]/k
        for symbol,amount in zip(names,cs):contributions[symbol]+=float(amount)/len(validdates)
        assert abs(cs.sum()-row['spread'])<1e-12
        groups.append((day,names,ar));daily.append(row)
    calendar=days[(days>='2023-04-03')&(days<='2024-12-31')]
    frame=pd.DataFrame(daily).set_index('date').reindex(calendar);frame.to_csv(B/'daily_diagnostics.csv',index_label='date',float_format='%.17g')
    assert np.nanmax(np.abs(frame.signal_RankIC-frame.market_relative_RankIC))<1e-12
    # Reuse existing circular-block bootstrap with NaN calendar slots unchanged.
    summary={c:block_mean(frame[c],5,samples=5000,seed=130301) for c in ['partial_RankIC','partial_REV5_only','partial_with_beta','signal_RankIC','REV5_RankIC','MOM20_RankIC','LOWVOL20_RankIC','beta_RankIC','spread','baseline_REV5_spread']}
    old=json.loads((R/'runtime/task14/validation.json').read_text())['primary_tests'];ps=[float(x['p']) for x in old]+[1.]*(38-len(old))+[summary['partial_RankIC']['p_positive']];assert len(ps)==39
    corrected=holm(ps)[-1]
    overlap={c:{'mean_daily_rank_correlation':float(frame['overlap_'+c].mean()),'median_daily_rank_correlation':float(frame['overlap_'+c].median()),'q05_q95':frame['overlap_'+c].quantile([.05,.95]).tolist()} for c in COLUMNS[1:]}
    contribution=sorted([{'symbol':s,'mean_daily_gross_spread_contribution':v} for s,v in contributions.items()],key=lambda x:-abs(x['mean_daily_gross_spread_contribution']))
    assert abs(sum(x['mean_daily_gross_spread_contribution'] for x in contribution)-frame.spread.mean())<1e-12
    topnames=[x['symbol'] for x in contribution[:3]]
    def filtered_means(exclude):
        scores=[]
        for day,names,ar in groups:
            a=ar[~np.isin(names,list(exclude))]
            if len(a)>=50:scores.append(partial_rank(a)[0])
        return {'mean_partial_RankIC':float(np.nanmean(scores)) if scores else None,'valid_dates':int(np.isfinite(scores).sum())}
    loo={s:filtered_means({s}) for s in sorted(assets)}
    sensitivity={'all_leave_one_out':loo,'drop_top1_spread_name':{'excluded':topnames[:1],**filtered_means(set(topnames[:1]))},'drop_top3_spread_names':{'excluded':topnames,**filtered_means(set(topnames))}}
    topdays=frame.partial_RankIC.abs().nlargest(5).index
    sensitivity['drop_top5_abs_partialIC_days']={'excluded':[d.date().isoformat() for d in topdays],'mean_partial_RankIC':float(frame.partial_RankIC.drop(topdays).mean())}
    loo_values=[v['mean_partial_RankIC'] for v in loo.values() if v['mean_partial_RankIC'] is not None]
    sensitivity['LOO_range']=[min(loo_values),max(loo_values)];sensitivity['positive_LOO_count']=sum(x>0 for x in loo_values)
    topabs=sum(abs(x['mean_daily_gross_spread_contribution']) for x in contribution[:3]);totalabs=sum(abs(x['mean_daily_gross_spread_contribution']) for x in contribution)
    sensitivity['top3_absolute_net_symbol_contribution_share']=topabs/totalabs if totalabs else None
    years={str(y):{c:block_mean(f[c],5,samples=5000,seed=130301) for c in ['partial_RankIC','signal_RankIC','spread']} for y,f in frame.groupby(frame.index.year)}
    # R0 pre-existing regime snapshot, evaluation stratification only; not fed to signal.
    rg=pd.read_csv(S/'US_regimes.csv',index_col='date',parse_dates=True).reindex(frame.index);regimes={}
    for axis in ['AS_OF_REGIME','EX_POST_REGIME']:
        regimes[axis]={str(key):{'dates':int(frame.loc[ix,'partial_RankIC'].notna().sum()),'mean_partial_RankIC':float(frame.loc[ix,'partial_RankIC'].mean()) if frame.loc[ix,'partial_RankIC'].notna().any() else None,'mean_spread':float(frame.loc[ix,'spread'].mean()) if frame.loc[ix,'spread'].notna().any() else None} for key,ix in rg.groupby(axis).groups.items()}
    p=summary['partial_RankIC'];ci=p['CI95'];near_duplicate=any(abs(overlap[c]['mean_daily_rank_correlation'])>=.95 for c in ['REV5','MOM20','LOWVOL20'])
    robust=all(x>0 for x in loo_values) and sensitivity['drop_top3_spread_names']['mean_partial_RankIC']>0 and sensitivity['drop_top5_abs_partialIC_days']['mean_partial_RankIC']>0
    rev=summary['partial_REV5_only'];increment=rev['mean']>0 and rev['CI95'][0]>0
    passed=p['mean']>0 and ci[0]>0 and corrected<.05 and not near_duplicate and robust and increment
    status='RESEARCH_CANDIDATE' if passed else ('NO_INCREMENTAL_EVIDENCE' if p['mean']<=0 else 'INSUFFICIENT_EVIDENCE')
    paired.to_csv(B/'paired_evaluation.csv.gz',index=False,float_format='%.17g',compression={'method':'gzip','mtime':0})
    write('evaluation.json',{'at':now(),'classification':'HISTORICAL_EXPLORATORY_SURVIVOR_RESEARCH','US':{'dates':len(validdates),'symbol_dates':len(paired),'names':paired.symbol.nunique(),'calendar_slots':len(calendar),'first':validdates.min().date().isoformat(),'last':validdates.max().date().isoformat(),'summary':summary,'Holm39_primary_p':corrected,'local_family1_p':p['p_positive'],'baseline_overlap':overlap,'mean_signal_residual_variance_fraction':float(frame.residual_signal_variance_fraction.mean()),'year_stability':years,'regime_stability':regimes,'symbol_contributions':contribution,'sensitivity':sensitivity},'KR':json.loads((B/'phase_a_gate.json').read_text())['KR'],'checks':{'market_relative_ranks_identical':True,'minimum50_same_names_for_all_comparisons':True,'full_forward6_valid_sessions':True,'exit_before_cutoff':True,'pair_count_matches_sealed_gate':True,'signal_source_hash_unchanged':sha(R/'experiments/task13_c1/factor.py')==seal['candidate_fingerprint']},'decision_gates':{'positive_primary':p['mean']>0,'CI_lower_positive':ci[0]>0,'Holm39_pass':corrected<.05,'increment_vs_REV5_only':increment,'not_near_duplicate':not near_duplicate,'concentration':robust},'decision':status,'independent_alpha_confirmed':False,'portfolio_or_after_cost_performance_computed':False,'Task15_automatic':False})
    write('label_alignment_samples.json',checks)
    write('evaluation_attempt.json',{'status':'COMPLETED','at':now(),'evaluations':1,'evaluation_sha256':sha(B/'evaluation.json'),'immutable_signal_seal_sha256':sha(B/'seal.json')})
    ledger=json.loads((B/'attempt_ledger.json').read_text());ledger['attempts'][0].update({'status':'COMPLETED','outcome_queries':1,'decision':status});write('attempt_ledger.json',ledger)
    write('resources.json',{'evaluation_CPU_seconds':time.process_time()-start,'evaluation_wall_seconds':time.monotonic()-wall,'internal_research_LLM_calls':0,'internal_research_tokens':0,'external_HTTP':0,'training':0,'new_installs':0,'Codex_session_usage':'Not metered here; not reported as zero','trade_strategy_or_operating_changes':False})
    write('completion.json',{'technical':'EXECUTION_VERIFIED_US_ONLY','research':status,'classification':'HISTORICAL_EXPLORATORY','KR':'BLOCKED_HISTORICAL_BOARD_MAPPING_UNVERIFIED','Task14':'Completed C1 diagnostic only; no automatic next task','Task15':False})
    print(json.dumps({'decision':status,'primary':p,'Holm39':corrected,'overlap':overlap,'gates':json.loads((B/'evaluation.json').read_text())['decision_gates']},ensure_ascii=False,indent=2))

if __name__=='__main__':run()

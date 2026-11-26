"""Single H20 label access and paired signal evaluation using the existing Qlib/statistics path."""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import json
import resource

import numpy as np
import pandas as pd
from qlib.contrib.eva.alpha import calc_ic

from experiments.task13_h1.prepare_inputs import OUT, sha, write_json
from experiments.task14.stats_eval import block_mean, corr, residual

CONTROL=['MOM20','MOM63','MOM10','VOL10','ON_MINUS_ID60']
VISIBLE=['score','MOM20','MOM63','ON_MINUS_ID60']
SERIES=['score','MOM20','MOM63','ON_MINUS_ID60']


def load_inputs(m):
    z=np.load(OUT/f'{m}_panel.npz')
    f=np.load(OUT/f'{m}_features.npz')
    days=pd.DatetimeIndex(z['dates'],name='datetime')
    names=pd.Index(z['symbols'],name='instrument')
    scores={k:pd.DataFrame(f[k],index=days,columns=names) for k in ['score',*CONTROL]}
    return z,scores,days,names


def exact_dates(days, contract):
    first,last=map(pd.Timestamp,contract['exposure_dates'])
    within=np.flatnonzero((days>=first)&(days<=last))
    return days[within[within+21<=within[-1]]]


def preflight(m, contract):
    z,scores,days,names=load_inputs(m)
    complete=np.logical_and.reduce([s.notna().to_numpy() for s in scores.values()])
    # Label eligibility uses only presence bits here, never computes returns.
    op=pd.DataFrame(np.isfinite(z['open']),index=days,columns=names)
    for i in range(1,22):
        complete &= op.shift(-i,fill_value=False).to_numpy()
    window=exact_dates(days,contract)
    eligible=pd.DataFrame(complete,index=days,columns=names).loc[window]
    counts=eligible.sum(axis=1)
    range_position=(pd.DataFrame(z['close'],index=days,columns=names)-z['low'])/(z['high']-z['low']+1e-8)
    volume=pd.DataFrame(z['volume'],index=days,columns=names)
    condition=volume.gt(2*volume.rolling(20,min_periods=20).median().shift())
    shocks=range_position.where(condition,0).where(range_position.notna()).rolling(10,min_periods=10).sum()
    overlap=scores['score'].where(eligible).rank(axis=1).corrwith(shocks.where(eligible).rank(axis=1),axis=1)
    overlap=overlap.reindex(counts.index[counts>=50]).dropna()
    assert len(window)>0 and int(counts.ge(50).sum())>=100, m
    return {'valid_days':int(counts.ge(50).sum()),'observation_pairs':int(counts[counts.ge(50)].sum()),
            'eligible_window_first':str(window[0].date()),'eligible_window_last':str(window[-1].date()),
            'shock_proxy_mean_spearman':float(overlap.mean()) if len(overlap) else None,
            'no_future_returns_computed':True},eligible


def finite(s):
    return float(s) if np.isfinite(s) else None


def stats(m, contract, eligible):
    z,scores,days,names=load_inputs(m)
    op=pd.DataFrame(z['open'],index=days,columns=names)
    labels=(op.shift(-21)/op.shift(-1)-1).where(eligible.reindex(days,fill_value=False))
    members=eligible.index[eligible.sum(axis=1)>=50]
    group={k:s.loc[members].where(eligible.loc[members]) for k,s in scores.items()}
    paired=pd.DataFrame({k:s.stack(future_stack=True) for k,s in group.items()}|{'label':labels.loc[members].stack(future_stack=True)}).dropna()
    assert paired.groupby(level=0).size().ge(50).all()
    outcome={}
    for k in SERIES:
        ic,ric=calc_ic(paired[k],paired.label)
        outcome[k]={'IC':finite(ic.mean()),'RankIC':finite(ric.mean())}
    outcome['ZERO']={'IC':None,'RankIC':None,'spread':None,'reason':'constant score; no ranked portfolios'}
    records=[]
    contributions=defaultdict(float)
    for dt,row in paired.groupby(level=0,sort=True):
        ranks=row.rank()
        response=ranks.label
        rc=ranks.score
        record={'date':dt,'n':len(row)}
        for k in SERIES:
            record[f'{k}_RankIC']=corr(ranks[k],response)
            # Average ties at the exact boundary so alphabetical order cannot break them.
            band=len(row)//5
            u=row[k].rank(ascending=False)
            d=row[k].rank()
            top=row.label[u<=band]
            bottom=row.label[d<=band]
            record[f'{k}_spread']=top.mean()-bottom.mean()
            if k=='score':
                for ix,v in top.items():
                    contributions[ix[1]]+=v/len(top)
                for ix,v in bottom.items():
                    contributions[ix[1]]-=v/len(bottom)
        for k in VISIBLE[1:]:
            record[f'overlap_{k}']=corr(ranks[k],rc)
            r0,_=residual(rc,ranks[[k]])
            r1,_=residual(response,ranks[[k]])
            record[f'partial_{k}']=corr(r0,r1)
        r0,_=residual(rc,ranks[CONTROL])
        r1,_=residual(response,ranks[CONTROL])
        record['partial_joint']=corr(r0,r1)
        records.append(record)
    daily=pd.DataFrame(records).set_index('date').reindex(eligible.index)
    for k in SERIES:
        pd_rank_ic=daily[f'{k}_RankIC'].mean()
        assert abs(pd_rank_ic-outcome[k]['RankIC'])<1e-10,k
        outcome[k]['spread']=finite(daily[f'{k}_spread'].mean())
    seed=contract['statistics']['seed']
    inference=block_mean(daily.partial_joint,20,samples=5000,seed=seed)
    inference['bonferroni43_positive']=min(1,inference['p_positive']*43)
    regime=pd.Series(z['regime'],index=days).reindex(daily.index)
    yearly=daily.groupby(daily.index.year).partial_joint.agg(['count','mean'])
    regimes=daily.groupby(regime).partial_joint.agg(['count','mean'])
    yearly=yearly[yearly['count']>0]
    regimes=regimes[regimes['count']>0]
    monthly=daily.groupby(daily.index.to_period('M')).partial_joint.mean().dropna()
    daily['regime']=regime
    daily.to_csv(OUT/f'{m}_daily.csv')
    spread_n=int(daily.score_spread.notna().sum())
    pos=sorted(((name,pnl/spread_n) for name,pnl in contributions.items()),key=lambda a:-a[1])
    gross_positive=sum(x[1] for x in pos if x[1]>0)
    excluded=[]  # contribution arithmetic only; no reranking or alternative evaluation
    for n in [1,3,5]:
        value=sum(x[1] for x in pos[:n])
        excluded.append({'n':n,'share_positive':value/gross_positive if gross_positive else None,
                         'additive_spread_without_top_contributions':outcome['score']['spread']-value})
    return {'paired_rows':len(paired),'unique_symbols':paired.index.get_level_values('instrument').nunique(),
            'measures':outcome,'partial_joint':inference,
            'overlap':{k:finite(daily[f'overlap_{k}'].mean()) for k in VISIBLE[1:]},
            'single_control_partial':{k:finite(daily[f'partial_{k}'].mean()) for k in VISIBLE[1:]},
            'by_year':yearly.to_dict('index'),'by_regime':regimes.to_dict('index'),
            'weakest_months':{str(k):v for k,v in monthly.nsmallest(3).items()},
            'strongest_months':{str(k):v for k,v in monthly.nlargest(3).items()},
            'positive_months':int(monthly.gt(0).sum()),'months':len(monthly),
            'concentration':excluded,'positive_contributors':pos[:5],'negative_contributors':pos[-5:]}


def main():
    assert not (OUT/'reservation.json').exists()
    p=OUT/'research_contract.json'
    contract=json.loads(p.read_bytes())
    features=json.loads((OUT/'feature_gate.json').read_bytes())
    assert features['contract_sha256']==sha(p)
    assert sha(OUT/'input_receipt.json')==features['inputs_sha256']
    assert sha(Path(__file__).with_name('native_features.py'))==features['worker_sha256']
    inputs=json.loads((OUT/'input_receipt.json').read_bytes())
    for m in ('US','KR'):
        assert sha(OUT/f'{m}_panel.npz')==inputs['checks'][m]['panel_sha256']
        assert sha(OUT/f'{m}_features.npz')==features['members'][m]['sha256']
    gates={m:preflight(m,contract) for m in ('US','KR')}
    write_json(OUT/'evaluation_gate.json',{m:x[0] for m,x in gates.items()})
    write_json(OUT/'reservation.json',{'utc':datetime.now(timezone.utc).isoformat(),'contract_sha256':sha(p),
              'code_sha256':sha(Path(__file__)),'feature_gate_sha256':sha(OUT/'feature_gate.json'),
              'evaluation_gate_sha256':sha(OUT/'evaluation_gate.json'),'max_eval_runs':1})
    result={m:stats(m,contract,elig) for m,(_,elig) in gates.items()}
    primary=result['US']['partial_joint']
    action='SIGNAL_PROMISING_HISTORICAL' if primary['CI95'][0]>0 and primary['bonferroni43_positive']<.05 else 'NO_INCREMENTAL_SIGNAL'
    use=resource.getrusage(resource.RUSAGE_SELF)
    write_json(OUT/'result.json',{'execution':'NATIVE_COMPONENT_VALIDATED','prediction':action,
               'economics':'TRADING_ECONOMICS_NOT_TESTED','task15':'TASK15_ELIGIBILITY_BLOCKED',
               'history':contract['history'],'candidate':contract['candidate'],'markets':result,
               'CPU_s':use.ru_utime+use.ru_stime,'LLM_calls':0,'market_requests':0,'portfolio_runs':0})
    print({k:r['partial_joint'] for k,r in result.items()},flush=True)


if __name__=='__main__':
    main()

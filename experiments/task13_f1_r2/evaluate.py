"""One isolated F1 replay, with original V77 execution and matched exposures."""
from dataclasses import replace
import json
from pathlib import Path
import numpy as np
import pandas as pd
from experiments.task13_f1_r2.collect import ROOT, OUT, sha, now, save
from experiments.task13_f1_r2.prepare import COST, POLICY, INDEX, SCORE_CONTROLS, frame
from experiments.task14.stats_eval import block_mean, corr, holm, residual
from quant_harness.investment.research import replay_targets, metrics
from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec


def target_ledgers(prior, flow, risk, dates):
    schedule=set(dates[::5])
    scheduled=risk.ne(risk.shift()).reindex(dates)
    rebalances=set(scheduled.index[scheduled])|schedule
    ledgers=[[],[]]
    picks=[{},{}]
    for d in dates:
        if d in rebalances:
            picks=[{},{}]
            if risk[d]:
                mom=prior.loc[d]
                pool=mom[mom.gt(0)&flow.loc[d].notna()].dropna()
                fused=(pool.rank(pct=True)+flow.loc[d,pool.index].rank(pct=True))/2
                for i,ranks in enumerate([pool,fused]):
                    names=ranks.sort_values(ascending=False,kind='stable').index[:4]
                    picks[i]={s:.2 for s in names}
        assert len(picks[0])==len(picks[1])
        for book,pick in zip(ledgers,picks):
            book.append({'date':d,'target_weights_json':json.dumps(pick)})
    return [pd.DataFrame(book) for book in ledgers],rebalances


def rank_diagnostics(flow, prior, ret, dates, board_returns):
    records=[]
    for day in dates:
        group=pd.DataFrame({k:prior[k].loc[day] for k in SCORE_CONTROLS})
        group['FLOW5']=flow.loc[day]
        group['H5']=ret.loc[day]
        group=group.dropna()
        if len(group)<12:
            continue
        ranks=group.rank()
        z=ranks[SCORE_CONTROLS].to_numpy()
        if np.linalg.matrix_rank(np.column_stack([np.ones(len(z)),z]))!=len(SCORE_CONTROLS)+1:
            continue
        x,_=residual(ranks.FLOW5,z)
        y,_=residual(ranks.H5,z)
        gross=group.sort_values('FLOW5',kind='stable').H5
        tail=len(gross)//5
        dayrow={'date':day,'n':len(group),'RankIC':corr(ranks.FLOW5,ranks.H5),
                'partial_RankIC':corr(x,y),'MOM63_RankIC':corr(ranks.MOM63,ranks.H5),
                'tail_spread':gross.iloc[-tail:].mean()-gross.iloc[:tail].mean(),
                'board_relative_RankIC':corr(group.FLOW5,group.H5-board_returns.loc[day,group.index],rank=True)}
        records.append(dayrow)
    daily=pd.DataFrame(records).set_index('date').reindex(dates)
    return daily, block_mean(daily.partial_RankIC,5)


def summarize(account,fills,initial,dates):
    nav=account.set_index('date').nav_krw
    if len(nav)==0 or not np.isfinite(nav.iloc[-1]):
        return {'missing_nav':int(nav.isna().sum())}, None, None
    out=metrics(account,fills,initial)
    observed=pd.concat([pd.Series([initial]),nav]).dropna()
    out['mdd_pct']=float((observed/observed.cummax()-1).min()*100)
    ret=nav.div(nav.shift(1,fill_value=initial))-1
    expo=1-account.set_index('date').cash_krw/nav
    out.update(missing_nav=int(nav.isna().sum()),sharpe=float(ret.mean()/ret.std(ddof=0)*np.sqrt(252)) if ret.std(ddof=0)>0 else 0,annualized_vol_pct=float(ret.std()*np.sqrt(252)*100),
               mean_equity_exposure_pct=float(expo.mean()*100),mean_cash_pct=float((1-expo.mean())*100))
    return out,ret,expo


def pnl_attribution(account,fills,closes,initial,sector):
    """Additive close-to-close cash P&L by instrument, with the execution ledger."""
    qty={}; total={}
    grouped={d:g for d,g in fills.groupby('date')} if len(fills) else {}
    marks={}
    for row in account.itertuples():
        prices=closes.loc[row.date]
        for s in qty:
            if np.isfinite(prices[s]):
                if qty[s]:
                    total[s]+=qty[s]*(prices[s]-marks[s])
                marks[s]=prices[s]
        for f in grouped.get(row.date,[]).itertuples() if row.date in grouped else []:
            signed=f.quantity if f.side=='BUY' else -f.quantity
            total[f.ticker]=total.get(f.ticker,0)+signed*(prices[f.ticker]-f.fill_price_krw)-f.fee_krw
            qty[f.ticker]=qty.get(f.ticker,0)+signed
            marks[f.ticker]=prices[f.ticker]
    if not np.isclose(sum(total.values()),account.nav_krw.iloc[-1]-initial,atol=.01):
        raise ValueError('cannot reconcile attribution')
    groups={}
    for name,pnl in total.items():
        groups[sector[name]]=groups.get(sector[name],0)+pnl
    return total,groups


def run():
    verdict=json.loads((OUT/'preflight.json').read_bytes())
    assert verdict['status']=='PASS_HISTORICAL_ONLY'
    assert all(k['eligible_dates_min12']>=60 for k in verdict['precheck'].values())
    original=OUT/'evaluation_reservation.json'
    if original.exists():
        prior=json.loads(original.read_bytes())
        assert prior['preflight_sha256']==sha((OUT/'preflight.json').read_bytes())
        assert prior['contract_sha256']==sha((OUT/'contract.json').read_bytes())
        assert not any(OUT.glob('T?_rank.csv')) and not (OUT/'result.json').exists()
        assert 'operands could not be broadcast' in (OUT/'evaluation_alignment_failure.log').read_text()
    for filename,hashval in verdict['sources'].items():
        if original.exists() and filename=='experiments/task13_f1_r2/evaluate.py':
            assert sha((OUT/'evaluate_before_alignment_repair.py').read_bytes())==hashval
            continue
        if sha((ROOT/filename).read_bytes())!=hashval:
            raise ValueError('sealed input changed: '+filename)
    contract=json.loads((OUT/'contract.json').read_bytes())
    e=OUT/'evaluation_repair_reservation.json' if original.exists() else original
    save(e,{'status':'RESERVED_ONCE','at':now(),'preflight_sha256':sha((OUT/'preflight.json').read_bytes()),
            'contract_sha256':sha((OUT/'contract.json').read_bytes()), 'implementation_sha256':sha(Path(__file__).read_bytes())})
    x=pd.read_pickle(OUT/'inputs.pkl')
    p=x['panel']
    dates=p['open'].loc['2023-04-03':].index
    idx=frame(INDEX).close.reindex(p['open'].index)
    idx_ret=idx.reindex(dates).div(idx.shift(1).reindex(dates))-1
    ko=frame(INDEX).open.reindex(p['open'].index)
    kd=frame(ROOT/'runtime/task13_r0/accepted/KR/^KQ11/quote.csv').open.reindex(p['open'].index)
    bret={'KS':ko.shift(-5)/ko-1,'KQ':kd.shift(-5)/kd-1}
    # Prior-only eligibility governs selection; actual open/volume limits govern fills.
    gap=p['eligible'].rolling(6,min_periods=6).sum().shift(-5).eq(6)
    h5=(p['open'].shift(-5)/p['open']-1).where(gap)
    for _,end in contract['testing']:
        final=int(dates.get_indexer([pd.Timestamp(end)],method='pad')[0])
        h5.loc[dates[final-4:final+1]]=np.nan
    rel=pd.DataFrame({s:bret[s.split('.')[-1]] for s in h5.columns})
    market={'open':p['open'].where(p['eligible']),'close':p['close'].where(p['eligible']),
            'adv20_d1':(p['close']*p['volume']).where(p['eligible']).rolling(20,min_periods=20).mean().shift(1)}
    # Task10 uses prior rolling close times volume for sizing; FLOW5 uses separate official amounts.
    initial=json.loads(POLICY.read_bytes())['strategy']['capital']['KR']
    pars=json.loads(COST.read_bytes())['execution_assumptions']
    min_notional=initial*pars.pop('minimum_order_nav_fraction')
    spec=ExecutionSpec(**pars,minimum_order_notional_krw=min_notional)
    no_cost=replace(spec,buy_fee_bps=0,sell_fee_bps=0,half_spread_bps=0,impact_bps_at_1pct_adv=0,max_impact_bps=0)
    etf=x['ETF']
    risk=etf.ge(etf.rolling(63,min_periods=63).mean()).shift(1,fill_value=False)
    sector={a['symbol']:a.get('sector_current') for a in json.loads((ROOT/'runtime/task13_r0/native_manifest/assets.json').read_bytes())}
    results={}
    for lag in [1,2]:
        ledgers,rebalances=target_ledgers(x['prior']['MOM63'],x['flow'][lag],risk,dates)
        b_names=[set(json.loads(v)) for v in ledgers[1].target_weights_json]
        a_names=[set(json.loads(v)) for v in ledgers[0].target_weights_json]
        changed=pd.Series([a!=b for a,b in zip(a_names,b_names)],index=dates)
        ranks,rank_stats=rank_diagnostics(x['flow'][lag],x['prior'],h5,dates,rel)
        ranks.to_csv(OUT/f'T{lag}_rank.csv')
        bucket={'partial_RankIC':rank_stats,'mean_RankIC':float(ranks.RankIC.mean()),
                'mean_MOM63_RankIC':float(ranks.MOM63_RankIC.mean()),
                'board_relative_RankIC':float(ranks.board_relative_RankIC.mean()),
                'mean_H5_tail_spread':float(ranks.tail_spread.mean()),
                'rank_by_year':ranks.partial_RankIC.groupby(ranks.index.year).mean().to_dict(),
                'changed_rebalance_sessions':sum(bool(changed.loc[d]) for d in rebalances),
                'rebalance_sessions':len(rebalances),'changed_target_holding_days':int(changed.sum()),
                'max_equal_gross_deviation':0,'market_KOSPI_price_return_pct':float(((1+idx_ret).prod()-1)*100)}
        paths=[]
        for label,ledger in zip(['A','B'],ledgers):
            name=f'T{lag}_{label}'
            account,fills,intents=replay_targets(market,dates,ledger,initial,spec,rebalance_dates=rebalances,allow_unpriced_hold=True)
            gross,_,_=replay_targets(market,dates,ledger,initial,no_cost,rebalance_dates=rebalances,allow_unpriced_hold=True)
            account.to_csv(OUT/f'{name}_nav.csv',index=False)
            fills.to_csv(OUT/f'{name}_fills.csv',index=False)
            intents.to_csv(OUT/f'{name}_intents.csv',index=False)
            ledger.to_csv(OUT/f'{name}_targets.csv',index=False)
            o,ret,expo=summarize(account,fills,initial,dates)
            if ret is not None:
                o['excess_KOSPI_pp']=o['return_pct']-bucket['market_KOSPI_price_return_pct']
                o['matched_exposure_KOSPI_return_pct']=float(((1+idx_ret*expo.shift(1,fill_value=0)).prod()-1)*100)
                o['pnl_by_stock_krw'],o['pnl_by_sector_krw']=pnl_attribution(account,fills,market['close'],initial,sector)
            o['gross_no_cost_return_pct']=float((gross.nav_krw.iloc[-1]/initial-1)*100) if np.isfinite(gross.nav_krw.iloc[-1]) else None
            bucket[label]=o
            paths.append((ret,expo))
        if all(ret is not None for ret,_ in paths):
            a,ea=paths[0]; b,eb=paths[1]
            delta=b-a
            adjusted=delta-idx_ret*(eb-ea).shift(1,fill_value=0)
            bucket.update(net_delta_pp=bucket['B']['return_pct']-bucket['A']['return_pct'],
                          net_daily_delta=block_mean(delta,20),net_daily_delta_common_market_exposure=block_mean(adjusted,20),
                          net_daily_delta_by_year=delta.groupby(delta.index.year).mean().to_dict(),
                          net_daily_delta_by_asof_regime=delta.groupby(x['regimes'].reindex(dates)).agg(['count','mean']).to_dict('index'),
                          conditional_delta_when_target_diff=float(delta[changed].mean()))
            stock_a=bucket['A']['pnl_by_stock_krw']; stock_b=bucket['B']['pnl_by_stock_krw']
            changes={s:stock_b.get(s,0)-stock_a.get(s,0) for s in sorted(set(stock_a)|set(stock_b))}
            largest=max(changes,key=lambda s:abs(changes[s]))
            bucket['attribution']={'largest_difference_symbol':largest,'largest_difference_krw':changes[largest],
                                   'additive_delta_without_largest_krw':sum(changes.values())-changes[largest]}
        results[lag]=bucket
    tests=[(lag,k) for lag in results for k in ['net_daily_delta','partial_RankIC']]
    raw=[results[lag].get(k,{}).get('p_positive',1) for lag,k in tests]
    correction=holm(raw)
    for (lag,k), value,pval in zip(tests,correction,raw):
        if k in results[lag]:
            results[lag][k].update(Holm4=value,Bonferroni_campaign45=min(1,pval*45))
    primary=results[1]
    state='INSUFFICIENT_EVIDENCE'
    if 'net_daily_delta' in primary:
        if primary['net_delta_pp']<=0 and primary['partial_RankIC']['mean']<=0:
            state='NO_INCREMENTAL_EVIDENCE'
        elif (primary['net_delta_pp']>0 and primary['net_daily_delta']['Bonferroni_campaign45']<.05
              and primary['partial_RankIC']['Bonferroni_campaign45']<.05
              and all(v>0 for v in primary['net_daily_delta_by_year'].values())
              and primary['attribution']['additive_delta_without_largest_krw']>0):
            state='HISTORICAL_INCREMENTAL_CANDIDATE'
    save(OUT/'result.json',{'status':state,'classification':'HISTORICAL_EXPLORATORY','operational_T1':'NOT_VERIFIED',
                           'results':results,'sessions':len(dates),'starts':str(dates[0].date()),'ends':str(dates[-1].date())})
    print(state,[(k,r.get('net_delta_pp'),r['partial_RankIC']['mean']) for k,r in results.items()],flush=True)


if __name__=='__main__':
    run()

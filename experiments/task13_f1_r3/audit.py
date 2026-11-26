"""Independent R2 ledger audit. No stock execution engine or new strategy."""
from collections import Counter, defaultdict, deque
from hashlib import sha256
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
R2=ROOT/'runtime/task13_f1_r2'
OUT=ROOT/'runtime/task13_f1_r3'
R0=ROOT/'runtime/task13_r0'
CAP=10_000_000


def read(p):
    return json.loads(p.read_bytes())


def timed(p):
    x=pd.read_csv(p,parse_dates=['date']).set_index('date')
    assert x.index.is_unique, str(p)
    return x.sort_index()


def ratio_metrics(nav):
    first,last=nav.index[[0,-1]]
    assert nav.iloc[-1]>0
    total=float(nav.iloc[-1]/CAP-1)
    years=(last-first).days/365.2425
    observed=np.r_[CAP,nav.dropna().to_numpy()]
    dd=observed/np.maximum.accumulate(observed)-1
    daily=nav.div(nav.shift(1,fill_value=CAP)).sub(1).dropna()
    return {'final_nav':float(nav.iloc[-1]),'total_pct':total*100,
            'cagr_pct':100*((1+total)**(1/years)-1),'mdd_pct':100*float(dd.min()),
            'vol_pct':float(100*daily.std(ddof=1)*math.sqrt(252)),
            'sharpe_rf0':float(daily.mean()/daily.std(ddof=0)*math.sqrt(252)),
            'observed_marks':int(nav.notna().sum()),'daily_returns':len(daily)}


def reconstruct(arm, datasets, dates, schedule, risk, expected_targets, cfg):
    p,q,nom,adv,boards,assets=datasets
    nav=timed(R2/f'T1_{arm}_nav.csv')
    ledger=timed(R2/f'T1_{arm}_targets.csv')
    assert nav.index.equals(dates) and ledger.index.equals(dates)
    targets=ledger.target_weights_json.map(json.loads)
    assert targets.tolist()==expected_targets
    fills=pd.read_csv(R2/f'T1_{arm}_fills.csv',parse_dates=['date'])
    assert not fills.duplicated(['date','ticker']).any()
    fills_by_day={d:g for d,g in fills.groupby('date')}
    cash=CAP
    qty=defaultdict(int)
    lots=defaultdict(deque)
    realized=[]
    marks={}
    gain=defaultdict(float)
    day_rows=[]
    snapshots=[]
    cap_events=[]
    latest_known_masks=Counter()
    weights=defaultdict(list)
    held_sessions=Counter()
    errors=defaultdict(float)
    costs=Counter()
    nominal_probe=Counter()
    plan=read(OUT/'plan.json')
    assert plan['capital_krw']==CAP
    for i,d in enumerate(dates):
        day=nav.loc[d]
        fills_day=fills_by_day.get(d)
        invested_before={s:n for s,n in qty.items() if n}
        prices=p['close'].loc[d]
        for s,n in invested_before.items():
            if np.isfinite(prices[s]):
                gain[s]+=n*(prices[s]-marks[s])
                marks[s]=prices[s]
        if fills_day is not None:
            assert d in schedule
            assert fills_day.side.tolist()==sorted(fills_day.side,reverse=True)
            prior=datasets[0]['close'].index.get_loc(d)-1
            old=p['close'].iloc[prior]
            prev_nav=cash+sum(n*old[s] for s,n in invested_before.items())
            assert np.isfinite(prev_nav) and prev_nav>0
            for f in fills_day.itertuples(index=False):
                s=f.ticker
                n=int(f.quantity)
                signed=1 if f.side=='BUY' else -1
                target_n=int(prev_nav*targets[d].get(s,0)/old[s]) if s in targets[d] else 0
                assert f.quantity==n and n>0 and f.side in ('BUY','SELL')
                assert signed*(target_n-qty[s])>=n
                assert d >= pd.Timestamp(max(assets[s]['list_date_kind'],assets[s]['list_date_toss']))
                assert q.loc[d,s]
                op=p['open'].loc[d,s]
                avg=adv.loc[d,s]
                assert op>0 and avg>0
                assert n*op>=CAP*cfg['minimum_order_nav_fraction']-1e-6
                assert n*op<=avg*cfg['max_participation_of_d1_adv']+1e-6
                bps=min(cfg['max_impact_bps'],cfg['impact_bps_at_1pct_adv']*math.sqrt(n*op/avg/.01))
                fill=op*(1+signed*(cfg['half_spread_bps']+bps)/10_000)
                fee=n*fill*cfg['buy_fee_bps' if signed>0 else 'sell_fee_bps']/10_000
                for metric,v in [('open',op-f.reference_open_krw),('fill',fill-f.fill_price_krw),('fee',fee-f.fee_krw),
                                 ('spread',n*op*cfg['half_spread_bps']/10_000-f.half_spread_cost_krw),
                                 ('impact',n*op*bps/10_000-f.impact_cost_krw)]:
                    errors[metric]=max(errors[metric],abs(v))
                wx=nom['open'].loc[d,s]
                if np.isfinite(wx):
                    nominal_probe['available_quote_fills']+=1
                    nominal_probe['different_from_quote_open']+=int(not np.isclose(op,wx,rtol=1e-8))
                    nominal_probe['nonintegral_adjusted_open']+=int(not np.isclose(op,round(op),rtol=1e-9))
                qty[s]+=signed*n
                cash-=signed*n*fill+fee
                marks[s]=prices[s]
                gain[s]+=signed*n*(prices[s]-fill)-fee
                costs[f.side+'_fee']+=fee
                costs['spread']+=f.half_spread_cost_krw
                costs['impact']+=f.impact_cost_krw
                costs['notional']+=n*op
                if signed>0:
                    lots[s].append([i,n,fill+fee/n])
                else:
                    left=n
                    while left:
                        lot=lots[s][0]
                        take=min(left,lot[1])
                        realized.append({'symbol':s,'buy':str(dates[lot[0]].date()),'sell':str(d.date()),
                                         'sessions':i-lot[0],'shares':take,'cost':take*lot[2],
                                         'profit':take*(fill-fee/n-lot[2])})
                        left-=take
                        lot[1]-=take
                        if not lot[1]:
                            lots[s].popleft()
                assert cash>=-1e-6 and qty[s]>=0
        active={s:n for s,n in qty.items() if n}
        ref={s:n for s,n in json.loads(day.holdings_json).items() if n}
        assert active==ref, (arm,d,'holdings')
        errors['cash']=max(errors['cash'],abs(cash-day.cash_krw))
        valuation={s:n*prices[s] for s,n in active.items()}
        total=cash+sum(valuation.values())
        assert pd.isna(total)==pd.isna(day.nav_krw)
        if np.isfinite(total):
            errors['nav']=max(errors['nav'],abs(total-day.nav_krw))
        stock_weight=max(valuation.values(),default=0)/total if np.isfinite(total) else np.nan
        expo=(total-cash)/total if np.isfinite(total) else np.nan
        for s in active:
            held_sessions[s]+=1
            if np.isfinite(total):
                weights[s].append(valuation[s]/total)
        snapshots.append(dict(gain))
        day_rows.append({'date':d,'nav':total,'cash':cash,'names':len(active),
                         'equity':expo,'max_name':stock_weight,'risk_on':bool(risk[d])})
        if len(active)>4 or (expo>.8+1e-9) or (not risk[d] and active):
            cap_events.append({'date':str(d.date()),'names':len(active),'held':active,'target':targets[d],
                               'risk_on':bool(risk[d]),'exposure':None if pd.isna(expo) else expo,
                               'new_buy':[] if fills_day is None else fills_day.loc[fills_day.side.eq('BUY'),'ticker'].tolist(),
                               'exit_to_zero_unfilled':sorted(set(active)-set(targets[d]))})
        for s in active:
            if not q.loc[d,s]:
                latest_known_masks[s]+=1
    assert all(v<=1e-5 for v in errors.values()), errors
    assert not any(qty.values()) and abs(sum(gain.values())-(cash-CAP))<.01
    assert abs(sum(r['profit'] for r in realized)-(cash-CAP))<.01
    table=pd.DataFrame(day_rows).set_index('date')
    daily=table.nav.div(table.nav.shift(1,fill_value=CAP))-1
    annual={}
    opening=CAP
    for year,sub in table.groupby(table.index.year):
        last=sub.nav.dropna().iloc[-1]
        annual[str(year)]={'return_pct':100*(last/opening-1),'endpoint_nav':last}
        opening=last
    significant=sorted(gain,key=gain.get,reverse=True)
    positive=sum(v for v in gain.values() if v>0)
    attribution=[{'ticker':s,'pnl_krw':gain[s],'held_sessions':held_sessions[s],
                  'mean_weight_when_held':float(np.mean(weights[s]))} for s in significant]
    by_board=defaultdict(float)
    for s,pnl in gain.items():
        by_board[boards[s]]+=pnl
    peak_proxy=table.nav.dropna()
    trough=(peak_proxy/peak_proxy.cummax()-1).idxmin()
    peak=peak_proxy.loc[:trough].idxmax()
    peak_g,trough_g=[snapshots[dates.get_loc(d)] for d in (peak,trough)]
    drawdown_attribution=sorted(((s,trough_g.get(s,0)-peak_g.get(s,0)) for s in set(peak_g)|set(trough_g)),key=lambda item:item[1])
    buy_sum=sum(t['shares'] for t in realized)
    episodes=pd.DataFrame(realized)
    realized_extremes=episodes.groupby(['symbol','buy','sell','sessions'],as_index=False).sum().sort_values('profit')
    result={
        **ratio_metrics(table.nav),'costs':dict(costs),'max_errors':dict(errors),'fills':len(fills),
        'distinct_fill_dates':int(fills.date.nunique()),'terminal_cash':cash,'min_cash':float(table.cash.min()),
        'stock_fill_basis':dict(nominal_probe),'max_names':int(table.names.max()),
        'days_over_four':int(table.names.gt(4).sum()),'risk_off_days_with_holdings':int((~table.risk_on&table.names.gt(0)).sum()),
        'target_breaches_with_new_buys':sum(e['names']>4 and bool(e['new_buy']) for e in cap_events),
        'max_equity':float(table.equity.max()),'max_name':float(table.max_name.max()),
        'days_equity_over_80_pct':int(table.equity.gt(.8+1e-9).sum()),'avg_equity':float(table.equity.mean()),
        'days_by_number_of_held_names':{str(k):int(v) for k,v in table.names.value_counts().items()},
        'missing_dates':table.index[table.nav.isna()].strftime('%Y-%m-%d').tolist(),
        'gaps_between_observed_marks':[
            {'from':str(peak_proxy.index[j-1].date()),'to':str(d.date()),
             'observed_nav_change_pct':100*float(peak_proxy.iloc[j]/peak_proxy.iloc[j-1]-1)}
            for j,d in enumerate(peak_proxy.index) if j and dates.get_loc(d)-dates.get_loc(peak_proxy.index[j-1])>1],
        'holding_sessions_share_weighted':sum(t['shares']*t['sessions'] for t in realized)/buy_sum,
        'top_fraction_of_positive':{str(j):sum(gain[s] for s in significant[:j])/positive for j in (1,3,5)},
        'arithmetic_net_delta_if_top_removed':{str(j):(cash-CAP-sum(gain[s] for s in significant[:j]))/CAP
                                               for j in (1,3,5)},
        'top_profit':attribution[:10],'top_loss':sorted([x for x in attribution if x['pnl_krw']<0],
                                                      key=lambda x:x['pnl_krw'])[:10],
        'winning_held_symbols':sum(v>0 for v in gain.values()),'held_symbols':len(gain),
        'pnl_by_board':dict(by_board),
        'largest_closed_fifo_win':realized_extremes.iloc[-1].to_dict(),
        'largest_closed_fifo_loss':realized_extremes.iloc[0].to_dict(),
        'annual':annual,'drawdown_peak':str(peak.date()),'drawdown_trough':str(trough.date()),
        'missing_stock_marks_while_held':dict(latest_known_masks),
        'peak_to_trough_nav_krw':float(table.nav[trough]-table.nav[peak]),
        'peak_to_trough_worst_contributors':drawdown_attribution[:5],
    }
    return result,table,daily,pd.DataFrame(cap_events),episodes


def stock_inputs(assets,calendar, expected_sources):
    adjusted={k:{} for k in ('open','close','volume')}
    quotes={k:{} for k in ('open','close')}
    masks={}
    match={}
    for s,a in assets.items():
        files=[ROOT/a['adjusted_path'],ROOT/a['eligibility_path']]
        for f,key in zip(files,('adjusted_hash','eligibility_hash')):
            digest=sha256(f.read_bytes()).hexdigest()
            assert digest==a[key]==expected_sources[str(f.relative_to(ROOT))]
        stock,quality=[timed(f).reindex(calendar) for f in files]
        mask=quality.eligible.eq(True)
        for k in adjusted:
            adjusted[k][s]=stock[k].where(mask)
        raw=timed(files[0].parent/'quote.csv').reindex(calendar)
        for k in quotes:
            quotes[k][s]=raw[k]
        masks[s]=mask
        match[s]=raw
    return ({k:pd.DataFrame(v) for k,v in adjusted.items()},pd.DataFrame(masks),
            {k:pd.DataFrame(v) for k,v in quotes.items()})


def frozen_selection(p, dates, risk, flow):
    close=p['close']
    mom=(close/close.shift(63)-1).where(close.rolling(64,min_periods=64).count().eq(64)).shift(1)
    schedule=set(dates[::5]) | {d for d in dates if risk.loc[d]!=risk.shift(1).loc[d]}
    assert len(schedule)==168
    ledgers={'A':[],'B':[]}
    t={'A':{},'B':{}}
    for d in dates:
        if d in schedule:
            s=mom.loc[d]
            pool=s.loc[s.gt(0)&flow.loc[d].notna()]
            scores={'A':pool,'B':(pool.rank(pct=True)+flow.loc[d,pool.index].rank(pct=True))*.5}
            t={a: {k:.2 for k in scores[a].sort_values(ascending=False,kind='stable').index[:4]} if risk.loc[d] else {}
               for a in scores}
        for a in t:
            ledgers[a].append(t[a])
    return schedule,ledgers


def benchmarks(dates,etf_adjusted,cfg,etf_nominal):
    kospi=timed(R0/'accepted/KR/^KS11/quote.csv').reindex(dates)
    kosdaq=timed(R0/'accepted/KR/^KQ11/quote.csv').reindex(dates)
    assert not kospi[['open','close']].isna().any().any() and not kosdaq[['open','close']].isna().any().any()
    level={'KOSPI':CAP*kospi.close/kospi.open.iloc[0],'KOSDAQ':CAP*kosdaq.close/kosdaq.open.iloc[0]}
    level['MIX_35_25']=(35*level['KOSPI']+25*level['KOSDAQ'])/60
    o=etf_nominal.loc[dates[0],'openPrice']
    proxy=etf_nominal['closePrice']*etf_nominal['volume']
    adv=proxy.rolling(20,min_periods=20).mean().shift(1).loc[dates[0]]
    n=min(int(CAP/o),int(adv*cfg['max_participation_of_d1_adv']/o))
    while n>0:
        impact=min(cfg['max_impact_bps'],cfg['impact_bps_at_1pct_adv']*math.sqrt(n*o/adv/.01))
        execution=o*(1+(cfg['half_spread_bps']+impact)/10000)
        fee=n*execution*cfg['buy_fee_bps']/10000
        cash=CAP-n*execution-fee
        if cash>=0:
            break
        n-=1
    assert n>0 and cash>=0
    level['KODEX200_NOMINAL_COST']=n*etf_nominal.closePrice.reindex(dates)+cash
    assert level['KODEX200_NOMINAL_COST'].notna().all()
    # Adjusted close is an indicative adjusted return, not an audited distribution ledger.
    level['KODEX200_ADJUSTED_PROXY']=CAP*etf_adjusted.close.reindex(dates)/etf_adjusted.open.loc[dates[0]]
    return level,{'shares':n,'buy_open':o,'modeled_fill':execution,'fee':fee,'residual_cash':cash,
                  'end_close':etf_nominal.closePrice.loc[dates[-1]],
                  'buy_benchmark_cost':n*(execution-o)+fee,'prior_adv20_krw':adv,
                  'prior_close_based_R2_KOSPI_pct':100*(kospi.close.iloc[-1]/timed(R0/'accepted/KR/^KS11/quote.csv').close.loc[:dates[0]].iloc[-2]-1)}


def regime_returns(daily, market, gate, regimes):
    paired=daily.notna()
    groups={}
    for label,category in [('state',regimes),('gate',gate.map({True:'ON',False:'OFF'}))]:
        groups[label]={}
        for k,sub in daily[paired].groupby(category):
            market_sub=market.reindex(sub.index)
            groups[label][k]={'n':len(sub),'compound_on_noncontiguous_dates_pct':100*((sub+1).prod()-1),
                               'market_same_dates_pct':100*((market_sub+1).prod()-1),
                               'mean_daily_bps':10000*sub.mean()}
    return groups


def main():
    historical=read(R2/'result.json')
    pre=read(R2/'preflight.json')
    c=read(R2/'collection_plan.json')
    config=read(ROOT/'config/task3_equity_contract.json')['execution_assumptions']
    for path,digest in read(R2/'artifact_manifest.json').items():
        assert sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    symbols=set(c['symbols'])
    assets={x['symbol']:x for x in read(R0/'native_manifest/assets.json') if x['symbol'] in symbols}
    assert len(assets)==60
    board={s:a['board'] for s,a in assets.items()}
    assert Counter(board.values())=={'KOSPI':35,'KOSDAQ':25}
    etf_adjusted=timed(ROOT/'runtime/task6/data/accepted/069500.KS.csv')
    grid=etf_adjusted.loc['2021-12-15':historical['ends']].index
    dates=grid[(grid>=historical['starts'])]
    assert len(dates)==historical['sessions']==669
    p,q,nom=stock_inputs(dict(sorted(assets.items())),grid,pre['sources'])
    adv=(p['close']*p['volume']).rolling(20,min_periods=20).mean().shift(1)
    risk=etf_adjusted.close.ge(etf_adjusted.close.rolling(63,min_periods=63).mean()).shift(1,fill_value=False).reindex(grid)
    x=pd.read_csv(R2/'normalized.csv.gz',parse_dates=['trade_date'],usecols=['symbol','trade_date','foreign_net_krw','institution_net_krw','total_krw','amount_valid'])
    def flow_column(field):
        temp=x.pivot(index='trade_date',columns='symbol',values=field).reindex(grid)
        valid=x.pivot(index='trade_date',columns='symbol',values='amount_valid').reindex(grid).eq(True)
        return temp.where(valid&q).rolling(5,min_periods=5).sum()
    flow=((flow_column('foreign_net_krw')+flow_column('institution_net_krw'))/flow_column('total_krw')).shift(1)
    schedule,ledgers=frozen_selection(p,dates,risk,flow)
    dates_report=pd.DataFrame({'date':sorted(schedule)})
    dates_report['scheduled_grid']=dates_report.date.isin(dates[::5])
    dates_report['risk_transition']=dates_report.date.map(risk.ne(risk.shift()).to_dict())
    dates_report.to_csv(OUT/'decision_dates.csv',index=False)
    records={}; tables={};daily={};caps={}
    for a in 'AB':
        records[a],tables[a],daily[a],caps[a],episodes=reconstruct(a,(p,q,nom,adv,board,assets),dates,schedule,risk,ledgers[a],config)
        tables[a].to_csv(OUT/f'{a}_independent_nav.csv')
        caps[a].to_csv(OUT/f'{a}_constraint_days.csv',index=False)
        episodes.to_csv(OUT/f'{a}_fifo_closed_lots.csv',index=False)
        assert np.isclose(records[a]['total_pct'],historical['results']['1'][a]['return_pct'],rtol=1e-12)
    etf_nominal=pd.DataFrame.from_dict(read(OUT/'etf_nominal.json'),orient='index')
    etf_nominal.index=pd.to_datetime(etf_nominal.index)
    etf_nominal=etf_nominal.sort_index().astype({k:float for k in ('openPrice','highPrice','lowPrice','closePrice','volume')})
    assert etf_nominal.index.is_unique and etf_nominal.currency.eq('KRW').all()
    assert etf_nominal.highPrice.ge(etf_nominal[['openPrice','closePrice']].max(axis=1)).all()
    assert etf_nominal.lowPrice.le(etf_nominal[['openPrice','closePrice']].min(axis=1)).all()
    nominal_ratio=(etf_nominal.closePrice/etf_adjusted.close).loc[dates]
    level,mkt=benchmarks(dates,etf_adjusted,config,etf_nominal)
    mkt['ETF_adjusted_to_nominal_ratio_start_end']=[1/float(nominal_ratio.iloc[i]) for i in [0,-1]]
    market=level['MIX_35_25'].div(level['MIX_35_25'].shift(1,fill_value=CAP))-1
    regimes=timed(R0/'KOSPI_regimes.csv').AS_OF_REGIME.reindex(grid).shift(1).reindex(dates)
    bench={}
    for key,v in level.items():
        ret=ratio_metrics(v)
        ret['avg_equity']=(float(((v-mkt['residual_cash'])/v).mean()) if key=='KODEX200_NOMINAL_COST' else 1.)
        bench[key]=ret
    for a in 'AB':
        rec=records[a]
        rec['comparisons_pp']={k:rec['total_pct']-b['total_pct'] for k,b in bench.items()}
        const=(1+market*rec['avg_equity']).cumprod()*CAP
        dynamic=market*tables[a].equity.shift(1,fill_value=0)
        pairs=pd.concat([daily[a].rename('strategy'),dynamic.rename('market')],axis=1).dropna()
        rec['fixed_mean_exposure_mix']=ratio_metrics(const)
        rec['equal_prior_exposure_paired']={
            'n_common_days':len(pairs),'mix_compound_pct_on_common_days':100*((1+pairs.market).prod()-1),
            'strategy_compound_pct_on_common_days':100*((1+pairs.strategy).prod()-1),
            'mean_daily_difference_bps':10000*(pairs.strategy-pairs.market).mean(),
        }
        rec['regime']=regime_returns(daily[a],market,risk,regimes)
    dates_df=pd.concat(level,axis=1)
    dates_df.to_csv(OUT/'benchmark_nav.csv')
    corporate={}
    for a in 'AB':
        counts=Counter()
        affected=[]
        stock_held=timed(R2/f'T1_{a}_nav.csv').holdings_json.map(json.loads)
        f=pd.read_csv(R2/f'T1_{a}_fills.csv',parse_dates=['date'])
        for s,instrument in assets.items():
            actions=read((ROOT/instrument['adjusted_path']).parent/'quality.json')['actions']
            for typ in ['splits','dividends']:
                for event in actions.get(typ,{}).values():
                    d=pd.to_datetime(event['date'],unit='s',utc=True).tz_convert('Asia/Seoul').tz_localize(None).normalize()
                    if d not in dates:
                        continue
                    counts[typ+'_in_universe']+=1
                    if stock_held[d].get(s,0) or (d!=dates[0] and stock_held.shift().loc[d].get(s,0)) or ((f.date==d)&(f.ticker==s)).any():
                        counts[typ+'_while_held_or_traded']+=1
                        affected.append({'date':str(d.date()),'symbol':s,'kind':typ})
        corporate[a]={'counts':dict(counts),'affected':affected}
    result={'audit_status':'BACKTEST_INVALID','scope':'strict four-name/80%-target strategy executability; bookkeeping and arithmetic benchmark outperformance reproducible',
            'starting_nav':CAP,'first_date':str(dates[0].date()),'last_date':str(dates[-1].date()),
            'decisions':len(schedule),'evaluation_days':len(dates),'history_days':977,
            'universe':dict(Counter(board.values())),'arms':records,'benchmark':bench,'benchmark_details':mkt,
            'corporate_action_coverage':corporate,'independent_target_and_schedule_match':True,
            'pipeline_isolation':'No strategy engine execution, existing R2 preserved'}
    with (OUT/'result.json').open('x') as handle:
        json.dump(result,handle,indent=2,ensure_ascii=False,allow_nan=False,default=np.generic.item)
        handle.write('\n')
    print({k:(v['total_pct'],v['mdd_pct']) for k,v in [*records.items(),*bench.items()]})


if __name__=='__main__':
    main()

"""One repaired historical replay against the existing sealed targets."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from experiments.task13_f1_r3.audit import ratio_metrics
from experiments.task13_f1_r4.execution import Account, trade_open, corporate_adjust
from experiments.task13_f1_r4.prices import ROOT, OUT, R2, RAW
from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec
from quant_harness.v87_actual_data_ingestion.engine import ProviderBatch, _validate_batch, _revision_audit

R0=ROOT/'runtime/task13_r0'
R3=ROOT/'runtime/task13_f1_r3'
CAP=10_000_000
LIMIT='2025-12-30'
ARMS=['T1_A','T1_B','T2_A','T2_B']


def load(p):
    return json.loads(p.read_bytes())


def sha(p):
    return sha256(p.read_bytes()).hexdigest()


def save(path,obj):
    with path.open('x') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,default=lambda v:v.item(),allow_nan=False)
        f.write('\n')


def dates_csv(path):
    f=pd.read_csv(path,parse_dates=['date']).set_index('date').sort_index()
    assert f.index.is_unique
    return f


def indices(files):
    return pd.DatetimeIndex(pd.read_csv(files,parse_dates=['date']).date)


def inputs():
    hashes={}
    def seal(p,expected=None):
        h=sha(p)
        if expected and h!=expected:
            raise ValueError(f'sealed source mismatch: {p}')
        hashes[str(p.relative_to(ROOT))]=h
        return h
    for f in [OUT/'repair_contract.json',Path(__file__),Path(__file__).with_name('execution.py'),
              R2/'contract.json',R2/'result.json',R3/'result.json',R3/'decision_dates.csv',R3/'benchmark_nav.csv',
              ROOT/'config/task3_equity_contract.json',ROOT/'config/task3_equity_price_contract.json',
              ROOT/'runtime/task6/data/accepted/069500.KS.csv',R2/'collection_plan.json',
              OUT/'nominal_source_receipts.json',OUT/'supplemental_krx_receipts.json']:
        seal(f)
    original=load(R2/'artifact_manifest.json')
    for a in ARMS:
        f=R2/(a+'_targets.csv')
        seal(f,original[str(f.relative_to(ROOT))])
    symbols=sorted(load(R2/'collection_plan.json')['symbols'])
    dates=indices(R2/'T1_A_targets.csv')
    assert len(dates)==669
    calendar=dates_csv(ROOT/'runtime/task6/data/accepted/069500.KS.csv').loc['2023-03-02':LIMIT].index
    assert calendar[calendar>=dates[0]].equals(dates)
    assets={r['symbol']:r for r in load(R0/'native_manifest/assets.json') if r['symbol'] in symbols}
    nominal, actions, gaps, flags, exclusions = {}, {}, {}, Counter(), {}
    cfg=load(ROOT/'config/task3_equity_price_contract.json')
    cfg['provider_contract'].update(required_source_tag='KIWOOM_REGULAR_NOMINAL',canonical_price_scale='NOMINAL_KRW')
    cross={}; toss={}
    sources=load(OUT/'nominal_source_receipts.json')+load(OUT/'supplemental_krx_receipts.json')
    for r in sources:
        if 'file' not in r:
            continue
        p=OUT/r['file']
        seal(p,r['sha256'])
        if r['source']=='KRX':
            for row in load(p)['OutBlock_1']:
                cross[(r['date'],row['ISU_CD'])]=row
        else:
            for row in load(p)['result']['candles']:
                toss[(row['timestamp'][:10].replace('-',''),r['symbol'])]=row
    cross_stats=Counter()
    scoped_differences=[]
    for s in symbols:
        code=s[:6]
        pages=sorted(RAW.glob(f'ka11081_{code}_[0-9].json'))
        rows=[]; dated_actions={}
        qf=ROOT/assets[s]['adjusted_path']
        seal(qf,assets[s]['adjusted_hash'])
        quality_path=qf.parent/'quality.json'
        seal(quality_path)
        quality=load(quality_path)
        splits={pd.to_datetime(e['date'],unit='s',utc=True).tz_convert('Asia/Seoul').strftime('%Y%m%d'):
                e['numerator']/e['denominator'] for e in quality['actions'].get('splits',{}).values()}
        base={}
        for p in pages:
            receipt_path=p.with_suffix('.receipt.json')
            seal(receipt_path)
            receipt=load(receipt_path)
            seal(p,receipt['sha256'])
            assert receipt['query']['upd_stkpc_tp']=='0' and receipt['tr']=='ka11081'
            b=load(p)
            assert b['stk_cd']==code
            for r in b['result_list']:
                d=r['dt']
                if not ('20230302'<=d<='20251230'):
                    continue
                assert d not in base
                base[d]=r
                rows.append({'date':pd.Timestamp(d).strftime('%Y-%m-%d'),'ticker':code,
                             'open':int(r['open_pric']),'high':int(r['high_pric']),'low':int(r['low_pric']),
                             'close':int(r['cur_prc']),'volume':int(r['trde_qty']),'value_approx':int(r['trde_prica'])*1_000_000})
                f=set(filter(None,r['upd_stkpc_tp'].split(',')))
                if d>='20230403' and (f or d in splits):
                    flags.update(f)
                    noncash=f-{'4'}
                    if noncash or d in splits:
                        ratio=splits.get(d)
                        broker_ratio=(1+float(r['upd_rt'])/100) if r['upd_rt'] else None
                        verified=noncash in ({'8'},{'16'}) and ratio and broker_ratio and abs(broker_ratio*ratio-1)<.0002
                        dated_actions[pd.Timestamp(d)]={'flags':sorted(f),'ratio':float(ratio) if verified else None}
        frame=_validate_batch(ProviderBatch('KIWOOM',code,tuple(rows),False,'KIWOOM_REGULAR_NOMINAL',
                                            receipt['at'],{}),cfg).set_index('date')
        frame.index=pd.to_datetime(frame.index)
        if len(calendar.difference(frame.index)) or len(frame.index.difference(calendar)):
            gaps[s]=[str(d.date()) for d in calendar.difference(frame.index)]
            continue
        listing=pd.Timestamp(max(assets[s]['list_date_toss'],assets[s]['list_date_kind']))
        frame['listing_eligible']=frame.index>=listing
        exclusions[s]=int((~frame.listing_eligible).sum())
        nominal[s]=frame
        actions[s]=dated_actions
        references=[]
        for (d,c),row in cross.items():
            if c!=code or d not in base:
                continue
            x=base[d]
            want=[int(row[k]) for k in ['TDD_OPNPRC','TDD_HGPRC','TDD_LWPRC','TDD_CLSPRC','ACC_TRDVOL']]
            got=[int(x[k]) for k in ['open_pric','high_pric','low_pric','cur_prc','trde_qty']]
            if want!=got:
                raise ValueError(f'KRX nominal mismatch {s}: {d}')
            references.append({'ticker':code,'date':pd.Timestamp(d).strftime('%Y-%m-%d'),'close':want[3]})
            cross_stats['KRX_exact_OHLCV']+=1
        for (d,c),row in toss.items():
            if c==code and d in base:
                x=base[d]
                want=[int(row[k]) for k in ['openPrice','highPrice','lowPrice','closePrice','volume']]
                got=[int(x[k]) for k in ['open_pric','high_pric','low_pric','cur_prc','trde_qty']]
                cross_stats['Toss_exact_OHLCV' if want==got else 'Toss_OHLCV_difference']+=1
                if want!=got:
                    official=cross.get((d,c))
                    if not official or got!=[int(official[k]) for k in ['TDD_OPNPRC','TDD_HGPRC','TDD_LWPRC','TDD_CLSPRC','ACC_TRDVOL']]:
                        raise ValueError(f'Toss nominal difference without official KRX confirmation {s}: {d}')
                    scoped_differences.append({'symbol':s,'date':d,'field_order':'OHLCV','Toss':want,'Kiwoom_and_KRX':got})
        if not {'20230403','20240122','20250919','20251230'} <= {x['date'].replace('-','') for x in references}:
            raise ValueError(f'KRX sample missing: {s}')
        # Existing V87 revisions contract applied to the immutable independently observed checkpoints.
        reference=OUT/'krx_revision_reference.csv'
        pd.DataFrame(references).to_csv(reference,index=False)
        checked=_revision_audit(frame.reset_index().assign(date=lambda p:p.date.dt.strftime('%Y-%m-%d')),reference,cfg)
        if not checked['passed']:
            raise ValueError(f'V87 official reference mismatch {s}: {checked}')
    if gaps:
        save(OUT/'price_gaps.json',gaps)
        raise ValueError('nominal stock-date coverage incomplete')
    capture={'hashes':hashes,'calendar_days':len(calendar),'evaluation_days':len(dates),'universe':len(symbols),
             'KRX_cross':dict(cross_stats),'Toss_differences':scoped_differences,'corporate_flags':dict(flags),
             'zero_volume_reference_rows':sum(int(f.loc[dates].volume.eq(0).sum()) for f in nominal.values()),
             'corporate_actions':{s:{str(d.date()):v for d,v in rows.items()} for s,rows in actions.items() if rows},
             'pre_current_documented_listing_boundary':{s:n for s,n in exclusions.items() if n}}
    return dates,nominal,actions,capture


def simulate(name, dates, nominal, actions, risk, decisions, spec):
    targets=dates_csv(R2/(name+'_targets.csv')).target_weights_json.map(json.loads)
    open_=pd.DataFrame({s:f.open.where(f.volume.gt(0)&f.listing_eligible) for s,f in nominal.items()})
    close=pd.DataFrame({s:f.close.where(f.listing_eligible) for s,f in nominal.items()})
    adv=pd.DataFrame({s:(f.close*f.volume).rolling(20,min_periods=20).mean().shift(1) for s,f in nominal.items()})
    prior=close.shift(1)
    account=Account(CAP)
    ledger=[]; trades=[]; exceptions=[]; cashflows=[]; gain=defaultdict(float); marks={}
    days=Counter()
    for d in dates:
        op=open_.loc[d].to_dict()
        previous=prior.loc[d].to_dict()
        end=close.loc[d].to_dict()
        for s,changes in actions.items():
            if d not in changes:
                continue
            record=changes[d]
            ratio=record['ratio']
            if ratio is None:
                if s in account.positions:
                    raise ValueError(f'unresolved corporate action on held name {name} {s} {d}: {record}')
                op[s]=None
                exceptions.append({'date':d,'symbol':s,'reason':'UNRESOLVED_ACTION_NO_TRADE_FLAT'})
            else:
                if s in account.positions:
                    corporate_adjust(account,s,float(ratio))
                    marks[s]/=ratio
                    exceptions.append({'date':d,'symbol':s,'reason':'VERIFIED_SPLIT','quantity':account.positions[s]})
                previous[s]/=ratio
        starting=dict(account.positions)
        tx,es,before=trade_open(account,targets.loc[d],previous,op,adv.loc[d].to_dict(),spec,
                                 rebalance=d in decisions,risk_on=bool(risk.loc[d]))
        if any(t['side']=='BUY' for t in tx):
            opening=sum(q*op[s] for s,q in account.positions.items())
            if len(account.positions)>4 or opening>.8*(account.cash+opening)+1e-6 or not risk.loc[d]:
                raise ValueError(f'portfolio risk invariant {name} {d}')
        if any(not np.isfinite(end[s]) for s in set(starting)|set(account.positions)):
            raise ValueError(f'missing nominal close while held {name} {d}')
        for s,count in starting.items():
            gain[s]+=count*(end[s]-marks[s])
        for t in tx:
            sign=1 if t['side']=='BUY' else -1
            s=t['symbol']
            gain[s]+=sign*t['quantity']*(end[s]-t['fill_price'])-t['fee']
        marks.update({s:end[s] for s in account.positions})
        stock=sum(n*end[s] for s,n in account.positions.items())
        total=account.cash+stock
        if not np.isfinite(total) or total<=0:
            raise ValueError(f'invalid NAV {name} {d}')
        nav_check=CAP+sum(gain.values())
        assert abs(nav_check-total)<1e-5
        references=[s for s in account.positions if nominal[s].loc[d,'volume']==0]
        if references:
            days['reference_mark_days']+=1
        if before is not None and before>.8:
            days['pretrade_drift_over80_days']+=1
        if len(account.positions)>4:
            raise ValueError(f'actual holding count breach {name} {d}')
        ledger.append({'date':d,'nav':total,'cash':account.cash,'equity':stock/total,
                       'number_held':len(account.positions),'positions_json':json.dumps(account.positions,sort_keys=True),
                       'sell_residual_target_json':json.dumps(account.pending_sells,sort_keys=True),
                       'reference_marks_json':json.dumps(references),'risk_on':bool(risk.loc[d])})
        trades.extend({'date':d,**t} for t in tx)
        exceptions.extend({'date':d,**e} for e in es)
    df=pd.DataFrame(ledger).set_index('date')
    fills=pd.DataFrame(trades)
    intents=pd.DataFrame(exceptions)
    m=ratio_metrics(df.nav)
    ordered=sorted(gain.items(),key=lambda r:-r[1])
    pos=sum(v for _,v in ordered if v>0)
    ret=df.nav/df.nav.shift(1,fill_value=CAP)-1
    m.update(max_names=int(df.number_held.max()),nominal_nav_sessions=len(df),close_over80_days=int(df.equity.gt(.8).sum()),
             max_close_exposure=float(df.equity.max()),opens_with_buy_cap_breach=0,
             risk_off_buy_breaches=0,min_cash=float(df.cash.min()),mean_equity=float(df.equity.mean()),
             fills=len(fills),pending_sell_events=int(intents.reason.eq('SELL_REMAINDER').sum()),
             pending_sell_eod_days=int(df.sell_residual_target_json.ne('{}').sum()),
             expected_risk_off_residual_days=int((~df.risk_on&df.number_held.gt(0)).sum()),
             trading_cost=float(fills.fee.sum()+(fills['quantity']*(fills.fill_price-fills.reference_open).abs()).sum()),
             turnover_multiple=float(fills.open_notional.sum()/CAP),source_reference_marks=dict(days),
             annual_pct={str(y):float(100*((1+r).prod()-1)) for y,r in ret.groupby(ret.index.year)},
             top_five_positive_fraction=float(sum(v for _,v in ordered[:5])/pos) if pos else None,
             pnl_by_symbol=dict(ordered))
    return m,df,fills,intents


def main():
    dates,nominal,actions,evidence=inputs()
    if sys.argv[1]=='preflight':
        save(OUT/'price_gate.json',evidence)
        print({k:v for k,v in evidence.items() if k not in ('hashes','corporate_actions')})
        return
    gate=load(OUT/'price_gate.json')
    if gate!=evidence:
        raise ValueError('price gate or implementation changed')
    decisions=set(indices(R3/'decision_dates.csv'))
    assert len(decisions)==168
    proxy=dates_csv(ROOT/'runtime/task6/data/accepted/069500.KS.csv').close
    risk=proxy.ge(proxy.rolling(63,min_periods=63).mean()).shift(1,fill_value=False).reindex(dates)
    costs=load(ROOT/'config/task3_equity_contract.json')['execution_assumptions']
    spec=ExecutionSpec(**{k:v for k,v in costs.items() if k!='minimum_order_nav_fraction'},
                       minimum_order_notional_krw=CAP*costs['minimum_order_nav_fraction'])
    save(OUT/'reservation.json',{'price_gate_sha256':sha(OUT/'price_gate.json'),'type':'one R4 repaired replay'})
    materialized={a:simulate(a,dates,nominal,actions,risk,decisions,spec) for a in ARMS}
    bench=dates_csv(R3/'benchmark_nav.csv').loc[dates]
    assert bench.index.equals(dates) and not bench.isna().any().any()
    benchmark={k:ratio_metrics(bench[k]) for k in bench if k!='KODEX200_ADJUSTED_PROXY'}
    mix=bench.MIX_35_25
    bm_ret=mix/mix.shift(1,fill_value=CAP)-1
    result={}
    for a,(m,df,fills,intents) in materialized.items():
        df.to_csv(OUT/f'{a}_nav.csv')
        fills.to_csv(OUT/f'{a}_fills.csv',index=False)
        intents.to_csv(OUT/f'{a}_events.csv',index=False)
        m.update(fixed_same_mean_equity_mix_pct=float(100*((1+bm_ret*m['mean_equity']).prod()-1)),
                 prior_equity_matched_mix_pct=float(100*((1+bm_ret*df.equity.shift(1,fill_value=0)).prod()-1)),
                 index_excess_pp={k:m['total_pct']-v['total_pct'] for k,v in benchmark.items()})
        result[a]=m
    diffs={t:result[t+'_B']['total_pct']-result[t+'_A']['total_pct'] for t in ['T1','T2']}
    from experiments.task14.stats_eval import block_mean
    intervals={}
    for t in ['T1','T2']:
        a=materialized[t+'_A'][1].nav
        b=materialized[t+'_B'][1].nav
        intervals[t]=block_mean(b/b.shift(1,fill_value=CAP)-a/a.shift(1,fill_value=CAP),20)
    save(OUT/'result.json',{'execution':'EXECUTION_REPAIRED',
        'mom63_market':'HISTORICAL_OUTPERFORMANCE_ONLY' if all(result['T1_A']['index_excess_pp'][k]>0 for k in benchmark)
        else 'MIXED_BENCHMARK_RESULTS','flow5':'NO_INCREMENTAL_EVIDENCE' if diffs['T1']<=0 or intervals['T1']['CI95'][0]<=0
        else 'POSITIVE_HISTORICAL_ESTIMATE','evaluation_type':'HISTORICAL_REPAIR_AFTER_EXPOSURE',
        'arms':result,'models_net_difference_pp':diffs,'paired_daily_uncertainty':intervals,'benchmarks':benchmark})
    print({a:round(r['total_pct'],4) for a,r in result.items()})


if __name__=='__main__':
    main()

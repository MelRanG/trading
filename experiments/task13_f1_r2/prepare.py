"""Normalize sealed Kiwoom observations and build lagged inputs without H5 labels."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from experiments.task13_f1_r2.collect import ROOT, OUT, RAW, ASSETS, FIELDS, sha, save

INDEX=ROOT/'runtime/task13_r0/accepted/KR/^KS11/quote.csv'
ETF=ROOT/'runtime/task6/data/accepted/069500.KS.csv'
SCORE_CONTROLS=['MOM63','MOM20','REV5','LOWVOL20']
POLICY=ROOT/'experiments/task10/contract.json'
COST=ROOT/'config/task3_equity_contract.json'
REGIME=ROOT/'runtime/task13_r0/KOSPI_regimes.csv'


def frame(path):
    f=pd.read_csv(path, parse_dates=['date']).set_index('date').sort_index()
    if not f.index.is_unique:
        raise ValueError(f'duplicate date: {path}')
    return f


def main():
    sources = {}
    def digest(p,expected=None):
        h=sha(p.read_bytes())
        if expected is not None and h!=expected:
            raise ValueError(f'input mismatch: {p}')
        sources[str(p.relative_to(ROOT))]=h
        return h

    for p in [INDEX,ETF,POLICY,COST,REGIME,Path(__file__),OUT/'contract.json',OUT/'collection_plan.json',
              OUT/'pilot.json',OUT/'collection.json',ROOT/'experiments/task13_f1_r2/evaluate.py',
              ROOT/'experiments/task14/stats_eval.py',ROOT/'src/quant_harness/investment/research.py']:
        digest(p)
    plan=json.loads((OUT/'collection_plan.json').read_bytes())
    digest(ASSETS,plan['assets_sha256'])
    assets={a['symbol']:a for a in json.loads(ASSETS.read_bytes())}
    etf=frame(ETF).close.loc['2021-12-15':'2025-12-30']
    calendar=etf.index
    for exchange in [INDEX, ROOT/'runtime/task13_r0/accepted/KR/^KQ11/quote.csv']:
        digest(exchange)
        idx=frame(exchange).loc['2021-12-15':'2025-12-30'].index
        if len(idx.difference(calendar)) or len(calendar[calendar >= '2023-04-03'].difference(idx)):
            raise ValueError('ETF and market calendar conflict in evaluation')
    if (etf.isna() | etf.le(0)).any():
        raise ValueError('missing Task10 KODEX 200 benchmark observations')
    stocks=sorted(plan['symbols'])
    panels={field:{} for field in ['open','close','volume','eligible','foreign','institution','value']}
    stats={}
    normalized=[]
    for symbol in stocks:
        a=assets[symbol]
        for kind in ['adjusted','eligibility']:
            digest(ROOT/a[kind+'_path'],a[kind+'_hash'])
        prices=frame(ROOT/a['adjusted_path']).reindex(calendar)
        mask=frame(ROOT/a['eligibility_path']).eligible.reindex(calendar).eq(True)
        for k in ['open','close','volume']:
            panels[k][symbol]=prices[k]
        panels['eligible'][symbol]=mask
        rows=[]
        for f in sorted(RAW.glob(symbol[:6]+'_history_*.json')):
            if f.name.endswith('.receipt.json'):
                continue
            meta=f.with_suffix('.receipt.json')
            digest(meta)
            receipt=json.loads(meta.read_bytes())
            digest(f,receipt['sha256'])
            if receipt['symbol']!=symbol or receipt['market_scope']!='KRX' or receipt['unit']!='million KRW':
                raise ValueError(f'bad receipt: {f}')
            for r in json.loads(f.read_bytes())['stk_invsr_orgn']:
                date=r['dt']
                if not(plan['start']<=date<=plan['end']):
                    continue
                try:
                    foreign,org,total=(int(r[k])*1_000_000 for k in FIELDS)
                except (KeyError,TypeError,ValueError):
                    foreign=org=total=None
                valid=total is not None and total>0 and abs(foreign)+0<=total and abs(org)<=total and abs(foreign+org)<=total
                # Keep raw and output quarantine distinct.
                timestamp=pd.Timestamp(date)
                rows.append((timestamp,foreign if valid else None,org if valid else None,total if valid else None))
                normalized.append((symbol,timestamp,foreign,org,total,valid,receipt['received_at'],receipt['sha256']))
        flows=pd.DataFrame(rows,columns=['date','foreign','institution','value']).set_index('date')
        if not flows.index.is_unique:
            raise ValueError(f'duplicate source date: {symbol}')
        if len(flows.index.difference(calendar)):
            raise ValueError(f'non-session source date: {symbol}')
        k=flows.reindex(calendar).where(mask,axis=0)
        for col in ['foreign','institution','value']:
            panels[col][symbol]=k[col]
        stats[symbol]={'source_rows':len(flows),'bad_amount_rows':int(flows.value.isna().sum()),
                       'common_rows':int(k.value.notna().sum()),'price_mask_reason_rows':int((flows.value.notna()&~mask.reindex(flows.index)).sum())}
    p={k:pd.DataFrame(d,index=calendar) for k,d in panels.items()}
    ratio=(p['foreign']+p['institution']).rolling(5,min_periods=5).sum()/p['value'].rolling(5,min_periods=5).sum()
    close=p['close'].where(p['eligible'])
    ret=close.pct_change(fill_method=None)
    def change(h):
        return (close/close.shift(h)-1).where(close.rolling(h+1,min_periods=h+1).count().eq(h+1))
    trailing={'MOM63':change(63),'MOM20':change(20),'REV5':-change(5),
              'LOWVOL20':-ret.rolling(20,min_periods=20).std()}
    flow={lag:ratio.shift(lag) for lag in [1,2]}
    precheck={}
    for lag in [1,2]:
        common=flow[lag].notna() & trailing['MOM63'].shift(1).notna()
        overlap=flow[lag].where(common).rank(axis=1).corrwith(trailing['MOM63'].shift(1).where(common).rank(axis=1),axis=1)
        scoped=common.loc['2023-04-03':]
        precheck[lag]={'sessions':len(scoped),'min_common_names':int(scoped.sum(axis=1).min()),
                       'median_common_names':float(scoped.sum(axis=1).median()),
                       'eligible_dates_min12':int(scoped.sum(axis=1).ge(12).sum()),
                       'median_cross_sectional_sd':float(flow[lag].where(common).std(axis=1).loc['2023-04-03':].median()),
                       'mean_rank_overlap_mom63':float(overlap.loc['2023-04-03':].mean())}
    out=pd.DataFrame(normalized,columns=['symbol','trade_date','foreign_net_krw','institution_net_krw','total_krw','amount_valid','retrieved_at','source_sha256'])
    out['market_scope']='KRX'
    out['source']='KIWOOM ka10059'
    out['revision_status']='UNVERIFIED_HISTORICAL_FIRST_VERSION'
    out.to_csv(OUT/'normalized.csv.gz',index=False)
    # Both inputs preserve full session indices. No H5 labels are materialized.
    payload={'panel':p,'prior':{k:v.shift(1) for k,v in trailing.items()},'flow':flow,'ETF':etf,
             'regimes':frame(REGIME).AS_OF_REGIME.shift(1).reindex(calendar)}
    pd.to_pickle(payload,OUT/'inputs.pkl')
    digest(OUT/'inputs.pkl')
    digest(OUT/'normalized.csv.gz')
    pre=OUT/'preflight.json'
    save(pre,{'status':'PASS_HISTORICAL_ONLY','stats':stats,'precheck':precheck,'sources':sources})
    if not all(x['eligible_dates_min12']>=60 for x in precheck.values()):
        raise RuntimeError('insufficient date-level common data for this research')
    print(precheck,flush=True)


if __name__=='__main__':
    main()

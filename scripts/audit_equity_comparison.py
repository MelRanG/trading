"""Independent NAV and regime diagnostics from frozen collected stock inputs."""
from pathlib import Path
import argparse,json,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.equities import normalize_chart,settings
from quant_harness.investment.research import digest


def source_frame(directory,receipt):
    symbol=receipt['symbol']
    if receipt.get('source')=='TOSS_ADJUSTED_EQUITY':
        f=pd.read_csv(directory/'toss_stocks'/(symbol.split('.')[0]+'.reference.csv'))
        f['date']=pd.to_datetime(f.date);return f.set_index('date')
    if receipt.get('source')=='TOSS_KOSPI_INDEX':
        f=pd.DataFrame(json.loads((directory/'toss_index'/(receipt['source_hash']+'.json')).read_text()))
        f['date']=pd.to_datetime(f.timestamp,utc=True).dt.tz_convert('Asia/Seoul').dt.tz_localize(None).dt.normalize()
        return f.drop_duplicates('date').set_index('date').sort_index()
    payload=json.loads((directory/'prices'/(receipt['source_hash']+'.raw')).read_text())
    f,_=normalize_chart(payload,symbol)
    zone='Asia/Seoul' if symbol.endswith('.KS') or symbol=='^KS11' else 'America/New_York'
    f['date']=pd.to_datetime(f.timestamp,utc=True).dt.tz_convert(zone).dt.tz_localize(None).dt.normalize()
    return f.set_index('date').sort_index()


def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();directory=a.directory
    cycle=json.loads((directory/'cycle_result.json').read_text());comparison=cycle['comparison'];market=cycle['market'];cfg=settings(ROOT)
    receipts={r['symbol']:r for r in cycle['price_receipts'] if r['status']=='SAVED'}
    frames={s:source_frame(directory,r) for s,r in receipts.items()}
    index=frames[cfg[market]['index']].close.astype(float)
    regime=(index>index.rolling(120,min_periods=120).mean()).shift(1)
    volatility=index.pct_change(fill_method=None).rolling(21,min_periods=21).std().shift(1)
    elevated=volatility>volatility.expanding(min_periods=120).median().shift(1)
    results={}
    for name,result in comparison['results'].items():
        nav=pd.read_csv(directory/'comparison'/(name+'_nav.csv'),parse_dates=['date']).set_index('date').nav
        fills=pd.read_csv(directory/'comparison'/(name+'_fills.csv'),parse_dates=['date'])
        cash=float(cfg[market]['initial_capital']);held={};rebuilt=[]
        for day in nav.index:
            for row in fills[fills.date.eq(day)].to_dict('records'):
                quantity=row['quantity'];symbol=row['ticker'];side=row['side']
                cash+=-(quantity*row['fill_price_krw']+row['fee_krw']) if side=='BUY' else quantity*row['fill_price_krw']-row['fee_krw']
                held[symbol]=held.get(symbol,0)+(quantity if side=='BUY' else -quantity)
            value=cash+sum(q*float(frames[s].loc[day,'close']) for s,q in held.items() if q)
            rebuilt.append(value)
        error=float(np.max(np.abs(np.asarray(rebuilt)-nav.to_numpy())))
        tolerance=0.000001 if market=='US' else 0.01
        daily=nav.pct_change().fillna(nav.iloc[0]/cfg[market]['initial_capital']-1)
        groups={}
        for label,mask in [('trend_on',regime.eq(True)),('trend_off',regime.eq(False)),('high_vol',elevated.eq(True)),('lower_vol',elevated.eq(False))]:
            subset=daily[mask.reindex(daily.index,fill_value=False)]
            groups[label]={'sessions':len(subset),'mean_daily_return_bps':float(subset.mean()*10000) if len(subset) else None}
        normalized=fills.rename(columns={'reference_open_krw':'reference_price','fill_price_krw':'fill_price','fee_krw':'fee','half_spread_cost_krw':'half_spread_cost','impact_cost_krw':'impact_cost'})
        normalized['currency']=cfg[market]['currency'];normalized.to_csv(directory/'comparison'/(name+'_fills_currency.csv'),index=False)
        results[name]={'independent_nav_max_abs_error':error,'currency':cfg[market]['currency'],'reconstruction_passed':error<=tolerance,'regimes':groups}
    from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec,_buy_fill_terms
    assumptions=cfg['US_execution_assumptions'] if market=='US' else cfg['execution_assumptions']
    initial=cfg[market]['initial_capital']
    spec=ExecutionSpec(**{k:v for k,v in assumptions.items() if k!='minimum_order_nav_fraction'},minimum_order_notional_krw=initial*assumptions['minimum_order_nav_fraction'])
    benchmark=frames[cfg[market]['benchmark']]
    start,end=pd.Timestamp(comparison['start']),pd.Timestamp(comparison['end'])
    raw=float(benchmark.loc[start,'open']);adv=float(benchmark.value_approx.rolling(20,min_periods=20).mean().shift(1).loc[start])
    benchmarks={}
    for fraction in (1.0,0.8):
        quantity,impact,price,fee,_=_buy_fill_terms(cash=initial*fraction,max_quantity=min(int(initial*fraction/raw),int(adv*spec.max_participation_of_d1_adv/raw)),raw_open=raw,adv=adv,spec=spec)
        cash=initial-quantity*price-fee
        values=cash+quantity*benchmark.loc[start:end,'close'].astype(float)
        path=pd.concat([pd.Series([float(initial)],index=[start-pd.Timedelta(days=1)]),values])
        returns=path.pct_change().dropna()
        benchmarks[str(fraction)]={'symbol':cfg[market]['benchmark'],'target_initial_exposure':fraction,'return_pct':float((values.iloc[-1]/initial-1)*100),
          'mdd_pct':float((path/path.cummax()-1).min()*100),'sharpe':float(returns.mean()/returns.std(ddof=0)*np.sqrt(252)),
          'initial_execution_cost':float(fee+quantity*(price-raw)),'currency':cfg[market]['currency'],'execution_authority':'BENCHMARK_SIMULATION_ONLY'}
    audit={'net_buy_hold_benchmarks':benchmarks,'source_comparison_hash':digest(comparison),'market':market,'results':results,
           'equal_weight_definition':'First four seed symbols, 20% each, daily rebalance; not a diversified all-stock market portfolio.',
           'benchmark_caveat':'Index and ETF are gross reference series; strategy returns include registered research costs. ETF reference is not traded by this pipeline.',
           'regime_status':'Post-run diagnostic only; not used to select/tune parameters or activate strategies.'}
    (directory/'comparison'/'independent_audit.json').write_text(json.dumps(audit,indent=2,allow_nan=False))
    if not all(r['reconstruction_passed'] for r in results.values()):raise ValueError('NAV reconstruction failed')
    print(market,'independent NAV reconstructed for',len(results),'strategies')

if __name__=='__main__':main()

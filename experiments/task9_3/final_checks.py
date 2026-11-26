from common import *
import pandas as pd,numpy as np
from evaluate import load_panel
checks=[];points=[]
for market in ['US','KR']:
 names=[c['symbol'] for c in json.loads((B/'decisions'/market/'2026-05-15.json').read_text())['cases']];panel,dates,bench=load_panel(market,names);f=B/'evaluation'/market;capital=C['capital'][market]
 for arm in ['POLICY','SELECTION_EQUAL90','INITIAL_SELECTION_HOLD90','MOM63_POSITIVE90']:
  a=pd.read_csv(f/(arm+'_nav.csv'));fills=pd.read_csv(f/(arm+'_fills.csv'));assert not fills.client_order_id.duplicated().any();cash=capital;held={};na=0
  for r in a.to_dict('records'):
   for q in fills[fills.date==r['date']].to_dict('records'):
    assert not str(q['ticker']).startswith('^');assert abs(q['reference_open_krw']-panel['open'].loc[q['date'],q['ticker']])<1e-5
    side=1 if q['side']=='BUY' else -1;held[q['ticker']]=held.get(q['ticker'],0)+side*q['quantity'];cash-=side*q['quantity']*q['fill_price_krw']+q['fee_krw']
    if arm=='POLICY' and side>0:
     d=sorted(p for p in (B/'decisions'/market).glob('*.json') if p.stem<q['date'])[-1];c=next(x for x in json.loads(d.read_text())['cases'] if x['symbol']==q['ticker']);assert c['state']=='INVESTABLE' and c['weight']>0
   assert abs(cash-r['cash_krw'])<.01;assert {s:int(q) for s,q in held.items() if q}=={s:q for s,q in json.loads(r['holdings_json']).items() if q};assert cash>=-1e-6 and all(q>=0 for q in held.values())
   value=cash+sum(q*panel['close'].loc[r['date'],s] for s,q in held.items() if q)
   if not np.isfinite(value):assert not np.isfinite(r['nav_krw']);na+=1
   else:assert abs(value-r['nav_krw'])<.02
  result=next(x for x in json.loads((f/'results.json').read_text()) if x['arm']==arm);assert abs(sum(result['contribution_per_initial_capital'].values())-result['net_price_return'])<1e-9;assert result['unpriced_held_days']==na
  if na:assert result['mdd_close'] is None and result['annualized_sharpe'] is None
  for label,d in [('3calendar_months_after_first_entry','2026-08-18'),('TASK_END_APPROX_6_MONTHS','2026-11-13')]:
   r=a[a.date>=d].iloc[0];points.append({'market':market,'arm':arm,'checkpoint':label,'date':r.date,'nav':float(r.nav_krw) if np.isfinite(r.nav_krw) else None,'net_return':float(r.nav_krw/capital-1) if np.isfinite(r.nav_krw) else None,'benchmark_return':float(bench.loc[r.date,'close']/bench.loc[dates[0],'open']-1)})
  checks.append({'market':market,'arm':arm,'cash_position_nav_reconciled_days':len(a)-na,'missing_nav_explicit':na,'fills_verified':len(fills),'unique_client_order_ids':True,'no_benchmark_orders':True,'policy_buys_presealed_eligible':True if arm=='POLICY' else 'NOT_AI_POLICY'})
rs=[json.loads(p.read_text()) for p in (B/'model_calls/research').glob('*.reserved.json')];assert len(rs)<=16 and all(x['status']=='SUCCEEDED' for x in rs);assert sum(x['measured_tokens'] for x in rs)<=1000000
freeze(B/'ledger_reconciliation.json',checks);freeze(B/'checkpoints.json',points);print('ACCOUNTS_RECONCILED',len(checks),'TRADES',sum(r['fills_verified'] for r in checks),'LLM',len(rs),sum(x['measured_tokens'] for x in rs))

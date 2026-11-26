"""Sequential targets into EXISTING V77 shared Paper replay. No model selection here."""
from common import *
import pandas as pd,numpy as np,math
from quant_harness.investment.research import replay_targets
from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec

def load_panel(m,names):
 index='^GSPC' if m=='US' else '^KS11';bench=pd.read_csv(B/'evaluator_only'/index/'bars.csv').set_index('date');dates=sorted(d for d in bench.index if '2026-05-18'<=d<=C['end']);frames={}
 for s in names:
  initial=pd.read_csv(B/'screen_inputs'/s/'bars.csv');f=B/'evaluator_only'/s;later=pd.read_csv(f/('bars_v2.csv' if m=='KR' else 'bars.csv'));df=pd.concat([initial[initial.date<'2026-05-15'],later]).drop_duplicates('date').sort_values('date').set_index('date');frames[s]=df
 all_days=sorted(set(['2026-05-15']+dates));panel={k:pd.DataFrame({s:df[k].reindex(all_days) for s,df in frames.items()}) for k in ['open','close']};panel['adv20_d1']=pd.DataFrame({s:(df.close*df.volume).rolling(20,min_periods=20).mean().shift(1).reindex(all_days) for s,df in frames.items()});return panel,dates,bench

def plan(m,arm,decisions,panel,dates,spec):
 initial=C['capital'][m];current={};ledger=[];rebalance=set();events=[];entry={};held={};cash=initial;last_replay_fills=0;pending=None;prior_decision=None
 schedule={next(d for d in dates if d>x['asof']):x for x in decisions if x['asof']<dates[-1]};initial_names=decisions[0]['selection_top3'];last_selection=None
 for i,day in enumerate(dates):
  reasons=[]
  if day in schedule:
   dec=schedule[day];prior_decision=dec
   if arm=='POLICY':target={c['symbol']:float(c['weight']) for c in dec['cases'] if c['weight']>0}
   elif arm=='SELECTION_EQUAL90':target={s:.3 for s in dec['selection_top3']}
   elif arm=='INITIAL_SELECTION_HOLD90':target={s:.3 for s in initial_names} if i==0 else None
   else:
    rows=json.loads((B/'packets'/m/(dec['asof']+'.json')).read_text())['cases'];chosen=[c['symbol'] for c in sorted(rows,key=lambda c:(-c['momentum63'],c['symbol'])) if c['momentum63']>0][:3];target={s:.3 for s in chosen}
   if target is not None:
    pending=None
    # This is a PRESEALED conditional limit, not discretionary use of future open.
    if arm=='POLICY':
     for c in dec['cases']:
      s=c['symbol'];ceiling=c.get('entry_price_ceiling')
      if s in target and not held.get(s) and ceiling is not None and float(panel['open'].loc[day,s])>float(ceiling):
       target.pop(s);reasons.append({'symbol':s,'reason':'PRESEALED_ENTRY_CEILING_NOT_MET','ceiling':ceiling})
    current=target;rebalance.add(day);reasons.append({'reason':'NEXT_SESSION_FROM_SEALED_RESEARCH','decision_asof':dec['asof'],'decision_hash':digest(dec),'targets':target})
  elif pending is not None and arm=='POLICY':
   current={s:w for s,w in current.items() if s not in pending};rebalance.add(day);reasons.append({'reason':'PREVIOUS_CLOSE_STOP_NEXT_OPEN','symbols':pending});pending=None
  ledger.append({'date':day,'target_weights_json':json.dumps(current,sort_keys=True)})
  if day in rebalance:
   a,f,intents=replay_targets(panel,dates[:i+1],pd.DataFrame(ledger),initial,spec,rebalance_dates=rebalance,allow_unpriced_hold=True);held=json.loads(a.iloc[-1].holdings_json);cash=float(a.iloc[-1].cash_krw)
   if not f.empty:
    for row in f.iloc[last_replay_fills:].to_dict('records'):
     s=row['ticker']
     if row['side']=='BUY':entry[s]=float(row['fill_price_krw']) # declared latest-entry close drawdown, not hindsight trailing peak
     elif held.get(s,0)==0:entry.pop(s,None)
    last_replay_fills=len(f)
  if arm=='POLICY':
   stop=[s for s,q in held.items() if q>0 and s in entry and np.isfinite(panel['close'].loc[day,s]) and float(panel['close'].loc[day,s])<entry[s]*(1-C['risk']['stop_close_drawdown_from_entry'])]
   if stop:pending=stop;reasons.append({'reason':'CLOSE_STOP_OBSERVED_NEXT_SESSION_ONLY','symbols':stop})
  events.append({'date':day,'arm':arm,'kind':'DECISION_OR_RISK' if reasons else 'HOLD_OBSERVATION','reasons':reasons,'held_quantities':held.copy(),'price_known_through_local_close':day,'missing_held_marks':[s for s,q in held.items() if q and not np.isfinite(panel['close'].loc[day,s])]})
 return pd.DataFrame(ledger),rebalance,events

def run(m):
 decisions=[json.loads(p.read_text()) for p in sorted((B/'decisions'/m).glob('*.json'))];required=set(json.loads((B/'calendar_mapping.json').read_text())['review_dates'][m].values())| (set(json.loads((Path(__file__).parent/'event_policy.json').read_text())['US_material_event_reviews']) if m=='US' else set());assert required<={x['asof'] for x in decisions},'ALL_DECISIONS_NOT_SEALED'
 names=[c['symbol'] for c in decisions[0]['cases']];panel,dates,bench=load_panel(m,names);assert dates[0]=='2026-05-18' and dates[-1]=='2026-11-13';f=B/'evaluation'/m;f.mkdir(parents=True,exist_ok=True);results=[];capital=C['capital'][m];cost=C['cost_bps'][m];spec=ExecutionSpec(cost['buy_fee'],cost['sell_fee'],cost['half_spread'],5,30,.01,C['minimum_order_notional'][m]);gross=ExecutionSpec(0,0,0,0,0,.01,C['minimum_order_notional'][m]);benchmark=pd.Series({d:capital*float(bench.loc[d,'close'])/float(bench.loc[dates[0],'open']) for d in dates});benchmark.to_csv(f/'benchmark.csv',header=['nav']);all_months=[]
 for arm in ['POLICY','SELECTION_EQUAL90','INITIAL_SELECTION_HOLD90','MOM63_POSITIVE90']:
  ledger,rebalance,events=plan(m,arm,decisions,panel,dates,spec);a,fills,intents=replay_targets(panel,dates,ledger,capital,spec,rebalance_dates=rebalance,allow_unpriced_hold=True);ag,fg,_=replay_targets(panel,dates,ledger,capital,gross,rebalance_dates=rebalance,allow_unpriced_hold=True);
  if fills.empty:fills=pd.DataFrame(columns=['date','ticker','side','quantity','fill_price_krw','fee_krw','half_spread_cost_krw','impact_cost_krw','reference_open_krw'])
  fills['client_order_id']=['TASK93-'+digest({'market':m,'arm':arm,'date':r['date'],'ticker':r['ticker'],'side':r['side'],'contract':sha(Path(__file__).parent/'contract.json')})[:24] for r in fills.to_dict('records')]
  assert not fills.client_order_id.duplicated().any()
  a.to_csv(f/(arm+'_nav.csv'),index=False);fills.to_csv(f/(arm+'_fills.csv'),index=False);intents.to_csv(f/(arm+'_unfilled.csv'),index=False);ledger.to_csv(f/(arm+'_targets.csv'),index=False);dump(f/(arm+'_daily_actions.json'),events)
  if fills.empty:fills=pd.DataFrame(columns=['date','ticker','side','quantity','fill_price_krw','fee_krw','half_spread_cost_krw','impact_cost_krw','reference_open_krw'])
  nav=pd.Series(a.nav_krw.values,index=dates);missing=int(nav.isna().sum());daily=nav.pct_change(fill_method=None).dropna();r=float(nav.iloc[-1]/capital-1) if np.isfinite(nav.iloc[-1]) else None;br=float(benchmark.iloc[-1]/capital-1);contributions={};dividends=[]
  for s in names:
   sub=fills[fills.ticker==s];cashflow=sum((1 if x['side']=='SELL' else -1)*x['quantity']*x['fill_price_krw']-x['fee_krw'] for x in sub.to_dict('records'));q=json.loads(a.iloc[-1].holdings_json).get(s,0);endmark=float(panel['close'].loc[dates[-1],s]);contributions[s]=(cashflow+q*endmark)/capital
   ev=json.loads((B/'evaluator_only'/s/'quality.json').read_text()).get('declared_events',{}).get('dividends',{})
   for item in ev.values():
    d=__import__('datetime').datetime.fromtimestamp(item['date'],__import__('datetime').timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Seoul' if m=='KR' else 'America/New_York')).date().isoformat();before=a[a.date<d];q=json.loads(before.iloc[-1].holdings_json).get(s,0) if not before.empty else 0
    if q:dividends.append({'symbol':s,'declared_exdate':d,'amount_per_share':item['amount'],'held_before_exdate':q,'economic_entitlement':q*item['amount'],'payment_date_unknown':True})
  # Exposure attribution uses same-day index intraday on day1, prior-close realized stock exposure later.
  exp=[]
  for row in a.to_dict('records'):
   exp.append(1-row['cash_krw']/row['nav_krw'] if np.isfinite(row['nav_krw']) else np.nan)
  matched=capital;matched_path=[]
  for i,d in enumerate(dates):
   e=exp[0] if i==0 else exp[i-1];idxreturn=float(bench.loc[d,'close']/bench.loc[d,'open']-1) if i==0 else float(bench.loc[d,'close']/bench.loc[dates[i-1],'close']-1)
   matched=matched*(1+e*idxreturn) if np.isfinite(e) and np.isfinite(matched) else np.nan;matched_path.append(matched)
  pd.DataFrame({'date':dates,'approx_exposure_matched_nav':matched_path,'exposure':exp}).to_csv(f/(arm+'_exposure_matched.csv'),index=False)
  dividendtotal=sum(v['economic_entitlement'] for v in dividends);out={'market':m,'arm':arm,'initial_capital':capital,'entry':dates[0],'end':dates[-1],'final_nav':float(nav.iloc[-1]) if np.isfinite(nav.iloc[-1]) else None,'net_price_return':r,'gross_price_return':float(ag.iloc[-1].nav_krw/capital-1) if np.isfinite(ag.iloc[-1].nav_krw) else None,'benchmark_price_return':br,'excess_percentage_points':(r-br)*100 if r is not None else None,'benchmark_cash_opportunity_cost':br-r if r is not None else None,'mdd_close':float((nav/pd.concat([pd.Series([capital],index=['START']),nav]).cummax().reindex(nav.index)-1).min()) if not missing else None,'annualized_sharpe':float(daily.mean()/daily.std()*np.sqrt(252)) if not missing and daily.std()>0 else None,'average_equity_exposure':float(np.nanmean(exp)),'final_cash_weight':float(a.iloc[-1].cash_krw/nav.iloc[-1]) if np.isfinite(nav.iloc[-1]) else None,'trade_count':len(fills),'buy_count':int((fills.side=='BUY').sum()),'sell_count':int((fills.side=='SELL').sum()),'one_way_turnover':float((fills.quantity*fills.reference_open_krw).sum()/capital),'fees':float(fills.fee_krw.sum()),'spread_cost':float(fills.half_spread_cost_krw.sum()),'impact_cost':float(fills.impact_cost_krw.sum()),'unpriced_held_days':missing,'contribution_per_initial_capital':contributions,'unpaid_or_unverified_paydate_dividend_entitlement':dividendtotal,'economic_dividend_sensitivity_return':r+dividendtotal/capital if r is not None else None,'dividend_sensitivity_not_reinvested_or_paydate_cash':True,'approx_same_exposure_index_return':matched_path[-1]/capital-1 if np.isfinite(matched_path[-1]) else None,'risk_control_warning':'Lagged realized stock exposure applied to close-close index returns; firstday intraday; approximate descriptive attribution, not exact indextradeaccount','price_trust':'PARTIAL_TWO_PROVIDER_MATCH_WITH_KR_FIELD_PROVENANCE','not_forward_or_official_paper':True};results.append(out);dump(f/(arm+'_dividend_entitlements.json'),dividends)
  months=a.assign(month=a.date.str[:7]).groupby('month').tail(1)
  for row in months.to_dict('records'):all_months.append({'market':m,'arm':arm,'date':row['date'],'nav':row['nav_krw'],'cash':row['cash_krw'],'cumulative_return':row['nav_krw']/capital-1,'benchmark_return':float(benchmark.loc[row['date']]/capital-1)})
  print(m,arm,'NET',r,'INDEX',br,'FILLS',len(fills),'MISSING_NAV',missing,flush=True)
 dump(f/'results.json',results);pd.DataFrame(all_months).to_csv(f/'monthly.csv',index=False);dump(f/'execution_spec.json',{'net':spec.__dict__,'gross':gross.__dict__,'contract_hash':sha(Path(__file__).parent/'contract.json'),'replay_source_hash':sha(R/'src/quant_harness/investment/research.py'),'no_live_orders':True})
if __name__=='__main__':
 for m in sys.argv[1:] or ['US','KR']:run(m)

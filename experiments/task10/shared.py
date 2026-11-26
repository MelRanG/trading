from common import *
import pandas as pd,numpy as np
from quant_harness.investment.research import replay_targets,metrics
from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec

def frames(m,cutoff=None):
 out={}
 for p in sorted((B/'tape'/m).glob('*.csv')):
  f=pd.read_csv(p,parse_dates=['date']).set_index('date').sort_index()
  if cutoff is not None:f=f.loc[:cutoff]
  out[p.stem]=f
 return out

def make_panel(fs):
 return {'open':pd.DataFrame({s:f.open for s,f in fs.items()}),'close':pd.DataFrame({s:f.close for s,f in fs.items()}),'adv20_d1':pd.DataFrame({s:(f.close*f.volume).rolling(20,min_periods=20).mean().shift(1) for s,f in fs.items()})}

def trading_dates(fs,m):return fs[m+'_BENCHMARK'].index

def schedule(ds):return [ds[i] for i in range(0,len(ds),5)]

def target_scores(q,rd):return (q.rank(axis=1,pct=True)+rd.rank(axis=1,pct=True))/2-.5

def portfolio(scores,fs,m,start,end,*,version_schedule=None):
 panel=make_panel(fs);dates=panel['close'].index[(panel['close'].index>=pd.Timestamp(start))&(panel['close'].index<=pd.Timestamp(end))];dates=dates.intersection(fs[m+'_BENCHMARK'].index);names=sorted(s for s in fs if 'BENCHMARK' not in s);close=panel['close'];etf=m+'_BENCHMARK';risk=(close[etf]>=close[etf].rolling(63,min_periods=63).mean()).shift(1).fillna(False);oldtargets={};rebals=set(schedule(dates));ledger=[];journal=[]
 last_risk=None
 for i,d in enumerate(dates):
  risk_on=bool(risk.loc[d]);rebalance=d in rebals or (last_risk is not None and risk_on!=last_risk)
  last_risk=risk_on
  if rebalance:
   if risk_on:
    pos=close.index.get_loc(d);prev=close.index[pos-1];s=scores.reindex(columns=names).loc[prev];eligible=s[s.notna()&(s>0)&close.loc[prev,names].notna()];pick=eligible.sort_values(ascending=False,kind='stable').index[:4];oldtargets={s:.2 for s in pick}
   else:oldtargets={}
   rebals.add(d);journal.append({'effective_date':d.date().isoformat(),'observation_date':close.index[close.index.get_loc(d)-1].date().isoformat(),'risk_on':risk_on,'targets':dict(oldtargets)})
  ledger.append({'date':d,'target_weights_json':json.dumps(oldtargets)})
 cfg=json.loads((R/'config/task3_equity_contract.json').read_text());raw=cfg['US_execution_assumptions'] if m=='US' else cfg['execution_assumptions'];capital=C['strategy']['capital'][m];spec=ExecutionSpec(**{k:v for k,v in raw.items() if k!='minimum_order_nav_fraction'},minimum_order_notional_krw=capital*raw['minimum_order_nav_fraction']);l=pd.DataFrame(ledger);account,fills,intents=replay_targets(panel,dates,l,capital,spec,rebalance_dates=rebals,allow_unpriced_hold=True);metric=metrics(account,fills,capital)
 nav=account.set_index('date').nav_krw;grossnav=[];exposure=[];cash=float(capital);held={};maxerr=0.
 for obs in account.itertuples():
  day=obs.date
  for f in fills[fills.date==day].itertuples() if len(fills) else []:
   cash+=(-f.quantity*f.fill_price_krw-f.fee_krw) if f.side=='BUY' else f.quantity*f.fill_price_krw-f.fee_krw;held[f.ticker]=held.get(f.ticker,0)+(f.quantity if f.side=='BUY' else -f.quantity)
  maxerr=max(maxerr,abs(cash-obs.cash_krw));reconstructed=cash+sum(n*close.loc[day,s] for s,n in held.items() if n)
  if np.isfinite(reconstructed) and np.isfinite(obs.nav_krw):maxerr=max(maxerr,abs(reconstructed-obs.nav_krw))
  exposure.append(sum(n*close.loc[day,s] for s,n in held.items() if n)/obs.nav_krw if np.isfinite(obs.nav_krw) else np.nan)
 assert maxerr<1e-5,'CASH_POSITION_NAV_MISMATCH';metric['ledger_error']=maxerr;metric['mean_exposure']=float(np.nanmean(exposure));metric['missing_nav_marks']=int(nav.isna().sum());metric['price_only']=True;metric['no_orders_to_broker']=True;account['exposure']=exposure
 if metric['missing_nav_marks']:metric['mdd_pct']=None;metric['sharpe']=None
 return metric,account,fills,intents,l,journal

def labels(fs):
 return pd.DataFrame({s:f.open.shift(-6)/f.open.shift(-1)-1 for s,f in fs.items() if 'BENCHMARK' not in s})

def rank_ic(scores,fs,cutoff,start=None):
 scoped={s:f.loc[:cutoff] for s,f in fs.items()};target=labels(scoped);dates=target.index;valid=dates[:-6] if len(dates)>6 else dates[:0];valid=valid[valid<=pd.Timestamp(cutoff)]
 if start is not None:valid=valid[valid>=pd.Timestamp(start)]
 rows=[]
 for d in valid:
  a=scores.reindex(index=[d],columns=target.columns).loc[d];b=target.loc[d];mask=a.notna()&b.notna()
  if mask.sum()>=8 and a[mask].nunique()>1 and b[mask].nunique()>1:rows.append({'date':str(d.date()),'IC':float(a[mask].rank().corr(b[mask].rank())),'names':int(mask.sum())})
 return rows

def factor_input(fs,path):
 rows=[]
 for s,f in fs.items():
  if 'BENCHMARK' in s:continue
  x=f[['open','high','low','close','volume']].rename(columns=lambda c:'$'+c).copy();x['$return']=x['$close'].pct_change(fill_method=None);x.index.name='datetime';x['instrument']=s;rows.append(x.set_index('instrument',append=True))
 path.parent.mkdir(parents=True,exist_ok=True);pd.concat(rows).sort_index().to_csv(path)

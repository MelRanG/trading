"""V2: score at close t; enter next open, liquidate same next close.

Functional historical diagnostic only. V1 stays immutable. No overnight PnL.
"""
import json
import numpy as np
import pandas as pd

def evaluate(scores,frames,start='2025-01-01',end='2025-12-31',initial=100000.):
 close=pd.DataFrame({s:f.close for s,f in frames.items()});opens=pd.DataFrame({s:f.open for s,f in frames.items()});volume=pd.DataFrame({s:f.volume for s,f in frames.items()})
 adv=(close*volume).rolling(20,min_periods=20).mean().shift(1);lag=scores.reindex(index=close.index,columns=close.columns).shift(1);previous=close.shift(1)
 dates=close.dropna().index;dates=dates[(dates>=start)&(dates<=end)];nav=float(initial);rows=[];fills=[];ics=[]
 label=close.div(opens).sub(1)
 for day in dates:
  row=lag.loc[day];chosen=row[row>0].sort_values(ascending=False,kind='stable').index[:4];cash=nav;gross_pnl=cost=notional=0.
  for s in chosen:
   raw,exit,prior,liquid=float(opens.loc[day,s]),float(close.loc[day,s]),float(previous.loc[day,s]),float(adv.loc[day,s])
   if not all(np.isfinite(x) and x>0 for x in [raw,exit,prior,liquid]):raise ValueError('missing execution inputs')
   qty=min(int(nav*.2/prior),int(liquid*.01/raw));impact=min(50.,10.*(qty*raw/(liquid*.01))**.5);buy=raw*(1+(5+impact)/1e4);sell=exit*(1-(5+impact)/1e4)
   qty=min(qty,int(cash/(buy*1.0001)))
   if qty*raw<initial*.001:continue
   buy_fee=qty*buy*.0001;sell_fee=qty*sell*.0001;cash-=qty*buy+buy_fee;gross_pnl+=qty*(exit-raw);cost+=qty*(buy-raw+exit-sell)+buy_fee+sell_fee;notional+=qty*raw
   fills.append({'date':str(day),'symbol':s,'quantity':qty,'entry_open':raw,'exit_close':exit,'buy_price':buy,'sell_price':sell,'buy_fee':buy_fee,'sell_fee':sell_fee,'exit_time':'SAME_SESSION_CLOSE'})
  # Every selected share is sold at this close. No position is carried.
  net=gross_pnl-cost;new=nav+net;exposure=notional/nav if nav else 0.;benchmark=float(label.loc[day].mean());pair=pd.concat([row,label.loc[day]],axis=1).dropna()
  if len(pair)>4 and pair.iloc[:,0].nunique()>1 and pair.iloc[:,1].nunique()>1:ics.append(float(pair.iloc[:,0].rank().corr(pair.iloc[:,1].rank())))
  rows.append({'date':str(day),'nav':new,'net_return':net/nav,'gross_return':gross_pnl/nav,'cost':cost,'entry_notional':notional,'turnover':2*notional/nav,'exposure':exposure,'market_intraday':benchmark,'selection_effect':gross_pnl/nav-exposure*benchmark,'end_positions':0});nav=new
 df=pd.DataFrame(rows);ret=df.net_return;gross=df.gross_return;path=pd.Series([initial]+df.nav.tolist());ic=float(np.mean(ics)) if ics else None
 metrics={'version':'ALIGNED_INTRADAY_V2','evidence':'REPEATED_2025_FUNCTIONAL_NOT_HOLDOUT','sessions':len(df),'return_pct':(nav/initial-1)*100,'gross_compounded_return_pct':((1+gross).prod()-1)*100,'sharpe':float(ret.mean()/ret.std(ddof=0)*np.sqrt(252)) if ret.std(ddof=0) else 0.,'mdd_pct':float((path/path.cummax()-1).min()*100),'cost':float(df.cost.sum()),'turnover':float(df.turnover.sum()),'mean_exposure':float(df.exposure.mean()),'selection_mean_bps':float(df.selection_effect.mean()*1e4),'IC':ic,'ICIR':float(np.mean(ics)/np.std(ics)*np.sqrt(252)) if ics and np.std(ics)>0 else None,'ic_sessions':len(ics),'annualized_gross_mean':float(gross.mean()*252),'gross_mdd':float(((1+gross).cumprod()/(1+gross).cumprod().cummax()-1).min()),'terminal_positions':0,'fills':len(fills)}
 return metrics,df,pd.DataFrame(fills)

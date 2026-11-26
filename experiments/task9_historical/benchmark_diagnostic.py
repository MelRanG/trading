"""Actual index-price paths only. Never creates AI portfolio performance."""
from pathlib import Path
import sys,json,hashlib
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import normalize_chart,equity_revision_gate
b=R/'runtime/task9_historical';out=b/'evaluation';out.mkdir(exist_ok=True);result={}
for market,name,symbol in [('US','yahoo_index','^GSPC'),('KR','yahoo_kospi','^KS11')]:
 source=b/'audit'/(name+'.raw')
 if not source.exists():result[market]={'status':'MISSING'};continue
 receipt=json.loads((b/'audit'/(name+'.receipt.json')).read_text());receipt['source_hash']=receipt['sha256'];receipt['available_at']=receipt['observed_at']
 frame,meta=normalize_chart(json.loads(source.read_text()),symbol)
 frame['date']=pd.to_datetime(frame.timestamp,utc=True).dt.tz_convert('America/New_York' if market=='US' else 'Asia/Seoul').dt.strftime('%Y-%m-%d')
 frame=frame[frame.date<='2026-11-14'].copy();gate=equity_revision_gate(frame,symbol,out,receipt);frame.to_csv(out/(market+'_price_index.csv'),index=False)
 rows=[]
 for date in ['2021-11-30','2023-11-30','2024-11-29','2025-11-28','2026-05-29']:
  path=frame[frame.date>=date].copy()
  if path.empty or path.date.iloc[0]!=date:rows.append({'start':date,'status':'EXACT_START_PRICE_MISSING'});continue
  nav=path.close/path.close.iloc[0];ret=path.close.pct_change().dropna();elapsed=(pd.Timestamp(path.date.iloc[-1])-pd.Timestamp(path.date.iloc[0])).days/365.2425
  rows.append({'start':date,'end':path.date.iloc[-1],'rows':len(path),'price_return':float(nav.iloc[-1]-1),'cagr':float(nav.iloc[-1]**(1/elapsed)-1) if elapsed>0 else None,'sample_sharpe_rf0_252':float(ret.mean()/ret.std(ddof=1)*np.sqrt(252)) if len(ret)>1 and ret.std(ddof=1)>0 else None,'mdd':float((nav/nav.cummax()-1).min()),'basis':'PUBLISHED_PRICE_INDEX_NOT_TR_OR_INVESTABLE_ETF','official_session_verified':False})
 result[market]={'status':'PARTIAL_PRICE_INDEX_DIAGNOSTIC','symbol':symbol,'price_source_sha256':receipt['source_hash'],'start':frame.date.iloc[0],'end':frame.date.iloc[-1],'v87_numeric_revision_gate':gate,'periods':rows,'portfolio_comparison':'NOT_AVAILABLE_NO_ELIGIBLE_AI_REPLAY','dividends':'EXCLUDED_PRICE_INDEX_BY_DEFINITION','fees':'NO_INDEX_INVESTMENT_FILL_SIMULATED'}
(out/'benchmark_diagnostic.json').write_text(json.dumps(result,indent=2,default=str));print(json.dumps(result,indent=2,default=str))

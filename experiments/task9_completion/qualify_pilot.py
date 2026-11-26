"""Bounded-cohort qualification, no future PnL/selection scoring."""
from pathlib import Path
import sys,json,hashlib
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import normalize_chart,equity_revision_gate
B=R/'runtime/task9_completion';out=B/'qualified';out.mkdir(exist_ok=True)
limits=json.loads((Path(__file__).parent/'market_cap_contract.json').read_text());records=[]
# Same short company cohort; per-name capability, not complete-market claim.
for market,symbol,shares in [('KR','248070.KS',50005551),('US','ON',442000000)]:
 if market=='KR':
  f=pd.read_csv(B/'selected/248070.KS.csv');t=pd.read_csv(B/'pilot_prices/248070.csv');yreceipt=json.loads((B/'selected/248070.KS.receipt.json').read_text())['receipt'];zones='Asia/Seoul'
  sessions=json.loads((B/'sessions/manifest.json').read_text());dates=[r['day'] for r in sessions['active']];assert len(sessions['holding'])==63
 else:
  f=pd.read_csv(B/'us/ON/yahoo.csv');t=pd.read_csv(B/'us/ON/toss.csv');yreceipt=json.loads((B/'us/ON/yahoo.receipt.json').read_text());zones='America/New_York'
  # NYSE's published2021/2022 holiday schedule plus matching two-vendor trade bars.
  holidays={'2021-12-24','2022-01-17','2022-02-21'}
  dates=[d.strftime('%Y-%m-%d') for d in pd.date_range('2021-11-30','2022-03-15',freq='B') if d.strftime('%Y-%m-%d') not in holidays][:65]
  assert dates==f[(f.date>='2021-11-30')&(f.date<=dates[-1])].date.tolist()
 # Primary candles must cover every official session. A secondary source is a
 # cross-check, never an imputation source. Missing secondary bars are explicit.
 primary=t[(t.date>='2021-11-30')&(t.date<=dates[-1])];assert primary.date.tolist()==dates
 assert (primary.volume>0).all(),'primary has no executed-volume evidence'
 invalid_secondary=(f.volume==0)&(f.raw_open==f.raw_high)&(f.raw_high==f.raw_low)&(f.raw_low==f.raw_close)
 rejected_secondary=f.loc[invalid_secondary&f.date.between(dates[0],dates[-1]),'date'].tolist()
 secondary=f.loc[~invalid_secondary]
 joined=secondary.merge(t,on='date',suffixes=('_y','_t'));window=joined[(joined.date>='2021-11-30')&(joined.date<=dates[-1])]
 secondary_missing=sorted(set(dates)-set(window.date))
 # Vendor's displayed equity precision: integer KRW / cent USD. Never
 # optimize this tolerance against a portfolio result or average mismatches.
 tolerance=1.0 if market=='KR' else .0100001
 deltas={key:float((window['raw_'+key]-window[key+'_t']).abs().max()) for key in ('open','high','low','close')};assert all(d<=tolerance for d in deltas.values()),deltas
 cap=float(f.loc[f.date=='2021-11-30','raw_close'].iloc[0])*shares;floor=limits[market+'_min_market_cap_'+('KRW' if market=='KR' else 'USD')];assert cap>=floor
 # Provider normalization uses total-return-adjusted close; evaluation explicitly uses raw OHLC.
 audit=equity_revision_gate(f,symbol,out,yreceipt)
 raw=t.set_index('date')[['open','high','low','close','volume']];raw.to_csv(out/(market+'_raw_prices.csv'))
 # Fixed-size screen, original source share proxy explicit, not future-issued shares.
 records.append({'market':market,'symbol':symbol,'currency':'KRW' if market=='KR' else 'USD','reference_price':float(f.loc[f.date=='2021-11-30','raw_close'].iloc[0]),'shares_proxy':shares,'cap_proxy':cap,'floor':floor,'session_dates':dates,'entry':dates[1],'exit':dates[64],'holding_sessions':63,'primary_price_coverage':'ALL_OFFICIAL_SESSION_DATES_PRESENT_NO_FILL','secondary_missing_dates':secondary_missing,'secondary_rejected_flat_zero_volume':rejected_secondary,'crosscheck_tolerance_currency_units':tolerance,'max_cross_source_OHLC_difference':deltas,'numeric_revision_gate':audit,'status':'QUALIFIED_BOUNDED_RECONSTRUCTION','data_quality':'PARTIAL_SECONDARY_COVERAGE_AND_ASSUMED_COSTS','full_market_PIT':'NOT_CLAIMED','empirical_bid_ask_costs':'UNAVAILABLE_ASSUMPTIONS_ONLY'})
# Exclusions fixed before any post-cutoff PnL evaluation and not deleted.
excluded=[{'symbol':'115610.KQ','reasons':['CAP_BELOW_KRW500BN','TOSS_YAHOO_RAW_BASIS_MISMATCH','PRE_CUTOFF_BONUS_SHARE_BRIDGE_REQUIRED']},{'symbol':'950170.KQ','reasons':['CAP_BELOW_KRW500BN','EX_DIVIDEND_RECORD_NEEDS_CASH_ENTITLEMENT_IF_HELD']},{'symbol':'ANET','reasons':['TOSS_YAHOO_FACTOR4_PRICE_BASIS_MISMATCH_UNRESOLVED']},{'symbol':'VNO','reasons':['DIRECT_PRIMARY_RELEASE_DOWNLOAD_FAILED','DIVIDEND_CASH_PIPELINE_NOT_QUALIFIED_FOR_FIRST_PILOT']},{'symbol':'SPG','reasons':['DIRECT_PRIMARY_RELEASE_DOWNLOAD_FAILED','DIVIDEND_CASH_PIPELINE_NOT_QUALIFIED_FOR_FIRST_PILOT']}]
result={'version':'BOUNDED_PILOT_V1','cohort_scope':'Three KR original-report companies, four US dated issuer releases, not full market','qualified':records,'excluded':excluded,'risk':'Small exploratory research positions only; no official Paper approval','on_financial_source':'Primary official web-reader excerpt, not complete raw download','universe_change_reason':'User explicitly authorized bounded discovery + selected-name search and cap floor before new research'}
(out/'manifest.json').write_text(json.dumps(result,indent=2));print([(r['symbol'],r['entry'],r['exit'],r['cap_proxy'],r['max_cross_source_OHLC_difference']) for r in records])

from pathlib import Path
import sys,json
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).parent))
from evaluate import mix,window,valid_prices

def test_calendar_month_horizon_waits_for_market_event_and_excludes_cutoff():
 dates=pd.to_datetime(['2021-11-30','2021-12-01','2022-03-01','2022-03-02','2022-12-01'])
 assert window(dates,'2021-11-30',3)==(pd.Timestamp('2021-12-01'),pd.Timestamp('2022-03-01'))
 with pytest.raises(AssertionError,match='PENDING'):window(dates,'2021-11-30',24)

def test_full_exposure_and_cash_policy_are_distinct_and_cost_is_funded():
 idx=pd.date_range('2022-01-01',periods=3);a=pd.Series([1,1.1,1.2],index=idx);b=pd.Series([1,.95,1.1],index=idx)
 m,nav=mix({'a':a,'b':b},{'a':.5,'b':.5},a,6,6)
 assert m['gross_price_return']==pytest.approx(.15)
 assert m['net_price_return']<.15 and nav.net_nav.iloc[0]>=0
 policy,_=mix({'a':a},{'a':.2},a,6,6);assert policy['cash_target']==.8 and policy['gross_price_return']==pytest.approx(.04)

def test_missing_selected_name_blocks_no_survivor_renormalization():
 dates=pd.date_range('2022-01-01',periods=3);a=pd.Series([1,1.1,1.2],index=dates)
 with pytest.raises(ValueError,match='MISSING_SELECTED'):mix({'a':a},{'a':.5,'b':.5},a,6,6)

def test_cash_remains_zero_return_but_records_index_opportunity_cost():
 idx=pd.date_range('2022-01-01',periods=3);cash=pd.Series(1.,index=idx);b=pd.Series([1,1.1,1.2],index=idx)
 m,n=mix({'cash':cash},{'cash':0},b,0,0)
 assert m['net_price_return']==0 and m['excess_vs_full_index']==pytest.approx(-.2)
 assert m['net_vs_matched_gross']==0

def test_bad_ohlc_is_quarantined_without_imputation():
 f=pd.DataFrame({'date':['2022-01-01','2022-01-02'],'open':[10,10],'high':[11,11],'low':[9,9],'close':[10,8],'volume':[100,100]});good,bad=valid_prices(f)
 assert len(good)==len(bad)==1 and bad.close.iloc[0]==8

def test_all_sealed_companies_have_pre_cutoff_sources_and_fixed_portfolios():
 b=Path(__file__).resolve().parents[2]/'runtime/task9_value'
 for year,stage in [(2021,'deep2_2021'),(2022,'deep2_2022'),(2023,'deep3_2023')]:
  p=json.loads((b/'deep_inputs'/(stage+'.json')).read_text());s=json.loads((b/'decisions'/(str(year)+'.json')).read_text());assert s['session_input_hash']==p['session_input_hash']
  for c in p['cases']:assert str(c['source']['published']).replace('-','')<=str(year)+'1130'
  assert len(s['decision']['companies'])==6

def test_failed_transport_and_budget_overrun_not_hidden():
 b=Path(__file__).resolve().parents[2]/'runtime/task9_value';u=json.loads((b/'model_usage.json').read_text());assert u['transport_failed']==2 and u['token_overrun']==5741
 for year in [2021,2022]:
  x=json.loads((b/'decisions'/(str(year)+'.json')).read_text());assert x['transport_status']=='FAILED' and x['recovered_from_complete_raw_trace']

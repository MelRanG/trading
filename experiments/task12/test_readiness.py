from pathlib import Path
import sys
import pandas as pd,numpy as np,pytest
sys.path.insert(0,str(Path(__file__).parent))
from readiness import labels,regimes
from evaluation import signal_statistics,execution_arms
from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec

def frames():
 ds=pd.bdate_range('2024-01-01',periods=180)
 return {s:pd.DataFrame({'open':100+np.arange(len(ds),dtype=float),'close':101+np.arange(len(ds),dtype=float),'volume':1000000.},index=ds) for s in ['US001','US_BENCHMARK']}

def test_label_horizon_and_no_future_target():
 fs=frames();ds=fs['US001'].index;y,end=labels(fs,'US',5,ds[100]);assert y.loc[ds[80],'US001']==pytest.approx((100+86)/(100+81)-1)
 assert y.iloc[-6:].isna().all().all() and end.iloc[-6:].isna().all()
 later=frames();later['US001'].loc[ds[101]:,'open']*=100
 pd.testing.assert_frame_equal(y,labels(later,'US',5,ds[100])[0])

def test_missing_market_session_not_skipped_or_interpolated():
 fs=frames();ds=fs['US001'].index;fs['US001'].loc[ds[83],'open']=np.nan
 y,_=labels(fs,'US',5,ds[100]);assert pd.isna(y.loc[ds[80],'US001'])

def test_asof_regime_invariant_to_future_but_expost_not_a_feature():
 fs=frames();close=fs['US001'].close;cut=close.index[145];a=regimes(close);changed=close.copy();changed.loc[changed.index>cut]*=3;b=regimes(changed)
 pd.testing.assert_series_equal(a.loc[:cut,'AS_OF_REGIME'],b.loc[:cut,'AS_OF_REGIME']);assert (a.loc[:cut,'EX_POST_REGIME']!=b.loc[:cut,'EX_POST_REGIME']).any()

def test_event_not_forced_into_cross_sectional_ic():
 x=pd.DataFrame([[1.]],index=[pd.Timestamp('2025-01-01')],columns=['a'])
 with pytest.raises(ValueError,match='own preregistered'):signal_statistics(x,x,kind='event')
 with pytest.raises(ValueError,match='original qlib'):signal_statistics(x,x)

def test_layer2_and3_same_signal_different_risk_only():
 ds=pd.bdate_range('2025-01-01',periods=80);close=pd.DataFrame({'stock':100.,'benchmark':np.arange(180.,100.,-1)},index=ds);panel={'close':close,'open':close.copy(),'adv20_d1':pd.DataFrame(100000000.,index=ds,columns=close.columns)};dates=ds[-3:]
 ledger=pd.DataFrame({'date':dates,'target_weights_json':['{"stock":0.8}']*3});control=pd.DataFrame({'date':dates,'target_weights_json':['{"benchmark":0.8}']*3});spec=ExecutionSpec(1,1,5,10,50,.01,1000);copy=ledger.copy(deep=True)
 out=execution_arms(panel,dates,ledger,control,10000000,spec,{dates[0]},'benchmark');pd.testing.assert_frame_equal(ledger,copy)
 assert len(out['FIXED_EXPOSURE']['fills'])>0 and len(out['SAME_SIGNAL_WITH_EXISTING_RISK']['fills'])==0 and len(out['RISK_ONLY_BASELINE']['fills'])==0
 assert out['SAME_SIGNAL_WITH_EXISTING_RISK']['metrics']['return_pct']==0

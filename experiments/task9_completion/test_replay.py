import pytest,json
import pandas as pd
from replay import fixed_hold,performance,ExecutionSpec

def fixture():
 dates=pd.date_range('2021-01-01',periods=90,freq='B');f=pd.DataFrame({'open':[100+i for i in range(90)],'high':[102+i for i in range(90)],'low':[99+i for i in range(90)],'close':[101+i for i in range(90)],'volume':[1000000]*90},index=dates);return f,dates[-64:],ExecutionSpec(1.5,24.5,5,10,50,.01,100)

def test_real_qh_fees_fixed_shares_and_flat_exit_no_daily_rebalance():
 f,d,s=fixture();a,orders,_,detail=fixed_hold(f,'FIXTURE',d,.025,100000,s);assert orders.side.tolist()==['BUY','SELL'] and a.iloc[-1].cash_krw==a.iloc[-1].nav_krw
 metrics=performance(a,orders,detail,f,f,d,100000);assert metrics['fills']==2 and metrics['recorded_assumed_cost']>0 and metrics['gross_price_return']>metrics['net_return']

def test_holding_does_not_trade_on_intermediate_price_moves():
 f,d,s=fixture();f.loc[d[10:20],'close']*=.5
 a,orders,_,_=fixed_hold(f,'FIXTURE',d,.025,100000,s);assert len(orders)==2 and len(a)==64

def test_no_forced_buy_cash_choice_and_no_fake_costs():
 f,d,s=fixture();a,orders,_,detail=fixed_hold(f,'FIXTURE',d,0,100000,s);m=performance(a,orders,detail,f,f,d,100000);assert len(orders)==0 and m['net_return']==0 and m['recorded_assumed_cost']==0 and m['initial_exposure']==0

def test_missing_primary_session_and_unknown_action_fail_closed():
 f,d,s=fixture()
 with pytest.raises(ValueError):fixed_hold(f.drop(d[2]),'FIXTURE',d,.025,100000,s)
 with pytest.raises(ValueError):fixed_hold(f,'FIXTURE',d,.025,100000,s,actions=[{'split':2}])

def test_benchmark_alignment_uses_entry_exit_opens_not_terminal_close():
 f,d,s=fixture();a,o,_,detail=fixed_hold(f,'FIXTURE',d,.025,100000,s);b=f.copy();b.loc[d[-1],'close']*=2;m=performance(a,o,detail,f,b,d,100000);assert m['benchmark_price_return_same_open_interval']==pytest.approx(f.loc[d[-1],'open']/f.loc[d[0],'open']-1)


def test_postgres_signed_zero_roundtrip_requires_local_canonicalization():
 import psycopg
 from serialization_fix import canonical_zero
 from quant_harness.investment.research import digest
 original={'metric':-0.0,'nonzero_return':-.00123}
 with psycopg.connect('postgresql://quant_task9_history@127.0.0.1:55432/quant_task3_task9_history',options='-c default_transaction_read_only=on') as conn:
  decoded=conn.execute('SELECT %s::jsonb',(json.dumps(original),)).fetchone()[0]
  assert digest(original)!=digest(decoded)
  clean=canonical_zero(original);decoded2=conn.execute('SELECT %s::jsonb',(json.dumps(clean),)).fetchone()[0]
  assert digest(clean)==digest(decoded2) and clean['nonzero_return']==original['nonzero_return']

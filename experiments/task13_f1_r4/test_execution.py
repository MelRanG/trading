import pytest
from experiments.task13_f1_r4.execution import Account, trade_open, corporate_adjust
from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec

SPEC = ExecutionSpec(buy_fee_bps=1.5,sell_fee_bps=21.5,half_spread_bps=5,
                     impact_bps_at_1pct_adv=10,max_impact_bps=50,
                     max_participation_of_d1_adv=.01,minimum_order_notional_krw=10)
PRIOR = dict.fromkeys('ABCDEFGH',100.)
LIQUID = dict.fromkeys('ABCDEFGH',10_000_000.)
TARGET = dict.fromkeys('EFGH',.2)


def scenario(cash=2_000, units=20):
    return Account(cash,dict.fromkeys('ABCD',units))


def trade(account,tar=TARGET,open_prices=PRIOR,adv=LIQUID,rebalance=True,risk_on=True):
    return trade_open(account,tar,PRIOR,open_prices,adv,SPEC,rebalance=rebalance,risk_on=risk_on)


def buy(fills):
    return [f for f in fills if f['side']=='BUY']


def test_four_blocked_exits_and_gap_keeps_real_slots():
    a=scenario()
    fills,events,_=trade(a,adv={**LIQUID,**dict.fromkeys('ABCD',0.)})
    assert not fills
    assert len(a.pending_sells)==len(a.positions)==4
    assert sum(e['reason']=='SELL_REMAINDER' for e in events)==4


def test_partial_sell_does_not_free_a_slot():
    a=scenario()
    fills,_,_=trade(a,adv={**LIQUID,**dict.fromkeys('ABCD',10_000.)})
    assert [f['quantity'] for f in fills]==[1]*4
    assert not buy(fills)
    assert a.positions==dict.fromkeys('ABCD',19)


def test_one_executed_exit_frees_only_one_slot():
    a=scenario()
    f,_,_=trade(a,adv={**LIQUID,**dict.fromkeys('BCD',0.)})
    assert list(a.pending_sells)==list('BCD')
    assert len(buy(f))==1 and len(a.positions)==4
    assert not any(s in a.positions for s in 'FGH')


@pytest.mark.parametrize('gap',[70.,145.])
def test_open_gap_resizes_order_through_caps(gap):
    a=Account(10_000)
    op=dict.fromkeys('EFGH',gap)
    f,_,_=trade(a,open_prices=op)
    assert 0<len(f)<=4
    end=sum(q*gap for q in a.positions.values())
    assert end<=.8*(end+a.cash)
    assert max(a.positions.values())*gap<=.2*(end+a.cash)


def test_risk_off_retries_residual_on_nonrebalance_only_for_sell():
    a=scenario()
    first,_,_=trade(a,adv={**LIQUID,'B':0},risk_on=False)
    assert len(first)==3 and not buy(first) and a.positions=={'B':20}
    f,_,_=trade(a,rebalance=False,risk_on=False)
    assert len(f)==1 and f[0]['side']=='SELL'
    assert a.positions=={} and a.pending_sells=={}


def test_missing_mark_blocks_all_buys_and_allows_known_exits():
    a=scenario()
    f,_,_=trade(a,open_prices={**PRIOR,'D':None})
    assert len(f)==3 and not buy(f) and a.positions=={'D':20}


def test_low_cash_and_overweight_are_not_increased():
    a=scenario(cash=0)
    f,_,_=trade(a,tar=dict.fromkeys('ABCD',.2),open_prices={**PRIOR,'A':400.})
    assert not buy(f)
    assert a.cash>=0 and a.positions.get('A',0)<=20


def test_next_targets_replace_old_residual_and_buy_ioc_is_not_retried():
    a=scenario()
    trade(a,adv={**LIQUID,**dict.fromkeys('ABCD',0.)})
    f,_,_=trade(a,rebalance=False)
    assert len(f)==4 and not buy(f) and not a.positions
    f,_,_=trade(a,tar=dict.fromkeys('ABCD',.2))
    assert len(buy(f))==4
    assert not a.pending_sells


def test_split_updates_shares_and_residual_without_cash():
    a=Account(2000,{'A':20},{'A':10})
    corporate_adjust(a,'A',2.)
    assert a.positions=={'A':40} and a.pending_sells=={'A':20} and a.cash==2000
    with pytest.raises(ValueError):
        corporate_adjust(a,'A',1./3)


def test_archived_january_22_reproduction_blocks_three_legacy_buys():
    from pathlib import Path
    import json
    import pandas as pd
    root=Path(__file__).resolve().parents[2]/'runtime/task13_f1_r2'
    nav=pd.read_csv(root/'T1_A_nav.csv').set_index('date')
    intents=pd.read_csv(root/'T1_A_intents.csv')
    old=pd.read_csv(root/'T1_A_fills.csv')
    assert len(old[(old.date=='2024-01-22')&(old.side=='BUY')])==3
    blocked=set(intents.loc[(intents.date=='2024-01-22')&(intents.reason=='HOLD_ONLY_MISSING_OPEN_OR_ADV'),'symbol'])
    prev=nav.loc['2024-01-19']
    state=Account(float(prev.cash_krw),{s:q for s,q in json.loads(prev.holdings_json).items() if q})
    assert set(state.positions)==blocked and len(blocked)==4
    targets=pd.read_csv(root/'T1_A_targets.csv').set_index('date')
    target=json.loads(targets.loc['2024-01-22','target_weights_json'])
    # Reproduce the archived failure mechanism, without consuming historical return data.
    prices=dict.fromkeys(set(blocked)|set(target),100_000.)
    adv={**dict.fromkeys(target,1_000_000_000.),**dict.fromkeys(blocked,0.)}
    fills,events,_=trade_open(state,target,prices,prices,adv,SPEC,rebalance=True,risk_on=True)
    assert fills==[] and set(state.positions)==set(state.pending_sells)==blocked
    assert sum(e['reason']=='SELL_REMAINDER' for e in events)==4

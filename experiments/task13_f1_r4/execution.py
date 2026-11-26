"""Isolated research-only next-open execution guard. No broker interfaces."""
import math
from dataclasses import dataclass, field
from quant_harness.v77_corrected_price_allocation.engine import _buy_fill_terms, _impact_bps


def usable(value):
    return value is not None and math.isfinite(value) and value>0


@dataclass
class Account:
    cash: float
    positions: dict = field(default_factory=dict)
    pending_sells: dict = field(default_factory=dict)


def exposure(account, prices):
    if any(not usable(prices.get(s)) for s in account.positions):
        return None
    return sum(n*prices[s] for s,n in account.positions.items())


def trade_open(account, targets, prior_close, opening, adv, spec, *, rebalance, risk_on):
    """Process sells first; buys are IOC, sell residuals retry until replaced."""
    if len(targets)>4 or any(w!=.2 for w in targets.values()) or sum(targets.values())>.8+1e-9:
        raise ValueError('frozen target violates name/weight rules')
    fills,events=[],[]
    before=exposure(account,opening)
    before_ratio=before/(account.cash+before) if before is not None else None
    if not risk_on:
        targets={}
        account.pending_sells=dict.fromkeys(account.positions,0)
    desired={}
    valid_prior=rebalance and all(usable(prior_close.get(s)) for s in set(targets)|set(account.positions))
    if valid_prior:
        prior_nav=account.cash+exposure(account,prior_close)
        desired={s:int(prior_nav*w/prior_close[s]) for s,w in targets.items()}
        account.pending_sells={s:desired.get(s,0) for s,n in account.positions.items() if desired.get(s,0)<n}
    elif rebalance:
        events.append({'reason':'MISSING_PRIOR_MARK_NO_NEW_BUYS'})
        # Explicit zero-weight exits do not need account valuation to size.
        account.pending_sells={s:0 for s in account.positions if s not in targets}

    def liquidity(symbol, need):
        price=opening.get(symbol)
        amount=adv.get(symbol)
        if not usable(price) or not usable(amount):
            return 0
        q=min(need,int(amount*spec.max_participation_of_d1_adv/price))
        return q if q*price>=spec.minimum_order_notional_krw else 0

    def apply(symbol, qty, terms, side):
        price=opening[symbol]
        impact,fill,fee=terms
        direction=1 if side=='BUY' else -1
        account.cash-=direction*qty*fill+fee
        account.positions[symbol]=account.positions.get(symbol,0)+direction*qty
        if not account.positions[symbol]:
            del account.positions[symbol]
        assert account.cash>=-1e-6 and min(account.positions.values(),default=0)>=0
        fills.append({'symbol':symbol,'side':side,'quantity':qty,'reference_open':price,
                      'fill_price':fill,'fee':fee,'impact_bps':impact,
                      'open_notional':qty*price,'cash_after':account.cash})

    for s,target in sorted(account.pending_sells.items()):
        need=account.positions.get(s,0)-target
        if need<=0:
            del account.pending_sells[s]
            continue
        q=liquidity(s,need)
        if q:
            p=opening[s]
            bps=_impact_bps(q*p,adv[s],spec)
            fill=p*(1-(spec.half_spread_bps+bps)/10000)
            apply(s,q,(bps,fill,q*fill*spec.sell_fee_bps/10000),'SELL')
        if q==need:
            del account.pending_sells[s]
        else:
            events.append({'symbol':s,'reason':'SELL_REMAINDER','quantity':need-q})

    if risk_on and valid_prior:
        for s,target in sorted(desired.items()):
            held=account.positions.get(s,0)
            if target<=held:
                continue
            value=exposure(account,opening)
            available=(value is not None and (held>0 or len(account.positions)<4)
                       and len(account.positions)<=4 and value<.8*(account.cash+value))
            cap=liquidity(s,target-held) if available else 0
            bought=0
            if cap:
                p=opening[s]
                cap,_,_,_,_=_buy_fill_terms(cash=account.cash,max_quantity=cap,raw_open=p,adv=adv[s],spec=spec)
                lo,hi=0,cap
                while lo<hi:
                    mid=(lo+hi+1)//2
                    bps=_impact_bps(mid*p,adv[s],spec)
                    fill=p*(1+(spec.half_spread_bps+bps)/10000)
                    fee=mid*fill*spec.buy_fee_bps/10000
                    after_nav=account.cash+value-mid*(fill-p)-fee
                    if value+mid*p<=.8*after_nav and (held+mid)*p<=.2*after_nav:
                        lo=mid
                    else:
                        hi=mid-1
                if lo and lo*p>=spec.minimum_order_notional_krw:
                    bps=_impact_bps(lo*p,adv[s],spec)
                    fill=p*(1+(spec.half_spread_bps+bps)/10000)
                    apply(s,lo,(bps,fill,lo*fill*spec.buy_fee_bps/10000),'BUY')
                    post=exposure(account,opening)
                    assert len(account.positions)<=4 and post<=.8*(account.cash+post)+1e-7
                    assert account.positions[s]*p<=.2*(account.cash+post)+1e-7
                    bought=lo
            if bought<target-held:
                events.append({'symbol':s,'reason':'BUY_IOC_UNFILLED','quantity':target-held-bought})
    return fills,events,before_ratio


def corporate_adjust(account, symbol, ratio):
    """Apply an externally verified split ratio once, before open."""
    if symbol not in account.positions:
        return
    q=account.positions[symbol]*ratio
    pending=account.pending_sells.get(symbol)
    if not q.is_integer() or (pending is not None and not (pending*ratio).is_integer()):
        raise ValueError('fractional corporate-action settlement unverified')
    account.positions[symbol]=int(q)
    if pending is not None:
        account.pending_sells[symbol]=int(pending*ratio)

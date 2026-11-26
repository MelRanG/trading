"""One frozen C1 feature; no labels, fitting, network or strategy execution."""
import numpy as np
import pandas as pd


def estimate_beta_sigma(stock_returns, market_returns):
    """OLS slope (intercept included); sample SD of its demeaned residuals.
    shift(6) makes the inclusive 120-return window t-125..t-6.
    Missing returns are omitted only inside this estimation window (>=110).
    """
    y = stock_returns.where(np.isfinite(market_returns))
    x = market_returns.where(y.notna())
    n = y.rolling(120, min_periods=110).count()
    present = pd.Series(np.arange(len(y)) >= 119, index=y.index)
    n = n.where(present)
    vx = x.rolling(120, min_periods=110).var(ddof=1)
    vy = y.rolling(120, min_periods=110).var(ddof=1)
    cov = y.rolling(120, min_periods=110).cov(x, ddof=1)
    beta = (cov / vx).where((n >= 110) & (vx > 0))
    variance = vy - cov * cov / vx
    sigma = np.sqrt(variance.where(variance > 0)).where(n >= 110)
    return beta.shift(6), sigma.shift(6), n.shift(6)


def features(close, eligible, market_close, market_eligible):
    if not close.index.equals(market_close.index):
        raise ValueError('Common session calendar required')
    price = close.where(eligible & (close > 0))
    market = market_close.where(market_eligible & (market_close > 0))
    # diff keeps invalid endpoints invalid; never connects across a missing session.
    r = np.log(price).diff()
    rm = np.log(market).diff()
    beta, sigma, count = estimate_beta_sigma(r, rm)
    shock = r.rolling(5, min_periods=5).sum() - beta * rm.rolling(5, min_periods=5).sum()
    score = -shock / (np.sqrt(5) * sigma)
    simple_r = price.pct_change(fill_method=None)
    continuous63 = eligible.rolling(63, min_periods=63).sum().eq(63)
    out = pd.DataFrame({'signal': score, 'REV5': -(price / price.shift(5) - 1),
                        'MOM20': price / price.shift(20) - 1,
                        'LOWVOL20': -simple_r.rolling(20, min_periods=20).std(ddof=1),
                        'beta': beta, 'sigma': sigma, 'beta_n': count})
    required = ['signal', 'REV5', 'MOM20', 'LOWVOL20', 'beta', 'sigma']
    finite = np.isfinite(out[required]).all(axis=1) & continuous63
    out.loc[~finite, required] = np.nan
    return out


def forward_valid(eligible, H=5):
    """Quality of all t+1..t+H+1 sessions; no price target computed here."""
    good = pd.Series(True, index=eligible.index)
    for j in range(1, H + 2):
        good &= eligible.shift(-j, fill_value=False)
    return good


def labels(open_price, eligible, H=5):
    return (open_price.shift(-H-1) / open_price.shift(-1) - 1).where(forward_valid(eligible, H))

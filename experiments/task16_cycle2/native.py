"""Compute one score with the original Vibe registry on existing local daily data."""
import sys

import numpy as np
import pandas as pd
from src.factors.registry import get_default_registry


def main():
    panel, output = sys.argv[1:]
    registry = get_default_registry()
    key = "academic_retskew"
    meta = registry.get(key).meta
    assert "equity_us" in meta["universe"] and "equity_kr" not in meta["universe"]
    assert meta["columns_required"] == ["close"]
    with np.load(panel) as z:
        close = pd.DataFrame(z["close"], index=pd.DatetimeIndex(z["dates"]), columns=z["symbols"])
    def compute(frame):
        return registry.compute(key, {"close":frame})
    original = compute(close)
    skew = -close.pct_change(fill_method=None).rolling(60).skew()
    denom = skew.std(axis=1, ddof=1)
    oracle = skew.sub(skew.mean(axis=1),axis=0).div(denom.where(denom>0),axis=0)
    pd.testing.assert_frame_equal(original,oracle,atol=1e-9,rtol=1e-9)
    i = len(close)//2
    pd.testing.assert_frame_equal(original.iloc[:i], compute(close.iloc[:i]))
    amended = close.copy()
    amended.iloc[i:] *= 1+np.arange(len(close)-i)[:,None]/len(close)
    pd.testing.assert_frame_equal(original.iloc[:i],compute(amended).iloc[:i])
    with open(output,"xb") as stream:
        np.save(stream,original.to_numpy())
    print(f"native registry {registry.health()['loaded']} entries; {key} original/oracle parity and causal tests passed")


if __name__=="__main__":
    main()

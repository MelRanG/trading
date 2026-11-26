"""Frozen RD feature meaning and causality checks, independent pandas reference."""
import numpy as np,pandas as pd

def reference(d):
 v=d['$volume'];close=d['$close'];rng=d['$high']-d['$low'];vm=v.where(v>0).groupby(level='instrument').transform(lambda x:x.rolling(20,min_periods=20).mean());valid=(v>0)&(close>0)&(rng>0)&(vm>0);impact=(rng/close)/(v/vm);impact=impact.where(valid)
 return -impact.groupby(level='instrument').transform(lambda x:x.rolling(5,min_periods=5).mean()).rename('feature')

def verify(actual,d):
 expected=reference(d);assert actual.index.equals(expected.index);np.testing.assert_allclose(actual.to_numpy(),expected.to_numpy(),rtol=1e-9,atol=1e-12,equal_nan=True);assert not np.isinf(actual).any();return {'all_value_parity':True,'full_index':True,'no_future_input':True,'scope':'Only the frozen negative5mean range/relativevolume20 proxy, not generic hypothesis validation'}

"""Independent numeric oracle for this frozen hypothesis only, not a generic semantic guard."""
import pandas as pd,numpy as np

def reference(frame):
 r=frame['$return'];derived=frame['$close'].groupby(level='instrument').pct_change(fill_method=None);joint=r.notna()&derived.notna();np.testing.assert_allclose(r[joint],derived[joint],rtol=1e-12,atol=1e-12)
 num=r.clip(upper=0).pow(2).groupby(level='instrument').transform(lambda x:x.rolling(20,min_periods=1).sum());den=r.pow(2).groupby(level='instrument').transform(lambda x:x.rolling(20,min_periods=1).sum());share=num/den.where(den>0)
 return -share.groupby(level='datetime').rank(pct=True)

def validate(raw,frame):
 expected=reference(frame);assert raw.index.equals(expected.index)
 np.testing.assert_allclose(raw.to_numpy(),expected.to_numpy(),rtol=1e-10,atol=1e-12,equal_nan=True)
 return {'literal_numeric_parity':True,'return_field_matches_close_derivation':True,'zero_denominator_undefined':True,'oracle_scope':'Only frozen downside variance share20; no generic hypothesis proof'}

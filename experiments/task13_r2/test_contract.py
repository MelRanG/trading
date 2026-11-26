import json
import numpy as np,pandas as pd,pytest
from feature_oracle import reference,verify
from json_shape import repair_formulation

def frame():
 index=pd.MultiIndex.from_product([pd.date_range('2020-01-01',periods=70),['A','B']],names=['datetime','instrument'])
 return pd.DataFrame({'$high':12.,'$low':10.,'$close':11.,'$volume':100.},index=index)

def test_feature_contract_full_windows_and_missing():
 d=frame();s=reference(d);days=d.index.get_level_values(0).unique();assert s.xs('A',level=1).iloc[:23].isna().all();assert s.loc[(days[23],'A')]==pytest.approx(-2/11)
 d.loc[(days[30],'B'),'$volume']=0;s=reference(d);assert s.loc[(days[53],'B')]!=s.loc[(days[53],'B')];assert s.loc[(days[54],'B')]==pytest.approx(-2/11)
 with pytest.raises(AssertionError):verify(-s,d)

def test_future_prefix_unchanged():
 d=frame();old=reference(d);days=d.index.get_level_values(0).unique();d.loc[(slice(days[50],None),slice(None)),'$high']*=2
 pd.testing.assert_series_equal(old.loc[(slice(None,days[49]),slice(None))],reference(d).loc[(slice(None,days[49]),slice(None))])

def test_json_formula_repair_preserves_other_fields():
 text=r'{"x":{"formulation":"y=\frac{1}{5}\sum x","description":"same","count":20}}';fixed,changed=repair_formulation(text);assert changed;d=json.loads(fixed);assert d['x']['formulation']==r'y=\frac{1}{5}\sum x';assert d['x']['count']==20 and d['x']['description']=='same';assert repair_formulation(fixed)==(fixed,False)
 with pytest.raises(json.JSONDecodeError):repair_formulation(r'{"code":"bad\q"}')

from pathlib import Path
import ast,json
import numpy as np,pandas as pd,pytest
from syntax_adapter import normalized
from meaning import reference,validate

def gate():
 s=Path(__file__).with_name('native_worker.py').read_text();tree=ast.parse(s);node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='strict_gate_result');scope={'json':json};exec(compile(ast.Module(body=[node],type_ignores=[]),'<same native gate>','exec'),scope);return scope['strict_gate_result']

def test_native_error_cannot_be_pass():
 f=gate();d={'consistency':{'is_consistent':True,'overall_feedback':'Consistency check failed with error: test. Skipping check.'},'corrected_expression':'x'}
 with pytest.raises(ValueError,match='FAIL_CLOSED'):f((True,'',d),'x')
 d['consistency']={'is_consistent':False}
 with pytest.raises(ValueError):f((False,'',d),'x')
 d['consistency']={'is_consistent':True};d['corrected_expression']='weakened'
 with pytest.raises(ValueError,match='AUTOCORRECTION'):f((True,'',d),'x')

def test_oracle_and_wrong_meaning():
 ix=pd.MultiIndex.from_product([pd.date_range('2020-01-01',periods=30),['MIX','FLAT']],names=['datetime','instrument']);returns=np.tile([.01,0,-.02,0,.03,0],10);frame=pd.DataFrame({'$return':returns},index=ix);frame['$close']=(1+frame['$return']).groupby(level=1).cumprod()*100;expected=reference(frame);assert expected.xs('FLAT',level=1).isna().all();validate(expected,frame)
 with pytest.raises(AssertionError):validate(-expected,frame)
 assert normalized('-RANK(x)')=='SUBTRACT(0,RANK(x))'


def test_unary_fix_must_not_negate_an_entire_binary_expression():
 assert normalized('-RANK(x)+y')=='-RANK(x)+y'
 assert normalized('RANK(x)')=='RANK(x)'

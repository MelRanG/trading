from pathlib import Path
import json,numpy as np,pandas as pd
from quantaalpha.pipeline.evolution import EvolutionController
from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression
from quantaalpha.factors.regulator.factor_regulator import FactorRegulator
from quantaalpha.factors.coder.function_lib import RANK,TS_SUM,MIN,POW,SUBTRACT
from syntax_adapter import normalized
expr='-RANK(TS_SUM(POW(MIN($return, 0), 2), 20) / TS_SUM(POW($return, 2), 20))'
r=FactorRegulator();a,old=r.evaluate(expr);b,new=r.evaluate(normalized(expr));assert old['num_all_nodes']==0 and new['num_all_nodes']>0 and r.is_expression_acceptable(new)
index=pd.MultiIndex.from_product([pd.date_range('2020-01-01',periods=40),['A','B','C']],names=['datetime','instrument']);x=pd.Series(np.sin(np.arange(len(index))*.7)*.01,index=index);raw=-RANK(TS_SUM(POW(MIN(x,0),2),20)/TS_SUM(POW(x,2),20));canon=SUBTRACT(0,RANK(TS_SUM(POW(MIN(x,0),2),20)/TS_SUM(POW(x,2),20)));np.testing.assert_allclose(raw,canon,equal_nan=True)
Path('/work/syntax_probe.json').write_text(json.dumps({'original_nodes':old['num_all_nodes'],'normalized_nodes':new['num_all_nodes'],'original_expression':expr,'AST_only_normalization':normalized(expr),'native_numeric_equivalence':True,'structural_acceptance':True},indent=2));print('PASS')

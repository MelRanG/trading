from pathlib import Path
import json,traceback,pandas as pd
import sys
sys.path.insert(0,'/code');from loader import supervised
out={'LLM_calls':0}
for m in ['US','KR']:
 d=pd.read_hdf('/inputs/'+m+'_train.h5',key='data');f,meta=supervised(d,20);dates=f.index.get_level_values(0);days=d.index.get_level_values(0).unique().sort_values();end=pd.Series(days,index=days).shift(-21);maturity=dates.map(end);out[m]={'supervised':meta,'fit_rows':int(((dates<='2020-12-31')&(maturity<='2020-12-31')).sum()),'inner_rows':int(((dates>='2021-04-01')&(maturity<='2022-12-31')).sum())}
try:
 from rdagent.app.qlib_rd_loop.quant import QuantRDLoop
 from rdagent.app.qlib_rd_loop.conf import QUANT_PROP_SETTING
 loop=QuantRDLoop(QUANT_PROP_SETTING);out['full_controller_constructor']='PASS_ONLY_NO_RESEARCH_RUN'
except Exception as e:out['full_controller_constructor']={'type':type(e).__name__,'error':str(e),'trace':traceback.format_exc()}
Path('/work/phase_a_probe.json').write_text(json.dumps(out,indent=2,default=str));print(json.dumps(out,default=str))

"""Perturb future raw observations and recompute the unmodified original factor."""
from pathlib import Path
import json
import pandas as pd
from src.factors.registry import get_default_registry
root=Path('/work');plan=json.loads((root/'inputs/preregistration.json').read_text());result={}
for market,cfg in plan['markets'].items():
 frames={s:pd.read_csv(root/'inputs'/market/(s+'.csv'),index_col=0,parse_dates=True) for s in cfg['symbols']}
 panel={k:pd.DataFrame({s:f[k] for s,f in frames.items()}) for k in ('close','volume')}
 reg=get_default_registry();base=reg.compute('alpha101_012',panel);cut=base.index[len(base)//2]
 changed={k:v.copy(deep=True) for k,v in panel.items()}
 changed['close'].loc[changed['close'].index>cut]*=2.7
 changed['volume'].loc[changed['volume'].index>cut]*=3.1
 challenger=reg.compute('alpha101_012',changed)
 pd.testing.assert_frame_equal(base.loc[:cut],challenger.loc[:cut])
 result[market]={'status':'PASSED','cutoff':str(cut),'unchanged_past_rows':len(base.loc[:cut]),'perturbed':'future raw close and volume, then original Registry recomputation'}
(root/'poc/causality.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

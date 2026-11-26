"""Run unmodified Vibe modules inside a credential-free offline container.

This harness supplies local CSVs and a fixed signal-to-portfolio mapping; it
is not an upstream-provided strategy and is never an operational adapter.
"""
from pathlib import Path
import json,hashlib,time,traceback,os
import pandas as pd
ROOT=Path('/work');INPUT=ROOT/'inputs';plan=json.loads((INPUT/'preregistration.json').read_text());OUT=ROOT/'poc';OUT.mkdir(exist_ok=True)
os.environ['VIBE_TRADING_ALLOWED_RUN_ROOTS']=str(OUT)
os.environ['VIBE_TRADING_HYPOTHESES_PATH']=str(OUT/'hypotheses.json')
from src.factors.registry import get_default_registry
from backtest import runner
from src.research_lab import service
from src.hypotheses import HypothesisRegistry
from src.tools.autopilot_tool import RunResearchAutopilotTool,LinkAutopilotBacktestTool


def code():
 return '''import pandas as pd
from src.factors.registry import get_default_registry
class SignalEngine:
    def generate(self,data_map):
        panel={k:pd.DataFrame({s:f[k] for s,f in data_map.items()}) for k in ('close','volume')}
        values=get_default_registry().compute('alpha101_012',panel)
        signals=pd.DataFrame(0.0,index=values.index,columns=values.columns)
        for day,row in values.iterrows():
            chosen=row[row>0].sort_values(ascending=False,kind='stable').index[:4]
            signals.loc[day,chosen]=.2
        return {s:signals[s] for s in signals}
'''

start=time.monotonic();summary={'model_calls':0,'tokens':0,'network':'none','original_code_modified':False,'stages':{}}
bridge=[]
for market,contract in plan['markets'].items():
 for symbol,entry in contract['files'].items():
  path=INPUT/market/(symbol+'.csv')
  if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('input mutation')
  native=symbol+'.US' if market=='US' else symbol
  bridge.append({'symbol':native,'type':'csv','path':str(path)})
config=Path.home()/'.vibe-trading/data-bridge/config.yaml';config.parent.mkdir(parents=True,exist_ok=True);config.write_text(json.dumps({'sources':bridge}))
for market,contract in plan['markets'].items():
 try:
  frames={s:pd.read_csv(INPUT/market/(s+'.csv'),index_col='date',parse_dates=True) for s in contract['symbols']}
  panel={k:pd.DataFrame({s:f[k] for s,f in frames.items()}) for k in ('close','volume')}
  reg=get_default_registry();values=reg.compute('alpha101_012',panel);values.to_csv(OUT/(market+'_factor.csv'))
  formula=(panel['volume'].diff().apply(lambda x:x.map(lambda v:1 if v>0 else -1 if v<0 else 0 if pd.notna(v) else float('nan')))*-panel['close'].diff())
  error=float((values-formula).abs().max().max())
  directory=OUT/(market+'_native');(directory/'code').mkdir(parents=True,exist_ok=True);(directory/'code/signal_engine.py').write_text(code())
  names=[s+'.US' if market=='US' else s for s in contract['symbols']]
  cfg={'codes':['local:'+s for s in names],'source':'local','start_date':min(str(f.index.min().date()) for f in frames.values()),'end_date':contract['end'],
       'evaluation_start_date':contract['start'],'initial_cash':plan['contract'][market]['initial_capital'],'position_adjustment':'rebalance','allow_short':False,
       'slippage_us':.0005,'slippage':.0005}
  (directory/'config.json').write_text(json.dumps(cfg,indent=2));runner.main(directory)
  summary['stages'][market]={'status':'ORIGINAL_RUNNER_EXECUTED','formula_max_abs_error':error,'factor_shape':list(values.shape),'native_run':str(directory),
                            'metrics':json.loads((directory/'run_card.json').read_text()).get('metrics')}
 except Exception as exc:
  summary['stages'][market]={'status':'FAILED','type':type(exc).__name__,'reason':str(exc)};traceback.print_exc()
try:
 hyp=HypothesisRegistry().create(title='Frozen alpha101_012 diagnostic',thesis='A fixed volume/price reversal factor may have incremental value; efficacy unproven.',universe='US frozen Task3 stocks',signal_definition='alpha101_012 positive top4; D1; 20% each',data_sources=['local'])
 goal=json.loads(RunResearchAutopilotTool().execute(hypothesis_id=hyp.hypothesis_id,session_id='task6-pre-isolated'))
 link=json.loads(LinkAutopilotBacktestTool().execute(hypothesis_id=hyp.hypothesis_id,run_dir=str(OUT/'US_native'),notes='Historical diagnostic only; not independent Forward'))
 summary['research_workflow']={'hypothesis_id':hyp.hypothesis_id,'goal':goal,'backtest_link':link,'persisted_hypothesis':next(h for h in HypothesisRegistry().list() if h.hypothesis_id==hyp.hypothesis_id).to_dict()}
except Exception as exc:
 summary['research_workflow']={'status':'FAILED','type':type(exc).__name__,'reason':str(exc)};traceback.print_exc()
try:
 study=service.run('cost_sensitivity',{'run_dir':str(OUT/'US_native'),'scenarios':[{'name':'base','fee_multiplier':1},{'name':'fixed_adverse','fee_multiplier':2,'extra_slippage_bps':5}]})
 summary['cost_study']={'id':study.get('id'),'status':study.get('status'),'error':study.get('error'),'result':study.get('result')}
except Exception as exc:summary['cost_study']={'status':'FAILED','type':type(exc).__name__,'reason':str(exc)};traceback.print_exc()
summary['elapsed_seconds']=time.monotonic()-start
(OUT/'summary.json').write_text(json.dumps(summary,indent=2,default=str));print(json.dumps(summary,indent=2,default=str))

from pathlib import Path
import json,os,traceback
os.environ['VIBE_TRADING_ALLOWED_RUN_ROOTS']='/work'
from backtest import runner
from src.research_lab import service
from src.hypotheses import HypothesisRegistry
from src.tools.autopilot_tool import RunResearchAutopilotTool,LinkAutopilotBacktestTool
root=Path('/work');native=root/'native_run';result={}
try:
 runner.main(native);result['native_runner']='PASS';result['run_card']=json.loads((native/'run_card.json').read_text())
 hyp=HypothesisRegistry().list()[0];result['hypothesis_id']=hyp.hypothesis_id;result['autopilot']=json.loads(RunResearchAutopilotTool().execute(hypothesis_id=hyp.hypothesis_id,session_id='task6-completion'));result['linked_backtest']=json.loads(LinkAutopilotBacktestTool().execute(hypothesis_id=hyp.hypothesis_id,run_dir=str(native),notes='Original native overnight accounting; separate from aligned intraday V2; repeated2025 diagnostic.'))
 study=service.run('cost_sensitivity',{'run_dir':str(native),'scenarios':[{'name':'fixed_base','fee_multiplier':1},{'name':'fixed_stress','fee_multiplier':2,'extra_slippage_bps':5}]});result['research_lab']=study
except Exception as e:result['failure']={'type':type(e).__name__,'error':str(e)};traceback.print_exc()
(root/'native_result.json').write_text(json.dumps(result,indent=2,default=str));print(json.dumps(result,indent=2,default=str))

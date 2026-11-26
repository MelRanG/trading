from pathlib import Path
import json,traceback,threading
from quantaalpha.pipeline.loop import AlphaAgentLoop
from quantaalpha.pipeline.settings import AlphaAgentFactorBasePropSetting
try:
 loop=AlphaAgentLoop(AlphaAgentFactorBasePropSetting(),potential_direction='OHLCV input compatibility probe only; no LLM research calls permitted.',stop_event=threading.Event(),use_local=True)
 result={'status':'CONSTRUCTOR_OK','full_loop_executed':False,'reason':'Constructor only, no unbudgeted LLM or default CN backtest permitted'}
except Exception as e:
 result={'status':'BLOCKED_ORIGINAL_CONSTRUCTOR','type':type(e).__name__,'error':str(e),'trace':traceback.format_exc(),'full_loop_executed':False}
Path('/work/full_probe.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

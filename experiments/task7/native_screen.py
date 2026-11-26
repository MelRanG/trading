from pathlib import Path
import json,time
from src.tools.market_screener_tool import _screen_market
r={'source':'VIBE_ORIGINAL_EASTMONEY_SCREEN','status':'NOT_RUN','observed_epoch':time.time()}
try:r.update(status='SAVED',rows=_screen_market('us',sort_by='amount',top_n=30))
except Exception as e:r.update(status='FAILED',reason=str(e),error_type=type(e).__name__)
Path('/work/native_screen.json').write_text(json.dumps(r,indent=2,default=str));print(json.dumps(r,indent=2,default=str))

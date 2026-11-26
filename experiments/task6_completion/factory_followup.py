from pathlib import Path
import json,sys
sys.path.insert(0,'/oldcode');sys.path.insert(0,'/code')
from quanta_loop import Scenario
from quantaalpha.core.proposal import Trace
from quantaalpha.factors.proposal import AlphaAgentHypothesisGen
packet=json.loads(Path('/work/factory_followup_packet.json').read_text());scen=Scenario();direction='This request comes from the isolated OFFICIAL Factory result -> existing PostgreSQL FOLLOWUP queue. No promotion. Diagnose costs vs prediction vs insufficient evidence; propose one falsifiable next research task without claiming alpha. Actual record: '+json.dumps(packet)
h=AlphaAgentHypothesisGen(scen,potential_direction=direction).gen(Trace(scen));Path('/work/factory_followup_hypothesis.json').write_text(json.dumps(vars(h),indent=2,default=str));print(json.dumps(vars(h),indent=2,default=str))

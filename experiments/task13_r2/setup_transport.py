"""Historical one-time bootstrap; finalized transport is preserved alongside this file."""
raise SystemExit("Do not overwrite finalized R2 transport/relay. Use preserved files and model policy.")
from pathlib import Path
import json
R=Path(__file__).resolve().parents[2];D=R/'experiments/task13_r2'
s=(R/'experiments/task10/model_relay.py').read_text();s=s.replace('90000','40000').replace("reservations=list(directory.glob('*.reserved.json'))", "reservations=list(self.folder.glob('*/*.reserved.json'))")
s=s.replace("'--json','--output-schema'", "'-c','model_reasoning_effort=\"medium\"','--json','--output-schema'")
(D/'transport.py').write_text(s);(D/'contract.json').write_text(json.dumps({'budgets':{'rd':{'calls':12,'tokens':300000},'economic':{'calls':12,'tokens':300000}}}));(D/'model_policy.json').write_text(json.dumps({'scope_models':{'rd':'gpt-6-luna','economic':'gpt-6.1-terra'}}))
s=(R/'experiments/task13_r1/relay.py').read_text().replace("runtime/task13_r1'","runtime/task13_r2'").replace("R/'experiments/task10/model_relay.py'","R/'experiments/task13_r2/transport.py'").replace("m.BUDGET={'quanta':{'calls':20,'tokens':650000}}", "m.BUDGET=json.loads((R/'experiments/task13_r2/contract.json').read_text())['budgets']").replace('/tmp/quant-task13-r1.sock','/tmp/quant-task13-r2.sock');(D/'relay.py').write_text(s)
s=(R/'experiments/task13_r1/run_native.py').read_text().replace('task13_r1/','task13_r2/').replace("'experiments/task13_r1'","'experiments/task13_r2'").replace('quant-task13-r1-','quant-task13-r2-').replace('quant-task13-r1.sock','quant-task13-r2.sock');s=s.replace("'-v',str(R/'experiments/task6')+':/oldcode:ro',", "'-v',str(R/'experiments/task6')+':/oldcode:ro','-v',str(R/'runtime/task13_r2/contract.json')+':/spec/contract.json:ro',");(D/'run_native.py').write_text(s)

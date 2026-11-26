from common import *
from replay_factory import record
v=json.loads((B/'first_experiment.json').read_text());stage=v['proposal']['challenger'].replace('TASK10_','').replace('_ONE_CANDIDATE','');result=json.loads((B/'experiments'/stage/'validation.json').read_text());done=record(v,result);freeze(B/'experiments'/stage/'factory_result.json',done);print(result['status'],result['isolated_replay_gate_passed'],done.get('followup_done'),flush=True)

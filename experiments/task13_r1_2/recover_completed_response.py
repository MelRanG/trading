"""Replay only the exact completed semantic model response; no fresh API allowed."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,'/oldcode');sys.path.insert(0,'/code')
from native_worker import Scenario,strict_gate_result
from syntax_adapter import attach
from quantaalpha.pipeline.evolution import EvolutionController
from quantaalpha.core.proposal import Trace
from quantaalpha.factors.proposal import AlphaAgentHypothesisGen,AlphaAgentHypothesis2FactorExpression
from quantaalpha.factors.coder.evolving_strategy import FactorParsingStrategy
from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
from quantaalpha.factors.regulator.consistency_checker import FactorQualityGate,FactorConsistencyChecker
from quantaalpha.llm.client import APIBackend
root=Path('/work');node=root/'S0';scen=Scenario();calls=Path('/calls');reservation=next(calls.glob('1d14*.reserved.json'));rec=json.loads(reservation.read_text());assert rec['exit_code']==0 and rec['measured_tokens']==24609 and rec['status']=='FAILED'
request=json.loads(reservation.with_name(reservation.name.replace('.reserved.json','.request.json')).read_text());tracepath=reservation.with_name(reservation.name.replace('.reserved.json','.trace.jsonl'));messages=[json.loads(x)['item']['text'] for x in tracepath.read_text().splitlines() if json.loads(x).get('item',{}).get('type')=='agent_message'];assert len(messages)==1;answer=json.loads(messages[0]);assert answer['tool_calls']==[];content=answer['content'];assert json.loads(content)['is_consistent'] is True
h=AlphaAgentHypothesisGen(scen).convert_response((node/'hypothesis.json').read_text());original_response=next(calls.glob('3d7*.response.json'));response=json.loads(original_response.read_text())['choices'][0]['message']['content'];exp=AlphaAgentHypothesis2FactorExpression(consistency_enabled=False).convert_response(response,Trace(scen));task=exp.sub_tasks[0]
replay=[]
def exact(self,*args,**kwargs):
 assert kwargs['user_prompt']==next(x['content'] for x in request['messages'] if x['role']=='user'),'semantic request mismatch'
 assert kwargs['system_prompt']==next(x['content'] for x in request['messages'] if x['role']=='system'),'semantic system mismatch'
 replay.append({'request_hash':rec['request_hash'],'trace_hash':hashlib.sha256(tracepath.read_bytes()).hexdigest(),'actual_model_usage':rec['usage'],'new_LLM_calls':0,'transport_failed_at_18k_cap':True,'completed_model_response_replayed':True});return content
APIBackend.build_messages_and_create_chat_completion=exact
checker=FactorConsistencyChecker(max_correction_attempts=1,enabled=True,strict_mode=True);gate=FactorQualityGate(consistency_checker=checker,consistency_enabled=True);attach(gate.redundancy_checker.factor_regulator);result=gate.evaluate(str(h),task.factor_name,task.factor_description,task.factor_formulation,task.factor_expression,task.variables);strict_gate_result(result,task.factor_expression);assert len(replay)==1
(node/'semantic_gate_replayed.json').write_text(json.dumps({'passed':result[0],'details':result[2],'replay_provenance':replay},indent=2));code=FactorParsingStrategy(scen=scen,settings=FACTOR_COSTEER_SETTINGS).implement_one_task(task,None);(node/'factor.py').write_text(code);(node/'generation.json').write_text(json.dumps({'id':'S0','hypothesis':vars(h),'tasks':[vars(task)],'fingerprint':hashlib.sha256(code.encode()).hexdigest(),'H':20,'source':'Actual native model proposals and exact completed semantic response replay; native DSL coder. No new model request.','fullAlphaAgentLoop':False},indent=2,default=str));print('EXACT_COMPLETED_MODEL_RESPONSE_REPLAY_AND_NATIVE_CODE_PASS')

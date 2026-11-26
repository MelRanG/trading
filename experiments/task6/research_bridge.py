"""Research-only immutable handoff to the existing official Factory.

Never starts an experiment without Factory reservation. Never changes parent,
Paper settings, or live authority. Safe to resume the same frozen candidate.
"""
from pathlib import Path
import json,hashlib,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.alpha_research_factory import register_review_proposal,reserve_review_experiment
BASE=ROOT/'runtime/task6'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def freeze():
 path=BASE/'candidate_freeze.json'
 candidate={str(p.relative_to(BASE)):sha(p) for p in sorted((BASE/'candidates').rglob('factor.py'))}
 payload={'candidate_files':candidate,'contract_sha256':sha(ROOT/'experiments/task6/research_contract.json'),'evaluation_sha256':sha(ROOT/'experiments/task6/evaluation.py'),'split_manifest_sha256':sha(BASE/'split_manifest.json'),'blend_rule':'Exploratory fixed equal blend of positive-only within-market percentile ranks; latest valid attempt1, no outcome-selected weights. Defined after validation0, before final.','selection':'No engine promoted or final-selected. Compare all frozen candidates; last follow-up is fixed, not best-validation selection.','final_feedback_to_research':False,'promotion':'NOT_ELIGIBLE_CURRENT_COHORT_AND_NO_FORWARD'}
 if path.exists():
  if json.loads(path.read_text())!=payload:raise ValueError('immutable candidate freeze conflict')
 else:path.write_text(json.dumps(payload,indent=2))
 return payload

def register(payload):
 proposal={'problem_evidence':{'source':'actual 2025 process diagnostics and original generated hypotheses','reference':'runtime/task6/candidates','issue':'Initial factor portfolios did not establish net investment advantage; compare fixed follow-up research strategies in independent future observations.'},'target':'strategy','expected_effect':'Evaluate incremental usefulness of original specialist output against Vibe; effect unproven.','falsification':'No credible positive independent net excess performance or predictive information at fixed risk/cost, or causality/integrity failure.','champion':'VIBE_LIQUIDITY_REVERSAL_V1_FROZEN','challenger':'TASK6_NATIVE_SPECIALIST_FIXED_FOLLOWUPS_V1','input_hash':sha(BASE/'split_manifest.json'),'budget':{'experiments':1,'parameter_search':0},'stop_conditions':['missing PIT membership','final leakage','budget exhausted','causality failure'],'evaluation_metric':['net_return','excess','IC','MDD','cost','reproducibility'],'minimum_cases':12,'split':'PROCESS_DIAGNOSTIC_ONLY','worker_hash':payload['evaluation_sha256']}
 queue=BASE/'factory_handoff.json';receipt={'proposal':proposal,'candidate_freeze_sha256':sha(BASE/'candidate_freeze.json'),'status':'NOT_ATTEMPTED','prior_diagnostics_are_factory_experiment':False,'automatic_promotion':False}
 try:
  attempt=register_review_proposal(ROOT,proposal);receipt['attempt']=attempt;receipt['status']='REGISTERED'
  try:receipt['reservation']=reserve_review_experiment(ROOT,attempt);receipt['status']='RESERVED_NOT_EXECUTED'
  except ValueError as e:receipt.update(status='BLOCKED_EXPERIMENT_BUDGET',reason=str(e))
 except ValueError as e:receipt.update(status='BLOCKED_REGISTRATION',reason=str(e))
 queue.write_text(json.dumps(receipt,indent=2));return receipt
if __name__=='__main__':print(json.dumps(register(freeze()),indent=2))

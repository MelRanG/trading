"""Allowlisted deterministic workers; no generated-code execution or credentials."""
import hashlib
import json
from pathlib import Path
from .research import digest


def worker_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def integrity_champion(packet):
    # Task3 Store guarantees immutable JSON hash integrity, not field presence.
    return {'record_integrity':'VALID','trace_complete':True}


def trace_challenger(packet):
    required=('contract_hash','input_hash','algorithm_hash')
    return {'record_integrity':'VALID','trace_complete':all(bool(packet.get(k)) for k in required)}


def review_manifest_experiment(bundle):
    cases=bundle['cases']
    if not cases:return {'status':'INSUFFICIENT_EVIDENCE','cases':0,'metrics':{}}
    # Gold audit labels belong only to evaluator, not the proposal/generator.
    champion=[];challenger=[]
    for case in cases:
        packet=case['packet']
        champion.append(integrity_champion(packet)['trace_complete'])
        challenger.append(trace_challenger(packet)['trace_complete'])
    truth=[case['evaluator_trace_complete'] for case in cases]
    accuracy=lambda predictions:sum(p==t for p,t in zip(predictions,truth))/len(truth)
    return {'cases':len(cases),'metrics':{'champion_accuracy':accuracy(champion),'challenger_accuracy':accuracy(challenger),
            'champion_missed_defects':sum(p and not t for p,t in zip(champion,truth)),
            'challenger_missed_defects':sum(p and not t for p,t in zip(challenger,truth)),
            'model_calls_per_arm':0,'tokens_per_arm':0},
            'status':'INSUFFICIENT_EVIDENCE' if len(cases)<bundle['minimum_cases'] else 'FORWARD_REQUIRED' if accuracy(challenger)>accuracy(champion) else 'REJECTED',
            'scope':'REVIEW_TRACE_DIAGNOSTIC_NOT_INVESTMENT_EFFICACY',
            'biases':['small reused convenience sample','reference labels audit field completeness only','no return or alpha claim'],
            'holdout_used_for_proposals':False}


def evaluate(bundle):
    if bundle.get('worker')!='review_manifest_v1':
        return {'status':'INSUFFICIENT_EVIDENCE','cases':0,'metrics':{},'reason':'UNIMPLEMENTED_OR_UNREGISTERED_WORKER'}
    result=review_manifest_experiment(bundle)
    result['input_hash']=digest(bundle)
    result['worker_hash']=worker_hash()
    return result


if __name__=='__main__':
    import sys
    source,target=map(Path,sys.argv[1:])
    target.write_text(json.dumps(evaluate(json.loads(source.read_text())),sort_keys=True,allow_nan=False))

"""Executable data-only boundary PoC: one research worker, no order authority."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]


def proposal(signal_file,input_hash):
    path=Path(signal_file)
    return {'schema':'TASK6_PRE_CANDIDATE_V1','input_hash':input_hash,'output_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
       'origin':'VIBE_ORIGINAL_ALPHA101_012_PLUS_DECLARED_MAPPING','strategy_version':'0025531f005d4a7aac3fb884cda2fba9318e7158',
       'evidence_class':'REUSED_HISTORICAL_DIAGNOSTIC','status':'UNVERIFIED','order_authority':False,'promotion_authority':False}


def validate(candidate,expected_hash):
    if set(candidate)!={'schema','input_hash','output_sha256','origin','strategy_version','evidence_class','status','order_authority','promotion_authority'}:raise ValueError('data-only proposal fields required')
    if candidate['input_hash']!=expected_hash or candidate['order_authority'] is not False or candidate['promotion_authority'] is not False:raise ValueError('hash/authority boundary')
    if candidate['status']!='UNVERIFIED':raise ValueError('proposal cannot self-approve')
    return True


def main():
    result=json.loads((ROOT/'runtime/task6_pre/comparison/results.json').read_text());market=result['markets']['US'];signal=ROOT/'runtime/task6_pre/comparison/US/VIBE_ALPHA101_012_targets.csv'
    packet=proposal(signal,market['input_hash']);validate(packet,market['input_hash'])
    rejected=[]
    for change in ({'order_authority':True},{'promotion_authority':True},{'input_hash':'changed'},{'status':'APPROVED'},{'shell_command':'echo untrusted'}):
        try:validate({**packet,**change},market['input_hash'])
        except ValueError:rejected.append(change)
        else:raise ValueError('unsafe candidate accepted')
    report={'packet':packet,'boundary_rejections':rejected,'operational_database_calls':0,'factory_mutations':0,'orders':0,
      'alternatives':{'A':'Original Vibe local loader + native US/KR runner + original hypothesis/goal + artifact/Paper fixture tests',
         'B':'Original factor CSV to unchanged Quant replay under frozen cost/risk contract',
         'C':'B research output to hash-bound unverified data-only proposal; one future official Factory/ledger authority required'},
      'specialist_arms':{'original_vibe':'measured_non_LLM','vibe_plus_specialist':'NOT_RUN','quant_plus_same_specialist':'NOT_RUN','minimal_hybrid':'measured_boundary_only'},
      'limits':'This demonstrates an isolated interface, not a production migration, approved strategy or independent investment uplift.'}
    (ROOT/'runtime/task6_pre/evidence/exchange_contract.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()

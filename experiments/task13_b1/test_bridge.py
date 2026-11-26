from pathlib import Path
import sys,json,gzip,copy,hashlib
import pytest
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));sys.path.insert(0,str(R/'experiments/task13_b1'))
from features import guidance_change,contract_changes,policy_context
from quant_harness.investment.financial_packet import verify_fact
B=R/'runtime/task13_b1'
def read(n):return json.loads((B/n).read_text())

def test_same_guidance_metric_and_parent_guard():
 a,b=read('guidance_events.json')['events'];v=guidance_change(a,b);assert v['value']==-1 and v['magnitude'] is None
 bad=copy.deepcopy(b);bad['basis']='GAAP_REPORTED';
 with pytest.raises(AssertionError,match='IDENTITY'):guidance_change(a,bad)
 bad=copy.deepcopy(b);bad['explicit_previous']='at_least_4_percent'
 with pytest.raises(AssertionError,match='NOT_MATCHED'):guidance_change(a,bad)

def test_future_amendment_perturbation_cannot_change_2024_feature():
 data=read('contract_events.json');cut='2024-12-05T23:59:59+09:00';base=contract_changes(data['events'],cut);assert len(base)==1 and base[0]['delta_contract_KRW']=='262557900000'
 changed=copy.deepcopy(data['events']);changed[-1]['amount']='1';changed[-1]['previous_amount']='2';assert contract_changes(changed,cut)==base
 bad=copy.deepcopy(data['events']);bad[1]['previous_amount']='1'
 with pytest.raises(AssertionError,match='PARENT_AMOUNT'):contract_changes(bad,cut)

def test_unknown_vintage_macro_not_in_context_and_stale_rejected():
 data=read('macro_normalized.json');partial=[x for x in data if x['PIT']=='PIT_PARTIAL'];assert len(partial)==2
 x=policy_context(data,'2024-10-08T23:59:59-04:00');assert x['public_date']=='2024-09-18' and x['midpoint_pct']==4.875
 assert policy_context(partial,'2026-11-16T23:59:59Z') is None
 assert policy_context(data,'2025-12-15T23:59:59+09:00') is None
 assert policy_context(data,'2024-06-12T13:59:59-04:00') is None

def test_real_financial_numeric_provenance_and_original_inline():
 rows=read('US_fundamentals.json');n=matched=0
 for company in rows:
  for e in company['events']:
   for f in e['facts']:
    p=R/f['source_path'];raw=gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes();assert verify_fact(f,raw,f['published'])['verified_numeric_provenance'];assert f['original_accession']==e['event_id'];n+=1
    if f['inline_original_confirmed']:assert f['inline_proof'] and f['inline_source_hash'];matched+=1
 assert n==51 and matched==25
 for e in read('KR_fundamentals.json'):
  for f in e.get('facts',[]):
   p=R/f['source_path'];assert verify_fact(f,p.read_bytes(),f['published'])['verified_numeric_provenance']

def test_worker_allowlist_excludes_future_revisions_and_whole_companyfacts():
 data=read('worker_packets/KR_2024-12-05.json');assert len(data['records'])==2
 assert all('20251215' not in r['event_id'] for r in data['records'])
 for p in read('worker_packet_seal.json')['packets']:
  file=R/p['path'];assert hashlib.sha256(file.read_bytes()).hexdigest()==p['sha256'];packet=json.loads(file.read_text())
  assert all('companyfacts' not in s['path'] and 'submissions' not in s['path'] for s in packet['source_mount_allowlist'])
  assert packet['operations_permission'] is False

def test_factory_drafts_match_existing_contract_without_registration():
 cfg=json.loads((R/'config/task4_review_contract.json').read_text());data=read('factory_handoff_drafts.json');assert data['registration_calls']==data['ledger_writes']==0
 required={'problem_evidence','target','expected_effect','falsification','champion','challenger','input_hash','budget','stop_conditions','evaluation_metric','minimum_cases','split','worker_hash'}
 for item in data['drafts']:
  p=item['proposal'];assert required<=p.keys();assert p['minimum_cases']>=cfg['minimum_independent_cases'];assert p['budget']=={'experiments':1,'parameter_search':0};assert p['split']=='PROCESS_DIAGNOSTIC_ONLY';assert item['status']=='DRAFT_NOT_REGISTERED_NOT_EXECUTED'

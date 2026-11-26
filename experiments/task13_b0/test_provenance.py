"""Verify actual archived numeric provenance, temporal rejection and revision separation."""
from pathlib import Path
import json,sys,pytest
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.financial_packet import verify_fact
B=R/'runtime/task13_b0'

def test_actual_financial_sources_reject_tampering_and_future_cutoff():
 d=json.loads((B/'validation.json').read_text());n=0
 for e in d['earnings']:
  for f in e.get('facts',[]):
   raw=(R/f['source_path']).read_bytes();assert verify_fact(f,raw,f['published'])['verified_numeric_provenance'];n+=1
   with pytest.raises(ValueError,match='hash mismatch'):verify_fact(f,raw+b'changed',f['published'])
   with pytest.raises(ValueError,match='future'):verify_fact(f,raw,'2020-01-01')
 assert n==24

def test_contract_arithmetic_and_revision_not_merged():
 d=json.loads((B/'validation.json').read_text());first=next(x for x in d['contracts'] if x['receipt_no']=='20240123800494')
 assert first['contract_amount_KRW']=='496272700000';assert first['overall_PIT_grade']=='PARTIAL'
 later=d['revision_audit'];assert len(later)==2 and all(x['not_used_in_initial_event'] for x in later)
 assert any('758,830,600,000' in s for s in later[0]['rows'])
 assert any('873,400,000,000' in s for s in later[1]['rows'])
 assert d['economic_test']['return_test']=='NOT_RUN'

def test_prior_preliminary_earnings_blocks_false_new_event():
 d=json.loads((B/'validation.json').read_text());audit=d['earlier_earnings_audit'];assert len(audit)==2
 for x in audit:assert x['earlier_public_date']<x['quarterly_public_date']
 x=next(x for x in audit if x['earlier_public_date']=='2025-04-23');assert x['preliminary_vs_quarterly']['operating_profit']['delta_KRW']=='1000000';assert not x['preliminary_vs_quarterly']['operating_profit']['exact_match']
 assert d['cost']['LLM_calls']==0 and d['cost']['python_HTTP_attempts']<=36 and d['no_price_access']

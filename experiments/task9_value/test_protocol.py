from pathlib import Path
import json
import pytest
B=Path(__file__).resolve().parents[2]/'runtime/task9_value'

def test_all_selected_horizons_remain_visible_and_no_data_failures_become_zero():
 rows=json.loads((B/'evaluation/portfolios.json').read_text());assert len(rows)==3*2*3*4
 assert all(r['decision_hash'] and r['status']=='CALCULATED_PARTIAL' for r in rows)
 for r in rows:
  if r['mode']!='policy':assert sum(r['positions'].values())==pytest.approx(1)

def test_annual_chain_connects_identical_exit_and_next_entry_with_frozen_decisions():
 rows=json.loads((B/'evaluation/chained.json').read_text());assert len(rows)==8
 assert all(r['annual_research_segments']==3 and len(r['input_decision_hashes'])==3 for r in rows)

def test_all_financial_sources_match_fiscal_forecast_and_no_guidance_is_scored_as_actual():
 rows=json.loads((B/'evaluation/forecast_scores_v2.json').read_text());assert len(rows)==18 and all(r['status']=='SCORED_HISTORICAL_DIAGNOSTIC' for r in rows)
 for r in rows:
  if r['status'].startswith('SCORED'):
   assert r['forecast']['independent_of_guidance'] and r['actual'] is not None and r['source']
   assert r['forecast']['fiscal_year']==r['year']+1

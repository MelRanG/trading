"""Boundary and falsification checks kept separate from scored injections."""
from copy import deepcopy

import pytest

from experiments.task16_a.diagnose import diagnose
from experiments.task16_a.evidence import ROOT
from quant_harness.investment.review import policy, process_review
from quant_harness.investment.review_engine import propose, experiment_bundle


def test_existing_review_can_propose_trace_repair_without_factory():
    cfg=policy(ROOT)
    p={'source_decision_id':'SYNTHETIC_NATIVE_PROPOSAL','cutoff':'2025-01-02T16:00:00+09:00',
       'strategy_id':'MOM63_STOCKS','market':'KR','eligible':True,'intents':[],
       'weights':{},'registered_policy':{'gross_cap':.8,'single_name_cap':.2},
       'analysis':{'missing':[]},'evidence':[],'company_candidates':[],
       'contract_hash':'ct','input_hash':'it'}  # missing sealed algorithm
    r=process_review(p,cfg)
    decision=propose(r,experiment_bundle([p],cfg))
    assert decision['status']=='PROPOSED'
    assert decision['proposal']['target']=='review'
    assert 'investment return' in decision['proposal']['evaluation_metric']
    changed=deepcopy(p)
    changed['analysis']['actual_return']=-.9
    with pytest.raises(ValueError,match='outcome fields forbidden'):
        process_review(changed,cfg)


def test_future_evaluation_evidence_is_quarantined():
    c={'decision_as_of':'2025-01-02T16:00:00+09:00','evaluation_as_of':'2025-01-06T16:00:00+09:00',
       'facts':{'input_times':[{'available_at':'2025-01-07T09:00:00+09:00','used':True}],
                'provider_amount':1,'normalized_amount':1000,'certified_unit_factor':1}}
    result=diagnose(c,{}, {})
    assert result['primary_cause']=='UNDETERMINED'
    assert result['recommended_action']=='INSUFFICIENT_EVIDENCE'


def test_cost_proposal_requires_paired_independent_validation():
    c={'decision_as_of':'2025-01-02T16:00:00+09:00','evaluation_as_of':'2025-01-06T16:00:00+09:00',
       'facts':{'equal_policy_and_exposure':True,'gross_before':.02,'gross_after':.02,
                'cost_before':.005,'cost_after':.01,'net_before':.015,'net_after':.01,
                'cost_repeats':4,'mature_windows':4,'independent_validation_available':False}}
    assert not diagnose(c,{}, {})['research_required']
    c['facts']['independent_validation_available']=True
    assert diagnose(c,{}, {})['research_required']
    c['facts']['gross_after']=-.02
    assert not diagnose(c,{}, {})['research_required']


def test_closed_flow_variant_facts_do_not_create_same_proposal():
    c={'decision_as_of':'2025-01-02T16:00:00+09:00','evaluation_as_of':'2025-01-06T16:00:00+09:00',
       'facts':{'hypothesis_id':'renamed_flow', 'same_policy_delta':-.2, 'mature_windows':7}}
    result=diagnose(c,{}, {'FLOW5_50_50':'known'})
    assert result['recommended_action']=='MONITOR'
    assert result['research_scope'] is None

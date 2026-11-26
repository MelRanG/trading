"""Synthetic labels test the boundary; they are not Forward results."""
from copy import deepcopy
import pytest
from company_contract import score_forecast,audit_forecast
F={'ticker':'TEST','metric':'quarterly_revenue','period_end':'2026-09-30','unit':'USD_million','sealed_at':'2026-11-13T15:00:00+00:00','base_value':100,'bear_value':80,'bull_value':120}
L={'ticker':'TEST','metric':'quarterly_revenue','period_end':'2026-09-30','unit':'USD_million','released_at':'2026-11-20T12:00:00+00:00','observed_at':'2026-11-20T12:01:00+00:00','actual':110,'source_id':'SYNTHETIC_TEST_RELEASE','source_class':'OFFICIAL_ISSUER','verification_status':'VERIFIED','source_sha256':'a'*64}
def test_elapsed_period_and_schedule_do_not_mature():
 assert score_forecast(F,now='2027-01-01T00:00:00Z')['status']=='PENDING'
def test_future_release_not_available():
 assert score_forecast(F,L,now='2026-11-13T16:00:00Z')['status']=='PENDING'
def test_actual_release_errors_and_interval():
 r=score_forecast(F,L,now='2026-11-21T00:00:00Z')
 assert r['status']=='MATURE' and r['signed_error']==-10 and r['absolute_error']==10 and r['interval_covered']
@pytest.mark.parametrize('field,value',[('ticker','OTHER'),('metric','EPS'),('unit','USD'),('period_end','2026-12-31')])
def test_incompatible_label_fail_closed(field,value):
 label=dict(L);label[field]=value
 with pytest.raises(ValueError):score_forecast(F,label,now='2026-11-21T00:00:00Z')
def test_prior_release_not_independent_forward():
 label=dict(L);label['released_at']='2026-11-12T00:00:00Z'
 with pytest.raises(ValueError,match='not independent Forward'):score_forecast(F,label,now='2026-11-21T00:00:00Z')
def test_impossible_chronology_and_nonfinite():
 label=dict(L);label['observed_at']='2026-11-19T00:00:00Z'
 with pytest.raises(ValueError,match='chronology'):score_forecast(F,label,now='2026-11-21T00:00:00Z')
 label=dict(L);label['actual']=float('nan')
 with pytest.raises(ValueError,match='nonfinite'):score_forecast(F,label,now='2026-11-21T00:00:00Z')
def test_probability_and_scenario_order_errors():
 r={'scenarios':{k:{'probability':p,'revenue_million':v,'assumptions':'Synthetic test only'} for k,p,v in [('bull',.25,120),('base',.5,100),('bear',.25,80)]}}
 assert audit_forecast(r)['status']=='PROCESS_CHECKS_PASS'
 bad=deepcopy(r);bad['scenarios']['bull']['probability']=.8
 assert 'PROBABILITIES_NOT_SUM_ONE' in audit_forecast(bad)['issues']
 bad=deepcopy(r);bad['scenarios']['bear']['revenue_million']=140
 assert 'REVENUE_SCENARIO_ORDER' in audit_forecast(bad)['issues']
 assert audit_forecast(r)['hypothesis_error_from_profit_loss'] is False

def test_unverified_or_unhashed_label_is_rejected():
 for field in ['source_class','verification_status','source_sha256','source_id']:
  label=dict(L);label.pop(field)
  with pytest.raises(ValueError,match='verified official source'):score_forecast(F,label,now='2026-11-21T00:00:00Z')

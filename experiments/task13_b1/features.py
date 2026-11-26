"""Small deterministic event transforms. Never generates orders, labels or forecasts."""
from decimal import Decimal
from datetime import datetime,timedelta

def timestamp(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def asof(records,cutoff):return [r for r in records if timestamp(r['available_upper_bound'])<=timestamp(cutoff)]
def policy_context(records,cutoff,max_days=120):
 good=asof([r for r in records if r.get('PIT')=='VERIFIED_DATED_RELEASE'],cutoff)
 if not good:return None
 r=max(good,key=lambda x:timestamp(x['available_upper_bound']))
 if timestamp(cutoff)-timestamp(r['available_upper_bound'])>timedelta(days=max_days):return None
 return r

def guidance_change(parent,child):
 assert parent['issuer']==child['issuer'] and parent['fiscal_year']==child['fiscal_year'] and parent['metric']==child['metric'] and parent['basis']==child['basis'],'GUIDANCE_IDENTITY_MISMATCH'
 assert timestamp(parent['available_upper_bound'])<timestamp(child['available_upper_bound']),'FUTURE_PARENT'
 assert child['explicit_previous']==parent['current'],'PREVIOUS_GUIDANCE_NOT_MATCHED'
 if parent['current']=='approximately_4_percent' and child['current']=='low_single_digit':
  return {'feature':'explicit_downward_guidance_revision','value':-1,'magnitude':None,'reason':'Explicit same-FY same-metric change, qualitative endpoint not converted to invented numeric range','primary_H':20}
 raise ValueError('UNSUPPORTED_OR_AMBIGUOUS_GUIDANCE_CHANGE')

def contract_changes(records,cutoff):
 rows=sorted(asof(records,cutoff),key=lambda x:timestamp(x['available_upper_bound']));out=[]
 for parent,child in zip(rows,rows[1:]):
  assert parent['contract_id']==child['contract_id'],'DIFFERENT_CONTRACT'
  assert child['previous_public_date']==parent['public_date'],'BROKEN_PREVIOUS_DATE'
  assert Decimal(child['previous_amount'])==Decimal(parent['amount']),'REVISION_PARENT_AMOUNT_MISMATCH'
  assert parent['currency']==child['currency'] and parent['VAT_included']==child['VAT_included'],'BASIS_CHANGE'
  delta=Decimal(child['amount'])-Decimal(parent['amount']);out.append({'parent_id':parent['event_id'],'event_id':child['event_id'],'available_upper_bound':child['available_upper_bound'],'delta_contract_KRW':str(delta),'delta_vs_previous_contract_pct':float(delta/Decimal(parent['amount'])*100),'primary_H':60,'economic_scope_increment_verified':False,'not_a_new_contract_full_amount':True})
 return out

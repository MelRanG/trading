"""Only source-schema/period guards, no alpha or return evaluation."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit import original_annual_rows,unique,structural_annual_events

def rows():
 base={'start':'2018-01-01','end':'2018-12-31','filed':'2019-02-15','form':'10-K','fp':'FY','accn':'a','val':10}
 return base

def facts():
 b=rows();return {'us-gaap':{k:{'units':{'USD':[dict(b)]}} for k in ['NetIncomeLoss','NetCashProvidedByUsedInOperatingActivities']}}

def candidate():return {'id':'C2_CASH_ACCRUAL_QUALITY','required_tags':['NetIncomeLoss','NetCashProvidedByUsedInOperatingActivities','Assets']}

def test_asof_excludes_future_restated_comparative_and_amended():
 b=rows();d={'us-gaap':{'NetIncomeLoss':{'units':{'USD':[b,dict(b,filed='2023-02-15'),dict(b,filed='2020-02-15'),dict(b,form='10-K/A')]}}}}
 assert original_annual_rows(d,'NetIncomeLoss')==[b]

def test_quarter_cannot_substitute_annual_or_unit():
 b=rows();d={'us-gaap':{'NetIncomeLoss':{'units':{'USD':[dict(b,start='2018-10-01')],'shares':[b]}}}}
 assert original_annual_rows(d,'NetIncomeLoss')==[]

def test_missing_cash_flow_not_zero():
 d=facts();del d['us-gaap']['NetCashProvidedByUsedInOperatingActivities'];out,reject=structural_annual_events(d,candidate());assert out==[] and sum(reject.values())==1

def test_conflicting_value_fails_closed():
 d=facts();d['us-gaap']['NetIncomeLoss']['units']['USD'].append(dict(rows(),val=11));assert unique(d,'NetIncomeLoss',{'accn':'a','end':'2018-12-31'}) is None

def test_matched_source_metadata_only_no_score():
 d=facts();b=rows();d['us-gaap']['Assets']={'units':{'USD':[dict(b,end='2017-12-31',val=100),dict(b,end='2018-12-31',val=110)]}}
 result,reject=structural_annual_events(d,candidate());assert len(result)==1 and not reject
 assert 'signal' not in result[0] and 'value' not in result[0]
 assert result[0]['status']=='STRUCTURAL_MATCH_ONLY_NOT_PIT_ORIGINAL_SCOPE_APPROVED'

def test_different_accession_cash_flow_and_assets_not_mixed():
 d=facts();d['us-gaap']['NetCashProvidedByUsedInOperatingActivities']['units']['USD'][0]['accn']='different'
 assert structural_annual_events(d,candidate())[0]==[]

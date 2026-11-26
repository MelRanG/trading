from copy import deepcopy
import pytest
from replay_contract import source_eligible,replay_gate,guarded_replay,score_forecast,seal

def eligible():
 return {'coverage':dict.fromkeys(('historical_universe','listing_and_identifiers','official_sessions','eligible_execution_prices','actions_dividends_delistings','original_information_versions'),'VERIFIED'),'sources':[{'published_at':'2021-11-30T01:00:00Z','sha256':'a'*64,'original_version':True}],'information_cutoff':'2021-11-30T08:00:00Z','next_session_open':'2021-12-01T00:00:00Z','weights':{'FIXTURE':.1}}

def test_later_correction_is_not_historical_information():
 s={'published_at':'2022-01-01T00:00:00Z','sha256':'a','original_version':True}
 assert not source_eligible(s,'2021-11-30T08:00:00Z')
 s['published_at']='2021-10-01T00:00:00Z';s['original_version']=False;assert not source_eligible(s,'2021-11-30T08:00:00Z')

def test_date_only_release_conservative_delay_and_period_not_publication():
 s={'publication_date':'2021-11-30','publication_timezone_offset':'+09:00','sha256':'a','original_version':True}
 assert not source_eligible(s,'2021-11-30T06:30:00Z')
 assert source_eligible(s,'2021-11-30T15:00:00Z')
 assert not source_eligible({'period_end':'2021-09-30','sha256':'a','original_version':True},'2021-11-30T15:00:00Z')

@pytest.mark.parametrize('field',list(eligible()['coverage']))
def test_missing_required_coverage_blocks_execution_and_performance(field):
 p=eligible();p['coverage'][field]='PARTIAL';called=[];r=guarded_replay(p,lambda p:called.append(1));assert r['status']=='BLOCKED_DATA_QUALITY' and r['portfolio_return'] is None and not called

def test_verified_fixture_calls_existing_execution_adapter_only_after_gate():
 p=eligible();assert guarded_replay(p,lambda p:{'fixture_only':True})['result']['fixture_only'];p['next_session_open']=p['information_cutoff'];assert replay_gate(p)['status']=='BLOCKED_DATA_QUALITY'

def test_immutable_research_seal(tmp_path):
 p=tmp_path/'seal.json';h=seal(p,{'before':'outcome'});assert seal(p,{'before':'outcome'})==h
 with pytest.raises(ValueError):seal(p,{'after':'outcome'})

def test_no_premature_or_unit_mismatched_prediction_score():
 f={'company_id':'FIXTURE','metric':'revenue','period_start':'2022-01-01','fiscal_end':'2022-12-31','unit':'KRW_million','bear':80,'base':100,'bull':120,'forecast_origin':'INDEPENDENT_SCENARIO'};a={**f,'value':110,'published_at':'2023-03-01T00:00:00Z','source_hash':'fixture','original_version':True}
 assert score_forecast(f,a,'2021-11-30T00:00:00Z','2022-12-31T00:00:00Z')['status']=='PENDING'
 r=score_forecast(f,a,'2021-11-30T00:00:00Z','2023-03-02T00:00:00Z');assert r['absolute_error']==10 and r['price_prediction_accuracy'] is None
 a['unit']='KRW';
 with pytest.raises(ValueError):score_forecast(f,a,'2021-11-30T00:00:00Z','2023-03-02T00:00:00Z')

def test_original_cp949_declaration_and_partial_xml_recovery():
 from original_parser import text_and_identity
 raw='<?xml version="1.0" encoding="utf-8"?><DOCUMENT><COMPANY-NAME>당시회사</COMPANY-NAME><P>매출액 1,234 &cr; 원</P></DOCUMENT>'.encode('cp949')
 text,m=text_and_identity(raw);assert '매출액 1,234' in text and m['original_document_company']=='당시회사' and 'cp949' in m['encoding']


def test_actual_existing_replay_arithmetic_fixture_and_action_boundary():
 import pandas as pd,json
 from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec
 from replay_contract import run_existing_replay
 dates=pd.date_range('2021-11-29',periods=3,freq='D');close=pd.DataFrame({'FIXTURE':[100.,101.,102.]},index=dates);market={'close':close,'open':close,'adv20_d1':close*100000};ledger=pd.DataFrame({'target_weights_json':[json.dumps({'FIXTURE':.1}),json.dumps({})]});spec=ExecutionSpec(1,1,5,0,0,.01,1)
 packet=eligible();packet['verified_action_free_interval']=True
 result=run_existing_replay(packet,market,dates[1:],ledger,100000,spec);account,fills,intents=result['result'];assert len(fills)==2 and fills.side.tolist()==['BUY','SELL'] and len(account)==2
 packet['corporate_action_events']=[{'kind':'SPLIT'}];assert run_existing_replay(packet,market,dates[1:],ledger,100000,spec)['status']=='BLOCKED_EXECUTION_ACTION_ADAPTER'

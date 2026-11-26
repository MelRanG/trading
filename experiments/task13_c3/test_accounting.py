import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import accounting as a

def original(unit='USD',member='',cik='320193'):
 return f'''<html><body><xbrli:context id="flow"><xbrli:entity><xbrli:identifier>{cik}</xbrli:identifier>{member}</xbrli:entity><xbrli:period><xbrli:startDate>2019-01-01</xbrli:startDate><xbrli:endDate>2019-12-31</xbrli:endDate></xbrli:period></xbrli:context><xbrli:context id="start"><xbrli:entity><xbrli:identifier>{cik}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2018-12-31</xbrli:instant></xbrli:period></xbrli:context><xbrli:context id="end"><xbrli:entity><xbrli:identifier>{cik}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2019-12-31</xbrli:instant></xbrli:period></xbrli:context><xbrli:unit id="usd"><xbrli:measure>iso4217:{unit}</xbrli:measure></xbrli:unit><ix:nonFraction name="us-gaap:NetIncomeLoss" contextRef="flow" unitRef="usd" scale="6" sign="-">10</ix:nonFraction><ix:nonFraction name="us-gaap:NetCashProvidedByUsedInOperatingActivities" contextRef="flow" unitRef="usd" scale="6">20</ix:nonFraction><ix:nonFraction name="us-gaap:Assets" contextRef="start" unitRef="usd" scale="6">100</ix:nonFraction><ix:nonFraction name="us-gaap:Assets" contextRef="end" unitRef="usd" scale="6">200</ix:nonFraction></body></html>'''.encode()

def facts():return [{'metric':r,'tag':t,'period_start':s,'period_end':e,'value':v} for r,t,s,e,v in [('NI','NetIncomeLoss','2019-01-01','2019-12-31','-10000000'),('CFO','NetCashProvidedByUsedInOperatingActivities','2019-01-01','2019-12-31','20000000'),('Assets_start','Assets','2018-12-31','2018-12-31','100000000'),('Assets_end','Assets','2019-12-31','2019-12-31','200000000')]]

def test_sign_scale_unit_entity_and_feature():
 out,p=a.verify_original(facts(),original(),'320193',{'source_hash':'test'});assert p['pass'];assert out['AverageAssets']=='150000000';assert out['feature']=='0.2'

def test_wrong_currency_and_CIK_rejected():
 assert a.verify_original(facts(),original(unit='EUR'),'320193',{'source_hash':'x'})[0]is None
 assert a.verify_original(facts(),original(cik='999'),'320193',{'source_hash':'x'})[0]is None

def test_segment_and_wrong_period_not_group_context():
 assert a.verify_original(facts(),original(member='<xbrldi:explicitMember dimension="x">segment</xbrldi:explicitMember>'),'320193',{'source_hash':'x'})[0]is None
 assert a.verify_original(facts(),original().replace(b'2019-01-01',b'2019-04-01'),'320193',{'source_hash':'x'})[0]is None

def test_conflicting_original_values_not_picked():
 raw=original().replace(b'</body>',b'<ix:nonFraction name="us-gaap:NetIncomeLoss" contextRef="flow" unitRef="usd" scale="6">30</ix:nonFraction></body>');assert a.verify_original(facts(),raw,'320193',{'source_hash':'x'})[0]is None

def test_original_rawhash_and_future_packet_boundary():
 from quant_harness.investment.financial_packet import verify_fact
 import hashlib
 raw=b'{"x":10}';f={'metric':'NI','raw_value':'10','multiplier':1,'value':'10','unit':'CURRENCY','currency':'USD','basis':'CFS','period_start':'2019-01-01','period_end':'2019-12-31','published':'2020-02-01','source_hash':hashlib.sha256(raw).hexdigest(),'locator':{'kind':'json','path':['x']}}
 import pytest
 with pytest.raises(ValueError):verify_fact(f,raw,'2020-01-31')
 with pytest.raises(ValueError):verify_fact(f,b'{"x":11}','2020-02-01')
 assert verify_fact(f,raw,'2020-02-01')['verified_numeric_provenance']

def test_existing_C2_comparative_duplicate_and_revision_contract():
 base={'start':'2019-01-01','end':'2019-12-31','filed':'2020-02-01','accn':'x','fp':'FY','form':'10-K','val':10};d={'us-gaap':{'NetIncomeLoss':{'units':{'USD':[base,dict(base,filed='2022-02-01'),dict(base,form='10-K/A')]}}}};assert len(a.c2.original_annual_rows(d,'NetIncomeLoss'))==1

def test_legacy_SGML_instance_unit_and_scope():
 xml=b'''<?xml version="1.0"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2019"><xbrli:context id="f"><xbrli:entity><xbrli:identifier>320193</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2019-01-01</xbrli:startDate><xbrli:endDate>2019-12-31</xbrli:endDate></xbrli:period></xbrli:context><xbrli:unit id="u"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit><us-gaap:NetIncomeLoss contextRef="f" unitRef="u">-10000000</us-gaap:NetIncomeLoss></xbrli:xbrl>'''
 raw=b'<DOCUMENT><TYPE>EX-101.INS\n<TEXT><XBRL>\n'+xml+b'\n</XBRL></TEXT></DOCUMENT>'
 values,p=a.original_values(raw,'320193');assert p['entity_CIK_confirmed'] and len(values)==1;assert values[0]['value']=='-10000000' and values[0]['currency']=='USD'

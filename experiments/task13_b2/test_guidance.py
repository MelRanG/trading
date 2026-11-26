"""Source fidelity and fail-closed tests; no prices or outcome-based selection."""
import json,hashlib
from pathlib import Path
import pytest
from common import B,C,body
from parse_guidance import extract,compare,value,basis_matches

def parsed(symbol,day):
 row=json.loads((B/'collection'/f'{symbol}.json').read_text())
 event=next(e for e in row['parents']+row['targets'] if e['filing']['filingDate']==day)
 return extract(body(event['source']),row['company'],event['filing'],event.get('source_kind','SGML'),event.get('exhibit_filename'))

def one(symbol,day,fy):
 return next(x for x in parsed(symbol,day)['guidance'] if x['FY']==fy)

def test_frozen_contract_and_no_price_outcomes():
 assert hashlib.sha256((B/'contract.json').read_bytes()).hexdigest()==(B/'contract.sha256').read_text()
 assert C['H']==20 and len(C['companies'])==40
 if (B/'events_audited.json').exists():
  events=json.loads((B/'events_audited.json').read_text())
  gate=json.loads((B/'final_sample_gate.json').read_text())
  assert len(events)==300 and not gate['pass']
  assert all(x['H20_return'] is None for x in events)
 assert all(not r['price_outcomes_queried'] for r in json.loads((B/'events_classified.json').read_text()))

def test_pep_actual_source_original_two_versions():
 a,b=one('PEP','2022-02-10','2022'),one('PEP','2022-04-26','2022')
 assert a['value']['lo']=='6' and b['value']['lo']=='8'
 assert compare(a,b,'PEP','2022-04-26')=='UP'
 a,b=one('PEP','2024-07-11','2024'),one('PEP','2024-10-08','2024')
 assert a['value']['qualifier']=='approximately' and b['value']['lo'] is None
 assert compare(a,b,'PEP','2024-10-08')=='DOWN'

def test_coca_cola_separate_outlook_year_heading():
 a,b=one('KO','2022-02-10','2022'),one('KO','2022-04-25','2022')
 assert (a['value']['lo'],a['value']['hi'])==('7','8')
 assert compare(a,b,'KO','2022-04-25')=='UNCHANGED'

def test_pg_organic_not_reported_growth():
 a=one('PG','2022-01-19','2022')
 assert (a['value']['lo'],a['value']['hi'])==('4','5')

def test_operating_margin_cannot_be_primary_revenue():
 s='Adjusted operating income as a percentage of sales (adjusted operating margin) of 12.4 to 12.5% (previously 12.6 to 12.7%)'
 assert not basis_matches(s,'ANNUAL_REPORTED_TOTAL_REVENUE_GROWTH')

def test_realized_table_is_not_forecast():
 company={'metric_basis':'ANNUAL_ORGANIC_REVENUE_GROWTH'}
 raw=b'<html><h2>2024 Outlook</h2><p>We expect full-year organic sales growth of 4% to 6%.</p><table><tr><td>Organic Sales Growth</td><td>9.8%</td></tr></table></html>'
 d=extract(raw,company,{},'EXHIBIT_HTML','actual.html')
 assert len(d['guidance'])==1
 assert (d['guidance'][0]['value']['lo'],d['guidance'][0]['value']['hi'])==('4','6')

def test_missing_and_qualitative_are_not_imputed():
 assert value('Organic revenue growth low-single-digit')['lo'] is None
 assert value('Total sales of $90 billion') is None
 assert value('Organic revenue growth 10%+')['qualifier']=='at_least'
 assert value('Organic revenue growth 4% (versus our previous guidance of 6%)')['lo']=='4'
 a={'FY':'2024','basis':'organic','value':value('approximately 4%')}
 b={'FY':'2024','basis':'organic','value':value('at least 4%')}
 assert compare(a,b,'X','2024-07-01')=='AMBIGUOUS'
 b['FY']='2025'
 assert compare(a,b,'X','2024-07-01')=='NO_COMPARABLE_GUIDANCE'

def test_conflicting_values_fail_closed():
 raw=b'<html><h2>2024 Outlook</h2><p>We expect organic revenue growth of 4% to 6% for full-year 2024.</p><p>We expect organic revenue growth of 5% to 7% for full-year 2024.</p></html>'
 d=extract(raw,{'metric_basis':'ANNUAL_ORGANIC_REVENUE_GROWTH'},{},'EXHIBIT_HTML','x.html')
 assert not d['guidance'] and d['ambiguities']


def test_fx_drag_and_ex_covid_are_not_total_revenue_growth():
 assert not basis_matches('Merck anticipates full-year 2024 sales to be between $62.7 billion and $64.2 billion, including a negative impact of foreign exchange of approximately 2%.','ANNUAL_REPORTED_TOTAL_REVENUE_GROWTH')
 assert not basis_matches('Abbott projects full-year 2024 organic sales growth, excluding COVID-19 testing-related sales, to be 8% to 10%.','ANNUAL_ORGANIC_REVENUE_GROWTH')
 assert value('Organic sales growth towards the high end of 3% to 5%') is None

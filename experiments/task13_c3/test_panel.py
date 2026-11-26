"""Checks real panel clocks, mask-only H252 dates and no-request resume."""
import sys,json
from pathlib import Path
from decimal import Decimal
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import R,B,sha,sources
from collect import company

def test_real_panel_original_fields_clock_and_distinct_periods():
 rows=json.loads((B/'financial_panel.json').read_text())['rows'];seen=set()
 for r in rows:
  key=(r['CIK'],r['period_start'],r['period_end']);assert key not in seen;seen.add(key)
  assert r['period_end']<=r['filed']<='2022-12-31'
  assert pd.Timestamp(r['public_available_upper_bound']).date().isoformat()==r['filed']
  assert r['source_grade']=='ORIGINAL_DIMENSIONLESS_USD_CIK_FOUR_VALUES_VERIFIED'
  assert -(Decimal(r['NI'])-Decimal(r['OperatingCashFlow']))/((Decimal(r['Assets_start'])+Decimal(r['Assets_end']))/2)==Decimal(r['feature'])
 assert len(rows)>=150

def test_real_H252_calendar_bounds_no_price_values_used():
 data=json.loads((B/'label_availability.json').read_text());days=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(R/'runtime/task13_r0/accepted/US/^GSPC/quote.csv',usecols=['date']).date));days=days[days<='2024-12-31']
 for r in data['rows']:
  assert r['label_value'] is None
  if r['entry_session'] is None:continue
  i=days.get_loc(pd.Timestamp(r['entry_session']));assert r['filed']<r['entry_session']
  assert i==days.searchsorted(pd.Timestamp(r['filed']),side='right')
  if r['exit_H252_session']:assert days.get_loc(pd.Timestamp(r['exit_H252_session']))-i==252

def test_completed_company_resume_no_request_or_file_change():
 p=json.loads((B/'plan.json').read_text());a=p['pilot'][0];file=B/'companies'/(a['symbol']+'.json');before=sha(file);n=len(list((B/'requests').glob('*.json')))
 row=company(sources(),a,1);assert row['events'] and sha(file)==before
 assert len(list((B/'requests').glob('*.json')))==n

def test_economic_plan_and_user_request_ceiling_unchanged():
 plan=json.loads((B/'plan.json').read_text());assert sha(B/'plan.json')==(B/'plan.sha256').read_text().strip();assert plan['H']==252 and plan['direction']==1 and plan['HTTP_max']==300
 assert len(list((B/'requests').glob('*.json')))<=300
 assert len(plan['pilot'])==20 and len(plan['conditional_extension'])<=60

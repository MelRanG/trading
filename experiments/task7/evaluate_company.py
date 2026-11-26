from pathlib import Path
import json,math,re,sys,hashlib
from company_contract import audit_forecast
R=Path(__file__).resolve().parents[2];b=R/'runtime/task7';packet=json.loads((b/'company/packet.json').read_text());prices={c['ticker']:c['prices']['close'] for c in packet['cases']}
def canonical(f,symbol):
 metric=f['metric'].lower();p=f.get('period','').lower();v=float(f['value']);u=f.get('unit','')
 if 'close' in metric:return 'price',prices[symbol],'USD_per_share'
 if 'data center' in metric:return 'data_center_revenue',89000,'USD_million'
 if 'receivable' in metric:return 'receivables',63059,'USD_million'
 if 'gains' in metric and 'equity' in metric:return 'equity_gains',7771,'USD_million'
 if 'eps' in metric or 'earnings per' in metric:return ('non_gaap_eps',2.22,'USD_per_share') if 'non-gaap' in metric else ('gaap_eps',2.46,'USD_per_share')
 if 'free cash' in metric:return 'fcf',21341,'USD_million'
 if 'operating cash' in metric or 'cash provided by operating' in metric:return 'cfo',24077 if symbol=='NVDA' else 1975,'USD_million'
 if 'property' in metric:return 'capex',9441,'USD_million'
 if 'interest' in metric:return 'interest_expense',846,'USD_million'
 if 'net loss' in metric:return 'net_loss',-529 if 'adjusted' in metric else -709,'USD_million'
 if 'ebitda' in metric:return 'adj_ebitda',2256,'USD_million'
 if 'operating income' in metric:return ('adj_operating_income',379,'USD_million') if 'adjusted' in metric else ('gaap_operating_income',63734 if symbol=='NVDA' else 207,'USD_million')
 if 'gross margin' in metric:return 'gross_margin',75.,'percent'
 if 'backlog' in metric:return 'backlog_conditional',132500,'USD_million'
 if 'active power' in metric:return 'active_power_lower_bound',1.7,'GW'
 if 'revenue' in metric:
  if symbol=='NVDA':return 'revenue',96221,'USD_million'
  if '2025' in p:return 'prior_revenue',1365,'USD_million'
  if any(x in p for x in ['9m','nine','nine-month','nine month']):return 'nine_month_revenue',8314,'USD_million'
  return 'revenue',3661,'USD_million'
 raise ValueError('NOT_IN_LIMITED_GOLD_AUDIT')
result={'kind':'TWO_CASE_SOURCE_GROUNDED_PILOT_NOT_EFFICACY','gold_authority':'Issuer tables independently read; limited explicit metrics, not a blinded multi-reviewer semantic audit. Forecasts are assumptions, never gold facts.','comparability':['Same issuer snapshots, observed cutoff and actual Terra, common JSON objective, max6calls/260k perarm','Vibe earnings component batches2cases; other arms percase. Native CLI had different grounding behavior. Not a pure causal comparison of reasoning methods.','TA original independent bull/bear nodes plus schema synthesis; not fullGraph; FinRobot originalExpertInvestor withtoolkits unregistered; skills are a bundle subset.'],'arms':{}}
for arm in ['vibe_component','tradingagents','finrobot','skills']:
 rows={}
 for symbol in ['NVDA','CRWV']:
  path=b/'comparison'/arm/symbol/'analysis.json';record=json.loads(path.read_text());facts=[];verified=set();errors=[]
  for f in record.get('facts',[]):
   item={'reported':f}
   try:
    key,expected,unit=canonical(f,symbol);source_ok=f.get('source_id') in [symbol+'_IR','TOSS_ADJUSTED_DAILY'];numeric_ok=math.isclose(float(f['value']),expected,rel_tol=1e-8,abs_tol=1e-6) and f.get('unit')==unit
    item.update(canonical=key,source_valid=source_ok,numeric_and_unit_valid=numeric_ok,status='VERIFIED' if source_ok and numeric_ok else 'ERROR')
    if source_ok and numeric_ok:verified.add(key)
    else:errors.append(item)
   except (ValueError,TypeError,KeyError) as e:item.update(status='NOT_AUDITED',reason=str(e))
   facts.append(item)
  rows[symbol]={'verified_facts':sorted(verified),'verified_count':len(verified),'fact_errors':errors,'facts':facts,'forecast_process':audit_forecast(record),'future_accuracy':'PENDING','analysis_hash':hashlib.sha256(path.read_bytes()).hexdigest(),'prediction_notes':'Subjective forecast probabilities are not calibrated. No realized releases were supplied.'}
 result['arms'][arm]=rows
for arm,rows in result['arms'].items():
 for symbol,row in rows.items():
  base=set(result['arms']['vibe_component'][symbol]['verified_facts']);own=set(row['verified_facts']);row['incremental_verified_vs_vibe']=sorted(own-base);row['vibe_facts_omitted']=sorted(base-own)
(b/'comparison/evaluation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False));print(json.dumps({a:{s:{'verified':r['verified_count'],'incremental':r['incremental_verified_vs_vibe'],'errors':len(r['fact_errors']),'forecast':r['forecast_process']['status']} for s,r in rows.items()} for a,rows in result['arms'].items()},indent=2))

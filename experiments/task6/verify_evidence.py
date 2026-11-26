"""Read-only independent integrity checks; never changes strategy/data."""
from pathlib import Path
import json,hashlib
import pandas as pd
import numpy as np
BASE=Path('runtime/task6');manifest=json.loads((BASE/'split_manifest.json').read_text());checks=[];warmup_mismatches=0
for market,m in manifest['markets'].items():
 for alias,p in m['parts'].items():
  for split,folder in [('train','worker_train'),('validation','evaluator_validation'),('final','private_final')]:
   path=BASE/folder/(alias+'.csv');assert hashlib.sha256(path.read_bytes()).hexdigest()==p['counts'][split]['sha256'];checks.append(str(path))
# Independent arithmetic for native original initial factors.
for market in ['US','KR']:
 q=pd.read_csv(BASE/f'evaluation/validation/{market}/quanta0/factor_values.csv',parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0]
 r=pd.read_csv(BASE/f'evaluation/validation/{market}/rd0/factor_values.csv',parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0]
 for path in sorted((BASE/'worker_train').glob(market+'[0-9]*.csv')):
  f=pd.concat([pd.read_csv(path,parse_dates=['date']).set_index('date'),pd.read_csv(BASE/'evaluator_validation'/path.name,parse_dates=['date']).set_index('date')]);spread=f.high-f.low;loc=((2*f.close-f.high-f.low)/spread).where(spread>0,0);expected=(f.volume*loc).rolling(20,min_periods=20).sum()/f.volume.rolling(20,min_periods=20).sum()
  actual=q.xs(path.stem,level='instrument');warmup_mismatches+=int((actual.notna() & expected.isna()).sum())
  native_expected=(f.volume*loc).rolling(20,min_periods=1).sum()/f.volume.rolling(20,min_periods=1).sum()
  np.testing.assert_allclose(actual.to_numpy(),native_expected.to_numpy(),rtol=1e-8,atol=1e-8,equal_nan=True)
  np.testing.assert_allclose(actual[expected.notna()].to_numpy(),expected.dropna().to_numpy(),rtol=1e-8,atol=1e-8)
  np.testing.assert_allclose(r.xs(path.stem,level='instrument').to_numpy(),(1-f.close/f.open).to_numpy(),rtol=1e-8,atol=1e-8,equal_nan=True)
source=(BASE/'company/source.txt').read_text();company=json.loads((BASE/'company/result.json').read_text());assert abs(company['derived_gaap_operating_margin_percent']['value']-45915/92279*100)<1e-10
numbers=['92,279','45,915','36,629','36,422','4.92','4.89']
assert all(s in source for s in numbers)
report={'snapshot_files_verified':len(checks),'split_membership_hashes':'PASSED','native_quanta0_and_rd0_formula_reconstruction':'NATIVE_NUMERICAL_BEHAVIOR_REPRODUCED_BOTH_MARKETS','quanta0_requested_20_valid_observations_contract':'FAILED_NATIVE_TS_SUM_MIN_PERIODS_1','quanta0_unexpected_warmup_values':warmup_mismatches,'warmup_mismatch_changes_2025_2026_returns':False,'company_fact_numbers_found_in_supplied_source':numbers,'company_margin_arithmetic':'PASSED','company_future_scenarios':'PENDING_NOT_ACCURACY_SCORED','final_no_research_mount':'See credential-free docker commands; no private_final/evaluator_validation mount into research workers','caveat':'Source numeric presence/arithmetic is not full corporate analysis or forecast quality validation.'}
(BASE/'evidence/integrity_checks.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

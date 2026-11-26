"""Post-seal fiscal outcome collection; never sent back to historical worker."""
from pathlib import Path
import json,sys
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);c=OpenDartClient();B=R/'runtime/task9_value';assert (B/'decision_seals.json').exists()
catalog=json.loads((R/'runtime/task8b/discovery/kr_catalog.json').read_text())['rows']
for y in [2021,2022,2023]:
 for company in json.loads((B/'decisions'/(str(y)+'.json')).read_text())['decision']['companies']:
  if company['market']!='KR':continue
  s=company['symbol'];target=int(company['forecast']['fiscal_year']);folder=B/'evaluator_only'/s;p=folder/('actual_'+str(target)+'.json')
  if p.exists():continue
  corp=next(x['corp_code'] for x in catalog if x['stock_code']==s.split('.')[0])
  try:
   raw=c._request('fnlttSinglAcntAll.json',{'corp_code':corp,'bsns_year':str(target),'reprt_code':'11011','fs_div':'CFS'});p.write_text(json.dumps(raw,ensure_ascii=False));print(s,target,raw.get('status'),[(x['account_id'],x['account_nm'],x.get('thstrm_amount'),x.get('account_detail')) for x in raw.get('list',[]) if x['account_id'] in ['ifrs-full_Revenue','ifrs-full_DilutedEarningsLossPerShare','ifrs-full_BasicEarningsLossPerShare']],flush=True)
  except Exception as e:print(s,target,type(e).__name__,flush=True)

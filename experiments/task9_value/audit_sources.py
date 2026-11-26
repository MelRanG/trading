from pathlib import Path
import json,hashlib,sys
from datetime import datetime,timezone
import pandas as pd
from dotenv import dotenv_values
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_value';rows=[];portfolios=json.loads((B/'evaluation/portfolios.json').read_text())
for x in json.loads((B/'evaluation/stock_outcomes.json').read_text()):
 s=x['symbol'];a=pd.read_csv(B/'evaluator_only'/s/'bars.csv').set_index('date');y=pd.read_csv(B/'prices'/s/'bars.csv').set_index('date');p=next(r for r in portfolios if r['year']==x['year'] and r['market']==x['market'] and r['months']==x['months']);diff=max(abs(float(a.loc[d,'open'])-float(y.loc[d,'open'])) for d in [p['entry'],p['exit']]);rows.append({'year':x['year'],'market':x['market'],'symbol':s,'months':x['months'],'max_endpoint_open_difference_currency_units':diff,'within_currency_rounding':diff<=(1 if x['market']=='KR' else .010001)})
assert len(rows)==54 and all(x['within_currency_rounding'] for x in rows)
p=B/'evaluation/price_endpoint_audit.json'
if p.exists():assert json.loads(p.read_text())==rows
else:p.write_text(json.dumps(rows,indent=2))
raws=[p for p in B.rglob('*') if p.is_file() and (p.suffix in ['.raw','.pdf','.zip'] or p.name in ['chart.json','raw.json','toss_reference.raw.json'] or p.name.startswith('page_'))]
source_inventory=[{'path':str(p.relative_to(R)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'local_write_time_UTC_not_historical_receipt':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),'bytes':p.stat().st_size} for p in sorted(raws)]
(B/'source_inventory.json').write_text(json.dumps(source_inventory,indent=2))
secrets=[(k,v.encode()) for k,v in dotenv_values(R/'.env').items() if v and len(v)>15 and any(n in k.upper() for n in ['API_KEY','SECRET','PASSWORD','TOKEN'])];hits=[]
for base in [B,R/'experiments/task9_value']:
 for p in base.rglob('*'):
  if p.is_file():
   data=p.read_bytes()
   for k,v in secrets:
    if v in data:hits.append({'path':str(p.relative_to(R)),'name':k})
assert not hits,'Credential text found; do not publish affected artifact'
(B/'credential_audit.json').write_text(json.dumps({'private_credential_hits':0,'values_printed_or_stored':False},indent=2))
counts={'Yahoo_price_GET':{'successful_archived':len(list((B/'prices').glob('*/raw/*.receipt.json'))),'failed_WBA_attempts':3,'diagnostic_GET':len(list((B/'diagnostics').glob('*.receipt.json'))),'initial_limit':56},'Toss_candle_GET':{'precutoff_references':len(list((B/'deep').glob('*/*/toss_reference.raw.json'))),'failed_1000_bar_attempts':len(list((B/'evaluator_only').glob('*/receipt.json'))),'diagnostic_400':1,'valid_pagination':len(list((B/'evaluator_only').glob('*/page_*.json'))),'amended_limit':110},'DART_GET':{'original_list_document_accounts':27,'annual_actuals':9,'limit':70},'source_limit_note':'Archival counts for host financial data endpoints; browser requests, authentication and network-level retries are not an exact aggregate network census'}
counts['Yahoo_price_GET']['estimated_actual_attempts']=sum(counts['Yahoo_price_GET'][k] for k in ['successful_archived','failed_WBA_attempts','diagnostic_GET']);counts['Toss_candle_GET']['actual_data_attempts']=sum(counts['Toss_candle_GET'][k] for k in ['precutoff_references','failed_1000_bar_attempts','diagnostic_400','valid_pagination'])
(B/'source_usage.json').write_text(json.dumps(counts,indent=2));print('54 price checks PASS; credential hits0; raw sources',len(source_inventory));print(json.dumps(counts,indent=2))

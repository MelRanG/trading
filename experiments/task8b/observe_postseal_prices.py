"""New observation after seal. Never rewrites sealed hypotheses or entry intents."""
from pathlib import Path
from datetime import datetime,timezone
import json,sys,hashlib
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.investment.exploration import research_store
from quant_harness.investment.review_jobs import Queue
from quant_harness.investment.opportunity import value_scenario
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
b=R/'runtime/task8b';path=b/'postseal_price_observation.json'
if path.exists():print('USE_EXISTING_POSTSEAL_OBSERVATION');raise SystemExit(0)
load_environment(R);opps=json.loads((b/'final_opportunities.json').read_text());client=TossOpenApiClient();raw=client._request('GET',client.endpoint_map.quote_path,query={'symbols':','.join(c['ticker'].split('.')[0] if c['market']=='KR' else c['ticker'] for c in opps['cases'])});encoded=json.dumps(raw,sort_keys=True).encode();(b/'postseal_quotes.raw.json').write_bytes(encoded);observed=datetime.now(timezone.utc).isoformat();values=json.loads((b/'conditional_values.json').read_text());rows=[]
for c in opps['cases']:
 native=c['ticker'].split('.')[0] if c['market']=='KR' else c['ticker'];q=next(r for r in raw['result'] if r['symbol']==native and r['currency']==('USD' if c['market']=='US' else 'KRW'));current=float(q['lastPrice']);updates=[]
 for row in values.get(c['ticker'],{}).get('scenarios',[]):
  updates.append({'spec':row['spec'],'value':value_scenario(row['spec'],current)})
 rows.append({'ticker':c['ticker'],'original_reference':c['current_price'],'new_observed_price':current,'event_at':q['timestamp'],'observed_at':observed,'valuation_update':updates,'sealed_classification_unchanged':c['status'],'new_opportunity_selection':False})
result={'observed_at':observed,'source_hash':hashlib.sha256(encoded).hexdigest(),'scope':'AFTER_SEAL_NEW_PRICE_OBSERVATION_NOT_BACKDATED_SIGNAL','rows':rows,'quote_state':'Market closed; last trade may be afterhours, not an executable regular-session quote','bootstrap_provider_calls_total':19};path.write_text(json.dumps(result,indent=2));store,cfg=research_store(R);identity=store.put('opportunity_postseal_price_observation',result);Queue(store).enqueue('TASK9_NEW_PRICE_REEVALUATION',{'source_record_id':identity,'reason':'Newly observed prices; sealed decisions preserved, no automatic promotion'});print(json.dumps({r['ticker']:r['new_observed_price'] for r in rows},indent=2))

"""After-seal operating forecast check, independent from unexecuted price returns."""
from pathlib import Path
import sys,json,hashlib
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_historical';sys.path.insert(0,str(Path(__file__).parent))
from replay_contract import score_forecast,seal
W=Path('/home/ansy/app/quant-diligence/task9-historical-work');pred=json.loads((W/'A2_202111.json').read_text());meta=json.loads((B/'evaluator_only/outcome_manifest.json').read_text());api=json.loads((B/'evaluator_only/structured_2022.json').read_text());text=(B/'evaluator_only/original_2022.txt').read_text();results=[]
assert meta['api_original_accession_match'],'Current API does not refer to original released annual report'
c=next(c for c in pred['candidates'] if c['accession']==meta['forecast_accession'])
sealed=seal(B/'seals/A2_202111.json',pred)
for f in c['forecasts']:
 tag={'revenue':'ifrs-full_Revenue','operating_profit':'dart_OperatingIncomeLoss'}[f['metric']];rows=[r for r in api['list'] if r['account_id']==tag and r['sj_div'] in ('IS','CIS')]
 if len(rows)!=1:results.append({'metric':f['metric'],'status':'BLOCKED_AMBIGUOUS_STATEMENT'});continue
 row=rows[0];value=int(row['thstrm_amount'].replace(',',''));assert format(value,',') in text,'Structured outcome not found in original accession text'
 assert row.get('currency')=='KRW'
 assert row['bsns_year']=='2022' and row['reprt_code']=='11011'
 actual={'company_id':meta['company_id'],'metric':f['metric'],'period_start':'2022-01-01','fiscal_end':'2022-12-31','unit':'KRW_million','value':value/1000000,'published_at':'2023-03-20T15:00:00Z','source_hash':json.loads((B/'evaluator_only/original_2022.receipt.json').read_text())['source_hash'],'original_version':True}
 score=score_forecast({**f,'company_id':meta['company_id']},actual,'2021-11-30T23:59:59Z','2026-11-14T00:00:00Z')
 naive={'revenue':15731.856*4/3,'operating_profit':953.338749*4/3}[f['metric']]
 results.append({'metric':f['metric'],'prediction':f,'actual':actual,'score':score,'same_information_simple_9m_annualization':{'base':naive,'absolute_error':abs(naive-actual['value']),'relative_absolute_error':abs(naive-actual['value'])/abs(actual['value'])},'not_a_clean_predictive_test':'Historical LLM knowledge and one purposive original-filing cohort; no statistical superiority claim'})
result={'prediction_seal':sealed,'selected_before_future_outcome':True,'outcome_knowledge_not_in_worker_mount':True,'quality':'PARTIAL_HISTORICAL_OPERATING_SCENARIO_CHECK','results':results,'guidance_and_consensus_comparison':'MISSING_ARCHIVED_INDEPENDENT_CONSENSUS; no fabricated benchmark','portfolio_accuracy':None};(B/'evaluation/forecast_scores.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))

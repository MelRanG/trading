from protocol import *
research_seal();rows=[]
for m in ['US','KR']:
 d=json.loads((B/'worker_results'/('discover_'+m+'.json')).read_text());final=json.loads((B/'research'/(m+'.json')).read_text());old=json.loads((R/'runtime/task9_3/screens'/(m+'.json')).read_text());oldnames={x['symbol'] for x in old};deeps=[x for x in json.loads((B/'deep_packets_v2.json').read_text()) if x['market']==m]
 rows.append({'market':m,'initial_discovered_count':len(d['broad_candidates']),'deeper_selected_count':len(d['deep_candidates']),'final_promising_count':len(final['selected']),'old_Task93_screen_count':len(old),'selected_outside_old_screen':[x['symbol'] for x in final['selected'] if x['symbol'] not in oldnames],'all_broad_candidates':d['broad_candidates'],'deeper_candidates':d['deep_candidates'],'not_selected_final':final['not_selected'],'financial_typed_fact_count':sum(len(x['verified_facts']) for x in deeps),'deep_cases_with_asof_price':sum('asof_price' in x for x in deeps),'final_targetprice_scenario_count':sum(x['valuation'].get('scenarios_or_null') is not None for x in final['selected']),'broad_industry_labels_not_standard_GICS':sorted(set(x['industry'] for x in d['broad_candidates']))})
freeze(B/'discovery_audit.json',rows)
qa=[]
for p in (B/'evaluator_only').glob('*/quality.json'):
 q=json.loads(p.read_text());qa.append({'symbol':q['symbol'],'original_status':q['status'],'rows':q['rows'],'failures':q['failures'],'dividends':len(q.get('events',{}).get('dividends',{})),'splits':len(q.get('events',{}).get('splits',{}))})
freeze(B/'evaluation_v2/source_quality_summary.json',qa)
print([(x['market'],x['initial_discovered_count'],x['deeper_selected_count'],x['financial_typed_fact_count'],x['selected_outside_old_screen']) for x in rows])

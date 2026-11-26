from common import *
W=Path('/home/ansy/app/quant-diligence/task9-4-work');p=B/'requests/final_KR.request.json';q=json.loads(p.read_text());v=json.loads(q['messages'][1]['content']);d=v['discovery']
v['discovery']={k:d[k] for k in ['market','asof','market_industry_direction']};v['discovery']['broad_candidates']=[{k:x[k] for k in ['name','symbol','industry','discovery_evidence_ids','status'] if k in x} for x in d['broad_candidates']]
v['discovery']['deep_candidates']=[{k:x[k] for k in ['name','symbol','industry'] if k in x} for x in d['deep_candidates']]
# Deduplicate repeated exact metric names/labels, not values or capital fields.
metricdictionary={};reverse={}
for x in v['deeper_packets']:
 rows=[]
 for metric,label,value,unit,group in x['numeric_rows']:
  k=(metric,label)
  if k not in reverse:reverse[k]=str(len(reverse));metricdictionary[reverse[k]]=[metric,label]
  rows.append([reverse[k],value,unit,group])
 x['numeric_rows']=rows;x['numeric_columns']=['metric_dictionary_key','value','unit','group_id'];x.pop('business',None)
v['numeric_metric_dictionary_columns']=['metric','label'];v['numeric_metric_dictionary']=metricdictionary
q['messages'][1]['content']=json.dumps(v,ensure_ascii=False,separators=(',',':'));print('retrychars',len(json.dumps(q)));assert len(json.dumps(q))<145000
stage='final_KR_compact';freeze(B/'requests'/(stage+'.request.json'),q);freeze(W/(stage+'.request.json'),q)
freeze(B/'KR_retry_provenance.json',{'original_input_hash':sha(p),'retry_input_hash':sha(B/'requests'/(stage+'.request.json')),'failed_record':'282aea77da66597a2731cff93ceb35b34de6d85777963dcf246fd34d98fa93e9','failure':'100955measured_tokens>90000percall; validgenerationnotdelivered; FAILEDretained','numeric_values_retained':True,'deduplication':'Metric names/labels dictionary, all percompanyvalues/units/periods/sourcehashretained. Broad narrative reduced tooriginalsourceIDs; annualbusinessexcerptsremoved, primarydatednewskept.','max_total_calls':8,'no_future_prices_queried':True})

"""Seal measured resources, all proposal attempts and read-only old evidence audit."""
from pathlib import Path
import hashlib,json,datetime,subprocess
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,x):(B/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
usage={}
for engine in ['quanta','rd']:
 records=[json.loads(p.read_text()) for p in (B/'model_calls'/engine).glob('*.reserved.json')];usage[engine]={'actual_calls':len(records),'input_tokens':sum(x.get('usage',{}).get('input_tokens',0) for x in records),'output_tokens':sum(x.get('usage',{}).get('output_tokens',0) for x in records),'cached_input_tokens':sum(x.get('usage',{}).get('cached_input_tokens',0) for x in records),'total_measured_tokens':sum(x.get('measured_tokens',0) for x in records),'statuses':[x['status'] for x in records],'models':list({x['model'] for x in records}),'elapsed_call_seconds':sum(x.get('elapsed_seconds',0) for x in records),'cash_cost':'UNKNOWN_Codex_auth_not_library_GPT4o_estimate'}
usage.update({'Vibe_calls':0,'data_requests':0,'no_new_installs':True,'new_neural_model_fits':2,'neural_intermediate_checkpoint_recovery':True,'native_call_budget_respected':True,'proposal_budget_overrun':'Native converter returned6Quanta proposals vs5requested,9total vs8preregistered. Five executed candidates, four unexecuted proposals preserved; no further calls after gate.','CPU':'No cumulativeCPU meter; per-container2cores4GB. Do not infer CPU from model elapsed time.'});save('usage.json',usage)
ledger=[]
for node in sorted((B/'native/quanta').glob('Q[0-9]*')):
 p=node/'all_proposed_tasks.json'
 if not p.exists():continue
 d=json.loads(p.read_text());g=json.loads((node/'generation.json').read_text()) if (node/'generation.json').exists() else None
 for i,t in enumerate(d['tasks']):ledger.append({'attempt_id':node.name+'_'+str(i),'phase':json.loads((node/'attempt.json').read_text())['phase'],'name':t['factor_name'],'expression':t['factor_expression'],'proposal_hash':hashlib.sha256(json.dumps(t,sort_keys=True).encode()).hexdigest(),'state':'EXECUTED' if i==0 and g else 'UNEXECUTED_EXTRA_OR_CAP','code_hash':g['fingerprint'] if i==0 and g else None,'source':str(p.relative_to(R)),'selected_before_score':i==0})
seal=json.loads((B/'candidate_seal.json').read_text());diag=json.loads((B/'diagnostics/initial_diagnostics.json').read_text());handoff=[]
for c in seal['candidates']:
 for m in ['US','KR']:
  if c['id']=='RD_SMALL':v=diag['model_adjusted_track'][m]['RD_SMALL'];causal=diag['model_adjusted_track'][m]['causality'];track='ADJUSTED_2025_H5';reason='Small native linear; US near originalRidge, KR worse thanZero. Epoch history gap disclosed; not model-engine superiority.'
  else:v=next(x for x in diag['nominal_candidates'] if x['id']==c['id'] and x['market']==m);causal={'prefix':True,'future_perturbation':True};track='NOMINAL_2026_H20';reason='Exposed smallcohort and weak/crossmarket unstable diagnostic; strict input-window mask required. Q1/ROC strongly correlated.'
  source_hash=sha(B/'adjusted_inputs'/(m+'.csv')) if c['id']=='RD_SMALL' else sha(B/'nominal_inputs'/m/'panel.csv')
  binding={'code_hash':c['code_hash'],'input_hash':source_hash,'contract_hash':sha(B/'contract.json'),'H':5 if c['id']=='RD_SMALL' else 20,'evaluator_hash':sha(R/'experiments/task13/diagnose_worker.py'),'checkpoint_hash':diag['model_adjusted_track'][m]['training']['checkpoint_hash'] if c['id']=='RD_SMALL' else None}
  fingerprint=hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest()
  handoff.append({'candidate_fingerprint':fingerprint,'binding':binding,'id':c['id'],'market':m,'state':'INSUFFICIENT_EVIDENCE','technical_calculation':'PASS','Task14_diagnostic_admissible':True,'independent_confirmation_ready':False,'track':track,'code_hash':c['code_hash'],'rows':v['rows'],'dates':v['dates'],'H':5 if c['id']=='RD_SMALL' else 20,'reason':reason,'no_promotion':True})
save('attempt_ledger.json',{'all_quanta_proposals':ledger,'executed_candidate_count':5,'total_proposals_including_library_model':9,'unexecuted_count':4,'neural_or_Qlib_controls_are_baselines_not_extra_RD_generated_alphas':['ZERO','QLIB_RIDGE','QLIB_TREE'],'known_adapter_failures':['PyTables missing in host; usedCSV transport +existing isolatedHDF env','Quanta multi-expression first attempt fail and bounded resume','OriginalQlib needs internalvalid, then LGB dataset.segments','LGB tracking requiresqlib.init; localMLflow filestore explicitoptin (no newDB/service)','Vibe env lackedQlib; reusedexistingQuanta env with originalVibe source','One hostlauncher comment/newline error','Per-epoch neural history lost on downstreamcontrol failure; checkpoints recovered; selected actualloss measured'],'generation_closed':True})
save('task14_handoff.json',{'contract_hash':sha(B/'contract.json'),'candidate_seal_hash':sha(B/'candidate_seal.json'),'candidates':handoff,'all_attempts':'runtime/task13/attempt_ledger.json','comparison_rule':'Engine roles not alphaquality; adjustedH5 vsnominalH20 are separate tracks, never rank their metrics as samecondition. No native controller/fullfinquant claim.'})
old=[]
for f in ['runtime/task6_completion/evidence/artifact_manifest.json','runtime/task10/artifact_manifest.json','runtime/task12/artifact_manifest.json']:
 d=json.loads((R/f).read_text());bad=[v['path'] for v in d['files'] if sha(R/v['path'])!=v['sha256']];assert not bad,(f,bad);old.append({'path':f,'entries':len(d['files']),'mismatches':bad})
save('preservation.json',{'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'old_manifests':old,'no_operating_source_modified':True,'old_forward_contract_hash':sha(R/'runtime/task10_1/forward/contract.json'),'current_forward_source_hash':sha(R/'experiments/task10_1/forward.py'),'Task12_expected_source_hash':json.loads((R/'runtime/task12/forward_patch.json').read_text())['new_source_hash']});assert sha(R/'experiments/task10_1/forward.py')==json.loads((R/'runtime/task12/forward_patch.json').read_text())['new_source_hash']
print('CALLS',usage['quanta']['actual_calls'],usage['rd']['actual_calls'],'TOKENS',usage['quanta']['total_measured_tokens']+usage['rd']['total_measured_tokens'],'VALID_CANDIDATES',5,'RAW_PROPOSALS',9)

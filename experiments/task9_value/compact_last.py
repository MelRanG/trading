from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_value';W=Path('/home/ansy/app/quant-diligence/task9-value-work')
original=json.loads((W/'deep2_2023.request.json').read_text());body=json.loads(original['messages'][1]['content']);p=body['input'];p.pop('session_input_hash')
for case in p['cases']:
 source=case['source'];source.pop('receipt',None);source.pop('original_identity',None)
 for e in source['excerpts']:
  e['text']=e['text'][:(5000 if case['candidate']['market']=='US' else (2000 if e['label']=='financial_summary' else 700))]
 keys=['account_id','thstrm_amount','thstrm_add_amount','frmtrm_amount','currency'];source['accounts']=[{k:a.get(k) for k in keys if a.get(k) is not None} for a in source.get('accounts',[]) if a['account_id'] in ['ifrs-full_Revenue','ifrs-full_ProfitLoss','ifrs-full_ProfitLossAttributableToOwnersOfParent','dart_OperatingIncomeLoss','ifrs-full_CashFlowsFromUsedInOperatingActivities','ifrs-full_Assets','ifrs-full_Liabilities','ifrs-full_Equity','ifrs-full_CashAndCashEquivalents','ifrs-full_BasicEarningsLossPerShare']]
for k in p['original_vibe_skill_methods']:p['original_vibe_skill_methods'][k]=p['original_vibe_skill_methods'][k][:700]
for x in p['macro']:
 if 'text' in x:x['text']=x['text'][:2000]
fp=hashlib.sha256(json.dumps(p,sort_keys=True,ensure_ascii=False).encode()).hexdigest();p['session_input_hash']=fp;body['output_schema']['session_input_hash']=fp;original['messages'][1]['content']=json.dumps(body,ensure_ascii=False)
q=W/'deep3_2023.request.json'
if q.exists():assert json.loads(q.read_text())==original
else:q.write_text(json.dumps(original,ensure_ascii=False))
(B/'deep_inputs/deep3_2023.json').write_text(json.dumps(p,ensure_ascii=False,indent=2));print(len(json.dumps(original)),fp)

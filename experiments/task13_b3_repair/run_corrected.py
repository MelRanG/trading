"""One technical re-evaluation using the exact original algorithm + mask adapter."""
from common import *
import difflib,os,ast
OUT=B/'replay_v2'

def prepare():
 old_manifest=json.loads((R/'runtime/task13_b3/artifact_manifest.json').read_text());assert sha(R/'runtime/task13_b3/artifact_manifest.json')==C['original_B3_manifest_SHA']
 for rec in old_manifest['files']:
  assert sha(R/rec['path'])==rec['sha256'],'ORIGINAL_B3_CHANGED'
 OUT.mkdir(exist_ok=True)
 for name in ['plan.json','phase_c_gate.json','signal_events.json','signal_seal.json']:
  p=OUT/name;original=R/'runtime/task13_b3'/name
  if not p.exists():p.symlink_to(original)
  assert sha(p)==sha(original)
 path=R/'experiments/task13_b3/evaluate.py';source=path.read_text();assert sha(path)==next(x['sha256']for x in old_manifest['files']if x['path']=='experiments/task13_b3/evaluate.py')
 old="frames[symbol]=f;valid[symbol]=good&m.eligible.reindex(f.index).eq(True)";new="frames[symbol]=f;valid[symbol]=qualified_mask(symbol,f,good,m)";assert source.count(old)==1
 prefix="from common import *\nP=json.loads((R/'runtime/task13_b3/plan.json').read_text())\nB=R/'runtime/task13_b3_repair/replay_v2'\nfrom eligibility import qualified_mask\n"
 patched=source.replace('from common import *\n',prefix,1).replace(old,new,1)
 # Function 'fitted' is byte-for-byte AST-identical; only data mask call & output namespace differ.
 a=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef)and x.name=='fitted');b=next(x for x in ast.parse(patched).body if isinstance(x,ast.FunctionDef)and x.name=='fitted');assert ast.dump(a)==ast.dump(b)
 p=B/'executed_evaluator_v2.py.txt'
 if p.exists():assert p.read_text()==patched
 else:p.write_text(patched)
 (B/'minimal_evaluator.diff').write_text(''.join(difflib.unified_diff(source.splitlines(True),patched.splitlines(True),fromfile='preserved_B3_evaluate.py',tofile='study_local_evaluate_v2.py')))
 ns={'__name__':'b3_repair_loaded','__file__':str(path)};exec(compile(patched,str(p),'exec'),ns);return ns

def reserve(path):
 with path.open('x')as f:json.dump({'status':'RESERVED','at':now(),'corrected_evaluation_number':1,'maximum':1,'technical_attempt':1,'original_signal_SHA':C['original_signal_SHA'],'identity_overlay_SHA':sha(B/'identity_overlay.json'),'reconciled_admission_SHA':sha(B/'reconciled_admission.json'),'native_manifest_SHA':sha(R/'runtime/task13_r0/native_manifest/assets.json')},f,indent=2)

def run():
 ns=prepare();reservation=B/'corrected_evaluation_attempt.json';reserve(reservation)
 try:ns['main']()
 except Exception as e:
  d=json.loads(reservation.read_text());d.update(status='FAILED',exception_type=type(e).__name__);dump(reservation,d);raise
 from eligibility import REFERENCES,asof_identity
 rows=json.loads((OUT/'evaluated_events.json').read_text())
 for r in rows:r['peer_identities_asof_entry']={s:asof_identity(s,r['entry'])for s in r['peer_membership']}
 dump(OUT/'evaluated_events_with_identity.json',rows);dump(OUT/'qualified_mask_references.json',REFERENCES)
 result=json.loads((OUT/'evaluation.json').read_text());dump(B/'technical_completion.json',{'status':'REPAIR_VERIFIED_LIMITED_RESEARCH','corrected_evaluations':1,'technical_attempts':1,'maximum_technical_attempts':2,'original_signal_unchanged':sha(OUT/'signal_events.json')==C['original_signal_SHA'],'original_plan_unchanged':sha(OUT/'plan.json')==C['original_plan_SHA'],'original_evaluation_unchanged':sha(R/'runtime/task13_b3/evaluation.json')==C['original_evaluation_SHA'],'raw_prices_changed':False,'market_mask_and_corporate_action_flags_changed':False,'alpha_direction_horizon_controls_companies_changed':False,'signal_hypothesis_result':result['verdict'],'current_sector_survivor_partial_limit_still_applies':True,'other_native_masks_unchanged':'Existing11 boundary disparities remain inherited fail-closed; not independently audited historical identity. No broader historical universe claim.','official_operating_or_paper_promotion':False});d=json.loads(reservation.read_text());d.update(status='COMPLETED',evaluation_SHA=sha(OUT/'evaluation.json'));dump(reservation,d)
 print('CORRECTED_RESULT',result['verdict'],result['price_gate']['events'])
if __name__=='__main__':run()

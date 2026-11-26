"""Deliver fit-only measured feedback, then authorize bounded phase2 on validity."""
from pathlib import Path
import time,json,sys,traceback
from compute import run,B
root=B/'native/quanta';deadline=time.monotonic()+1800
while time.monotonic()<deadline:
 for node in sorted(root.glob('Q[0-9]*')):
  if (node/'generation.json').exists() and not (node/'metrics.json').exists():
   try:
    met=run(node.name,'US',fit=True);(node/'metrics.json').write_text(json.dumps(met,indent=2));print('FIT_FEEDBACK',node.name,met['RankIC'],flush=True)
   except Exception as e:
    (node/'metrics.json').write_text(json.dumps({'scope':'FIT_ONLY_NO_OUTER_RESULTS','failed':True,'reason':str(e)}));raise
 if len(list(root.glob('Q*/feedback.json')))>=2 and not (root/'phase2_authorization.json').exists():
  # No outer results used. Require the complete5candidate phase1 ABI evidence.
  expected=[B/'models'/m/'metrics.json' for m in ['US','KR']]+[B/'calculations'/c/('nominal_'+m)/'calculation.json' for c in ['V_ROC20','V_LOWVAR20'] for m in ['US','KR']]
  if all(p.exists() for p in expected):
   (root/'phase2_authorization.json').write_text(json.dumps({'allow':True,'reason':'Phase1 both originals causal+fit labels, bothVibe2markets andRD2markets executed; no outer ranking/selection used. Quanta remaining proposal cap applies.','at':time.time()}));print('PHASE2_VALIDITY_GATE_PASS',flush=True)
 if (root/'events.json').exists():
  tasks=sum(len(json.loads(p.read_text())['tasks']) for p in root.glob('Q*/all_proposed_tasks.json'))
  if tasks>=5 and len(list(root.glob('Q*/feedback.json')))==len(list(root.glob('Q*/generation.json'))):break
 time.sleep(2)
else:raise TimeoutError('Native evolution pending, preserve state')

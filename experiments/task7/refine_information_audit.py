"""Separate whole-report incremental facts from limited facts-array extraction."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[2];B=R/'runtime/task7';original=B/'comparison/evaluation.json';evaluation=json.loads(original.read_text())
notes={'scope':'MANUAL_TWO_CASE_WHOLE_REPORT_REVIEW_V1','prior_evaluation_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'correction':'Facts-array difference is not necessarily new information across the full baseline report. NVDA CFO24077 was already explicitly in baseline counterevidence. Original evaluation and sealed review retained; this is append-only refinement.','baseline_extra_coverage':{'NVDA':['cfo'],'CRWV':[]},'arms':{}}
for arm,rows in evaluation['arms'].items():
 notes['arms'][arm]={}
 for symbol,row in rows.items():
  reported=row['incremental_verified_vs_vibe'];already=set(notes['baseline_extra_coverage'][symbol]);novel=[x for x in reported if x not in already]
  notes['arms'][arm][symbol]={'facts_array_incremental':reported,'already_in_baseline_narrative':[x for x in reported if x in already],'whole_report_additional_quantified_items':novel,'investment_materiality':'Not an independent market discovery; same supplied issuer documents. CRWV interest quantifies a debt-service risk already recognized by baseline. Forecast/alpha improvement unmeasured.','unknowns':'Limited manual metric coverage, no blinded duplicate graders; cannot infer exhaustive precision/recall.'}
(B/'comparison/information_audit_refinement.json').write_text(json.dumps(notes,indent=2));print(json.dumps(notes,indent=2))

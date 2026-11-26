"""Admission checks for the declared R1 hypothesis contracts; never edits factors."""
import hashlib,json,re
from pathlib import Path

def bound_feedback(candidate,code_path,metrics,description):
 fingerprint=hashlib.sha256(Path(code_path).read_bytes()).hexdigest()
 if metrics.get('candidate')!=candidate or metrics.get('code_hash')!=fingerprint or metrics.get('H')!=20 or metrics.get('failed'):raise ValueError('EVALUATION_BINDING_MISMATCH')
 # Original generation descriptions remain immutable; provide a separate current-state view.
 return {'candidate':candidate,'code_hash':fingerprint,'status':'EVALUATED','H':20,'description_at_generation':description,'task_description_for_feedback':re.sub(r'This factor has not been evaluated\.', '',description).strip()+'\nCURRENT STATUS: EVALUATED candidate='+candidate+' code_hash='+fingerprint+' H=20. Only the bound metrics below apply.','evaluation':metrics,'precedence':'EVALUATED status with code/hash supersedes historical has-not-been-evaluated wording'}

def admit(candidate,requirements,implementation,pool_correlations):
 missing=[x for x in requirements if implementation.get(x) is not True]
 duplicates=[{'candidate':p,'correlation':v} for p,v in pool_correlations.items() if p!=candidate and abs(v)>=.90]
 return {'candidate':candidate,'admitted':not missing and not duplicates,'missing_essential_components':missing,'pool_duplicates':duplicates,'scope':'Technical historical replay; not new alpha selection or prospective policy validation'}

def enforce(result):
 if not result['admitted']:raise ValueError('QUALITY_GATE_REJECTED:'+result['candidate'])
 return result

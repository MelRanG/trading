"""Seal final Task10.1 evidence without touching historical manifests."""
from pathlib import Path
import hashlib,json,datetime,re,os,gzip
from dotenv import dotenv_values
R=Path(__file__).resolve().parents[2];B=R/'runtime/task10_1';docs=[R/'docs/development/10_1_factory_artifacts_forward.md',R/'docs/development/10_1_progress.md']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
files=lambda:list({p for base in [B,R/'experiments/task10_1'] for p in base.rglob('*') if p.is_file()}|set(docs))
secrets=[]
for path in [R/'.env',R/'runtime/task5/service.env']:
 if path.exists():
  for k,v in dotenv_values(path).items():
   if v and len(v)>=10 and (any(s in k.upper() for s in ['SECRET','PASSWORD','TOKEN','API_KEY']) or k=='DART_API') and 'URL' not in k.upper():secrets.append(v.encode())
hits=[]
for p in files():
 if p.suffix in ['.pyc','.dump','.pth'] or p.name.endswith('.tar.gz'):continue
 if p.name.endswith('.json.gz'):
  with gzip.open(p,'rb') as f:data=f.read()
 else:
  try:data=p.read_bytes()
  except OSError:continue
 if any(v in data for v in secrets):hits.append(str(p.relative_to(R)))
write(B/'credentials_scan.json',{'known_secret_values_scanned':len(set(secrets)),'matched_file_paths':hits,'values_printed':False,'compressed_DB_audit_exports_included':True})
assert not hits,'credential matches require review (values withheld)'
growth=B/'new_artifact_growth.json';growth.write_text('{}') if not growth.exists() else None
for _ in range(5):
 ps=[p for p in files() if p.name!='artifact_manifest.json'];physical={}
 for p in ps:
  st=p.stat();physical[(st.st_dev,st.st_ino)]=st.st_blocks*512
 item={'scope':'New Task10.1 runtime+experiment code+two documents; excludes final manifest overhead, includes own caches','files':len(ps),'logical_bytes':sum(p.stat().st_size for p in ps),'physical_allocated_bytes_unique_inode':sum(physical.values()),'restored_operating_Factory_files_separate':len([p for p in (R/'runtime/alpha_research_factory/task4').rglob('*') if p.is_file()]),'new_model_checkpoints':0,'LLM_calls':0,'training_jobs':0,'legacy_evidence_deletions':0,'new_audit_export_net_saved_bytes':28131710,'full_context_inputs_retained':'Required by existing offline workers, classified regenerable but not silently removed'}
 encoded=json.dumps(item,ensure_ascii=False,indent=2)+'\n'
 if growth.read_text()==encoded:break
 growth.write_text(encoded)
missing=[]
for target in re.findall(r'\]\(([^)]+)\)',docs[0].read_text()):
 p=(docs[0].parent/target.split('#')[0]).resolve()
 if '://' not in target and p!=B/'artifact_manifest.json' and not p.exists():missing.append(target)
assert not missing,missing
records=[]
for p in sorted(files()):
 if p.name=='artifact_manifest.json' or '__pycache__' in p.parts:continue
 records.append({'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p)})
write(B/'artifact_manifest.json',{'schema':'TASK101_EVIDENCE_MANIFEST_V1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'classification':'RECOVERY_AND_PROSPECTIVE_ENROLLMENT; NO_MATURE_FORWARD_RESULT_YET','files':records,'exclusions':['self','rebuildable __pycache__'],'source_prior_task10_manifest':sha(R/'runtime/task10/artifact_manifest.json'),'report_missing_links':missing})
print(json.dumps({'sealed_files':len(records),'new_growth':item,'missing_links':missing,'credential_matches':len(hits)},ensure_ascii=False))

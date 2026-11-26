"""Local evidence/resource audit; no requests, models or operating writes."""
from pathlib import Path
import json,hashlib,subprocess,collections,datetime
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,x):(B/name).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str)+'\n')
coverage=json.loads((B/'coverage.json').read_text());assets=coverage['assets'];requests=[json.loads(x) for x in (B/'requests.jsonl').read_text().splitlines()];inode={};n=logical=allocated=0
for p in B.rglob('*'):
 if not p.is_file() or p.is_symlink():continue
 s=p.stat();n+=1;logical+=s.st_size
 if (s.st_dev,s.st_ino) not in inode:allocated+=s.st_blocks*512;inode[(s.st_dev,s.st_ino)]=s.st_size
native_versions={}
for name,folder in [('Vibe','vibe-original'),('QuantaAlpha','quanta-original'),('RD-Agent','rd-original')]:
 repo=Path('/home/ansy/app/quant-diligence')/folder
 p=subprocess.run(['git','-C',str(repo),'rev-parse','HEAD'],capture_output=True,text=True)
 native_versions[name]={'checkout':str(repo),'commit':p.stdout.strip(),'command_exit':p.returncode}
dump('resources.json',{'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'HTTP_attempts_including_OAuth':len(requests),'HTTP_budget':500,'HTTP_categories':dict(collections.Counter(x.get('category') for x in requests)),'count_definition':'Application HTTP attempts reserved before I/O, includes4OAuth. urllib physical redirects not separately metered.','research_LLM_calls':0,'research_LLM_tokens':0,'main_coding_session_tokens':'NOT_METERED_NOT_ZERO_CLAIM','model_training_jobs':0,'new_services':0,'scope_files_before_final_report_manifest':n,'scope_logical_bytes':logical,'scope_allocated_unique_inode_bytes':allocated,'shared_train_hdf_bytes':sum(p.stat().st_size for p in (B/'native').glob('*.h5')),'source_versions':native_versions,'CPU':'No cumulative session CPU meter; input probes limited CPU2/memory4GiB/network-none. No claim of exact elapsed CPU.','quality_totals_structurally_accepted_stocks':{k:sum(x.get(k,0) for x in assets) for k in ['observed_rows','missing_within_observed_life','unverified_jumps','zero_volume','declared_splits','declared_dividends']}})
checks=[]
for p in (B/'accepted').glob('*/*/quality.json'):
 d=json.loads(p.read_text());source=R/d['source_receipt']['path'];checks.append(source.exists() and sha(source)==d['source_hash'])
 for name,h in d['output_hashes'].items():checks.append(sha(p.parent/name)==h)
for a in json.loads((B/'native_manifest/assets.json').read_text()):
 for key,hkey in [('adjusted_path','adjusted_hash'),('eligibility_path','eligibility_hash')]:checks.append(sha(R/a[key])==a[hkey])
patch=json.loads((R/'runtime/task12/forward_patch.json').read_text());forward=R/'experiments/task10_1/forward.py'
dump('integrity.json',{'checked':len(checks),'all_pass':all(checks),'failure_count':sum(not x for x in checks),'existing_forward_matches_prior_Task12_authorized_patch':sha(forward)==patch['new_source_hash']});assert all(checks) and sha(forward)==patch['new_source_hash']
print('INTEGRITY',len(checks),all(checks),'FILES',n,'BYTES',logical,allocated,'HTTP',len(requests))

"""Read-only authority/retention audit. Never synthesizes a Factory ledger."""
from pathlib import Path
import json,hashlib,subprocess,tarfile,os,datetime,collections
import psycopg
R=Path(__file__).resolve().parents[2]; B=R/'runtime/task10_1';B.mkdir(exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
 return h.hexdigest()
def dump(name,x): (B/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def read_export(p):
 import gzip
 p=Path(p)
 return p.read_text() if p.exists() else gzip.open(str(p)+'.gz','rt').read()
def cmd(*args):return subprocess.run(args,capture_output=True,text=True,check=True).stdout
stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
service=cmd('systemctl','--user','show','quant-operations.service','-p','WorkingDirectory','-p','ExecStart','-p','EnvironmentFiles','-p','ActiveState')
# Do not print environment values or credentials. Only indicate overrides by variable name.
envfiles=[R/'runtime/task5/service.env',R/'.env']; overrides={}
for p in envfiles:
 if p.exists():overrides[str(p.relative_to(R))]=[l.split('=',1)[0] for l in p.read_text().splitlines() if '=' in l and any(x in l.split('=',1)[0] for x in ('FACTORY','DATABASE','ROOT','DIRECTORY'))]
dbs=cmd('docker','exec','quant-task3-postgres','psql','-U','quant_task3','-d','postgres','-Atc',"SELECT datname FROM pg_database WHERE datname LIKE 'quant_task3%' ORDER BY datname").splitlines()
observations=[]
for name in ['quant_task3_review','quant_task3_ops','quant_task3_task8b_research','quant_task3_task10_replay','quant_task3_task9_history']:
 with psycopg.connect('postgresql://quant_task3@127.0.0.1:55432/'+name,options='-c default_transaction_read_only=on') as c:
  tables=[r[0] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()];item={'database':name,'tables':tables}
  if 'investment_record' in tables:
   rows=c.execute('SELECT record_id,kind,payload,payload_hash,created_at FROM investment_record ORDER BY created_at').fetchall()
   dump('db_'+name+'.json', [{'record_id':a,'kind':b,'payload':d,'payload_hash':e,'created_at':f} for a,b,d,e,f in rows])
   item['kinds']=c.execute('SELECT kind,count(*),min(created_at),max(created_at) FROM investment_record GROUP BY kind ORDER BY kind').fetchall()
  if 'review_job' in tables:
   item['jobs']=c.execute('SELECT kind,status,count(*),min(updated_at),max(updated_at) FROM review_job GROUP BY kind,status ORDER BY kind,status').fetchall()
  observations.append(item)
backups=[]
for p in sorted((R/'runtime/task5/backups').glob('*/evidence_code.tar.gz')):
 with tarfile.open(p) as t:
  members=[m for m in t if '/alpha_research_factory/task4/' in m.name and m.isfile()]
  backups.append({'path':str(p.relative_to(R)),'sha256':sha(p),'mtime':p.stat().st_mtime,'factory_members':[{'path':m.name,'sha256':hashlib.sha256(t.extractfile(m).read()).hexdigest(),'bytes':m.size} for m in members]})
registries=[]
for p in (R/'runtime').rglob('attempt_registry.jsonl'):
 if 'task10_1' in p.parts:continue
 rows=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]; registries.append({'path':str(p.relative_to(R)),'sha256':sha(p),'rows':len(rows),'last_timestamp':max([x.get('timestamp_utc','') for x in rows],default=None)})
authority={'observed_at':stamp,'status':'BLOCKED_AUTHORITY_UNRESOLVED','authoritative_directory':'runtime/alpha_research_factory/task4','directory_exists':(R/'runtime/alpha_research_factory/task4').exists(),'budget_usage':None,'service':service,'environment_variable_names_only':overrides,'databases':dbs,'database_observations':observations,'registry_candidates':registries,'backup_archives':backups,'reason':'Registry/contracts/reservations are official file authority. PostgreSQL records are partial consumers, not an atomic mirror of all reservations. Missing authority cannot be reconstructed from past backups without proof of continuity. No empty registry created.'}
dump('authority_audit.json',authority)
# Physical identity (device,inode), logical hash duplication, references retained.
records=[]; hashes=collections.defaultdict(list);inodes=set()
roots=[p for p in (R/'runtime').iterdir() if p.is_dir() and (p.name.startswith(('task6','task7','task8','task9')) or p.name=='task10')]
for base in sorted(roots):
 for p in sorted(base.rglob('*')):
  if not p.is_file():continue
  st=p.lstat();rel=str(p.relative_to(R)); cache='__pycache__' in p.parts or p.suffix=='.pyc'
  # All existing evidence may be manifest/database referenced. Do not assume removable from suffix.
  classification='DISPOSABLE_CANDIDATE' if cache else 'RETAIN_ACTIVE' if p.suffix in ('.pth','.dump') or 'factory' in p.parts else 'REGENERABLE_RETAIN_REFERENCED' if any(x in p.parts for x in ('input','predictions','factor_execution')) else 'RETAIN_ARCHIVE'
  rec={'path':rel,'bytes':st.st_size,'allocated_bytes':st.st_blocks*512,'inode':[st.st_dev,st.st_ino],'symlink':p.is_symlink(),'sha256':sha(p),'classification':classification}
  records.append(rec);hashes[rec['sha256']].append(rec)
physical={tuple(x['inode']):x['allocated_bytes'] for x in records}
groups=[]
for h,rs in hashes.items():
 if len(rs)<2:continue
 unique={tuple(x['inode']) for x in rs};groups.append({'sha256':h,'copies':len(rs),'unique_inodes':len(unique),'logical_extra_bytes':(len(rs)-1)*rs[0]['bytes'],'physical_extra_bytes':max(len(unique)-1,0)*rs[0]['allocated_bytes'],'paths':[x['path'] for x in rs]})
summary={'mode':'DRY_RUN','scanned_roots':[str(p.relative_to(R)) for p in roots],'files':len(records),'logical_bytes':sum(x['bytes'] for x in records),'physical_allocated_bytes_unique_inode':sum(physical.values()),'duplicate_extra_paths':sum(x['copies']-1 for x in groups),'duplicate_extra_logical_bytes':sum(x['logical_extra_bytes'] for x in groups),'duplicate_extra_physical_bytes_estimate':sum(x['physical_extra_bytes'] for x in groups),'duplicate_groups':len(groups),'classifications':dict(collections.Counter(x['classification'] for x in records)),'manifest_references_policy':'Every pre-existing manifest is preserved; referenced regenerable paths are retained. DB exports retained for path-reference review. No source deletion based on hash equality.','safe_deletion_approved_paths':[],'expected_savings_bytes':0,'restore_verified_before_deletion':False,'reason':'No known unreferenced disposable file has both reference clearance and verified restoration yet.'}
dump('artifact_inventory.json',records);dump('duplicate_groups.json',groups);dump('hygiene_dry_run.json',summary)
print(json.dumps({'authority':authority['status'],'inventory':summary},ensure_ascii=False))

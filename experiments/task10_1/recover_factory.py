"""Reconcile full archive with known consumers before atomic, nonempty recovery."""
from pathlib import Path
if (Path(__file__).resolve().parents[2]/'runtime/alpha_research_factory/task4').exists():raise SystemExit('REFUSE_REPLACE_EXISTING_AUTHORITY')
from audit import R,B,sha,dump,cmd,read_export
from quant_harness.alpha_research_factory import _hash,register_review_proposal,reserve_review_experiment,record_review_experiment
import tarfile,json,shutil,datetime,os
source=R/'runtime/task5/backups/20261115T030249053499';manifest=json.loads((source/'manifest.json').read_text());archive=source/'evidence_code.tar.gz'
assert sha(archive)==manifest['archive']['sha256']
stage=B/'restore_probe';stage.mkdir(exist_ok=True)
with tarfile.open(archive) as tar:
 for m in tar:
  prefix='runtime/alpha_research_factory/task4/'
  if m.isfile() and m.name.startswith(prefix):
   target=stage/m.name[len(prefix):];assert target.resolve().is_relative_to(stage.resolve());target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(tar.extractfile(m).read())
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
attempts=rows(stage/'attempt_registry.jsonl');res=rows(stage/'experiment_reservations.jsonl');results=rows(stage/'diagnostic_registry.jsonl');ids={a['attempt_id'] for a in attempts}
assert len(ids)==len(attempts)==7 and len(res)==len(results)==3
for a in attempts:
 c=json.loads((stage/'contracts'/(a['proposal_id']+'.json')).read_text());assert c['contract_hash']==a['contract_hash']==_hash({k:v for k,v in c.items() if k!='contract_hash'})
 # Actual official duplicate/reservation replay (only in disposable restored directory).
 assert register_review_proposal(R,c['proposal'],directory=stage)==a
 if a['attempt_id'] in {x['attempt_id'] for x in res}:assert reserve_review_experiment(R,a,directory=stage)==next(x for x in res if x['attempt_id']==a['attempt_id'])
for x in results:
 a=next(a for a in attempts if a['attempt_id']==x['attempt_id']);assert record_review_experiment(R,a,x['result'],directory=stage)==x
# Every older complete backup is an append-only prefix of the recovered authority.
continuity=[]
for old in sorted((R/'runtime/task5/backups').glob('*/evidence_code.tar.gz')):
 with tarfile.open(old) as t:
  for name in ['attempt_registry.jsonl','diagnostic_registry.jsonl','experiment_reservations.jsonl','state_events.jsonl']:
   try:data=t.extractfile('runtime/alpha_research_factory/task4/'+name).read()
   except KeyError:continue
   assert (stage/name).read_bytes().startswith(data),(old,name)
 continuity.append(str(old.relative_to(R)))
# Consumer copies are incomplete, but every actual result/attempt they contain must agree.
matched=[]
def walk(x):
 if isinstance(x,dict):
  if x.get('attempt_id') in ids and 'contract_hash' in x:
   a=next(a for a in attempts if a['attempt_id']==x['attempt_id']);assert x['contract_hash']==a['contract_hash']
   if 'result' in x:
    stored=next((z for z in results if z['attempt_id']==x['attempt_id']),None)
    if stored:assert x['result']==stored['result'];matched.append(x['attempt_id'])
  for v in x.values():walk(v)
 elif isinstance(x,list):
  for v in x:walk(v)
for name in ['db_quant_task3_ops.json','db_quant_task3_review.json','db_quant_task3_task8b_research.json']:walk(json.loads(read_export(B/name)))
assert set(matched)=={x['attempt_id'] for x in results}
# Backup live consumer DBs before any authority restoration; actual isolated restore of review DB.
backup=B/'pre_recovery_backup';backup.mkdir(exist_ok=True)
for name in ['quant_task3_review','quant_task3_ops','quant_task3_task8b_research']:
 p=backup/(name+'.dump')
 if not p.exists():
  import subprocess
  with p.open('wb') as f:subprocess.run(['docker','exec','quant-task3-postgres','pg_dump','-U','quant_task3','-Fc',name],stdout=f,check=True)
target='quant_task3_task101_restore_probe'
cmd('docker','exec','quant-task3-postgres','createdb','-U','quant_task3',target)
try:
 import subprocess,psycopg
 subprocess.run(['docker','exec','-i','quant-task3-postgres','pg_restore','-U','quant_task3','-d',target,'--exit-on-error'],input=(backup/'quant_task3_review.dump').read_bytes(),check=True,capture_output=True)
 with psycopg.connect('postgresql://quant_task3@127.0.0.1:55432/'+target,options='-c default_transaction_read_only=on') as c:
  count=c.execute('SELECT count(*) FROM investment_record').fetchone()[0]
finally:cmd('docker','exec','quant-task3-postgres','dropdb','-U','quant_task3',target)
# All restored existing operations above are idempotent, no fresh approval or reservation.
live=R/'runtime/alpha_research_factory/task4';live.parent.mkdir(parents=True,exist_ok=True)
assert not live.exists(),'refuse to replace any existing authority'
backupmeta={'absence_observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'live_directory_absent':True,'snapshot_sha256':sha(archive),'db_dumps':{p.name:sha(p) for p in backup.glob('*.dump')}}
dump('pre_recovery_backup.json',backupmeta)
install=live.parent/'.task101_recovery_staging';assert not install.exists();shutil.copytree(stage,install);os.rename(install,live)
verification={'status':'RESTORED_RECONCILED_SNAPSHOT','source':str(source.relative_to(R)),'source_archive_hash':sha(archive),'attempts':7,'reservations':3,'results':3,'all_known_consumer_results_matched':sorted(set(matched)),'older_backup_prefixes':continuity,'restored_review_records':count,'fresh_registration_or_approval':False,'daily_budget_reset':False,'promotion':False,'unknown_manual_writes_after_snapshot':'Cannot prove absence of unlogged writes; all known scheduler/DB consumers reconciled. Preserve provenance and fail closed on any later conflict.','live_file_hashes':{str(p.relative_to(live)):sha(p) for p in live.rglob('*') if p.is_file() and p.name!='.registry.lock'}}
dump('recovery_result.json',verification);print(json.dumps(verification))

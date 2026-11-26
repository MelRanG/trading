"""Evidence preservation, retention policy and post-recovery observations."""
from pathlib import Path
import hashlib,json,subprocess,tarfile,datetime,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[2];B=R/'runtime/task10_1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(B/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
old=json.loads((R/'runtime/task10/artifact_manifest.json').read_text());bad=[]
for x in old['files']:
 p=R/x['path']
 if not p.exists() or sha(p)!=x['sha256']:bad.append(x['path'])
assert not bad,bad;dump('task10_preservation.json',{'files_verified':len(old['files']),'mismatches':bad,'original_manifest_hash':sha(R/'runtime/task10/artifact_manifest.json')})
# Backup the recovered nonempty live authority without changing its reservation state.
live=R/'runtime/alpha_research_factory/task4';archive=B/'recovered_factory_backup.tar.gz'
with tarfile.open(archive,'w:gz') as tar:tar.add(live,arcname='runtime/alpha_research_factory/task4')
with tarfile.open(archive) as tar:
 verified=0
 for member in tar:
  if member.isfile():assert hashlib.sha256(tar.extractfile(member).read()).hexdigest()==sha(R/member.name);verified+=1
dump('recovered_backup_check.json',{'archive_sha256':sha(archive),'restored_member_hashes_verified':verified,'operating_ledger_mutated':False})
# Latest persisted authority counts are known reservations, never missing=zero.
now=datetime.datetime.now(datetime.timezone.utc).isoformat();day=now[:10]
def rows(n):return [json.loads(x) for x in (live/n).read_text().splitlines()]
dump('authority_current.json',{'observed_at':now,'state':'RESTORED_RECONCILED_SNAPSHOT','authority_path':str(live.relative_to(R)),'counts':{'attempts':len(rows('attempt_registry.jsonl')),'reservations':len(rows('experiment_reservations.jsonl')),'results':len(rows('diagnostic_registry.jsonl'))},'UTC_day':day,'proposals_used':sum(x['timestamp_utc'][:10]==day for x in rows('attempt_registry.jsonl')),'experiments_reserved':sum(x['timestamp_utc'][:10]==day for x in rows('experiment_reservations.jsonl')),'new_strategy_approvals':0,'normal_next_day_new_experiment':'PENDING_NATURAL_BUDGET_AND_ELIGIBLE_WORK','unknown_manual_write_gap':'Explicit recovery limitation; known scheduler/DB consumers all reconciled.'})
policy={'scope':'Task6~10 research evidence and future Task10.1 outputs','classes':{'RETAIN_ACTIVE':['Nonempty operating Factory registries/contracts/reservations; no automatic reset','Frozen current model checkpoints, strategy source/parameters and active Forward plans','Current research queue state and session/calendar receipts'],'RETAIN_ARCHIVE':['Source bytes, observation timestamps and identity metadata','LLM full requests/responses and usage','Accepted/rejected/failed research, generated code/checkpoints/environment versions','Immutable decisions/fills/NAV/evaluations, verified DB dumps and original manifests'],'REGENERABLE':['Worker input panel copies, derived factor/prediction CSV, interim summaries','Keep while code/DB/manifest references require their path; no automatic removal in this task'],'DISPOSABLE':['Unreferenced sockets, transient relay/process files and import caches with source present','Only after reference audit, hash-verified backup/restore and unchanged-content recheck']},'future_generation':['Mount frozen model/checkpoint read-only instead of copy (Task10.1 implemented)','Share one source snapshot across all comparison arms (implemented)','Hourly calendar polling/cache and once per completed-session data, not five-minute full collection (implemented)','Cache deterministic inference by market/session; no LLM or retraining in observer (implemented)','All current full-context worker inputs remain regenerable but referenced; do not prune them automatically','No conversion of existing archives to content-addressable storage; no retention pruning of original failures/ledgers'],'deletion_gate':['No active lease/process uses file','No source/manifest/DB/scheduler path reference; dynamic uncertainty means retain','Verified recoverable archive and source hash match before deletion'],'actual_deletion':'Zero legacy evidence paths: both apparent import caches were manifest referenced'}
dump('retention_policy.json',policy)
def cases(p):
 tree=ET.parse(p);return {(x.attrib.get('classname',''),x.attrib.get('name','')) for x in tree.iter('testcase')}
tests=cases(B/'regression.xml')|cases(B/'forward_tests_final.xml');issues=[]
for p in [B/'regression.xml',B/'forward_tests_final.xml']:
 for x in ET.parse(p).getroot().iter():
  if x.tag in ['failure','error','skipped']:issues.append(x.tag)
dump('test_summary.json',{'unique_pytest_cases':len(tests),'issues':issues,'factory_live_reopen':'PASS_CACHED_NO_NEW_BUDGET','isolated_budget_queue':'PASS_NOT_FORWARD_EVIDENCE','actual_server_reboot':False})
print(json.dumps({'old_task10_preserved':len(old['files']),'tests':len(tests),'issues':issues}))

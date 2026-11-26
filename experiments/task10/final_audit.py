from common import *
import os,hashlib,subprocess,stat
preserved=[]
for name in ['task9_3','task9_4']:
 p=R/'runtime'/name/'artifact_manifest.json';x=json.loads(p.read_text());bad=[]
 for f in x['files']:
  q=R/f['path']
  if not q.exists() or sha(q)!=f['sha256']:bad.append(f['path'])
 assert not bad,(name,bad);preserved.append({'task':name,'files':len(x['files']),'mismatches':bad,'manifest_hash':sha(p)})
freeze(B/'prior_preservation.json',preserved)
from quant_harness.investment.equities import load_environment
load_environment(R);keys={k:v for k,v in os.environ.items() if any(a in k.upper() for a in ['API_KEY','SECRET','PASSWORD','ACCESS_TOKEN']) and len(v)>=12};hits=[]
for root in [B,Path(__file__).parent]:
 for p in root.rglob('*'):
  if not p.is_file() or p.suffix in ['.pth','.dump','.h5','.pkl','.pyc'] or p.stat().st_size>30000000:continue
  raw=p.read_bytes()
  for k,v in keys.items():
   if v.encode() in raw:hits.append({'path':str(p.relative_to(R)),'variable_name':k})
assert not hits
freeze(B/'credentials_scan.json',{'known_secret_values_checked':sorted(keys),'hits':hits,'values_printed':False,'not_a_general_secret_detector':True})
# Stop only our temporary relay, never the operating timer/DB.
pids=[]
for d in Path('/proc').iterdir():
 if not d.name.isdigit():continue
 try:argv=(d/'cmdline').read_bytes().split(b'\0')
 except (PermissionError,FileNotFoundError,ProcessLookupError):continue
 if len(argv)>1 and argv[1].endswith(b'experiments/task10/model_relay.py') and b'/tmp/quant-task10.sock' in argv:pids.append(int(d.name))
for pid in pids:os.kill(pid,15)
socket=Path('/tmp/quant-task10.sock')
if socket.exists():assert stat.S_ISSOCK(socket.lstat().st_mode);socket.unlink()
freeze(B/'cleanup.json',{'terminated_own_relay_pids':pids,'removed_own_temporary_socket':True,'operating_timer_and_DB_untouched':True,'retained':'Pinnedupstreams,venvs,Task10workspaces/controllerpool, generatedmodels, rawdata, failedtraining, reviewV1/V2, FactoryandPGbackup. Reusable researchstateisnotdiscarded.'})
print('PRIOR',preserved,'SECRET_HITS',len(hits),'OWN_RELAY_STOPPED',pids)

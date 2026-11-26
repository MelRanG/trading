"""Remove only this task's redundant worker scratch after archival byte checks."""
from protocol import *
import shutil,stat,os
research_seal();W=Path('/home/ansy/app/quant-diligence/task9-4-work');checked=[];size=0
if W.exists():
 for p in W.rglob('*'):
  if not p.is_file():continue
  rel=p.relative_to(W)
  if rel.parts[0] in ['home','__pycache__']:continue
  if len(rel.parts)>1:
   assert rel.parts[0].startswith(('search_','target_'));q=B/'native_search_evidence'/rel
  else:q=B/('worker_code' if p.suffix=='.py' else 'worker_results')/p.name
  assert q.exists() and sha(p)==sha(q),'ARCHIVE_NOT_VERIFIED:'+str(rel);checked.append(str(rel));size+=p.stat().st_size
 shutil.rmtree(W)
socket=Path('/tmp/quant-task9-4.sock');pid=Path('/proc/3211882/cmdline')
if pid.exists():assert b'task9_4/model_relay.py' not in pid.read_bytes(),'relay stillrunning'
if socket.exists():assert stat.S_ISSOCK(socket.lstat().st_mode) and socket.lstat().st_uid==os.getuid();socket.unlink()
p=Path(__file__).parent/'__pycache__'
if p.exists():shutil.rmtree(p)
freeze(B/'cleanup.json',{'scratch':str(W),'verified_archived_files':checked,'redundant_bytes_removed':size,'removed':['ownworker_scratch','ownstale_socket','ownexperiment_pycache'],'preserved':['originalcheckout','existingvenv','allresearchandpriceevidence','allTask93andoperatingassets'],'relay_stopped':True,'research_reproduction':'Usearchivedrequests/results; neverreinvokehistoricalLLMafterfuturepricesknown'})
print('removedonlyredundantscratch',len(checked),'files',size,'bytes')

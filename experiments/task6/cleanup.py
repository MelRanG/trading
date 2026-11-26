"""Remove only reproducible Task6 intermediates, retaining decision evidence."""
from pathlib import Path
import json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'runtime/task6';EXT=Path('/home/ansy/app/quant-diligence')
log=BASE/'evidence/cleanup.json'
if log.exists():raise SystemExit('cleanup already recorded; inspect receipt before another cleanup')
folders=[EXT/f'task6-{e}-work/build-source' for e in ['quanta','rd']]
folders += [EXT/f'task6-{e}-work/home/.cache/pip' for e in ['quanta','rd']]
folders += [ROOT/'experiments/task6/__pycache__']
files=[]
for pattern in ['evaluation/*/*/*/input/panel.csv','evaluation/*/*/*/full/*.h5','evaluation/*/*/*/prefix/*.h5']:
 files.extend(BASE.glob(pattern))
records=[]
def describe(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
for directory in folders:
 if directory.exists():
  children=[describe(p) for p in directory.rglob('*') if p.is_file() and not p.is_symlink()]
  records.append({'directory':str(directory),'files':len(children),'bytes':sum(c['bytes'] for c in children),'file_index_sha256':hashlib.sha256(json.dumps(children,sort_keys=True).encode()).hexdigest(),'reason':'Reproducible installation source copy/pip or bytecode cache; pinned checkout and installed package retained'})
  shutil.rmtree(directory)
for p in files:
 if p.exists():records.append({**describe(p),'reason':'Duplicate intermediate; original split CSV, generated factor CSV, code hash, execution logs and ledgers retained'});p.unlink()
receipt={'removed':records,'removed_bytes':sum(r['bytes'] for r in records),'retained':['original checkouts and envs','raw and observation receipts','all split CSV and hash manifests','native factor/model specs, state and Vibe hypotheses/goals','model trace/request/response/usage and failure logs','original generation artifacts and evaluation CSV/metrics','operational DB, ledgers, Factory records, historical results'],'temporary_relay':'stopped and socket removed before safety retest','scope':'Task6-only reproducible files; no broad legacy deletion'}
log.write_text(json.dumps(receipt,indent=2));print(json.dumps({'records':len(records),'removed_bytes':receipt['removed_bytes']},indent=2))

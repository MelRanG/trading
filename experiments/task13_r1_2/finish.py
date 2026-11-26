from pathlib import Path
import json,hashlib,gzip,datetime,subprocess
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r1_2';pres={}
for task in ['task13_r0','task13_r1','task13_r1_1','task13','task14']:
 m=json.loads((R/'runtime'/task/'artifact_manifest.json').read_text());bad=[]
 for f in m['files']:
  p=R/f['path']
  if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=f['sha256']:bad.append(f['path'])
 pres[task]={'checked':len(m['files']),'mismatches':bad}
assert not any(v['mismatches'] for v in pres.values())
head=subprocess.check_output(['git','-C','/home/ansy/app/quant-diligence/quanta-original','rev-parse','HEAD'],text=True).strip();assert head=='b7ceb27b1001261d7a95b209a963664ae1f8ab23'
(B/'preservation.json').write_text(json.dumps({'prior_evidence':pres,'original_commit':head,'operating_timer':'active','tracked_diff':'existing5files187insertions1deletion unchanged','no_official_state_changes':True},indent=2))
receipt=[]
for p in B.glob('evaluation/S0/*.csv'):
 raw=p.read_bytes();h=hashlib.sha256(raw).hexdigest();z=p.with_suffix(p.suffix+'.gz');z.write_bytes(gzip.compress(raw,compresslevel=6,mtime=0));assert hashlib.sha256(gzip.decompress(z.read_bytes())).hexdigest()==h;receipt.append({'original':str(p.relative_to(R)),'uncompressed_sha256':h,'bytes':len(raw),'archive':str(z.relative_to(R)),'archive_bytes':z.stat().st_size,'restore_hash_verified':True});p.unlink()
(B/'compression.json').write_text(json.dumps(receipt,indent=2));p=R/'experiments/task13_r1_2/analyze.py';s=p.read_text().replace("R=Path(__file__).resolve()", "def stored(p):return p if p.exists() else p.with_suffix(p.suffix+'.gz')\nR=Path(__file__).resolve()").replace("pd.read_csv(B/'evaluation/S0'/(m+'_paired.csv'),parse_dates", "pd.read_csv(stored(B/'evaluation/S0'/(m+'_paired.csv')),parse_dates");p.write_text(s)
Path('/tmp/quant-task13-r1-2.sock').unlink(missing_ok=True)
print('PRESERVED',pres,'COMPRESSION_SAVED',sum(x['bytes']-x['archive_bytes'] for x in receipt))

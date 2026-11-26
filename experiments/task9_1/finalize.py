from common import *
import subprocess,os
versions={}
for name in ['vibe-original','quanta-original','rd-original']:
 root=Path('/home/ansy/app/quant-diligence')/name
 result=subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True);versions[name]={'head':result.stdout.strip(),'native_checkout_reinstalled':False,'used_in_Task91':name=='vibe-original'}
freeze(B/'source_versions.json',versions)
usage={'Yahoo_chart_GET_success':len(list((B/'inputs').glob('*/*/price_receipt.json')))+len(list((B/'evaluator_only').glob('*/*/raw/*.receipt.json'))),'Toss_supported_GET_saved':len(list((B/'inputs').glob('*/*/toss_raw.json')))+len(list((B/'evaluator_only').glob('*/*/toss_*.json'))),'DART_GET_saved':len(list((B/'discovery').glob('dart_*.json')))+len(list((B/'inputs').glob('*/*.KS/shares.json')))+len(list((B/'inputs').glob('*/*.KS/annual_shares.json')))+len(list((B/'inputs').glob('*/*.KS/original.zip')))+len(list((B/'deep').glob('*/*.KS/accounts.json'))),'Naver_GET_saved_including_probe':len(list((B/'third_source').glob('*/receipt.json')))+len(list((B/'third_source_probe/raw').glob('*.receipt.json'))),'primary_US_fetch_attempts':len(json.loads((B/'primary_source_plan.json').read_text())),'macro_fetch_attempts':4,'FTSE_GET_saved':2,'measurement':'Saved request/response artifacts; not provider-side billing telemetry. Cache reruns do not count as new requests. Failed primary fetches are included as attempts.'}
freeze(B/'api_usage.json',usage)
from dotenv import dotenv_values
secret_values=[v for k,v in dotenv_values(R/'.env').items() if v and len(v)>=12 and any(w in k.upper() for w in ['KEY','TOKEN','SECRET','PASSWORD'])]
found=[]
for p in B.rglob('*'):
 if p.is_file() and p.suffix in ['.json','.jsonl','.txt','.log','.csv']:
  raw=p.read_bytes()
  if any(v.encode() in raw for v in secret_values):found.append(str(p.relative_to(B)))
assert not found,'credential value found in artifact'
freeze(B/'credentials_scan.json',{'files_scanned':sum(p.is_file() and p.suffix in ['.json','.jsonl','.txt','.log','.csv'] for p in B.rglob('*')),'matched_secret_values':0,'values_never_printed':True})
print(json.dumps(usage));print('SECRET_SCAN_PASS','VERSIONS_SAVED')

from pathlib import Path
import json,hashlib,re,datetime,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[2];B=R/'runtime/task14';report=R/'docs/development/14_alpha_signal_validation.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
for path in ['runtime/task13/artifact_manifest.json','runtime/task12/artifact_manifest.json','runtime/task10/artifact_manifest.json']:
 m=json.loads((R/path).read_text());bad=[x['path'] for x in m['files'] if sha(R/x['path'])!=x['sha256']];assert not bad,(path,bad);checks.append({'manifest':path,'count':len(m['files']),'mismatches':bad})
results=[]
for name in ['safety','validation']:
 p=B/(name+'_tests.xml');e=ET.parse(p).getroot().find('testsuite');v={k:int(e.attrib[k]) for k in ['tests','failures','errors','skipped']};assert v['failures']==v['errors']==v['skipped']==0;results.append({**v,'seconds':float(e.attrib['time']),'path':str(p.relative_to(R))})
links=[]
for t in re.findall(r'\]\(([^)]+)\)',report.read_text()):
 if t.startswith(('http:','https:','#')):continue
 p=(report.parent/t.split('#')[0]).resolve();assert p.exists() or p==B/'artifact_manifest.json',t;links.append(t)
assert not re.search('[ぁ-ヿ]',report.read_text())
out={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'decision':'RETURN_TO_TASK13','tests':results,'passed':sum(x['tests'] for x in results),'compileall':'PASS','old_preservation':checks,'LLM':0,'external_requests':0,'training':0,'new_alphas':0,'Task15_started':False,'operating_code_or_policy_modified':False,'initial_failure':'supplement strict Pearson1e-12 assertion: nativefloat32/CSV and constantTree dates audited, old results preserved','local_links_checked':len(links)}
(B/'completion.json').write_text(json.dumps(out,indent=2)+'\n')
files=[p for folder in [R/'experiments/task14',B] for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='artifact_manifest.json'];files.append(report)
m={'schema':'TASK14_EVIDENCE_MANIFEST_V1','at':out['at'],'scope':'EXPOSED_SIGNAL_VALIDATION_NOT_NEW_ALPHA_OR_INVESTMENT_ECONOMICS','files':[{'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)],'file_count':len(files),'logical_bytes':sum(p.stat().st_size for p in files),'physical_allocated_bytes':sum(p.stat().st_blocks*512 for p in files),'old_evidence_modified':False}
(B/'artifact_manifest.json').write_text(json.dumps(m,indent=2)+'\n');print({'decision':out['decision'],'PASS':out['passed'],'files':len(files),'logicalMiB':m['logical_bytes']/2**20,'links':len(links)})

"""Seal Task12 evidence without rewriting previous manifests or results."""
from pathlib import Path
import hashlib,json,datetime,re,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[2];B=R/'runtime/task12';report=R/'docs/development/12_alpha_data_readiness.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
results=[]
for name in ['safety','recovery','readiness']:
 p=B/(name+'_tests.xml');t=ET.parse(p).getroot().find('testsuite');v={k:int(t.attrib[k]) for k in ['tests','failures','errors','skipped']};v['seconds']=float(t.attrib['time']);v['path']=str(p.relative_to(R));assert v['failures']==v['errors']==v['skipped']==0;results.append(v)
links=[]
for target in re.findall(r'\]\(([^)]+)\)',report.read_text()):
 if target.startswith(('http:','https:','#')):continue
 raw=target.split('#')[0];p=(report.parent/raw).resolve();links.append({'target':target,'exists':p.exists() or p==B/'artifact_manifest.json'})
missing=[x for x in links if not x['exists']];assert not missing,missing
r={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'READY_FOR_TASK13_S','B':'NOT_READY','tests':results,'passed_total':sum(v['tests'] for v in results),'compile':'PASS','external_data_requests':0,'LLM_calls':0,'new_training':0,'new_installations':0,'CPU_budget_hours':4,'total_CPU_measurement':'NOT_INSTRUMENTED; per-test elapsed in XML; bounded probes used CPU2/memory4GB','historical_economic_tests':0,'Forward':'PENDING_NEXT_COMPLETED_SESSION; normal scheduler read-only evidence','local_report_links_checked':len(links),'missing_links':missing,'known_initial_failures':['Pre-fix immutable attempt prevented retry (confirmed red reproduction)','Temporary-root / missing policy / ExecutionSpec fixture corrections','RD log permission then small cross-sectional fixture correction','Blocked import-time cost-map DNS; local-only mode set','System python absent; .venv/bin/python used','Finalizer self-manifest link checked before its creation, fixed deferred existence check'],'old_preservation':'runtime/task12/preservation.json'}
(B/'test_summary.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
paths=[]
for root in [R/'experiments/task12',B]:
 paths.extend(p for p in root.rglob('*') if p.is_file() and p.name!='artifact_manifest.json' and '__pycache__' not in p.parts)
paths.append(report);files=[{'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(paths)]
m={'schema':'TASK12_EVIDENCE_MANIFEST_V1','at':r['at'],'scope':'INPUT_REGIME_ADMISSIBILITY_AND_TECHNICAL_FORWARD_FIX_NOT_ALPHA_ECONOMIC_SUCCESS','files':files,'file_count':len(files),'logical_bytes':sum(p['bytes'] for p in files),'physical_allocated_bytes':sum(p.stat().st_blocks*512 for p in paths),'cache_excluded':True,'no_previous_evidence_deleted':True,'retention':'Keep technical original/receipt, failed attempts, source hashes, fixed inputs and test evidence. Shared fit prefix only once per market; no new checkpoint copies.'}
(B/'artifact_manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');print({'tests':r['passed_total'],'report_links':len(links),'artifact_files':m['file_count'],'logical_bytes':m['logical_bytes'],'physical_allocated_bytes':m['physical_allocated_bytes']})

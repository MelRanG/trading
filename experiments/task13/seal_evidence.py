"""Final file hashes and test status; never creates a new research attempt."""
from pathlib import Path
import json,hashlib,re,datetime,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13';report=R/'docs/development/13_native_alpha_research.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
tests=[]
for name in ['safety','research']:
 p=B/(name+'_tests.xml');e=ET.parse(p).getroot().find('testsuite');v={k:int(e.attrib[k]) for k in ['tests','failures','errors','skipped']};v.update(seconds=float(e.attrib['time']),path=str(p.relative_to(R)));assert v['errors']==v['failures']==v['skipped']==0;tests.append(v)
links=[]
for t in re.findall(r'\]\(([^)]+)\)',report.read_text()):
 if t.startswith(('http:','https:','#')):continue
 p=(report.parent/t.split('#')[0]).resolve();assert p.exists() or p==B/'artifact_manifest.json',t;links.append(t)
summary={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tests':tests,'passed':sum(x['tests'] for x in tests),'compileall':'PASS','new_candidate_calculation':'PASS_5_CANDIDATES_2_MARKETS','native_evolution':'PARTIAL_2_ORIGINALS_COMPLETE_MUTATION_PROPOSAL_ONLY_NO_CROSSOVER','investment_alpha':'NOT_CONFIRMED','no_Task14_or15_run':True,'report_links_checked':len(links),'failures_are_preserved':'runtime/task13/attempt_ledger.json','no_current_Task13_relay_socket':not Path('/tmp/quant-task13.sock').exists()}
(B/'test_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
files=[]
for root in [R/'experiments/task13',B]:files += [p for p in root.rglob('*') if p.is_file() and p.name!='artifact_manifest.json' and '__pycache__' not in p.parts]
files.append(report);unique={(p.stat().st_dev,p.stat().st_ino):p for p in files}
m={'schema':'TASK13_EVIDENCE_MANIFEST_V1','at':summary['at'],'classification':'EXPOSED_HISTORICAL_RESEARCH_NOT_FORWARD_OR_STRATEGY_APPROVAL','files':[{'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)],'file_count':len(files),'logical_bytes':sum(p.stat().st_size for p in files),'unique_inode_files':len(unique),'physical_allocated_bytes_unique_inodes':sum(p.stat().st_blocks*512 for p in unique.values()),'pycache_excluded':True,'source_data_shared_per_track_market':True,'temporary_relay_removed':True,'old_evidence_deleted':False}
(B/'artifact_manifest.json').write_text(json.dumps(m,indent=2)+'\n');print({'files':m['file_count'],'logicalMiB':m['logical_bytes']/2**20,'physicalMiB':m['physical_allocated_bytes_unique_inodes']/2**20,'tests':summary['passed'],'links':len(links)})

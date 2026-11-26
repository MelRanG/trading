from common import *
import shutil,subprocess,xml.etree.ElementTree as ET
E=Path('/home/ansy/app/quant-diligence')
for engine in ['quanta','rd']:
 source=E/('task10-'+engine+'-work');target=B/'native_full'/engine
 shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('home','__pycache__'))
rows=[json.loads(p.read_text()) for p in (B/'model_calls').glob('*/*.reserved.json')];freeze(B/'usage.json',{'actual_model':'gpt-6.1-terra','calls':len(rows),'successful':sum(r['status']=='SUCCEEDED' for r in rows),'failed':sum(r['status']!='SUCCEEDED' for r in rows),'input_tokens':sum(r.get('usage',{}).get('input_tokens',0) for r in rows),'output_tokens':sum(r.get('usage',{}).get('output_tokens',0) for r in rows),'cached_input_tokens':sum(r.get('usage',{}).get('cached_input_tokens',0) for r in rows),'total_tokens':sum(r.get('measured_tokens',0) for r in rows),'model_elapsed_seconds':sum(r.get('elapsed_seconds',0) for r in rows),'scopes':{name:{'calls':sum(r['engine']==name for r in rows),'tokens':sum(r.get('measured_tokens',0) for r in rows if r['engine']==name)} for name in ['quanta','rd','review']},'incremental_bill_USD':None,'cost_note':'Codexsubscription, no paidAPI. NativeLiteLLM gpt4oaliascostestimates areNOTactualTerraUSDcost. Startup/contextoverhead included inCodexusage.','data_requests':len((B/'data_requests.jsonl').read_text().splitlines()),'successful_training_jobs':4,'failed_training_jobs':1,'compute_limits':C['compute']})
version={}
for name in ['quanta','rd']:
 root=E/(name+'-original');version[name]={'checkout':str(root),'commit':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),'environment':str(E/('task6-'+name+'-env'))}
freeze(B/'source_versions.json',{'upstreams':version,'Quanta_bundled_RD_version':'0.8.0','separate_RD_version':'1.0.0','pyqlib':'0.9.7','CPUtorch':'2.8.0+cpu','new_dependency_installations':False})
tests={}
for name in ['safety_tests','walk_forward_tests_final']:
 root=ET.parse(B/(name+'.xml')).getroot();suites=list(root.iter('testsuite'));tests[name]={key:sum(int(s.get(key,0)) for s in suites) for key in ['tests','failures','errors','skipped']}
freeze(B/'test_results.json',tests);print(json.loads((B/'usage.json').read_text()))

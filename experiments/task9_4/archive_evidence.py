from common import *
import shutil,subprocess
W=Path('/home/ansy/app/quant-diligence/task9-4-work')
for p in W.iterdir():
 if p.name in ['home','__pycache__']:continue
 if p.is_dir():
  if p.name.startswith(('search_','target_')):shutil.copytree(p,B/'native_search_evidence'/p.name,dirs_exist_ok=True)
 elif p.suffix in ['.json','.txt','.log','.py']:
  folder=B/('worker_code' if p.suffix=='.py' else 'worker_results');folder.mkdir(exist_ok=True);shutil.copyfile(p,folder/p.name)
rows=[json.loads(p.read_text()) for p in (B/'model_calls/research').glob('*.reserved.json')]
freeze(B/'usage.json',{'calls':len(rows),'successful_transport':sum(x['status']=='SUCCEEDED' for x in rows),'failed':sum(x['status']!='SUCCEEDED' for x in rows),'input_tokens':sum(x.get('usage',{}).get('input_tokens',0) for x in rows),'output_tokens':sum(x.get('usage',{}).get('output_tokens',0) for x in rows),'cached_input_tokens':sum(x.get('usage',{}).get('cached_input_tokens',0) for x in rows),'measured_total_tokens':sum(x.get('measured_tokens',0) for x in rows),'monetary_cost':None,'cost_note':'ExistingChatGPTsubscription; incrementalUSDunitpriceunknown. Failedcalltokensincluded. No paidAPI purchased. Per-call90k measuredguard exceeded byoneKRattempt(100955), FAILEDretained, retriedonce.','model':'gpt-6.1-terra','hard_token_cap':False})
repo=Path('/home/ansy/app/quant-diligence/vibe-original');paths=['agent/src/tools/web_search_tool.py','agent/src/providers/chat.py'];freeze(B/'original_version.json',{'checkout':str(repo),'commit':subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),'source_hashes':{n:sha(repo/n) for n in paths},'scope':'OriginalWebSearchTool+ChatLLM+skilltext; hostPITcollection andstatic evaluatoradapter, NOTfullupstreamResearchAutopilotCLI','installed_native_search_hash':'8f02f05f94ac3aad13747d680fc4e3dc857539c5108fb326d6d84c56e9ce8e9a'})
print(json.loads((B/'usage.json').read_text()))

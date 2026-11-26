"""Reuse existing credential-isolated CLI transport for document second reading only.
No RD-Agent/Quanta invocation, no host tools, no HTTP data collection.
"""
from pathlib import Path
import importlib.util,json,re,sys
from read_sources import *

def focus(doc):
 bs=doc.get('blocks',[]);selected=[]
 for b in bs:
  t=b['text']
  if re.search(r'forward.looking statements|safe harbor|non.gaap financial measures|reconciliation|may differ materially',t,re.I):continue
  relevant=(re.search(r'full.year|fiscal\s+(?:year\s+)?20\d\d|outlook|guidance|forecast',t,re.I) and re.search(r'sales|revenue|growth|guidance',t,re.I)) or re.search(r'(?:organic|net|total|consolidated)\s+(?:sales|revenue)\s+(?:growth|increase|decline)',t,re.I)
  # Retain actual growth too; reader must distinguish actual and forecast independently.
  if relevant:selected.append({k:b[k]for k in ['n','file','xpath','text']})
 return {k:v for k,v in doc.items()if k in ['role','accession','filingDate']}|{'source_SHA':doc.get('source',{}).get('source_hash'),'blocks':selected}

def run(stage):
 items=P['stage1'] if stage==1 else P['conditional_stage2'];inputs=[]
 for x in items:
  o=packet(x);p=B/'reading_packets'/f"{x['event_id'].replace(':','_')}.json";p.parent.mkdir(exist_ok=True)
  if not p.exists():p.write_text(json.dumps(o,ensure_ascii=False,indent=2))
  else:assert json.loads(p.read_text())==o
  inputs.append({'event_id':o['event_id'],'predeclared_metric_basis':o['predeclared_metric_basis'],'documents':[focus(d)for d in o['documents']]})
 request={'role':'independent original-document second reader','B2_rules':{'same_FY':True,'annual_total_revenue_growth_only':True,'issuer_basis_fixed':True,'EPS_absolute_revenue_service_or_segment_revenue_excluded':True,'no_numeric_guess_of_qualitative':True,'qualitative_identical_allowed_UNCHANGED':True,'numeric_same_qualifier_both_endpoints_up_or_down':True,'qualifier_change_or_crossing_bounds':'UNRESOLVED','parent_required':'Previous available official original must provide same FY/basis value, not only new release self-description of old forecast. No parent sameFY => MISSING_PREVIOUS_SOURCE.'},'task':'Read supplied original excerpts independently, distinguish actual from guidance, total from segment and calendar from fiscal. Return JSON array, one per event, with event_id, category (RECOVERABLE/OUTSIDE_B2_CONTRACT/NO_ANNUAL_REVENUE_GROWTH_GUIDANCE/UNRESOLVED/MISSING_PREVIOUS_SOURCE), guidance_present_in_contract (bool), direction UP/DOWN/UNCHANGED or null, FY, prior/current literal values, evidence list of role+block n+short quote, reason. Do not claim facts not visible. Mixed quarterly/annual paragraphs can be disambiguated when source explicitly identifies annual clause. Missing relevant evidence => unresolved. Do not search or calculate prices. Output JSON only.','events':inputs}
 (B/f'stage{stage}_second_read_input.json').write_text(json.dumps(request,ensure_ascii=False,indent=2))
 spec=importlib.util.spec_from_file_location('existing_transport',R/'experiments/task13_r2/transport.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.BUDGET={'rd':{'calls':4,'tokens':80000}};relay=m.Relay(B/'second_reader')
 result=relay.call('rd',{'messages':[{'role':'user','content':json.dumps(request,ensure_ascii=False)}]})
 text=result['choices'][0]['message']['content'];(B/f'stage{stage}_second_read_response.txt').write_text(text);print('STAGE',stage,'usage',result['usage'])
if __name__=='__main__':run(int(sys.argv[1]))

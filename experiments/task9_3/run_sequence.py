from common import *
import subprocess,copy
E=Path(__file__).parent;P=str(R/'.venv/bin/python');dates=sorted(set(C['reviews']+json.loads((E/'event_policy.json').read_text())['US_material_event_reviews']))
def command(args,log):
 with open(B/log,'w') as f:subprocess.run(args,cwd=R,stdout=f,stderr=subprocess.STDOUT,check=True)
for m in ['US','KR']:
 # Actual initial sealed output exists, never call again.
 if not (B/'decisions'/m/'2026-05-15.json').exists():
  command([P,str(E/'seal_decision.py'),m,'2026-05-15'],m+'_initial_seal.log')
 for scheduled in dates:
  date=json.loads((B/'calendar_mapping.json').read_text())['review_dates'][m].get(scheduled,scheduled)
  if date=='2026-05-15' or (m=='KR' and scheduled not in C['reviews']):continue
  if (B/'decisions'/m/(date+'.json')).exists():continue
  command([P,str(E/'prepare_next.py'),m,date],m+'_'+date+'_packet.log')
  if m=='KR' and date not in ['2026-08-18','2026-11-02']:
   prior=sorted((B/'decisions'/m).glob('*.json'))[-1];obj=copy.deepcopy(json.loads(prior.read_text()));obj['asof']=date;obj['input_hash']=digest(json.loads((B/'packets'/m/(date+'.json')).read_text()));obj['review_origin']='DETERMINISTIC_NO_NEW_MODEL_JUDGMENT';obj['parent_decision_hash']=sha(prior);obj['portfolio_reason']='Preserve prior sealed research thesis/weights; no automatic WATCH purchase; monthly price/source/stop review only. New unmodeled facts flagged for next fullresearch.';freeze(B/'decisions'/m/(date+'.json'),obj);freeze(B/'seals'/m/(date+'.json'),{'market':m,'asof':date,'decision_hash':digest(obj),'parent_hash':sha(prior),'model_call':False,'method':'deterministic carryforward, not newforecast'});print(m,date,'DETERMINISTIC_REVIEW',flush=True);continue
  command([P,str(E/'prepare_research.py'),m,date],m+'_'+date+'_prepare.log')
  command(['bash',str(E/'run_model.sh'),m+'_'+date,'research'],m+'_'+date+'.log')
  command([P,str(E/'seal_decision.py'),m,date],m+'_'+date+'_seal.log');print(m,date,'MODEL_REVIEW_SEALED',flush=True)
print('ALL_SEQUENTIAL_DECISIONS_SEALED',flush=True)

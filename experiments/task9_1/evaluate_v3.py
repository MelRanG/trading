"""Data-only reconciliation adapter; every Naver field corroborated, no averaging."""
from common import *
import importlib.util,pandas as pd,numpy as np
spec=importlib.util.spec_from_file_location('research_eval_v1',R/'experiments/task9_1/evaluate.py');ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
original=ev.path_for

def corroborated(naver,yahoo,toss,dates):
 if not set(dates)<=set(naver.index):raise ValueError('MISSING_NAVER_REQUIRED_MARK')
 proof=[]
 for day in dates:
  for field in ['open','high','low','close']:
   reference=float(naver.loc[day,field]);agree=[]
   for label,source in [('YAHOO',yahoo),('TOSS',toss)]:
    if day in source.index and np.isfinite(source.loc[day,field]) and abs(float(source.loc[day,field])/reference-1)<=.005:agree.append(label)
   if not agree:raise ValueError('UNCORROBORATED_RAW_FIELD:'+str(day.date())+':'+field)
   proof.append({'day':str(day.date()),'field':field,'providers':agree})
 return proof

def path_for(date,s,entry,exit,dates):
 if not s.endswith('.KS'):return original(date,s,entry,exit,dates)
 f=B/'evaluator_only'/date/s;naver,bad=ev.valid_prices(pd.read_csv(B/'third_source'/s/'bars.csv'));y,ybad=ev.valid_prices(pd.read_csv(f/'yahoo_bars.csv'));t,tbad=ev.valid_prices(pd.read_csv(f/'bars.csv'));proof=corroborated(naver,y,t,dates)
 assert entry in naver.index and exit in naver.index
 # Selected KR cases have no declared splits in this frozen price window.
 r=json.loads((f/'receipt_v2.json').read_text());assert not r.get('events',{}).get('splits',{}),'CORPORATE_ACTION_REQUIRES_SEPARATE_AUDIT'
 out=naver.loc[dates,'close']/float(naver.loc[entry,'open']);out.loc[entry-pd.Timedelta(seconds=1)]=1.;out.loc[exit]=float(naver.loc[exit,'open']/naver.loc[entry,'open']);out=out.sort_index();stem=date+'_'+s+'_'+str(entry.date())+'_'+str(exit.date());freeze(B/'price_proofs'/(stem+'.json'),{'reference_source_hash':sha(B/'third_source'/s/'body.txt'),'validation_contract_hash':sha(R/'experiments/task9_1/price_resolution_v3.json'),'proof':proof})
 return out,{'symbol':s,'entry_open':float(naver.loc[entry,'open']),'exit_open':float(naver.loc[exit,'open']),'price_return':float(out.iloc[-1]-1),'source':'WHOLE_ORIGINAL_NAVER_BARS_FIELD_CORROBORATED_BY_SECONDARY','proof_hash':sha(B/'price_proofs'/(stem+'.json')),'quality':'PARTIAL_THREE_PUBLIC_PROVIDERS_NOT_EXCHANGE_ORIGINAL','dividend_policy':'EXCLUDED_BOTH_SIDES'}

if __name__=='__main__':
 date=sys.argv[1];assert (B/'followup_preregistered.json').exists();ev.path_for=path_for
 # Preserve original V1 results; reuse evaluator under a separate output root
 # with read-only symbolic references to existing frozen source directories.
 view=B/'verified_replay';view.mkdir(exist_ok=True)
 for name in ['screens','decisions','inputs','evaluator_only']:
  p=view/name
  if not p.exists():p.symlink_to(B/name,target_is_directory=True)
 (view/'evaluation').mkdir(exist_ok=True);ev.B=view;rows=ev.run(date);dump(B/'evaluation_v3'/(date+'.json'),rows);dump(B/'evaluation_v3'/(date+'_stock.json'),json.loads((view/'evaluation'/(date+'_stock.json')).read_text()));print(date,'CALCULATED',sum(x['status']=='CALCULATED_PARTIAL' for x in rows),'BLOCKED',sum(x['status']!='CALCULATED_PARTIAL' for x in rows))

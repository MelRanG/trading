from common import *
from collections import Counter
import importlib.util

def run():
 src=Sources();spec=importlib.util.spec_from_file_location('b1_numeric_reused',R/'experiments/task13_b1/normalize.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n);proof=[]
 for s in ['MSFT','PEP']:
  d=json.loads((B/'fundamentals'/f'{s}.json').read_text());e=d['events'][-1];f=e['filing'];acc=f['accessionNumber'];url=f"https://www.sec.gov/Archives/edgar/data/{int(d['cik'])}/{acc.replace('-','')}/{f['primaryDocument']}";raw,meta=src.get(s+'_original_spot',url)
  if not raw:proof.append({'symbol':s,'pass':False,'reason':'ORIGINAL_UNAVAILABLE','source':meta});continue
  inline=n.inline_values(raw);matches=[]
  for fact in e['facts']:
   a=[x for x in inline if x['name']=='us-gaap:'+fact['tag']and x['period'].get('startdate')==fact['period_start']and x['period'].get('enddate')==fact['period_end']and n.Decimal(x['value'])==n.Decimal(fact['value'])];matches.append({'tag':fact['tag'],'role':fact['role'],'value':fact['value'],'pass':bool(a),'original_locator':a[:1]})
  proof.append({'symbol':s,'accession':acc,'source':meta,'facts':matches,'pass':all(x['pass']for x in matches)})
 dump(B/'inline_original_proof.json',proof)
 companies=[json.loads(p.read_text())for p in(B/'fundamentals').glob('*.json')];raw_events=[e for c in companies for e in c['events']];rows=[e for e in raw_events if all(f['period_start']>=P['financial_inputs'][0] and f['period_end']<=P['financial_inputs'][1]for f in e['facts'])];sectors={x['symbol']:x['sector_current']for x in P['universe']};nfirms=len({e['symbol']for e in rows});pos=sum(e['margin_delta']>0 for e in rows);neg=sum(e['margin_delta']<0 for e in rows);nyears=len({e['filed_date'][:4]for e in rows});nsectors=len({sectors[e['symbol']]for e in rows});gate=all(x['pass']for x in proof)and len(proof)==2 and len(rows)>=100 and nfirms>=8 and nsectors>=3 and nyears>=4 and pos>=25 and neg>=25
 result={'pass':gate,'events':len(rows),'support_period_outside_contract_excluded':len(raw_events)-len(rows),'issuers':nfirms,'years':nyears,'sectors':nsectors,'positive':pos,'negative':neg,'flat':sum(e['margin_delta']==0 for e in rows),'by_issuer':{c['symbol']:{'filings':c.get('candidate_original_filings',0),'paired_events':len(c['events']),'exclusions':dict(Counter(x['reason']for x in c.get('exclusions',[])))}for c in companies},'original_spotcheck_documents':len(proof),'original_spotcheck_values':sum(len(x.get('facts',[]))for x in proof),'original_spotcheck_pass':all(x['pass']for x in proof),'source_grade':'PARTIAL original-accession reconstruction with2original filing spot checks; not an independently archived PIT full-universe','universal_original_inline_check':False,'signal_extremes_not_trimmed':True,'prices_accessed_for_outcomes':False}
 dump(B/'phase_c_gate.json',result);dump(B/'signal_events.json',sorted(rows,key=lambda x:(x['filed_date'],x['symbol'])));new_seal={'at':now(),'events_SHA':sha(B/'signal_events.json'),'plan_SHA':sha(B/'plan.json'),'gate_SHA':sha(B/'phase_c_gate.json'),'engine_runs':0,'price_outcomes_not_seen':True,'eligible_signal_hypothesis_fixed':True}
 if (B/'signal_seal.json').exists():assert {k:v for k,v in json.loads((B/'signal_seal.json').read_text()).items()if k!='at'}=={k:v for k,v in new_seal.items()if k!='at'}
 else:dump(B/'signal_seal.json',new_seal)
 print(json.dumps(result))
if __name__=='__main__':run()

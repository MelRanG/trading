"""One preregistered quarterly margin signal, existing official-source transport."""
from common import *
from collections import defaultdict,Counter
from datetime import date
from quant_harness.investment.financial_packet import verify_fact

def records(a):return [{k:v[i]for k,v in a.items()}for i in range(len(a['accessionNumber']))]
def values(arr,acc):
 out=defaultdict(list)
 for i,x in enumerate(arr):
  if x.get('accn')!=acc or not x.get('start'):continue
  duration=(date.fromisoformat(x['end'])-date.fromisoformat(x['start'])).days
  if 70<=duration<=110:out[(x['start'],x['end'])].append((i,x))
 return {k:v[0]for k,v in out.items()if len({x['val']for i,x in v})==1}

def company(sources,symbol):
 existing=B/'fundamentals'/f'{symbol}.json'
 if existing.exists():return json.loads(existing.read_text())
 old=R/'runtime/task13_b2/collection'/f'{symbol}.json'
 c=json.loads(old.read_text())if old.exists()else next(x for x in json.loads((R/'runtime/task13_b1/US_collection.json').read_text())if x['symbol']==symbol);cik=c['cik'];raw,cm=sources.get(symbol+'_companyfacts',f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json');sr,sm=sources.get(symbol+'_submissions',f'https://data.sec.gov/submissions/CIK{cik}.json');result={'symbol':symbol,'cik':cik,'companyfacts':cm,'submissions':sm,'events':[],'exclusions':[]}
 if raw is None or sr is None:result['status']='SOURCE_FAILED';dump(existing,result);return result
 cf=json.loads(raw);sub=json.loads(sr);assert int(cf['cik'])==int(cik)==int(sub['cik']);gaap=cf.get('facts',{}).get('us-gaap',{});filings=records(sub['filings']['recent']);history=[]
 for f in sorted(sub['filings'].get('files',[]),key=lambda x:x['filingFrom'],reverse=True):
  if min(x['filingDate']for x in filings)<='2020-01-01':break
  if f['filingFrom']>'2024-12-31'or f['filingTo']<'2020-01-01':continue
  hr,hm=sources.get('history_'+f['name'],'https://data.sec.gov/submissions/'+f['name']);history.append(hm)
  if hr:filings+=records(json.loads(hr))
  if len(history)>=4:break
 result['history']=history;filings=sorted({x['accessionNumber']:x for x in filings if x['form']=='10-Q'and'2020-01-01'<=x['filingDate']<='2024-12-31'}.values(),key=lambda x:(x['filingDate'],x['accessionNumber']));result['candidate_original_filings']=len(filings);seen=set()
 for f in filings:
  end=f.get('reportDate');acc=f['accessionNumber'];filed=f['filingDate']
  if not end or end in seen:continue
  seen.add(end)
  if not 0<=(date.fromisoformat(filed)-date.fromisoformat(end)).days<=90:result['exclusions'].append({'acc':acc,'reason':'FILIAL_DELAY_OR_END'});continue
  op=values(gaap.get(P['facts']['operating_tag'],{}).get('units',{}).get('USD',[]),acc);pair=None
  for tag in P['facts']['revenue_tags']:
   rev=values(gaap.get(tag,{}).get('units',{}).get('USD',[]),acc)
   current=[k for k in rev if k[1]==end and k in op]
   if len(current)!=1:continue
   k=current[0];prior=[p for p in rev if p in op and 350<=(date.fromisoformat(end)-date.fromisoformat(p[1])).days<=380]
   if len(prior)!=1:continue
   p=prior[0]
   if (date.fromisoformat(k[0])-date.fromisoformat(p[0])).days not in range(350,381):continue
   pair=(tag,k,p,rev,op);break
  if pair is None:result['exclusions'].append({'acc':acc,'reason':'NO_SAME_ACCESSION_QUARTERLY_COMPARATIVE_REV_OP_PAIR'});continue
  tag,k,p,rev,op=pair;facts=[];valid=True
  for role,key in [('current',k),('prior',p)]:
   for metric,t,arr in [('revenue',tag,rev),('operating_profit',P['facts']['operating_tag'],op)]:
    i,x=arr[key]
    if x.get('filed')!=filed or x.get('form')!='10-Q':valid=False;break
    fact={'metric':metric,'role':role,'raw_value':str(x['val']),'value':str(x['val']),'multiplier':1,'unit':'CURRENCY','currency':'USD','basis':'CFS','period_start':key[0],'period_end':key[1],'published':filed,'source_hash':cm['source_hash'],'source_path':cm['storage_path'],'original_accession':acc,'tag':t,'locator':{'kind':'json','path':['facts','us-gaap',t,'units','USD',i,'val']}}
    facts.append(verify_fact(fact,raw,filed))
  if not valid:result['exclusions'].append({'acc':acc,'reason':'FILED_FORM_MISMATCH'});continue
  currev=rev[k][1]['val'];prevrev=rev[p][1]['val']
  if currev<=0 or prevrev<=0:result['exclusions'].append({'acc':acc,'reason':'NONPOSITIVE_REVENUE'});continue
  currentmargin=op[k][1]['val']/currev;priormargin=op[p][1]['val']/prevrev
  result['events'].append({'symbol':symbol,'accession':acc,'FY_original':rev[k][1].get('fy'),'fiscal_period_original':rev[k][1].get('fp'),'filing':f,'filed_date':filed,'report_end':end,'prior_end':p[1],'revenue_tag':tag,'margin_delta':currentmargin-priormargin,'current_margin':currentmargin,'prior_margin':priormargin,'facts':facts,'available_rule':'NewYork filing date end; not earliest earnings news','source_grade':'PARTIAL_ORIGINAL_ACCESSION_COMPANYFACTS_RECONSTRUCTION','no_future_target_input':True})
 result['status']='SOURCE_NORMALIZED';dump(existing,result);print(symbol,'filings',len(filings),'valid',len(result['events']),flush=True);return result
if __name__=='__main__':
 import sys
 src=Sources();names=P['phaseC']['pilot_first']if len(sys.argv)>1 and sys.argv[1]=='pilot'else[x['symbol']for x in P['universe']]
 for s in names:company(src,s)

"""Frozen issuer/quarter ordering. No prices, numerical models or LLM calls."""
from common import *
import argparse,re
parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['pilot','initial','reserve'],default='pilot');args=parser.parse_args();sources=Sources();root=B/'collection';root.mkdir(exist_ok=True)
raw,meta=sources.get('SEC_ticker_identity','https://www.sec.gov/files/company_tickers.json');assert raw;cat=json.loads(raw);mapping={r['ticker']:str(r['cik_str']).zfill(10) for r in cat.values()};dump(B/'identity_reference.json',meta)
plans=C['companies'][:3] if args.stage=='pilot' else C['companies'][:20] if args.stage=='initial' else C['companies'][20:]
if args.stage=='reserve':
 assert (B/'initial_sample_gate.json').exists() and not json.loads((B/'initial_sample_gate.json').read_text())['pass'],'RESERVE_ONLY_IF_SAMPLE_SHORT'
for company in plans:
 symbol=company['symbol'];out=root/(symbol+'.json')
 if out.exists() and json.loads(out.read_text()).get('complete'):print(symbol,'CACHED',flush=True);continue
 used=[p for p in root.glob('*.json') if p.name not in ['index.json'] and not p.name.endswith('.target_seal.json') and p!=out];target_count=sum(len(json.loads(p.read_text()).get('targets',[])) for p in used);parent_count=sum(len(json.loads(p.read_text()).get('parents',[])) for p in used)
 if target_count>=C['max_analyzed_release_events']:print('TARGET_CAP_REACHED',flush=True);break
 cik=mapping.get(symbol)
 if cik is None:dump(out,{'company':company,'complete':True,'status':'NO_CIK_MAPPING','targets':[]});continue
 raw,sm=sources.get(symbol+'_submissions',f'https://data.sec.gov/submissions/CIK{cik}.json');row={'company':company,'cik':cik,'submissions':sm,'targets':[],'parents':[],'complete':False}
 if raw is None:row.update(complete=True,status='SOURCE_ACCESS_FAILED');dump(out,row);continue
 sub=json.loads(raw);assert int(sub['cik'])==int(cik)
 def records(a):return [{k:v[i] for k,v in a.items()} for i in range(len(a['accessionNumber']))]
 filings=records(sub['filings']['recent']);history=[]
 for f in sorted(sub['filings'].get('files',[]),key=lambda f:f['filingFrom'],reverse=True):
  if f['filingFrom']>'2024-12-31' or f['filingTo']<'2021-10-01':continue
  if min((r['filingDate'] for r in filings),default='9999')<='2021-10-01':break
  if len(history)>=3:break
  raw,m=sources.get(symbol+'_history_'+f['name'],'https://data.sec.gov/submissions/'+f['name']);history.append(m)
  if raw:filings+=records(json.loads(raw))
 row['history']=history;all8=sorted({f['accessionNumber']:f for f in filings if f['form']in ['8-K','8-K/A'] and '2.02'in f.get('items','')}.values(),key=lambda f:(f['filingDate'],f['accessionNumber']));row['earnings_metadata']=[f for f in all8 if '2021-10-01'<=f['filingDate']<='2024-12-31'];selected=[];seen=set()
 window_start='2022-01-01' if company['stage']=='INITIAL' else '2024-01-01'
 for f in all8:
  day=f['filingDate']
  if f['form']!='8-K' or not window_start<=day<='2024-12-31':continue
  key=(day[:4],(int(day[5:7])-1)//3)
  if key in seen:continue
  seen.add(key);selected.append(f)
 selected=selected[:max(0,C['max_analyzed_release_events']-target_count)]
 parent=[f for f in all8 if f['form']=='8-K' and '2021-10-01'<=f['filingDate']<window_start][-1:] if parent_count<C['supporting_parent_releases_max'] else []
 target_plan={'symbol':symbol,'cik':cik,'target_filings':selected,'parent_filings':parent,'algorithm':'Frozen earliest original Item2.02 each calendarquarter, dates not returns','frozen_before_document_download':now()};p=root/(symbol+'.target_seal.json')
 if p.exists():assert {k:v for k,v in json.loads(p.read_text()).items() if k!='frozen_before_document_download'}=={k:v for k,v in target_plan.items() if k!='frozen_before_document_download'}
 else:dump(p,target_plan)
 for role,group in [('parents',parent),('targets',selected)]:
  for f in group:
   acc=f['accessionNumber'];base=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/";prior=B/'sources'/('release_'+acc)/'receipt.json';kind='SGML';primary=None;filename=None
   if prior.exists() and json.loads(prior.read_text()).get('status')=='SAVED':raw,dm=sources.get('release_'+acc,base+acc+'.txt')
   else:
    from lxml import html
    from urllib.parse import urljoin
    pr,primary=sources.get('release_primary_'+acc,base+f['primaryDocument']);links=[]
    if pr:
     d=html.fromstring(pr)
     for tr in d.xpath('//tr'):
      txt=' '.join(' '.join(tr.itertext()).split())
      if re.match(r'^99\.1(?:\s|$)',txt):links.extend(a.get('href') for a in tr.xpath('.//a[@href]'))
     if not links:links=[a.get('href') for a in d.xpath('//a[@href]') if re.search(r'(?:99[._-]?1|exhibit991)',a.get('href',''),re.I)]
     links=list(dict.fromkeys(x for x in links if x and not x.startswith('#')))
    if links:
     filename=links[0];raw,dm=sources.get('release_exhibit_'+acc,urljoin(base,filename));kind='EXHIBIT_HTML'
    else:raw=None;dm={'status':'EXHIBIT_NOT_FOUND','primary':primary};kind='UNAVAILABLE'
   row[role].append({'filing':f,'source':dm,'source_kind':kind,'exhibit_filename':filename,'primary_source':primary,'role':'supporting_parent' if role=='parents' else 'analyzed_target'})
   # No new source categories or contact retries when an access path fails repeatedly.
   if raw is None:
    failed=[json.loads(p.read_text()) for p in (B/'requests').glob('*.json')][-3:]
    if len(failed)==3 and all(x.get('http_status') in [401,403,429] for x in failed):dump(out,row);raise SystemExit('SOURCE_CIRCUIT_STOP')
  dump(out,row)
 row.update(complete=True,status='COLLECTED');dump(out,row);print(symbol,'targets',len(row['targets']),'parent',len(row['parents']),flush=True)
 # Metadata-only quarter list/correction list retained; no claim all other IR updates checked.
print('STAGE_COMPLETE',args.stage,flush=True)

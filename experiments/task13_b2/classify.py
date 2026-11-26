from common import *
from parse_guidance import extract,compare
import collections,argparse
parser=argparse.ArgumentParser();parser.add_argument('--phase',default='pilot');args=parser.parse_args();rows=[];source_counts=collections.Counter();firmcounts={}
for company in C['companies']:
 p=B/'collection'/(company['symbol']+'.json')
 if not p.exists():continue
 data=json.loads(p.read_text());previous=None;fr=[]
 for event in data.get('parents',[])+data.get('targets',[]):
  f=event['filing'];source=event['source'];item={'symbol':company['symbol'],'CIK':data['cik'],'exchange_board':company['listing_board'],'sector_current':company['sector_current'],'source':source,'accession':f['accessionNumber'],'filingDate':f['filingDate'],'event_role':event['role'],'metric_basis':company['metric_basis'],'classification':'NO_COMPARABLE_GUIDANCE','price_outcomes_queried':False}
  if source['status']!='SAVED':item['exclusion_reason']='SOURCE_FAILED';previous=None
  else:
   parsed=extract(body(source),company,f,event.get('source_kind','SGML'),event.get('exhibit_filename'));item['parsed']=parsed
   if not parsed['exhibit_documents']:item['exclusion_reason']='NO_VERIFIED_EARNINGS_EXHIBIT';previous=None
   elif not parsed['guidance']:item['classification']='AMBIGUOUS' if parsed['ambiguities'] else 'NO_COMPARABLE_GUIDANCE';item['exclusion_reason']='GUIDANCE_UNSUPPORTED_OR_ABSENT';previous=None
   else:
    possible=[]
    if previous:
     for child in parsed['guidance']:
      for parent in previous['parsed']['guidance']:
       if parent['FY']==child['FY'] and parent['basis']==child['basis']:possible.append((parent,child))
    if len(possible)==1:
     parent,child=possible[0];item.update(classification=compare(parent,child,company['symbol'],f['filingDate']),guidance_parent=parent,guidance_current=child,parent_accession=previous['accession'],parent_public_date=previous['filingDate'],parent_source=previous['source'],source_pair_grade='PAIRED_ORIGINAL_EARNINGS_RELEASE_ONLY_NOT_ALL_IR_CHANNELS',parent_latest_scope='Immediately previous collected quarter release; intervening unknown public IR cannot be assumed absent')
    else:item['exclusion_reason']='NO_UNAMBIGUOUS_SAME_FY_PARENT'
    previous=item
  if event['role']=='analyzed_target':rows.append(item);fr.append(item);source_counts[item['classification']]+=1
 firmcounts[company['symbol']]={'targets':len(fr),'guidance_found':sum(bool(x.get('parsed',{}).get('guidance')) for x in fr),'counts':dict(collections.Counter(x['classification'] for x in fr))}
dump(B/'events_classified.json',rows);dump(B/'classification_summary.json',{'counts':dict(source_counts),'firms':firmcounts,'analyzed_events':len(rows),'prices_queried':False,'LLM_calls':0})
changes=[r for r in rows if r['classification']in ['UP','DOWN']];counts=collections.Counter(r['classification'] for r in changes);gate={'pass':len(changes)>=30 and len(set(r['symbol'] for r in changes))>=12 and counts['UP']>=8 and counts['DOWN']>=8 and source_counts['UNCHANGED']>0,'raw_changes':len(changes),'changed_issuers':len(set(r['symbol'] for r in changes)),'UP':counts['UP'],'DOWN':counts['DOWN'],'UNCHANGED':source_counts['UNCHANGED'],'needs_overlap_dedup_before_final_gate':True,'no_return_based_selection':True}
dump(B/('initial_sample_gate.json' if args.phase=='initial' else args.phase+'_sample_gate.json'),gate);print(json.dumps({'counts':dict(source_counts),'sample_gate':gate,'firms':firmcounts},ensure_ascii=False))

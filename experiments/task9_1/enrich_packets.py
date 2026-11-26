"""Correct demonstrated source-packet omissions; no extra LLM or strategy tuning."""
from common import *
import re
coverage=json.loads((B/'packet_coverage_audit.json').read_text());results=[]
patterns={'shares':r'weighted.average|shares outstanding|발행주식|주당순','debt':r'total debt|long.term debt|차입금|부채','cashflow':r'cash flow|cash flows|현금흐름','earnings':r'earnings|net income|영업이익|당기순'}
for row in coverage:
 date,s=row['date'],row['symbol'];p=B/'deep'/date/s/'original.txt'
 if s.endswith('.KS'):p=B/'inputs'/date/s/'original.txt'
 if not p.exists():results.append({'date':date,'symbol':s,'status':'BLOCKED_NO_LOCAL_ORIGINAL'});continue
 text=p.read_text();start=0
 if not s.endswith('.KS') and (B/'deep'/date/s/'original.bin').read_bytes()[:4]!=b'%PDF':
  anchors={'SMCI':'Preliminary First Quarter','SMCI_update':'SAN JOSE','PR':'MIDLAND','SFM':'First Quarter Highlights','AUR':'PITTSBURGH'};anchor=anchors.get(s);assert anchor and anchor in text;start=text.index(anchor)
 body=text[start:];stop=body.find('View source version')
 if stop>=0:body=body[:stop]
 spans=[]
 for field,pattern in patterns.items():
  match=re.search(pattern,body,re.I)
  if match:
   a=start+max(0,match.start()-150);z=min(len(text),start+match.end()+900);spans.append({'field':field,'start':a,'end':z,'exact_text':text[a:z]})
 packet={'date':date,'symbol':s,'original_text_sha256':sha(p),'original_text_path':str(p.relative_to(R)),'source_record':str((B/'deep'/date/s/'packet.json').relative_to(R)),'source_boundaries':'dated primary PDF or DART original; HTML clipped to dated article anchor before related content','spans':spans,'not_new_financial_forecast':True,'not_LLM_rerun':True}
 freeze(B/'enriched_packets'/date/(s+'.json'),packet);results.append({'date':date,'symbol':s,'status':'EXTRACTED_SOURCE_SPANS_NOT_SEMANTIC_SUFFICIENCY_PASS','original_omitted_fields':[k for k in patterns if row[k]['in_original'] and not row[k]['in_worker']],'recovered_named_fields':[v['field'] for v in spans],'packet_hash':digest(packet)})
freeze(B/'enriched_packets/coverage_result.json',results);print('ENRICHED_ORIGINALS',sum(r['status'].startswith('EXTRACTED') for r in results),'MISSING',sum(r['status'].startswith('BLOCKED') for r in results))

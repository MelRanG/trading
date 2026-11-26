from pathlib import Path
import json,re,hashlib
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_historical';W=Path('/home/ansy/app/quant-diligence/task9-historical-work')
base=json.loads((W/'A2_202111.request.json').read_text());user=json.loads(base['messages'][1]['content']);packet=user['packet']
prices={p['accession']:p for p in json.loads((B/'representative_prices/manifest.json').read_text())}
for doc in packet['documents']:
 text=(B/'originals'/doc['source_id']/'original.txt').read_text()
 for s in doc['sections']:
  if s['section']!='financial':continue
  matches=list(re.finditer(r'1\.\s*요약재무정보',text));qualified=[m for m in matches if re.search('단위|매출|자산',text[m.end():m.end()+600])]
  if qualified:
   pos=qualified[0].start();s.update(start_char=pos,end_char=min(len(text),pos+2800),text=text[pos:pos+2800])
 doc['partial_price_reference']=prices.get(doc['source_id'],{'status':'MISSING'})
packet['extraction_version']='REPRESENTATIVE_V3_FINANCIAL_TOC_REPAIR_PLUS_PARTIAL_PRICES'
packet['prices']='PARTIAL_CURRENT_IDENTIFIER_MAPPING_UNVERIFIED_ACTIONS'
from importlib.machinery import SourceFileLoader
# Independent hash, no importing an executable collector.
packet['input_hash']=hashlib.sha256(json.dumps({k:v for k,v in packet.items() if k!='input_hash'},sort_keys=True,default=str,allow_nan=False).encode()).hexdigest()
user['task']+=' This is a separately versioned data repair: use actual financial summary rather than a table of contents. PARTIAL historical prices are diagnostics only, not certified same-issuer execution prices. You may provide explicit conditional scenario value arithmetic, but do not fabricate a validated target or override required-data abstention. Record changes from earlier source limitations without knowledge of its outputs.'
base['messages'][1]['content']=json.dumps(user,ensure_ascii=False);dest=W/'A3_202111.request.json'
if dest.exists():assert json.loads(dest.read_text())==base
else:dest.write_text(json.dumps(base,ensure_ascii=False))
(B/'packets/A3_202111.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2));print(packet['input_hash'])

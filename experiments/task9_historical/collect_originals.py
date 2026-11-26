"""Bounded original-accession corpus, never a reconstructed full stock universe."""
from pathlib import Path
import sys,json,hashlib,zipfile,io,re
from datetime import datetime,timezone
from lxml import etree
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);dart=OpenDartClient();b=R/'runtime/task9_historical';out=b/'originals';out.mkdir(exist_ok=True)
# Predefined BEFORE downloading/reading company evidence or later price results.
plan={'version':'PARTIAL_ORIGINAL_CORPUS_V1','status':'PARTIAL_NOT_FULL_INVESTABLE_UNIVERSE','selection':'First four unique corporate accession reports, ascending receipt number, no correction, quarterly/half-year, no current listing or future outcome filter','documents_per_date':4,'extra_dart_limit':20,'stage':'representative source feasibility + five-date partial corpus, no stage D permission','research_scope':'Original texts only; list alias/classification excluded from research input as not historical identity proof'}
p=Path(__file__).parent/'partial_corpus_contract.json'
if p.exists():assert json.loads(p.read_text())==plan
else:p.write_text(json.dumps(plan,indent=2))
manifest=[]
for month in ['202111','202311','202411','202511','202605']:
 rows=json.loads((b/'audit'/('dart_'+month+'.json')).read_text())['list'];selected=[];seen=set()
 for row in sorted(rows,key=lambda r:r['rcept_no']):
  if '[' in row['report_nm'] or not any(k in row['report_nm'] for k in ('분기보고서','반기보고서')) or row['corp_code'] in seen:continue
  selected.append(row);seen.add(row['corp_code'])
  if len(selected)==4:break
 for row in selected:
  key=row['rcept_no'];folder=out/key;folder.mkdir(exist_ok=True);meta=folder/'receipt.json'
  if meta.exists():manifest.append(json.loads(meta.read_text()));continue
  receipt={'month':month,'rcept_no':key,'corp_code':row['corp_code'],'report_name':row['report_nm'],'reported_publication_date':row['rcept_dt'],'observed_at':datetime.now(timezone.utc).isoformat(),'list_alias_not_research_fact':row['corp_name'],'list_class_not_historical_proof':row['corp_cls'],'quality':'PARTIAL'}
  try:
   raw=dart._request('document.xml',{'rcept_no':key},binary=True);(folder/'original.zip').write_bytes(raw);receipt['source_hash']=hashlib.sha256(raw).hexdigest();archive=zipfile.ZipFile(io.BytesIO(raw));names=archive.namelist();texts=[]
   for name in names:
    if not name.lower().endswith('.xml'):continue
    data=archive.read(name)
    if len(data)>15000000:raise ValueError('xml cap')
    tree=etree.fromstring(data,etree.XMLParser(recover=True,resolve_entities=False,no_network=True));text='\n'.join(' '.join(t.split()) for t in tree.itertext() if t.strip());texts.append(text)
   if not texts:raise ValueError('no original XML')
   text='\n'.join(texts);(folder/'original.txt').write_text(text);receipt.update(status='SAVED',xml_members=names,text_characters=len(text),text_hash=hashlib.sha256(text.encode()).hexdigest())
  except Exception as e:receipt.update(status='FAILED',error_type=type(e).__name__)
  meta.write_text(json.dumps(receipt,ensure_ascii=False,indent=2));manifest.append(receipt);print(month,key,receipt['status'],receipt.get('text_characters'),flush=True)
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))

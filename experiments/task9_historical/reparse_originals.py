from pathlib import Path
import json,zipfile,hashlib
from original_parser import text_and_identity
b=Path(__file__).resolve().parents[2]/'runtime/task9_historical/originals';records=[]
for folder in sorted(b.iterdir()):
 if not folder.is_dir() or not (folder/'original.zip').exists():continue
 m=json.loads((folder/'receipt.json').read_text());z=zipfile.ZipFile(folder/'original.zip');texts=[];enc=[];names=[];warnings=[]
 try:
  for member in z.namelist():
   if member.lower().endswith('.xml'):
    text,meta=text_and_identity(z.read(member));texts.append(text);enc.append(meta['encoding']);names.append(meta['original_document_company']);warnings.append(meta['xml_recovery_warnings'])
  raw='\n'.join(texts);p=folder/'original.txt'
  if not (folder/'original.declared_encoding_v0.txt').exists():p.rename(folder/'original.declared_encoding_v0.txt')
  p.write_text(raw);m.update(parse_status='SAVED',parser='STRICT_DECODING_RECOVERY_XML_V1',xml_recovery_warnings=warnings,encodings=enc,original_document_companies=names,text_characters=len(raw),text_hash=hashlib.sha256(raw.encode()).hexdigest());(folder/'receipt.json').write_text(json.dumps(m,indent=2,ensure_ascii=False));print(folder.name,names,enc,warnings)
 except Exception as e:print('PARSE_FAILED',folder.name,str(e)[:130]);m['parse_status']='FAILED';m['parse_error']=type(e).__name__
 records.append(m)
(b/'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))

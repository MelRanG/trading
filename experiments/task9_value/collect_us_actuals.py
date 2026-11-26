from pathlib import Path
import sys,json,io,re
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));sys.path.insert(0,'/home/ansy/app/quant-diligence/task6-quanta-env/lib/python3.12/site-packages')
from quant_harness.investment.equities import fetch
from quant_harness.investment.company_outcomes import Document
from pypdf import PdfReader
B=R/'runtime/task9_value';assert (B/'decision_seals.json').exists()
for x in json.loads((Path(__file__).parent/'us_actual_contract.json').read_text()):
 folder=B/'evaluator_only'/x['symbol'];p=folder/('actual_'+str(x['fiscal_year'])+'_receipt.json')
 if p.exists():continue
 try:
  raw,receipt=fetch(x['url'],folder/'actual_raw')
  if raw.startswith(b'%PDF'):text='\n'.join(p.extract_text(extraction_mode='layout') or '' for p in PdfReader(io.BytesIO(raw)).pages)
  else:d=Document();d.feed(raw.decode());text='\n'.join(d.text)
  (folder/('actual_'+str(x['fiscal_year'])+'.txt')).write_text(text)
  assert str(x['fiscal_year']) in text and any(z in text for z in [str(x['actual']),format(x['actual'],',')]),'manual actual not present in source'
  p.write_text(json.dumps({'status':'SAVED_MANUAL_FISCAL_TABLE_AUDIT','contract':x,'receipt':receipt,'caveat':'value mapped to fiscal annual GAAP diluted EPS or consolidated sales table; not extracted from generic first-number match'},indent=2));print(x['symbol'],x['fiscal_year'],'SAVED',flush=True)
 except Exception as e:p.write_text(json.dumps({'status':'FAILED','contract':x,'error_type':type(e).__name__}));print(x['symbol'],x['fiscal_year'],type(e).__name__,flush=True)

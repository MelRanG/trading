"""All remaining A2 numeric2025 forecasts; no result-driven subset selection."""
from pathlib import Path
import sys,json,hashlib,zipfile,io
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));sys.path.insert(0,str(Path(__file__).parent))
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
from original_parser import text_and_identity
W=Path('/home/ansy/app/quant-diligence/task9-historical-work');B=R/'runtime/task9_historical/evaluator_only';data=json.loads((W/'A2_202411.json').read_text());candidates=[c for c in data['candidates'] if c.get('forecasts')];plan={'rule':'All and only already-generated A2_202411 numeric forecasts, no outcome/stock-return selection; no prompt or model tuning after first2022 result','prediction_source_hash':hashlib.sha256((W/'A2_202411.json').read_bytes()).hexdigest(),'accessions':[c['accession'] for c in candidates],'max_dart_calls':6,'grade':'Exploratory original-report outcome audit, not independent holdout'}
p=B/'phase2_contract.json'
if p.exists():assert json.loads(p.read_text())==plan
else:p.write_text(json.dumps(plan,indent=2))
load_environment(R);client=OpenDartClient();manifest=json.loads((R/'runtime/task9_historical/originals/manifest.json').read_text())
for c in candidates:
 m=next(m for m in manifest if m['rcept_no']==c['accession']);folder=B/c['accession'];folder.mkdir(exist_ok=True)
 def request(name,endpoint,params,binary=False):
  p=folder/(name+('.zip' if binary else '.json'))
  if p.exists():return p.read_bytes() if binary else json.loads(p.read_text())
  if len(list(B.glob('*/api*.receipt.json')))>=6:raise ValueError('phase2 budget')
  r=client._request(endpoint,params,binary=binary);raw=r if binary else json.dumps(r,sort_keys=True,ensure_ascii=False).encode();p.write_bytes(raw);(folder/(name+'.receipt.json')).write_text(json.dumps({'endpoint':endpoint,'public_params':params,'source_hash':hashlib.sha256(raw).hexdigest(),'observed_at':datetime.now(timezone.utc).isoformat()},indent=2));return r
 listing=request('api_list','list.json',{'corp_code':m['corp_code'],'bgn_de':'20260301','end_de':'20260430','pblntf_ty':'A','page_count':100,'sort':'date','sort_mth':'asc','last_reprt_at':'N'})
 rows=[r for r in listing.get('list',[]) if r['report_nm']=='사업보고서 (2025.12)']
 if not rows:(folder/'status.json').write_text(json.dumps({'status':'MISSING_ORIGINAL_ANNUAL_REPORT'}));continue
 original=rows[0];raw=request('api_original','document.xml',{'rcept_no':original['rcept_no']},True);z=zipfile.ZipFile(io.BytesIO(raw));texts=[]
 for n in z.namelist():
  if n.lower().endswith('.xml'):t,_=text_and_identity(z.read(n));texts.append(t)
 text='\n'.join(texts);(folder/'original.txt').write_text(text)
 # Prefer the SAME reporting scope as the original forecast summary evidence.
 scope='CFS' if '연결' in next((s['text'] for d in json.loads((R/'runtime/task9_historical/packets/A2_202411.json').read_text())['documents'] if d['source_id']==c['accession'] for s in d['sections'] if s['section']=='financial'),'') else 'OFS'
 structured=request('api_statement','fnlttSinglAcntAll.json',{'corp_code':m['corp_code'],'bsns_year':'2025','reprt_code':'11011','fs_div':scope})
 (folder/'status.json').write_text(json.dumps({'status':'COLLECTED','forecast_accession':c['accession'],'company_id':m['corp_code'],'original_report':original,'statement_scope':scope,'original_accession_match':bool(structured.get('list')) and all(r['rcept_no']==original['rcept_no'] for r in structured.get('list',[]))},ensure_ascii=False,indent=2));print(c['original_company'],original['rcept_no'],scope,structured.get('status'),flush=True)

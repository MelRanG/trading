"""Evaluator-only future observations; NEVER mounted in a research worker."""
from pathlib import Path
import sys,json,hashlib,zipfile,io
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));sys.path.insert(0,str(Path(__file__).parent))
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
from original_parser import text_and_identity
load_environment(R);c=OpenDartClient();B=R/'runtime/task9_historical/evaluator_only';B.mkdir(exist_ok=True)
# This source is chosen from a SEALED forecast, not subsequent stock performance.
W=Path('/home/ansy/app/quant-diligence/task9-historical-work');prediction=json.loads((W/'A2_202111.json').read_text());selected=[x for x in prediction['candidates'] if x.get('forecasts')]
selection={'forecast_source_hash':hashlib.sha256((W/'A2_202111.json').read_bytes()).hexdigest(),'selection_rule':'First candidate with independent2022 forecast in original A2; maximum one company, no price outcome filter','max_dart_calls':3,'selected':selected[0]['accession'] if selected else None}
p=B/'contract.json'
if p.exists():assert json.loads(p.read_text())==selection
else:p.write_text(json.dumps(selection,indent=2))
if not selected:print('NO_ELIGIBLE_NUMERIC_FORECAST');sys.exit(0)
x=selected[0];m=next(x for x in json.loads((R/'runtime/task9_historical/originals/manifest.json').read_text()) if x['rcept_no']==selection['selected']);corp=m['corp_code']
def saved(name,endpoint,params,binary=False):
 p=B/(name+('.zip' if binary else '.json'))
 if p.exists():return p.read_bytes() if binary else json.loads(p.read_text())
 if len(list(B.glob('*.receipt.json')))>=3:raise ValueError('outcome budget')
 data=c._request(endpoint,params,binary=binary);raw=data if binary else json.dumps(data,sort_keys=True,ensure_ascii=False).encode();p.write_bytes(raw);(B/(name+'.receipt.json')).write_text(json.dumps({'endpoint':endpoint,'public_params':params,'available_at':datetime.now(timezone.utc).isoformat(),'source_hash':hashlib.sha256(raw).hexdigest()},indent=2));return data
listdata=saved('list_2023','list.json',{'corp_code':corp,'bgn_de':'20230301','end_de':'20230430','pblntf_ty':'A','page_count':100,'last_reprt_at':'N','sort':'date','sort_mth':'asc'})
rows=[r for r in listdata.get('list',[]) if r['report_nm']=='사업보고서 (2022.12)']
if not rows:print('NO_ORIGINAL_ANNUAL_REPORT');sys.exit(0)
row=rows[0];raw=saved('original_2022','document.xml',{'rcept_no':row['rcept_no']},True);z=zipfile.ZipFile(io.BytesIO(raw));texts=[]
for n in z.namelist():
 if n.lower().endswith('.xml'):t,meta=text_and_identity(z.read(n));texts.append(t)
(B/'original_2022.txt').write_text('\n'.join(texts))
api=saved('structured_2022','fnlttSinglAcntAll.json',{'corp_code':corp,'bsns_year':'2022','reprt_code':'11011','fs_div':'OFS'})
(B/'outcome_manifest.json').write_text(json.dumps({'forecast_accession':x['accession'],'company_id':corp,'original_report':row,'api_original_accession_match':all(r['rcept_no']==row['rcept_no'] for r in api.get('list',[])) and bool(api.get('list')),'scope':'Ground truth is future data held only in evaluator directory','price_results':'NOT_COLLECTED'},ensure_ascii=False,indent=2));print(row['rcept_no'],[(r['account_nm'],r.get('thstrm_amount'),r.get('currency'),r['rcept_no']) for r in api.get('list',[]) if r.get('account_id') in ('ifrs-full_Revenue','dart_OperatingIncomeLoss')])

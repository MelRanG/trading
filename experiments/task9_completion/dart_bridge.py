"""Bounded additional DART evidence using the already configured key."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);c=OpenDartClient();B=R/'runtime/task9_completion/dart';B.mkdir(exist_ok=True)
originals=[m for m in json.loads((R/'runtime/task9_historical/originals/manifest.json').read_text()) if m['month']=='202111' and m['rcept_no']!='20211101000152'];result=[]
for m in originals:
 folder=B/m['corp_code'];folder.mkdir(exist_ok=True);items=[]
 for name,endpoint,params in [('shares_2021q3','stockTotqySttus.json',{'corp_code':m['corp_code'],'bsns_year':'2021','reprt_code':'11013'}),('disclosures_2021q4','list.json',{'corp_code':m['corp_code'],'bgn_de':'20211001','end_de':'20211231','page_count':100,'page_no':1,'sort':'date','sort_mth':'asc','last_reprt_at':'N'}),('disclosures_2022q1','list.json',{'corp_code':m['corp_code'],'bgn_de':'20220101','end_de':'20220331','page_count':100,'page_no':1,'sort':'date','sort_mth':'asc','last_reprt_at':'N'})]:
  p=folder/(name+'.json');meta=folder/(name+'.receipt.json')
  if not p.exists():
   if len(list(B.glob('*/*.receipt.json')))>=20:raise ValueError('DART research budget')
   receipt={'endpoint':endpoint,'public_params':params,'at':datetime.now(timezone.utc).isoformat(),'status':'RESERVED'};meta.write_text(json.dumps(receipt))
   try:data=c._request(endpoint,params);raw=json.dumps(data,sort_keys=True,ensure_ascii=False).encode();p.write_bytes(raw);receipt.update(status=data.get('status'),source_hash=hashlib.sha256(raw).hexdigest())
   except Exception as e:receipt.update(status='FAILED',error_type=type(e).__name__)
   meta.write_text(json.dumps(receipt,indent=2))
  if not p.exists():items.append({'name':name,'status':'FAILED'});continue
  data=json.loads(p.read_text());rows=data.get('list',[]);item={'name':name,'status':data.get('status'),'total_count':data.get('total_count'),'received':len(rows)}
  if name.startswith('shares'):
   item['rows']=rows;item['source_accession_before_research_cutoff']=all(r.get('rcept_no','')[:8]<='20211130' for r in rows) and bool(rows)
  else:
   item['potential_action_or_identity_events']=[{'rcept_no':r['rcept_no'],'report_nm':r['report_nm'],'rcept_dt':r['rcept_dt']} for r in rows if any(word in r['report_nm'] for word in ['배당','증자','분할','합병','상호','주식','거래정지','상장폐지'])];item['complete_page']=len(rows)==data.get('total_count',len(rows))
  items.append(item)
 row={'corp_code':m['corp_code'],'original_accession':m['rcept_no'],'original_name':m['original_document_companies'],'sources':items,'action_completeness':'NOT_CERTIFIED_BY_KEYWORD_ABSENCE_OR_SINGLE_PAGE'};result.append(row);print(m['corp_code'],[(x['name'],x['status'],x.get('received')) for x in items],flush=True)
(B/'bridge.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))

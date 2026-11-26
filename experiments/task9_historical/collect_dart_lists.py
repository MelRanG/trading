"""Restore broad monthly source lists; never use latest-only correction filtering."""
from pathlib import Path
import sys,json,hashlib
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);c=OpenDartClient();b=R/'runtime/task9_historical/audit'
for month in ['202111','202311','202411','202511','202605']:
 p=b/('dart_'+month+'.json')
 if p.exists():continue
 params={'bgn_de':month+'01','end_de':month+('31' if month.endswith('05') else '30'),'pblntf_ty':'A','page_count':100,'page_no':1,'sort':'date','sort_mth':'asc','last_reprt_at':'N'}
 r={'provider':'OPENDART','endpoint':'list.json','public_params':params,'observed_at':datetime.now(timezone.utc).isoformat()}
 try:
  data=c._request('list.json',params);raw=json.dumps(data,ensure_ascii=False,sort_keys=True).encode();p.write_bytes(raw);r.update(status=data.get('status'),sha256=hashlib.sha256(raw).hexdigest(),total_count=data.get('total_count'),rows=len(data.get('list',[])))
 except Exception as e:r.update(status='FAILED',error_type=type(e).__name__)
 (b/('dart_'+month+'.receipt.json')).write_text(json.dumps(r,indent=2))

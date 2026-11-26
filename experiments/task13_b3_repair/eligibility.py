"""Single audited mask route; no economic parameters or signal changes."""
from common import *
import pandas as pd
NATIVE={r['symbol']:r for r in json.loads((R/'runtime/task13_r0/native_manifest/assets.json').read_text())if r['market']=='US'}
PATCH={r['storage_symbol']:r for r in json.loads((B/'reconciled_admission.json').read_text())}
IDENTITY=json.loads((B/'identity_overlay.json').read_text());REFERENCES={}

def asof_identity(storage_symbol,day):
 row=next((x for x in IDENTITY['entries']if x['storage_symbol']==storage_symbol),None)
 if row is None:return {'symbol':storage_symbol,'identity_source':'INHERITED_R0_NATIVE_CURRENT_METADATA_PARTIAL'}
 for t in row['timeline']:
  if t['from']<=day and (t['until']is None or day<=t['until']):return {'symbol':t['symbol'],'exchange':t['exchange'],'CIK':row['CIK'],'identity_source':'OFFICIAL_CONTINUITY_AUDIT'}
 raise ValueError('NO_CONFIRMED_ASOF_IDENTITY')

def qualified_mask(symbol,frame,geometry,quality):
 base=geometry & quality.eligible.reindex(frame.index).eq(True)
 if symbol.startswith('^'):return base  # inherited index mask deliberately unchanged
 if symbol in PATCH:
  rec=PATCH[symbol];path=R/rec['path'];expected=rec['sha256'];scope='VERIFIED_FOUR_IDENTITY_OVERLAY'
 else:
  if symbol not in NATIVE:raise ValueError('UNKNOWN_NATIVE_IDENTITY_FAIL_CLOSED')
  rec=NATIVE[symbol];path=R/rec['eligibility_path'];expected=rec['eligibility_hash'];scope='INHERITED_NATIVE_ELIGIBILITY_NO_OVERRIDE'
 assert sha(path)==expected,'ELIGIBILITY_REVISION';mask=pd.read_csv(path,index_col='date',parse_dates=True).eligible.reindex(frame.index).eq(True)
 REFERENCES[symbol]={'path':str(path.relative_to(R)),'sha256':expected,'scope':scope};return base & mask

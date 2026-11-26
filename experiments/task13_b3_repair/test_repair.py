import json
from pathlib import Path
import pandas as pd,numpy as np,pytest
from common import R,B,C,sha
from eligibility import qualified_mask,asof_identity
from run_corrected import prepare,reserve

def test_old_transfer_boundary_bug_reproduced_and_repaired():
 for s in ['KMB','HLT','PLTR','SGI']:
  root=R/'runtime/task13_r0/accepted/US'/s;f=pd.read_csv(root/'adjusted.csv',index_col='date',parse_dates=True);q=pd.read_csv(root/'quality_mask.csv',index_col='date',parse_dates=True);day=pd.Timestamp('2021-04-01');assert q.loc[day,'eligible']
  old=next(x for x in json.loads((B/'identity_overlay.json').read_text())['entries']if x['storage_symbol']==s)
  assert day<pd.Timestamp(old['original_bad_listDate'])
  assert qualified_mask(s,f,pd.Series(True,index=f.index),q).loc[day]

def test_alias_exchange_and_prelisting_are_time_specific():
 assert asof_identity('SGI','2020-01-02')['symbol']=='TPX'
 assert asof_identity('SGI','2025-02-18')['symbol']=='SGI'
 assert asof_identity('PLTR','2024-11-25')['exchange']=='NYSE'
 assert asof_identity('PLTR','2024-11-26')['exchange']=='NASDAQ'
 with pytest.raises(ValueError):asof_identity('PLTR','2020-09-29')


def test_quality_and_corporate_action_failure_never_reenabled():
 for s in ['KMB','HLT','PLTR','SGI']:
  root=R/'runtime/task13_r0/accepted/US'/s;f=pd.read_csv(root/'adjusted.csv',index_col='date',parse_dates=True);q=pd.read_csv(root/'quality_mask.csv',index_col='date',parse_dates=True);got=qualified_mask(s,f,pd.Series(True,index=f.index),q)
  assert not got.loc[q.eligible.eq(False)].any()
  assert not got.loc[got.index>'2024-12-31'].any()
 s='PLTR';f=pd.DataFrame(index=pd.to_datetime(['2020-09-29','2020-09-30']));q=pd.DataFrame({'eligible':[True,True]},index=f.index);got=qualified_mask(s,f,pd.Series(True,index=f.index),q);assert not got.iloc[0]


def test_other_native_mask_is_inherited_without_widening():
 root=R/'runtime/task13_r0/accepted/US/LIN';f=pd.read_csv(root/'adjusted.csv',index_col='date',parse_dates=True);q=pd.read_csv(root/'quality_mask.csv',index_col='date',parse_dates=True);native=pd.read_csv(root/'native_eligibility.csv',index_col='date',parse_dates=True).eligible.reindex(f.index).eq(True);got=qualified_mask('LIN',f,pd.Series(True,index=f.index),q);assert got.equals(q.eligible.eq(True)&native)


def test_original_algorithm_and_inputs_preserved():
 ns=prepare();assert ns['P']['H']==60 and ns['P']['direction']==1
 assert sha(R/'runtime/task13_b3/signal_events.json')==C['original_signal_SHA']
 assert sha(R/'runtime/task13_b3/evaluation.json')==C['original_evaluation_SHA']


def test_evaluation_reservation_is_at_most_once(tmp_path):
 p=tmp_path/'attempt.json';reserve(p)
 with pytest.raises(FileExistsError):reserve(p)

def test_completed_single_run_preserves_events_features_and_stock_returns():
 old=json.loads((R/'runtime/task13_b3/evaluated_events.json').read_text());new=json.loads((B/'replay_v2/evaluated_events.json').read_text());a={r['accession']:r for r in old};b={r['accession']:r for r in new};assert a.keys()==b.keys()
 for acc in a:
  for key in ['symbol','entry','exit','filed_date','controls_last_close','sector']:assert a[acc][key]==b[acc][key]
  for key in ['margin_delta','MOM20','REV5','VOL20','stock_H60']:assert abs(a[acc][key]-b[acc][key])<1e-9
 rec=json.loads((B/'corrected_evaluation_attempt.json').read_text());assert rec['status']=='COMPLETED'and rec['corrected_evaluation_number']==1
 assert sha(B/'replay_v2/evaluation.json')==rec['evaluation_SHA']


def test_corrected_peer_labels_use_contemporaneous_TPX():
 rows=json.loads((B/'replay_v2/evaluated_events_with_identity.json').read_text());seen=0
 for row in rows:
  if 'SGI'in row['peer_membership']:
   i=row['peer_identities_asof_entry']['SGI'];assert i['symbol']=='TPX'and i['CIK']=='0001206264';seen+=1
 assert seen>0

import json,hashlib
from pathlib import Path
import pandas as pd,numpy as np
from common import B,P,R,sha
from fundamentals import values
from evaluate import fitted,labels

def test_frozen_signals_and_publication_boundary():
 seal=json.loads((B/'signal_seal.json').read_text());assert sha(B/'signal_events.json')==seal['events_SHA'] and sha(B/'plan.json')==seal['plan_SHA']
 assert P['H']==60 and P['direction']==1
 events=json.loads((B/'signal_events.json').read_text())
 for e in events:
  assert len(e['facts'])==4
  assert all(f['original_accession']==e['accession'] and f['published']==e['filed_date'] for f in e['facts'])
  assert all('2019-01-01'<=f['period_start']<=f['period_end']<='2024-12-31'for f in e['facts'])


def test_future_revision_does_not_replace_original_accession_and_conflicts_fail():
 a={'accn':'original','start':'2020-01-01','end':'2020-03-31','val':10}
 b={**a,'accn':'future-amendment','val':99}
 assert values([a,b],'original')[('2020-01-01','2020-03-31')][1]['val']==10
 assert not values([a,{**a,'val':11}],'original')


def test_native_H60_open_label_has_no_day_zero_fill():
 days=pd.bdate_range('2020-01-01',periods=65);f=pd.DataFrame({'open':np.arange(1,66,dtype=float)},index=days)
 y,end=labels({'US_BENCHMARK':f,'TEST':f},'US',60,'2021-01-01');assert y.iloc[0,0]==62/2-1 and end.iloc[0]==days[61]
 altered=f.copy();altered.iloc[30,0]=np.nan;y2,_=labels({'US_BENCHMARK':f,'TEST':altered},'US',60,'2021-01-01');assert pd.isna(y2.iloc[0,0])


def test_coefficient_units_against_known_linear_relation():
 rng=np.random.default_rng(7);N=120;x=rng.normal(0,.03,N);d=pd.DataFrame({'margin_delta':x,'MOM20':rng.normal(size=N),'REV5':rng.normal(size=N),'VOL20':rng.uniform(.01,.05,N),'year':np.tile([2020,2021,2022,2023,2024],24),'sector':np.tile(['A','B','C'],40),'symbol':np.repeat([str(i)for i in range(10)],12)})
 d['sector_relative']=2*x+.1*d.MOM20
 o=fitted(d);assert abs(o['effect_per1pp_margin']-.02)<1e-10


def test_actual_evaluation_keeps_cost_and_historical_limitations():
 d=json.loads((B/'evaluation.json').read_text());assert d['verdict']=='NO_INCREMENTAL_EVIDENCE'
 assert d['controls_strictly_before_filing'] and d['horizon_reconciliation_rows']==105
 assert d['primary']['design_rank']==d['primary']['design_columns']
 assert d['no_risk_cash_weights_or_trades'] and 'costs_not_deducted'in d
 assert any(v<0 for v in d['leave_one_issuer_out_per1pp'].values())

def test_native_basic_eligibility_disagreement_invalidates_economic_claim():
 final=json.loads((B/'result_summary.json').read_text());audit=json.loads((B/'post_evaluation_quality_audit.json').read_text())
 assert final['verdict']=='DATA_BLOCKED' and final['qualified_incremental_prediction']is None
 assert audit['affected_evaluated_events']==74 and set(audit['unresolved_peer_symbols'])=={'PLTR','KMB','HLT','SGI'}
 assert sha(B/'evaluation.json')==audit['provisional_evaluation_SHA']
 assert not audit['production_or_source_masks_changed'] and audit['return_rows_removed_or_retested']==0

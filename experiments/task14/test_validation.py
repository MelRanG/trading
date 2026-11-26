from pathlib import Path
import json,sys,hashlib
import numpy as np,pandas as pd
sys.path.insert(0,str(Path(__file__).parent))
from stats_eval import block_mean,holm,residual,corr
R=Path(__file__).resolve().parents[2];B=R/'runtime/task14'
def test_centered_null_and_no_fake_constant_correlation():
 assert block_mean(pd.Series(np.ones(100)),20,samples=199)['p_positive']==.005
 assert block_mean(pd.Series(-np.ones(100)),20,samples=199)['p_positive']==1
 assert np.isnan(corr(np.ones(20)*.003,np.arange(20)))
def test_dependency_and_missing_calendar_not_iid():
 rng=np.random.default_rng(14);x=pd.Series(np.repeat(rng.normal(size=20),10));a=block_mean(x,1,samples=999);b=block_mean(x,20,samples=999);assert b['CI95'][1]-b['CI95'][0]>a['CI95'][1]-a['CI95'][0]
 x.iloc[50:60]=np.nan;c=block_mean(x,20,samples=99);assert c['n']==190 and c['calendar_slots']==200
 assert c==block_mean(x,20,samples=99)
def test_holm_and_projection_do_not_optimize_future_returns():
 assert np.allclose(holm([.01,.04,.03]),[.03,.06,.06]);z=np.arange(40.);x=2*z+np.sin(z);r,b=residual(x,z);assert abs(r.sum())<1e-10 and abs(r@z)<1e-8
 y=z[::-1];assert np.allclose(residual(x,z)[0],r) # target not an input to residual scores
 assert np.isnan(corr(residual(2*z,z)[0],y))
def test_actual_family_and_old_preservation():
 v=json.loads((B/'validation.json').read_text());assert len(v['primary_tests'])==10 and v['unexecuted_p1_slots']==8
 p=[x['p'] for x in v['primary_tests']]+[1.]*8;assert np.allclose(holm(p)[:10],[x['holm18_p'] for x in v['primary_tests']]);assert not any(x['pass05'] for x in v['primary_tests'])
 m=json.loads((R/'runtime/task13/artifact_manifest.json').read_text());assert all(hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256'] for x in m['files'])
def test_real_aggregate_attribution_not_selected_new_strategy():
 d=pd.read_csv(B/'factor_daily.csv');g=d[(d.id=='V_ROC20')&(d.market=='KR')];c=pd.read_csv(B/'factor_tail_contributions.csv');c=c[(c.id=='V_ROC20')&(c.market=='KR')]
 assert np.isclose(c.weighted_contribution.sum()/len(g),g.spread.mean());assert np.isclose(g.spread,g.top_mean-g.bottom_mean).all()
 assert g.spread.median()<0 and g.spread.mean()>0
 s=json.loads((B/'supplement.json').read_text());assert s['zero_new_models_or_data'];assert s['RD_native_metric_parity']['KR']['QLIB_TREE']['constant_or_near_constant_dates']>0

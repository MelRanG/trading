"""Synthetic and real feature-only checks; no research H5 outcomes queried."""
import json,sys
from pathlib import Path
import numpy as np,pandas as pd,pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from factor import features,estimate_beta_sigma,labels,forward_valid
from common import R,S,read_before,bool_col,loaded,reserve
from evaluate import partial_rank


def fixture():
    rng=np.random.default_rng(130301);days=pd.bdate_range('2017-01-03',periods=500)
    rm=rng.normal(.0001,.01,len(days));r=.001+1.7*rm+rng.normal(0,.018,len(days))
    return (pd.Series(100*np.exp(np.cumsum(r)),index=days),pd.Series(True,index=days),pd.Series(100*np.exp(np.cumsum(rm)),index=days))


def oracle(c,g,m,mg,t):
    p=c.where(g);market=m.where(mg);r=np.log(p).diff();rm=np.log(market).diff();i=c.index.get_loc(t)
    y=r.iloc[i-125:i-5].to_numpy();x=rm.iloc[i-125:i-5].to_numpy();ok=np.isfinite(x)&np.isfinite(y);assert ok.sum()>=110
    slope=np.linalg.lstsq(np.column_stack([np.ones(ok.sum()),x[ok]]),y[ok],rcond=None)[0]
    sig=np.std(y[ok]-slope[1]*x[ok],ddof=1)
    shock=r.iloc[i-4:i+1].sum()-slope[1]*rm.iloc[i-4:i+1].sum()
    return slope[1],sig,-shock/(np.sqrt(5)*sig)


def test_literal_120_window_and_score_oracle():
    c,g,m=fixture();f=features(c,g,m,g)
    for i in [126,250,400]:
        beta,sigma,score=oracle(c,g,m,g,c.index[i]);np.testing.assert_allclose(f.iloc[i][['beta','sigma','signal']], [beta,sigma,score],rtol=1e-9,atol=1e-10)
    assert f.signal.iloc[:125].isna().all()


def test_no_future_or_prefix_dependence():
    c,g,m=fixture();old=features(c,g,m,g);cut=300;c2=c.copy();m2=m.copy();c2.iloc[cut+1:]*=17;m2.iloc[cut+1:]*=.2
    pd.testing.assert_frame_equal(old.iloc[:cut+1],features(c2,g,m2,g).iloc[:cut+1])
    pd.testing.assert_frame_equal(old.iloc[:cut+1],features(c.iloc[:cut+1],g.iloc[:cut+1],m.iloc[:cut+1],g.iloc[:cut+1]))


def test_recent_five_and_gap_day_not_in_estimation():
    c,g,m=fixture();i=300;f=features(c,g,m,g);changed=c.copy();changed.iloc[i-5:]*=.8
    revised=features(changed,g,m,g);np.testing.assert_allclose(revised.iloc[i][['beta','sigma']],f.iloc[i][['beta','sigma']],rtol=1e-12)
    # A one-time price step on t-5 is outside both estimation and t-4..t shock.
    np.testing.assert_allclose(revised.iloc[i].signal,f.iloc[i].signal,atol=1e-12)
    changed=c.copy();changed.iloc[i:]*=.8;revised=features(changed,g,m,g)
    np.testing.assert_allclose(revised.iloc[i][['beta','sigma']],f.iloc[i][['beta','sigma']],rtol=1e-12)
    assert revised.iloc[i].signal>f.iloc[i].signal


def test_minimum110_pairs_and_positive_sigma():
    rng=np.random.default_rng(1);ix=pd.bdate_range('2020-01-01',periods=300);x=pd.Series(rng.normal(0,.01,300),index=ix);y=x+pd.Series(rng.normal(0,.01,300),index=ix);t=200
    z=y.copy();z.iloc[t-125:t-115]=np.nan;b,s,n=estimate_beta_sigma(z,x);assert n.iloc[t]==110 and np.isfinite(b.iloc[t])
    z.iloc[t-115]=np.nan;b,s,n=estimate_beta_sigma(z,x);assert n.iloc[t]==109 and pd.isna(b.iloc[t])
    b,s,n=estimate_beta_sigma(y,pd.Series(0.,index=ix));assert s.isna().all() and b.isna().all()


def test_missing_price_does_not_bridge_and_masks_restore_warmup():
    c,g,m=fixture();g.iloc[299]=False;f=features(c,g,m,g)
    assert f.signal.iloc[299:362].isna().all()
    assert pd.notna(f.signal.iloc[363])
    c.iloc[298]=np.nan;f=features(c,g,m,g);assert pd.isna(f.signal.iloc[300])


def test_h5_open_alignment_and_full_path_and_cutoff():
    ix=pd.bdate_range('2024-01-01',periods=30);op=pd.Series(np.arange(30)+10.,index=ix);g=pd.Series(True,index=ix)
    y=labels(op,g);assert y.iloc[3]==op.iloc[9]/op.iloc[4]-1
    assert y.iloc[-6:].isna().all()
    g.iloc[8]=False;y=labels(op,g);assert pd.isna(y.iloc[3])
    assert (y.notna()<=forward_valid(g)).all()


def test_partial_rank_definition_not_rank_of_residuals():
    rng=np.random.default_rng(4);a=rng.normal(size=(100,6));value,frac=partial_rank(a)
    ranks=pd.DataFrame(a).rank(method='average').to_numpy();z=np.column_stack([np.ones(100),ranks[:,1:4]])
    x=ranks[:,0]-z@np.linalg.lstsq(z,ranks[:,0],rcond=None)[0];y=ranks[:,-1]-z@np.linalg.lstsq(z,ranks[:,-1],rcond=None)[0]
    np.testing.assert_allclose(value,np.corrcoef(x,y)[0,1],atol=1e-14)
    a[:,0]=a[:,1];value,frac=partial_rank(a);assert np.isnan(value) and frac<1e-20


def test_second_evaluation_reservation_fails(tmp_path):
    path=tmp_path/'once.json';reserve(path)
    with pytest.raises(FileExistsError):reserve(path)


def test_actual_fit_feature_samples_match_independent_formula():
    assets=json.loads((S/'native_manifest/assets.json').read_text());by={a['symbol']:a for a in assets if a['market']=='US'}
    p=S/'accepted/US/^GSPC';market=read_before(p/'quote.csv',cutoff='2022-12-31');days=market.index;mg=bool_col(read_before(p/'quality_mask.csv',cutoff='2022-12-31').reindex(days))
    for symbol in ['MSFT','PEP','GOOGL']:
        bars,g=loaded(by[symbol],days);f=features(bars.close,g,market.close,mg);t=f.signal.dropna().index[-1]
        beta,sigma,score=oracle(bars.close,g,market.close,mg,t)
        np.testing.assert_allclose(f.loc[t,['beta','sigma','signal']],[beta,sigma,score],rtol=1e-8,atol=1e-9)


def test_existing_block_bootstrap_reproducible_and_holm():
    sys.path.insert(0,str(R/'experiments/task14'));from stats_eval import block_mean,holm
    s=pd.Series([.01,np.nan,.03,-.01,.02]*30)
    a=block_mean(s,5,samples=5000,seed=130301);b=block_mean(s,5,samples=5000,seed=130301)
    assert a==b and a['calendar_slots']==150 and a['block']==5 and a['CI95'][0]<=a['mean']<=a['CI95'][1]
    assert holm([.001,1,1])==[.003,1.,1.]


def test_machine_geometry_rounding_is_not_price_or_mask_repair():
    from common import numeric_geometry
    f=pd.DataFrame({'open':[60.,60.],'high':[60.984966278076165,60.],'low':[59.,59.],'close':[60.98496627807617,61.]})
    assert numeric_geometry(f).tolist()==[True,False]

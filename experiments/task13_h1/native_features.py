"""Run the frozen R1 alternative with original Quanta operators, before labels."""
from pathlib import Path
import json
import runpy

import numpy as np
import pandas as pd

from experiments.task13_h1.prepare_inputs import OUT, sha, write_json

LIB=Path('/native/quantaalpha/factors/coder/function_lib.py')


def frames(z):
    dates=pd.DatetimeIndex(z['dates'],name='datetime')
    symbols=pd.Index(z['symbols'],name='instrument')
    return {k:pd.DataFrame(z[k],index=dates,columns=symbols) for k in ['open','high','low','close','volume']}


def flatten(data):
    return data.stack(future_stack=True)


def raw_score(p, ops):
    close, high, low, volume=(p[k] for k in ['close','high','low','volume'])
    location=(close-low)/(high-low+1e-8)
    nvol=flatten(volume)
    past=ops['DELAY'](ops['TS_MEDIAN'](nvol,20),1)
    baseline=past.unstack()
    relative=volume/(baseline+1e-8)
    recent=volume.notna().rolling(20,min_periods=20).sum().shift().eq(20)
    relative=relative.where(recent&baseline.gt(0))
    location=location.where(high.gt(low))
    full=location.notna().rolling(10,min_periods=10).sum().eq(10) & relative.notna().rolling(10,min_periods=10).sum().eq(10)
    varying=location.rolling(10,min_periods=10).max().gt(location.rolling(10,min_periods=10).min()) & (
        relative.rolling(10,min_periods=10).max().gt(relative.rolling(10,min_periods=10).min()))
    warm=close.notna().rolling(63,min_periods=63).sum().eq(63)
    mask=full&varying&warm
    source=ops['TS_CORR'](flatten(location),flatten(relative),10).unstack()
    score=source.where(mask)
    oracle_baseline=volume.rolling(20,min_periods=20).median().shift()
    pd.testing.assert_frame_equal(baseline.where(recent),oracle_baseline,rtol=1e-12,atol=1e-12)
    oracle=location.rolling(10,min_periods=10).corr(relative).where(mask)
    pd.testing.assert_frame_equal(score,oracle,rtol=1e-9,atol=1e-9)
    return score


def make(market, ops):
    z=np.load(OUT/f'{market}_panel.npz')
    p=frames(z)
    score=raw_score(p,ops)
    cut=len(score)//2
    prefix=raw_score({k:f.iloc[:cut] for k,f in p.items()},ops)
    pd.testing.assert_frame_equal(score.iloc[:cut],prefix)
    rng=np.random.default_rng(131601)
    altered={k:f.copy() for k,f in p.items()}
    perturb=rng.uniform(.75,1.4,size=p['close'].iloc[cut:].shape)
    for k in ['open','high','low','close']:
        altered[k].iloc[cut:]*=perturb
    altered['volume'].iloc[cut:]*=1.9
    changed=raw_score(altered,ops)
    pd.testing.assert_frame_equal(score.iloc[:cut],changed.iloc[:cut])
    close,op=p['close'],p['open']
    ret=close.pct_change(fill_method=None)
    decomposition=np.log(op/close.shift())-np.log(close/op)
    base={
        'MOM20':close/close.shift(20)-1, 'MOM63':close/close.shift(63)-1,
        'MOM10':close/close.shift(10)-1,'VOL10':ret.rolling(10,min_periods=10).std(),
        'ON_MINUS_ID60':decomposition.rolling(60,min_periods=60).mean(),
    }
    path=OUT/f'{market}_features.npz'
    np.savez_compressed(path,score=score.to_numpy(),**{k:v.to_numpy() for k,v in base.items()})
    return {'raw_valid_features':int(score.count().sum()),'sha256':sha(path),'causal_prefix':True,
            'future_perturbation':True,'literal_oracle_match':True,'declared_assets':len(score.columns)}


def main():
    assert not (OUT/'feature_gate.json').exists()
    ops=runpy.run_path(str(LIB))
    receipt=json.loads((OUT/'input_receipt.json').read_bytes())
    for m,data in receipt['checks'].items():
        assert sha(OUT/f'{m}_panel.npz')==data['panel_sha256']
    members={m:make(m,ops) for m in ('US','KR')}
    write_json(OUT/'feature_gate.json',{'operator_sha256':sha(LIB),'worker_sha256':sha(Path(__file__)), 'members':members,
                                      'inputs_sha256':sha(OUT/'input_receipt.json'),
                                      'contract_sha256':sha(OUT/'research_contract.json')})
    print(members,flush=True)


if __name__=='__main__':
    main()

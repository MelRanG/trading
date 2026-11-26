"""Rebuild narrow R0 adjusted research panel with original identities and receipts."""
from collections import defaultdict
from hashlib import file_digest, sha256
from io import BytesIO
import json
from pathlib import Path
import tarfile

import numpy as np
import pandas as pd

from experiments.research_references import source

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'runtime/task13_h1'
begin,end='2022-07-01','2024-12-31'


def write_json(path,obj):
    with path.open('x') as f:
        json.dump(obj,f,indent=2,ensure_ascii=False,allow_nan=False)
        f.write('\n')


def sha(path):
    with path.open('rb') as f:
        return file_digest(f,'sha256').hexdigest()


def main():
    path=source(ROOT,'runtime/task13_r0/native_manifest/assets.json')
    assets=[a for a in json.loads(path.read_bytes()) if a['cohort']=='CORE']
    groups={m:sorted((a for a in assets if a['market']==m),key=lambda x:x['symbol']) for m in ['US','KR']}
    assert {m:len(a) for m,a in groups.items()}=={'US':176,'KR':119}
    req={a[f+'_path']:a[f+'_hash'] for a in assets for f in ['adjusted','eligibility']}
    calendars={a['calendar_path'] for a in assets}
    regimes={m:f'runtime/task13_r0/{s}_regimes.csv' for m,s in [('US','US'),('KR','KOSPI')]}
    archive=json.loads((ROOT/'runtime/research_reference/index.json').read_bytes())
    inv=Path(archive['archive_inventory'])
    assert sha(inv)==archive['archive_inventory_sha256']
    inventory=json.loads(inv.read_bytes())
    for p in calendars|set(regimes.values()):
        req[p]=inventory[p]['sha256']
    frames={}
    def put(name,b):
        assert sha256(b).hexdigest()==req[name],name
        frame=pd.read_csv(BytesIO(b),index_col='date',parse_dates=['date']).loc[begin:end]
        assert frame.index.is_unique and frame.index.is_monotonic_increasing
        frames[name]=frame
    for name in req:
        p=source(ROOT,name)
        if p.exists():
            put(name,p.read_bytes())
    needed=req.keys()-frames.keys()
    if needed:
        b=Path(archive['archive'])
        assert sha(b)==archive['archive_sha256']
        with tarfile.open(b,'r|gz') as f:
            for m in f:
                if m.name in needed:
                    put(m.name,f.extractfile(m).read())
                    needed.remove(m.name)
                    if not needed:
                        break
    assert not needed
    checks={}
    cols=['open','high','low','close','volume']
    for market,group in groups.items():
        calendars=[frames[p].index for p in sorted({a['calendar_path'] for a in group})]
        days=calendars[0]
        assert all(days.equals(other) for other in calendars[1:]),'different market calendars'
        panel=defaultdict(dict)
        for a in group:
            s=a['symbol']
            f=frames[a['adjusted_path']].reindex(days)[cols]
            valid=frames[a['eligibility_path']].eligible.reindex(days).eq(True)
            valid &= np.isfinite(f).all(axis=1) & f.gt(0).all(axis=1)
            assert not ((f.high<f[['open','close','low']].max(axis=1)-1e-9)|
                        (f.low>f[['open','close','high']].min(axis=1)+1e-9)).loc[valid].any(),s
            for k in cols:
                panel[k][s]=f[k].where(valid)
        filename=OUT/f'{market}_panel.npz'
        matrix={k:pd.DataFrame(v).to_numpy(dtype=float) for k,v in panel.items()}
        np.savez_compressed(filename,**matrix,dates=days.astype(str).to_numpy(dtype=str),
                            symbols=np.array([a['symbol'] for a in group]),
                            regime=frames[regimes[market]].AS_OF_REGIME.reindex(days).fillna('UNKNOWN').to_numpy(dtype=str))
        checks[market]={'assets':len(group),'dates':len(days),'valid_rows':int(np.isfinite(matrix['close']).sum()),
                        'panel_sha256':sha(filename),'missing_regime':int(frames[regimes[market]].AS_OF_REGIME.reindex(days).isna().sum())}
    write_json(OUT/'input_receipt.json',{'source_hashes':req,'asset_manifest_sha256':sha(path),'checks':checks,
                                        'research_contract_sha256':sha(OUT/'research_contract.json')})
    print(checks,flush=True)


if __name__=='__main__':
    main()

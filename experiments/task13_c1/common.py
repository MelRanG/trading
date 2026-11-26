from pathlib import Path
from datetime import datetime, timezone
import hashlib, json
import pandas as pd
R = Path(__file__).resolve().parents[2]
B = R / 'runtime/task13_c1'
S = R / 'runtime/task13_r0'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(name, value):
    p = B / name
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def now():
    return datetime.now(timezone.utc).isoformat()


def read_before(p, cutoff='2024-12-31'):
    # Never use numerical prices after 2024, including in feature normalization.
    pieces = []
    with pd.read_csv(p, index_col='date', parse_dates=True, chunksize=512) as chunks:
        for part in chunks:
            if part.index.has_duplicates or not part.index.is_monotonic_increasing:
                raise ValueError('Duplicate or unordered sessions: ' + str(p))
            pieces.append(part.loc[:cutoff])
            if part.index.max() > pd.Timestamp(cutoff):
                break
    result = pd.concat(pieces)
    if result.index.has_duplicates or not result.index.is_monotonic_increasing:
        raise ValueError('Invalid full session order')
    return result


def bool_col(frame):
    col = frame['eligible']
    if not col.dropna().isin([True, False]).all():
        raise ValueError('Non-boolean eligibility')
    return col.astype('boolean').fillna(False).astype(bool)


def loaded(asset, days):
    path = R / asset['adjusted_path']
    price = read_before(path).reindex(days)
    basic = bool_col(read_before(path.parent / 'quality_mask.csv').reindex(days))
    native = bool_col(read_before(R / asset['eligibility_path']).reindex(days))
    # Do not replace masks with B3 overlay or reconstruct historical listDate.
    if (native & ~basic).any():
        raise ValueError('Native eligibility admits a basic-masked bar: ' + asset['symbol'])
    return price, native & basic


def reserve(path):
    with Path(path).open('x') as f:
        json.dump({'status': 'STARTED', 'at': now(), 'maximum_evaluations': 1}, f)


def numeric_geometry(frame):
    import numpy as np
    scale=frame[['open','high','low','close']].abs().max(axis=1)
    tolerance=8*np.finfo(float).eps*scale
    return ((frame.high+tolerance)>=frame[['open','close','low']].max(axis=1)) & ((frame.low-tolerance)<=frame[['open','close','high']].min(axis=1))

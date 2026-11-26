import sys,json,hashlib
from pathlib import Path
import pytest
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import network
from loader import supervised

def test_cache_resume_hash_and_terminal_error(tmp_path,monkeypatch):
 monkeypatch.setattr(network,'B',tmp_path)
 url='https://example.invalid/one'
 folder=tmp_path/'http'/hashlib.sha256(url.encode()).hexdigest();folder.mkdir(parents=True)
 raw=tmp_path/'raw';raw.write_bytes(b'original')
 (folder/'receipt.json').write_text(json.dumps({'path':str(raw),'source_hash':hashlib.sha256(raw.read_bytes()).hexdigest()}))
 monkeypatch.setattr(network,'fetch',lambda *a,**k:pytest.fail('cache must not fetch'))
 assert network.Network().get(url)[0]==b'original'
 raw.write_bytes(b'changed')
 with pytest.raises(AssertionError):network.Network().get(url)
 (folder/'receipt.json').unlink();(folder/'failure_0.json').write_text('{"status":404}')
 with pytest.raises(network.PermanentError,match='CACHED_HTTP_404'):network.Network().get(url)
 assert not (tmp_path/'requests.jsonl').exists()

def test_labels_next_open_horizon_and_no_future_leak():
 days=pd.bdate_range('2020-01-01',periods=180)
 idx=pd.MultiIndex.from_product([days,['A','B']],names=['datetime','instrument'])
 x=np.repeat(np.arange(180,dtype=float)+100,2)
 d=pd.DataFrame({k:x.copy() for k in ['$open','$high','$low','$close','$volume']},index=idx)
 a,meta=supervised(d,20,cutoff=str(days[140].date()))
 t=a.index.get_level_values(0)[0];i=days.get_loc(t)
 assert a['label'].iloc[0,0]==pytest.approx((100+i+21)/(100+i+1)-1)
 d.loc[days[141]:,:]=999999
 b,_=supervised(d,20,cutoff=str(days[140].date()))
 pd.testing.assert_frame_equal(a,b)
 assert pd.Timestamp(meta['last_target'])<=days[140]
 assert i>=63
 # A missing session invalidates all labels spanning it, never jumps over it.
 d.loc[(days[100],'A'),:]=np.nan
 c,_=supervised(d,20,cutoff=str(days[140].date()))
 assert (days[90],'A') not in c.index

def test_actual_source_geometry_identity_and_adjustment():
 from quality import normalize
 root=Path(__file__).resolve().parents[3]
 q=json.loads((root/'runtime/task13_r0/accepted/US/AAPL/quality.json').read_text())
 payload=json.loads((root/q['source_receipt']['path']).read_text())
 import copy
 bad=copy.deepcopy(payload);r=bad['chart']['result'][0];r['timestamp'][1]=r['timestamp'][0]
 with pytest.raises(AssertionError,match='DUPLICATE'):normalize(bad,'AAPL','US',q['observed_at'])
 with pytest.raises(AssertionError,match='IDENTITY_SYMBOL'):normalize(payload,'WRONG','US',q['observed_at'])
 bad=copy.deepcopy(payload);bad['chart']['result'][0]['indicators']['quote'][0]['close'][0]=-1
 f,mask,audit,_,_=normalize(bad,'AAPL','US',q['observed_at'])
 assert audit['rejected_rows'] and audit['rejected_rows'][0]['reason']=='NONPOSITIVE_OR_GEOMETRY'
 assert (f.close>0).all() and not f.index.duplicated().any()
 # Existing normalizer's adjustment is applied consistently to every OHLC field.
 ratio=f.close/f.raw_close
 for col in ['open','high','low','close']:
  np.testing.assert_allclose(f[col],f['raw_'+col]*ratio,rtol=1e-12)

"""Research-only seal validation and price consensus. No order authority."""
from common import *
import math

def research_seal():
 p=B/'research_seal.json';z=json.loads(p.read_text());assert z['contract_hash']==sha(Path(__file__).parent/'contract.json')
 for m in ['US','KR']:
  for kind in ['request','result']:
   row=z['markets'][m][kind];assert sha(R/row['path'])==row['sha256'],'CHANGED_FROZEN_RESEARCH'
 return z

def choose_observation(values):
 for a,b in [('YAHOO','NAVER'),('TOSS','NAVER'),('YAHOO','TOSS')]:
  v,w=values.get(a),values.get(b)
  if v is not None and w is not None and math.isfinite(v) and math.isfinite(w) and v>0 and w>0 and abs(v/w-1)<=.005:return w,{'pair':[a,b],'values':[v,w]}
 return None,{'status':'NO_TWO_SOURCE_AGREEMENT','values':values}

def asset_list():
 research_seal();p=B/'sealed_assets.json';x=json.loads(p.read_text());assert digest(x)==json.loads((B/'research_seal.json').read_text())['asset_list_hash'];return x

"""Serial checkpointed collection, no model use. pilot/batch gates are explicit."""
from pathlib import Path
import json,datetime,sys,traceback,hashlib
from urllib.parse import quote
from network import Network,B,CircuitOpen
from quality import validate_and_save
START=int(datetime.datetime(2017,1,1,tzinfo=datetime.timezone.utc).timestamp());END=int(datetime.datetime(2026,11,14,tzinfo=datetime.timezone.utc).timestamp())
def collect(asset,net):
 folder=B/'accepted'/asset['market']/asset['symbol'];q=folder/'quality.json'
 if q.exists() and json.loads(q.read_text()).get('quality_policy_version')==2:
  d=json.loads(q.read_text());assert all(hashlib.sha256((folder/p).read_bytes()).hexdigest()==h for p,h in d['output_hashes'].items());return {'symbol':asset['symbol'],'market':asset['market'],'status':'REUSED_ACCEPTED','rows':d['structural_valid_rows']}
 url='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(asset['symbol'],safe='')+f'?interval=1d&period1={START}&period2={END}&events=div%2Csplits';raw,r=net.get(url);d=validate_and_save(json.loads(raw),r,asset,folder);return {'symbol':asset['symbol'],'market':asset['market'],'status':d['status'],'rows':d['structural_valid_rows'],'masked':d['unverified_jumps']+d['zero_volume']}
if __name__=='__main__':
 mode=sys.argv[1];n=Network();universe=json.loads((B/'universe.json').read_text());pilot=json.loads((B/'pilot.json').read_text());lookup={a['symbol']:a for a in universe}
 if mode=='pilot':
  todo=[lookup.get(x['symbol'],{'symbol':x['symbol'],'market':'KR' if '.' in x['symbol'] else 'US','selection_source':'PREREGISTERED_SCHEMA_PILOT','PIT_membership':'SURVIVOR_RESEARCH'}) for x in pilot]
 else:
  gate=json.loads((B/'pilot_quality_gate.json').read_text());assert gate['all10_structural_pass'],'Pilot quality failed; no expansion';todo=json.loads((B/'smallcap_universe.json').read_text()) if mode=='small' else universe
 records=[];bad_common=0
 for i,a in enumerate(todo):
  try:r=collect(a,n);bad_common=0
  except CircuitOpen as e:
   r={'symbol':a['symbol'],'market':a['market'],'status':'BLOCKED_CIRCUIT','reason':str(e)};records.append(r);(B/(mode+'_collection.json')).write_text(json.dumps(records,indent=2));raise
  except Exception as e:
   r={'symbol':a['symbol'],'market':a['market'],'status':'FAILED_QUARANTINED','error_type':type(e).__name__,'reason':str(e)[:180]};folder=B/'quarantine';folder.mkdir(exist_ok=True);(folder/(a['symbol']+'.json')).write_text(json.dumps(r));bad_common+=int(isinstance(e,(KeyError,AssertionError,json.JSONDecodeError)))
   if bad_common>=3:raise RuntimeError('COMMON_SCHEMA_OR_IDENTITY_CIRCUIT') from e
  records.append(r);(B/(mode+'_collection.json')).write_text(json.dumps(records,indent=2));print(i+1,len(todo),r['symbol'],r['status'],flush=True)
  if mode!='pilot' and (i+1)%25==0:
   # Next batch only after completed records persisted; no LLM or refetch of successful assets.
   (B/'batch_checkpoint.json').write_text(json.dumps({'completed':i+1,'total':len(todo),'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'failures':sum(x['status']=='FAILED_QUARANTINED' for x in records)},indent=2))
 if mode=='pilot':(B/'pilot_quality_gate.json').write_text(json.dumps({'all10_structural_pass':len(records)==10 and all(r['status'] in ['ACCEPTED_PARTIAL_RESEARCH','REUSED_ACCEPTED'] for r in records),'records':records,'no_generalized_PIT_claim':True},indent=2))

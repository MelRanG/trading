"""Lexical provenance audit, immutable output seals, and honest replay blocks."""
from pathlib import Path
import sys,json,hashlib,shutil
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_historical';W=Path('/home/ansy/app/quant-diligence/task9-historical-work');sys.path.insert(0,str(Path(__file__).parent));from replay_contract import seal,guarded_replay
out=B/'research_outputs';out.mkdir(exist_ok=True);audit=[];seals=[]
for stage in ['A2_202111','A2_202311','A2_202411','A2_202511','A2_202605','A3_202111','B3_202111','C3_202111']:
 p=W/(stage+'.json')
 if not p.exists():audit.append({'stage':stage,'status':'NOT_COMPLETED'});continue
 x=json.loads(p.read_text());request=json.loads((W/(stage+'.request.json')).read_text());user=json.loads(request['messages'][1]['content']);packet=user.get('packet',user.get('common_foundation'));given={d['source_id']:d for d in packet['documents']};issues=[];quotes=0;exact=0
 for c in x.get('candidates',[]):
  if c['accession'] not in given:issues.append('UNSUPPLIED_CANDIDATE:'+c['accession'])
  for f in c.get('facts',[]):
   quotes+=1;sid=f['source_id'];q=f['quote'];path=B/'originals'/sid/'original.txt'
   if not path.exists():path=B/'audit'/(sid+'.txt')
   source=path.read_text() if path.exists() else ''
   if q and q in source:exact+=1
   else:issues.append({'type':'QUOTE_NOT_EXACTLY_FOUND','source_id':sid,'quote':q})
 if x.get('input_hash')!=packet['input_hash']:issues.append('MODEL_ECHOED_INPUT_HASH_MISMATCH')
 h=seal(B/'seals'/(stage+'.json'),x);seals.append({'stage':stage,'output_hash':h,'input_hash':packet['input_hash']})
 for suffix in ('.json','.raw.txt','.request.json'):
  src=W/(stage+suffix)
  if src.exists():shutil.copy2(src,out/src.name)
 audit.append({'stage':stage,'status':'LEXICAL_CHECK_PASS' if not issues else 'PARTIAL_REQUIRES_FACT_AUDIT','candidates':len(x.get('candidates',[])),'quotes':quotes,'exact_quotes':exact,'issues':issues,'warning':'Exact quote is not a semantic, unit, period or historical-identity proof'})
coverage=[]
for month in ['202111','202311','202411','202511','202605']:
 for market in ('US','KR'):
  p={'coverage':{'historical_universe':'PARTIAL' if market=='KR' else 'UNVERIFIED','listing_and_identifiers':'PARTIAL' if market=='KR' else 'UNVERIFIED','official_sessions':'UNVERIFIED','eligible_execution_prices':'PARTIAL' if market=='KR' and month=='202111' else 'UNVERIFIED','actions_dividends_delistings':'UNVERIFIED','original_information_versions':'PARTIAL' if market=='KR' else 'UNVERIFIED'},'information_cutoff':month[:4]+'-'+month[4:]+'-01T00:00:00Z','sources':[],'weights':None}
  result=guarded_replay(p,lambda x:(_ for _ in ()).throw(AssertionError('must not execute without evidence')));coverage.append({'market':market,'month':month,'cutoff':'CIVIL_MONTH_END_RESEARCH_ONLY_OFFICIAL_SESSION_UNCONFIRMED','coverage':p['coverage'],'execution':result})
usage={}
for p in (B/'model_calls').rglob('*.reserved.json'):
 r=json.loads(p.read_text());s=usage.setdefault(r['engine'],{'attempts':0,'succeeded':0,'failed_or_pending':0,'known_tokens':0,'unknown_usage':0,'money_cost':None});s['attempts']+=1;s['succeeded']+=r['status']=='SUCCEEDED';s['failed_or_pending']+=r['status']!='SUCCEEDED';s['known_tokens']+=r.get('measured_tokens',0);s['unknown_usage']+=not bool(r.get('usage'))
(B/'evaluation/provenance_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2));(B/'seals/manifest.json').write_text(json.dumps(seals,indent=2));(B/'coverage.json').write_text(json.dumps(coverage,indent=2));(B/'model_usage.json').write_text(json.dumps({'scopes':usage,'preflight_oversize_rejections_not_llm_calls':2,'model':'gpt-6.1-terra','historical_not_forward':True},indent=2));print(json.dumps({'models':usage,'quotes':[(r['stage'],r.get('quotes'),r.get('exact_quotes'),r['status']) for r in audit],'full_replay_eligible_market_dates':0,'simulated_portfolio_returns_generated':0},ensure_ascii=False,indent=2))

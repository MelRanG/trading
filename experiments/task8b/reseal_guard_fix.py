"""Explicit bug-fix reseal of UNFILLED exploration only, same research/weights."""
from pathlib import Path
import json,sys,hashlib,psycopg
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.exploration import research_store,account_store
from quant_harness.investment.stockpaper import seal
b=R/'runtime/task8b';store,cfg=research_store(R);source=R/'src/quant_harness/investment/exploration.py';worker=hashlib.sha256(source.read_bytes()).hexdigest();folder=b/'code_versions';folder.mkdir(exist_ok=True);(folder/(worker+'.py')).write_bytes(source.read_bytes());out=[]
for row in json.loads((b/'sealed_plans.json').read_text()):
 old_id=row['plan_id'];old=store.get(old_id);account=account_store(cfg,old['market'])
 if old['worker_hash']==worker:continue
 with psycopg.connect(account.url) as conn:
  fills=conn.execute('SELECT count(*) FROM stock_fill WHERE decision_id=%s',(old['paper_decision_id'],)).fetchone()[0]
  if fills:raise ValueError('cannot reseal filled research')
 account.state(old['paper_decision_id'],'INVALIDATED_VERSION',{'reason':'EXPLORATION_POSTCOST_CAP_GUARD_BUGFIX_NO_ALPHA_CHANGE'})
 original=account.get(old['paper_decision_id']);prices={s:{'meta':{'instrumentType':'EQUITY'}} for s in old['weights']};identity,payload=seal(account,R,old['market'],original['analysis'],prices,old['catalog_id'])
 plan={**old,'paper_decision_id':identity,'worker_hash':worker,'sealed_at':payload['sealed_at'],'supersedes_unfilled_plan':old_id,'reseal_reason':'POSTCOST_EXPLORATION_CAP_GUARD_BUGFIX_SAME_WEIGHTS_HYPOTHESES'};new_id=store.put('exploration_plan',plan);store.state(old_id,'SUPERSEDED_UNFILLED',{'successor':new_id,'fills':0});out.append({'market':old['market'],'old_plan':old_id,'new_plan':new_id,'paper_decision_id':identity,'weights':old['weights'],'sealed_at':payload['sealed_at'],'hypotheses_or_weights_changed':False})
(b/'guard_reseal.json').write_text(json.dumps(out,indent=2));store.export(b/'research_records.jsonl');print(json.dumps(out,indent=2))

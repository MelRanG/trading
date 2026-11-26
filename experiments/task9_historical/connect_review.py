"""Separate durable research queue; normal official Factory registration only."""
from pathlib import Path
import sys,json,hashlib,subprocess
from datetime import datetime,timezone,timedelta
import psycopg
from psycopg import sql
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
from quant_harness.investment.research import digest
from quant_harness.alpha_research_factory import register_review_proposal
B=R/'runtime/task9_historical';db='quant_task3_task9_history';role='quant_task9_history'
with psycopg.connect('postgresql://quant_task3@127.0.0.1:55432/postgres',autocommit=True) as conn:
 if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone():conn.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION').format(sql.Identifier(role)))
 if not conn.execute('SELECT 1 FROM pg_database WHERE datname=%s',(db,)).fetchone():conn.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(db),sql.Identifier(role)))
store=Store('postgresql://'+role+'@127.0.0.1:55432/'+db,'TASK9_HISTORICAL_ONLY');queue=Queue(store)
manifest=json.loads((B/'originals/manifest.json').read_text());identity=store.put('historical_source_snapshot',{'version':'TASK9_SOURCE_AUDIT_V1','manifest_hash':digest(manifest),'full_pit_replay':'BLOCKED','current_alias_is_not_past_identity':True})
problems=[{'kind':'DATA_PIT','target':'historical_universe_sessions_actions','evidence':'SEC/KRX403, current aliases differ from original reports, no delisting/action chain','engine':'Source workers first, not more alpha LLM','budget':'No purchase; cap source feasibility tests before new replay','validation':'Original listings/identifier intervals, official sessions, corrections and action reconciliation; then one common-input fully eligible replay'}, {'kind':'RESEARCH_EXTRACTION','target':'financial_table_grounding','evidence':'XML declared encoding mismatch and TOC versus real financial summary, recover warnings','engine':'Vibe research facts + deterministic parser','budget':'12 independent source documents, one process diagnostic','validation':'Exact quotes, units, periods, original issuer, source exclusions before model judgment'}, {'kind':'FORECAST_QUALITY','target':'independent_numeric_scenarios','evidence':'One historical operating forecast is not independent alpha; compare against naive annualization','engine':'Vibe valuation/company analysis','budget':'Forward preregistered multi-company forecasts, no historical retuning','validation':'Period/unit-aligned forecast errors, archived guidance/consensus where available; later price performance separate'}]
jobs=[]
for problem in problems:
 payload={'source_snapshot':identity,'problem':problem,'historical_not_forward':True,'automatic_strategy_changes':False};jobs.append(queue.enqueue('TASK9_RESEARCH_REQUEST',payload));store.put('historical_improvement_request',payload)
proposal={'problem_evidence':{'manifest_hash':digest(manifest),'case_count':len(manifest),'identity_warning':'Current DART alias is not original issuer name; use accession original','source_snapshot':identity},'target':'source','expected_effect':'Prevent current-alias, XML extraction and unavailable-session evidence from being treated as historically tradeable company research','falsification':'No source-integrity improvement on12 independent archived company documents, or unverifiable transformations','champion':'CURRENT_METADATA_AND_UNQUALIFIED_ARCHIVE_ASSUMPTION','challenger':'TASK9_ACCESSION_GROUNDED_PIT_GATE_V1','input_hash':digest(manifest),'budget':{'experiments':1,'parameter_search':0},'stop_conditions':['Missing original accession','Less than12 independent companies','Budget or priority unavailable','Attempt to interpret historical diagnostic as alpha'],'evaluation_metric':['Original identity match','Exact quote and unit/period match','Proper exclusion of unsupported session/action claims'],'minimum_cases':12,'split':'PROCESS_DIAGNOSTIC_ONLY','worker_hash':hashlib.sha256((Path(__file__).parent/'replay_contract.py').read_bytes()).hexdigest()}
(B/'factory_proposal.json').write_text(json.dumps(proposal,indent=2))
p=B/'factory_handoff.json'
if p.exists():status=json.loads(p.read_text())
else:
 try:status={'status':'REGISTERED','attempt':register_review_proposal(R,proposal),'experiment_status':'NOT_RESERVED_NOT_EXECUTED'}
 except ValueError as e:status={'status':'BLOCKED_REGISTRATION','reason':str(e),'experiment_status':'NOT_RESERVED_NOT_EXECUTED'}
 p.write_text(json.dumps(status,indent=2))
receipt={'database':db,'source_record':identity,'research_jobs':jobs,'factory':status,'promotion':False,'operating_db_modified':False};store.put('historical_handoff',receipt);store.export(B/'research_records.jsonl');(B/'review_handoff.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))

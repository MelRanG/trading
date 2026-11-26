"""Task3 read-only inputs -> sealed review -> official Factory -> bounded A/B."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import uuid
import psycopg
from .store import Store
from .research import digest
from .review import Source,policy,process_review,score_mature_outcome,proposal_context,process_worker_hash
from .review_jobs import Queue
from .review_experiment import worker_hash
from quant_harness.alpha_research_factory import register_review_proposal,record_review_experiment,reserve_review_experiment,find_review_hypothesis


def sealed_review(store,packet,cfg):
    store.put('review_policy',cfg,digest(cfg))
    key='PROCESS-'+digest({'packet':digest(packet),'policy':digest(cfg),'worker_hash':process_worker_hash()})
    try:return key,store.get(key)
    except ValueError:pass
    result=process_review(packet,cfg)
    store.put('review_process',result,key)
    return key,result


def experiment_bundle(packets,cfg):
    # Reference audit is made from original immutable source records, not the
    # challenger outputs. No returns, ranking labels or trading alpha involved.
    return {'worker':'review_manifest_v1','minimum_cases':cfg['minimum_independent_cases'],
            'cases':[{'packet':{k:p.get(k) for k in ('source_decision_id','contract_hash','input_hash','algorithm_hash')},
                      'evaluator_trace_complete':all(bool(p.get(k)) for k in cfg['required_trace_fields'])} for p in packets]}


def propose(process,bundle):
    issues={f['issue'] for f in process['findings']}
    if 'PROVENANCE_GAP' not in issues:
        return {'status':'NO_CHANGE','reason':'NO_ELIGIBLE_IMPLEMENTED_IMPROVEMENT_HYPOTHESIS','evidence':proposal_context(process)}
    return {'status':'PROPOSED','proposal':{
        'problem_evidence':proposal_context(process),'target':'review',
        'expected_effect':'Detect absent sealed algorithm/version fields before treating a review as reproducible.',
        'falsification':'No paired accuracy gain or false defect flags on independently labeled records.',
        'champion':'TASK3_IMMUTABLE_JSON_INTEGRITY_ONLY','challenger':'REQUIRED_VERSION_TRACE_AUDIT_V1',
        'input_hash':digest(bundle),'budget':{'experiments':1,'parameter_search':0},
        'stop_conditions':['input hash mismatch','worker version change','unavailable labels','budget exceeded'],
        'evaluation_metric':'trace completeness accuracy / missed defects, not investment return',
        'minimum_cases':bundle['minimum_cases'],'split':'PROCESS_DIAGNOSTIC_ONLY','worker_hash':worker_hash()}}


def run_isolated(bundle):
    """New process running an audited built-in worker, never LLM-generated code."""
    with tempfile.TemporaryDirectory(prefix='quant-review-eval-') as folder:
        source,target=Path(folder)/'input.json',Path(folder)/'result.json'
        source.write_text(json.dumps(bundle,allow_nan=False));source.chmod(0o400)
        env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','LANG','LC_ALL')}
        env['PYTHONPATH']=str(Path(__file__).resolve().parents[2])
        completed=subprocess.run([sys.executable,'-m','quant_harness.investment.review_experiment',str(source),str(target)],
            cwd=folder,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        if completed.returncode or not target.exists():raise RuntimeError('isolated evaluation failed')
        return json.loads(target.read_text())


def run_cycle(root,source_url,review_url,decision_id,**kwargs):
    from urllib.parse import urlsplit
    if urlsplit(source_url).path==urlsplit(review_url).path:
        raise ValueError('source and review DBs must be distinct')
    guard=Store(review_url,'TASK4_REVIEW_ONLY')
    with guard.lock():
        return _run_cycle(root,source_url,review_url,decision_id,**kwargs)


def registered_experiment(root,attempt,bundle,directory=None):
    """A shared lock + durable result cache prevents duplicate actual executions."""
    import fcntl
    out=Path(directory) if directory else Path(root)/'runtime/alpha_research_factory/task4'
    reserve_review_experiment(root,attempt,directory=out)
    folder=out/'results';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(attempt['attempt_id']+'.json')
    with (folder/(attempt['attempt_id']+'.lock')).open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        if path.exists():
            result=json.loads(path.read_text())
            if result['input_hash']!=digest(bundle) or result['worker_hash']!=worker_hash():raise ValueError('immutable experiment cache conflict')
            return result
        result=run_isolated(bundle)
        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(result,sort_keys=True,allow_nan=False))
        with temporary.open('r') as written:os.fsync(written.fileno())
        temporary.replace(path)
        return result


def _run_cycle(root,source_url,review_url,decision_id,*,comparison_ids=(),factory_directory=None,labels=None):
    if source_url==review_url:raise ValueError('source and review DBs must be distinct')
    root=Path(root);cfg=policy(root)
    source=Source(source_url);store=Store(review_url,'TASK4_REVIEW_ONLY');queue=Queue(store)
    packet=source.process_packet(root,decision_id)
    packet_id=store.put('review_process_input',packet)
    job_id=queue.enqueue('PROCESS_REVIEW',{'packet_id':packet_id,'policy_hash':digest(cfg),'worker_hash':process_worker_hash()})
    owner=str(uuid.uuid4());claim=queue.claim(owner,cfg['research_job_lease_seconds'],job_id)
    if claim:
        try:
            review_id,review=sealed_review(store,packet,cfg)
            queue.finish(job_id,owner,review_id,'NO_CHANGE' if review['classification']=='NO_CHANGE' else 'DONE')
        except Exception as exc:
            queue.fail(job_id,owner,type(exc).__name__);raise
    else:
        with psycopg.connect(store.url) as conn:
            state=conn.execute('SELECT status FROM review_job WHERE job_id=%s',(job_id,)).fetchone()[0]
        if state not in ('DONE','NO_CHANGE'):
            return {'decision_id':decision_id,'proposal_status':'WAITING_RESEARCH_LEASE_OR_FAILED_JOB','outcome_status':'PENDING','job_id':job_id}
        review_id,review=sealed_review(store,packet,cfg)
    event_registration=None
    trigger_issue=next((f['issue'] for f in review['findings'] if f['issue']!='PROVENANCE_GAP'),None)
    if trigger_issue:
        event={'kind':'UNVERIFIED_SOURCE' if trigger_issue=='UNVERIFIED_SOURCE' else 'EXECUTION_EXCEPTION',
               'available_at':packet['cutoff'],'source_hash':digest(packet),
               'record_id':packet_id,'source_market':packet['market'],'reason':trigger_issue}
        immediate=enqueue_event(store,decision_id,event)
        event_registration=run_event_job(root,store,immediate,factory_directory=factory_directory)
    # Only after process seal is persisted does evaluator obtain outcomes.
    availability=source.current_outcome_availability(decision_id)
    from .review_execution import audit_execution
    execution_audit=audit_execution(source,decision_id)
    execution_audit_id=store.put('review_execution_audit',execution_audit)
    outcome=score_mature_outcome(review,packet,cfg,labels)
    outcome_id=store.put('review_outcome',{'decision_id':decision_id,'process_review_id':review_id,
                                         'availability':availability,'execution_audit_id':execution_audit_id,'evaluation':outcome})
    followup=queue.enqueue('OUTCOME_REVIEW',{'decision_id':decision_id,'process_review_id':review_id,'horizons':cfg['strategy_horizons'].get(packet['strategy_id'],[])})
    followup_owner=str(uuid.uuid4());claim=queue.claim(followup_owner,cfg['research_job_lease_seconds'],followup)
    if claim:queue.finish(followup,followup_owner,outcome_id,'PENDING_LABELS' if outcome['status']=='PENDING' else 'DONE')
    packets=[packet]
    for url,other_id in comparison_ids:
        packets.append(Source(url).process_packet(root,other_id))
    bundle=experiment_bundle(packets,cfg)
    proposal=propose(review,bundle)
    proposal_id=store.put('review_proposal_decision',proposal)
    result={'event_registration':event_registration,'decision_id':decision_id,'process_review_id':review_id,'process_findings':review['findings'],
            'outcome_status':outcome['status'],'outcome_id':outcome_id,'proposal_status':proposal['status'],'proposal_record_id':proposal_id,
            'source_mutation_calls':0,'broker_mutation_calls':0,'automatic_promotion':False,'followup_job_id':followup}
    if proposal['status']=='PROPOSED':
        existing=find_review_hypothesis(root,proposal['proposal'],directory=factory_directory)
        if existing:
            result.update(proposal_status='EXISTING_HYPOTHESIS_FOLLOWUP',factory_attempt_id=existing['attempt_id'],experiment_reexecuted=False)
            result_id=store.put('review_cycle_result',result)
            return {**result,'record_id':result_id}
        attempt=register_review_proposal(root,proposal['proposal'],directory=factory_directory)
        # Registry is official; DB keeps an immutable pointer, not a second approval.
        store.put('review_factory_registration',attempt)
        reserve_review_experiment(root,attempt,directory=factory_directory)
        bundle_id=store.put('review_evaluator_input',bundle)
        execution_id='EXPERIMENT-'+attempt['attempt_id']
        try:measured=store.get(execution_id)
        except ValueError:
            measured=registered_experiment(root,attempt,bundle,directory=factory_directory)
            store.put('review_experiment_result',measured,execution_id)
        official=record_review_experiment(root,attempt,measured,directory=factory_directory)
        store.put('review_factory_result',official)
        result.update(factory_attempt_id=attempt['attempt_id'],experiment_id=execution_id,experiment=measured)
    result_id=store.put('review_cycle_result',result)
    return {**result,'record_id':result_id}


def enqueue_event(store,decision_id,event):
    """Immediate research task, without retroactively changing the decision."""
    from .discovery import instant,now
    if set(event)-{'kind','available_at','source_hash','record_id','source_market','reason','next_observation_at'}:
        raise ValueError('unapproved event context; results/holdout cannot enter research triggers')
    if event['kind'] not in policy(Path(__file__).resolve().parents[3])['immediate_triggers']:
        raise ValueError('unregistered event trigger')
    if instant(event['available_at'])>instant(now()):raise ValueError('future trigger event')
    if not event.get('source_hash'):raise ValueError('event provenance required')
    payload={'decision_id':decision_id,'event':event,'authority':'RESEARCH_ONLY_NO_STRATEGY_MUTATION'}
    return Queue(store).enqueue('EVENT_RESEARCH',payload,event.get('next_observation_at'))


def run_event_job(root,store,job_id,*,factory_directory=None):
    """Immediate follow-up registration; unknown source efficacy remains pending."""
    cfg=policy(root);queue=Queue(store);owner=str(uuid.uuid4())
    claim=queue.claim(owner,cfg['research_job_lease_seconds'],job_id)
    if not claim:return {'status':'ALREADY_CLAIMED_OR_COMPLETE','job_id':job_id}
    try:
        if claim['kind']!='EVENT_RESEARCH':raise ValueError('wrong event worker')
        payload=claim['payload'];event=payload['event']
        reason=event.get('reason','')
        target='source' if event['kind']=='UNVERIFIED_SOURCE' or reason=='REQUIRED_INPUT_MISSING' else 'strategy' if reason in ('RISK_POLICY_VIOLATION','INELIGIBLE_INTENT') else 'prompt' if reason=='CITATION_NOT_RECONSTRUCTABLE' else 'review'
        proposal={'problem_evidence':{'event':event,'decision_id':payload['decision_id']},'target':target,
          'expected_effect':{'source':'Improve verified source coverage before decision use.','strategy':'Reproduce and eliminate registered risk-policy violations in isolation; no parameter optimization.','prompt':'Improve citation/uncertainty discipline without exposing holdout outcomes.','review':'Improve independent review traceability.'}[target],
          'falsification':'No gain in independently verified coverage/precision at equal collection cost.',
          'champion':'CURRENT_SOURCE_AND_TRACE_POLICY','challenger':'OFFICIAL_SOURCE_VERIFICATION_RESEARCH_V1' if target=='source' else target.upper()+'_VERIFICATION_RESEARCH_V1',
          'input_hash':digest(payload),'budget':{'experiments':1,'parameter_search':0},
          'stop_conditions':['unverifiable timestamps','unapproved network source','budget exceeded','holdout exposure'],
          'evaluation_metric':'verified new evidence, false positives and cost','minimum_cases':cfg['minimum_independent_cases'],
          'split':'PREREGISTERED_FORWARD','worker_hash':worker_hash()}
        attempt=find_review_hypothesis(root,proposal,directory=factory_directory) or register_review_proposal(root,proposal,directory=factory_directory)
        result={'status':'PENDING_EVIDENCE','experiment_executed':False,'attempt':attempt,
                'reason':'No independently verified source labels; no metrics fabricated. Existing daily experiment reservation is not bypassed.'}
        identity=store.put('event_research_registration',result)
        queue.finish(job_id,owner,identity,'PENDING_EVIDENCE',event.get('next_observation_at'))
        return {'job_id':job_id,'record_id':identity,**result}
    except Exception as exc:
        queue.fail(job_id,owner,type(exc).__name__);raise

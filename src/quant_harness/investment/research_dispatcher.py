"""Bounded research-only work on the existing canonical operations schedule.

No broker, strategy mutation, model subprocess or ledger-write API is imported.
All entry requests remain subject to the existing exploratory Paper registrar.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib
from .research import digest
from .review_jobs import Queue
from .exploration import research_store,official_sessions,provider_call,quote_events,reserve
from .discovery import instant,now
from .financial_packet import verify_fact
from quant_harness.alpha_research_factory import register_review_proposal,reserve_review_experiment,record_review_experiment


def worker_hash():
    return digest({name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('research_dispatcher.py','financial_packet.py')})


def evaluate_numeric_bundle(root,bundle):
    checked=0;failures=[]
    for case in bundle['cases']:
        for fact in case.get('facts',[]):
            source=(Path(root)/fact['source_path']).resolve()
            if not source.is_relative_to(Path(root).resolve()/'runtime'):raise ValueError('numeric source outside research evidence')
            try:verify_fact(fact,source.read_bytes(),bundle['asof']);checked+=1
            except ValueError as exc:failures.append({'symbol':case['symbol'],'reason':str(exc)})
    return {'status':'INSUFFICIENT_EVIDENCE','cases':len(bundle['cases']),'verified_numeric_facts':checked,'failures':failures,
            'reason':'Numeric provenance diagnostic; fewer than12 independent company cases, no efficacy or promotion claim',
            'input_hash':digest(bundle),'worker_hash':worker_hash()}


def factory_work(root,proposal,bundle,*,directory=None):
    """Official reservation precedes actual deterministic evaluation. No fallback registry."""
    if proposal['worker_hash']!=worker_hash() or proposal['input_hash']!=digest(bundle):raise ValueError('frozen worker or input changed')
    try:
        attempt=register_review_proposal(root,proposal,directory=directory)
        reserve_review_experiment(root,attempt,directory=directory)
    except ValueError as exc:return {'status':'BLOCKED','reason':str(exc),'experiment_executed':False}
    if proposal['worker_hash']!=worker_hash() or proposal['input_hash']!=digest(bundle):raise ValueError('frozen worker or input changed')
    out=Path(directory) if directory else Path(root)/'runtime/alpha_research_factory/task4'
    log=out/'diagnostic_registry.jsonl'
    if log.exists():
        for line in log.read_text().splitlines():
            prior=json.loads(line)
            if prior['attempt_id']==attempt['attempt_id']:return {'status':prior['result']['status'],'experiment_executed':False,'cached_result':True,'attempt_id':attempt['attempt_id'],'record':prior}
    result=evaluate_numeric_bundle(root,bundle)
    record=record_review_experiment(root,attempt,result,directory=directory)
    return {'status':result['status'],'experiment_executed':True,'attempt_id':attempt['attempt_id'],'record':record}


def classify_observation(decision,events):
    """A price move is an observation, not proof of earnings/valuation failure."""
    for event in events.values():
        if instant(event['event_at'])<=instant(decision['sealed_at']):raise ValueError('preseal mark is not Forward evidence')
    return {'status':'PENDING_FINANCIAL_AND_HORIZON_LABELS','cause':'UNDETERMINED','new_price_events':events,
            'future_returns_mature':False,'investment_error_inferred_from_price':False,
            'followup':'Observe thesis conditions and source-linked realized financials; do not replace initial forecast'}


def poll_filings(root,store,cfg,decision,clock,client=None):
    if decision['market']!='KR':return {'status':'US_REALIZED_FINANCIAL_FEED_NOT_CONNECTED'}
    from zoneinfo import ZoneInfo
    if client is None:
        from quant_harness.v72_integration_ready.opendart import OpenDartClient
        client=OpenDartClient()
    cutoff=instant(decision['sealed_at']).astimezone(ZoneInfo('Asia/Seoul')).date().isoformat();end=instant(clock).astimezone(ZoneInfo('Asia/Seoul')).date().isoformat();results=[]
    for symbol,corp in decision.get('issuer_codes',{}).items():
        reserve(store,'TASK92_DART_'+symbol,cfg['daily_provider_calls'],1)
        raw=client._request('list.json',{'corp_code':corp,'bgn_de':cutoff.replace('-',''),'end_de':end.replace('-',''),'pblntf_ty':'A','page_count':20,'last_reprt_at':'N'})
        fingerprint=digest(raw);folder=Path(root)/'runtime/task9_2/forward_raw';folder.mkdir(parents=True,exist_ok=True);path=folder/(fingerprint+'.json')
        if not path.exists():path.write_text(json.dumps(raw,ensure_ascii=False))
        # Date-only disclosures cannot prove availability after a same-day seal.
        new=[r for r in raw.get('list',[]) if cutoff.replace('-','')<r['rcept_dt']<=end.replace('-','')]
        results.append({'symbol':symbol,'source_hash':fingerprint,'new_filings':new,'observed_at':clock})
    return {'status':'OBSERVED_DART_NOTICES_ONLY','issuers':results,'annual_forecast_realizations':'PENDING_MATCHED_PERIOD_AND_UNIT_ACTUALS'}


def run_tick(root,*,current=None,client=None):
    root=Path(root);registry=root/'runtime/task9_2/dispatch_registry.json'
    if not registry.exists():return {'status':'DISABLED_NO_REGISTERED_RESEARCH'}
    manifest=json.loads(registry.read_text());body={k:v for k,v in manifest.items() if k!='registry_hash'}
    if digest(body)!=manifest['registry_hash']:raise ValueError('research registry integrity')
    store,cfg=research_store(root);queue=Queue(store);clock=current or now();day=instant(clock).astimezone(timezone.utc).date().isoformat();out=[]
    # A separate advisory lock prevents timer/manual overlap. It does not change
    # the existing trading lock, strategies, account state or Factory limits.
    with store.lock():
        proposal=store.get(manifest['proposal_id']);bundle=store.get(manifest['bundle_id'])
        job=queue.enqueue('TASK92_FACTORY_NUMERIC_AUDIT',{'proposal_id':manifest['proposal_id'],'bundle_id':manifest['bundle_id'],'utc_day':day})
        owner='research-dispatch-'+day;claim=queue.claim(owner,120,job)
        if claim:
            try:
                result=factory_work(root,proposal,bundle);result_id=store.put('task92_factory_dispatch_result',result)
                queue.finish(job,owner,result_id,'PENDING_EVIDENCE' if result['status']=='BLOCKED' else 'DONE');out.append({'job':job,**result})
            except Exception as exc:queue.fail(job,owner,type(exc).__name__);raise
        for identity in manifest['decision_ids']:
            decision=store.get(identity);market=decision['market'];sessions=official_sessions(market,clock);regular=next((s for s in sessions if instant(s['opening'])<=instant(clock)<instant(s['closing'])),None)
            slot=regular['day'] if regular else day+'-WAIT'
            job=queue.enqueue('TASK92_MONITOR',{'decision_id':identity,'observation_slot':slot});claim=queue.claim(owner,120,job)
            if not claim:continue
            try:
                if not regular:result={'status':'WAIT_NEXT_VERIFIED_REGULAR_SESSION','decision_id':identity,'orders':0,'financial_labels':'PENDING','cause':'UNDETERMINED'}
                else:
                    if client is None:
                        from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
                        client=TossOpenApiClient()
                    names=sorted(set(decision['symbols']));native=[s.split('.')[0] if market=='KR' else s for s in names]
                    raw,receipt=provider_call(root,store,cfg,client,'TASK92_MONITOR_'+market,client.endpoint_map.quote_path,{'symbols':','.join(native)},1)
                    events=quote_events(raw,receipt,market,names,regular,decision['sealed_at'],clock)
                    filings=poll_filings(root,store,cfg,decision,clock)
                    result={'decision_id':identity,**classify_observation(decision,events),'filings':filings,'orders':0,'entry_status':'NO_NEW_REGISTRAR_AUTHORITY_FROM_MONITOR','benchmark_status':'PENDING_SEPARATE_NONTRADABLE_INDEX_ADAPTER'}
                    request=store.put('task92_followup_request',{'decision_id':identity,'evidence_hash':digest(events),'category':'UNDETERMINED','requests':['Compare new facts with sealed forecast/valuation','Resolve source gaps before changing eligibility'],'automatic_strategy_change':False})
                    queue.enqueue('TASK92_EVIDENCE_REVIEW',{'request_id':request})
                rid=store.put('task92_monitor_result',result);queue.finish(job,owner,rid,'PENDING_LABELS');out.append({'job':job,**result})
            except Exception as exc:queue.fail(job,owner,type(exc).__name__);out.append({'job':job,'status':'FAILED_CLOSED','error_type':type(exc).__name__})
        # Only the registered typed evidence-review kind is dispatched. Unknown
        # legacy job kinds are left untouched, never interpreted as executable code.
        import psycopg
        from .review import process_review,policy
        with psycopg.connect(store.url) as conn:
            jobs=conn.execute("SELECT job_id FROM review_job WHERE kind='TASK92_EVIDENCE_REVIEW' AND status IN ('READY','RETRY') ORDER BY updated_at LIMIT4".replace('LIMIT4','LIMIT 4')).fetchall()
        for (job,) in jobs:
            claim=queue.claim(owner,120,job)
            if not claim:continue
            try:
                request=store.get(claim['payload']['request_id'])
                decision=store.get(request['decision_id'])
                review=process_review(decision['process_packet'],policy(root))
                result={'decision_id':request['decision_id'],'process':review,'cause':request.get('category','UNDETERMINED'),'evidence_hash':request['evidence_hash'],'causal_return_effect':'UNDETERMINED','new_version_requires_separate_budget':True}
                rid=store.put('task92_evidence_review',result);queue.finish(job,owner,rid,'DONE');out.append({'job':job,'status':'EVIDENCE_REVIEW_DONE','result_id':rid})
            except Exception as exc:queue.fail(job,owner,type(exc).__name__);out.append({'job':job,'status':'REVIEW_FAILED_CLOSED','error_type':type(exc).__name__})
    return {'status':'DISPATCHED_RESEARCH_ONLY','results':out,'broker_mutations':0,'LLM_calls':0}

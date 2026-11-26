"""Independent, outcome-blind process review and maturity-gated scoring.

No collector, execution or promotion functions are called by this module.
"""
from pathlib import Path
from datetime import datetime,timezone
import json
import math
import hashlib
import psycopg
from psycopg.rows import dict_row
from .research import digest
from .discovery import instant,now
from .store import require_database

TAXONOMY={'INFORMATION_MISSING','FORECAST_ERROR','SELECTION','TIMING','SIZING','EXECUTION','STOCHASTIC_LOSS','UNDETERMINED'}


def policy(root):
    return json.loads((Path(root)/'config/task4_review_contract.json').read_text())


def process_worker_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class Source:
    """Task3 is read-only, including DDL. Only coordinator holds this object."""
    def __init__(self,url):
        self.url=require_database(url)

    def connect(self):
        return psycopg.connect(self.url,options='-c default_transaction_read_only=on',row_factory=dict_row)

    def record(self,identity,kind=None):
        with self.connect() as conn:
            row=conn.execute('SELECT kind,payload,payload_hash FROM investment_record WHERE record_id=%s',(identity,)).fetchone()
        if not row or (kind is not None and row['kind']!=kind) or digest(row['payload'])!=row['payload_hash']:
            raise ValueError('source identity/kind/hash mismatch')
        return row['payload']

    def decisions(self):
        with self.connect() as conn:
            return [r['record_id'] for r in conn.execute("SELECT record_id FROM investment_record WHERE kind='stock_decision' ORDER BY created_at,record_id")]

    def process_packet(self,root,identity):
        """Whitelist construction: never reads fill, NAV, outcome or later prices."""
        decision=self.record(identity,'stock_decision')
        cutoff=decision['sealed_at'];instant(cutoff)
        packet={'source_decision_id':identity,'cutoff':cutoff,'market':decision['market'],
            'strategy_id':decision['strategy_id'],'currency':decision['currency'],
            'contract_hash':decision.get('contract_hash'),'input_hash':decision.get('input_hash'),
            'algorithm_hash':decision.get('algorithm_hash'),'eligible':decision['eligible'],
            'weights':decision['weights'],'prior_marks':decision.get('prior_marks',{}),
            'intents':decision['intents'],'analysis':{k:decision['analysis'].get(k) for k in ('status','reason','missing','as_of','strategy_id')},
            'evidence':[],'source_receipts':[],'company_candidates':[],'numeric_forecasts':[],
            'counterfactuals':[],'information_scope':'AT_DECISION_ONLY_NO_OUTCOME_ACCESS'}
        if packet['analysis'].get('as_of') and instant(packet['analysis']['as_of'])>instant(cutoff):
            raise ValueError('analysis occurred after decision cutoff')
        with self.connect() as conn:
            row=conn.execute('SELECT payload,payload_hash FROM investment_record WHERE record_id=%s',(identity+':lineage',)).fetchone()
        if row:
            if digest(row['payload'])!=row['payload_hash']:raise ValueError('lineage integrity')
            lineage=row['payload']
            evidence=self.record(lineage['evidence_id'],'stock_evidence_collection')
            if instant(evidence['observed_at'])>instant(cutoff):raise ValueError('evidence receipt after cutoff')
            packet['source_receipts']=[{k:r.get(k) for k in ('provider','status','reason')} for r in evidence.get('receipts',[])]
            for item in evidence['records']:
                if instant(item['available_at'])>instant(cutoff):raise ValueError('future evidence in sealed lineage')
                packet['evidence'].append({k:item.get(k) for k in ('evidence_id','source_class','title','url','available_at','published_at','source_hash','entity_mapping','capital_authority')})
            company=self.record(lineage['company_id'],'stock_company_analysis')
            if company.get('as_of') and instant(company['as_of'])>instant(cutoff):raise ValueError('future company analysis')
            packet['company_candidates']=company.get('candidates',[])
            packet['model_trace']={k:company.get(k) for k in ('model','prompt_hash','instruction_version','skills','input_hash','status','reason')}
        registered=json.loads((Path(root)/'config/task3_equity_contract.json').read_text())
        packet['registered_policy']=registered if digest(registered)==decision.get('contract_hash') else None
        return packet

    def current_outcome_availability(self,identity):
        """Evaluator-only inventory. A same-event NAV is not a mature horizon."""
        with self.connect() as conn:
            fills=[dict(r) for r in conn.execute('SELECT symbol,side,quantity,price,fee,event_hash,created_at FROM stock_fill WHERE decision_id=%s ORDER BY created_at',(identity,))]
            nav=conn.execute('SELECT * FROM stock_nav WHERE decision_id=%s',(identity,)).fetchone()
        return {'fills':json.loads(json.dumps(fills,default=str)),'nav':json.loads(json.dumps(dict(nav),default=str)) if nav else None,
                'status':'PENDING','reason':'OFFICIAL_SESSION_HORIZON_AND_MARK_LABELS_NOT_AVAILABLE'}


def process_review(packet,contract):
    """Deterministic evidence audit, with uncertainty rather than hindsight labels."""
    forbidden={'nav','nav_krw','actual_return','realized_return','outcome_labels','holdout_results','pnl','filled_at','fill_price'}
    def guard(value):
        if isinstance(value,dict):
            if forbidden.intersection(value):raise ValueError('outcome fields forbidden in process review')
            for child in value.values():guard(child)
        elif isinstance(value,list):
            for child in value:guard(child)
    guard(packet)
    findings=[]
    def issue(code,tag,evidence,confidence,impact):
        findings.append({'issue':code,'category':tag,'evidence':evidence,'confidence':confidence,'impact_on_return':'UNDETERMINED','interpretation':impact})
    for key in contract['required_trace_fields']:
        if not packet.get(key):issue('PROVENANCE_GAP','UNDETERMINED',[key],1.0,'Missing reproducibility field; this does not prove a bad investment.')
    registered=packet.get('registered_policy')
    if registered is None:
        issue('POLICY_NOT_RECONSTRUCTABLE','UNDETERMINED',['contract_hash'],1.0,'No matching frozen policy; do not assume current parameters were used.')
    else:
        weights=packet['weights']
        if any(not isinstance(w,(int,float)) or not math.isfinite(w) or w<0 for w in weights.values()) or sum(weights.values())>registered['gross_cap']+1e-12 or any(w>registered['single_name_cap']+1e-12 for w in weights.values()):
            issue('RISK_POLICY_VIOLATION','SIZING',['weights','registered_policy'],1.0,'Sealed targets exceed the registered constraint.')
    if not packet['eligible'] and packet['intents']:
        issue('INELIGIBLE_INTENT','EXECUTION',['eligible','intents'],1.0,'An ineligible decision contains orders; actual execution has not been inspected.')
    if packet['analysis'].get('missing') and packet['intents']:
        issue('REQUIRED_INPUT_MISSING','INFORMATION_MISSING',['analysis.missing','intents'],1.0,'Incomplete required inputs should block new orders.')
    if any(str(r.get('status','')).startswith(('FAILED','MISSING')) for r in packet.get('source_receipts',[])):
        issue('UNVERIFIED_SOURCE','INFORMATION_MISSING',['source_receipts'],1.0,'A source was unavailable; source research is warranted, but no investment error is inferred.')
    evidence_ids={e['evidence_id'] for e in packet['evidence']}
    for candidate in packet['company_candidates']:
        if not set(candidate.get('evidence_ids',[]))<=evidence_ids:
            issue('CITATION_NOT_RECONSTRUCTABLE','INFORMATION_MISSING',['company_candidates'],0.8,'Candidate citation cannot be traced within the decision snapshot.')
    return {'schema_version':'TASK4_PROCESS_REVIEW_V1','decision_id':packet['source_decision_id'],'packet_hash':digest(packet),
            'policy_hash':digest(contract),'worker_version':contract['review_worker_version'],'worker_hash':process_worker_hash(),'findings':findings,
            'classification':'RESEARCH_NEEDED' if findings else 'NO_CHANGE',
            'coverage':{'future_returns_seen':False,'trade_execution_evaluated':False,'information_omission_against_complete_oracle':False,
                        'causal_thesis_accuracy':'UNVERIFIED','timing_optimality':'NOT_ASSUMED'},
            'uncertainty':'No single PnL or hindsight-best action is used to infer a cause.',
            'loss_classification':'PENDING_OUTCOME','capital_authority':'NONE'}


def score_mature_outcome(process,packet,contract,labels=None):
    """Labels must carry verified trading sessions, explicit availability and provenance.

    Evaluation outputs never enter the process-review input or proposal context.
    """
    if process['packet_hash']!=digest(packet) or process['decision_id']!=packet['source_decision_id'] or process['policy_hash']!=digest(contract):
        raise ValueError('sealed process/packet/policy mismatch')
    if labels is not None and labels.get('decision_id')!=packet['source_decision_id']:
        raise ValueError('outcome decision identity mismatch')
    horizons=contract['strategy_horizons'].get(packet['strategy_id'])
    if not horizons:return {'status':'PENDING','reason':'PENDING_CONTRACT_REQUIRED'}
    if labels is None:return {'status':'PENDING','horizons':{str(h):'PENDING' for h in horizons},'reason':'NO_MATURE_SESSION_LABELS','process_hash':digest(process)}
    if not labels.get('calendar_verified') or not labels.get('source_hash'):
        raise ValueError('verified session calendar and label provenance required')
    if instant(labels['available_at'])>instant(now()):raise ValueError('future label availability')
    sessions=labels['sessions']
    if sessions!=sorted(set(sessions)) or labels['entry_session'] not in sessions:raise ValueError('invalid session labels')
    from zoneinfo import ZoneInfo
    zone=ZoneInfo('America/New_York' if packet['market']=='US' else 'Asia/Seoul')
    start=sessions.index(labels['entry_session']);results={}
    for horizon in horizons:
        if start+horizon>=len(sessions):results[str(horizon)]={'status':'PENDING'};continue
        days=sessions[start:start+horizon+1]
        if days[-1]>instant(labels['available_at']).astimezone(zone).date().isoformat():
            results[str(horizon)]={'status':'PENDING'};continue
        paths=labels.get('nav',{})
        if any(day not in paths for day in days):results[str(horizon)]={'status':'INSUFFICIENT_EVIDENCE','reason':'MISSING_NAV_MARKS'};continue
        values=[float(paths[d]) for d in days]
        if any(not math.isfinite(v) or v<=0 for v in values):raise ValueError('invalid outcome NAV')
        # Real labels need observed timestamps for every marked session. Merely
        # naming a future session never makes its result mature.
        observed=labels.get('observed_at_by_session',{})
        if any(d not in observed or instant(observed[d])>instant(labels['available_at']) or instant(observed[d])<instant(packet['cutoff']) or instant(observed[d]).astimezone(zone).date().isoformat()<d for d in days):
            raise ValueError('missing/future outcome mark receipt')
        peak=values[0];mdd=0
        for value in values:peak=max(peak,value);mdd=min(mdd,value/peak-1)
        total=values[-1]/values[0]-1
        daily=[values[i]/values[i-1]-1 for i in range(1,len(values))]
        average=sum(daily)/len(daily)
        variance=sum((x-average)**2 for x in daily)/len(daily)
        risk={'annualized_sharpe':average/math.sqrt(variance)*math.sqrt(252) if len(daily)>1 and variance>0 else None,
              'observations':len(daily),'risk_free_assumption':0,'small_sample_not_efficacy':True}
        benchmark=labels.get('benchmark',{});sector=labels.get('sector',{})
        def relative(path):
            if days[0] not in path or days[-1] not in path:return None
            a,b=float(path[days[0]]),float(path[days[-1]])
            if not math.isfinite(a+b) or min(a,b)<=0:raise ValueError('invalid benchmark marks')
            return total-(b/a-1)
        classification='UNDETERMINED';confidence=0.0
        if total<0 and not process['findings']:
            classification='STOCHASTIC_LOSS';confidence=0.3
        result={'status':'MATURED','return':total,'mdd':mdd,'excess_market':relative(benchmark),'excess_sector':relative(sector),
                'classification':classification,'confidence':confidence,'causality_proven':False,
                'normal_loss_note':'Consistent with stochastic loss; one result cannot establish cause.',
                'cost':labels.get('cost'),'slippage':labels.get('slippage'),'execution_delay':labels.get('execution_delay'),
                'risk_adjusted_metric':risk,
                'forecast_scores':[],'counterfactual_scores':[]}
        for forecast in packet.get('numeric_forecasts',[]):
            actual=labels.get('forecast_actuals',{}).get(forecast['forecast_id'])
            if actual is None:continue
            if forecast['horizon_end']>days[-1]:continue
            score={'forecast_id':forecast['forecast_id']}
            if not math.isfinite(float(actual)):raise ValueError('nonfinite forecast label')
            if 'point' in forecast:
                if not math.isfinite(float(forecast['point'])):raise ValueError('nonfinite registered prediction')
                score['absolute_error']=abs(float(actual)-float(forecast['point']))
            if 'probability' in forecast:
                probability=float(forecast['probability'])
                if not 0<=probability<=1 or actual not in (True,False,0,1):raise ValueError('invalid binary forecast')
                score['brier']=(probability-float(bool(actual)))**2
            result['forecast_scores'].append(score)
        # Counterfactual IDs must pre-exist the frozen process packet.
        for action in packet.get('counterfactuals',[]):
            measured=labels.get('counterfactuals',{}).get(action['id'])
            if measured is not None:result['counterfactual_scores'].append({'id':action['id'],'measurement':measured})
        results[str(horizon)]=result
    return {'status':'MATURED' if any(isinstance(r,dict) and r.get('status')=='MATURED' for r in results.values()) else 'PENDING',
            'horizons':results,'process_hash':digest(process),'source_hash':labels['source_hash'],'evidence_class':labels.get('evidence_class','UNVERIFIED')}


def proposal_context(process):
    """The generator receives process findings only, never final metric outputs."""
    return {'decision_id':process['decision_id'],'process_hash':digest(process),'findings':process['findings'],
            'coverage':process['coverage'],'authority':'PROPOSAL_ONLY_NO_FINAL_HOLDOUT'}

"""Post-seal execution arithmetic, isolated from the blind process review."""
import math
from .discovery import instant


def audit_execution(source,decision_id):
    inventory=source.current_outcome_availability(decision_id)
    rows=[];fee_total=0.0;slippage_total=0.0
    for fill in inventory['fills']:
        bundle=source.record(fill['event_hash'],'stock_quote_events')
        if bundle['decision_id']!=decision_id:raise ValueError('fill/event decision mismatch')
        event=next((e for e in bundle['events'] if e['symbol']==fill['symbol']),None)
        if event is None:raise ValueError('fill reference quote missing')
        quantity,price,reference,fee=map(float,(fill['quantity'],fill['price'],event['price'],fill['fee']))
        if any(not math.isfinite(v) for v in (quantity,price,reference,fee)) or min(quantity,price,reference)<=0 or fee<0:
            raise ValueError('invalid execution values')
        direction=1 if fill['side']=='BUY' else -1 if fill['side']=='SELL' else 0
        if not direction:raise ValueError('invalid fill side')
        slippage=(price-reference)*quantity*direction
        fee_total+=fee;slippage_total+=slippage
        delay=(instant(fill['created_at'])-instant(event['event_at'])).total_seconds()
        if delay<0:raise ValueError('fill preceded quote')
        rows.append({'symbol':fill['symbol'],'side':fill['side'],'quantity':quantity,'fee':fee,
                     'slippage_cost':slippage,'quote_to_commit_seconds':delay,'event_id':fill['event_hash']})
    return {'status':'EXECUTION_OBSERVED' if rows else 'NO_EXECUTION','decision_id':decision_id,
            'fills':rows,'fee_total':fee_total,'slippage_total':slippage_total,'total_execution_cost':fee_total+slippage_total,
            'model':'TASK3_SYNTHETIC_PAPER_FILL_CONTRACT','investment_error_inferred':False,
            'holding_period_performance':'PENDING','note':'Execution arithmetic is known; alpha and optimal timing are not inferred.'}

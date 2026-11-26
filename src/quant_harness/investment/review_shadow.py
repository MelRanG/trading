"""Optional Hermes-compatible Shadow protocol; project DB remains authoritative."""
from .research import digest


def packet_for_shadow(process):
    from .review import proposal_context
    context=proposal_context(process)
    return {'protocol':'TASK4_HERMES_SHADOW_V1','task':'recall unresolved evidence and next observation',
            'context':context,'input_hash':digest(context),'allowed_reference_ids':[process['decision_id']],
            'permissions':{'trade_write':False,'promotion':False,'cron':False,'gateway':False}}


def compare_shadow_reply(packet,reply,execution_receipt=None):
    if reply.get('input_hash')!=packet['input_hash']:raise ValueError('shadow input mismatch')
    if any(reply.get(k) for k in ('orders','strategy_changes','promote','cron')):raise ValueError('shadow authority violation')
    references=reply.get('reference_ids',[])
    if not set(references)<=set(packet['allowed_reference_ids']):raise ValueError('unverified shadow memory reference')
    return {'protocol':packet['protocol'],'status':'SHADOW_ONLY','valid_references':len(set(references)),
            'cost':reply.get('cost'),'external_hermes_executed':bool(execution_receipt and execution_receipt.get('tool')=='Hermes' and execution_receipt.get('exit_code')==0 and execution_receipt.get('input_hash')==packet['input_hash'] and execution_receipt.get('result_hash')==digest(reply)),
            'investment_efficacy':'NOT_EVALUATED','permissions':packet['permissions']}

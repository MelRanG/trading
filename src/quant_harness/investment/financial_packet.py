"""Source-linked numeric facts; no forecasts, valuation or order authority."""
from decimal import Decimal,InvalidOperation
from datetime import date
import hashlib,json,re

def verify_fact(fact,raw,asof):
    required={'metric','raw_value','multiplier','value','unit','currency','basis','period_start','period_end','published','source_hash','locator'}
    if not required<=fact.keys():raise ValueError('incomplete numeric provenance')
    if hashlib.sha256(raw).hexdigest()!=fact['source_hash']:raise ValueError('financial source hash mismatch')
    cutoff=str(asof)[:10]
    if not fact['period_start']<=fact['period_end']<=fact['published']<=cutoff:raise ValueError('future or inconsistent financial period')
    for key in ['period_start','period_end','published']:date.fromisoformat(fact[key])
    if fact['basis'] not in ['CFS','SFS'] or fact['currency'] not in ['USD','KRW']:raise ValueError('unsupported accounting identity')
    if fact['unit'] not in ['CURRENCY','SHARES','PER_SHARE','RATIO']:raise ValueError('unknown financial unit')
    if ('EarningsLossPerShare' in fact['metric'] or 'EarningsPerShare' in fact['metric']) and fact['unit']!='PER_SHARE':raise ValueError('EPS requires per-share unit')
    token=str(fact['raw_value']);loc=fact['locator']
    if loc['kind']=='json':
        obj=json.loads(raw)
        for key in loc['path']:obj=obj[key]
        if str(obj)!=token:raise ValueError('numeric JSON locator mismatch')
    elif loc['kind']=='text':
        text=raw.decode('utf-8');a,b=loc['start'],loc['end']
        if text[a:b]!=loc['quote'] or token not in loc['quote']:raise ValueError('numeric original quote mismatch')
        # Period and unit must be explicit in the source window, not inferred
        # merely because the same number appears elsewhere in a document.
        for anchor in loc['context_anchors']:
            if anchor not in text:raise ValueError('missing period or unit anchor')
        if len(loc['context_anchors'])<2:raise ValueError('period/unit context required')
    else:raise ValueError('unsupported source locator')
    cleaned=token.replace(',','').replace(' ','').replace('\n','').replace('$','')
    if cleaned.startswith('(') and cleaned.endswith(')'):cleaned='-'+cleaned[1:-1]
    try:value=Decimal(cleaned)*Decimal(str(fact['multiplier']));expected=Decimal(str(fact['value']))
    except InvalidOperation as exc:raise ValueError('invalid financial number') from exc
    if not value.is_finite() or value!=expected:raise ValueError('financial normalization mismatch')
    if fact['unit']=='SHARES' and value<=0:raise ValueError('nonpositive share count')
    return {**fact,'verified_numeric_provenance':True}


def research_state(*,numeric_complete,valuation_complete,price_verified,entry_met,attractive,rank=None):
    """Rank never confers investment authority; missing facts != negative edge."""
    if not numeric_complete or not valuation_complete or not price_verified:return 'RESEARCH_INCOMPLETE'
    if not attractive:return 'UNATTRACTIVE'
    return 'INVESTABLE' if entry_met else 'WATCH'


def model_numeric_view(facts):
    """Keep every verified numeric fact; trim narrative elsewhere, never capital fields."""
    if not all(f.get('verified_numeric_provenance') for f in facts):raise ValueError('unverified numeric model input')
    fields=('metric','value','unit','currency','basis','period_start','period_end','published','source_hash')
    return [{k:f[k] for k in fields} for f in facts]


def score_financial_forecast(forecast,actual,raw,asof):
    if actual is None:return {'status':'PENDING','reason':'NO_PUBLISHED_ACTUAL'}
    verified=verify_fact(actual,raw,asof)
    if any(forecast[k]!=verified[k] for k in ('metric','unit','currency','basis','period_end')):raise ValueError('forecast/actual accounting contract mismatch')
    if verified['published']<=forecast['sealed_at'][:10]:raise ValueError('actual not independently after forecast')
    value=float(verified['value']);estimate=float(forecast['value'])
    return {'status':'MATURE','error':estimate-value,'absolute_percentage_error':abs(estimate-value)/abs(value) if value else None,'source_hash':verified['source_hash'],'cause':'UNDETERMINED'}

"""Cross-sleeve risk preview, separate from independent comparison account NAV."""
import math


def aggregate(sleeves, *, gross_cap, single_name_cap, sector_caps, sectors):
    """Capital fractions are fixed before decisions; unused sleeves stay cash."""
    fractions=[s['capital_fraction'] for s in sleeves]
    if any(not math.isfinite(x) or x<0 for x in fractions) or sum(fractions)>1+1e-12:
        raise ValueError('invalid capital allocation')
    targets={}
    for sleeve in sleeves:
        for symbol,weight in sleeve['weights'].items():
            if not math.isfinite(weight) or not 0<=weight<=1 or symbol not in sectors:
                raise ValueError('unverified portfolio target')
            targets[symbol]=targets.get(symbol,0)+weight*sleeve['capital_fraction']
    sector_weights={}
    for symbol,weight in targets.items():
        sector=sectors[symbol]
        sector_weights[sector]=sector_weights.get(sector,0)+weight
    violations=[]
    if sum(targets.values())>gross_cap+1e-12:violations.append('GROSS_EXPOSURE')
    if any(w>single_name_cap+1e-12 for w in targets.values()):violations.append('DUPLICATE_NAME_EXPOSURE')
    if any(k not in sector_caps or w>sector_caps[k]+1e-12 for k,w in sector_weights.items()):violations.append('SECTOR_EXPOSURE')
    return {'status':'HOLD_ONLY' if violations else 'PREVIEW_ONLY','weights':targets,
            'sector_weights':sector_weights,'violations':violations,'execution_authority':'NONE'}

from protocol import *
research_seal();a=json.loads((B/'evaluation_v2/hypothesis_scores.json').read_text());lookup={x['symbol']:x for x in a};cases=[]
for s,minvalue,margin,minmargin,p in [('AIR',3,10.6,9,B/'actuals/AIR_Q4/normalized.txt'),('ETN',2,None,None,B/'evaluation_web_extract_US.json'),('GEV',100,None,None,B/'evaluation_GEV_release.json'),('010120.KS',1.2,233543/1877789*100,6,B/'actuals/010120.KS/20261021800151.txt'),('003230.KS',6000,1962/7918*100,18,B/'actuals/003230.KS/20261106800605.txt'),('281820.KS',900,None,None,B/'actuals/281820.KS/accounts_Q3.json')]:
 market='KR' if s.endswith('.KS') else 'US';x=next(r for r in json.loads((B/'research'/(market+'.json')).read_text())['selected'] if r['symbol']==s);actual=lookup[s]['actual']['value'];t=p.read_text()
 if s=='AIR':assert 'Adjusted operating margin increased to 10.6%' in t
 if s=='010120.KS':assert '233,543' in t and '1,877,789' in t
 if s=='003230.KS':assert '1,962' in t and '7,918' in t
 cases.append({'symbol':s,'sealed_invalidation':x['invalidation'],'minimum_value':minvalue,'actual_value':actual,'margin_percent_if_conditioned':margin,'minimum_margin_percent':minmargin,'numeric_condition_triggered':actual<minvalue or (margin is not None and margin<minmargin),'assessment':'NUMERIC_CONDITION_NOT_TRIGGERED; businessdriverconsistent, fullqualitativerisknotproven','price_cause':'UNDETERMINED; improvedbusiness doesnotproveadequatepurchasevaluation','actual_source_hash':sha(p)})
freeze(B/'evaluation_v2/invalidation.json',cases)

from common import *
import pandas as pd
from datetime import datetime,timedelta
rows=[];forecasts=[];status=[]
for market,sym in [('US','^GSPC'),('KR','^KS11')]:
 days=sorted(d for d in pd.read_csv(B/'evaluator_only'/sym/'bars.csv').date if d>='2026-05-18');decisions=[json.loads(p.read_text()) for p in sorted((B/'decisions'/market).glob('*.json'))];last=None
 for day in days:
  if last is not None and pd.Timestamp(day).isocalendar().week==pd.Timestamp(last).isocalendar().week and day!=days[-1]:continue
  # each weekly checkpoint can only enumerate documents already public.
  packets=[x for x in decisions if x['asof']<=day];parent=packets[-1];facts=[]
  for c in parent['cases']:
   for p in (B/'primary'/c['symbol']).glob('*/receipt.json'):
    r=json.loads(p.read_text());pub=r.get('published','9999');pub=pub[:4]+'-'+pub[4:6]+'-'+pub[6:8] if '-' not in pub else pub
    if (last or '2026-05-15')<pub<day and r.get('status')=='SAVED' and not p.with_name('invalid_document.json').exists():facts.append({'symbol':c['symbol'],'published':pub,'source_hash':r.get('raw_sha256'),'kind':'PRIMARY_FINANCIAL_UPDATE'})
  rows.append({'market':market,'observed_through':day,'parent_research_asof':parent['asof'],'new_dated_evidence_since_previous_check':facts,'no_new_material_evidence_in_bounded_feed':not facts,'not_full_market_news_coverage':True,'decision_policy':'Month/event research acts only after sealed reconsideration; no guessed thesis invalidation'});last=day
 for dec in decisions:
  for c in dec['cases']:
   for f in c.get('forecasts',[]):
    # Annual FY projections are not matched against arbitrary quarterly results.
    forecasts.append({'market':market,'symbol':c['symbol'],'decision_asof':dec['asof'],'forecast':f,'status':'PENDING_MATCHED_FISCAL_YEAR_ACTUAL','reason':'No independently period/unit/basis matched annual actual known by2026-11-13; no price-based forecast score','reused_prior_forecast':dec.get('review_origin')=='DETERMINISTIC_NO_NEW_MODEL_JUDGMENT'})
 status.append({'market':market,'initial_screen_candidates':len(json.loads((B/'screens'/f'{market}.json').read_text())),'deep_researched':len(decisions[0]['cases']),'research_decisions':len(decisions),'model_decisions':sum(d.get('review_origin')!='DETERMINISTIC_NO_NEW_MODEL_JUDGMENT' for d in decisions),'latest_states':[{k:c[k] for k in ['symbol','state','decision_reason','weight']} for c in decisions[-1]['cases']]})
dump(B/'weekly_observations.json',rows);dump(B/'forecast_status.json',forecasts);dump(B/'research_coverage.json',status);print('WEEKLY',len(rows),'FORECAST_VERSIONS',len(forecasts))

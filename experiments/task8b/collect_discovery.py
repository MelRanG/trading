from pathlib import Path
from urllib.parse import urlencode
from datetime import datetime,timezone
import json,sys,re,hashlib
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import fetch,load_environment,us_catalog,kr_catalog
from quant_harness.investment.discovery import recent_media,instant
b=R/'runtime/task8b/discovery';b.mkdir(parents=True,exist_ok=True)
if (b/'pool.json').exists():print('USE_FROZEN_POOL');raise SystemExit(0)
queries={'US':['(earnings OR guidance) (industrial OR power OR utilities) when:7d','(earnings OR turnaround) (healthcare OR pharmaceutical) when:7d','(valuation OR earnings) (consumer OR retail) when:7d','(earnings OR undervalued) (bank OR financial) when:7d'],'KR':['(수주 OR 전력 OR 방산) 실적 when:7d','(금융 OR 은행 OR 보험) 실적 when:7d','(제약 OR 바이오 OR 자동차) 실적 when:7d','(소비 OR 유통 OR 턴어라운드) 실적 when:7d']};rows=[];receipts=[]
for market,qs in queries.items():
 for q in qs:
  try:
   raw,receipt=fetch('https://news.google.com/rss/search?'+urlencode({'q':q,'hl':'en-US' if market=='US' else 'ko','gl':market,'ceid':'US:en' if market=='US' else 'KR:ko'}),b/'rss');items=recent_media(raw,instant(receipt['available_at']),q)[:20]
   rows.extend([{**x,'market':market} for x in items]);receipts.append({**receipt,'query':q,'market':market,'items':len(items)})
  except Exception as exc:receipts.append({'market':market,'query':q,'status':'FAILED','error_type':type(exc).__name__})
# Fresh light catalogs only, not whole-market price history.
load_environment(R);us=us_catalog(b/'us_catalog');kr=kr_catalog(b/'kr_catalog')
(b/'us_catalog.json').write_text(json.dumps(us,ensure_ascii=False));(b/'kr_catalog.json').write_text(json.dumps(kr,ensure_ascii=False))
kr_names=[]
for c in kr['rows']:
 name=c.get('corp_name','')
 if len(name)>=2 and any(name in x['title'] for x in rows if x['market']=='KR'):kr_names.append(c)
result={'observed_at':datetime.now(timezone.utc).isoformat(),'media_leads':rows,'receipts':receipts,'korean_matched_entities':kr_names,'limitations':'Media titles are discovery leads, never verified investment facts. Corp-code match does not independently verify KOSPI/KOSDAQ venue.'};(b/'pool.json').write_text(json.dumps(result,indent=2,ensure_ascii=False));print(json.dumps({'items':len(rows),'kr_entity_matches':len(kr_names),'query_results':[r.get('items') for r in receipts]},indent=2))

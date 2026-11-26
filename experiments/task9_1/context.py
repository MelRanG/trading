from common import *
from quant_harness.investment.equities import fetch
from quant_harness.investment.company_outcomes import Document
plans=[('2024-11-29','US','2024-11-07','https://www.federalreserve.gov/newsevents/pressreleases/monetary20241107a.htm','Recent indicators'),('2025-06-30','US','2025-06-18','https://www.federalreserve.gov/newsevents/pressreleases/monetary20250618a.htm','Although swings'),('2024-11-29','KR','2024-11-28','https://www.bok.or.kr/eng/bbs/E0000627/view.do?menuNo=400022&nttId=10088271','The Monetary Policy Board'),('2025-06-30','KR','2025-05-29','https://www.bok.or.kr/eng/bbs/E0000627/view.do?menuNo=400022&nttId=10091640','The Monetary Policy Board')]
for date,m,pub,u,anchor in plans:
 p=B/'context'/date/(m+'.json')
 if p.exists():continue
 try:
  raw,r=fetch(u,p.parent/'raw');d=Document();d.feed(raw.decode());t='\n'.join(d.text);start=t.find(anchor);assert start>=0;piece=t[start:start+5500];dump(p,{'published':pub,'url':u,'receipt':r,'text':piece,'quality':'DATED_POLICY_STATEMENT_CURRENT_DOWNLOAD'})
 except Exception as e:dump(p,{'published':pub,'url':u,'status':'FAILED','error_type':type(e).__name__})
# Small factual fallback from official PDF served to browser but host HTTP403.
p=B/'deep/2024-11-29/FIX/web_facts.json'
freeze(p,{'published':'2024-10-24','url':'https://investors.comfortsystemsusa.com/node/17331/pdf','source_kind':'OFFICIAL_PDF_WEB_EXTRACT_HOST_FETCH_FAILED','facts':'Q3 2024 revenue USD1.81bn vs USD1.38bn prior year; net income USD146.2m vs USD105.1m; diluted EPS4.09 vs2.93. These are reported quarter figures, not future forecast. Full balance/debt bridge not supplied.','quality':'PARTIAL_WEB_EXTRACT_NOT_LOCAL_ORIGINAL'})

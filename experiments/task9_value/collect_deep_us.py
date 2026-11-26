from pathlib import Path
import sys,json,io,re,hashlib
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));sys.path.insert(0,'/home/ansy/app/quant-diligence/task6-quanta-env/lib/python3.12/site-packages')
from quant_harness.investment.equities import fetch
from quant_harness.investment.company_outcomes import Document
from pypdf import PdfReader
B=R/'runtime/task9_value'
plan=[(2021,'INTC','2021-10-21','https://www.intc.com/news-events/press-releases/detail/1505/intel-reports-third-quarter-2021-financial-results'),(2021,'TRV','2021-10-19','https://s26.q4cdn.com/410417801/files/doc_financials/2021/q3/3Q21-Press-Release-FINAL.pdf'),(2021,'DOW','2021-10-21','https://investors.dow.com/en/news/news-details/2021/Dow-reports-third-quarter-2021-results/default.aspx'),(2022,'INTC','2022-10-27','https://www.intc.com/news-events/press-releases/detail/1586/intel-reports-third-quarter-2022-financial-results'),(2022,'DOW','2022-10-20','https://investors.dow.com/en/news/news-details/2022/Dow-reports-third-quarter-2022-results/default.aspx'),(2022,'AXP','2022-10-21','https://ir.americanexpress.com/files/doc_financials/2022/q3/Q3-2022-Earnings-Press-Release.pdf'),(2023,'CSCO','2023-11-15','https://investor.cisco.com/news/news-details/2023/CISCO-REPORTS-FIRST-QUARTER-EARNINGS/default.aspx'),(2023,'MRK','2023-10-26','https://www.merck.com/news/merck-announces-third-quarter-2023-financial-results/'),(2023,'DOW','2023-10-24','https://investors.dow.com/en/news/news-details/2023/Dow-reports-third-quarter-2023-results/default.aspx')]
(B/'ir_plan.json').write_text(json.dumps(plan,indent=2))
for year,s,date,u in plan:
 folder=B/'deep'/str(year)/s;folder.mkdir(parents=True,exist_ok=True);p=folder/'source_packet.json'
 if p.exists():continue
 try:
  raw,r=fetch(u,folder/'raw')
  if raw.startswith(b'%PDF'):
   (folder/'original.pdf').write_bytes(raw);text='\n'.join(p.extract_text(extraction_mode='layout') or '' for p in PdfReader(io.BytesIO(raw)).pages)
  else:
   (folder/'original.html').write_bytes(raw);d=Document();d.feed(raw.decode());text='\n'.join(d.text)
  (folder/'original.txt').write_text(text)
  # Trim current site header/footer. The article itself is dated; do not send
  # archive navigation or related current articles to the historical worker.
  anchors={'INTC':'News Summary','TRV':'Travelers Reports Third Quarter','DOW':'FINANCIAL HIGHLIGHTS','AXP':'AMERICAN EXPRESS','CSCO':'News Summary','MRK':'Sales Reflect Sustained'}
  a=text.lower().find(anchors[s].lower());a=max(0,a);main=text[a:a+22000]
  if len(main)<2500:raise ValueError('inadequate primary article text')
  parts=[{'label':'article_financial_and_outlook','start':a,'text':main[:12000]}]
  p.write_text(json.dumps({'symbol':s,'market':'US','published':date,'source_id':s+'_'+str(year)+'_OFFICIAL_RELEASE','source_url':u,'excerpts':parts,'quality':'PARTIAL_PIT_OFFICIAL_DATED_ARTICLE','raw_sha256':hashlib.sha256(raw).hexdigest(),'receipt':r},indent=2));print(year,s,'SAVED',len(main),flush=True)
 except Exception as e:(folder/'failure.json').write_text(json.dumps({'url':u,'error_type':type(e).__name__}));print(year,s,type(e).__name__,flush=True)

from common import *
import re,io
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'/home/ansy/app/quant-diligence/task6-quanta-env/lib/python3.12/site-packages')
from pypdf import PdfReader
from quant_harness.investment.equities import fetch
from quant_harness.investment.company_outcomes import Document
plans=[
('US_ETN','US','2026-05-05','https://www.eaton.com/us/en-us/company/news-insights/news-releases/2026/eaton-reports-record-first-quarter-2026-results.html','primary'),
('US_AIR','US','2026-01-06','https://www.aarcorp.com/en/newsroom/press-releases/2026/aar-reports-second-quarter-fiscal-year-2026-results/','primary'),
('US_GEV','US','2026-04-22','https://www.gevernova.com/news/press-releases/ge-vernova-reports-first-quarter-2026-financial-results','primary'),
('US_OTIS','US','2026-04-22','https://d18rn0p25nwr6d.cloudfront.net/CIK-0001781335/94176139-9f0d-413a-aebb-c72e6db59022.pdf','primary'),
('US_IR','US','2026-04-28','https://investors.irco.com/news/news-details/2026/Ingersoll-Rand-Reports-First-Quarter-2026-Results/default.aspx','primary'),
('US_MAIR','US','2026-05-12','https://investors.madisonair.com/2026-05-12-Madison-Air-Reports-First-Quarter-2026-Results?asPDF=1','primary'),
('US_XRAY','US','2026-05-05','https://docs.publicnow.com/viewDoc?filename=44260%5CEXT%5CE2B4678705F36B27B76A99D2CEDBC15AF8EA447A_FB0AFF8856E534BCA1226E8C6122D1B0216F59DD.PDF','issuer_release_mirror'),
('US_PHM','US','2026-04-23','https://s204.q4cdn.com/680895981/files/doc_earnings/2026/q1/earnings-result/Q1-2026-Earnings-Release.pdf','primary'),
('US_TILE','US','2026-05-08','https://investors.interface.com/news/news-details/2026/Interface-Reports-First-Quarter-2026-Results/default.aspx','primary'),
('US_FISV','US','2026-05-05','https://investors.fiserv.com/news-releases/news-release-details/fiserv-reports-first-quarter-2026-results','primary'),
('US_STC','US','2026-04-22','https://www.finansavisen.no/pressemeldinger/2026/04/22/211c842a-6548-525d-b089-6cba2cc79a7a/stewart-reports-first-quarter-2026-results','issuer_release_mirror'),
('US_TMHC','US','2026-04-22','https://www.finansavisen.no/pressemeldinger/2026/04/22/9780dfef-4a3c-520d-b721-794a3127b68a/taylor-morrison-reports-first-quarter-2026-results','issuer_release_mirror'),
('US_WATER','US','2026-04-30','https://www.awwa.org/AWWA-Articles/awwa-state-of-the-water-industry-report-underscores-infrastructure-funding-challenges/','industry'),
('US_FREIGHT','US','2026-01-08','https://www.chrobinson.com/en-us/resources/insights-and-advisories/north-america-freight-insights/jan-2026-freight-market-update/na-truckload/','industry'),
('KR_POWER','KR','2026-04-28','https://www.hankyung.com/article/2026042833721','news'),
('KR_POWER2','KR','2026-04-26','https://www.metroseoul.co.kr/article/20260426500234','news'),
('KR_FOOD','KR','2026-05-14','https://news.nate.com/view/20260514n31174','news'),
('KR_CONSTRUCTION','KR','2026-05-08','https://www.sankun.com/blog/detail/1608_major-listed-construction-companies-q1-2026-earnings','industry'),
('KR_SEMIEQUIP','KR','2026-02-28','https://www.etoday.co.kr/news/view/2560677','news'),
('KR_KCTECH','KR','2026-05-13','https://www.thelec.kr/news/articleView.html?idxno=56550','news'),
('KR_BIO','KR','2026-04-22','https://www.metroseoul.co.kr/article/20260422500442','news'),
('KR_BIOEXPORT','KR','2026-04-10','https://biz.chosun.com/science-chosun/bio/2026/04/10/ZKVUPULPRFEK5AWVZUFNXW2CXE/','news')]
freeze(B/'source_plan_initial.json',plans)
def run(row):
 ident,m,pub,url,kind=row;f=B/'sources'/ident;f.mkdir(parents=True,exist_ok=True)
 if (f/'receipt.json').exists():return
 try:
  raw,r=fetch(url,f/'raw');(f/'original.bin').write_bytes(raw)
  if raw.startswith(b'%PDF'):t='\n'.join(x.extract_text(extraction_mode='layout') or '' for x in PdfReader(io.BytesIO(raw)).pages)
  else:d=Document();d.feed(raw.decode('utf-8',errors='replace'));t='\n'.join(d.text)
  (f/'original.txt').write_text(t);n='\n'.join(re.sub(r'[ \t\xa0]+',' ',s).strip() for s in t.splitlines() if s.strip());(f/'normalized.txt').write_text(n)
  assert len(n)>700 and 'Page not Found' not in n[:1000] and 'Access Denied' not in n[:800],'INADEQUATE_TEXT'
  dump(f/'receipt.json',{'id':ident,'market':m,'published_claimed':pub,'kind':kind,'url':url,'status':'DOWNLOADED_NEEDS_ARTICLE_PUBLICATION_REVIEW','raw_sha256':sha(f/'original.bin'),'text_sha256':sha(f/'normalized.txt'),'receipt':r});print(ident,len(n),'DOWNLOADED',flush=True)
 except Exception as e:dump(f/'receipt.json',{'id':ident,'market':m,'published_claimed':pub,'kind':kind,'url':url,'status':'FAILED','error_type':type(e).__name__});print(ident,'FAILED',type(e).__name__,flush=True)
with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run,plans))

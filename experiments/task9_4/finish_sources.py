from common import *
from collect_sources import run
from concurrent.futures import ThreadPoolExecutor
plans=[
('KR_ETF_POWER','KR','2026-04-27','https://www.samsungfund.com/upload/kodex/newsroom/20260427141121713.pdf','dated_issuer_ETF'),
('KR_ETF_WEEK','KR','2026-04-20','https://bbn.kiwoom.com/rfTP743','dated_broker_ETF'),
('US_ETF_SECTORS','US','2026-02-28','https://www.ishares.com/us/literature/presentation/ishares-sector-and-industry-etfs.pdf','issuer_ETF_date_needs_check'),
('US_MHK','US','2026-04-30','https://ir.mohawkind.com/news-releases/news-release-details/mohawk-industries-reports-q1-2026-results','primary')]
freeze(B/'source_plan_final.json',plans)
with ThreadPoolExecutor(max_workers=3) as p:list(p.map(run,plans))

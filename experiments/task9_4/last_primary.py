from common import *
from collect_sources import run
from concurrent.futures import ThreadPoolExecutor
plans=[('US_AIR_Q3','US','2026-03-24','https://www.aarcorp.com/globalassets/investors/earnings/fy-2026-q3-results/aar-reports-third-quarter-fiscal-year-2026-results.pdf','primary'),('KR_SAMBIO_Q1','KR','2026-04-23','https://bbn.kiwoom.com/rfSN3705','dated_broker_with_consensus'),('KR_ETF_CONSTRUCTION','KR','2026-04-13','https://bbn.kiwoom.com/rfTP741','dated_broker_ETF')]
freeze(B/'source_plan_last.json',plans)
with ThreadPoolExecutor(max_workers=3) as p:list(p.map(run,plans))

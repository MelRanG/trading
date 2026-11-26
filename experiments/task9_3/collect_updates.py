from common import *
from collect_primary import us
from concurrent.futures import ThreadPoolExecutor
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);c=OpenDartClient();W=Path('/home/ansy/app/quant-diligence/task9-3-work')
plans=[('MOH','2026-04-22','https://investors.molinahealthcare.com/news-releases/news-release-details/molina-healthcare-reports-first-quarter-2026-financial-results'),('MOH','2026-07-22','https://investors.molinahealthcare.com/news-releases/news-release-details/molina-healthcare-reports-second-quarter-2026-financial-results'),('MOH','2026-10-21','https://investors.molinahealthcare.com/news-releases/news-release-details/molina-healthcare-reports-third-quarter-2026-financial-results'),('VRT','2026-07-29','https://investors.vertiv.com/news/news-details/2026/Vertiv-Reports-Strong-Second-Quarter-2026-with-Diluted-EPS-Growth-of-53-Adjusted-Diluted-EPS-Growth-of-60-Raises-Full-Year-2026-Guidance-Across-All-Key-Metrics/default.aspx'),('VRT','2026-10-28','https://investors.vertiv.com/news/news-details/2026/Vertiv-Reports-Strong-Third-Quarter-2026-with-Net-Sales-Growth-of-61-Organic-Orders-Growth-over-100-and-Diluted-EPS-Growth-of-91-Adjusted-Diluted-EPS-Growth-of-78-Raises-Full-Year-2026-Guidance-Across-All-Key-Metrics/default.aspx'),('SFM','2026-07-29','https://investors.sprouts.com/news/news-details/2026/Sprouts-Farmers-Market-Inc--Reports-Second-Quarter-2026-Results/default.aspx'),('SFM','2026-10-28','https://investors.sprouts.com/news/news-details/2026/Sprouts-Farmers-Market-Inc--Reports-Third-Quarter-2026-Results/default.aspx'),('BAM','2026-08-05','https://bam.brookfield.com/sites/brookfield-bam-v2/files/BAM-IR-Master/Press-Releases/2026/Q2-26-BAM-Press-Release.pdf'),('BAM','2026-11-06','https://bam.brookfield.com/sites/brookfield-bam-v2/files/BAM-IR-Master/Press-Releases/2026/Q3-26-BAM-Press-Release.pdf'),('FLUT','2026-08-05','https://flutter.com/media/g23an0ae/flutter-q2-2026-earnings-release.pdf'),('FLUT','2026-11-04','https://flutter.com/media/tc3jkeh1/flutter-q3-2026-earnings-release.pdf')]
freeze(B/'primary_plan_updates.json',plans)
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(us,plans))
for x in json.loads((W/'discover_KR_v2.json').read_text())['deep']:
 s=x['symbol'];identity=next(z for z in json.loads((B/'discovery/KR.json').read_text()) if z['symbol']==s);f=B/'updates'/s;f.mkdir(parents=True,exist_ok=True)
 for name,ep,query in [('list','list.json',{'bgn_de':'20260515','end_de':'20261113','pblntf_ty':'A','page_count':100,'sort':'date','sort_mth':'asc','last_reprt_at':'N'}),('accounts_H1','fnlttSinglAcntAll.json',{'bsns_year':'2026','reprt_code':'11012','fs_div':'CFS'}),('shares_H1','stockTotqySttus.json',{'bsns_year':'2026','reprt_code':'11012'})]:
  p=f/(name+'.json')
  if not p.exists():dump(p,c._request(ep,{'corp_code':identity['corp_code'],**query}))
 print(s,'H1_UPDATE_SAVED',flush=True)

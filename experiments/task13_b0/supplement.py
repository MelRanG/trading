"""Fixed sample official IR fallback and DART filing lineage, no prices."""
import collect
from pathlib import Path
import json
B=collect.B
collect.request('PEP_2024Q4','https://investor.pepsico.com/docs/pepsico-5v9wci20/media/Files/investors/q4-2024-earnings-release.pdf','OFFICIAL_IR')
collect.request('PEP_2024Q4_announcement','https://www.pepsico.com/en/newsroom/press-releases/2024/pepsico-announces-timing-and-availability-of-fourth-quarter-and-full-year-2024-financial-results','OFFICIAL_IR_SCHEDULE')
for e in json.loads((B/'events.json').read_text()):
 accession=e['filing']['rcept_no'];collect.request('viewer_'+accession,'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+accession,'DART_VIEWER')

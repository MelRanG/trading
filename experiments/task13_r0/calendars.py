"""Reuse bounded collector for observed market-index sessions, no weekday invention."""
import json,collections
from pathlib import Path
from collect import collect
from network import Network,B
n=Network();rows=[]
for m,s in [('US','^GSPC'),('KR','^KS11'),('KR','^KQ11')]:
 try:rows.append(collect({'market':m,'symbol':s,'role':'BENCHMARK_CALENDAR','selection_source':'PROVIDER_INDEX_SESSION_TAPE_NOT_OFFICIAL_FULL_CALENDAR'},n))
 except Exception as e:rows.append({'market':m,'symbol':s,'status':'FAILED','reason':type(e).__name__+':'+str(e)[:100]})
(B/'calendar_result.json').write_text(json.dumps(rows,indent=2)+'\n');print(rows)

from pathlib import Path
from urllib.request import urlopen,Request
import json,hashlib
items={
'investor-harness':'https://raw.githubusercontent.com/joansongjr/investor-harness/491cb380011a6533d56b6913d9c4424a9e4e1bdb/skills/sm-catalyst-sweep/SKILL.md',
'financial-services':'https://raw.githubusercontent.com/anthropics/financial-services/60565064557ca77b12f62aa7877f365d111c129d/plugins/agent-plugins/earnings-reviewer/skills/earnings-preview/SKILL.md',
'equity-research-skill':'https://raw.githubusercontent.com/rollingSirius/equity-research-skill/3d94e64ff53b325d866ea4bff69ad81a5adca8f5/SKILL.md'}
b=Path('runtime/task7/skills');b.mkdir(exist_ok=True);rows=[]
for name,url in items.items():
 try:
  raw=urlopen(Request(url,headers={'User-Agent':'QuantHarnessResearch'}),timeout=20).read(150000);(b/(name+'.md')).write_bytes(raw);rows.append({'name':name,'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'status':'SAVED'})
 except Exception as e:rows.append({'name':name,'url':url,'status':'FAILED','reason':str(e)})
(b/'manifest.json').write_text(json.dumps(rows,indent=2));print(rows)

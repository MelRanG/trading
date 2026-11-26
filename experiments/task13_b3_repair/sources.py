from common import *
from lxml import html
s=Sources();index={}
for name,url in C['official_sources'].items():
 raw,receipt=s.get(name,url);index[name]=receipt
 if raw:
  d=html.fromstring(raw);text=' '.join(' '.join(d.itertext()).split());dump(B/'source_text'/f'{name}.json',{'URL':url,'source_SHA':receipt['source_hash'],'text':text})
 print(name,receipt['status'],flush=True)
dump(B/'source_index.json',index)

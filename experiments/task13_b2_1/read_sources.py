"""Offline original exhibit reader. No B2 parser imports, no network or prices."""
from pathlib import Path
import json,gzip,hashlib,re
from lxml import html
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_b2_1';P=json.loads((B/'plan.json').read_text())
assert hashlib.sha256((B/'plan.json').read_bytes()).hexdigest()==json.loads((B/'plan.sha256.json').read_text())['sha256']
def load(meta):
 p=R/meta['storage_path'];raw=gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes();assert hashlib.sha256(raw).hexdigest()==meta['source_hash'];return raw

def blocks(e):
 raw=load(e['source']);s=raw.decode('utf-8','replace');docs=[]
 if e.get('source_kind')=='EXHIBIT_HTML':docs=[(e.get('exhibit_filename'),s)]
 else:
  for d in re.findall(r'<DOCUMENT>(.*?)</DOCUMENT>',s,re.S|re.I):
   m=re.search(r'<TYPE>([^\n\r<]+)',d);fn=re.search(r'<FILENAME>([^\n\r<]+)',d);body=re.search(r'<TEXT>(.*?)</TEXT>',d,re.S|re.I)
   if m and re.fullmatch(r'EX-99(?:\.1)?',m[1].strip()) and body:docs.append((fn[1].strip() if fn else None,body[1]))
 out=[]
 for name,src in docs:
  tree=html.fromstring(src)
  for node in tree.xpath('//script|//style'):node.drop_tree()
  seen=set()
  for node in tree.xpath('//p|//li|//tr|//h1|//h2|//h3|//h4|//div[not(p) and not(div)]'):
   text=' '.join(' '.join(node.itertext()).split())
   if not text or text in seen:continue
   seen.add(text)
   if len(text)>12000:continue
   out.append({'n':len(out),'tag':node.tag,'file':name,'xpath':tree.getroottree().getpath(node),'text':text})
 return out

def packet(item):
 c=json.loads((R/'runtime/task13_b2/collection'/f"{item['symbol']}.json").read_text());ev=sorted(c.get('parents',[])+c['targets'],key=lambda x:(x['filing']['filingDate'],x['filing']['accessionNumber']));idx=next(i for i,e in enumerate(ev) if e['filing']['accessionNumber']==item['accession']);support=ev[max(0,idx-1):idx];sel=[('CURRENT',ev[idx])]+[('PREVIOUS_COLLECTED',x)for x in support];out={'event_id':item['event_id'],'predeclared_metric_basis':c['company']['metric_basis'],'documents':[]}
 for role,e in sel:
  if e['source']['status']!='SAVED':out['documents'].append({'role':role,'status':e['source']['status']});continue
  bs=blocks(e);wanted=set()
  for i,b in enumerate(bs):
   if re.search(r'outlook|guidance|forecast|fiscal (?:year )?20\d\d|full.year|reaffirms?|updates?.{0,30}(?:sales|revenue)|(?:expect|anticipat|project).{0,80}(?:sales|revenue)|(?:sales|revenue).{0,80}(?:expect|anticipat|project)',b['text'],re.I):
    for j in range(max(0,i-1),min(len(bs),i+7)):wanted.add(j)
  out['documents'].append({'role':role,'accession':e['filing']['accessionNumber'],'filingDate':e['filing']['filingDate'],'source':e['source'],'blocks_total':len(bs),'blocks':[bs[j]for j in sorted(wanted)]})
 return out
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--stage',type=int,default=1);a.add_argument('--show',type=int);args=a.parse_args()
 items=P['stage1']if args.stage==1 else P['conditional_stage2']
 if args.show is not None:items=[items[args.show]]
 for i,x in enumerate(items):
  out=packet(x);p=B/'reading_packets'/f"{x['event_id'].replace(':','_')}.json";p.parent.mkdir(exist_ok=True)
  if p.exists():assert json.loads(p.read_text())==out
  else:p.write_text(json.dumps(out,ensure_ascii=False,indent=2))
  print('\n###',x['event_id'])
  for d in out['documents']:
   print(d['role'],d.get('filingDate'),d.get('accession'))
   for b in d.get('blocks',[]):
    t=b['text']
    if re.search(r'outlook|guidance|forecast|expect|full.year|fiscal|sales|revenue|organic|20(?:22|23|24|25)',t,re.I):print(f"[{b['n']}]",t[:6000])

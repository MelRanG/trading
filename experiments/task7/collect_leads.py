from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.rss_news_shadow import fetch_feed
from quant_harness.investment.discovery import recent_media
cfg=json.loads((Path(__file__).parent/'contract.json').read_text());b=ROOT/'runtime/task7/leads';b.mkdir(parents=True,exist_ok=True);records=[];receipts=[]
for query in cfg['discovery']['rss_queries']:
 try:
  raw,at=fetch_feed(query);h=hashlib.sha256(raw).hexdigest();(b/(h+'.rss')).write_bytes(raw);rows=recent_media(raw,at,query)[:25];records+=rows;receipts.append({'query':query,'observed_at':at.isoformat(),'sha256':h,'items':len(rows),'status':'SAVED'})
 except Exception as e:receipts.append({'query':query,'status':'FAILED','error':str(e)})
(b/'pool.json').write_text(json.dumps({'records':records,'receipts':receipts,'policy':'Unverified discovery leads, not investment facts; bounded cross-industry scan'},indent=2,ensure_ascii=False));print(json.dumps({'leads':len(records),'receipts':receipts},indent=2,ensure_ascii=False))

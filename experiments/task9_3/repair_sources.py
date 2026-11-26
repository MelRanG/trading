from common import *
from quant_harness.investment.company_outcomes import Document
for f in (B/'macro/US/raw').glob('*.receipt.json'):
 r=json.loads(f.read_text());date=r['url'].split('monetary')[1][:8];date=date[:4]+'-'+date[4:6]+'-'+date[6:];old=json.loads((B/'macro/US'/(date+'.json')).read_text())
 if old['status']=='SAVED':continue
 raw=(f.parent/(r['source_hash']+'.raw')).read_bytes();d=Document();d.feed(raw.decode());t='\n'.join(d.text);a=t.index('For release at');b=t.find('Implementation Note',a);text=t[a:b if b>a else a+3500];freeze(B/'macro/US'/(date+'.v2.json'),{'status':'SAVED','published':date,'source_hash':r['source_hash'],'url':r['url'],'receipt':r,'text':text,'repair':'actual policy body starts FOMCapproved, not Recentindicators; reused raw without API'})
for f in (B/'primary').glob('*/*/original.txt'):
 if 'Page not Found' in f.read_text()[:1000]:freeze(f.with_name('invalid_document.json'),{'status':'INVALID_HTTP200_ERROR_PAGE','hash':sha(f),'not_model_evidence':True})
print('SOURCE_REPAIRS_FROM_RAW_ONLY')

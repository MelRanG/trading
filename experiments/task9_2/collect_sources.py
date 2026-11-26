from common import *
import io,re,zipfile
sys.path.insert(0,'/home/ansy/app/quant-diligence/task6-quanta-env/lib/python3.12/site-packages')
from pypdf import PdfReader
from quant_harness.investment.equities import fetch,load_environment
from quant_harness.investment.company_outcomes import Document
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R)
plans=[('SFM_FY24','2025-02-20','https://d18rn0p25nwr6d.cloudfront.net/CIK-0001575515/b0777f9a-39ef-4901-94f3-eeb2011fbfa8.pdf'),('TPR','2026-11-05','https://investors.tapestry.com/static-files/15518901-bfb6-4952-ac1c-6087f19ab19d'),('PH','2026-11-05','https://investors.parker.com/sec-filings/all-sec-filings/content/0000076334-26-000170/exhibit991q1fy27.htm'),('KTG_NEWS','2026-11-05','https://www.ktng.com/media/news/press-release/detail/313572'),('LGINNOTEK_DAILY','2026-11-14','https://ir.gsifn.io/lginnotek/ir_daily.html?koreng=1')]
for name,pub,url in plans:
 f=B/'sources'/name;f.mkdir(parents=True,exist_ok=True)
 if (f/'receipt.json').exists():continue
 try:
  raw,receipt=fetch(url,f/'raw');(f/'original.bin').write_bytes(raw)
  if raw.startswith(b'%PDF'):text='\n'.join(p.extract_text(extraction_mode='layout') or '' for p in PdfReader(io.BytesIO(raw)).pages)
  else:d=Document();d.feed(raw.decode());text='\n'.join(d.text)
  (f/'original.txt').write_text(text);dump(f/'receipt.json',{'status':'SAVED','published':pub,'url':url,'receipt':receipt,'raw_sha256':sha(f/'original.bin'),'text_sha256':sha(f/'original.txt')});print(name,'SAVED',len(text),flush=True)
 except Exception as e:dump(f/'receipt.json',{'status':'FAILED','error_type':type(e).__name__,'url':url});print(name,'FAILED',type(e).__name__,flush=True)
c=OpenDartClient();catalog=json.loads((R/'runtime/task8b/discovery/kr_catalog.json').read_text())['rows']
for symbol in ['033780','003230']:
 item=next(x for x in catalog if x['stock_code']==symbol);f=B/'sources'/symbol;f.mkdir(parents=True,exist_ok=True)
 for name,endpoint,query in [('list','list.json',{'corp_code':item['corp_code'],'bgn_de':'20260801','end_de':'20261114','page_count':100,'sort':'date','sort_mth':'desc','last_reprt_at':'N'}),('accounts','fnlttSinglAcntAll.json',{'corp_code':item['corp_code'],'bsns_year':'2026','reprt_code':'11012','fs_div':'CFS'}),('shares','stockTotqySttus.json',{'corp_code':item['corp_code'],'bsns_year':'2026','reprt_code':'11012'})]:
  p=f/(name+'.json')
  if not p.exists():dump(p,c._request(endpoint,query))
 dump(f/'identity.json',{'symbol':symbol+'.KS','name':item['corp_name'] if 'corp_name' in item else item.get('name'),'corp_code':item['corp_code'],'mapping_only_not_PIT_universe':True})
 print(symbol,'DART_SAVED',flush=True)

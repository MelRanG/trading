"""Read-only company source capture. Never archive a URL containing DART keys."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys,shutil
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment,fetch
from quant_harness.v72_integration_ready.opendart import OpenDartClient
from quant_harness.investment.company_outcomes import Document
load_environment(R);dart=OpenDartClient();b=R/'runtime/task8b/fundamentals';b.mkdir(exist_ok=True)
selected=json.loads((R/'runtime/task8b/discovery/selection.json').read_text())['selected'];catalog=json.loads((R/'runtime/task8b/discovery/kr_catalog.json').read_text())['rows'];cases=[]
urls={
'NVDA':['https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-CEO-Transition/default.aspx','https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Sets-Conference-Call-for-Third-Quarter-Financial-Results/default.aspx'],
'FPS':['https://ir.forgentpower.com/news-events/press-releases/detail/110/forgent-reports-fiscal-first-quarter-2027-results-above-high-end-of-guidance-raises-full-year-outlook-on-strong-commercial-and-operational-execution'],
'HRMY':['https://harmonybiosciences.gcs-web.com/news-releases/news-release-details/harmony-biosciences-reports-q3-financial-results-track-achieve'],
'CFG':['https://investor.citizensbank.com/about-us/newsroom/latest-news/2026/2026-10-16-112016706.aspx'],
'AMKR':['https://ir.amkor.com/news-releases/news-release-details/amkor-technology-reports-financial-results-third-quarter-2026'],
'BE':['https://investor.bloomenergy.com/press-releases/press-release-details/2026/Bloom-Energy-Reports-Third-Quarter-2026-Financial-Results/default.aspx'],
'KDP':['https://investors.keurigdrpepper.com/2026-11-03-Keurig-Dr-Pepper-Reports-Q3-Results-and-Reaffirms-Guidance-for-2026']}
def saved_json(folder,name,endpoint,params):
 p=folder/(name+'.json');m=folder/(name+'.receipt.json')
 if p.exists():return json.loads(p.read_text()),json.loads(m.read_text())
 result=dart._request(endpoint,params);encoded=json.dumps(result,sort_keys=True,ensure_ascii=False).encode();p.write_bytes(encoded);receipt={'provider':'OFFICIAL_OPENDART','endpoint':endpoint,'public_params':params,'source_hash':hashlib.sha256(encoded).hexdigest(),'available_at':datetime.now(timezone.utc).isoformat(),'status':result.get('status')};m.write_text(json.dumps(receipt));return result,receipt
for original in selected:
 folder=b/original['ticker'];folder.mkdir(exist_ok=True);ready=folder/'case.json'
 if ready.exists():cases.append(json.loads(ready.read_text()));continue
 c={**original,'sources':[],'research_status':'RESEARCH_INCOMPLETE'}
 if c['market']=='KR':
  native=c['ticker'].split('.')[0];matches=[x for x in catalog if x['stock_code']==native]
  if len(matches)!=1:c['identity_error']='DART entity ambiguous';ready.write_text(json.dumps(c,ensure_ascii=False));cases.append(c);continue
  corp=matches[0]['corp_code']
  for name,endpoint,params in [('identity','company.json',{'corp_code':corp}),('q2','fnlttSinglAcntAll.json',{'corp_code':corp,'bsns_year':'2026','reprt_code':'11012','fs_div':'CFS'}),('shares','stockTotqySttus.json',{'corp_code':corp,'bsns_year':'2026','reprt_code':'11012'})]:
   try:
    data,receipt=saved_json(folder,name,endpoint,params);c['sources'].append({'source_id':native+'_'+name,'data':data,'receipt':receipt,'source_class':'OFFICIAL_REGULATORY_API'})
    if name=='identity':
     venue={'Y':'KS','K':'KQ'}.get(data.get('corp_cls'))
     if data.get('stock_code')!=native or not venue:raise ValueError('current listed company/venue mismatch')
     c['provisional_ticker']=c['ticker'];c['ticker']=native+'.'+venue;c['listing_verified']=True
   except Exception as exc:c['sources'].append({'source_id':native+'_'+name,'status':'FAILED','error_type':type(exc).__name__})
 else:
  cat=json.loads((R/'runtime/task8b/discovery/us_catalog.json').read_text())['rows'];identity=[x for x in cat if x['symbol']==c['ticker'] and x['common_stock_verified']];c['listing_verified']=len(identity)==1;c['listing_identity']=identity
  if c['ticker'] in ['NVDA','CRWV']:
   old=json.loads((R/'runtime/task7/company/packet.json').read_text());oc=next(x for x in old['cases'] if x['ticker']==c['ticker'])
   for source in oc['sources']:
    if source['status']=='SAVED':c['sources'].append({**source,'reused_frozen_original':True})
  for i,url in enumerate(urls.get(c['ticker'],[])):
   try:
    raw,receipt=fetch(url,folder/'raw',limit=3_000_000);doc=Document();doc.feed(raw.decode('utf-8',errors='replace'));text='\n'.join(doc.text);(folder/('ir'+str(i)+'.txt')).write_text(text);c['sources'].append({'source_id':c['ticker']+'_IR_'+str(i),'url':url,'text':text[:50000],'receipt':receipt,'source_class':'OFFICIAL_COMPANY_RELEASE'})
   except Exception as exc:c['sources'].append({'source_id':c['ticker']+'_IR_'+str(i),'url':url,'status':'FAILED','error_type':type(exc).__name__})
 ready.write_text(json.dumps(c,indent=2,ensure_ascii=False));cases.append(c)
(b/'cases.json').write_text(json.dumps(cases,indent=2,ensure_ascii=False));print(json.dumps([{'ticker':c['ticker'],'listing':c.get('listing_verified'), 'sources':[(s['source_id'],s.get('status',s.get('receipt',{}).get('status','SAVED'))) for s in c['sources']]} for c in cases],indent=2))

from common import *
from quant_harness.investment.equities import fetch
from quant_harness.investment.company_outcomes import Document
plans=[('US',d,'https://www.federalreserve.gov/newsevents/pressreleases/monetary'+d.replace('-','')+'a.htm','Recent indicators') for d in ['2026-04-29','2026-06-17','2026-07-29','2026-09-16','2026-10-28']]+[('KR','2026-04-10','https://www.bok.or.kr/eng/bbs/E0000627/view.do?menuNo=400022&nttId=10097453','The Monetary Policy Board'),('KR','2026-08-27','https://www.bok.or.kr/eng/bbs/E0000627/view.do?menuNo=400022&nttId=11064194','The Monetary Policy Board')]
for m,date,url,anchor in plans:
 p=B/'macro'/m/(date+'.json')
 if p.exists():continue
 try:
  raw,r=fetch(url,p.parent/'raw');d=Document();d.feed(raw.decode());t='\n'.join(d.text);a=t.find(anchor);assert a>=0,'NO_DATED_MAIN_BODY';end=t.find('Voting for',a);text=t[a:end+600 if end>a and m=='US' else a+4500];dump(p,{'status':'SAVED','published':date,'url':url,'source_hash':r['source_hash'],'text':text,'receipt':r});print(m,date,'SAVED',flush=True)
 except Exception as e:dump(p,{'status':'FAILED','published':date,'url':url,'error_type':type(e).__name__});print(m,date,'FAILED',flush=True)

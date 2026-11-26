from pathlib import Path
import sys,json
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import fetch
from quant_harness.investment.company_outcomes import Document
B=R/'runtime/task9_value/macro';B.mkdir(exist_ok=True)
for year,day in [(2021,'20211103'),(2022,'20221102'),(2023,'20231101')]:
 p=B/(str(year)+'.json')
 if p.exists():continue
 u='https://www.federalreserve.gov/newsevents/pressreleases/monetary'+day+'a.htm'
 try:
  raw,r=fetch(u,B/'raw');d=Document();d.feed(raw.decode());t='\n'.join(d.text);i=t.find('For release at');end=t.find('Voting for',i);text=t[i:end if end>i else i+8500];p.write_text(json.dumps({'source_id':'FED_'+day,'url':u,'published':str(year)+'-11-'+day[-2:],'text':text,'receipt':r},indent=2));print(year,len(text))
 except Exception as e:p.write_text(json.dumps({'url':u,'status':'FAILED','error_type':type(e).__name__}))

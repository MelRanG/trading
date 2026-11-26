"""Bounded dated source cohorts. No price/outcome inputs."""
from common import *
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);c=OpenDartClient()
US={
'2024-11-29': [('SMCI','Super Micro','Technology'),('MSTR','MicroStrategy','Technology'),('CVNA','Carvana','Discretionary'),('PR','Permian Resources','Energy'),('FIX','Comfort Systems','Industrials'),('DELL','Dell','Technology'),('CRH','CRH','Materials'),('SN','SharkNinja','Discretionary'),('ALAB','Astera Labs','Technology'),('AS','Amer Sports','Discretionary'),('LOAR','Loar','Industrials'),('MSFT','Microsoft','Technology'),('AAPL','Apple','Technology'),('NVDA','Nvidia','Technology'),('GOOGL','Alphabet','Communication'),('AMZN','Amazon','Discretionary'),('META','Meta','Communication'),('BRK-B','Berkshire Hathaway','Financials'),('LLY','Eli Lilly','Healthcare'),('AVGO','Broadcom','Technology'),('TSLA','Tesla','Discretionary'),('GE','GE Aerospace','Industrials'),('MS','Morgan Stanley','Financials'),('GS','Goldman Sachs','Financials'),('SCHW','Charles Schwab','Financials'),('CL','Colgate Palmolive','Staples'),('COIN','Coinbase','Financials'),('HD','Home Depot','Discretionary'),('ABBV','AbbVie','Healthcare'),('ACN','Accenture','Technology')],
'2025-06-30':[('SMMT','Summit Therapeutics','Healthcare'),('SFM','Sprouts Farmers Market','Staples'),('INSM','Insmed','Healthcare'),('AUR','Aurora Innovation','Industrials'),('PRMB','Primo Brands','Staples'),('BAM','Brookfield Asset Management','Financials'),('FLUT','Flutter','Discretionary'),('ONON','On Holding','Discretionary'),('QSR','Restaurant Brands','Discretionary'),('IOT','Samsara','Technology'),('SAIL','SailPoint','Technology'),('KRMN','Karman Holdings','Industrials'),('AAPL','Apple','Technology'),('MSFT','Microsoft','Technology'),('NVDA','Nvidia','Technology'),('AMZN','Amazon','Discretionary'),('GOOGL','Alphabet','Communication'),('META','Meta','Communication'),('BRK-B','Berkshire Hathaway','Financials'),('TSLA','Tesla','Discretionary'),('AVGO','Broadcom','Technology'),('LLY','Eli Lilly','Healthcare'),('WMT','Walmart','Staples'),('ABBV','AbbVie','Healthcare'),('PG','Procter Gamble','Staples')]}
for date,names in US.items():
 source=B/'discovery'/('r'+date[:4]+'.pdf')
 out=[dict(market='US',symbol=s,name=n,sector=sec,source_pdf_sha256=sha(source),source_published='2024-05-24' if date[:4]=='2024' else '2025-06-13',size_status='DATED_R1000_COHORT_PROXY_NOT_DAILY_CAP',identity_quality='PARTIAL_DATED_NAME_TICKER_MAPPING') for s,n,sec in names]
 freeze(B/'cohorts'/date/'US.json',out)
for date,day in [('2024-11-29','20241114'),('2025-06-30','20250515')]:
 out=[];seen=set()
 for page in range(1,5):
  p=B/'discovery'/('dart_'+day+'_'+str(page)+'.json')
  if p.exists():x=json.loads(p.read_text())
  else:
   x=c._request('list.json',{'bgn_de':day,'end_de':day,'pblntf_ty':'A','page_count':100,'page_no':page,'sort':'date','sort_mth':'asc','last_reprt_at':'N'});dump(p,x)
  for row in x.get('list',[]):
   if row['corp_cls'] not in ['Y'] or not row['stock_code'] or row['stock_code'] in seen:continue
   if any(w in row['corp_name'] for w in ['스팩','리츠','기업인수','투자회사']):continue
   if '분기보고서' not in row['report_nm'] or '[' in row['report_nm']:continue
   seen.add(row['stock_code']);out.append(dict(market='KR',symbol=row['stock_code']+('.KS' if row['corp_cls']=='Y' else '.KQ'),name=row['corp_name'],sector='UNVERIFIED',corp_code=row['corp_code'],accession=row['rcept_no'],source_published=row['rcept_dt'],report=row['report_nm'],source_sha256=sha(p),size_status='UNVERIFIED_PENDING_DATED_SHARES',identity_quality='DATED_DART_LISTED_REPORT_NOT_FULL_LISTING_HISTORY'))
  if len(out)>=20:break
 freeze(B/'cohorts'/date/'KR_mainboard_v2.json',out[:20]);print(date,len(out[:20]),[(r['symbol'],r['name']) for r in out[:20]],flush=True)

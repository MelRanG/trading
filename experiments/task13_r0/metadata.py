"""Current bounded universe metadata, explicitly not historical membership."""
from pathlib import Path
import json,io,re,sys
import pandas as pd
from lxml import html
from network import Network,B
n=Network();result={};errors=[]
for name,product in [('IVV','239726/ishares-core-sp-500-etf'),('IJH','239763/ishares-core-sp-midcap-etf')]:
 try:
  url='https://www.ishares.com/us/products/'+product+'/1467271812596.ajax?fileType=csv&fileName='+name+'_holdings&dataType=fund';raw,r=n.get(url,'universe_metadata');text=raw.decode('utf-8-sig');lines=text.splitlines();i=next(i for i,l in enumerate(lines) if l.startswith('Ticker,') or l.startswith('"Ticker",'));f=pd.read_csv(io.StringIO('\n'.join(lines[i:])));assert {'Ticker','Sector','Asset Class'}.issubset(f.columns);f=f[f['Asset Class'].eq('Equity')];result[name]={'rows':f.fillna('').to_dict('records'),'receipt':r,'authority':'CURRENT_FUND_HOLDINGS_NOT_HISTORICAL_MEMBER_OR_CAP','name':name};print(name,len(f),flush=True)
 except Exception as e:errors.append({'source':name,'error':type(e).__name__+':'+str(e)[:160]});print(name,'FAILED',errors[-1],flush=True)
for market,token in [('KOSPI','stockMkt'),('KOSDAQ','kosdaqMkt')]:
 try:
  url='https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType='+token;raw,r=n.get(url,'universe_metadata');f=pd.read_html(io.BytesIO(raw))[0];assert {'회사명','종목코드','업종','상장일'}.issubset(f.columns);f['종목코드']=f['종목코드'].map(lambda x:str(x).zfill(6));result[market]={'rows':f.fillna('').to_dict('records'),'receipt':r,'authority':'CURRENT_KRX_LISTING_NOT_HISTORICAL_ALL_LISTED','market':market};print(market,len(f),flush=True)
 except Exception as e:errors.append({'source':market,'error':type(e).__name__+':'+str(e)[:160]});print(market,'FAILED',errors[-1],flush=True)
# Existing current Nasdaq directory is reused; a price-history expansion is not a listing refresh.
R=Path(__file__).resolve().parents[2];result['NASDAQ_CACHED']=json.loads((R/'runtime/task6/data/US_catalog.json').read_text())
# At most3pages per board: light current-size screen, no whole-market history.
for m,sosok in [('KOSPI',0),('KOSDAQ',1)]:
 rows=[];receipts=[]
 for page in [1,2,3]:
  try:
   raw,r=n.get(f'https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}','universe_metadata');doc=html.fromstring(raw.decode('euc-kr'));headers=[t.text_content().strip() for t in doc.xpath('//table[contains(@class,"type_2")]/tr/th')]
   if not headers:headers=[t.text_content().strip() for t in doc.xpath('//table[contains(@class,"type_2")]//th')]
   cap_index=headers.index('시가총액')
   for tr in doc.xpath('//table[contains(@class,"type_2")]//tr'):
    links=tr.xpath('.//a[contains(@href,"/item/main.naver?code=")]');td=tr.xpath('./td')
    if not links or len(td)<=cap_index:continue
    code=re.search(r'code=(\d{6})',links[0].get('href')).group(1);cap=float(td[cap_index].text_content().strip().replace(',',''));rows.append({'stock_code':code,'name':links[0].text_content().strip(),'cap_KRW':cap*1e8,'board':m,'source_page':page})
   receipts.append(r)
  except Exception as e:errors.append({'source':m+'_SIZE_'+str(page),'error':type(e).__name__+':'+str(e)[:160]});break
 result[m+'_SIZE']={'rows':rows,'receipts':receipts,'authority':'CURRENT_NAVER_MARKET_CAP_NOT_PIT'};print(m+'_SIZE',len(rows),flush=True)
(B/'universe_metadata.json').write_text(json.dumps({'sources':result,'errors':errors,'historical_membership':'UNVERIFIED_SURVIVOR_RESEARCH'},ensure_ascii=False,indent=2,default=str)+'\n')

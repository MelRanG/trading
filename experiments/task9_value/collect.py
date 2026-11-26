from pathlib import Path
import sys,json,hashlib,time,re
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import fetch,normalize_chart,equity_revision_gate,load_environment
B=R/'runtime/task9_value';(B/'prices').mkdir(exist_ok=True)
us=[('MMM','3M','Industrials'),('AXP','American Express','Financials'),('AMGN','Amgen','Healthcare'),('AAPL','Apple','Technology'),('BA','Boeing','Industrials'),('CAT','Caterpillar','Industrials'),('CVX','Chevron','Energy'),('CSCO','Cisco','Technology'),('KO','Coca-Cola','Staples'),('DIS','Disney','Communication'),('DOW','Dow','Materials'),('GS','Goldman Sachs','Financials'),('HD','Home Depot','Discretionary'),('HON','Honeywell','Industrials'),('IBM','IBM','Technology'),('INTC','Intel','Technology'),('JNJ','Johnson&Johnson','Healthcare'),('JPM','JPMorgan','Financials'),('MCD','McDonalds','Discretionary'),('MRK','Merck','Healthcare'),('MSFT','Microsoft','Technology'),('NKE','Nike','Discretionary'),('PG','Procter&Gamble','Staples'),('CRM','Salesforce','Technology'),('TRV','Travelers','Financials'),('UNH','UnitedHealth','Healthcare'),('VZ','Verizon','Communication'),('V','Visa','Financials'),('WMT','Walmart','Staples'),('WBA','Walgreens','Healthcare')]
kr=[('005930','삼성전자','Technology'),('000660','SK하이닉스','Technology'),('051910','LG화학','Chemicals'),('010950','S-Oil','Energy'),('105560','KB금융','Financials'),('086790','하나금융지주','Financials'),('005380','현대차','Automotive'),('000270','기아','Automotive'),('023530','롯데쇼핑','Retail'),('139480','이마트','Retail'),('035420','NAVER','Communication'),('018260','삼성에스디에스','Technology'),('207940','삼성바이오로직스','Healthcare'),('068270','셀트리온','Healthcare'),('032830','삼성생명','Insurance'),('000810','삼성화재','Insurance'),('005490','POSCO','Materials'),('010130','고려아연','Materials'),('030200','KT','Communication'),('032640','LG유플러스','Communication'),('271560','오리온','Staples'),('097950','CJ제일제당','Staples'),('011170','롯데케미칼','Chemicals'),('012330','현대모비스','Automotive')]
cohort=[{'market':'US','symbol':s,'name':n,'sector':sec,'identity_source':'DOW30_2021_PRIMARY_PUBLISHER','size_status':'LARGE_CAP_DATED_COHORT_PROXY_NOT_DAILY_EXACT'} for s,n,sec in us]+[{'market':'KR','symbol':s+'.KS','name':n,'sector':sec,'identity_source':'HMSEC_20211101_INDUSTRY_TABLE','size_status':'DATED_SOURCE_TABLE_ABOVE_500BN_PROXY_NOT_DAILY_EXACT'} for s,n,sec in kr]
p=B/'cohort.json'
if p.exists():assert json.loads(p.read_text())==cohort
else:p.write_text(json.dumps(cohort,ensure_ascii=False,indent=2))
def get(item):
 s=item['symbol'];folder=B/'prices'/s;folder.mkdir(exist_ok=True);p=folder/'receipt_v3.json'
 if p.exists():return json.loads(p.read_text())
 u='https://query1.finance.yahoo.com/v8/finance/chart/'+s.replace('^','%5E')+'?interval=1d&period1=1609459200&period2=1733875200&events=div%2Csplits'
 try:
  
  if (folder/'chart.json').exists():
   raw=(folder/'chart.json').read_bytes();receipt=next(json.loads(x.read_text()) for x in (folder/'raw').glob('*.receipt.json') if json.loads(x.read_text())['source_hash']==hashlib.sha256(raw).hexdigest())
  else:raw,receipt=fetch(u,folder/'raw');(folder/'chart.json').write_bytes(raw)
  # Keep incomplete bars raw, reject them explicitly per evaluation window.
  x=json.loads(raw);r=x['chart']['result'][0];q=r['indicators']['quote'][0];a=r['indicators'].get('adjclose',[{}])[0].get('adjclose',[]);rows=[]
  import pandas as pd,numpy as np
  for i,t in enumerate(r['timestamp']):
   z={'date':datetime.fromtimestamp(t,timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Seoul' if item['market']=='KR' else 'America/New_York')).date().isoformat(),'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'symbol':s,**{k:q[k][i] for k in ('open','high','low','close','volume')},'adjusted_close':a[i] if i<len(a) else None};rows.append(z)
  f=pd.DataFrame(rows);f.to_csv(folder/'bars.csv',index=False)
  valid=f.dropna(subset=['open','high','low','close','volume']);valid=valid[(valid[['open','high','low','close']]>0).all(axis=1)&(valid.volume>=0)]
  valid=valid[(valid.high>=valid[['open','close','low']].max(axis=1))&(valid.low<=valid[['open','close','high']].min(axis=1))]
  f.loc[~f.index.isin(valid.index)].to_csv(folder/'rejected_bars.csv',index=False)
  valid=valid.assign(value_approx=valid.close*valid.volume)
  nf=valid.rename(columns={'open':'raw_open','high':'raw_high','low':'raw_low','close':'raw_close'})
  gate=equity_revision_gate(nf,s,folder,receipt)
  result={'symbol':s,'market':item['market'],'status':'SAVED','rows':len(f),'explicit_invalid_rows':len(f)-len(valid),'receipt':receipt,'gate':gate,'events':r.get('events',{}),'identity_current_metadata_not_historical':r['meta'].get('longName'),'no_forward':True}
 except Exception as e:result={'symbol':s,'status':'FAILED','error_type':type(e).__name__}
 p.write_text(json.dumps(result,indent=2));print(s,result['status'],result.get('rows'),flush=True);time.sleep(.3);return result
items=cohort+[{'market':'US','symbol':'^GSPC'},{'market':'KR','symbol':'^KS11'}]
with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(get,items))
(B/'collection.json').write_text(json.dumps(results,indent=2))

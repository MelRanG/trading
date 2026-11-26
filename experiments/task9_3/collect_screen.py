from common import *
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from urllib.parse import quote
import pandas as pd,numpy as np
from quant_harness.investment.equities import fetch,equity_revision_gate,load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
from quant_harness.investment.financial_packet import verify_fact
load_environment(R);c=OpenDartClient()
def run(x):
 s=x['symbol'];f=B/'screen_inputs'/s;f.mkdir(parents=True,exist_ok=True)
 if (f/'summary.json').exists():return
 try:
  end=int(datetime.fromisoformat('2026-05-16T00:00:00+00:00').timestamp());start=end-370*86400;p=f/'chart.json'
  if not p.exists():raw,r=fetch('https://query1.finance.yahoo.com/v8/finance/chart/'+quote(s,safe='')+f'?interval=1d&period1={start}&period2={end}&events=div%2Csplits',f/'raw');p.write_bytes(raw);dump(f/'receipt.json',r)
  z=json.loads(p.read_text())['chart']['result'][0];q=z['indicators']['quote'][0];rows=[]
  for i,t in enumerate(z.get('timestamp',[])):
   day=datetime.fromtimestamp(t,timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Seoul' if x['market']=='KR' else 'America/New_York')).date().isoformat()
   assert day<='2026-05-15'
   rows.append({'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'date':day,**{k:q[k][i] for k in ['open','high','low','close','volume']}})
  df=pd.DataFrame(rows).dropna();assert len(df)>=64 and df.date.iloc[-1]=='2026-05-15','INSUFFICIENT_ASOF_PRICES';assert (df[['open','high','low','close']]>0).all().all();df.to_csv(f/'bars.csv',index=False)
  gate=equity_revision_gate(df.assign(value_approx=df.close*df.volume).rename(columns={k:'raw_'+k for k in ['open','high','low','close']}),s,f,json.loads((f/'receipt.json').read_text()))
  result={**x,'status':'ELIGIBLE','asof':'2026-05-15','price':float(df.close.iloc[-1]),'momentum63':float(df.close.iloc[-1]/df.close.iloc[-64]-1),'vol63':float(df.close.pct_change().tail(63).std()*np.sqrt(252)),'adv20':float((df.close*df.volume).tail(20).mean()),'gate':gate,'financial_facts':[]}
  if x['market']=='KR':
   for name,ep in [('accounts','fnlttSinglAcntAll.json'),('shares','stockTotqySttus.json')]:
    a=f/(name+'.json')
    if not a.exists():dump(a,c._request(ep,{'corp_code':x['corp_code'],'bsns_year':'2026','reprt_code':'11013',**({'fs_div':'CFS'} if name=='accounts' else {})}))
   a=f/'accounts.json';api=json.loads(a.read_text());facts=[]
   for i,r in enumerate(api.get('list',[])):
    if r.get('rcept_no','9999')[:8]>'20260514':continue
    if r.get('sj_div') not in ['IS','CIS','BS','CF']:continue
    if not any(k in r.get('account_id','') for k in ['Revenue','OperatingIncome','ProfitLoss','CashAndCash','Borrowing','Debt','CashFlowsFromUsedInOperating','PaymentsToAcquireProperty','PurchaseOfProperty','Depreciation','EarningsLossPerShare','Liabilities','Equity']):continue
    if r.get('thstrm_amount') in [None,'','-']:continue
    stock=r['sj_div']=='BS';pub=r['rcept_no'];pub=pub[:4]+'-'+pub[4:6]+'-'+pub[6:8]
    fact={'metric':r['account_id'],'label':r['account_nm'],'raw_value':r['thstrm_amount'],'value':r['thstrm_amount'].replace(',',''),'multiplier':1,'unit':'PER_SHARE' if 'EarningsLossPerShare' in r['account_id'] else 'CURRENCY','currency':'KRW','basis':'CFS','period_start':'2026-03-31' if stock else '2026-01-01','period_end':'2026-03-31','published':pub,'source_hash':sha(a),'source_path':str(a.relative_to(R)),'locator':{'kind':'json','path':['list',i,'thstrm_amount']}}
    facts.append(verify_fact(fact,a.read_bytes(),'2026-05-15'))
   z=json.loads((f/'shares.json').read_text());shares=0
   for r in z.get('list',[]):
    if r.get('rcept_no','9999')[:8]<='20260514' and r.get('se') in ['보통주','보통주식']:
     shares+=int(r['istc_totqy'].replace(',',''))
   result.update(financial_facts=facts,reported_shares=shares,cap_proxy=shares*result['price'])
   if shares*result['price']<500e9:result['status']='EXCLUDED_SIZE_OR_MISSING_SHARES'
   if not facts:result['status']='EXCLUDED_NO_DATED_NUMERIC_FACTS'
  elif result['adv20']<1e7:result['status']='EXCLUDED_LIQUIDITY'
  dump(f/'summary.json',result);print(s,result['status'],flush=True)
 except Exception as e:dump(f/'summary.json',{**x,'status':'BLOCKED','error_type':type(e).__name__,'reason':str(e)[:120] if isinstance(e,(ValueError,AssertionError)) else None});print(s,'BLOCKED',type(e).__name__,flush=True)
tasks=[x for m in ['US','KR'] for x in json.loads((B/'discovery'/f'{m}.json').read_text())]
with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run,tasks))
for m in ['US','KR']:
 summaries=[json.loads((B/'screen_inputs'/x['symbol']/'summary.json').read_text()) for x in tasks if x['market']==m];freeze(B/'screens'/f'{m}.json',summaries);print(m,'ELIGIBLE',sum(x['status']=='ELIGIBLE' for x in summaries),flush=True)

from common import *
import io,zipfile,re
sys.path.insert(0,str(R/'experiments/task9_historical'))
from original_parser import text_and_identity
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
from quant_harness.investment.operations_data import strict_rows
from quant_harness.investment.financial_packet import verify_fact
load_environment(R);dc=OpenDartClient();tc=TossOpenApiClient();W=Path('/home/ansy/app/quant-diligence/task9-4-work');catalog=json.loads((R/'runtime/task8b/discovery/kr_catalog.json').read_text())['rows'];out=[]
alias={'LS일렉트릭':'엘에스일렉트릭','LS ELECTRIC':'엘에스일렉트릭','케이씨텍':'케이씨텍','동원F&B':'동원F&B'}
for market in ['US','KR']:
 discovery=json.loads((W/('discover_'+market+'.json')).read_text())
 for item in discovery['deep_candidates']:
  name=item['name'];symbol=item.get('symbol');corp=None
  if market=='KR':
   normalized=alias.get(name,name).replace(' ','').upper();matches=[r for r in catalog if r.get('stock_code') and r['corp_name'].replace(' ','').upper()==normalized]
   if not matches and symbol:matches=[r for r in catalog if r.get('stock_code')==str(symbol).split('.')[0].zfill(6)]
   if len(matches)==1:corp=matches[0];symbol=corp['stock_code']+'.KS'
  f=B/'deep_inputs'/market/(symbol or name);f.mkdir(parents=True,exist_ok=True);p=f/'packet.json'
  if p.exists():out.append(json.loads(p.read_text()));continue
  packet={**item,'market':market,'symbol':symbol,'identity':'Dated primary/article issuer plusstable mapping; current DARTcatalog isidentifier only, nothistoricaluniverse','verified_facts':[],'missing':[]}
  if symbol:
   try:
    q=f/'asof_candles.json'
    if not q.exists():dump(q,tc._request('GET',tc.endpoint_map.candles_path,query={'symbol':symbol[:6] if market=='KR' else symbol,'interval':'1d','count':1,'before':'2026-05-16T00:00:00'+('+09:00' if market=='KR' else '-04:00'),'adjusted':'false'}))
    df=strict_rows(json.loads(q.read_text()),symbol,'KRW' if market=='KR' else 'USD','Asia/Seoul' if market=='KR' else 'America/New_York','2026-05-15');assert df.date.max()=='2026-05-15' and len(df)==1,'NO_EXACT_ASOF_PRICE';packet['asof_price']={'date':'2026-05-15','close':float(df.close.iloc[-1]),'currency':'KRW' if market=='KR' else 'USD','source_hash':sha(q),'query_before':'2026-05-16','futurepricesqueried':False}
   except Exception as e:packet['missing'].append({'field':'asof_price','error_type':type(e).__name__})
  if market=='KR' and corp:
   packet['corp_code']=corp['corp_code']
   for label,ep,extra in [('accounts','fnlttSinglAcntAll.json',{'fs_div':'CFS'}),('shares','stockTotqySttus.json',{})]:
    q=f/(label+'.json')
    if not q.exists():dump(q,dc._request(ep,{'corp_code':corp['corp_code'],'bsns_year':'2025','reprt_code':'11011',**extra}))
   q=f/'accounts.json';api=json.loads(q.read_text());accessions=sorted(set(r['rcept_no'] for r in api.get('list',[]) if r.get('rcept_no','9999')[:8]<'20260515'))
   if not accessions:packet['missing'].append({'field':'dated_annual_financials','reason':'API_latest_missing_or_future_amendment_not_used'})
   for i,r in enumerate(api.get('list',[])):
    if r['rcept_no'] not in accessions or r['sj_div'] not in ['BS','IS','CIS','CF']:continue
    metric=r['account_id']
    if not any(t in metric for t in ['Revenue','OperatingIncome','ProfitLoss','CashAndCash','Borrowing','Debt','Liabilities','Equity','CashFlows','Purchase','PaymentsToAcquire','Depreciation','Amortisation','EarningsLossPerShare','Lease']):continue
    raw=r.get('thstrm_amount')
    if raw in [None,'','-']:continue
    pub=r['rcept_no'];pub=pub[:4]+'-'+pub[4:6]+'-'+pub[6:8];fact={'metric':metric,'label':r['account_nm'],'value':raw.replace(',',''),'raw_value':raw,'multiplier':1,'unit':'PER_SHARE' if 'EarningsLossPerShare' in metric else 'CURRENCY','currency':'KRW','basis':'CFS','period_start':'2025-12-31' if r['sj_div']=='BS' else '2025-01-01','period_end':'2025-12-31','published':pub,'source_hash':sha(q),'source_path':str(q.relative_to(R)),'locator':{'kind':'json','path':['list',i,'thstrm_amount']}};packet['verified_facts'].append(verify_fact(fact,q.read_bytes(),'2026-05-15'))
   q=f/'shares.json';z=json.loads(q.read_text())
   for i,r in enumerate(z.get('list',[])):
    if r.get('rcept_no','9999')[:8]>='20260515' or r.get('se') not in ['보통주','보통주식']:continue
    raw=r.get('istc_totqy');pub=r['rcept_no'];pub=pub[:4]+'-'+pub[4:6]+'-'+pub[6:8]
    if raw in [None,'-','']:continue
    fact={'metric':'issued_common_not_current_diluted','value':raw.replace(',',''),'raw_value':raw,'multiplier':1,'unit':'SHARES','currency':'KRW','basis':'SFS','period_start':'2025-12-31','period_end':'2025-12-31','published':pub,'source_hash':sha(q),'source_path':str(q.relative_to(R)),'locator':{'kind':'json','path':['list',i,'istc_totqy']}};packet['verified_facts'].append(verify_fact(fact,q.read_bytes(),'2026-05-15'))
   if len(accessions)==1:
    a=accessions[0];q=f/'original.zip'
    try:
     if not q.exists():q.write_bytes(dc._request('document.xml',{'rcept_no':a},binary=True))
     z=zipfile.ZipFile(io.BytesIO(q.read_bytes()));t='\n'.join(text_and_identity(z.read(n))[0] for n in z.namelist() if n.lower().endswith('.xml'));text=f/'original.txt';text.write_text(t);parts=[]
     for pat,count in [(r'II\. 사업의 내용',2700),(r'주요 제품 및 서비스',1700),(r'매출 및 수주상황',2000)]:
      ms=list(re.finditer(pat,t))
      if ms:parts.append(t[ms[-1].start():ms[-1].start()+count])
     packet['dated_annual_business']={'published':a[:4]+'-'+a[4:6]+'-'+a[6:8],'source_hash':sha(text),'raw_hash':sha(q),'excerpts':parts,'company_identity':corp['corp_name']}
    except Exception as e:packet['missing'].append({'field':'original_annual_business','error_type':type(e).__name__})
  elif market=='KR':packet['missing'].append({'field':'company_identity','reason':'no_unique_code_mapping; keepinsufficient_notlowvalue'})
  freeze(p,packet);out.append(packet);print(market,name,symbol,'FACTS',len(packet['verified_facts']),'asof_price',bool(packet.get('asof_price')),flush=True)
freeze(B/'deep_packets_v2.json',out)

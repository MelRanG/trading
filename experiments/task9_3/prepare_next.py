from common import *
import re,copy,pandas as pd,numpy as np
from quant_harness.investment.financial_packet import verify_fact
m,date=sys.argv[1:];base=json.loads((B/'packets'/m/'2026-05-15.json').read_text());packet=copy.deepcopy(base);packet['asof']=date;packet['review_kind']='MATERIAL_EVENT' if date in json.loads((Path(__file__).parent/'event_policy.json').read_text()).get('US_material_event_reviews',[]) else 'MONTHLY';docs=[]
previous=sorted((B/'decisions'/m).glob('*.json'));previous=[p for p in previous if p.stem<date]
if previous:packet['prior_decision']=json.loads(previous[-1].read_text())
for case in packet['cases']:
 s=case['symbol'];hist=pd.read_csv(B/'screen_inputs'/s/'bars.csv');f=B/'evaluator_only'/s;future=pd.read_csv(f/('bars_v2.csv' if m=='KR' else 'bars.csv'));hist=pd.concat([hist[hist.date<'2026-05-15'],future]);hist=hist[hist.date<=date].drop_duplicates('date').sort_values('date');past=hist.dropna(subset=['close']);assert past.date.iloc[-1]==date,'MISSING_ASOF_CLOSE';case['asof']=date;case['price']=float(past.close.iloc[-1]);case['momentum63']=float(past.close.iloc[-1]/past.close.iloc[-64]-1);case['vol63']=float(past.close.pct_change().tail(63).std()*np.sqrt(252));case['observed_price_tail']=past[['date','close']].tail(6).to_dict('records')
 case['capital_period_warning']='Dated verifiedfacts retain actualQ1period. Do not relabel them current; use later supplied statements when available. Unknowncurrentclaims remain uncertainty.'
 available=[]
 for p in (B/'primary'/s).glob('*/receipt.json'):
  r=json.loads(p.read_text());pub=r.get('published','9999');pub=pub[:4]+'-'+pub[4:6]+'-'+pub[6:8] if '-' not in pub else pub
  if r.get('status')!='SAVED' or pub>=date or p.with_name('invalid_document.json').exists():continue
  norm=p.with_name('normalized.txt')
  if not norm.exists():norm.write_text('\n'.join(re.sub(r'[ \t\xa0]+',' ',line).strip() for line in p.with_name('original.txt').read_text().splitlines() if line.strip()))
  t=norm.read_text()
  if m=='US':
   # Remove current website navigation, but keep dated article and all its tables.
   if s=='VRT':
    a=t.find('COLUMBUS');a=t.rfind('Quarter',0,a) if a>0 else 0;a=max(0,a-1000)
    # Financial article starts at dated release; no global archive/news list supplied.
    dm=re.search(r'(?:Apr|Jul|Oct)\s+\d{1,2},\s+2026',t)
    if dm:a=dm.start()
    b=t.find('SOURCE Vertiv',a);t=t[a:b if b>a else len(t)]
   elif s=='SFM':
    a=t.find('PHOENIX--');a=max(0,a);b=t.find('Investor Contacts',a);t=t[a:b if b>a else len(t)]
  available.append({'published':pub,'source_hash':sha(norm),'raw_hash':r['raw_sha256'],'text':t,'source_path':str(norm.relative_to(R))})
 if m=='US' and available:case['source_documents']=[sorted(available,key=lambda x:x['published'])[-1]]
 if m=='KR':
  if available:
   doc=sorted(available,key=lambda x:x['published'])[-1];full=doc['text'];chunks=[]
   for pat,n in [(r'II\. 사업의 내용',6500),(r'주요 제품 및 서비스',3500),(r'매출 및 수주상황',4000),(r'연결 현금흐름표',5000)]:
    hits=list(re.finditer(pat,full))
    if hits:chunks.append(full[hits[-1].start():hits[-1].start()+n])
   doc['text']='\n'.join(chunks);case['source_documents']=[doc]
  # H1 accessions may be later than the nominal Augdeadline: enforce real publication.
  p=B/'updates'/s/'accounts_H1.json';api=json.loads(p.read_text());facts=[]
  for i,r in enumerate(api.get('list',[])):
   pub=r['rcept_no'];pub=pub[:4]+'-'+pub[4:6]+'-'+pub[6:8]
   if pub>=date or r.get('sj_div') not in ['IS','CIS','BS','CF']:continue
   if not any(k in r.get('account_id','') for k in ['Revenue','OperatingIncome','ProfitLoss','CashAndCash','Borrowing','Debt','CashFlowsFromUsedInOperating','PaymentsToAcquireProperty','PurchaseOfProperty','Depreciation','EarningsLossPerShare','Liabilities','Equity']):continue
   key='thstrm_add_amount' if r.get('sj_div') in ['IS','CIS'] and r.get('thstrm_add_amount') else 'thstrm_amount'
   if r.get(key) in [None,'','-']:continue
   fct={'metric':r['account_id'],'label':r['account_nm'],'raw_value':r[key],'value':r[key].replace(',',''),'multiplier':1,'unit':'PER_SHARE' if 'EarningsLossPerShare' in r['account_id'] else 'CURRENCY','currency':'KRW','basis':'CFS','period_start':'2026-06-30' if r['sj_div']=='BS' else '2026-01-01' if key=='thstrm_add_amount' or r['sj_div']=='CF' else '2026-04-01','period_end':'2026-06-30','published':pub,'source_hash':sha(p),'source_path':str(p.relative_to(R)),'locator':{'kind':'json','path':['list',i,key]}};facts.append(verify_fact(fct,p.read_bytes(),date))
  if facts:case['verified_facts']=facts
  sp=B/'updates'/s/'shares_H1.json';z=json.loads(sp.read_text())
  for i,r in enumerate(z.get('list',[])):
   pub=r['rcept_no'];pub=pub[:4]+'-'+pub[4:6]+'-'+pub[6:8]
   if pub>=date or r.get('se') not in ['보통주','보통주식']:continue
   fct={'metric':'issued_common','raw_value':r['istc_totqy'],'value':r['istc_totqy'].replace(',',''),'multiplier':1,'unit':'SHARES','currency':'KRW','basis':'SFS','period_start':'2026-06-30','period_end':'2026-06-30','published':pub,'source_hash':sha(sp),'source_path':str(sp.relative_to(R)),'locator':{'kind':'json','path':['list',i,'istc_totqy']}};case['verified_facts'].append(verify_fact(fct,sp.read_bytes(),date))
  events=json.loads((B/'updates'/s/'list.json').read_text()).get('list',[]);case['dated_filings_observed']=[{k:r[k] for k in ['rcept_dt','rcept_no','report_nm']} for r in events if r['rcept_dt']<date.replace('-','')]
  if s=='011930.KS':case['capital_warning']='Yahoodeclared1:10reverse splitMay15before firstpossibletrade. InitialQ1sharesvscurrentprice incompatible; H1share count later known, full corporateactionprimary verification missing; never calculate10xvalue or performance from unadjusteddenominator.'
  case['forecast_basis_warning']='H1YTD income/CF differs from Q1; do not mechanically doubleseasonal numbers or mixsingleQ withYTD.'
 packet.setdefault('macro',[])
for p in (B/'macro'/m).glob('*.json'):
 r=json.loads(p.read_text())
 if r.get('status')=='SAVED' and r['published']<date:packet['macro'].append(r)
packet['macro']=sorted(packet.get('macro',[]),key=lambda x:x['published'])[-1:]
# Only new, not previously sealed packets gain causal account feedback. Prior US inputs remain immutable.
from evaluate import load_panel,plan
from quant_harness.investment.research import replay_targets
from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec
prior_decisions=[json.loads(p.read_text()) for p in previous];panel,all_dates,_=load_panel(m,[c['symbol'] for c in packet['cases']]);past_dates=[d for d in all_dates if d<=date]
if past_dates and prior_decisions:
 cost=C['cost_bps'][m];spec=ExecutionSpec(cost['buy_fee'],cost['sell_fee'],cost['half_spread'],5,30,.01,C['minimum_order_notional'][m]);ledger,rebalance,_=plan(m,'POLICY',prior_decisions,panel,past_dates,spec);account,fills,_=replay_targets(panel,past_dates,ledger,C['capital'][m],spec,rebalance_dates=rebalance,allow_unpriced_hold=True);last=account.iloc[-1]
 packet['account_state_asof']={'date':last['date'],'cash':float(last['cash_krw']),'nav':float(last['nav_krw']) if np.isfinite(last['nav_krw']) else None,'quantities':json.loads(last['holdings_json']),'fills_so_far':fills.to_dict('records'),'source':'causal existing shared replay, dates<=asof only','not_final_performance_feedback':True}
packet['new_information_limit']='Bounded dated earnings and policy statements, not full historical news/flows/consensus. Unknowns stayunknown. No futureevaluatorsummary or performance passed.'
freeze(B/'packets'/m/(date+'.json'),packet);print(m,date,'PACKET',flush=True)

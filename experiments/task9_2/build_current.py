from common import *
from decimal import Decimal
import re
from quant_harness.investment.financial_packet import verify_fact

def fact(p,metric,token,scale,unit,begin,end,pub,anchors,needle,occurrence=0):
 text=p.read_bytes().decode('utf-8');hits=list(re.finditer(re.escape(needle),text));a=hits[occurrence].start();pos=text.index(token,a);left=max(a,pos-40);right=pos+len(token)+40;v=token.replace(',','').replace('\n','').replace(' ','');v='-'+v[1:-1] if v.startswith('(') else v
 f={'metric':metric,'raw_value':token,'multiplier':scale,'value':str(Decimal(v)*Decimal(str(scale))),'unit':unit,'currency':'USD','basis':'CFS','period_start':begin,'period_end':end,'published':pub,'source_hash':sha(p),'source_path':str(p.relative_to(R)),'locator':{'kind':'text','start':left,'end':right,'quote':text[left:right],'context_anchors':anchors}};return verify_fact(f,p.read_bytes(),now())
cases=[]
p=B/'sources/PH/original.txt';anchors=['September 30,','(In millions)'];facts=[]
for metric,token,scale,unit,needle in [('revenue','5,992',1e6,'CURRENCY','Net sales'),('net_income','884',1e6,'CURRENCY','Income before income taxes'),('cash','711',1e6,'CURRENCY','Cash and cash equivalents'),('debt_current','4,744',1e6,'CURRENCY','long-term debt'),('debt_noncurrent','12,734',1e6,'CURRENCY','Long-term debt'),('minority_claims','102',1e6,'CURRENCY','Noncontrolling interests'),('operating_cashflow','752',1e6,'CURRENCY','Net cash provided by operating activities'),('capex_gross','(109)',1e6,'CURRENCY','Capital expenditures'),('depreciation','97',1e6,'CURRENCY','Depreciation'),('amortization','189',1e6,'CURRENCY','Amortization'),('diluted_shares','127.8',1e6,'SHARES','Weighted average shares outstanding')]:
 stock=metric in ['cash','debt_current','debt_noncurrent','minority_claims'];facts.append(fact(p,metric,token,scale,unit,'2026-09-30' if stock else '2026-07-01','2026-09-30','2026-11-05',anchors,needle))
text=p.read_text();cases.append({'symbol':'PH','market':'US','industry':'motion_control_industrial','verified_facts':facts,'business_and_guidance':text[:4200],'financial_statement_context':text[text.find('CONSOLIDATED STATEMENTS OF INCOME'):text.find('CONSOLIDATED STATEMENTS OF INCOME')+5000],'caveats':['GAAP sales5992m vs report highlights rounded6.0bn; do not conflate segment totals','Acquisition-driven debt increase and intangible amortization; distinguish adjusted earnings and actual reinvestment','Capital expenditure cash-flow token negative is outflow, use positive investment magnitude for FCFF'],'source_hash':sha(p)})
p=B/'sources/DECK/original.txt';anchors=['Three Months Ended September 30,','in thousands'];facts=[]
for metric,token,unit,needle in [('revenue','1,480,554','CURRENCY','Net sales'),('operating_income','389,456','CURRENCY','Income from operations'),('net_income','313,135','CURRENCY','Net income'),('cash','1,209,722','CURRENCY','Cash and cash equivalents'),('diluted_shares','135,300','SHARES','Weighted-average common shares outstanding')]:facts.append(fact(p,metric,token,1000,unit,'2026-09-30' if metric=='cash' else '2026-07-01','2026-09-30','2026-10-22',anchors,needle))
q=B/'sources/DECK_10Q/original.txt';text=q.read_text();m=re.search(r'Net cash \(used in\) provided by operating activities\s*(\(\s*9,262\s*\))',text);assert m
facts.append(fact(q,'operating_cashflow_6M',m.group(1),1000,'CURRENCY','2026-04-01','2026-09-30','2026-10-29',['September','in thousands'],'Net cash (used in) provided by operating activities'))
m=re.search(r'Purchases of property and equipment\s*(\(\s*37,176\s*\))',text);assert m;facts.append(fact(q,'capex_6M',m.group(1),1000,'CURRENCY','2026-04-01','2026-09-30','2026-10-29',['September','in thousands'],'Purchases of property and equipment'))
cases.append({'symbol':'DECK','market':'US','industry':'footwear_consumer','verified_facts':facts,'business_and_guidance':p.read_text()[p.read_text().find('Second Quarter Fiscal'):p.read_text().find('Non-GAAP Financial Measures')],'caveats':['No outstanding borrowings per issuer; finance/operating lease obligations need consistent valuation treatment','Tariff refund benefits are nonrecurring, strip them from normalized growth','Q2 diluted135.3m average shares; Oct8spot133479987; do not treat average shares as exact current diluted denominator','Six-month negative OCF is seasonal working-capital signal, not automatically annual negative cash flow'],'source_hash':sha(p),'additional_source_hash':sha(q)})
for symbol,folder in [('033780.KS','KTG_Q3'),('003230.KS','SAMYANG_Q3')]:
 p=B/'sources'/symbol.split('.')[0]/'accounts.json';api=json.loads(p.read_text());facts=[]
 for i,r in enumerate(api['list']):
  if r['sj_div'] not in ['IS','BS','CF']:continue
  wanted=['Revenue','OperatingIncome','ProfitLossAttributable','CashAndCash','Borrowing','LeaseLiabilities','CashFlowsFromUsedInOperating','PurchaseOfProperty','PaymentsToAcquire','EarningsLossPerShare','Depreciation']
  if not any(w in r['account_id'] for w in wanted):continue
  key='thstrm_add_amount' if r['sj_div']=='IS' and r.get('thstrm_add_amount') else 'thstrm_amount'
  if r.get(key) in [None,'','-']:continue
  stock=r['sj_div']=='BS';start='2026-06-30' if stock else '2026-01-01' if key=='thstrm_add_amount' or r['sj_div']=='CF' else '2026-04-01';pub=r['rcept_no'][:4]+'-'+r['rcept_no'][4:6]+'-'+r['rcept_no'][6:8];f={'metric':r['account_id'],'account_name':r['account_nm'],'raw_value':r[key],'multiplier':1,'value':r[key],'unit':'PER_SHARE' if 'EarningsLossPerShare' in r['account_id'] else 'CURRENCY','currency':'KRW','basis':'CFS','period_start':start,'period_end':'2026-06-30','published':pub,'source_hash':sha(p),'source_path':str(p.relative_to(R)),'locator':{'kind':'json','path':['list',i,key]}};facts.append(verify_fact(f,p.read_bytes(),now()))
 sp=p.with_name('shares.json');z=json.loads(sp.read_text())
 for i,r in enumerate(z.get('list',[])):
  if r['se'] not in ['보통주','보통주식']:continue
  pub=r['rcept_no'][:4]+'-'+r['rcept_no'][4:6]+'-'+r['rcept_no'][6:8]
  for key,metric in [('istc_totqy','issued_common'),('tesstk_co','treasury_common')]:
   if r.get(key) in [None,'-','']:continue
   f={'metric':metric,'raw_value':r[key],'multiplier':1,'value':r[key].replace(',',''),'unit':'SHARES','currency':'KRW','basis':'SFS','period_start':'2026-06-30','period_end':'2026-06-30','published':pub,'source_hash':sha(sp),'source_path':str(sp.relative_to(R)),'locator':{'kind':'json','path':['list',i,key]}}
   if metric=='treasury_common' and int(f['value'])==0:continue
   facts.append(verify_fact(f,sp.read_bytes(),now()))
 primary=B/'sources'/folder/'original.txt';cases.append({'symbol':symbol,'market':'KR','industry':'tobacco_staples' if symbol.startswith('033') else 'food_export_growth','verified_facts':facts,'Q3_official_presentation':primary.read_text()[:15000],'Q3_primary_hash':sha(primary),'caveats':['Q3presentation unaudited and H1 financials are different periods; never sum mismatched quarter/YTD figures','H1 share count/treasury may have changed due buybacks; exact current dilution requires follow-up','Use company-specific economics; quarterly earnings distortions and FX must be separated from operating growth']})
for c in cases:
 c['price_observation']=json.loads((B/'current_prices'/c['symbol']/'summary.json').read_text());assert c['price_observation']['status']=='SAVED'
packet={'asof':now(),'cases':cases,'source_time_policy':'All used documents public before seal; history cases excluded','candidate_discovery':{'TPR':'SOURCE_ACCESS_FAILED_NOT_INVESTMENT_REJECTION','PH':'current record results/acquisition/debt','DECK':'current brand growth vsDTC weakness/tariff refund','033780.KS':'Q3 growth vsnonoperating earnings/returns','003230.KS':'Q3export growth vsFX/working capital'},'quant_native':'No verified out-of-sample Quanta/RD forward alpha; MOM63 is independent descriptive reference only'}
freeze(B/'current_numeric_packet.json',packet);print('CURRENT_VERIFIED_FACTS',sum(len(c['verified_facts']) for c in cases))

from common import *
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
from quant_harness.investment.financial_packet import verify_fact
load_environment(R);c=OpenDartClient();p=B/'sources/LG_FY24_accounts.json'
if p.exists():api=json.loads(p.read_text())
else:api=c._request('fnlttSinglAcntAll.json',{'corp_code':'00105961','bsns_year':'2024','reprt_code':'11011','fs_div':'CFS'});dump(p,api)
facts=[]
for i,row in enumerate(api.get('list',[])):
 if row['sj_div'] not in ['CF','IS','BS'] or row.get('thstrm_amount') in [None,'','-']:continue
 if row['sj_div']=='BS' and not any(w in row['account_id'] for w in ['CashAnd','Borrowing','LeaseLiabilities','Equity']):continue
 pub=row['rcept_no'][:4]+'-'+row['rcept_no'][4:6]+'-'+row['rcept_no'][6:8];assert pub<='2025-06-30'
 f={'metric':row['account_id'],'account_name':row['account_nm'],'raw_value':row['thstrm_amount'],'value':row['thstrm_amount'],'multiplier':1,'currency':'KRW','unit':'PER_SHARE' if 'EarningsLossPerShare' in row['account_id'] else 'CURRENCY','basis':'CFS','period_start':'2024-12-31' if row['sj_div']=='BS' else '2024-01-01','period_end':'2024-12-31','published':pub,'source_hash':sha(p),'source_path':str(p.relative_to(R)),'locator':{'kind':'json','path':['list',i,'thstrm_amount']}};facts.append(verify_fact(f,p.read_bytes(),'2025-06-30'))
packet=json.loads((B/'historical_numeric_packet.json').read_text());lg=next(x for x in packet['cases'] if x['symbol']=='011070.KS');lg['annual_verified_facts']=facts;lg['annual_comparative_source_hash']=sha(R/'runtime/task9_1/inputs/2025-06-30/011070.KS/original.txt');sfm=next(x for x in packet['cases'] if x['symbol']=='SFM');sfm['annual_statement_source_hash']=sha(B/'sources/SFM_FY24/original.txt')
freeze(B/'historical_numeric_packet_v3.json',packet)
print('ANNUAL_FACTS',len(facts));print([(f['account_name'],f['value']) for f in facts if any(w in f['account_name'] for w in ['감가','상각','취득','현금흐름'])])

from common import *
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);c=OpenDartClient()
# Explicit original-table recovery; amended API is retained but not used.
for date,s,shares in [('2024-11-29','035720.KS',443530908),('2024-11-29','229640.KS',30624879)]:
 f=B/'inputs'/date/s;x=json.loads((f/'summary.json').read_text());text=(f/'original.txt').read_text();assert format(shares,',') in text;assert '2024년 09월 30일' in text
 x.update(dated_report_shares=shares,share_basis='MANUALLY_VERIFIED_ORIGINAL_COMMON_SHARE_TABLE',share_original_hash=sha(f/'original.zip'),cap_proxy=shares*x['last_close'],size_status='PASS_DATED_REPORTED_SHARES_PROXY' if shares*x['last_close']>=500e9 else 'FAIL_SIZE');freeze(f/'summary_v3.json',x)
# Quarterly sections explicitly omit shares. A public prior annual report is a
# dated proxy, not an interpolation or exact June30 share-count assertion.
for s in ['011070.KS','031210.KS','484870.KS']:
 f=B/'inputs/2025-06-30'/s;x=json.loads((f/'summary.json').read_text());p=f/'annual_shares.json'
 if p.exists():z=json.loads(p.read_text())
 else:z=c._request('stockTotqySttus.json',{'corp_code':x['corp_code'],'bsns_year':'2024','reprt_code':'11011'});dump(p,z)
 rows=[v for v in z.get('list',[]) if v.get('rcept_no','9999')[:8]<='20250630' and v.get('se') in ['보통주','보통주식']]
 def num(v):
  try:return int(v.replace(',',''))
  except:return 0
 shares=sum(num(v.get('istc_totqy','')) for v in rows)
 x.update(dated_report_shares=shares,dated_share_accessions=[v['rcept_no'] for v in rows],share_basis='PRIOR_ANNUAL_PROXY_NOT_EXACT_JUNE_SHARES',cap_proxy=shares*x['last_close'],size_status='PASS_DATED_REPORTED_SHARES_PROXY' if shares*x['last_close']>=500e9 else 'FAIL_OR_UNKNOWN_SIZE');freeze(f/'summary_v3.json',x)
for date in ['2024-11-29','2025-06-30']:
 for market in ['US','KR']:
  pool=json.loads((B/'cohorts'/date/('US.json' if market=='US' else 'KR_mainboard_v2.json')).read_text());rows=[]
  for x in pool:
   f=B/'inputs'/date/x['symbol'];p=next((f/n for n in ['summary_v3.json','summary_v2.json','summary.json'] if (f/n).exists()));rows.append(json.loads(p.read_text()))
  eligible=[x for x in rows if x['status']=='PRICE_ELIGIBLE' and (market=='US' or x['size_status'].startswith('PASS'))];deep=[];sectors=set()
  for x in eligible:
   if x['sector'] not in sectors:deep.append(x);sectors.add(x['sector'])
   if len(deep)==5:break
  for x in sorted(eligible,key=lambda x:(-x['momentum63'],x['symbol'])):
   if len(deep)>=5:break
   if x not in deep:deep.append(x)
  packet={'asof':date,'market':market,'screened':rows,'eligible_count':len(eligible),'deep':deep,'allocation_basket':[x['symbol'] for x in deep[:3]],'contract_hash':sha(R/'experiments/task9_1/contract.json'),'candidate_fingerprint':digest(pool),'created_at':now(),'partial_if_fewer_than5':len(deep)<5}
  freeze(B/'screens'/date/(market+'.json'),packet);print(date,market,len(eligible),[(x['symbol'],x['name']) for x in deep],flush=True)

from common import *
from collections import defaultdict,Counter

def main():
 if (B/'plan.json').exists():raise RuntimeError('Plan already fixed; reuse it')
 ref=json.loads((R/'runtime/task13_b2/identity_reference.json').read_text());catalog=json.loads(body(ref));mapping={v['ticker'].replace('-','.'):v for v in catalog.values()}
 assets=json.loads((R/'runtime/task13_r0/native_manifest/assets.json').read_text());us=[a for a in assets if a['market']=='US' and a['cohort']=='CORE'];existing=json.loads((R/'runtime/task13_c2/cache_inventory.json').read_text());cached={int(x['snapshots'][0]['CIK']) for x in existing['snapshots']}
 pools=defaultdict(list);cache=[];excluded=[];seen=set()
 for a in sorted(us,key=lambda x:x['symbol']):
  row=mapping.get(a['symbol'].replace('-','.'))
  if not row:excluded.append({'symbol':a['symbol'],'reason':'NO_CURRENT_OFFICIAL_CIK_MAPPING'});continue
  cik=int(row['cik_str']);sector=a['sector_current']
  if sector in ['Financials','Real Estate']:excluded.append({'symbol':a['symbol'],'CIK':cik,'reason':'PRESPECIFIED_ACCOUNTING_SCOPE_FINANCIAL_OR_REIT'});continue
  if cik in seen:excluded.append({'symbol':a['symbol'],'CIK':cik,'reason':'DUPLICATE_ISSUER_SHARECLASS'});continue
  seen.add(cik)
  import csv
  with (R/a['eligibility_path']).open() as f:dates=[r['date'] for r in csv.DictReader(f) if r['eligible']=='True']
  if not dates or dates[0]>'2018-01-01':excluded.append({'symbol':a['symbol'],'CIK':cik,'reason':'CONSERVATIVE_NATIVE_HISTORY_START_AFTER2018; no B3 overlay'});continue
  x={'symbol':a['symbol'],'CIK':str(cik).zfill(10),'current_title':row['title'],'sector_current':sector,'size_current':a['size_bucket_current'],'R0_first_native_session':dates[0],'R0_asset':a,'classification':'SURVIVOR_RESEARCH; current sector/size used only acquisition stratification, not historical membership'}
  if cik in cached:cache.append(x)
  else:pools[(sector,a['size_bucket_current'])].append(x)
 # Deterministic sector x current size round-robin, alphabetic within stratum, no returns.
 order=[]
 while any(pools.values()):
  for key in sorted(pools):
   if pools[key]:order.append(pools[key].pop(0))
 order=order[:80];assert len(order)>=20
 p={'id':'TASK13_C3_CASH_ACCRUAL_QUALITY','at':now(),'feature':'-(NetIncomeLoss-NetCashProvidedByUsedInOperatingActivities)/((Assets_start+Assets_end)/2)','direction':1,'H':252,'Vibe_family':'Known fund_accruals; cash-accrual proxy, not manipulation, not new independent formula','universe':'R0 US CORE176; dedupCIK, financials and REIT/realestate separate ineligible; no current-cap historical inference','new_order':order,'pilot':order[:20],'conditional_extension':order[20:80],'cache_reuse':cache,'excluded':excluded,'sample_policy':'No replacement outside frozen80. Stop acquiring new companies once source-verified>=50 and>=150 issuer-periods across>=4filedyear cohorts; exact counts are screening minima not power certification. Continue within300 requests only if pilot source yield supports goal.','financials':{'filed':['2017-01-01','2022-12-31'],'form':'10-K only; amendments separate/excluded; same original accession, annual300..430days, filed<=180days fromperiodend, sameUSD,no dimensions, entityCIK match','tags':['NetIncomeLoss','NetCashProvidedByUsedInOperatingActivities','Assets'],'no_alias_imputation_or_quarter_synthesis':True,'current_period_only':'SEC submissions reportDate==annual end, not later comparative vintage','period_priority_filing_years':[2021,2020,2019,2022,2018,2017],'per_company_original_cap':4,'first_pass_original_cap':1,'scope_risks':'M&A, discontinued operations, noncash investment/workingcapital remain explicit risks; no source-text-keyword suitability certificate'},'pilot_gate':{'n':20,'min_verified_original_issuers':14,'min_structural_issuer_fraction':.75,'expansion_basis':'at least14of20 representative original source matches, >=.75structuralyield, no fatal mismatches, projected >=50firms/150periods withinremainingrequestbudget; evaluate before expansion','extension_batch':10,'stop_if_last10_verified_rate_below':.5},'minimum':{'issuers':50,'issuer_periods':150,'filedyear_cohorts':4},'HTTP_max':300,'per_response_max_bytes':24000000,'total_download_cap_bytes':1200000000,'transport':'Existing B1 Sources->equities.fetch, same SEC UserAgent and environment. .5s between successes, <=2attempts per source,3consecutive403/429 circuit. No proxy/IPv4/identity changes.','original_policy':'Primary10-K HTML via submissions; cached metadata reused, history onlyforselected accession; one SGMLfallback if no inline. Request cap includesallfailures/retries. No new downloader.','public_clock':'Original SEC filingdate+conservative NewYork endofday -> nextR0 observedUSsession. Rawacceptance retained but timezone not assumed; not first earningsnews.','revision_gate':'Source SHA+immutable savedbody; same accession/tag/context/unit consistency, conflictingvalues failclosed. Task-local financial ingestion, not V87 price/canonical admission; no operational source revision.','LLM':{'planned_calls':0,'max_calls':2,'max_tokens':80000},'CPU_hours':8,'future_return_queries':0,'protection':'No Factory/Queue/Paper/Shadow/Champion/Live/Team2 changes; ongoing observations left running','baseline_C2':{'unique_cached':16,'accrual_structural_issuers':15,'accrual_periods':80,'grade':'Upperbounds not certified events; existing C2 outputs never overwritten or recounted as new collection'}}
 dump('plan.json',p);(B/'plan.sha256').write_text(sha(B/'plan.json')+'\n');dump('selection_distribution.json',{'pilot_sector':dict(Counter(x['sector_current'] for x in order[:20])),'pilot_size':dict(Counter(x['size_current'] for x in order[:20])),'new_order_sector':dict(Counter(x['sector_current'] for x in order)),'cache_reuse':len(cache),'official_mapping_receipt':ref,'mapping_raw_sha':ref['source_hash'],'before_first_HTTP':True});print('FROZEN pilot',[x['symbol'] for x in order[:20]],'cached',len(cache),'neworder',len(order))
if __name__=='__main__':main()

"""User amendment: separate100-500bn group, current actual turnover priority."""
import json,datetime,collections
from pathlib import Path
from toss_metadata import get,B
md=json.loads((B/'universe_metadata.json').read_text())['sources'];t=json.loads((B/'toss_universe_metadata.json').read_text());ranks,receipt=get('/api/v1/rankings',{'type':'MARKET_TRADING_AMOUNT','marketCountry':'KR','duration':'1mo','count':100})
rankrows=ranks['result'].get('rankings',[]);liquidity={r['symbol']:r for r in rankrows};candidates=[]
for board in ['KOSPI','KOSDAQ']:
 kind={r['종목코드']:r for r in md[board]['rows']}
 for r in t['markets'][board]['rows']:
  code=r['symbol'];cap=r['current_cap_KRW']
  if not(1e11<=cap<5e11) or code not in kind or r.get('status')!='ACTIVE' or r.get('securityType')!='STOCK' or not r.get('isCommonShare') or any(s in r['name'] for s in ['스팩','기업인수']):continue
  q=liquidity.get(code);amount=float(q['tradingAmount']) if q and q.get('tradingAmount') is not None else None
  candidates.append({'symbol':code+('.KS' if board=='KOSPI' else '.KQ'),'market':'KR','board':board,'name':r['name'],'sector_current':kind[code]['업종'],'current_cap_KRW':cap,'size_bucket_current':'CAP_0_1T_TO_0_5T_SEPARATE','list_date_toss':r.get('listDate'),'list_date_kind':str(kind[code]['상장일'])[:10],'isin':r.get('isinCode'),'current_listing_verified':True,'PIT_membership':'SURVIVOR_RESEARCH','cohort':'SMALLER_LIQUIDITY_RESEARCH_SEPARATE','selection_source':'TOSS_CURRENT_CAP_KIND_INDUSTRY_AND_CURRENT_MARKET_AMOUNT','current_actual_month_amount':amount})
# Data collection opportunity is bounded, not forced final admission. Actual monthly
# amount takes priority, with sector diversity; absent amount explicitly unknown.
known=sorted([r for r in candidates if r['current_actual_month_amount'] is not None],key=lambda r:(-r['current_actual_month_amount'],r['symbol']));unknown=sorted([r for r in candidates if r['current_actual_month_amount'] is None],key=lambda r:(r['board'],r['sector_current'],-r['current_cap_KRW'],r['symbol']))
chosen=[]
for board in ['KOSPI','KOSDAQ']:chosen.extend([r for r in known if r['board']==board][:10]);used={r['symbol'] for r in chosen}
# If top100market list has too few small names, cap-only staging is not admission:
# sample at most two perindustry, then require measurable60session liquidity.
counts=collections.Counter((r['board'],r['sector_current']) for r in chosen)
for r in unknown:
 if len(chosen)>=20:break
 if sum(x['board']==r['board'] for x in chosen)>=10:continue
 k=(r['board'],r['sector_current'])
 if counts[k]>=2:continue
 chosen.append(r);counts[k]+=1
for i,r in enumerate(chosen):r['alias']='KRS'+str(i+1).zfill(4)
contract={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope_change_reason':'Explicit user correction: stockresearch not tradeuniverse; retain>=500bn core, separate100-500bn cohort','core_universe_unchanged':True,'max_extra_downloads':20,'sampling_budget':'At most10perboard; failed or illiquid names will not be replaced to meet a count','current_cap_not_historical_eligibility':True,'liquidity_ranking_receipt':receipt,'known_actual_amount_candidates':len(known),'actual_month_amount_priority':True,'post_download_admission':{'eligible_sessions_last60_min':55,'median60_quoteclose_times_volume_KRW_min':500e6,'p10_60_quoteclose_times_volume_KRW_min':100e6,'proxy_not_actual_turnover':True,'bad_or_ambiguous_data':'quarantine, no imputation/no targetfilling'},'LLM_calls':0}
(B/'smallcap_contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n');(B/'smallcap_universe.json').write_text(json.dumps(chosen,ensure_ascii=False,indent=2)+'\n');print('SMALLCAP_STAGED',len(chosen),'CURRENT_ACTUAL_AMOUNT_KNOWN',len(known),'BOARDS',dict(collections.Counter(r['board'] for r in chosen)))

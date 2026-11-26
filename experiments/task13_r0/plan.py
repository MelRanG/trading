"""Pre-price selection: current broad/midfund+official listings, no future-return ranking."""
import json,hashlib,datetime,collections,re
from pathlib import Path
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r0'
if (B/'universe.json').exists():raise SystemExit('Universe frozen; reuse')
md=json.loads((B/'universe_metadata.json').read_text())['sources'];t=json.loads((B/'toss_universe_metadata.json').read_text());old=json.loads((R/'runtime/task10/universe.json').read_text());catalog={r['symbol']:r for r in md['NASDAQ_CACHED']['rows'] if r.get('common_stock_verified')};out=[]
def number(x):
 try:return float(str(x).replace(',',''))
 except (ValueError,TypeError):return 0.
def choose(rows,n,group,key):
 groups=collections.defaultdict(list)
 for r in sorted(rows,key=lambda x:(-x[key],x['symbol'])):groups[r[group]].append(r)
 selected=[]
 while len(selected)<n and any(groups.values()):
  for g in sorted(groups):
   if groups[g] and len(selected)<n:selected.append(groups[g].pop(0))
 return selected
used=set()
for name,limit in [('IVV',110),('IJH',70)]:
 rows=[]
 for r in md.get(name,{}).get('rows',[]):
  symbol=r.get('Ticker','')
  if symbol not in catalog or not re.fullmatch('[A-Z]{1,5}',symbol) or symbol in used:continue
  rows.append({'symbol':symbol,'market':'US','board':catalog[symbol]['exchange'],'sector_current':r['Sector'],'size_bucket_current':'LARGE_FUND_PROXY' if name=='IVV' else 'MID_FUND_PROXY','selection_value':number(r.get('Market Value')),'name':r.get('Name',catalog[symbol]['name']),'selection_source':name,'PIT_membership':'SURVIVOR_RESEARCH','current_listing_verified':True})
 selected=choose(rows,limit,'sector_current','selection_value');out.extend(selected);used.update(r['symbol'] for r in selected)
for board,target in [('KOSPI',70),('KOSDAQ',50)]:
 kind={r['종목코드']:r for r in md[board]['rows']};rows=[]
 for r in t['markets'][board]['rows']:
  code=r['symbol'];cap=r['current_cap_KRW']
  if code not in kind or r['status']!='ACTIVE' or r.get('securityType')!='STOCK' or not r.get('isCommonShare') or cap<500e9:continue
  if any(x in r['name'] for x in ['스팩','기업인수']):continue
  symbol=code+('.KS' if board=='KOSPI' else '.KQ');listing=r.get('listDate');kdate=str(kind[code]['상장일'])[:10]
  rows.append({'symbol':symbol,'market':'KR','board':board,'name':r['name'],'sector_current':kind[code]['업종'],'size_bucket_current':'CAP_GE_5T' if cap>=5e12 else 'CAP_0_5T_TO_5T','selection_value':cap,'current_cap_KRW':cap,'current_listing_verified':True,'list_date_toss':listing,'list_date_kind':kdate,'isin':r.get('isinCode'),'current_halt':r.get('koreanMarketDetail',{}).get('krxTradingSuspended') if r.get('koreanMarketDetail') else None,'selection_source':'TOSS_CURRENT_CAP_AND_KIND_CURRENT_INDUSTRY','PIT_membership':'SURVIVOR_RESEARCH'})
 selected=choose(rows,target,'sector_current','selection_value');out.extend(selected)
# Keep previously researched stocks only if selected by the same new broad screen;
# never append historical winners to boost apparent skill.
for i,r in enumerate(out):r['alias']=r['market']+'R'+str(i+1).zfill(4);r['old_cohort']=any(a['symbol']==r['symbol'] and a['role']=='stock' for a in old)
(B/'universe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
contract={'schema':'TASK13_R0_PRICE_EXPANSION_V1','sealed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'universe_hash':hashlib.sha256((B/'universe.json').read_bytes()).hexdigest(),'selection':'CURRENT_SURVIVOR_RESEARCH_NOT_HISTORICAL_UNIVERSE. Currentfund sector-strata110large70midUS; KR currentcap>=500bn, officialboard/currentindustry roundrobin70KOSPI50KOSDAQ. No stockreturn selection.','period':['2017-01-01','2026-11-13'],'requests_cap':500,'spacing_seconds':1,'pilot':'5US5KR raw checks then V87+revision+rowquality; no bulk expansion before pilot pass','batch_size':25,'quote_basis':'Yahoo provider quote (split-adjustment possible), NOT certified nominal execution','adjusted_basis':'Sourceadjclose/quoteclose applied consistently to OHLC, volume_as_reported retained; research-only, no total-return execution claim','data_policy':'No imputation/correction, unknown daily jump absreturn>35% OR zero volume masked UNVERIFIED, known splitdate retained but adjustedjump requiresreview. Structuralbad rows retained in raw/quarantined.','identity':'currentlisting verified; vendorfirstTradeDate and currentofficiallisting compared, historicalticker/delist completeness partial','fit':['2017-01-01','2022-12-31'],'validation':['2023-04-03','2024-12-31'],'exposed_evaluator':['2025-01-01','2026-11-13'],'split':'labels end strictly before fit boundary, fixed60session embargo conservative for5/20/60. Existinghistory remains exposed development notHoldout.','native_inputs':'SharedtrainonlyHDF/CSV reference; no evaluatorlabels toresearcher. QlibDatasetH ABI, originalfactor2probes, no fit/LLM/evolution.','LLM_calls':0,'training':0,'no_mutation_of_old_data':True}
(B/'contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
print('FROZEN',dict(collections.Counter(r['market'] for r in out)),dict(collections.Counter(r['size_bucket_current'] for r in out)))

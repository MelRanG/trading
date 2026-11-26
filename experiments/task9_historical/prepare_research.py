"""No future evaluation sources, credentials or current aliases enter research."""
from pathlib import Path
import json,re,hashlib,sys
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_historical';W=Path('/home/ansy/app/quant-diligence/task9-historical-work');W.mkdir(exist_ok=True);(W/'home').mkdir(exist_ok=True)
sys.path.insert(0,str(R/'src'));from quant_harness.investment.research import digest
manifest=json.loads((B/'originals/manifest.json').read_text())
core='''Apply the supplied V3 core principles: discover source-supported material facts, competitive and substitution risks, execution, leading indicators and conversion, cash/debt/dilution/contracts/accounting, independent future operating forecasts distinct from company guidance, suitable valuation/reverse valuation, Bull/Base/Bear and falsification. Do not invent the missing full V3 prompt. You are the pinned Vibe ChatLLM research component, not the full Autopilot/screener. No tools/web/memory. Analyze only attached sources. Your historical knowledge can leak: explicitly disclose any claim not grounded here and do not use it. Archived reports are partial extracts from recovered XML; line/table alignment and units may be uncertain. Original accession is dated but reconstructed market membership, prices, calendar and corporate actions are NOT verified. Do not claim this is a full historical investment replay. All eligible expected price returns, valuations and weights must remain null/zero if required data missing; do not call missing-data cash a successful strategy. You may nominate RESEARCH_PRIORITY candidates without price-qualified BUY. SPAC/unlisted/insufficient candidates may be excluded, but keep all exclusions. Return JSON only.'''
schema={'asof':'YYYY-MM-DD','input_hash':'provided','mode':'A','scope':'PARTIAL_FILING_COHORT_NOT_WHOLE_MARKET','candidates':[{'accession':'provided','original_company':'from document','research_priority':1,'decision':'RESEARCH_PRIORITY or WAIT_DATA or EXCLUDE','facts':[{'source_id':'accession','quote':'EXACT contiguous source quote, no invented punctuation','interpretation':'separate inference'}],'bull':'conditional thesis','bear':'independent counterargument','leading_indicators':[],'forecasts':[{'metric':'revenue or operating_profit','fiscal_end':'YYYY-MM-DD','period_start':'YYYY-MM-DD','unit':'KRW_million','bear':0,'base':0,'bull':0,'forecast_origin':'INDEPENDENT_SCENARIO or COMPANY_GUIDANCE_RESTATEMENT','basis':'derived scenario; no calibrated probability'}],'forecast_abstention_reason':'if none','equity_price_return':None,'weight':0,'missing_data':[],'falsification':[]}],'relative_selection':[],'errors_or_uncertainty':[],'historical_memory_limitation':True}
for month in ['202111','202311','202411','202511','202605']:
 docs=[]
 for m in manifest:
  if m['month']!=month or m.get('parse_status')!='SAVED':continue
  text=(B/'originals'/m['rcept_no']/'original.txt').read_text();regions=[('identity',0,600)]
  for name,pattern,size in [('business',r'II\.\s*사업의 내용',2000),('financial',r'1\.\s*요약재무정보',2800),('cashflow',r'(?:연결 )?현금흐름표',600),('shares',r'4\.\s*주식의 총수',500)]:
   match=re.search(pattern,text)
   if match:regions.append((name,match.start(),size))
  snippets=[{'section':n,'start_char':i,'end_char':min(len(text),i+size),'text':text[i:i+size]} for n,i,size in regions]
  docs.append({'source_id':m['rcept_no'],'original_company':m['original_document_companies'],'published_date':m['reported_publication_date'],'available_conservative_utc':m['reported_publication_date'][:4]+'-'+m['reported_publication_date'][4:6]+'-'+m['reported_publication_date'][6:]+'T15:00:00Z','original_hash':m['source_hash'],'text_hash':m['text_hash'],'parse_warnings':m['xml_recovery_warnings'],'sections':snippets})
 # End-of-month civil-clock research cut, NOT an asserted official trading session.
 import calendar
 year=int(month[:4]);mon=int(month[4:]);day=calendar.monthrange(year,mon)[1];asof=f'{year}-{mon:02d}-{day}'
 packet={'asof':asof,'cutoff_utc':asof+'T23:59:59Z','documents':docs,'candidate_scope':'first100 monthly periodic filing rows; first4 original documents, deterministic receipt order','universe_quality':'PARTIAL','market':'KR','historical_session':'UNVERIFIED_NO_EXECUTION','prices':'MISSING','consensus':'MISSING','ticker_aliases':'WITHHELD_CURRENT_METADATA_NOT_PIT'};packet['input_hash']=digest(packet)
 packet['extraction_version']='BOUNDED_EXCERPTS_V2';packet['input_hash']=digest({k:v for k,v in packet.items() if k!='input_hash'})
 p=B/'packets'/('A2_'+month+'.json');p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(packet,ensure_ascii=False,indent=2));name='A2_'+month
 req={'messages':[{'role':'system','content':core},{'role':'user','content':json.dumps({'task':'Rank the four original-report companies for further fundamental research, not hindsight winners. Supply carefully justified numeric future operating scenarios if possible; otherwise explicitly abstain. A is independent company research, no macro/context or other modes. Preserve original evidence and scenario basis.','packet':packet,'output_schema_example':schema},ensure_ascii=False)}],'temperature':0,'response_format':{'type':'json_object'}}
 dest=W/(name+'.request.json')
 if dest.exists():assert json.loads(dest.read_text())==req
 else:dest.write_text(json.dumps(req,ensure_ascii=False))
 print(name,len(json.dumps(req,ensure_ascii=False)),packet['input_hash'])

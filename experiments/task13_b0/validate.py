"""Source-linked, deterministic financial/contract feasibility; no prices or LLM."""
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
import sys,json,re,hashlib,io
from lxml import html
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.financial_packet import verify_fact
B=R/'runtime/task13_b0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False))
def clean(s):return ' '.join(s.split())
def parse(p):return html.fromstring(p.read_bytes(),parser=html.HTMLParser(encoding='utf-8'))
def cells(t):return [[clean(' '.join(c.itertext())) for c in r.xpath('./td|./th|./te|./tu')] for r in t.xpath('./tbody/tr|./tr|./thead/tr')]
def number(t):return Decimal(t.replace(',','').replace('$','').replace('(','-').replace(')','').strip())
def numeric_proof(p,token,anchors,metric,multiplier,pub,start,end,currency='KRW',table_index=None):
 raw=p.read_bytes();text=raw.decode('utf-8');table=parse(p).xpath('//table')[table_index];start_line=table.sourceline;offset=sum(len(x) for x in text.splitlines(keepends=True)[:start_line-1]);openings=list(re.finditer(r'<table\b',text,re.I))
 if len(openings)==len(parse(p).xpath('//table')):offset=openings[table_index].start()
 endpos=re.search(r'</table\s*>',text[offset:],re.I);assert endpos;bound=offset+endpos.end();pos=text.find(token,offset,bound);assert pos>=0;quote=text[max(0,pos-80):pos+len(token)+80];a=max(0,pos-80)
 fact={'metric':metric,'raw_value':token,'multiplier':multiplier,'value':str(number(token)*Decimal(multiplier)),'unit':'CURRENCY','currency':currency,'basis':'CFS','period_start':start,'period_end':end,'published':pub,'source_hash':sha(p),'source_path':str(p.relative_to(R)),'locator':{'kind':'text','start':a,'end':a+len(quote),'quote':quote,'context_anchors':anchors}}
 proof=verify_fact(fact,raw,pub);proof['source_table_index']=table_index;proof['table_source_line']=start_line;proof['numeric_locator_inside_selected_statement']=True;return proof
result={'earnings':[],'contracts':[],'revision_audit':[],'no_price_access':True,'v87_price_gate':'NOT_APPLICABLE_DOCUMENT_QUARANTINE; no price or operating data admission. Need typed financial release contract before engine integration.','LLM_calls':0,'quanta_RD_runs':0,'models_trained':0}
for e in json.loads((B/'events.json').read_text()):
 if e['status']!='ORIGINAL_FETCHED':continue
 acc=e['filing']['rcept_no'];p=next((B/'documents'/acc).glob('*.xml'));doc=parse(p);pub=e['filing']['rcept_dt'];pub=pub[:4]+'-'+pub[4:6]+'-'+pub[6:8]
 vp=B/'sources'/('viewer_'+acc)/'original.bin';options=[]
 if vp.exists():
  for o in parse(vp).xpath('//select/option'):
   v=o.get('value','');m=re.fullmatch(r'rcpNo=(\d+)',v)
   if m:options.append({'receipt':m[1],'label':clean(' '.join(o.itertext()))})
  options=list({x['receipt']:x for x in options}.values())
 base={'symbol':e['symbol'],'publication_date':pub,'public_time_precision':'DATE_ONLY','observed_at':'See source receipt; actual 2026 backfill, no historical observation claim','source_path':str(p.relative_to(R)),'source_sha256':sha(p),'receipt_no':acc,'lineage':options,'source_grade':'VERIFIED_ORIGINAL_RECEIPT_DATE_BOUND','overall_PIT_grade':'PARTIAL','intraday_trade_eligible':False,'historical_execution':'NOT_ATTEMPTED','revision_knowledge':'Current viewer later versions used audit-only, never first-event input'}
 assert acc in [o['receipt'] for o in options],'VIEWER_ORIGINAL_RECEIPT_MISMATCH'
 if e['mode']=='contract':
  rows=[' '.join(r) for t in doc.xpath('//table') for r in cells(t)];full=clean(' '.join(doc.itertext()))
  def get(label):
   r=next(r for r in rows if label in r);m=re.search(re.escape(label)+r'\s+([\d,.]+)',r);assert m,(label,r);return m[1]
  amount=get('계약금액(원)');revenue=get('최근매출액(원)');ratio=get('매출액대비(%)');value=number(amount)/number(revenue)*100;quant=Decimal('1').scaleb(number(ratio).as_tuple().exponent);assert value.quantize(quant,rounding=ROUND_HALF_UP)==number(ratio)
  # Exact raw original text anchors and independently checked unit, with no false CFS earnings identity.
  base.update({'contract_amount_KRW':str(number(amount)),'previous_annual_revenue_KRW':str(number(revenue)),'contract_to_revenue_pct':float(value),'reported_pct':ratio,'source_numeric_tokens':{k:{'token':v,'raw_position':p.read_bytes().decode('utf-8').find(v)} for k,v in [('amount',amount),('revenue',revenue),('ratio',ratio)]},'currency_unit_verified':'labels 원 and % in original table','VAT_included':'부가세 포함' in full or '부가가치세 포함' in full,'annual_denominator_context':[r for r in rows if ('재무제표 기준' in r or '매출액은' in r)],'contract_term':[r for r in rows if '시작일' in r or '종료일' in r],'counterparty':[r for r in rows if '계약상대' in r],'previous_partial_contract':'이전계약' in full or '일부계약' in full,'revenue_recognition_schedule_verified':False,'first_information_to_market_verified':False})
  for v in [amount,revenue,ratio]:assert v in p.read_bytes().decode('utf-8')
  result['contracts'].append(base)
 else:
  found=None
  for i,t in enumerate(doc.xpath('//table')):
   prev=t.getprevious();context='' if prev is None else clean(' '.join(prev.itertext()));rows=cells(t)
   if not ('연결' in context and '손익계산서' in context and '단위' in context):continue
   rev=[r for r in rows if r and re.match(r'^매출액(?:\s|$)',r[0]) and len(r)==5];op=[r for r in rows if r and re.match(r'^영업이익(?:\s|$)',r[0]) and len(r)==5]
   if len(rev)==1 and len(op)==1:found=(i,context,rev[0],op[0]);break
  assert found,'NO_UNAMBIGUOUS_CFS_STATEMENT';i,context,rev,op=found;mult=1000000 if '백만원' in context else 1;assert '백만원' in context or re.search(r'단위\s*:\s*원',context)
  facts=[]
  for metric,row in [('revenue',rev),('operating_profit',op)]:
   assert row[1]==row[2] and row[3]==row[4],'Q1_VS_YTD_MISMATCH'
   for yr,token in [(e['year'],row[1]),(e['year']-1,row[3])]:
    # Raw markup periods/units are independently present; current-publication comparator, not historical first-vintage prior-year fact.
    text=p.read_bytes().decode();period=f'{yr}.01.01';assert period in text and f'{yr}.03.31' in text;unit='백만원' if mult==1000000 else '단위 : 원';assert unit in text
    facts.append(numeric_proof(p,token,[period,unit],metric,mult,pub,f'{yr}-01-01',f'{yr}-03-31',table_index=i))
  base.update({'year':e['year'],'basis':'CFS','quarter':'Q1','statement_table_index':i,'statement_context':context,'facts':facts,'revenue_YoY':float(number(rev[1])/number(rev[3])-1),'operating_profit_YoY':float(number(op[1])/number(op[3])-1),'first_earnings_release_verified':False,'surprise_comparator':'same-report prior-year comparator, not analyst consensus or prior guidance','prior_comparator_vintage':'As presented in THIS publication; not silently substituted into earlier events'})
  result['earnings'].append(base)
# Official US IR original pages, date provenance is dateline not current HTTP Last-Modified.
for name,pub,end in [('MSFT_2024Q3','2024-10-30','2024-09-30'),('MSFT_2024Q4','2025-01-29','2024-12-31')]:
 p=B/'sources'/name/'original.bin';doc=parse(p);text=p.read_bytes().decode('utf-8-sig');visible=clean(' '.join(doc.itertext()));facts=[];found=None
 for i,t in enumerate(doc.xpath('//table')):
  rows=cells(t);rev=[r for r in rows if r and r[0]=='Total revenue'];op=[r for r in rows if r and r[0]=='Operating income']
  if len(rev)==1 and len(op)==1:found=(i,rev[0],op[0]);break
 assert found
 i,rev,op=found;rev=[x for x in rev if x];op=[x for x in op if x]
 for metric,row in [('revenue',rev),('operating_profit',op)]:
  for yr,token in [(2024,row[1]),(2023,row[2])]:
   # Fiscal Q1 July-Sep, Q2 Oct-Dec; IR includes fiscal and calendar labels.
   start=f'{yr}-07-01' if 'Q3' in name else f'{yr}-10-01';stop=f'{yr}'+end[4:];month='September 30' if 'Q3' in name else 'December 31';unit='In millions';assert unit.lower() in visible.lower()
   # verifier anchors must be exact original fragments, not normalized invented text.
   anchors=[month,'millions'];assert all(x in text for x in anchors)
   facts.append(numeric_proof(p,token,anchors,metric,1000000,pub,start,stop,'USD',table_index=i))
 result['earnings'].append({'symbol':'MSFT','period_end':end,'publication_date':pub,'dateline_verified':(('October 30, 2024' in visible) if 'Q3' in name else 'January 29, 2025' in visible),'public_time_precision':'DATE_ONLY','source_path':str(p.relative_to(R)),'source_sha256':sha(p),'overall_PIT_grade':'PARTIAL','reason':'official IR historical page, original publication clock and immutable revision lineage not independently certified; SEC access blocked','facts':facts,'revenue_YoY':float(number(rev[1])/number(rev[2])-1),'operating_profit_YoY':float(number(op[1])/number(op[2])-1),'historical_execution':'NOT_ATTEMPTED','prior_comparator_vintage':'At event report; segment recasts not first-vintage prior-year information'})
# PDF uses preinstalled library from original quanta environment, no package installation.
sys.path.append('/home/ansy/app/quant-diligence/task6-quanta-env/lib/python3.12/site-packages')
from pypdf import PdfReader
for name,pub in [('PEP_2024Q3','2024-10-08'),('PEP_2024Q4','2025-02-04')]:
 p=B/'sources'/name/'original.bin'
 if not p.exists():result['earnings'].append({'symbol':'PEP','publication_date':pub,'status':'ORIGINAL_ACCESS_FAILED','overall_PIT_grade':'UNVERIFIED'});continue
 text='\n'.join(page.extract_text(extraction_mode='layout') or '' for page in PdfReader(io.BytesIO(p.read_bytes())).pages);(p.parent/'extracted.txt').write_text(text)
 result['earnings'].append({'symbol':'PEP','publication_date':pub,'status':'OFFICIAL_PDF_FETCHED','source_path':str(p.relative_to(R)),'source_sha256':sha(p),'text_sha256':sha(p.parent/'extracted.txt'),'dateline_verified':'October 8, 2024' in text,'overall_PIT_grade':'PARTIAL','reason':'PDF source/date preserved; no independent original clock/revision chain; units/GAAP/nonGAAP require explicit separate binding before numerical feature admission','numeric_feature_admitted':False})
for folder in sorted((B/'revision_audit').iterdir()):
 p=next(folder.glob('*.xml'));doc=parse(p);rows=[' '.join(r) for t in doc.xpath('//table') for r in cells(t)];selected=[r for r in rows if any(w in r for w in ['계약금액(원)','종료일','정정관련 공시서류','정정사유','정정일자'])];result['revision_audit'].append({'receipt_no':folder.name,'source_sha256':sha(p),'rows':selected,'not_used_in_initial_event':True})
# Cross-check early preliminary releases against later quarterly statements, preserving both vintages.
result['earlier_earnings_audit']=[]
for e in json.loads((B/'earlier_releases.json').read_text()):
 acc=e['filing']['rcept_no'];p=next((B/'earlier_earnings'/acc).glob('*.xml'));doc=parse(p);rows=[' '.join(r) for t in doc.xpath('//table') for r in cells(t)];year=int(e['filing']['rcept_dt'][:4]);quarter=next(x for x in result['earnings'] if x['symbol']==e['symbol'] and x.get('year')==year);matched={}
 for metric,label in [('revenue','매출액'),('operating_profit','영업이익')]:
  r=next(r for r in rows if r.startswith(label+' '));tokens=re.findall(r'(?<![\d.])\d{1,3}(?:,\d{3})+(?![\d.])',r);assert tokens;value=number(tokens[0])*1000000;fact=next(f for f in quarter['facts'] if f['metric']==metric and f['period_start'].startswith(str(year)));matched[metric]={'preliminary':str(value),'quarterly':fact['value'],'delta_KRW':str(Decimal(fact['value'])-value),'exact_match':value==Decimal(fact['value'])}
 d=e['filing']['rcept_dt'];d=d[:4]+'-'+d[4:6]+'-'+d[6:8];quarter['earlier_public_preliminary_release']=d
 result['earlier_earnings_audit'].append({'symbol':e['symbol'],'earlier_receipt':acc,'earlier_public_date':d,'quarterly_public_date':quarter['publication_date'],'preliminary_vs_quarterly':matched,'source_sha256':sha(p),'conclusion':'Quarterly report is not first earnings disclosure. Preserve any preliminary-to-quarterly change separately, never silently overwrite original. First clock still date-only.'})
receipts=[json.loads(p.read_text()) for p in (B/'sources').glob('*/receipt.json')];result['cost']={'python_HTTP_attempts':sum(len(d['attempts']) for d in receipts),'requests_saved':sum(d['status']=='SAVED' for d in receipts),'requests_failed':sum(d['status']=='FAILED' for d in receipts),'download_bytes':sum(d.get('bytes',0) for d in receipts),'wall_request_seconds':sum(a.get('elapsed_seconds',0) for d in receipts for a in d['attempts']),'money_cost':'No new paid service. Existing public API; billing unavailable.','LLM_calls':0,'LLM_tokens':0,'web_research_tool_calls':3,'web_commands':5}
result['economic_test']={'status':'INSUFFICIENT_EVIDENCE','contract_events':len(result['contracts']),'companies':len(set(x['symbol'] for x in result['contracts'])),'return_test':'NOT_RUN','future_price_requests':0,'reason':'Below pre-frozen30events/10companies. No return, backtest or alpha claim.'}
dump(B/'validation.json',result);print(json.dumps({'earnings_events':len(result['earnings']),'contracts':len(result['contracts']),'cost':result['cost']},ensure_ascii=False))

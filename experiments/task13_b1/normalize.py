"""Financial raw facts with original accessions, no forecasts, prices, imputation or training."""
from common import *
from decimal import Decimal,InvalidOperation
from lxml import html
from quant_harness.investment.financial_packet import verify_fact
from zoneinfo import ZoneInfo

def text(e):return ' '.join(' '.join(e.itertext()).split())
def doc(raw):return html.fromstring(raw,parser=html.HTMLParser(encoding='utf-8'))
def num(s):return Decimal(s.strip().replace(',','').replace('$','').replace('(','-').replace(')',''))
def upper(day,market):return datetime.datetime.fromisoformat(day+'T23:59:59').replace(tzinfo=ZoneInfo('America/New_York' if market=='US' else 'Asia/Seoul')).isoformat()
def select_fact(units,acc,end,duration=True):
 a=[(i,r) for i,r in enumerate(units) if r.get('accn')==acc and r.get('end')==end]
 if duration:a=[(i,r) for i,r in a if 'start'in r and 70<=(datetime.date.fromisoformat(end)-datetime.date.fromisoformat(r['start'])).days<=110]
 vals={r['val'] for i,r in a}
 if len(vals)!=1:return None
 return a[0] if a else None

def inline_values(raw):
 d=doc(raw);contexts={};out=[]
 for e in d.iter():
  if not isinstance(e.tag,str) or e.tag.lower().split(':')[-1]!='context':continue
  r={};dims=False
  for c in e.iter():
   k=c.tag.lower().split(':')[-1] if isinstance(c.tag,str) else ''
   if k in ['startdate','enddate','instant']:r[k]=text(c)
   if k in ['explicitmember','typedmember']:dims=True
  if not dims:contexts[e.get('id')]=r
 for e in d.iter():
  if not isinstance(e.tag,str) or e.tag.lower().split(':')[-1]!='nonfraction':continue
  context=contexts.get(e.get('contextref'));token=text(e)
  if context is None or not re.fullmatch(r'[$()\d,.\-]+',token):continue
  try:value=num(token)*(Decimal(10)**int(e.get('scale','0')))*(-1 if e.get('sign')=='-' else 1)
  except (InvalidOperation,ValueError):continue
  out.append({'name':e.get('name'),'period':context,'value':str(value),'unitref':e.get('unitref'),'xpath':e.getroottree().getpath(e),'scale':e.get('scale','0')})
 return out

def main():
 US=[]
 for row in json.loads((B/'US_collection.json').read_text()):
  base={'symbol':row['symbol'],'market':'US','CIK':row['cik'],'sector':row['sector'],'events':[],'status':'PARTIAL'}
  if not row.get('companyfacts_entity_verified'):US.append(base);continue
  meta=row['companyfacts'];raw=body(meta);cf=json.loads(raw);gaap=cf.get('facts',{}).get('us-gaap',{})
  tags={'revenue':['RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet','Revenues'],'operating_profit':['OperatingIncomeLoss'],'net_income':['NetIncomeLoss'],'cash':['CashAndCashEquivalentsAtCarryingValue'],'debt_component':['LongTermDebtNoncurrent','LongTermDebtCurrent'],'OCF_as_reported':['NetCashProvidedByUsedInOperatingActivities']}
  if row['symbol']=='JPM':tags={'net_interest_income':['InterestIncomeExpenseNet'],'cash':['CashAndCashEquivalentsAtCarryingValue'],'net_income':['NetIncomeLoss']}
  proof=[];original=row.get('original_quarter')
  if original and original['source']['status']=='SAVED':proof=inline_values(body(original['source']))
  for f in row['quarterly_filings']:
   period=f['reportDate'];facts=[]
   for metric,choices in tags.items():
    for tag in choices:
     unit='USD';arr=gaap.get(tag,{}).get('units',{}).get(unit,[])
     if metric=='OCF_as_reported':
      candidates=[(i,r) for i,r in enumerate(arr) if r.get('accn')==f['accessionNumber'] and r.get('end')==period and r.get('start')];pick=candidates[0] if len({r['val'] for i,r in candidates})==1 and candidates else None
     else:pick=select_fact(arr,f['accessionNumber'],period,duration=metric not in ['cash','debt_component'])
     if not pick:continue
     idx,r=pick;assert r.get('filed')==f['filingDate'],'FILING_DATE_IDENTITY_MISMATCH';start=r.get('start',period)
     fact={'metric':metric,'tag':tag,'raw_value':str(r['val']),'multiplier':1,'value':str(r['val']),'unit':'CURRENCY','currency':'USD','basis':'CFS','period_start':start,'period_end':period,'published':r['filed'],'source_hash':meta['source_hash'],'source_path':meta['storage_path'],'locator':{'kind':'json','path':['facts','us-gaap',tag,'units',unit,idx,'val']},'original_accession':r['accn'],'label':gaap[tag].get('label'),'duration_days':(datetime.date.fromisoformat(period)-datetime.date.fromisoformat(start)).days}
     fact=verify_fact(fact,raw,f['filingDate']);matching=[v for v in proof if v['name']=='us-gaap:'+tag and v['period'].get('enddate',v['period'].get('instant'))==period and v['period'].get('startdate',period)==start and Decimal(v['value'])==Decimal(fact['value'])];fact['inline_original_confirmed']=bool(matching) and original['filing']['accessionNumber']==f['accessionNumber'];fact['inline_proof']=matching[:1] if fact['inline_original_confirmed'] else []
     if fact['inline_original_confirmed']:fact['inline_source_hash']=original['source']['source_hash']
     facts.append(fact);break
   base['events'].append({'event_id':f['accessionNumber'],'event_type':f['form'],'source_filing':f,'published_date':f['filingDate'],'available_upper_bound':upper(f['filingDate'],'US'),'precision':'DATE_BOUND_CONSERVATIVE','acceptance_clock_raw':f.get('acceptanceDateTime'),'acceptance_timezone_independently_verified':False,'observed_at':meta['observed_at'],'facts':facts,'source_vintage':'each API fact matched to SAME original accession/filed/report period; no latest-value substitution','first_earnings_release':False,'missing':['Earlier earnings release may exist; 10-Q is not automatically first news','Debt component is not total debt; OCF duration preserved, not mechanically quarterised']})
  base['status']='SOURCE_LINKED' if base['events'] else 'PARTIAL_NO_TARGET_SUBMISSION_METADATA';US.append(base)
 dump(B/'US_fundamentals.json',US)

 # Reuse B0 verified financial records; same sources/hashes, preserve initial disclosure flags.
 old=json.loads((R/'runtime/task13_b0/validation.json').read_text());KR=[{**e,'market':'KR','precision':'DATE_ONLY','available_upper_bound':upper(e['publication_date'],'KR')} for e in old['earnings'] if e['symbol'] in ['011070','003230']]
 new=json.loads((B/'KR_collection.json').read_text())
 for row in new:
  if 'periods' not in row:continue
  for period in row['periods']:
   yr=period['year'];es=period.get('events',[]);pre=[e for e in es if '잠정' in e['filing']['report_nm']]
   for event in es:
    if not event['filing']['report_nm'].startswith('분기보고서') or event.get('status')!='ORIGINAL_FETCHED':continue
    accession=event['filing']['rcept_no'];p=next((B/'documents'/accession).glob('*.xml'));raw=p.read_bytes();d=doc(raw);found=None
    for idx,t in enumerate(d.xpath('//table')):
     prev=t.getprevious();ctx='' if prev is None else text(prev)
     if not('연결' in ctx and '손익계산서' in ctx and '단위' in ctx):continue
     rows=[[text(c) for c in r.xpath('./td|./th|./te|./tu')] for r in t.xpath('./tbody/tr|./tr|./thead/tr')];rev=[r for r in rows if r and re.match(r'^매출(?:액)?(?:\s|$)',r[0]) and len(r)==5];op=[r for r in rows if r and re.match(r'^영업이익(?:\s|$)',r[0]) and len(r)==5]
     if len(rev)==len(op)==1:found=(t,idx,ctx,rev[0],op[0]);break
    if found is None:KR.append({'symbol':row['symbol'],'year':yr,'market':'KR','status':'CFS_EXTRACTION_PARTIAL','receipt_no':accession});continue
    t,idx,ctx,rev,op=found;mult=1000000 if '백만원' in ctx else 1;assert mult!=1 or '단위 : 원' in ctx;pub=event['filing']['rcept_dt'];pub=pub[:4]+'-'+pub[4:6]+'-'+pub[6:8];facts=[];rawtext=raw.decode();offset=sum(len(s) for s in rawtext.splitlines(keepends=True)[:t.sourceline-1]);end=re.search(r'</table\s*>',rawtext[offset:],re.I);assert end
    for metric,values in [('revenue',rev),('operating_profit',op)]:
     assert values[1]==values[2] and values[3]==values[4]
     for year,token in [(yr,values[1]),(yr-1,values[3])]:
      at=rawtext.find(token,offset,offset+end.end());assert at>=0;unit='백만원' if mult==1000000 else '단위 : 원';assert f'{year}.01.01' in ctx and f'{year}.03.31' in ctx
      a=max(offset,at-40);quote=rawtext[a:at+len(token)+40];fact={'metric':metric,'raw_value':token,'multiplier':mult,'value':str(num(token)*mult),'unit':'CURRENCY','currency':'KRW','basis':'CFS','period_start':f'{year}-01-01','period_end':f'{year}-03-31','published':pub,'source_hash':sha(p),'source_path':str(p.relative_to(R)),'locator':{'kind':'text','start':a,'end':a+len(quote),'quote':quote,'context_anchors':[f'{year}.01.01',unit]},'table_index':idx};facts.append(verify_fact(fact,raw,pub))
    KR.append({'symbol':row['symbol'],'market':'KR','year':yr,'publication_date':pub,'receipt_no':accession,'available_upper_bound':upper(pub,'KR'),'precision':'DATE_BOUND_CONSERVATIVE','facts':facts,'earlier_preliminary_receipts':[e['filing'] for e in pre],'first_earnings_release':False,'observed_at':event['source'].get('observed_at'),'first_vs_final_not_merged':True})
 dump(B/'KR_fundamentals.json',KR)
 # Company access != homogeneous industrial factor readiness.
 result={'US_companies':len(US),'US_quarter_events':sum(len(x['events']) for x in US),'US_facts':sum(len(e['facts']) for x in US for e in x['events']),'US_inline_facts':sum(f['inline_original_confirmed'] for x in US for e in x['events'] for f in e['facts']),'KR_earnings_events':len(KR),'KR_facts':sum(len(e.get('facts',[])) for e in KR),'KR_contract_companies':2,'prices_accessed':False};dump(B/'normalization_summary.json',result);print(result)

if __name__=="__main__":main()

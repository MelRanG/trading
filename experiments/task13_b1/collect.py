"""Frozen6+6 issuer panel and three macro indicators, no model/price calls."""
from common import *
import io,zipfile
from lxml import html
s=Sources();US=[];KR=[]
# Validate issuer identity from existing catalog BEFORE any KR request.
cat=json.loads((R/'runtime/task8b/discovery/kr_catalog.json').read_text())['rows'];corrections=[]
for x in P['KR']:
 mapped=next(r for r in cat if r['stock_code']==x['symbol'])
 if mapped['corp_code']!=x['corp_code']:corrections.append({'symbol':x['symbol'],'declared':x['corp_code'],'correct':mapped['corp_code'],'basis':'existing catalog + B0/Task9 identity, before first request','catalog_sha256':sha(R/'runtime/task8b/discovery/kr_catalog.json')})
dump(B/'identity_amendment_before_collection.json',corrections)
for x in P['US']:
 symbol=x['symbol'];cik=x['cik'];row={**x,'status':'PARTIAL'}
 for kind in ['submissions','companyfacts']:
  url=f'https://data.sec.gov/submissions/CIK{cik}.json' if kind=='submissions' else f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json';raw,meta=s.get(symbol+'_'+kind,url,fresh=symbol=='MSFT');row[kind]=meta
  if raw is None:continue
  d=json.loads(raw);assert int(d['cik'])==int(cik);row[kind+'_entity_verified']=True
 if not row.get('submissions_entity_verified'):US.append(row);continue
 sub=json.loads(body(row['submissions']));recent=sub['filings']['recent']
 def records(a):return [{k:v[i] for k,v in a.items()} for i in range(len(a['accessionNumber']))]
 filings=records(recent)
 if not any(f['filingDate'][:4]=='2024' and f['form']=='10-Q' for f in filings):
  hist=next((f for f in sub['filings'].get('files',[]) if f['filingFrom']<='2025-06-30' and f['filingTo']>='2024-01-01'),None)
  if hist:
   raw,meta=s.get(symbol+'_historical_submissions','https://data.sec.gov/submissions/'+hist['name']);row['history']=meta
   if raw:filings+=records(json.loads(raw))
 selected=[]
 for year in [2024,2025]:
  targets=[f for f in filings if f['form']=='10-Q' and f.get('reportDate','').startswith(str(year)) and '01-01'<=f.get('reportDate','')[5:]<='03-31']
  if symbol=='DECK':targets=[f for f in filings if f['form']=='10-Q' and f.get('reportDate')==f'{year-1}-12-31']
  if targets:selected.append(sorted(targets,key=lambda f:f['filingDate'])[0])
 row['quarterly_filings']=selected
 # One original quarterly statement per company, newer predefined period, no price-based choice.
 if selected:
  f=selected[-1];base=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{f['accessionNumber'].replace('-','')}/";raw,meta=s.get(symbol+'_quarter_original',base+f['primaryDocument']);row['original_quarter']={'filing':f,'source':meta}
 # Fixed PEP earnings releases to validate same-FY guidance revision, not ad hoc screening.
 if symbol=='PEP':
  releases=[]
  for day in ['2024-07-11','2024-10-08']:
   matches=[f for f in filings if f['form']=='8-K' and f['filingDate']==day and '2.02' in f.get('items','')]
   if not matches:releases.append({'date':day,'status':'MISSING_METADATA'});continue
   f=sorted(matches,key=lambda f:f['accessionNumber'])[0];base=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{f['accessionNumber'].replace('-','')}/";raw,meta=s.get('PEP_8K_'+day,base+f['primaryDocument']);item={'date':day,'filing':f,'primary':meta}
   if raw:
    doc=html.fromstring(raw);links=[a.get('href') for a in doc.xpath('//a[@href]') if re.search(r'(99[._-]?1|exhibit991)',a.get('href',''),re.I)]
    # Native exhibit label, not an invented accession/URL; avoid XBRL viewer wrappers.
    links=[v for v in links if v and not v.startswith('#')];item['exhibit_links']=links
    if links:
     from urllib.parse import urljoin
     link=next((v for v in links if v.endswith(('.htm','.html','.pdf'))),links[0]);r,m=s.get('PEP_earnings_'+day,urljoin(base,link));item['exhibit']=m
   releases.append(item)
  row['earnings_releases']=releases
 row['status']='COLLECTED' if row.get('companyfacts_entity_verified') else 'PARTIAL';US.append(row);dump(B/'US_collection.json',US);print(symbol,row['status'],len(selected),flush=True)
# Existing B0 raw/parsed documents reused, not copied/re-downloaded.
old=json.loads((R/'runtime/task13_b0/validation.json').read_text());dump(B/'B0_references.json',{'path':'runtime/task13_b0/validation.json','sha256':sha(R/'runtime/task13_b0/validation.json'),'symbols':['011070','003230','028050','064350'],'first_vintages_and_corrections_kept_separate':True})
for x in P['KR']:
 if x['symbol'] in ['011070','003230','028050','064350']:KR.append({**x,'status':'B0_REFERENCED'});continue
 corp=next(r['corp_code'] for r in cat if r['stock_code']==x['symbol']);row={**x,'corp_code':corp,'periods':[]}
 for year in [2024,2025]:
  params={'corp_code':corp,'bgn_de':f'{year}0401','end_de':f'{year}0630','last_reprt_at':'N','page_no':1,'page_count':100,'sort':'date','sort_mth':'asc'};d,meta=s.dart(f"{x['symbol']}_{year}_list",'list.json',params);period={'year':year,'list_source':meta}
  if d is not None:
   rows=d.get('list',[]);period.update(filings=rows,page_complete=len(rows)==d.get('total_count',len(rows)))
   q=[r for r in rows if r['report_nm'].strip().startswith('분기보고서') and f'{year}.03' in r['report_nm']];pre=[r for r in rows if '잠정' in r['report_nm'] and '실적' in r['report_nm']]
   chosen=pre[:1]+q[:1];period['events']=[]
   for f in chosen:
    raw,m=s.dart('KR_doc_'+f['rcept_no'],'document.xml',{'rcept_no':f['rcept_no']});item={'filing':f,'source':m}
    if raw:
     try:
      with zipfile.ZipFile(io.BytesIO(raw)) as z:
       files=[n for n in z.namelist() if n.endswith('.xml')];assert files;folder=B/'documents'/f['rcept_no'];folder.mkdir(parents=True,exist_ok=True)
       for n in files:(folder/Path(n).name).write_bytes(z.read(n))
      item['xml_files']=files;item['status']='ORIGINAL_FETCHED'
     except Exception as e:item.update(status='INVALID_ORIGINAL',error_type=type(e).__name__)
    period['events'].append(item)
  row['periods'].append(period)
 KR.append(row);dump(B/'KR_collection.json',KR);print(x['symbol'],'KR_COLLECTED',flush=True)
macro=[]
for day in ['20240612','20240918']:
 u=f'https://www.federalreserve.gov/newsevents/pressreleases/monetary{day}a.htm';raw,m=s.get('FOMC_'+day,u);macro.append({'kind':'FOMC_TARGET_RATE','date':day,'source':m})
for sid in ['DGS10','BAMLH0A0HYM2']:
 u='https://fred.stlouisfed.org/graph/fredgraph.csv?id='+sid+'&cosd=2024-06-01&coed=2025-06-30';raw,m=s.get(sid,u);macro.append({'kind':sid,'source':m,'PIT':'PARTIAL_LATEST_BACKFILL_NO_VINTAGE_API_KEY'})
dump(B/'macro_collection.json',macro);print('COLLECTION_COMPLETE',len(list((B/'requests').glob('*.json'))),flush=True)

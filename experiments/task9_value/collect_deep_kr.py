from pathlib import Path
import sys,json,zipfile,io,re,hashlib
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));sys.path.insert(0,str(R/'experiments/task9_historical'))
from original_parser import text_and_identity
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);client=OpenDartClient();B=R/'runtime/task9_value';W=Path('/home/ansy/app/quant-diligence/task9-value-work');catalog=json.loads((R/'runtime/task8b/discovery/kr_catalog.json').read_text())['rows']
def saved(folder,name,endpoint,params,binary=False):
 p=folder/name
 if p.exists():return p.read_bytes() if binary else json.loads(p.read_text())
 x=client._request(endpoint,params,binary=binary);p.write_bytes(x if binary else json.dumps(x,ensure_ascii=False).encode());return x
for file in sorted(W.glob('screen_*.json')):
 if '.request.' in file.name:continue
 screen=json.loads(file.read_text());year=int(file.stem[-4:]);date=str(year)+'-11-30'
 for c in screen['research_priorities']:
  if c['market']!='KR':continue
  s=c['symbol'];folder=B/'deep'/str(year)/s;folder.mkdir(parents=True,exist_ok=True)
  if (folder/'source_packet.json').exists():continue
  try:
   native=s.split('.')[0];matches=[x for x in catalog if x['stock_code']==native];assert len(matches)==1;corp=matches[0]['corp_code']
   listing=saved(folder,'list.json','list.json',{'corp_code':corp,'bgn_de':str(year)+'0901','end_de':str(year)+'1130','pblntf_ty':'A','page_count':100,'sort':'date','sort_mth':'desc','last_reprt_at':'N'})
   rows=[r for r in listing.get('list',[]) if '분기보고서' in r['report_nm'] and str(year)+'.09' in r['report_nm'] and '[' not in r['report_nm']];assert rows
   row=rows[0];raw=saved(folder,'original.zip','document.xml',{'rcept_no':row['rcept_no']},True);texts=[];ids=[]
   for name in zipfile.ZipFile(io.BytesIO(raw)).namelist():
    if name.lower().endswith('.xml'):
     t,i=text_and_identity(zipfile.ZipFile(io.BytesIO(raw)).read(name));texts.append(t);ids.append(i)
   text='\n'.join(texts);(folder/'original.txt').write_text(text);parts=[]
   for label,pattern,size in [('business',r'II\. 사업의 내용',1700),('financial_summary',r'1\. 요약재무정보',2400),('cashflow',r'연결 현금흐름표',1400),('shares',r'4\. 주식의 총수',900)]:
    ms=list(re.finditer(pattern,text))
    if ms:
     start=ms[-1].start() if label!='cashflow' else ms[0].start();parts.append({'label':label,'start':start,'text':text[start:start+size]})
   api=saved(folder,'accounts.json','fnlttSinglAcntAll.json',{'corp_code':corp,'bsns_year':str(year),'reprt_code':'11014','fs_div':'CFS'});ar=api.get('list',[]);accepted=bool(ar) and all(r['rcept_no']==row['rcept_no'] for r in ar)
   needles=['Revenue','ProfitLoss','OperatingIncomeLoss','CashFlowsFromUsedInOperating','CashAndCashEquivalent','Assets','Liabilities','Equity','Borrowing','Debt','IssuedCapital']
   facts=[{k:r.get(k) for k in ['account_id','account_nm','sj_div','thstrm_nm','thstrm_amount','thstrm_add_amount','frmtrm_nm','frmtrm_amount','frmtrm_add_amount','currency']} for r in ar if any(n in r.get('account_id','') for n in needles)][:32] if accepted else []
   result={'symbol':s,'market':'KR','source_id':'DART_'+row['rcept_no'],'source_url':'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+row['rcept_no'],'published':row['rcept_dt'],'report':row['report_nm'],'original_identity':ids,'excerpts':parts,'accounts':facts,'API_matches_original_accession':accepted,'quarter_warning':'IS thstrm_amount can be Q3 only; thstrm_add_amount is YTD. Units KRW unless stated in original. Original excerpts may use million KRW; never mix.','quality':'PARTIAL_PIT_ORIGINAL_ACCESSION','raw_sha256':hashlib.sha256(raw).hexdigest()}
   (folder/'source_packet.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(year,s,'SAVED',row['rcept_no'],accepted,len(facts),flush=True)
  except Exception as e:(folder/'failure.json').write_text(json.dumps({'error_type':type(e).__name__}));print(year,s,type(e).__name__,flush=True)

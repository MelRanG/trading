from pathlib import Path
import json,sys,re,hashlib
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_historical';W=Path('/home/ansy/app/quant-diligence/task9-historical-work');sys.path.insert(0,str(Path(__file__).parent));from replay_contract import score_forecast
pred=json.loads((W/'A2_202411.json').read_text());results=[]
for c in pred['candidates']:
 if not c.get('forecasts'):continue
 folder=B/'evaluator_only'/c['accession'];meta=json.loads((folder/'status.json').read_text());text=(folder/'original.txt').read_text();original=meta['original_report'];date=original['rcept_dt'];published=date[:4]+'-'+date[4:6]+'-'+date[6:]+'T15:00:00Z';source_hash=json.loads((folder/'api_original.receipt.json').read_text())['source_hash']
 for f in c['forecasts']:
  if c['accession']=='20241101000134':
   # Exact original summary, not an inferred substitute for the empty CFS API.
   start=text.index('1. 요약재무정보');end=text.index('2. 연결재무제표',start);summary=text[start:end];assert '(단위 : 천원)' in summary and '2025.01.01~ 2025.12.31' in summary
   label='매출액' if f['metric']=='revenue' else '영업이익';m=re.search(r'(?:^|\n)'+label+r'\n([\d,]+)\n',summary);assert m
   value=int(m.group(1).replace(',',''))/1000;extraction={'method':'Audited original summary first2025column','unit':'KRW_thousand_to_million','rounding_million':.001,'quote':m.group(0),'CFS_api_status':'013_NOT_SUBSTITUTED_WITH_FAKE_API_SUCCESS'}
  else:
   api=json.loads((folder/'api_statement.json').read_text());tag={'revenue':'ifrs-full_Revenue','operating_profit':'dart_OperatingIncomeLoss'}[f['metric']];rows=[r for r in api['list'] if r['account_id']==tag and r['sj_div'] in ('IS','CIS')];assert len(rows)==1 and meta['original_accession_match'];row=rows[0];assert row['currency']=='KRW' and row['bsns_year']=='2025';amount=int(row['thstrm_amount'].replace(',',''));assert format(amount,',') in text;value=amount/1000000;extraction={'method':'Original accession-matched CFS API cross-checked in original text','unit':'KRW_to_million'}
  actual={'company_id':meta['company_id'],'metric':f['metric'],'period_start':'2025-01-01','fiscal_end':'2025-12-31','unit':'KRW_million','value':value,'published_at':published,'source_hash':source_hash,'original_version':True};score=score_forecast({**f,'company_id':meta['company_id']},actual,'2024-11-30T23:59:59Z','2026-11-14T00:00:00Z')
  naive=None
  if f['metric']=='revenue':
   anchor=137986 if c['accession']=='20241101000134' else 185645.920315;naive={'base':anchor*4/3,'relative_absolute_error':abs(anchor*4/3-value)/abs(value),'basis':'Same original9months annualized, not company guidance'}
  results.append({'company':c['original_company'],'forecast_accession':c['accession'],'prediction':f,'actual':actual,'extraction':extraction,'score':score,'naive_annualization':naive})
(B/'evaluation/additional_forecast_scores.json').write_text(json.dumps({'scope':'Exploratory historical scenario checks, not independent predictive ability','results':results},ensure_ascii=False,indent=2));print(json.dumps([(r['company'],r['prediction']['metric'],r['actual']['value'],r['score']['relative_absolute_error']) for r in results],ensure_ascii=False))

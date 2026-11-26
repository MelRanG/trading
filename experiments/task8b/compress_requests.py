from pathlib import Path
import json,re,shutil
w=Path('/home/ansy/app/quant-diligence/task8b-vibe-work')
for i in [1,2,3]:
 p=w/('analysis'+str(i)+'.request.json');request=json.loads(p.read_text());text=request['messages'][1]['content'];head,raw=text.split('Frozen source cases:\n',1);cases=json.loads(raw)
 for c in cases:
  for s in c['sources']:
   data=s.get('data')
   if not isinstance(data,dict) or 'rows' not in data:continue
   if '_shares' in s['source_id']:continue
   rows=data['rows'];patterns=r'매출|수익\(매출액\)|영업수익|영업이익|당기순|반기순|지배기업.*순|기본주당|희석주당|현금및|현금 및|자산총계|부채총계|자본총계|지배기업.*지분|차입금|사채|리스부채|영업활동.*현금|유형자산.*취득|무형자산.*취득'
   chosen=[r for r in rows if re.search(patterns,r.get('account_nm','')) and (r.get('sj_div') not in ['IS','CIS'] or not any(x in r.get('account_nm','') for x in ['기타포괄','총포괄','관계기업']))]
   data['rows']=[{k:v for k,v in r.items() if k in ['account_nm','account_id','sj_div','currency','thstrm_nm','thstrm_amount','thstrm_add_amount','frmtrm_amount','frmtrm_add_amount']} for r in chosen]
 request['messages'][1]['content']=head+'Frozen source cases:\n'+json.dumps(cases,ensure_ascii=False)
 shutil.copy2(p,w/(p.stem+'.preflight.json'));p.write_text(json.dumps(request,ensure_ascii=False));print(p.name,len(json.dumps(request)),p.stat().st_size)

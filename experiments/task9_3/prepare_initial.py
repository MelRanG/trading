from common import *
import re,shutil
from decimal import Decimal
from quant_harness.investment.financial_packet import verify_fact,model_numeric_view
W=Path('/home/ansy/app/quant-diligence/task9-3-work');K=Path('/home/ansy/app/quant-diligence/vibe-original/agent/src/skills')
def typed(p,metric,token,scale,unit,pub,end,anchor,occ=0):
 t=p.read_text();start=list(re.finditer(re.escape(anchor),t))[occ].start();pos=t.index(token,start);f={'metric':metric,'raw_value':token,'value':str(Decimal(token.replace(',',''))*Decimal(str(scale))),'multiplier':scale,'unit':unit,'currency':'USD','basis':'CFS','period_start':end if metric in ['cash','debt'] else '2026-01-01','period_end':end,'published':pub,'source_hash':sha(p),'source_path':str(p.relative_to(R)),'locator':{'kind':'text','start':max(start,pos-40),'end':pos+len(token)+40,'quote':t[max(start,pos-40):pos+len(token)+40],'context_anchors':[('2026'),('millions' if scale==1000000 else 'THOUSANDS')]}}
 return verify_fact(f,p.read_bytes(),'2026-05-15')
for market in (sys.argv[1:] or ['US','KR']):
 src=W/('discover_US.json' if market=='US' else 'discover_KR_v2.json')
 if not src.exists():continue
 discovery=json.loads(src.read_text());freeze(B/'discovery'/f'{market}_model.json',discovery);screens=json.loads((B/'screens'/f'{market}.json').read_text());cases=[]
 for d in discovery['deep']:
  x=next(x for x in screens if x['symbol']==d['symbol']);s=x['symbol'];case={**d,'market':market,'asof':'2026-05-15','price':x['price'],'momentum63':x['momentum63'],'vol63':x['vol63'],'adv20':x['adv20'],'source_documents':[],'verified_facts':x.get('financial_facts',[]),'source_gaps':[]}
  for rp in (B/'primary'/s).glob('*/receipt.json'):
   r=json.loads(rp.read_text())
   if r['status']!='SAVED':case['source_gaps'].append(r);continue
   p=rp.with_name('normalized.txt')
   if not p.exists():
    p.write_text('\n'.join(re.sub(r'[ \t\xa0]+',' ',line).strip() for line in rp.with_name('original.txt').read_text().splitlines() if line.strip()))
   t=p.read_text();pub=r['published'];pub=pub[:4]+'-'+pub[4:6]+'-'+pub[6:8] if '-' not in pub else pub;assert pub<='2026-05-14'
   if market=='US':
    if s=='VRT':start=t.index('Apr 22, 2026');end=t.find('SOURCE Vertiv');body=t[start:end if end>start else len(t)]
    elif s=='SFM':start=t.index('April 29, 2026');end=t.find('Investor Contacts',start);body=t[start:end if end>start else len(t)]
    else:body=t
    # Complete numeric tables retained, not prefix-truncated.
    case['source_documents'].append({'published':pub,'source_hash':sha(p),'raw_hash':r['raw_sha256'],'text':body,'source_path':str(p.relative_to(R))})
   else:
    spans=[]
    for pat,n in [(r'II\. 사업의 내용',6500),(r'주요 제품 및 서비스',3500),(r'매출 및 수주상황',4000),(r'연결 현금흐름표',5000)]:
     ms=list(re.finditer(pat,t))
     if ms:spans.append(t[ms[-1].start():ms[-1].start()+n])
    case['source_documents'].append({'published':pub,'source_hash':sha(p),'raw_hash':r['raw_sha256'],'text':'\n'.join(spans),'source_path':str(p.relative_to(R))})
   if market=='US' and s in ['VRT','SFM']:
    end='2026-03-31' if s=='VRT' else '2026-03-29';scale=1000000 if s=='VRT' else 1000
    plan=[('revenue','2,649.5','CURRENCY','CONSOLIDATED STATEMENTS'),('cash','2,150.6','CURRENCY','CONSOLIDATED BALANCE'),('debt','2,922.2','CURRENCY','Long-term debt, net'),('operating_cashflow','766.8','CURRENCY','Net cash provided by'),('capex_outflow','112.6','CURRENCY','Capital expenditures')] if s=='VRT' else [('revenue','2,329,179','CURRENCY','CONSOLIDATED STATEMENTS'),('operating_income','215,307','CURRENCY','Income from operations'),('cash','252,161','CURRENCY','CONSOLIDATED BALANCE'),('finance_obligations_longterm','97,044','CURRENCY','Long-term debt and other'),('diluted_average_shares','95,585','SHARES','Diluted')]
    for metric,token,unit,a in plan:case['verified_facts'].append(typed(p,metric,token,scale,unit,pub,end,a))
  if market=='KR':
   p=B/'screen_inputs'/s/'shares.json';z=json.loads(p.read_text())
   for i,r in enumerate(z.get('list',[])):
    if r.get('se') not in ['보통주','보통주식'] or r.get('rcept_no','9999')[:8]>'20260514':continue
    pub=r['rcept_no'];pub=pub[:4]+'-'+pub[4:6]+'-'+pub[6:8]
    f={'metric':'issued_common','raw_value':r['istc_totqy'],'value':r['istc_totqy'].replace(',',''),'multiplier':1,'unit':'SHARES','currency':'KRW','basis':'SFS','period_start':'2026-03-31','period_end':'2026-03-31','published':pub,'source_hash':sha(p),'source_path':str(p.relative_to(R)),'locator':{'kind':'json','path':['list',i,'istc_totqy']}};case['verified_facts'].append(verify_fact(f,p.read_bytes(),'2026-05-15'))
  cases.append(case)
 packet={'asof':'2026-05-15','market':market,'cases':cases,'candidate_screen_hash':sha(B/'screens'/f'{market}.json'),'discovery_hash':sha(B/'discovery'/f'{market}_model.json'),'risk':C['risk'],'initial_capital':C['capital'][market],'quant_origin':'MOM63_CAUSAL_REFERENCE_NOT_QUANTA_RD_ALPHA','pit':'Re-downloaded dated primary documents; same-day filings excluded. Historicaldiagnostic, LLMoutcomememoryunremovable.'}
 freeze(B/'packets'/market/'2026-05-15.json',packet)
 print(market,'CASES',len(cases),'chars',len(json.dumps(packet,ensure_ascii=False)),flush=True)

"""Frozen masked inputs; no evaluation prices/performance/2022 accounts in worker."""
from pathlib import Path
import json,hashlib,re,sys
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_completion';W=Path('/home/ansy/app/quant-diligence/task9-completion-work');W.mkdir(exist_ok=True);(W/'home').mkdir(exist_ok=True)
mode=sys.argv[1];assert mode in ('A','B','C')
qualified=json.loads((B/'qualified/manifest.json').read_text());policy=json.loads((Path(__file__).parent/'bounded_pilot_contract_v2.json').read_text());foundation={'cutoff':policy['information_cutoff'],'mode':'EXPLORATORY_RESEARCH_SHADOW_NOT_OFFICIAL_PAPER','holding_sessions':63,'cap_floor':json.loads((Path(__file__).parent/'market_cap_contract.json').read_text()),'cases':[]}
text=(R/'runtime/task9_historical/originals/20211101000287/original.txt').read_text();sections=[]
for pattern,size,label in [(r'4\. 주식의 총수',1600,'shares'),(r'II\. 사업의 내용',4200,'business'),(r'1\. 요약재무정보',2900,'financial'),(r'연결 현금흐름표',2300,'cashflow')]:
 matches=list(re.finditer(pattern,text))
 if matches:
  start=matches[-1].start() if label!='cashflow' else matches[0].start();sections.append({'label':label,'source_id':'20211101000287','start':start,'text':text[start:start+size]})
for q in qualified['qualified']:
 c={k:q[k] for k in ('market','symbol','currency','reference_price','shares_proxy','cap_proxy','floor')};c['data_status']='Bounded reconstruction, not complete market PIT; no empirically observed spread; official strategy remains unapproved';c['tradable_for_research_probe']=True
 if q['market']=='KR':c.update(company='SOLUM',sources=sections,share_note='Q3 original50,005,551 common shares; not stale API49,092,219; later dilution scenario uncertain',funding_note='OriginalQ3 reports large negative CFO/inventory build. Do not ignore working-capital funding or infer revenue growth is equity upside.')
 else:c.update(company='onsemi',sources=[json.loads((B/'us/ON/primary_search_extract.json').read_text())])
 foundation['cases'].append(c)
market=json.loads((R/'runtime/task9_historical/packets/shared_session_B.json').read_text())['market'];market={k:v for k,v in market.items() if k!='index_price_history_through_cutoff'}
import pandas as pd
market['observed_history']={}
for q in qualified['qualified']:
 f=pd.read_csv(B/'qualified'/(q['market']+'_raw_prices.csv'));f=f[f.date<='2021-11-30'].tail(65);market['observed_history'][q['symbol']]=f[['date','close','volume']].to_dict('records')
common={'foundation':foundation,'market_context':market,'risk_cost_policy':policy};session_hash=hashlib.sha256(json.dumps(common,sort_keys=True,ensure_ascii=False).encode()).hexdigest();foundation_hash=hashlib.sha256(json.dumps(foundation,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
example={'mode':mode,'session_input_hash':session_hash,'foundation_hash':foundation_hash,'decisions':[{'market':'KR','symbol':'248070.KS','action':'PROBE or WAIT or REJECT','weight':0,'thesis':'source-backed conditional investment hypothesis','forecasts':{'revenue_bear_base_bull':None,'net_income_bear_base_bull':None,'unit':'million local currency','forecast_period':'explicit, no pretending guidance is independent'},'valuation':{'method':'EPS_PE or explicit FCFF-to-equity','bear_price':None,'base_price':None,'bull_price':None,'horizon':'explicit','assumptions':[],'net_debt_and_dilution_caveats':[]},'catalysts':[],'counterargument':'','falsification':[],'decision_change_from_previous':[],'why_probe_or_wait':'','evidence_ids':[]}],'incomplete_competitors':[],'what_information_changed_decision':[],'alpha_proven':False,'memory_contamination_risk':True}
system='''You are the original pinned Vibe ChatLLM investment research component. Use only the supplied pre-cutoff information; no tools, web, files, memory or future outcomes. Evaluate KR and US in separate currency accounts. This is a bounded historical exploratory SHADOW, not a validated trading strategy, official Paper eligibility or a clean prediction test. You may choose a small2.5% probe ONLY for a source-backed falsifiable thesis with sufficient economic rationale despite unproven alpha; otherwise WAIT. Never force a purchase just to make a demo. Price eligibility has been checked externally within declared limited scope; do not reset weights to zero merely because large-sample alpha is unproven. Corporate-action audits/2022 operating outcomes were withheld. Identify material risks and conditional price scenarios with explicit margins, earnings, multiples, shares, debt/dilution. Do not equate growth with investment attractiveness or invent consensus/probabilities. EPS valuation is already equity; do not subtract debt again. Output JSON only.'''
user={'task':{'A':'Independent company-value research and conditional valuation; no market add-on or relative ranking yet','B':'Preserve A operating research; add only supplied dated macro, past prices and catalyst interpretation. Explain actual changes','C':'Preserve B, compare cash and the same constrained alternatives. No new hindsight winner. Explain whether relative comparison changes research allocation'}[mode],'foundation':foundation,'risk_cost_policy':policy,'output_schema_example':example,'session_input_hash':session_hash,'foundation_hash':foundation_hash}
if mode!='A':user['market_context']=market;user['original_A']=json.loads((W/'A.json').read_text())
if mode=='C':user['previous_B']=json.loads((W/'B.json').read_text());user['fixed_exclusions']=qualified['excluded']
request={'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(user,ensure_ascii=False)}],'temperature':0,'response_format':{'type':'json_object'}}
p=W/(mode+'.request.json')
if p.exists():assert json.loads(p.read_text())==request
else:p.write_text(json.dumps(request,ensure_ascii=False))
(B/'research_inputs').mkdir(exist_ok=True);(B/'research_inputs'/('common_'+mode+'.json')).write_text(json.dumps(common,ensure_ascii=False,indent=2));print(mode,session_hash,len(json.dumps(request)))

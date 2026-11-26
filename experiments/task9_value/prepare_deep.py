from pathlib import Path
import json,hashlib,pandas as pd
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_value';W=Path('/home/ansy/app/quant-diligence/task9-value-work');V=Path('/home/ansy/app/quant-diligence/vibe-original/agent/src/skills');contract=json.loads((Path(__file__).parent/'contract.json').read_text());(B/'deep_inputs').mkdir(exist_ok=True)
skills={name:(V/name/'SKILL.md').read_text()[:1800] for name in ['earnings-forecast','valuation-model','sector-rotation','macro-analysis']}
for year in [2021,2022,2023]:
 date=str(year)+'-11-30';screen=json.loads((W/('screen_'+str(year)+'.json')).read_text());pack=json.loads((B/'screen_inputs'/('screen_'+str(year)+'.json')).read_text());cases=[]
 for c in screen['research_priorities']:
  s=c['symbol'];folder=B/'deep'/str(year)/s;p=folder/('source_packet_v2.json' if c['market']=='KR' else 'source_packet.json');source=json.loads(p.read_text());ref=json.loads((folder/'reference.json').read_text());assert ref['status']=='PROVIDER_RAW_REFERENCE' and str(source['published']).replace('-','')<=str(year)+'1130'
  f=pd.read_csv(B/'prices'/s/'bars.csv');z=f[f.date==date];assert len(z)==1;ratio=float(z.close.iloc[0])/ref['reference_price'];assert abs(ratio-1)<.005,'raw unit mismatch requires source audit before model'
  for part in source['excerpts']:
   part['text']=part['text'][:(8000 if c['market']=='US' else (1000 if part['label']=='business' else 2400))]
  cases.append({'candidate':next(x for x in pack['candidates'] if x['symbol']==s),'research_priority':c,'reference':ref,'source':source,'price_unit_crosscheck_ratio':ratio})
 macro=[json.loads((B/'macro'/(str(year)+'.json')).read_text())]
 if year==2021:
  old=json.loads((B/'macro/BOK_2021_existing.json').read_text());macro.append({'source_id':'BOK_20211125_EXISTING_EXTRACT','text':str(old.get('bok_20211125',old))[:6000],'scope':'existing dated historical packet; no future outcome'})
 else:macro.append(json.loads((B/'macro'/('BOK_'+str(year)+'.json')).read_text()))
 if year==2022:macro.append(json.loads((B/'macro/POWELL_2022.json').read_text()))
 # Restrict long speeches; retain the key final policy discussion separately.
 for m in macro:
  if isinstance(m.get('text'),str) and len(m['text'])>7000:m['text']=m['text'][:4000]+'\n[bounded excerpt omitted]\n'+m['text'][-2500:]
 sectors={}
 for market in ['US','KR']:
  for sec in sorted({x['sector'] for x in pack['candidates'] if x['market']==market}):
   vals=[x.get('past_price_returns',{}).get('63') for x in pack['candidates'] if x['market']==market and x['sector']==sec];vals=[v for v in vals if v is not None]
   sectors[market+':'+sec]={'median_past63_price_return':float(pd.Series(vals).median()) if vals else None,'sample_names':len(vals),'quality':'limited cohort proxy, not official sector index or capital flows'}
 payload={'cutoff':date+'T23:00:00Z','cases':cases,'macro':macro,'sector_context':sectors,'original_vibe_skill_methods':skills,'risk_policy':contract,'research_horizon':'3/6/12calendar months after next market session open','missing_context':'No verified full consensus history, institutional net flows or ETF flows. Do not invent them. Source guidance is issuer forecast, not independent prediction.'}
 fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest();payload['session_input_hash']=fingerprint
 schema={'cutoff':payload['cutoff'],'session_input_hash':fingerprint,'companies':[{'market':'US or KR','symbol':'provided','source_ids':[],'evidence_backed_thesis':'','missing_evidence':[],'forecast':{'fiscal_year':year+1,'metric':'diluted_EPS OR consolidated_revenue','unit':'USD/share or KRW/share or USD_million or KRW_million','bear':None,'base':None,'bull':None,'independent_of_guidance':True,'basis':'explicit volume/price/margin/share assumptions, not probability'},'valuation':{'method':'EPS_PE or PB or EV_bridge or INCOMPLETE','bear':None,'base':None,'bull':None,'reference_price':'use provided raw units','assumptions':[],'equity_vs_EV_and_dilution':'','price_implied_expectation':''},'market_repricing':{'narrative':'source-backed vs hypothesis explicit','catalyst':'','timing':'','fund_flow_evidence':'MISSING if unavailable','counterargument':''},'policy_action':'BUY or WAIT or REJECT','policy_weight':0,'falsification':[],'research_quality':'PARTIAL or UNVERIFIED'}],'portfolios':[{'market':'US or KR','value_only_top2':[],'value_market_top2':[],'relative_final_top2':[],'change_reason_from_value_to_market_to_relative':'','cash_weight':1}],'limitations':[]}
 request={'messages':[{'role':'system','content':"""You are the original Vibe ChatLLM company-investment research component. Use only supplied dated evidence, no tools/web/files/memory/later outcomes. Work independently of other date experiments. First value-only ranking, then macro/sector/repricing/catalysts, then relative opportunity; record changes, do not pretend this within-call staging is an independent causal A/B. Choose exactly2 research-quality names per market from the3 studied, even if their policy is WAIT, to separately test discovery quality at equal equity exposure. That ranking is NOT a buy. The actual policy may BUY with 0<weight<=0.20 per name and total<=0.60 or WAIT with0; don't force cash solely because independent alpha is unproven, and don't force buying to demonstrate a system. Explain business quality versus investment attractiveness at supplied price. Produce numerically checkable independent FY-next forecasts and bear/base/bull equity values when supported; unknown values remain null, never invent consensus, probability, net flows, share counts or debt. Use bank/insurer appropriate valuation, EPS already equity no repeated debt subtraction; differentiate cyclical peak earnings from normalized profits. Respect KR amounts vs millions and Q3-only vs YTD. Output JSON only."""},{'role':'user','content':json.dumps({'input':payload,'output_schema':schema},ensure_ascii=False)}]}
 p=W/('deep2_'+str(year)+'.request.json')
 if p.exists():assert json.loads(p.read_text())==request
 else:p.write_text(json.dumps(request,ensure_ascii=False))
 (B/'deep_inputs'/('deep2_'+str(year)+'.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=2));print(year,fingerprint,len(json.dumps(request)),len(cases))

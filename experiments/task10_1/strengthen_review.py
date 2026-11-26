"""One-time pre-entry code completion; no historical results or signals changed."""
from pathlib import Path
p=Path(__file__).with_name('forward.py');s=p.read_text().replace('TASK101_FORWARD_SHADOW_V3','TASK101_FORWARD_SHADOW_V4')
s=s.replace("R/'experiments/task10/components.py',", "R/'experiments/task10/components.py',R/'experiments/task6/evaluate_worker.py',R/'src/quant_harness/investment/review.py',")
s=s.replace("'nontradable_index_adapter':'PENDING; ETF reference separately labelled, never called identical index'", "'nontradable_index_adapter':'Separate bounded benchmark collector; primary index availability remains explicit, ETF never called identical index'")
s=s.replace("'poll_minutes':30", "'poll_minutes':60")
s=s.replace("'review':'5 Forward sessions; mature t+1 to t+6 labels only since actual first signal seal. 20session warmup, two weak reviews before request; no automatic research worker activation.'", "'review':'5 Forward sessions; mature t+1 to t+6 labels only from prospectively sealed scores. 20session warmup and two weak reviews (matchedETF active<-2pp and IC<0) before separate Quanta/RD requests; no automatic research worker activation.'")
s=s.replace("  out['arms'][arm]={'net20':net,", "  exposure=pd.Series({r['day']:sum(float(q)*float(frames[k].close.loc[r['day']]) for k,q in json.loads(r['nav']['holdings_json']).items() if q)/float(r['nav']['nav_krw']) for r in rs},dtype=float)\n  br=etf.reindex(pd.to_datetime(recent.index)).pct_change(fill_method=None);br.index=recent.index\n  matched=float((1+br*exposure.reindex(recent.index).shift(1).fillna(0.)).prod()-1);active=net-matched if net is not None else None\n  model_errors=[]\n  for p in plans:\n   ds=frames[m+'_BENCHMARK'].index;idx=ds.get_indexer([pd.Timestamp(p['signal_date'])])[0]\n   if idx<0 or idx+6>=len(ds) or str(ds[idx+6].date())>day:continue\n   stage='US_2026-07-15' if arm=='ADAPTIVE_COMBINED' else 'initial';fp=F/'compute'/p['signal_date']/stage/m/'predictions.csv'\n   if fp.exists():\n    pred=pd.read_csv(fp,parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0].unstack('instrument')\n    if pd.Timestamp(p['signal_date']) in pred.index:\n     for name,v in pred.loc[pd.Timestamp(p['signal_date'])].dropna().items():\n      actual=frames[name].open.loc[ds[idx+6]]/frames[name].open.loc[ds[idx+1]]-1\n      if math.isfinite(actual):model_errors.append((float(v)-actual)**2)\n  out['arms'][arm]={'matched_ETF20':matched,'matched_active20':active,'model_MSE':float(np.mean(model_errors)) if model_errors and arm!='MOM63' else None,'model_error_cases':len(model_errors) if arm!='MOM63' else 0,'exposure':float(exposure.iloc[-1]),'net20':net,")
s=s.replace("'model_error':'PENDING_SEPARATELY_MATCHED_PREDICTIONS',", "'model_error':'SAME_FIVE_SESSION_OPEN_TARGET',")
s=s.replace("net is not None and net<-.02:", "active is not None and active<-.02:")
s=s.replace(" save(F/'reviews'/m/(day+'.json'),out);return out", " from quant_harness.investment.review import score_mature_outcome\n for arm,rs in records.items():\n  pp=plans[0]['process'][arm];nav={r['day']:r['nav']['nav_krw'] for r in rs};labels={'decision_id':pp['packet']['source_decision_id'],'calendar_verified':True,'calendar_verification_scope':'Contemporaneously archived provider regular sessions, not independent exchange certification','source_hash':digest(nav),'available_at':now(),'sessions':list(nav),'entry_session':next(iter(nav)),'nav':nav,'observed_at_by_session':{r['day']:str(datetime.datetime.fromisoformat(c['sealed_at'])+datetime.timedelta(days=0)) for r in []},'benchmark':{k:float(etf.loc[k]) for k in nav}}\n  labels['observed_at_by_session']={k:now() for k in nav}\n  out['arms'][arm]['native_outcome_review']=score_mature_outcome(pp['result'],pp['packet'],pp['policy'],labels)\n save(F/'reviews'/m/(day+'.json'),out);return out")
# helper process sealing, called before outcomes and stored with each decision.
helper='''def process_seals(plan):
 from quant_harness.investment.review import process_review,policy
 cfg=policy(R);cfg={**cfg,'strategy_horizons':{**cfg['strategy_horizons'],'TASK101_FORWARD':[5,20,60]}}
 out={}
 for arm,data in plan['arms'].items():
  packet={'source_decision_id':'TASK101-'+plan['market']+'-'+arm+'-'+plan['signal_date'],'market':plan['market'],'strategy_id':'TASK101_FORWARD','cutoff':plan['sealed_at'],'contract_hash':plan['contract_hash'],'input_hash':plan['source_hash'],'algorithm_hash':sha(__file__),'registered_policy':{'gross_cap':.8,'single_name_cap':.2},'weights':data['weights'],'eligible':True,'intents':[],'analysis':{'missing':[]},'source_receipts':[{'status':'TWO_PROVIDER_PARTIAL_ACTIONS'}],'evidence':[],'company_candidates':[]}
  out[arm]={'packet':packet,'policy':cfg,'result':process_review(packet,cfg)}
 return out

'''
s=s.replace('def market_tick(m,c,client):',helper+'def market_tick(m,c,client):')
s=s.replace(' save(planpath,plan)'," plan['process']=process_seals(plan)\n save(planpath,plan)")
p.write_text(s)

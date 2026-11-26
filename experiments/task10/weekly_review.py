from shared import *
from quant_harness.investment.review import process_review,score_mature_outcome,policy
from quant_harness.investment.research import digest as native_digest
from quant_harness.investment.equities import now

def weekly(m,asof,fs,scores,account,fills,intents,previous_bad,version='initial'):
 day=pd.Timestamp(asof);prefix={s:f.loc[:day] for s,f in fs.items()};n=account.set_index('date');window=n.iloc[-21:];metric={};vals=window.nav_krw;valid=vals.notna().all();etf=prefix[m+'_BENCHMARK'];br=etf.close.reindex(window.index).pct_change(fill_method=None);exp=window.exposure.shift(1).fillna(0.);matched=float((1+br*exp).prod()-1);net=float(vals.iloc[-1]/vals.iloc[0]-1) if valid and len(vals)>1 else None;icrows=rank_ic(scores,prefix,day,start=C['asof']);recent=icrows[-20:];ic=float(np.mean([r['IC'] for r in recent])) if len(recent)>=10 else None;weak=valid and len(account)>=20 and net is not None and net-matched<-.02 and ic is not None and ic<0
 previc=icrows[-40:-20];prevmean=float(np.mean([r['IC'] for r in previc])) if len(previc)>=10 else None;degrade=valid and ic is not None and ic<0 and prevmean is not None and prevmean-ic>.05;bad=previous_bad+1 if weak or degrade else 0
 if not valid:status='DATA_ISSUE'
 elif bad>=2:status='RESEARCH'
 elif weak or degrade:status='MONITOR'
 elif n.exposure.iloc[-1]==0:status='RISK_ACTION'
 else:status='MAINTAIN'
 snapshot={'asof':str(day.date()),'files':{s:digest(f.reset_index().to_json(date_format='iso',double_precision=15)) for s,f in prefix.items()}};sealed=json.loads((B/'process'/m/(version+'.json')).read_text());packet=sealed['packet'];cfg=sealed['policy'];process=sealed['process'];decision=packet['source_decision_id']
 # SourcefirstseenNOW is honest. Virtualhistoricalcutoff is separate from receipt time.
 timestamp=now();available=timestamp;nav={str(d.date()):float(v) for d,v in n.nav_krw.items() if pd.notna(v)};labels={'decision_id':decision,'calendar_verified':True,'calendar_verification_scope':'Ordered observed source local-session tape; full exchangeclosure proof partial','source_hash':digest(nav),'available_at':available,'sessions':[str(d.date()) for d in n.index],'entry_session':str(n.index[0].date()),'nav':nav,'observed_at_by_session':{d:timestamp for d in nav},'benchmark':{str(d.date()):float(v) for d,v in etf.close.reindex(n.index).items() if pd.notna(v)},'evidence_class':'HISTORICAL_REPLAY_BACKFILL_OBSERVED_NOW_NOT_FORWARD'};outcome=score_mature_outcome(process,packet,cfg,labels)
 result={'market':m,'asof':str(day.date()),'status':status,'consecutive_weak_reviews':bad,'rolling20_net':net,'rolling20_matched_ETF_return':matched,'rolling20_active':net-matched if net is not None else None,'rolling_mature5session_IC':ic,'prior_mature_IC':prevmean,'mature_signal_sessions':len(recent),'fees_to_date':float(fills.fee_krw.sum()) if len(fills) else 0.,'fills':len(fills),'unfilled':len(intents),'current_exposure':float(n.exposure.iloc[-1]) if pd.notna(n.exposure.iloc[-1]) else None,'cause':'UNDETERMINED; sustained signalweakness/cost/data separated, notsingleloss attribution','process':process,'outcome':outcome,'snapshot':snapshot,'packet':packet,'cutoff_is_replay_clock_not_historical_firstseen':True}
 return result,bad


def seal_process(m,version,asof,snapshot_hash,algorithm_hash):
 cfg=policy(R);cfg={**cfg,'strategy_horizons':{**cfg['strategy_horizons'],'TASK10_NATIVE':[5,20]}};packet={'source_decision_id':'T10-'+m+'-'+version,'market':m,'strategy_id':'TASK10_NATIVE','cutoff':str(asof)[:10]+('T17:00:00-04:00' if m=='US' else 'T16:00:00+09:00'),'contract_hash':sha(Path(__file__).parent/'contract.json'),'input_hash':snapshot_hash,'algorithm_hash':algorithm_hash,'registered_policy':{'gross_cap':.8,'single_name_cap':.2},'weights':{},'eligible':True,'intents':[],'analysis':{'missing':[]},'source_receipts':[{'status':'PARTIAL_TWO_PROVIDER_RAW_REPLAY'}],'evidence':[],'company_candidates':[]};process=process_review(packet,cfg);freeze(B/'process'/m/(version+'.json'),{'packet':packet,'policy':cfg,'process':process,'scope':'Prospective process integrityseal; NAVaccountmarks areindependentfromnativeopen-to-openforecastIC, notsamehorizonlabels.'})

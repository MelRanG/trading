from components import *
from measure import measure
from weekly_review import weekly,seal_process
from replay_factory import preregister,record,open_store,clock_at
from validate_candidate import validation


def research_event(m,review,parent,fs):
 day=review['asof'];stage=m+'_'+day;out=B/'experiments'/stage;result=out/'event.json'
 if result.exists():return json.loads(result.read_text())
 v=preregister(m,day,review['snapshot'],review,trading_dates(fs,m));source=frames(m,day)
 if m=='US':
  assert day==json.loads((B/'first_trigger.json').read_text())['asof'];candidate=pd.read_csv(B/'signals/US/candidate.csv',index_col=0,parse_dates=True,float_precision='round_trip');qstage='mutation_full'
 else:
  train_model(stage,m,source);rd=predict(stage,m,fs);first=json.loads((B/'first_trigger.json').read_text());usemutation=clock_at(day,m)>clock_at(first['asof'],'US');qstage='mutation_full' if usemutation else 'initial_full';q=factor(qstage,m,fs,E/('task10-quanta-work/mutation/factor.py' if usemutation else 'task10-quanta-work/initial/factor.py'));candidate=target_scores(q,rd);candidate.to_csv(B/'signals'/m/'candidate.csv');q.to_csv(B/'signals'/m/'quanta_candidate.csv')
 res=validation(m,day,parent,candidate,stage);recorded=record(v,res);accepted=res['isolated_replay_gate_passed'];ds=trading_dates(fs,m);nextdates=ds[ds>pd.Timestamp(v['processing_day'])];effective=str(nextdates[0].date()) if len(nextdates) else None;accepted=accepted and effective is not None
 event={'market':m,'source_asof':day,'decision_day':v['processing_day'],'effective_session':effective if accepted else None,'local_status':'REPLAY_ADOPTED' if accepted else 'MAINTAIN_PARENT','official_status':res['status'],'not_official_Champion_or_Paper_promotion':True,'candidate_signal_path':str((B/'signals'/m/'candidate.csv').relative_to(R)),'candidate_signal_hash':sha(B/'signals'/m/'candidate.csv'),'source_quanta':qstage,'rd_model_stage':stage,'validation_hash':sha(out/'validation.json'),'Factory':recorded,'reservation':v,'no_retroactive_use':True}
 freeze(result,event)
 if accepted:seal_process(m,stage,v['processing_day'],v['input_hash'],digest({'candidate':event['candidate_signal_hash'],'checkpoint':sha(B/'models'/stage/m/'model.pth')}))
 return event


def run_market(m):
 fs=frames(m);base=pd.read_csv(B/'signals'/m/'combined_initial.csv',index_col=0,parse_dates=True);used=base.copy();ds=trading_dates(fs,m);ds=ds[(ds>=C['entry'])&(ds<=C['end'])];bad=0;event=None;version='initial';store=open_store();reviews=[];effectivedate=None
 for i in [*range(4,len(ds),5),*([len(ds)-1] if (len(ds)-1)%5!=4 else [])]:
  day=ds[i];prefix={s:f.loc[:day] for s,f in fs.items()};met,nav,fills,intents,ledger,journal,ic=measure(used,prefix,m,C['entry'],day);review,bad=weekly(m,day,prefix,used,nav,fills,intents,bad,version);review['strategy_version']=version
  path=B/'reviews'/m/(str(day.date())+'.json');freeze(path,review);store.put('task10_weekly_review',review);reviews.append(review);print(m,str(day.date()),review['status'],'version',version,flush=True)
  if review['status']=='RESEARCH' and event is None and day<ds[-1]:
   event=research_event(m,review,base,fs)
   if event['local_status']=='REPLAY_ADOPTED':
    candidate=pd.read_csv(R/event['candidate_signal_path'],index_col=0,parse_dates=True,float_precision='round_trip');activation=pd.Timestamp(event['decision_day']);before=used.copy();mask=used.index>=activation;used.loc[mask,:]=candidate.reindex(index=used.index[mask],columns=used.columns);pd.testing.assert_frame_equal(used.loc[used.index<activation],before.loc[before.index<activation]);_,n0,f0,*_=measure(before,{s:f.loc[:activation] for s,f in fs.items()},m,C['entry'],activation);_,n1,f1,*_=measure(used,{s:f.loc[:activation] for s,f in fs.items()},m,C['entry'],activation);pd.testing.assert_frame_equal(n0,n1);pd.testing.assert_frame_equal(f0,f1);freeze(B/'experiments'/(m+'_'+event['source_asof'])/'no_retroactive_rewrite.json',{'max_prior_NAV_change':0,'prior_fills_identical':True,'strategy_effective':event['effective_session'],'activation_signal_close':event['decision_day'],'first_possible_open_afterdecision':True});effectivedate=event['effective_session'];version=m+'_'+event['source_asof'];print('ISOLATED_REPLAY_ADOPTED',m,effectivedate,flush=True)
 used.to_csv(B/'signals'/m/'adaptive_used.csv');names=[s for s in fs if 'BENCHMARK' not in s];mom=pd.DataFrame({s:fs[s].close.pct_change(63,fill_method=None) for s in names});out=B/'accounts'/m;out.mkdir(parents=True,exist_ok=True);results={}
 for arm,scores in [('STATIC',base),('ADAPTIVE',used),('MOM63',mom)]:
  metric,nav,fills,intents,ledger,journal,ics=measure(scores,fs,m,C['entry'],C['end']);nav.to_csv(out/(arm+'_nav.csv'),index=False);fills.to_csv(out/(arm+'_fills.csv'),index=False);intents.to_csv(out/(arm+'_unfilled.csv'),index=False);ledger.to_csv(out/(arm+'_targets.csv'),index=False);freeze(out/(arm+'_decisions.json'),journal);freeze(out/(arm+'_IC.json'),ics);results[arm]=metric;store.put('task10_replay_account',{'market':m,'arm':arm,'metrics':metric,'NAV_hash':sha(out/(arm+'_nav.csv')),'fills_hash':sha(out/(arm+'_fills.csv')),'no_operational_orders':True})
 freeze(out/'summary.json',{'market':m,'results':results,'research_event':event,'review_status_counts':{status:sum(x['status']==status for x in reviews) for status in ['MAINTAIN','MONITOR','RESEARCH','RISK_ACTION','DATA_ISSUE']},'strategy_versions':1+int(event is not None and event['local_status']=='REPLAY_ADOPTED'),'five_session_reviews':len(reviews),'evaluation_class':'HISTORICAL_DIAGNOSTIC_ONLY'});store.export(B/'research_records.jsonl');print('ACCOUNT_FINISHED',m,{k:v['return_pct'] for k,v in results.items()},flush=True)
if __name__=='__main__':
 for m in (sys.argv[1:] or ['US','KR']):run_market(m)

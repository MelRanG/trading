"""Correct outcome horizon origin per adopted strategy, preserving all V1 reviews.
V1 weekly trigger/IC and Factory decisions did not use these NAV-horizon fields.
"""
from shared import *
from quant_harness.investment.review import score_mature_outcome
from quant_harness.investment.equities import now
from quant_harness.investment.research import digest as native_digest
from replay_factory import open_store

def version_scoped_labels(packet,account,benchmark,asof):
 cutoff=pd.Timestamp(packet['cutoff']).date().isoformat();n=account.set_index('date') if 'date' in account.columns else account
 n=n[(n.index>pd.Timestamp(cutoff))&(n.index<=pd.Timestamp(asof))];assert len(n),'NO_POST_DECISION_MARKS';timestamp=now();nav={str(d.date()):float(v) for d,v in n.nav_krw.items() if pd.notna(v)}
 return {'decision_id':packet['source_decision_id'],'calendar_verified':True,'calendar_verification_scope':'Observed localbenchmarksessions, exchangeholidaycertificationpartial','source_hash':digest(nav),'available_at':timestamp,'sessions':[str(d.date()) for d in n.index],'entry_session':str(n.index[0].date()),'nav':nav,'observed_at_by_session':{d:timestamp for d in nav},'benchmark':{str(d.date()):float(v) for d,v in benchmark.reindex(n.index).items() if pd.notna(v)},'evidence_class':'HISTORICAL_REPLAY_VERSION_SCOPED_ACCOUNT_MARKS_NOT_NATIVE_FORECAST_LABEL'}

def main():
 store=open_store();rows=[]
 for m in ['US','KR']:
  fs=frames(m);a=pd.read_csv(B/'accounts'/m/'ADAPTIVE_nav.csv',parse_dates=['date'])
  for p in sorted((B/'reviews'/m).glob('*.json')):
   r=json.loads(p.read_text());v=r['strategy_version'];sealed=json.loads((B/'process'/m/(v+'.json')).read_text());labels=version_scoped_labels(sealed['packet'],a,fs[m+'_BENCHMARK'].close,r['asof']);result=score_mature_outcome(sealed['process'],sealed['packet'],sealed['policy'],labels);record={'version':'TASK10_REVIEW_OUTCOME_V2','market':m,'asof':r['asof'],'strategy_version':v,'original_review_path':str(p.relative_to(R)),'original_review_hash':sha(p),'entry_session':labels['entry_session'],'result':result,'no_trigger_or_account_changes':True};freeze(B/'review_outcomes_v2'/m/p.name,record);store.put('task10_version_outcome_correction',record);rows.append({'market':m,'asof':r['asof'],'version':v,'entry_session':labels['entry_session'],'status':result['status']})
 freeze(B/'review_outcome_v2_audit.json',{'reason':'V1 post-adoptionNAVhorizon incorrectly retainedaccountstartMay18 despite newprocesscutoffJuly15. Native5sessionIC, trigger, validationgate, actualfills/NAVwereunaffected. V1preserved; V2newversionstartsJuly16; first5markweekstillPENDING5intervals.','rows':rows,'historical_correction_not_investment_improvement':True});store.export(B/'research_records.jsonl');print('VERSION_SCOPED_OUTCOMES',len(rows))
if __name__=='__main__':main()

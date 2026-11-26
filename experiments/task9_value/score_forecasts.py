from pathlib import Path
import json,re
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_value';rows=[]
def number(v):return float(str(v).replace(',','').strip())
for year in [2021,2022,2023]:
 decision=json.loads((B/'decisions'/(str(year)+'.json')).read_text())['decision']
 for c in decision['companies']:
  s=c['symbol'];f=c['forecast'];p=B/'evaluator_only'/s;fy=int(f['fiscal_year']);r={'year':year,'market':c['market'],'symbol':s,'forecast':f,'actual':None,'baseline':None,'source':None,'status':'UNSCORED'}
  try:
   if c['market']=='US':
    rp=p/('actual_'+str(fy)+'_receipt_v2.json');rp=rp if rp.exists() else p/('actual_'+str(fy)+'_receipt.json');receipt=json.loads(rp.read_text());assert receipt['status'] in ['SAVED_MANUAL_FISCAL_TABLE_AUDIT','SAVED_PRIMARY_VISUAL_AUDIT'];actual=receipt['contract'];assert actual['unit']==f['unit'];r.update(actual=actual['actual'],baseline=actual['last_quarter_runrate'],source=receipt,baseline_basis='Last disclosed quarter times4, diagnostic preregistered naive runrate')
   else:
    data=json.loads((p/('actual_'+str(fy)+'.json')).read_text());ar=data['list']
    if f['metric']=='consolidated_revenue':vals=[x for x in ar if x['account_id']=='ifrs-full_Revenue' and x['sj_div'] in ['IS','CIS']]
    elif s=='005380.KS':vals=[x for x in ar if x['account_nm']=='보통주 희석주당이익']
    else:vals=[x for x in ar if x['account_id']=='ifrs-full_DilutedEarningsLossPerShare' and x['sj_div'] in ['IS','CIS']]
    assert len(vals)==1,'ambiguous fiscal metric';a=vals[0];value=number(a['thstrm_amount'])/(1e6 if f['unit']=='KRW_million' else 1);r.update(actual=value,source={'rcept_no':a['rcept_no'],'url':'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+a['rcept_no'],'reported_at':a['rcept_no'][:8],'account_nm':a['account_nm'],'account_id':a['account_id'],'currency':a.get('currency'),'vintage':'API supplied annual accession; not asserted first release or unrevised'})
    source=json.loads((B/'deep'/str(year)/s/'source_packet_v2.json').read_text());raw=json.loads((B/'deep'/str(year)/s/'accounts.json').read_text()).get('list',[])
    if source['API_matches_original_accession']:
     if f['metric']=='consolidated_revenue':bs=[x for x in raw if x['account_id']=='ifrs-full_Revenue' and x['sj_div'] in ['IS','CIS']]
     elif s=='005380.KS':bs=[x for x in raw if '보통주' in x['account_nm'] and '희석주당이익' in x['account_nm']]
     else:bs=[x for x in raw if x['account_id']=='ifrs-full_DilutedEarningsLossPerShare' and x['sj_div'] in ['IS','CIS']]
     if len(bs)==1 and bs[0].get('thstrm_add_amount') not in [None,'','-']:r['baseline']=number(bs[0]['thstrm_add_amount'])*4/3/(1e6 if f['unit']=='KRW_million' else 1);r['baseline_basis']='Nine-month YTD times4/3; identical accession validated'
   assert r['actual'] is not None and f['base'] is not None
   r.update(status='SCORED_HISTORICAL_DIAGNOSTIC',absolute_error=abs(f['base']-r['actual']),relative_absolute_error=abs(f['base']-r['actual'])/max(abs(r['actual']),1e-12),scenario_contains_actual=f['bear']<=r['actual']<=f['bull'])
   if r['baseline'] is not None:r['baseline_absolute_error']=abs(r['baseline']-r['actual']);r['beats_naive']=r['absolute_error']<r['baseline_absolute_error']
  except Exception as e:r['error_type']=type(e).__name__
  rows.append(r)
(B/'evaluation/forecast_scores_v2.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
for m in ['US','KR']:
 z=[x for x in rows if x['market']==m];print(m,'scored',sum(x['status'].startswith('SCORED') for x in z),'baseline_pairs',sum('beats_naive' in x for x in z),'beats',sum(x.get('beats_naive',False) for x in z),'inside_scenario',sum(x.get('scenario_contains_actual',False) for x in z))
for x in rows:print(x['symbol'],x['year'],x['actual'],x.get('relative_absolute_error'),x.get('beats_naive'),x['status'])

"""Assemble original-verified features, inspect mask/calendar availability only."""
from common import *
from decimal import Decimal
from collections import Counter,defaultdict
import pandas as pd,numpy as np,math

def main():
 P=json.loads((B/'plan.json').read_text());companies=[json.loads(p.read_text())for p in sorted((B/'companies').glob('*.json'))];rows=[];source_fail=[];seen=set();sources_checked={}
 for c in companies:
  a=c['company']
  for e in c['events']:
   key=(e['CIK'],e['period_start'],e['period_end'])
   assert key not in seen,'DUPLICATE_ISSUER_PERIOD';seen.add(key)
   original=body(e['source']);sources_checked[e['source']['storage_path']]=sha(R/e['source']['storage_path'])
   assert str(Decimal(e['feature']))==str(-(Decimal(e['NI'])-Decimal(e['OperatingCashFlow']))/Decimal(e['AverageAssets']))
   assert e['period_end']<=e['filed']<='2022-12-31' and e['filed']>='2017-01-01'
   assert all(x['original_source_hash']==e['source']['source_hash'] for x in e['proofs'])
   assert len(e['proofs'])==4 and all(x['original']['currency']=='USD' and int(x['original']['entity_CIK'])==int(e['CIK']) for x in e['proofs'])
   # Prior grade event retained exactly; row+provenance references avoid raw copies.
   rows.append({k:v for k,v in e.items() if k!='proofs'}|{'original_numeric_proof_path':'runtime/task13_c3/companies/'+a['symbol']+'.json','proof_roles':['NI','CFO','Assets_start','Assets_end']})
 dump('financial_panel.json',{'grade':'RECONSTRUCTED_PIT_DATE_BOUND_ORIGINAL_VALUES_VERIFIED_SURVIVOR_RESEARCH','rows':rows,'scope':'Same original filing date/current reported annual period; not original observation archive, first-news, full M&A comparability or fullmarket PIT'})
 flat=[{k:r[k]for k in ['symbol','CIK','period_start','period_end','filed','event_id','sector_current','NI','OperatingCashFlow','Assets_start','Assets_end','AverageAssets','feature']}for r in rows];pd.DataFrame(flat).to_csv(B/'financial_panel.csv',index=False)
 # Only use date/eligible columns, never open/close/forward returns.
 calendarpath=R/'runtime/task13_r0/accepted/US/^GSPC/quote.csv';dates=pd.to_datetime(pd.read_csv(calendarpath,usecols=['date']).date);days=pd.DatetimeIndex(dates[dates<='2024-12-31']);marketmaskpath=calendarpath.parent/'quality_mask.csv';market=pd.read_csv(marketmaskpath,index_col='date',parse_dates=True).eligible.reindex(days).fillna(False).to_numpy(bool)
 mask_inputs={str(calendarpath.relative_to(R)):sha(calendarpath),str(marketmaskpath.relative_to(R)):sha(marketmaskpath)};label_ready=[]
 for c in companies:
  a=c['company'];path=R/a['R0_asset']['eligibility_path'];assert sha(path)==a['R0_asset']['eligibility_hash']
  ep=pd.read_csv(path,index_col='date',parse_dates=True).eligible.reindex(days).fillna(False).to_numpy(bool);basicpath=path.parent/'quality_mask.csv';basic=pd.read_csv(basicpath,index_col='date',parse_dates=True).eligible.reindex(days).fillna(False).to_numpy(bool);good=ep&basic;mask_inputs[str(path.relative_to(R))]=sha(path);mask_inputs[str(basicpath.relative_to(R))]=sha(basicpath)
  for e in c['events']:
   i=int(days.searchsorted(pd.Timestamp(e['filed']),side='right'));j=i+252;reason=[]
   if j>=len(days):reason.append('H252_NOT_MATURE_BY2024_CUTOFF')
   else:
    if not good[i]:reason.append('NEXT_US_SESSION_NOT_NATIVE_ELIGIBLE')
    if not good[i:j+1].all():reason.append('INHERITED_STOCK_MASK_GAP_IN253_MARK_SESSIONS')
    if not market[i:j+1].all():reason.append('INHERITED_INDEX_MASK_GAP_IN253_MARK_SESSIONS')
   if i<127:reason.append('BASELINE_BETA_WARMUP_NOT_PRESENT')
   else:
    past=good[i-64:i];pair=good[i-126:i-6]&good[i-127:i-7]&market[i-126:i-6]&market[i-127:i-7]
    if not past.all() or pair.sum()<110:reason.append('BASELINE_FEATURE_MASK_WARMUP')
   label_ready.append({'event_id':e['event_id'],'symbol':e['symbol'],'CIK':e['CIK'],'filed':e['filed'],'entry_session':days[i].date().isoformat()if i<len(days)else None,'exit_H252_session':days[j].date().isoformat()if j<len(days)else None,'mask_potentially_usable':not reason,'reason':reason,'label_value':None})
 dump('label_availability.json',{'scope':'Only calendar and existingquality masks inspected. No prices or returns read; positive variance / actual numeric label not certified. H252 same nextopen-to-open convention. No masks changed.','rows':label_ready,'input_hashes':mask_inputs})
 values=np.array([float(r['feature'])for r in rows]);byyear={};fiscal={}
 for year in sorted({r['filed'][:4]for r in rows}):
  rs=[r for r in rows if r['filed'].startswith(year)];vs=np.array([float(r['feature'])for r in rs]);byyear[year]={'issuers':len({r['CIK']for r in rs}),'periods':len(rs),'mean':float(vs.mean()),'std':float(vs.std()),'unique_values':len(set(vs.tolist()))}
 for year in sorted({r['period_end'][:4]for r in rows}):
  rs=[r for r in rows if r['period_end'].startswith(year)];fiscal[year]={'issuers':len({r['CIK']for r in rs}),'periods':len(rs)}
 available=[r for r in label_ready if r['mask_potentially_usable']];minimum=P['minimum'];fundgate=len({r['CIK']for r in rows})>=50 and len(rows)>=150 and len(byyear)>=4;analysisgate=len({r['CIK']for r in available})>=50 and len(available)>=150 and len({r['filed'][:4]for r in available})>=4
 out={'source_verified_issuers':len({r['CIK']for r in rows}),'source_verified_periods':len(rows),'filed_year':byyear,'fiscal_year':fiscal,'sectors_current':dict(Counter(r['sector_current']for r in rows)),'max_current_sector_period_share':max(Counter(r['sector_current']for r in rows).values())/len(rows)if rows else None,'feature_diagnostics':{'mean':float(values.mean())if len(values)else None,'std':float(values.std())if len(values)else None,'quantiles':np.quantile(values,[0,.01,.25,.5,.75,.99,1]).tolist()if len(values)else [],'finite':bool(np.isfinite(values).all()),'negative':int((values<0).sum()),'positive':int((values>0).sum()),'zero':int((values==0).sum()),'abs_gt1_flagged_not_removed':int((abs(values)>1).sum()),'no_winsorization_or_outcome_trimming':True},'minimum_reference':minimum,'financial_count_gate':fundgate,'H252_mask_potential_issuers':len({r['CIK']for r in available}),'H252_mask_potential_periods':len(available),'H252_mask_reason_counts':dict(Counter(s for r in label_ready for s in r['reason'])),'H252_count_gate':analysisgate,'unique_publication_dates':len({r['filed']for r in rows}),'source_grade':'Source-linked original numbers and conservative public date reconstruction; survivorselection, sectorhistory and actiontape partial; calendar observedvendorindex','independent_evidence':'No unexposed outcome period or independent Forward evidence created. Future independent confirmation requires separately sealed new observations.','decision':'RESEARCH_DATA_READY' if fundgate and analysisgate else ('PARTIAL' if fundgate else 'DATA_INSUFFICIENT'),'technical':'VERIFIED_ORIGINAL_VALUES_FEATURE' if rows else 'BLOCKED_SOURCE','new_return_evaluations':0}
 dump('panel_diagnostics.json',out);dump('original_recheck.json',{'distinct_source_files':len(sources_checked),'hashes':sources_checked,'all_existing_original_hashes_match':True,'numeric_feature_reproducible':True,'features_not_alpha':True});print(json.dumps({k:v for k,v in out.items()if k in ['source_verified_issuers','source_verified_periods','filed_year','financial_count_gate','H252_mask_potential_issuers','H252_mask_potential_periods','H252_count_gate','decision','technical']},indent=2))
if __name__=='__main__':main()

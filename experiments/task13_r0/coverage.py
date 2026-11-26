"""Automatic coverage/eligibility/labels, sequential per-symbol memory."""
from pathlib import Path
import sys,json,hashlib,collections,datetime
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r0';sys.path.insert(0,str(R/'experiments/task12'));from readiness import regimes

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(B/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
core=json.loads((B/'universe.json').read_text());small=json.loads((B/'smallcap_universe.json').read_text()) if (B/'smallcap_universe.json').exists() else [];extra=json.loads((B/'extra_identity.json').read_text());usids={r['symbol']:r for r in extra['US']['rows']};assets=[{**a,'cohort':'CORE'} for a in core]+small
cal={};reg={}
for key,m,s in [('US','US','^GSPC'),('KOSPI','KR','^KS11'),('KOSDAQ','KR','^KQ11')]:
 p=B/'accepted'/m/s/'quote.csv';f=pd.read_csv(p,index_col='date',parse_dates=True);cal[key]=f.index;reg[key]=regimes(f.close);reg[key].to_csv(B/(key+'_regimes.csv'),index_label='date')
(B/'native_manifest').mkdir(exist_ok=True);counts={};native=[];rows=[];smalladmission=[]
for a in assets:
 folder=B/'accepted'/a['market']/a['symbol'];p=folder/'quality.json';key='US' if a['market']=='US' else a['board'];days=cal[key]
 if not p.exists():rows.append({**a,'status':'NO_ACCEPTED_PRICE','native_admitted':False});continue
 q=json.loads(p.read_text());f=pd.read_csv(folder/'adjusted.csv',index_col='date',parse_dates=True).reindex(days);quotes=pd.read_csv(folder/'quote.csv',index_col='date',parse_dates=True).reindex(days);qm=pd.read_csv(folder/'quality_mask.csv',index_col='date',parse_dates=True).reindex(days);valid=qm.eligible.astype('boolean').fillna(False).astype(bool)&np.isfinite(f).all(axis=1)&(f[['open','high','low','close','volume']]>0).all(axis=1)
 listing=a.get('list_date_toss') or usids.get(a['symbol'],{}).get('listDate')
 if listing:valid &=days>=pd.Timestamp(listing)
 # No stale dates are mistaken for verified halts/delists. Missing sessions stay NaN.
 aligned_missing=int(f.open.isna().loc[(days>=pd.Timestamp(q['start']))&(days<=pd.Timestamp(q['end']))].sum());last60=valid.iloc[-60:];proxy=quotes.close*quotes.volume;eligible_proxy=proxy.iloc[-60:].where(last60);liquid={'eligible_last60':int(last60.sum()),'median60_amount_proxy_KRW':float(eligible_proxy.median()) if eligible_proxy.notna().any() else 0.,'p10_60_amount_proxy_KRW':float(eligible_proxy.quantile(.1)) if eligible_proxy.notna().any() else 0.,'actual_month_amount':a.get('current_actual_month_amount'),'proxy_definition':'Yahoo quoteclose * volume_as_reported; approximate, not actual market trade amount'}
 admitted=int(valid.sum())>=500
 if a['cohort']!='CORE':
  c=json.loads((B/'smallcap_contract.json').read_text())['post_download_admission'];admitted &=liquid['eligible_last60']>=c['eligible_sessions_last60_min'] and liquid['median60_amount_proxy_KRW']>=c['median60_quoteclose_times_volume_KRW_min'] and liquid['p10_60_amount_proxy_KRW']>=c['p10_60_quoteclose_times_volume_KRW_min'];smalladmission.append({'symbol':a['symbol'],'admitted':bool(admitted),'liquidity':liquid,'reason':'PASS_FIXED_LIQUIDITY_AND_QUALITY' if admitted else 'INSUFFICIENT_RECENT_LIQUIDITY_OR_HISTORY_NOT_REPLACED'})
 row={**a,'status':q['status'],'native_admitted':bool(admitted),'first_bar':q['start'],'last_bar':q['end'],'observed_rows':q['structural_valid_rows'],'eligible_rows':int(valid.sum()),'missing_within_observed_life':aligned_missing,'unverified_jumps':q['unverified_jumps'],'zero_volume':q['zero_volume'],'declared_splits':len(q['actions'].get('splits',{})),'declared_dividends':len(q['actions'].get('dividends',{})),'source_quality':'PARTIAL_SURVIVOR_RESEARCH','identity_history':'UNVERIFIED_HISTORICAL_CHANGE_TAPE','input_paths':{'adjusted':str((folder/'adjusted.csv').relative_to(R)),'quote':str((folder/'quote.csv').relative_to(R)),'mask':str((folder/'quality_mask.csv').relative_to(R))},'source_hash':q['source_hash'],'liquidity_recent':liquid};rows.append(row)
 if not admitted:continue
 group=a['market']+'_'+('CORE' if a['cohort']=='CORE' else 'SMALLER');gs=counts.setdefault(group,{'days':days,'eligible':pd.Series(0,index=days,dtype=int),'H':{str(h):{'all':pd.Series(0,index=days,dtype=int),'fit':pd.Series(0,index=days,dtype=int),'validation':pd.Series(0,index=days,dtype=int)} for h in [5,20,60]}});gs['eligible']=gs['eligible'].add(valid.astype(int),fill_value=0).astype(int)
 feature=valid.rolling(63,min_periods=63).sum().eq(63)&pd.Series(np.arange(len(days))>=63,index=days);bad=np.r_[0,np.cumsum(~valid.to_numpy())];op=f.open.to_numpy();N=len(days)
 for h in [5,20,60]:
  idx=np.arange(N);mature=idx+h+1<N;good=np.zeros(N,bool);loc=idx[mature];good[loc]=(bad[loc+h+2]-bad[loc+1])==0;good&=feature.to_numpy();end=pd.Series(days,index=days).shift(-h-1);fit=good&(days<='2022-12-31')&end.lt(pd.Timestamp('2023-01-01')).to_numpy();validation=good&(days>='2023-04-03')&end.le(pd.Timestamp('2024-12-31')).to_numpy()
  for tag,mask in [('all',good),('fit',fit),('validation',validation)]:gs['H'][str(h)][tag]=gs['H'][str(h)][tag].add(pd.Series(mask.astype(int),index=days),fill_value=0).astype(int)
 # Persist compact eligibility once, source OHLCV stays immutable. Native builder masks, never fills.
 ep=folder/'native_eligibility.csv';pd.DataFrame({'eligible':valid},index=days).to_csv(ep,index_label='date');native.append({**a,'adjusted_path':str((folder/'adjusted.csv').relative_to(R)),'adjusted_hash':sha(folder/'adjusted.csv'),'eligibility_path':str(ep.relative_to(R)),'eligibility_hash':sha(ep),'calendar_key':key,'calendar_path':str((B/'accepted'/a['market']/('^GSPC' if key=='US' else '^KS11' if key=='KOSPI' else '^KQ11')/'quote.csv').relative_to(R)),'calendar_authority':'OBSERVED_PROVIDER_INDEX_SESSIONS_NOT_COMPLETE_OFFICIAL_EXCHANGE_CALENDAR'})
summary={}
for group,g in counts.items():
 days=g['eligible'].index;out={'admitted_symbols':sum(a['market']+'_'+('CORE' if a['cohort']=='CORE' else 'SMALLER')==group for a in native),'first':str(days.min().date()),'last':str(days.max().date()),'market_sessions':len(days),'eligible_symbol_sessions':int(g['eligible'].sum()),'per_year':{str(y):{'sessions':len(v),'min_names':int(v.min()),'median_names':float(v.median()),'max_names':int(v.max()),'dates_atleast50':int((v>=50).sum())} for y,v in g['eligible'].groupby(g['eligible'].index.year)},'labels':{}}
 for h,tags in g['H'].items():
  out['labels'][h]={}
  for tag,n in tags.items():
   active=n[n>0];out['labels'][h][tag]={'symbol_sessions':int(n.sum()),'dates_any':len(active),'dates_ge8':int((n>=8).sum()),'dates_ge50':int((n>=50).sum()),'nonoverlap_date_blocks_upper_bound':len(active)//int(h),'min_names_positive':int(active.min()) if len(active) else 0,'median_names_positive':float(active.median()) if len(active) else 0,'first':str(active.index.min().date()) if len(active) else None,'last':str(active.index.max().date()) if len(active) else None}
 countsdf=pd.DataFrame({'eligible':g['eligible'],**{'H'+h+'_'+tag:n for h,tags in g['H'].items() for tag,n in tags.items()}});countsdf.to_csv(B/(group+'_coverage_daily.csv'),index_label='date');summary[group]=out
# Actual symbol-data availability in regimes, not index coverage alone.
regime_coverage=[]
for group,g in counts.items():
 key='US' if group.startswith('US') else 'KOSPI';rg=reg[key].reindex(g['eligible'].index)
 for axis in ['AS_OF_REGIME','EX_POST_REGIME','AS_OF_HIGH_VOL']:
  for label,ix in rg.groupby(axis).groups.items():
   n=g['eligible'].reindex(ix);regime_coverage.append({'group':group,'axis':axis,'regime':str(label),'dates':len(n),'median_names':n.median(),'symbol_sessions':int(n.sum()),'dates_ge50':int((n>=50).sum()),'classification':'AS_OF historical causal only; EX_POST evaluator only; no independentHoldout'})
 for y in [2018,2020,2022,2026]:
  n=g['eligible'].loc[str(y)];regime_coverage.append({'group':group,'axis':'year','regime':str(y),'dates':len(n),'median_names':n.median(),'symbol_sessions':int(n.sum()),'dates_ge50':int((n>=50).sum())})
dump('coverage.json',{'groups':summary,'assets':rows,'regime_stock_coverage':regime_coverage,'PIT_universe':'SURVIVOR_RESEARCH_NOT_GENERALIZED_PIT_BACKTEST','market_calendar':'Provider-index observed sessions and current officialToss schedule. No full historical exchange-calendar certification.','native_admitted_total':len(native)});dump('smallcap_admission.json',smalladmission);dump('native_manifest/assets.json',native)
print('COVERAGE', {g:{'symbols':x['admitted_symbols'],'rows':x['eligible_symbol_sessions'],'H60fit':x['labels']['60']['fit']['dates_ge8']} for g,x in summary.items()},'SMALL_ADMITTED',sum(r['admitted'] for r in smalladmission))

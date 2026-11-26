"""One frozen H60 event diagnostic; reuses Task12 labels and Task14 residual metrics.
No model training, trade allocation, alpha search, or operational writes.
"""
from common import *
import pandas as pd,numpy as np
from scipy.stats import t
from collections import Counter
sys.path[:0]=[str(R/'experiments/task12'),str(R/'experiments/task14')]
from readiness import labels
from stats_eval import residual,corr

def fitted(d):
 z=pd.concat([d[['MOM20','REV5','VOL20']],pd.get_dummies(d.year.astype(str),prefix='year',drop_first=True,dtype=float),pd.get_dummies(d.sector,prefix='sector',drop_first=True,dtype=float)],axis=1).to_numpy(float)
 x=d.margin_delta.to_numpy(float);y=d.sector_relative.to_numpy(float);rx,_=residual(x,z);ry,_=residual(y,z);X=np.column_stack([np.ones(len(d)),x,z]);beta=np.linalg.lstsq(X,y,rcond=None)[0];u=y-X@beta;bread=np.linalg.pinv(X.T@X);meat=np.zeros((X.shape[1],X.shape[1]));ids=d.symbol.unique()
 for name in ids:
  m=d.symbol.eq(name).to_numpy();a=X[m].T@u[m];meat+=np.outer(a,a)
 G=len(ids);N,K=X.shape;cov=bread@meat@bread*(G/(G-1))*((N-1)/(N-K));se=float(np.sqrt(max(0,cov[1,1])));cut=float(t.ppf(.975,G-1));b=float(beta[1]);return {'coefficient_per1_margin_ratio':b,'effect_per1pp_margin':b*.01,'issuer_cluster_CI95_per1pp':[(b-cut*se)*.01,(b+cut*se)*.01],'issuer_cluster_SE_raw':se,'issuer_clusters':G,'observations':N,'design_columns':K,'design_rank':int(np.linalg.matrix_rank(X)),'partial_Pearson':corr(rx,ry),'partial_Spearman':corr(rx,ry,True),'standardized_effect':b*float(np.std(x,ddof=1)),'estimator':'inferential OLS/CR1 issuer clusters, smallG and cross-issuer date dependence unresolved; not predictive-model training'}

def main():
 assert json.loads((B/'phase_c_gate.json').read_text())['pass'];seal=json.loads((B/'signal_seal.json').read_text());assert sha(B/'signal_events.json')==seal['events_SHA'];assert sha(B/'plan.json')==seal['plan_SHA']
 universe=json.loads((R/'runtime/task13_r0/universe.json').read_text());assets=[a for a in universe if a['market']=='US'];sectors={a['symbol']:a['sector_current']for a in assets};frames={};valid={};refs=[]
 for symbol in [a['symbol']for a in assets]+['^GSPC']:
  root=R/'runtime/task13_r0/accepted/US'/symbol
  if not (root/'adjusted.csv').exists():continue
  for name in ['adjusted.csv','quality_mask.csv']:
   refs.append({'path':str((root/name).relative_to(R)),'sha256':sha(root/name)})
  f=pd.read_csv(root/'adjusted.csv',index_col='date',parse_dates=True).loc[:P['label_exit_max']];m=pd.read_csv(root/'quality_mask.csv',index_col='date',parse_dates=True)
  good=np.isfinite(f[['open','high','low','close']]).all(axis=1)&f[['open','high','low','close']].gt(0).all(axis=1)&f.high.ge(f[['open','close','low']].max(axis=1))&f.low.le(f[['open','close','high']].min(axis=1))
  if not symbol.startswith('^'):good&=f.volume.gt(0)
  frames[symbol]=f;valid[symbol]=good&m.eligible.reindex(f.index).eq(True)
 days=frames['^GSPC'].index;frames={s:f.reindex(days)for s,f in frames.items()};valid={s:v.reindex(days).fillna(False)for s,v in valid.items()};dump(B/'price_inputs.json',{'references':refs,'basis':'R0 adjusted SURVIVOR_RESEARCH; observed index calendar, not certified execution dates; no new download'})
 events=json.loads((B/'signal_events.json').read_text());items=[];rejected=[];N=len(days)
 for e in events:
  s=e['symbol'];day=pd.Timestamp(e['filed_date']);entry=days.searchsorted(day,side='right');exit=entry+P['H'];previous=days.searchsorted(day,side='left')-1;sector=sectors[s];reason=None
  if previous<62 or exit>=N:reason='WARMUP_OR_UNMATURED_H60'
  elif not valid[s].iloc[previous-62:previous+1].all()or not valid[s].iloc[entry:exit+1].all():reason='STOCK_MASK_OR_MISSING_PATH'
  if reason:rejected.append({'event':e['accession'],'symbol':s,'reason':reason});continue
  # Peer membership selected with pre-filing data only. Future-invalid member
  # blocks whole event, never selectively drop a bad realized peer return.
  peers=[k for k in frames if k!=s and sectors.get(k)==sector and valid[k].iloc[previous-62:previous+1].all()]
  if len(peers)<3:reason='FEWER_THAN3_ASOF_SECTOR_PEERS'
  elif not all(valid[k].iloc[entry:exit+1].all()for k in peers):reason='FROZEN_PEER_PATH_INVALID_BLOCK_EVENT'
  elif not valid['^GSPC'].iloc[entry:exit+1].all():reason='MARKET_PATH_INVALID'
  if reason:rejected.append({'event':e['accession'],'symbol':s,'reason':reason});continue
  items.append({'event':e,'symbol':s,'sector':sector,'entry_i':int(entry),'exit_i':int(exit),'previous_i':int(previous),'base_i':int(entry-1),'peers':peers})
 counts={'events':len(items),'issuers':len({x['symbol']for x in items}),'sectors':len({x['sector']for x in items}),'rejected':dict(Counter(x['reason']for x in rejected)),'minimum':P['prices']['minimum_price_events'],'future_invalid_peer_policy':'block full event; no ex-post peer survivor selection','calendar':'Observed providerSP500 sessions corroborated by actual positive stock observations, complete official exchange/halts not independently certified','price_tier':'PARTIAL_ADJUSTED_RESEARCH_ONLY'}
 gate=len(items)>=80 and counts['issuers']>=8 and counts['sectors']>=3;counts['pass']=gate;dump(B/'price_gate.json',counts);dump(B/'rejected_labels.json',rejected)
 if not gate:
  dump(B/'evaluation.json',{'verdict':'DATA_BLOCKED','reason':'Prespecified price/event sample gate failed; no alternative candidate or label horizon','price_gate':counts,'H60_results':None});print(json.dumps(counts));return
 # Only here calculate targets. Common-label horizon matches Task12, not a new backtester.
 native,target_end=labels({**{s:f for s,f in frames.items()if s!='^GSPC'},'US_BENCHMARK':frames['^GSPC']},'US',P['H'],P['label_exit_max']);rows=[]
 for item in items:
  e=item['event'];s=item['symbol'];a,b,p,c=[item[k]for k in ['entry_i','exit_i','previous_i','base_i']];f=frames[s];own=float(f.open.iloc[b]/f.open.iloc[a]-1);assert abs(own-float(native.loc[days[c],s]))<1e-12;assert target_end.loc[days[c]]==days[b]
  peer_ret=float(np.mean([frames[k].open.iloc[b]/frames[k].open.iloc[a]-1 for k in item['peers']]));mkt=float(frames['^GSPC'].open.iloc[b]/frames['^GSPC'].open.iloc[a]-1)
  rows.append({'symbol':s,'accession':e['accession'],'filed_date':e['filed_date'],'entry':str(days[a].date()),'exit':str(days[b].date()),'controls_last_close':str(days[p].date()),'year':day.year if False else int(e['filed_date'][:4]),'sector':item['sector'],'margin_delta':e['margin_delta'],'MOM20':float(f.close.iloc[p]/f.close.iloc[p-20]-1),'REV5':float(1-f.close.iloc[p]/f.close.iloc[p-5]),'VOL20':float(f.close.pct_change(fill_method=None).iloc[p-19:p+1].std(ddof=1)),'stock_H60':own,'peer_H60':peer_ret,'sector_relative':own-peer_ret,'market_relative_basis_partial':own-mkt,'peer_count':len(item['peers']),'peer_membership':item['peers'],'calendar_60block':int(a//60)})
 d=pd.DataFrame(rows);d.to_json(B/'evaluated_events.json',orient='records',indent=2);fit=fitted(d);loo={s:fitted(d[d.symbol!=s].copy())['effect_per1pp_margin']for s in d.symbol.unique()};annual={str(y):{'n':len(g),'pooled_event_Pearson':corr(g.margin_delta,g.sector_relative),'sign_spread':float(g.loc[g.margin_delta>0,'sector_relative'].mean()-g.loc[g.margin_delta<0,'sector_relative'].mean())}for y,g in d.groupby('year')};positive=d[d.margin_delta>0];negative=d[d.margin_delta<0];positive_years=sum(v['pooled_event_Pearson']>0 for v in annual.values());promising=fit['partial_Pearson']>0 and fit['issuer_cluster_CI95_per1pp'][0]>0 and all(v>0 for v in loo.values()) and positive_years>=len(annual)-1
 result={'verdict':'PROMISING'if promising else'NO_INCREMENTAL_EVIDENCE','scope':'One exposed-history source/adjusted-price diagnostic, not net-of-cost alpha or independently validated research','price_gate':counts,'primary':fit,'pooled_event_correlations_not_daily_IC':{'Pearson':corr(d.margin_delta,d.sector_relative),'Spearman':corr(d.margin_delta,d.sector_relative,True)},'sign_groups':{'UP_margin_n':len(positive),'DOWN_margin_n':len(negative),'UP_mean_sector_H60':float(positive.sector_relative.mean()),'DOWN_mean_sector_H60':float(negative.sector_relative.mean()),'UP_minus_DOWN':float(positive.sector_relative.mean()-negative.sector_relative.mean())},'baseline_pooled_correlations':{s:corr(d[s],d.sector_relative)for s in ['MOM20','REV5','VOL20']},'year_diagnostics':annual,'leave_one_issuer_out_per1pp':loo,'calendar_nonoverlap60_blocks':int(d.calendar_60block.nunique()),'earliest_entry':d.entry.min(),'latest_exit':d.exit.max(),'controls_strictly_before_filing':bool((pd.to_datetime(d.controls_last_close)<pd.to_datetime(d.filed_date)).all()),'horizon_reconciliation_rows':len(d),'no_risk_cash_weights_or_trades':True,'costs_not_deducted':'No trade strategy or turnover chosen; overlapping event sign spread not investable/accountreturn; costs could remove any gross effect','market_baseline_caveat':'Stock/peers consistently adjusted research basis. GSPC is priceindex; secondary market relative not dividend-comparable economic alpha.','remaining_limits':['survivor/current-sector sample','CF backfill original accessions spotchecked only','same-information earnings bundle not controlled','issuer/time overlap & cross-issuer common shocks','no universal corporate-scope comparability','no independent holdout','no validated nominal fills or net trade returns']}
 dump(B/'evaluation.json',result);print(json.dumps(result))
if __name__=='__main__':main()

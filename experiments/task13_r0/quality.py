"""Existing normalization/V87+revision gate; explicit per-session quarantine mask."""
from pathlib import Path
from zoneinfo import ZoneInfo
import json,copy,datetime,hashlib
import pandas as pd,numpy as np
from quant_harness.investment.equities import normalize_chart
from quant_harness.v87_actual_data_ingestion.engine import ProviderBatch,_validate_batch,_revision_audit
R=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def normalize(payload,symbol,market,observed):
 chart=payload['chart']['result'][0];meta=chart['meta'];assert meta['symbol'].upper()==symbol.upper(),'IDENTITY_SYMBOL';assert meta.get('currency')==('USD' if market=='US' else 'KRW'),'IDENTITY_CURRENCY'
 assert meta.get('instrumentType',meta.get('quoteType','EQUITY')) in ['EQUITY','INDEX','ETF'],'INSTRUMENT_TYPE'
 zone=ZoneInfo('America/New_York' if market=='US' else 'Asia/Seoul');q=chart['indicators']['quote'][0];adj=chart['indicators']['adjclose'][0]['adjclose'];ts=chart['timestamp'];assert len(ts)==len(set(ts)),'DUPLICATE_TIMESTAMPS';good=[];rejected=[]
 for i,t in enumerate(ts):
  day=datetime.datetime.fromtimestamp(t,datetime.timezone.utc).astimezone(zone).date().isoformat()
  try:
   vals=[float(q[k][i]) for k in ['open','high','low','close','volume']]+[float(adj[i])];o,h,l,c,v,a=vals
   if not all(np.isfinite(vals)) or min(o,h,l,c,a)<=0 or v<0 or h<max(o,l,c) or l>min(o,h,c):raise ValueError('NONPOSITIVE_OR_GEOMETRY')
   if day>'2026-11-13' or day<'2017-01-01':raise ValueError('OUTSIDE_FROZEN_RANGE')
   good.append(i)
  except (TypeError,ValueError,IndexError) as e:rejected.append({'date':day,'reason':str(e)})
 if not good:raise ValueError('NO_VALID_BARS')
 sub=copy.deepcopy(payload);z=sub['chart']['result'][0];z['timestamp']=[ts[i] for i in good]
 for k,v in z['indicators']['quote'][0].items():z['indicators']['quote'][0][k]=[v[i] for i in good]
 z['indicators']['adjclose'][0]['adjclose']=[adj[i] for i in good]
 f,_=normalize_chart(sub,symbol);f['date']=[datetime.datetime.fromtimestamp(ts[i],datetime.timezone.utc).astimezone(zone).date().isoformat() for i in good];assert not f.date.duplicated().any(),'DUPLICATE_MARKET_DATE';f=f.set_index('date').sort_index();f.index=pd.to_datetime(f.index);f.index.name='date'
 # Values are not repaired. Eligible tracks exclude unexplained events/zero-volume bars.
 actions=chart.get('events',{});ret=f.close.pct_change(fill_method=None);jump=ret.abs()>.35;zero=f.volume.eq(0);first=meta.get('firstTradeDate');pre=pd.Series(False,index=f.index)
 if first is not None:
  firstdate=datetime.datetime.fromtimestamp(first,datetime.timezone.utc).astimezone(zone).date();pre=f.index.date<firstdate;pre=pd.Series(pre,index=f.index)
 mask=pd.DataFrame({'ZERO_VOLUME_UNCLASSIFIED':zero,'UNVERIFIED_JUMP_GT35PCT':jump,'BEFORE_VENDOR_FIRST_TRADE':pre},index=f.index);
 known_splits={datetime.datetime.fromtimestamp(e['date'],datetime.timezone.utc).astimezone(zone).date() for e in actions.get('splits',{}).values()}
 mask['KNOWN_SPLIT_VOLUME_BASIS_GUARD']=[d.date() in known_splits for d in mask.index]
 mask['eligible']=~mask.any(axis=1)
 # Structural V87 validates the provider quote basis, not historical executable nominal prices.
 cfg=json.loads((R/'config/task3_equity_price_contract.json').read_text());cfg['provider_contract']['required_source_tag']='R0_YAHOO_PROVIDER_QUOTE';cfg['provider_contract']['canonical_price_scale']='PROVIDER_QUOTE_RESEARCH_ONLY'
 quote=f[['raw_open','raw_high','raw_low','raw_close','volume','value_approx']].rename(columns=lambda x:x.removeprefix('raw_')).copy();quote['date']=quote.index.strftime('%Y-%m-%d');quote['ticker']=symbol.zfill(6)
 canonical=_validate_batch(ProviderBatch('YAHOO_CHART',symbol.zfill(6),tuple(quote.to_dict('records')),False,'R0_YAHOO_PROVIDER_QUOTE',observed,{}),cfg)
 return f,mask,{'meta':meta,'actions':actions,'rejected_rows':rejected,'structural_valid_rows':len(f),'eligible_observed_rows':int(mask.eligible.sum()),'zero_volume':int(zero.sum()),'unverified_jumps':int(jump.sum()),'pre_first_trade':int(pre.sum()),'quality_level':'PARTIAL','numeric_geometry':'VERIFIED_ON_RETAINED_ROWS','actions_status':'PARTIAL_PROVIDER_EVENTS_NOT_INDEPENDENT_CERTIFICATION','price_basis':'Yahooquote_possible_split_adjusted; adjustedOHLC=quote*sourceadjclose/quoteclose; volume_as_reported','observed_at':observed,'historical_observation_authority':False},canonical,cfg

def validate_and_save(payload,receipt,asset,folder):
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);symbol=asset['symbol'];f,mask,quality,canonical,cfg=normalize(payload,symbol,asset['market'],receipt['available_at'])
 if len(f)<500:raise ValueError('SHORT_HISTORY_LT500_VALID_ROWS')
 reference=folder/'quote.reference.csv';revision=_revision_audit(canonical,reference,cfg);quality['V87_revision']=revision
 if not revision['passed']:raise ValueError('SOURCE_REVISION_QUARANTINED')
 # Last known endpoint is not silently extended; missing-date diagnosis later uses benchmark sessions.
 
 listing_dates=[pd.Timestamp(x) for x in [asset.get('list_date_toss'),asset.get('list_date_kind')] if x and str(x)!='NaT']
 if listing_dates:
  mask['BEFORE_CURRENT_DOCUMENTED_LISTING_OR_TRANSFER']=mask.index<max(listing_dates);mask['eligible']&=~mask['BEFORE_CURRENT_DOCUMENTED_LISTING_OR_TRANSFER'];quality['listing_boundary']=str(max(listing_dates).date());quality['listing_boundary_note']='Conservative currentlisting/possibletransfer bound, historical identity continuity not inferred'
 quality['quality_policy_version']=2;quality['asset']=asset;quality['source_receipt']=receipt;quality['start']=str(f.index.min().date());quality['end']=str(f.index.max().date());quality['nominal_execution_eligible']=False
 paths={}
 for name,data in [('quote.csv',f[['raw_open','raw_high','raw_low','raw_close','volume']].rename(columns=lambda x:x.removeprefix('raw_'))),('adjusted.csv',f[['open','high','low','close','volume']]),('quality_mask.csv',mask),('quote.reference.csv',canonical)]:
  p=folder/name
  if name=='quote.reference.csv' and p.exists():continue
  tmp=p.with_suffix(p.suffix+'.tmp');data.to_csv(tmp,index=name!='quote.reference.csv');tmp.replace(p);paths[name]=sha(p)
 quality['output_hashes']=paths;quality['source_hash']=receipt['source_hash'];quality['status']='ACCEPTED_PARTIAL_RESEARCH';tmp=folder/'quality.json.tmp';tmp.write_text(json.dumps(quality,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n');tmp.replace(folder/'quality.json')
 return quality

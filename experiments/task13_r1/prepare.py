from pathlib import Path
import json,hashlib,pandas as pd,subprocess
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r1';S=R/'runtime/task13_r0'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((S/'native/inputs.json').read_text())
for a in inputs.values():assert sha(R/a['path'])==a['sha256']
assert subprocess.check_output(['git','-C','/home/ansy/app/quant-diligence/quanta-original','rev-parse','HEAD'],text=True).strip()=='b7ceb27b1001261d7a95b209a963664ae1f8ab23'
counts=pd.read_csv(S/'KR_CORE_coverage_daily.csv',index_col=0);low=counts[counts.eligible<50];details=[]
assets=json.loads((S/'native_manifest/assets.json').read_text())
for day,row in low.iterrows():
 reasons={};names=[]
 for a in assets:
  if a['market']!='KR':continue
  p=R/a['adjusted_path'];f=pd.read_csv(p,index_col=0)
  if day not in f.index:reason='SOURCE_DATE_MISSING'
  else:
   q=pd.read_csv(p.parent/'quality_mask.csv',index_col=0)
   reason=';'.join(c for c in q.columns if c!='eligible' and bool(q.loc[day,c])) if day in q.index else 'MASK_DATE_MISSING'
   reason=reason or 'VALID_OR_LISTING_BOUNDARY'
  reasons[reason]=reasons.get(reason,0)+1
  if reason!='VALID_OR_LISTING_BOUNDARY':names.append(a['symbol'])
 details.append({'date':day,'core_eligible':int(row.eligible),'reasons':reasons,'affected_symbols':names})
(B/'kr_low_dates.json').write_text(json.dumps(details,indent=2))
contract={'commit':'b7ceb27b1001261d7a95b209a963664ae1f8ab23','directions':2,'execution_cap':4,'proposal_selection':'first returned task before performance; save all extras as NOT_EXECUTED','phase1':{'calls':10,'tokens':350000},'total':{'calls':20,'tokens':650000},'model':'gpt-6.1-terra','primary_H':20,'sign':1,'min_crosssection':50,'warmup':63,'fit':'2017..2022 labels mature<=2022-12-31','validation':'2023-04-03..2024-12-31 labels mature<=2024-12-31','diagnostic':'2025..2026 only after final freeze; exposed not Holdout','label':'nextopen t+1 to t+H+1','mechanisms':['overnight versus intraday asymmetry','liquidity shocks versus subsequent resilience'],'no_parameter_or_horizon_search':True,'native_inputs':inputs,'KR_low_date_rule':'Require>=50 score/label valid names both markets; missing/unknown days quarantined, not declared actual halts','scope':'SURVIVOR_RESEARCH; original controller+components with external evaluator if full AlphaAgentLoop cannot consume current provider'}
(B/'contract.json').write_text(json.dumps(contract,indent=2));print('SEALED',len(details),'KR_LOW_DATES')

"""Evidence-backed issuer lifetimes, separate from market/ticker start dates.
Only study-local eligibility overlays; original R0 files remain immutable.
"""
from common import *
import pandas as pd,numpy as np

def evidence(name,pattern):
 rec=json.loads((B/'source_text'/f'{name}.json').read_text());m=re.search(pattern,rec['text'],re.I)
 assert m,(name,pattern)
 meta=json.loads((B/'source_index.json').read_text())[name];body(meta)
 return {'document':name,'URL':rec['URL'],'source_SHA':rec['source_SHA'],'text_start':m.start(),'quote':rec['text'][max(0,m.start()-60):m.end()+110]}

def build():
 rows=[{'storage_symbol':'KMB','CIK':'0000055785','issuer':'Kimberly-Clark Corporation','history_supported_from':'2019-07-30','initial_public_date':None,'original_bad_listDate':'2025-05-30','date_semantics':'NYSE_TO_NASDAQ_TRANSFER_NOT_IPO','timeline':[{'from':'2019-07-30','until':'2025-05-29','symbol':'KMB','exchange':'NYSE'},{'from':'2025-05-30','until':None,'symbol':'KMB','exchange':'NASDAQ'}],'evidence':[evidence('KMB_2019_COVER',r'Trading Symbol KMB'),evidence('KMB_TRANSFER_SEC',r'May 30, 2025')]},
 {'storage_symbol':'HLT','CIK':'0001585689','issuer':'Hilton Worldwide Holdings Inc.','history_supported_from':'2013-12-12','initial_public_date':'2013-12-12','original_bad_listDate':'2026-11-05','date_semantics':'NYSE_TO_NASDAQ_TRANSFER_NOT_IPO','timeline':[{'from':'2013-12-12','until':'2026-11-04','symbol':'HLT','exchange':'NYSE'},{'from':'2026-11-05','until':None,'symbol':'HLT','exchange':'NASDAQ'}],'evidence':[evidence('HLT_IPO',r'opened for trading yesterday, December 12'),evidence('HLT_TRANSFER',r'Nov\. 5, 2026')]},
 {'storage_symbol':'PLTR','CIK':'0001321655','issuer':'Palantir Technologies Inc.','history_supported_from':'2020-09-30','initial_public_date':'2020-09-30','original_bad_listDate':'2024-11-26','date_semantics':'NYSE_TO_NASDAQ_TRANSFER_NOT_IPO','timeline':[{'from':'2020-09-30','until':'2024-11-25','symbol':'PLTR','exchange':'NYSE'},{'from':'2024-11-26','until':None,'symbol':'PLTR','exchange':'NASDAQ'}],'evidence':[evidence('PLTR_HISTORY',r'From September 30, 2020 through November 25, 2024'),evidence('PLTR_TRANSFER',r'maintain historical data')]},
 {'storage_symbol':'SGI','CIK':'0001206264','issuer':'Tempur Sealy International / Somnigroup International','history_supported_from':'2003-12-18','initial_public_date':'2003-12-18','original_bad_listDate':'2025-02-18','date_semantics':'TPX_TO_SGI_SAME_ISSUER_NAME_SYMBOL_CHANGE_NOT_IPO','timeline':[{'from':'2003-12-18','until':'2025-02-17','symbol':'TPX','exchange':'NYSE'},{'from':'2025-02-18','until':None,'symbol':'SGI','exchange':'NYSE'}],'evidence':[evidence('TPX_2019_10K',r'Trading of our common stock commenced on the NYSE on December 18, 2003'),evidence('SGI_RENAME',r'effective February 18, 2025'),evidence('SGI_IPO_HISTORY',r'ticker symbol .TPX.')]}]
 data={'scope':'B3 2020-24 limited survivor research; repair identity metadata only, not stock recommendations or broad-PIT proof','verified_mask_end':'2024-12-31','later_publication_used_for_audit_not_predictor':True,'KMB_bound_note':'2019 original SEC cover confirms exchange+symbol; exact initialIPO not inferred. Support starts at original cover date, not an invented earlyIPO. Older R0 data left ineligible in this overlay.','entries':rows};p=B/'identity_overlay.json'
 if p.exists():assert json.loads(p.read_text())==data
 else:dump(p,data)
 audits=[]
 for e in rows:
  root=R/'runtime/task13_r0/accepted/US'/e['storage_symbol'];q=pd.read_csv(root/'quality_mask.csv',index_col='date',parse_dates=True);mask=q.eligible.eq(True)&(q.index>=e['history_supported_from'])&(q.index<=data['verified_mask_end']);out=pd.DataFrame({'eligible':mask},index=q.index);p=B/'eligibility'/f"{e['storage_symbol']}.csv";p.parent.mkdir(exist_ok=True)
  if p.exists():assert p.read_text()==out.to_csv()
  else:out.to_csv(p)
  audits.append({'storage_symbol':e['storage_symbol'],'CIK':e['CIK'],'eligible_sessions_through2024':int(mask.sum()),'native500_history_gate':bool(mask.sum()>=500),'path':str(p.relative_to(R)),'sha256':sha(p),'raw_price_sha':sha(root/'adjusted.csv'),'raw_mask_sha':sha(root/'quality_mask.csv')})
 assert all(x['native500_history_gate']for x in audits);dump(B/'reconciled_admission.json',audits);print(json.dumps(audits))
if __name__=='__main__':build()

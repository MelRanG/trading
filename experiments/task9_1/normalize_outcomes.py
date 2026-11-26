"""Recover inclusive-page overlap without new downloads; conflicting revisions block."""
from common import *
import pandas as pd
from quant_harness.investment.operations_data import strict_rows

def merge_pages(frames):
 full=pd.concat(frames).sort_values('date');duplicates=full[full.duplicated('date',keep=False)]
 for date,group in duplicates.groupby('date'):
  if len(group[['open','high','low','close','volume']].drop_duplicates())!=1:raise ValueError('CONFLICTING_PAGE_REVISION:'+date)
 return full.drop_duplicates('date'),len(duplicates)//2

def main():
 for folder in (B/'evaluator_only').glob('*/*'):
  p=folder/'receipt.json';old=json.loads(p.read_text())
  if old['status']=='SAVED':continue
  if (folder/'receipt_v2.json').exists():continue
  s=folder.name;market='KR' if s.endswith(('.KS','.KQ')) else 'US';frames=[]
  for raw in sorted(folder.glob('toss_*.json')):frames.append(strict_rows(json.loads(raw.read_text()),s,'KRW' if market=='KR' else 'USD','Asia/Seoul' if market=='KR' else 'America/New_York','2026-11-14'))
  full,overlaps=merge_pages(frames);full.to_csv(folder/'bars.csv',index=False);chart=json.loads((folder/'chart.json').read_text())['chart']['result'][0];receipt=next(json.loads(x.read_text()) for x in (folder/'raw').glob('*.receipt.json') if json.loads(x.read_text())['source_hash']==sha(folder/'chart.json'))
  freeze(folder/'receipt_v2.json',{'status':'SAVED','source':receipt,'toss_receipts':[{'file':p.name,'sha256':sha(p)} for p in sorted(folder.glob('toss_*.json'))],'events':chart.get('events',{}),'normalized_from_preserved_raw':True,'inclusive_identical_page_overlaps':overlaps,'initial_failure_preserved':'receipt.json','outcome_access':'EVALUATOR_ONLY_AFTER_ALL_SEALS','quality':'PARTIAL_PRICE_ONLY_NO_FULL_ACTION_AUDIT'});print(folder.parent.name,s,len(full),'RECOVERED_NO_API',flush=True)
if __name__=='__main__':main()

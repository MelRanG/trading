from common import *
import pandas as pd,json
from quant_harness.investment.equities import fetch,load_environment
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);Bdir=B/'limited_historical_audit';Bdir.mkdir(exist_ok=True);c=TossOpenApiClient();results=[]
for date in ['2025-07-01','2026-07-01']:
 p=Bdir/('KOSPI_'+date+'.json')
 if p.exists():rows=json.loads(p.read_text())
 else:rows,_=c.get_market_indicator_candles_page('KOSPI',count=3,before=date+'T23:59:59+09:00');dump(p,rows)
 results.append({'date':date,'Toss_KOSPI_rows':rows,'source_hash':sha(p)})
d=OpenDartClient();p=Bdir/'LG_shares_H1_2026.json'
if not p.exists():dump(p,d._request('stockTotqySttus.json',{'corp_code':'00105961','bsns_year':'2026','reprt_code':'11012'}))
p=Bdir/'LG_capital_actions.json'
if not p.exists():dump(p,d._request('list.json',{'corp_code':'00105961','bgn_de':'20250701','end_de':'20260701','pblntf_ty':'B','page_count':100,'sort':'date','sort_mth':'asc','last_reprt_at':'N'}))
for symbol in ['011070','KOSPI']:
 p=Bdir/(symbol+'_naver.txt')
 if p.exists():continue
 try:
  raw,r=fetch('https://api.finance.naver.com/siseJson.naver?symbol='+symbol+'&requestType=1&startTime=20260701&endTime=20260702&timeframe=day',Bdir/'raw');p.write_bytes(raw)
 except Exception as exc:dump(Bdir/(symbol+'_failure.json'),{'error_type':type(exc).__name__})
old=R/'runtime/task9_1';lg=pd.read_csv(old/'third_source/011070.KS/bars.csv').set_index('date');y=pd.read_csv(old/'evaluator_only/2025-06-30/011070.KS/yahoo_bars.csv').set_index('date');idx=pd.read_csv(old/'evaluator_only/2025-06-30/^KS11/bars.csv').set_index('date');shares=json.loads((Bdir/'LG_shares_H1_2026.json').read_text());actions=json.loads((Bdir/'LG_capital_actions.json').read_text());split=json.loads((old/'evaluator_only/2025-06-30/011070.KS/receipt_v2.json').read_text()).get('events',{}).get('splits',{})
report={'original_result_preserved':True,'LG_entry_open':float(lg.loc['2025-07-01','open']),'LG_exit_open':float(lg.loc['2026-07-01','open']),'LG_price_return':float(lg.loc['2026-07-01','open']/lg.loc['2025-07-01','open']-1),'Yahoo_endpoint_parity':all(abs(lg.loc[v,'open']/y.loc[v,'open']-1)<.005 for v in ['2025-07-01','2026-07-01']),'LG_yahoo_declared_splits':split,'DART_latest_dated_share_rows':[v for v in shares.get('list',[]) if v['se'] in ['보통주','보통주식']],'DART_action_report_names':[v['report_nm'] for v in actions.get('list',[])],'DART_action_search_total':actions.get('total_count'),'index_entry_open':float(idx.loc['2025-07-01','open']),'index_exit_open':float(idx.loc['2026-07-01','open']),'index_return':float(idx.loc['2026-07-01','open']/idx.loc['2025-07-01','open']-1),'independent_index_probe':results,'limitation':'Limited endpoint/capital action audit, not full exchange/corporate-action certification'};dump(Bdir/'result.json',report);print('AUDIT',report['LG_price_return'],report['index_return'],len(report['DART_action_report_names']))

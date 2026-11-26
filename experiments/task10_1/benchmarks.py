"""Nontradable S&P500/KOSPI price-index references, separate from ETF proxies."""
from pathlib import Path
import sys,json,datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import fetch

def observe():
 F=R/'runtime/task10_1/forward';out={}
 for m,symbol,zone in [('US','^GSPC','America/New_York'),('KR','^KS11','Asia/Seoul')]:
  plans=sorted((F/'plans'/m).glob('*.json'))
  if not plans:out[m]={'status':'PENDING_REGISTRATION'};continue
  first=json.loads(plans[0].read_text())['next_session']['day'];accepted=sorted((F/'observations'/m).glob('*/accepted.json'))
  if not accepted or accepted[-1].parent.name<first:out[m]={'status':'PENDING_FIRST_COMPLETED_FORWARD_SESSION','symbol':symbol,'first_eligible_session':first};continue
  cutoff=accepted[-1].parent.name;folder=F/'benchmarks'/m/cutoff;folder.mkdir(parents=True,exist_ok=True);rawfile=folder/'response.json';receiptfile=folder/'receipt.json'
  if not rawfile.exists():
   raw,receipt=fetch('https://query1.finance.yahoo.com/v8/finance/chart/'+quote(symbol,safe='')+'?range=1mo&interval=1d',folder/'raw');rawfile.write_bytes(raw);receiptfile.write_text(json.dumps(receipt,indent=2))
  chart=json.loads(rawfile.read_text())['chart']['result'][0]
  if chart['meta']['symbol'].upper()!=symbol:raise ValueError('benchmark identity')
  q=chart['indicators']['quote'][0];rows=[]
  for i,t in enumerate(chart['timestamp']):
   d=datetime.datetime.fromtimestamp(t,datetime.timezone.utc).astimezone(ZoneInfo(zone)).date().isoformat()
   if first<=d<=cutoff and q['open'][i] and q['close'][i]:rows.append({'day':d,'open':q['open'][i],'close':q['close'][i]})
  prior=sorted((F/'benchmarks'/m).glob('*/result.json'))
  anchor=json.loads(prior[0].read_text()) if prior else None
  if not rows or rows[-1]['day']!=cutoff or (anchor is None and rows[0]['day']!=first):out[m]={'status':'INSUFFICIENT_INDEX_MARKS','symbol':symbol};continue
  start_open=anchor['start_open'] if anchor else rows[0]['open']
  if anchor and anchor['start_session']!=first:raise ValueError('frozen index start changed')
  result={'symbol':symbol,'classification':'NONTRADABLE_PRICE_INDEX_NOT_TOTAL_RETURN','currency':'USD' if m=='US' else 'KRW','start_session':first,'end_session':cutoff,'start_open':start_open,'end_close':rows[-1]['close'],'price_return_pct':(rows[-1]['close']/start_open-1)*100,'source_receipt':json.loads(receiptfile.read_text()),'status':'OBSERVED','ETF_is_separate_reference':True}
  p=folder/'result.json'
  if p.exists():assert json.loads(p.read_text())==result
  else:p.write_text(json.dumps(result,indent=2))
  out[m]=result
 return out
if __name__=='__main__':
 try:print(json.dumps(observe(),indent=2))
 except Exception as exc:print(json.dumps({'status':'FAILED_CLOSED','error_type':type(exc).__name__}))

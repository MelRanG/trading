"""Two already-listed earlier earnings releases; preserve, do not replace quarterly evidence."""
import collect,io,zipfile,json
B=collect.B;out=[]
for item in json.loads((B/'dart_lists.json').read_text()):
 if item['mode']!='earnings':continue
 for row in item['filings']:
  if '연결재무제표기준영업(잠정)실적' not in row['report_nm']:continue
  raw=collect.c._request('document.xml',{'rcept_no':row['rcept_no']},binary=True);folder=B/'earlier_earnings'/row['rcept_no'];folder.mkdir(parents=True,exist_ok=True)
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   for name in z.namelist():
    if name.lower().endswith('.xml'):(folder/collect.Path(name).name).write_bytes(z.read(name))
  out.append({'symbol':item['symbol'],'filing':row,'quarterly_report_is_later':True})
collect.dump(B/'earlier_releases.json',out);print('EARLIER_RELEASES',len(out))

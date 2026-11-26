"""Five bounded official SEC requests; declared identity, no bypass/proxies or retries."""
from pathlib import Path
import sys,os,json,time,hashlib,datetime,gzip,socket,subprocess
from urllib.request import Request,urlopen,getproxies
from urllib.error import HTTPError
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
load_environment(R);B=R/'runtime/sec_access_diagnostic';B.mkdir(exist_ok=True)
identity=os.getenv('SEC_USER_AGENT') or os.getenv('EDGAR_IDENTITY') or 'ansy tpdud285@naver.com'
# Same configured real contact, explicit application identity; no browser impersonation.
declared='QuantHarness Research '+identity if 'QuantHarness' not in identity else identity
base='https://data.sec.gov/submissions/CIK0000789019.json'
cases=[('python_original',base,{'User-Agent':identity,'Accept':'application/json,text/html'}),('python_documented',base,{'User-Agent':declared,'Accept':'application/json','Accept-Encoding':'gzip, deflate'}),('python_companyconcept','https://data.sec.gov/api/xbrl/companyconcept/CIK0000789019/us-gaap/Revenues.json',{'User-Agent':declared,'Accept':'application/json','Accept-Encoding':'gzip, deflate'}),('python_documentation','https://www.sec.gov/search-filings/edgar-application-programming-interfaces',{'User-Agent':declared,'Accept':'text/html','Accept-Encoding':'gzip, deflate'})]
records=[]
for name,url,headers in cases:
 p=B/(name+'.json')
 if p.exists():records.append(json.loads(p.read_text()));continue
 row={'name':name,'url':url,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'headers_without_identity':{k:v for k,v in headers.items() if k!='User-Agent'},'user_agent_sha256':hashlib.sha256(headers['User-Agent'].encode()).hexdigest(),'user_agent_has_contact':'@' in headers['User-Agent'],'user_agent_has_application':'QuantHarness' in headers['User-Agent']};start=time.monotonic()
 try:
  try:response=urlopen(Request(url,headers=headers),timeout=20)
  except HTTPError as e:response=e
  with response as r:
   raw=r.read(2000001);row.update(status=r.status,headers={k:v for k,v in r.headers.items() if k.lower() not in ['set-cookie']},final_url=r.geturl());enc=r.headers.get('Content-Encoding','')
  if enc=='gzip':raw=gzip.decompress(raw)
  (B/(name+'.body')).write_bytes(raw);row.update(bytes=len(raw),body_sha256=hashlib.sha256(raw).hexdigest())
 except Exception as e:row.update(error_type=type(e).__name__)
 row['seconds']=time.monotonic()-start;p.write_text(json.dumps(row,indent=2));records.append(row);time.sleep(1)
# Compare an independent standard HTTP client at identical endpoint/identity, normal HTTPS1.1.
p=B/'curl.json'
if not p.exists():
 args=['curl','--silent','--show-error','--max-time','20','--compressed','-A',declared,'-H','Accept: application/json','-D',str(B/'curl.headers'),'-o',str(B/'curl.body'),'-w','%{json}',base];start=time.monotonic();r=subprocess.run(args,capture_output=True,text=True);row={'name':'curl_same_documented','url':base,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':r.returncode,'seconds':time.monotonic()-start,'user_agent_sha256':hashlib.sha256(declared.encode()).hexdigest(),'curl':json.loads(r.stdout) if r.returncode==0 else None,'error':r.stderr[:400]};p.write_text(json.dumps(row,indent=2))
(B/'environment.json').write_text(json.dumps({'proxy_schemes_configured':list(getproxies()),'python':sys.version.split()[0],'dns':{host:sorted(set(x[4][0] for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM))) for host in ['data.sec.gov','www.sec.gov']},'max_network_requests':5,'no_retries':True,'no_strategy_changes':True},indent=2))
for r in records:print(r['name'],r.get('status'),r.get('headers'),r.get('seconds'))
print('curl',json.loads(p.read_text()).get('curl',{}).get('http_code'))

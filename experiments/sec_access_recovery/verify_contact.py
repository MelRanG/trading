"""Use existing Git user contact, not invented identity. At most two SEC GETs."""
from pathlib import Path
import subprocess,datetime,json,time,hashlib,re,os
B=Path(__file__).resolve().parents[2]/'runtime/sec_access_recovery';B.mkdir(exist_ok=True)
mail=subprocess.check_output(['git','config','--get','user.email'],text=True).strip();assert re.fullmatch(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',mail);assert not any(x in mail.lower() for x in ['example.','noreply','localhost'])
ua='QuantHarness/1.0 '+mail
for name,url in [('submissions','https://data.sec.gov/submissions/CIK0000789019.json'),('companyconcept','https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/AccountsPayableCurrent.json')]:
 p=B/(name+'.json')
 if p.exists():continue
 r=subprocess.run(['curl','-4','-sS','--max-time','25','-A',ua,'-D',str(B/(name+'.headers')),'-o',str(B/(name+'.body')),'-w','%{json}',url],capture_output=True,text=True);c=json.loads(r.stdout) if r.returncode==0 else {};d={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'url':url,'contact_source':'existing git config user.email','identity_sha256':hashlib.sha256(ua.encode()).hexdigest(),'curl':c,'returncode':r.returncode,'error':r.stderr[:200]}
 if c.get('http_code')==200:
  data=json.loads((B/(name+'.body')).read_text());d['expected_entity_valid']=str(data.get('cik')).lstrip('0')==('789019' if name=='submissions' else '320193');assert d['expected_entity_valid']
 p.write_text(json.dumps(d,indent=2));print(name,c.get('http_code'),c.get('remote_ip'));time.sleep(1)

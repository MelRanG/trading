"""Change SEC contact settings only after successful real-identity probes."""
from pathlib import Path
import os,json,subprocess,hashlib,datetime
from dotenv import dotenv_values,set_key
R=Path(__file__).resolve().parents[2];B=R/'runtime/sec_access_recovery';env=R/'.env'
assert all(json.loads((B/(n+'.json')).read_text())['curl']['http_code']==200 for n in ['submissions','companyconcept'])
mail=subprocess.check_output(['git','config','--get','user.email'],text=True).strip();identity='QuantHarness/1.0 '+mail;before=dict(dotenv_values(env));private=B/'identity_before.private.json'
if not private.exists():
 fd=os.open(private,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:json.dump({k:before.get(k) for k in ['SEC_USER_AGENT','EDGAR_IDENTITY']},f)
for key in ['SEC_USER_AGENT','EDGAR_IDENTITY']:set_key(env,key,identity,quote_mode='always')
after=dict(dotenv_values(env));assert {k:v for k,v in before.items() if k not in ['SEC_USER_AGENT','EDGAR_IDENTITY']}=={k:v for k,v in after.items() if k not in ['SEC_USER_AGENT','EDGAR_IDENTITY']}
for p in [R/'runtime/task5/service.env']:
 if p.exists():
  d=dotenv_values(p);assert not any(d.get(k) and d[k]!=identity for k in ['SEC_USER_AGENT','EDGAR_IDENTITY']),'CONFLICTING_SERVICE_IDENTITY'
(B/'configuration_change.json').write_text(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'settings_file':'.env','changed_keys':['SEC_USER_AGENT','EDGAR_IDENTITY'],'source':'Existing Git user.email, same user configured Gmail contact','identity_sha256':hashlib.sha256(identity.encode()).hexdigest(),'non_SEC_settings_unchanged':True,'strategies_services_permissions_unchanged':True,'private_rollback_file':'identity_before.private.json'},indent=2));print('SEC_IDENTITY_SETTINGS_UPDATED_OTHER_VALUES_UNCHANGED')

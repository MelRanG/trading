import hashlib,json,tempfile,unittest
from pathlib import Path
from model_relay import Relay
class RelayHistoryTests(unittest.TestCase):
 def test_failed_request_is_not_overwritten_or_reexecuted(self):
  with tempfile.TemporaryDirectory() as d:
   body={'model':'gpt-4o','messages':[]};fingerprint=hashlib.sha256(('gpt-6.1-terra'+'\n'+json.dumps(body,sort_keys=True)).encode()).hexdigest();p=Path(d)/'terra';p.mkdir();r=p/(fingerprint+'.reserved.json');r.write_text('{"status":"FAILED","measured_tokens":0}');before=r.read_bytes()
   with self.assertRaisesRegex(ValueError,'never overwrite'):Relay(d).call('terra',body)
   self.assertEqual(before,r.read_bytes())
if __name__=='__main__':unittest.main()

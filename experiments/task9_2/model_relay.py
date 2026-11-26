from pathlib import Path
import importlib.util,socketserver,argparse
R=Path(__file__).resolve().parents[2];p=R/'experiments/task8b/model_relay.py';spec=importlib.util.spec_from_file_location('completion_transport',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.__file__=__file__;m.BUDGET={'research':{'calls':6,'tokens':420000}}
# Require a worst-case90k reservation before each new native call. Native CLI
# exposes no trusted hard token cap, so disclose that and retain every attempt.
original_call=m.Relay.call
def bounded_call(self,engine,body):
 import json
 directory=self.folder/engine
 rows=[json.loads(p.read_text()) for p in directory.glob('*.reserved.json')] if directory.exists() else []
 if any(r.get('status') in ['RESERVED','TIMEOUT'] for r in rows):raise ValueError('unknown usage; stop')
 if sum(r.get('measured_tokens',0) for r in rows)+90000>420000:raise ValueError('insufficient worst-case call reservation')
 return original_call(self,engine,body)
m.Relay.call=bounded_call
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--socket',required=True);a.add_argument('--evidence',required=True);x=a.parse_args();p=Path(x.socket)
 if p.exists():raise ValueError('inspect existing socket first')
 server=socketserver.ThreadingUnixStreamServer(str(p),m.Handler);server.relay=m.Relay(x.evidence);p.chmod(0o600)
 try:server.serve_forever()
 finally:server.server_close();p.unlink(missing_ok=True)

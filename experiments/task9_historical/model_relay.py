"""Reuse the existing audited Codex transport; separate budget/attempt namespace."""
from pathlib import Path
import importlib.util,json,socketserver,argparse
R=Path(__file__).resolve().parents[2]
p=R/'experiments/task8b/model_relay.py';spec=importlib.util.spec_from_file_location('task9_relay_transport',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.__file__=__file__
c=json.loads((Path(__file__).parent/'contract.json').read_text())
m.BUDGET={k:{'calls':v['llm_calls_max'],'tokens':v['known_token_budget']} for k,v in c['stages'].items() if k in ('representative','five_dates')}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--socket',required=True);a.add_argument('--evidence',required=True);args=a.parse_args();p=Path(args.socket)
 if p.exists():raise ValueError('existing relay socket: inspect first')
 server=socketserver.ThreadingUnixStreamServer(str(p),m.Handler);server.relay=m.Relay(args.evidence);p.chmod(0o600)
 try:server.serve_forever()
 finally:server.server_close();p.unlink(missing_ok=True)

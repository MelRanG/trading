"""Reuse the existing credential-isolated transport, Task13 budget scope only."""
from pathlib import Path
import importlib.util,json,socketserver
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r1_2'
spec=importlib.util.spec_from_file_location('prior_transport',R/'experiments/task13_r1_2/transport.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.BUDGET={'quanta':{'calls':8,'tokens':180000}}
p=Path('/tmp/quant-task13-r1-2.sock')
if p.exists():raise ValueError('socket already exists; inspect before cleanup')
s=socketserver.ThreadingUnixStreamServer(str(p),m.Handler);s.relay=m.Relay(B/'model_calls');p.chmod(0o600)
try:s.serve_forever()
finally:s.server_close();p.unlink(missing_ok=True)

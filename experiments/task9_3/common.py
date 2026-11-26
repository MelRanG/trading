from pathlib import Path
import sys,json,hashlib,datetime
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
B=R/'runtime/task9_3';B.mkdir(exist_ok=True)
def dump(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()
def freeze(p,x):
 p=Path(p)
 if p.exists():assert json.loads(p.read_text())==json.loads(json.dumps(x,ensure_ascii=False)),'immutable conflict: '+str(p)
 else:dump(p,x)
C=json.loads((Path(__file__).parent/'contract.json').read_text())

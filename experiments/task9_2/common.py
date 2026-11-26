from pathlib import Path
import sys,json,hashlib,datetime
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
B=R/'runtime/task9_2';B.mkdir(exist_ok=True)
def dump(path,obj):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def freeze(path,obj):
 path=Path(path)
 if path.exists():assert json.loads(path.read_text())==obj,'immutable conflict '+str(path)
 else:dump(path,obj)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

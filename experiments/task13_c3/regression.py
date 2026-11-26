"""Reuse unchanged mandatory C1 safety snapshot checks; output namespace only."""
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'task13_c1/regression.py';s=p.read_text();old="B=R/'runtime/task13_c1'";assert s.count(old)==1
exec(compile(s.replace(old,"B=R/'runtime/task13_c3'"),str(p),'exec'),{'__file__':str(p),'__name__':'__main__'})

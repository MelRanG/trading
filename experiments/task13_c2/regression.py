"""Reuse C1's unchanged mandatory safety checks, changing output directory only."""
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'task13_c1/regression.py'
s=p.read_text();old="B=R/'runtime/task13_c1'";assert s.count(old)==1
exec(compile(s.replace(old,"B=R/'runtime/task13_c2'"),str(p),'exec'),{'__file__':str(p),'__name__':'__main__'})

"""Local JSONB signed-zero compatibility; never mutates the global Store hash."""
import math

def canonical_zero(value):
 if isinstance(value,float) and value==0:return 0.0
 if isinstance(value,dict):return {k:canonical_zero(v) for k,v in value.items()}
 if isinstance(value,list):return [canonical_zero(v) for v in value]
 return value

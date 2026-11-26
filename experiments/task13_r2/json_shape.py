"""Repair JSON escaping only in mathematical formulation strings, never code or numeric fields."""
import json,re

def repair_formulation(text):
 try:json.loads(text);return text,False
 except json.JSONDecodeError:pass
 def field(m):
  body=re.sub(r'(?<!\\)\\(?![\\\"])',lambda x:'\\\\',m.group(2))
  return m.group(1)+body+m.group(3)
 result=re.sub(r'("formulation"\s*:\s*")((?:\\.|[^"\\])*)(")',field,text)
 json.loads(result)
 return result,result!=text

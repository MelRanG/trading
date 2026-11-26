"""Normalize leading arithmetic minus for upstream AST analysis only."""
import ast,re

def normalized(expression):
 e=expression.strip()
 try:root=ast.parse(re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)',r'V_\1',e),mode='eval').body
 except SyntaxError:return expression
 return 'SUBTRACT(0,'+e[1:]+')' if isinstance(root,ast.UnaryOp) and isinstance(root.op,ast.USub) and e.startswith('-') and not e.startswith('--') else expression

def attach(regulator):
 original=regulator.evaluate
 regulator.evaluate=lambda expression:original(normalized(expression))
 return regulator

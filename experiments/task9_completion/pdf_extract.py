from pathlib import Path
from pypdf import PdfReader
B=Path('/work')
for p in B.rglob('*.pdf'):
 try:
  text='\n'.join(page.extract_text() or '' for page in PdfReader(p).pages);p.with_suffix('.pdf.txt').write_text(text);print(str(p),len(text),flush=True)
 except Exception as e:print(str(p),type(e).__name__,flush=True)

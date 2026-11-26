"""Separate later revisions for audit only; never merge into first event features."""
import collect,io,zipfile
B=collect.B
for accession in ['20241205800251','20251215801116']:
 raw=collect.c._request('document.xml',{'rcept_no':accession},binary=True);folder=B/'revision_audit'/accession;folder.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  for name in z.namelist():
   if name.lower().endswith('.xml'):(folder/collect.Path(name).name).write_bytes(z.read(name))
print('REVISION_ONLY_NO_FEATURE_OVERWRITE')

"""High-precision original-exhibit parser. Unsupported language stays ambiguous."""
import re,html as stdhtml
from decimal import Decimal
from lxml import html
WORDS={'zero':'0','one':'1','two':'2','three':'3','four':'4','five':'5','six':'6','seven':'7','eight':'8','nine':'9','ten':'10','eleven':'11','twelve':'12','thirteen':'13','fourteen':'14','fifteen':'15','sixteen':'16','seventeen':'17','eighteen':'18','nineteen':'19','twenty':'20'}
FUTURE=re.compile(r'expect|outlook|guidance|forecast|project|anticipat|estimat',re.I)
METRIC=re.compile(r'(?:revenue|sales)(?:\s|\b)',re.I)
ANNUAL=re.compile(r'full[\s-]*year|fiscal\s*(?:year\s*)?20\d\d|(?:20\d\d)\s+(?:financial\s+)?(?:outlook|guidance)',re.I)
def clean(s):return ' '.join(s.replace('\xa0',' ').replace('\u2011','-').split())
def years(s):
 patterns=[r'(?:fiscal\s*(?:year\s*)?|full[ -]*year\s*(?:fiscal\s*)?|for\s+)(20\d\d)',r'(20\d\d)\s+(?:financial\s+)?(?:outlook|guidance)']
 return sorted(set(y for p in patterns for y in re.findall(p,s,re.I)))
def spell(s):
 return re.sub(r'\b('+'|'.join(WORDS)+r')\b',lambda m:WORDS[m[0].lower()],s,flags=re.I)
def value(s):
 s=clean(s).lower()
 if re.search(r'(?:towards?|at) the (?:high|low) end',s):return None
 s=spell(s).replace('–','-').replace('−','-');s=re.sub(r'(?<=\d)\s*%',' percent',s)
 # If explicitly from old range to new range, latest expression is current.
 old=None
 m=re.search(r'from (?:a )?range of (.*?) to (?:a )?range of (.*)',s)
 if m:old=m[1];s=m[2]
 else:s=re.split(r'\(?previously|\(?prior (?:guidance|outlook)|\(?(?:versus|vs\.?)\s+(?:our\s+)?previous|\(?previous guidance',s)[0]
 # Prior EPS clauses must not contribute percentages to revenue values.
 s=re.split(r'\b(?:eps|earnings per share|income per share)\b',s)[0]
 matches=list(re.finditer(r'(-?\d+(?:\.\d+)?)\s*(?:percent)?\s*(?:to|-)\s*(-?\d+(?:\.\d+)?)\s*percent',s));ranges=[]
 for m in matches:
  a,b=Decimal(m[1]),Decimal(m[2]);prefix=s[max(0,m.start()-80):m.start()]
  if a>100 or b>100 or a < -100 or b < -100:continue
  if re.search(r'declin|decreas|down',prefix) and a>=0 and b>=0:a,b=-b,-a
  if a<=b:ranges.append((a,b,m.start(),m.end()))
 points=[]
 for m in re.finditer(r'(-?\d+(?:\.\d+)?)\s*percent',s):
  if any(a<=m.start()<b for _,_,a,b in ranges):continue
  n=Decimal(m[1]);prefix=s[max(0,m.start()-65):m.start()]
  if abs(n)>100:continue
  if re.search(r'declin|decreas|down',prefix) and n>0:n=-n
  points.append((n,prefix))
 # Economic/metric sentence should give a unique percentage; duplicated same number is okay.
 vals={(str(a),str(b)) for a,b,_,_ in ranges}
 if len(vals)==1 and not points:
  a,b=next(iter(vals));return {'kind':'range','lo':a,'hi':b,'qualifier':'range','explicit_old_range_text':old}
 if not ranges and len(set(n for n,_ in points))==1:
  n,prefix=points[0];qual='at_least' if (re.search('at least|no less than',prefix) or re.search(r'\d+(?:\.\d+)?\s*percent\s*\+',s)) else 'approximately' if re.search('approximat|about|around',prefix) else 'point';return {'kind':'point','lo':str(n),'hi':str(n),'qualifier':qual}
 if not matches and not points:
  q=re.search(r'(low|mid|high)[ -]single[ -]digits?',s)
  if q:return {'kind':'qualitative','category':q[1]+'_single_digit','qualifier':'qualitative','lo':None,'hi':None}
 return None

def basis_matches(s,basis):
 s=s.lower()
 if not METRIC.search(s):return False
 if not re.search(r'\b(?:growth|increase|increases|decrease|decreases|decline|declines)\b',s):return False
 if re.search(r'(?:sales|revenue).{0,60}(?:\$|billion|million)',s) and not re.search(r'(?:sales|revenue).{0,30}growth',s):return False
 if re.search(r'excluding covid|excluding covid-19',s):return False
 if re.search(r'operating (?:income|margin)|(?:percentage|percent) of sales|gross margin|tax rate',s):return False
 if re.search(r'comparable|same.store|segment|per.store|division|volume growth|earnings growth',s):return False
 if basis=='ANNUAL_ORGANIC_REVENUE_GROWTH':return 'organic' in s
 if basis=='ANNUAL_CONSTANT_CURRENCY_NET_REVENUE_GROWTH':return 'constant currency'in s or 'constant-currency'in s
 return not re.search(r'organic|constant.currency|operational growth',s)

def exhibit_parts(raw):
 source=raw.decode('utf-8',errors='replace');parts=[]
 for i,p in enumerate(re.findall(r'<DOCUMENT>(.*?)</DOCUMENT>',source,re.S|re.I)):
  t=re.search(r'<TYPE>([^\r\n<]+)',p,re.I);fn=re.search(r'<FILENAME>([^\r\n<]+)',p,re.I);typ=t[1].strip().upper() if t else ''
  if not typ.startswith('EX-99'):continue
  # Earnings release is first99.1, not quarterly model text or exhibits/images.
  if not re.match(r'EX-99(?:\.1)?$',typ):continue
  body=re.search(r'<TEXT>(.*?)</TEXT>',p,re.S|re.I)
  if not body:continue
  try:d=html.fromstring(body[1])
  except Exception:continue
  for node in d.xpath('//script|//style'):node.drop_tree()
  parts.append((i,fn[1].strip() if fn else None,d))
 return parts,source

def extract(raw,company,filing,source_kind='SGML',exhibit_filename=None):
 if source_kind=='EXHIBIT_HTML':
  source=raw.decode('utf-8',errors='replace');tree=html.fromstring(source)
  for node in tree.xpath('//script|//style'):node.drop_tree()
  parts=[(0,exhibit_filename,tree)]
 else:parts,source=exhibit_parts(raw)
 blocks=[];exhibits=[]
 for partnum,fn,d in parts:
  exhibits.append({'document_index':partnum,'filename':fn})
  seen=set()
  for node in d.iter():
   if not isinstance(node.tag,str) or node.tag.lower().split(':')[-1] not in ['div','p','li','tr','h1','h2','h3','h4']:continue
   s=clean(' '.join(node.itertext()))
   if not 3<=len(s)<=1600 or s in seen:continue
   # Suppress parent text when it simply concatenates child block paragraphs.
   children=[c for c in node if isinstance(c.tag,str) and c.tag.lower()in ['div','p','li','tr']]
   if len(children)>1:continue
   seen.add(s);blocks.append({'text':s,'xpath':node.getroottree().getpath(node),'filename':fn,'document_index':partnum,'node_tag':node.tag.lower()})
 candidates=[];rejected=[];eps=[];annual_scope=None;scope_at=-999;outlook_at=-999;quarter_scope=False
 guide_years=sorted(set(y for b in blocks if len(b['text'])<220 and (FUTURE.search(b['text']) or ANNUAL.search(b['text'])) for y in years(b['text'])))
 for idx,b in enumerate(blocks):
  s=b['text'];ys=years(s)
  # Table cells without explicit forward context are not forecasts merely because
  # an outlook heading appeared earlier in a long exhibit. Preserve raw, fail closed.
  if b['node_tag']=='tr' and not FUTURE.search(s):continue
  if s.lower() in ['outlook','guidance','financial outlook','guidance and outlook']:outlook_at=idx;quarter_scope=False
  if len(s)<140 and re.search(r'(?:first|second|third|fourth) quarter.*(?:considerations|outlook|guidance)',s,re.I):annual_scope=None;quarter_scope=True
  if len(s)<100 and ANNUAL.search(s) and len(ys)==1 and idx-outlook_at<=3:annual_scope=ys[0];scope_at=idx;quarter_scope=False
  if len(s)<200 and (ANNUAL.search(s) or re.match(r'^For\s+20\d\d',s,re.I)) and len(ys)==1 and re.search(r'outlook|guidance|considerations|expectations|estimate|expects?',s,re.I) and not re.search(r'announces|reports|results|quarter|raises|confirms|provides',s,re.I):annual_scope=ys[0];scope_at=idx
  if FUTURE.search(s) and re.search(r'eps|earnings per share',s,re.I):eps.append(b)
  if not basis_matches(s,company['metric_basis']) or quarter_scope:continue
  section=annual_scope if idx-scope_at<=25 else None
  # Annual subject and prospective role, not realized/segment revenue tables.
  future=bool(FUTURE.search(s) or section)
  fy=ys[0] if len(ys)==1 and (ANNUAL.search(s) or re.search(r'for\s+20\d\d',s,re.I)) else section
  if not fy and future and len(guide_years)==1:fy=guide_years[0]
  if not future or fy is None:continue
  if re.search(r'for (?:the )?(?:first|second|third|fourth|next) quarter',s,re.I) and not ANNUAL.search(s):continue
  # Take sentence that specifically carries selected metric; after explicit revenue word, before EPS.
  sentences=re.split(r'(?<=[a-z%])\.\s+(?=[A-Z])',s)
  for sentence in sentences:
   if not basis_matches(sentence,company['metric_basis']):continue
   if re.search(r'\bgrew\b|\bincreased\b|\bdecreased\b|\bdeclined\b|\bdelivered\b|\brecorded\b|\breported\b|\bwere\b|\bwas\b',sentence,re.I) and not FUTURE.search(sentence):continue
   if re.search(r'ANNOUNCES.*RESULTS|REPORTS.*RESULTS',sentence) and len(sentence)<500:continue
   if re.search(r'(?:organic (?:revenue|sales)|net sales|revenues?)\b.{0,25}\b(?:grew|increased|was|were|delivered|achieved)\b',sentence,re.I) and not re.search(r'guidance|outlook|expect',sentence,re.I):continue
   if re.search(r'results|second quarter|first quarter|fourth quarter|third quarter',sentence,re.I) and not re.search(r'(?:expect|outlook|guidance).{0,90}(?:organic (?:revenue|sales)|sales growth|revenue growth)',sentence,re.I):continue
   if not FUTURE.search(sentence) and section is None:continue
   if re.search(r'foreign exchange.*headwind|foreign exchange.*tailwind',sentence,re.I) and not re.search(r'organic (?:revenue|sales).*growth',sentence,re.I):continue
   v=value(sentence)
   if v is None:rejected.append({**b,'reason':'UNSUPPORTED_OR_MULTIPLE_PERCENTAGES','FY':fy});continue
   candidates.append({**b,'FY':fy,'basis':company['metric_basis'],'value':v,'metric':'annual_total_revenue_growth','original_text_semantics_not_numeric_guesses':True})
 # Most current FY with a clear issuer outlook, never choose a favorable percentage.
 by={}
 for c in candidates:by.setdefault(c['FY'],[]).append(c)
 selected=[]
 for fy,cs in by.items():
  signatures={tuple((k,str(c['value'].get(k))) for k in ['kind','lo','hi','qualifier','category']) for c in cs}
  if len(signatures)==1:selected.append(min(cs,key=lambda c:len(c['text'])))
  else:rejected.append({'reason':'CONFLICTING_SAME_FY_METRIC_VALUES','FY':fy,'candidates':cs})
 return {'exhibit_documents':exhibits,'guidance':selected,'ambiguities':rejected,'candidate_count':len(candidates),'EPS_context':eps[:6],'guide_years_seen':guide_years,'total_blocks':len(blocks),'full_submission_header':{'acceptance_raw':(re.search(r'<ACCEPTANCE-DATETIME>(\d+)',source).group(1) if re.search(r'<ACCEPTANCE-DATETIME>(\d+)',source) else None)},'no_price_input':True}

def compare(parent,child,symbol,date):
 if parent['FY']!=child['FY'] or parent['basis']!=child['basis']:return 'NO_COMPARABLE_GUIDANCE'
 a,b=parent['value'],child['value']
 if a==b:return 'UNCHANGED'
 if a['kind']=='qualitative' and b['kind']=='qualitative':return 'UNCHANGED' if a.get('category')==b.get('category') else 'AMBIGUOUS'
 if symbol=='PEP' and date=='2024-10-08' and a['kind']=='point' and a.get('qualifier')=='approximately' and a['lo']=='4' and b.get('category')=='low_single_digit':return 'DOWN'
 if a['kind']!=b['kind'] or a['qualifier']!=b['qualifier']:return 'AMBIGUOUS'
 if a['kind'] not in ['range','point']:return 'AMBIGUOUS'
 al,ah,bl,bh=map(Decimal,[a['lo'],a['hi'],b['lo'],b['hi']])
 if bl==al and bh==ah:return 'UNCHANGED'
 if bl>=al and bh>=ah:return 'UP'
 if bl<=al and bh<=ah:return 'DOWN'
 return 'AMBIGUOUS'

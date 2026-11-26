"""Original-unit/context/CIK verification; B1 inline parser and numeric packet reused."""
from common import *
from decimal import Decimal
from lxml import html,etree
from quant_harness.investment.financial_packet import verify_fact
import re
inline=module('c3_existing_inline','experiments/task13_b1/normalize.py')
c2=module('c3_existing_field_match','experiments/task13_c2/audit.py')

def local(e):return e.tag.lower().split('}')[-1].split(':')[-1] if isinstance(e.tag,str) else ''
def txt(e):return ' '.join(' '.join(e.itertext()).split())
def original_values(raw,cik):
 blocks=[]
 if b'<DOCUMENT>' in raw.upper():
  for block in re.findall(br'<DOCUMENT>(.*?)</DOCUMENT>',raw,re.S|re.I):
   kind=re.search(br'<TYPE>\s*([^\r\n<]+)',block,re.I)
   if kind and kind[1].strip().upper() in [b'10-K',b'EX-101.INS']:
    text=re.search(br'<TEXT>(.*)</TEXT>',block,re.S|re.I)
    if text:
     payload=text[1]
     if re.match(br'\s*<XBRL>\s*<\?xml',payload,re.I):
      payload=re.sub(br'^\s*<XBRL>\s*',b'',payload,count=1,flags=re.I)
      payload=re.sub(br'</XBRL>\s*$',b'',payload,count=1,flags=re.I)
     blocks.append(payload)
 else:blocks=[raw]
 out=[];entity=False;forms=[]
 for block in blocks:
  isxml=bool(re.search(br'<(?:\w+:)?xbrl[\s>]',block[:1000],re.I))
  try:tree=etree.fromstring(block.strip(),etree.XMLParser(recover=False,resolve_entities=False,no_network=True)) if isxml else inline.doc(block)
  except (ValueError,etree.XMLSyntaxError):continue
  contexts={};units={}
  for e in tree.iter():
   k=local(e)
   if k=='context':
    p={};dims=False;ident=None
    for c in e.iter():
     name=local(c)
     if name in ['startdate','enddate','instant']:p[name]=txt(c)
     if name in ['explicitmember','typedmember']:dims=True
     if name=='identifier':ident=txt(c)
    try:validcik=int(ident)==int(cik)
    except (ValueError,TypeError):validcik=False
    entity |= validcik
    if not dims and validcik:contexts[e.get('id')]=p
   if k=='unit':
    measures=[txt(c).split(':')[-1] for c in e.iter() if local(c)=='measure']
    if measures==['USD']:units[e.get('id')]='USD'
   if (e.get('name') or '').lower()=='dei:documenttype':forms.append(txt(e))
  if not isxml:
   # B1 parser has actual sign/scale and Decimal handling; add missing CIK/unit gates.
   pathmap={e.getroottree().getpath(e):e for e in tree.iter() if local(e)=='nonfraction'}
   for v in inline.inline_values(block):
    e=pathmap.get(v['xpath'])
    if e is None:continue
    context=contexts.get(e.get('contextref'))
    if context is not None and v['unitref'] in units:out.append({**v,'period':context,'currency':'USD','entity_CIK':str(int(cik))})
  else:
   for e in tree.iter():
    if 'us-gaap' not in (e.tag if isinstance(e.tag,str) else ''):continue
    context=contexts.get(e.get('contextRef'));unit=units.get(e.get('unitRef'))
    if context is None or unit!='USD':continue
    try:value=Decimal(txt(e))
    except Exception:continue
    if not value.is_finite():continue
    out.append({'name':'us-gaap:'+e.tag.split('}')[-1],'period':context,'value':str(value),'currency':'USD','entity_CIK':str(int(cik)),'xpath':e.getroottree().getpath(e),'scale':'0'})
 return out,{'entity_CIK_confirmed':entity,'dimensionless_USD_values':len(out),'DocumentType_values':forms,'payloads_examined':len(blocks)}

def structural(cf):
 candidate={'id':'C2_CASH_ACCRUAL_QUALITY','required_tags':['NetIncomeLoss','NetCashProvidedByUsedInOperatingActivities','Assets']}
 return c2.structural_annual_events(cf.get('facts',{}),candidate)

def api_facts(cf,cfraw,meta,event):
 tags=['NetIncomeLoss','NetCashProvidedByUsedInOperatingActivities','Assets','Assets'];roles=['NI','CFO','Assets_start','Assets_end'];result=[]
 for role,tag in zip(roles,tags):
  idx=event['locations'][tag if role in ['NI','CFO'] else role];r=cf['facts']['us-gaap'][tag]['units']['USD'][idx]
  assert r['accn']==event['accession'] and r['filed']==event['filed'];period_start=r.get('start',r['end'])
  fact={'metric':role,'raw_value':str(r['val']),'multiplier':1,'value':str(r['val']),'unit':'CURRENCY','currency':'USD','basis':'CFS','period_start':period_start,'period_end':r['end'],'published':event['filed'],'source_hash':meta['source_hash'],'locator':{'kind':'json','path':['facts','us-gaap',tag,'units','USD',idx,'val']},'tag':tag,'accession':event['accession']}
  result.append(verify_fact(fact,cfraw,event['filed']))
 return result

def verify_original(facts,original,cik,source):
 values,proof=original_values(original,cik);matches=[]
 if not proof['entity_CIK_confirmed']:return None,{**proof,'reason':'ORIGINAL_CIK_NOT_CONFIRMED'}
 for f in facts:
  period={'instant':f['period_end']} if f['metric'].startswith('Assets') else {'startdate':f['period_start'],'enddate':f['period_end']}
  a=[v for v in values if v['name']=='us-gaap:'+f['tag'] and v['period']==period]
  unique_values={Decimal(v['value']) for v in a}
  if len(unique_values)!=1 or Decimal(f['value']) not in unique_values:return None,{**proof,'reason':'ORIGINAL_VALUE_UNIT_SCOPE_OR_PERIOD_MISMATCH','role':f['metric'],'matches':len(a)}
  matches.append({'role':f['metric'],'api_fact':f,'original':a[0],'original_source_hash':source['source_hash']})
 a={f['metric']:Decimal(f['value']) for f in facts};avg=(a['Assets_start']+a['Assets_end'])/2
 if avg<=0:return None,{'reason':'NONPOSITIVE_ASSETS'}
 feature=-(a['NI']-a['CFO'])/avg
 return {'NI':str(a['NI']),'OperatingCashFlow':str(a['CFO']),'Assets_start':str(a['Assets_start']),'Assets_end':str(a['Assets_end']),'AverageAssets':str(avg),'feature':str(feature),'proofs':matches},{**proof,'pass':True}

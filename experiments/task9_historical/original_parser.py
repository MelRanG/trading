"""Strict decoding for accession XML; reported UTF-8 may actually be CP949."""
import re,hashlib
from lxml import etree

def parse_xml(raw):
 try:text=raw.decode('utf-8');encoding='utf-8'
 except UnicodeDecodeError:text=raw.decode('cp949');encoding='cp949 (declaration mismatch)'
 text=re.sub(r'<\?xml[^>]*\?>','',text,count=1)
 # DART presentation line-break entity, not a numeric or financial fact.
 text=text.replace('&cr;','\n').replace('&nbsp;',' ')
 parser=etree.XMLParser(recover=True,resolve_entities=False,no_network=True)
 tree=etree.fromstring(text.encode('utf-8'),parser)
 if tree is None:raise ValueError('unreadable document')
 tree.set('_research_parser_warning_count',str(len(parser.error_log)))
 return tree,encoding

def text_and_identity(raw):
 tree,encoding=parse_xml(raw)
 text='\n'.join(' '.join(t.split()) for t in tree.itertext() if t.strip())
 name=tree.find('.//COMPANY-NAME');name=' '.join(name.itertext()).strip() if name is not None else None
 return text,{'encoding':encoding,'original_document_company':name,'xml_recovery_warnings':int(tree.get('_research_parser_warning_count')),'text_hash':hashlib.sha256(text.encode()).hexdigest()}

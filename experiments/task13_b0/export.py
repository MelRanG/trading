"""Export only first-vintage event quantities, excluding all future revision knowledge."""
from pathlib import Path
import json,hashlib
from lxml import html
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_b0';x=json.loads((B/'validation.json').read_text());out=[]
for e in x['contracts']:
 p=R/e['source_path'];doc=html.fromstring(p.read_bytes(),parser=html.HTMLParser(encoding='utf-8'));title=doc.xpath('string(//title)')
 out.append({'symbol':e['symbol'],'original_company_name':title.split('/')[0],'original_receipt':e['receipt_no'],'source_path':e['source_path'],'source_sha256':e['source_sha256'],'available_date_upper_bound':e['publication_date']+'T23:59:59+09:00','precision':'DATE_ONLY','download_is_2026_backfill':True,'amount_KRW':e['contract_amount_KRW'],'annual_revenue_KRW':e['previous_annual_revenue_KRW'],'ratio_pct':e['contract_to_revenue_pct'],'VAT_included':e['VAT_included'],'term':e['contract_term'],'counterparty':e['counterparty'],'new_incremental_amount_verified':False,'eligibility':'INCOMPLETE_PRIOR_PARTIAL_CONTRACT_DELTA' if e['previous_partial_contract'] else 'DATE_BOUND_RESEARCH_ONLY','limits':['No intraday timestamp','Historical observation latency unknown','No price/return labels','Not ready for operating ingestion'],'future_revision_fields_exported':False})
(B/'research_events.json').write_text(json.dumps({'type':'contract_first_vintage_feasibility','phase_C_contract_hash':hashlib.sha256((B/'phase_c_contract.json').read_bytes()).hexdigest(),'events':out,'no_strategy_or_approval_authority':True},ensure_ascii=False,indent=2))

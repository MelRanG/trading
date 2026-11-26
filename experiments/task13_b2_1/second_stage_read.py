"""Second-stage original-source adjudications. Does not rewrite B2 results."""
from read_sources import *
D=[
('UNRESOLVED',None,'2022','high-single to low-double digit','low-double digit',True,[60,61,70],[59,60,69],'Changed qualitative bounds; do not invent numeric endpoints or direction.'),
('RECOVERABLE','UNCHANGED','2024','mid-single digits','mid-single digits',True,[12,13,124],[18,19],'Same literal annual consolidated sales growth category; quarterly forecast separated. No numeric conversion.'),
('MISSING_PREVIOUS_SOURCE',None,'2025',None,'low single digits',True,[18,19],[12,13],'FY2025 new annual outlook vs FY2024 prior; no same-FY parent.'),
('NO_ANNUAL_REVENUE_GROWTH_GUIDANCE',None,'2022',None,None,False,[10,11,108],[11,12],'EPS and absolute COVID-testing sales only, not annual total organic growth.'),
('OUTSIDE_B2_CONTRACT',None,'2023',None,'$88-90 billion',False,[18,19,20,21],[17,18,20],'Total sales absolute amount; percentage is comp-sales or operating margin, not total sales growth.'),
('OUTSIDE_B2_CONTRACT',None,'2024','$82.7-83.2 billion','$83.0-83.5 billion',False,[18,19,20,21],[17,18,19,20],'Total sales absolute amount; comp-sales percentage and operating margin are ineligible. Do not turn margin decline into revenue downgrade.'),
('RECOVERABLE','UP','2023','10-12%','14-16%',True,[19,20],[28,30],'Explicit annual FY2023 net-sales YoY percentage paragraph and earlier original. Dollar outlook not used for feature.'),
('UNRESOLVED',None,'2023','5-7%','10+%',True,[46],[95],'Range to open-ended lower bound with explicit raise; do not extend B2 implemented numeric-kind/qualifier rule or borrow PEP-specific exception. Source economic increase visible but strict classifier eligibility remains unresolved.'),
('RECOVERABLE','UP','2024','8-9%','9-10%',True,[119,120],[99,100],'Annual organic forecast explicitly 9-10; high-end refers to separate long-term model clause, not a qualifier of the numerical 9-10 range. Global qualifier guard falsely rejected it.'),
('RECOVERABLE','UNCHANGED','2024','upper end of 3-5%','upper end of 3-5%',True,[64],[61],'Identical source range-end condition retained literally; no midpoint or numerical upper-end inference.'),
('RECOVERABLE','UNCHANGED','2022','high-single digit to low-double-digit','high-single to low-double digit',True,[59,60,69],[58,59,68],'Equivalent literal annual qualitative band; table header separates quarterly columns. EPS downgrade is not revenue downgrade.'),
('NO_ANNUAL_REVENUE_GROWTH_GUIDANCE',None,'2023',None,None,False,[235,236],[0],'Strong organic sales / robust growth not quantified comparable annual outlook; numbers concern EPS/actual period.'),
('OUTSIDE_B2_CONTRACT',None,'2024',None,None,False,[118,151],[107,140],'Forecast percentages are industry/segment-level; no total issuer annual revenue growth. Financial-services forecast is net income.'),
('NO_ANNUAL_REVENUE_GROWTH_GUIDANCE',None,'2022',None,None,False,[27,28],[34,35],'Release defers guidance to future conference call; no numeric forecast in retained release. Do not assume call transcript present.'),
('OUTSIDE_B2_CONTRACT',None,'2023','4.5-5.5% excluding COVID vaccine','5.5-6.5% excluding COVID vaccine',False,[65,67,82,98],[42,44,54,68],'Estimated Reported Sales table footnote5 excludes COVID vaccine in BOTH originals. Table header alone would produce false total-revenue recovery.'),
('NO_ANNUAL_REVENUE_GROWTH_GUIDANCE',None,'2024',None,None,False,[7,8],[8,9],'Annual outlook EPS only; realized quarterly revenues cannot replace guidance.'),
('NO_ANNUAL_REVENUE_GROWTH_GUIDANCE',None,'2024',None,None,False,[21,96],[88,89,90],'Forecast customers, EBITDA and FCF; no consolidated annual revenue growth forecast.'),
('OUTSIDE_B2_CONTRACT',None,'2023','about4.5% reported','about5.5% reported',False,[46,47,53,55],[40,41,47,49],'Annual growth INCLUDES FX headwind; fixed issuer contract requires CONSTANT CURRENCY. Do not silently switch WMT basis or use divestiture-excluded figure.'),
('MISSING_PREVIOUS_SOURCE',None,'2024',None,'approximately4.0-4.5% cc',True,[103,105,115],[],'Current annual constant-currency table present, but immediately previous collected May2023 source is FAILED. Current release not sufficient to reconstruct latest prior version.'),
('OUTSIDE_B2_CONTRACT',None,'2025','$60-61 billion','$62.5-63.5 billion',False,[57,59,60],[79,81,82],'Absolute sales plus changed acquisition scope (Cheney); no primary revenue-growth percentage pair.')]
def run():
 rows=[]
 for x,t in zip(P['conditional_stage2'],D):
  cat,direction,fy,old,new,present,ci,pi,note=t;o=packet(x);ev=[]
  coll=json.loads((R/'runtime/task13_b2/collection'/f"{x['symbol']}.json").read_text())
  for doc,inds in zip(o['documents'],[ci,pi]):
   if not doc.get('source'):continue
   e=next(e for e in coll.get('parents',[])+coll['targets'] if e['filing']['accessionNumber']==doc['accession']);lookup={b['n']:b for b in blocks(e)}
   for i in inds:
    assert i in lookup,(x['event_id'],doc['role'],i)
    ev.append({'role':doc['role'],'accession':doc['accession'],'filingDate':doc['filingDate'],'URL':doc['source']['url'],'source_SHA':doc['source']['source_hash'],**lookup[i]})
  rows.append({**x,'category':cat,'direction':direction,'FY':fy,'prior_literal':old,'current_literal':new,'in_contract_current_guidance':present,'reason':note,'evidence':ev,'review_stage':'MAIN_ORIGINAL_READING_STAGE2_NO_NEW_LLM','PIT_scope':'Source/FY/basis only; no earliestIR/price/horizon-independence qualification'})
 p=B/'stage2_first_read.json'
 if p.exists():assert json.loads(p.read_text())==rows
 else:p.write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 print('STAGE2_READ_SAVED',len(rows))
if __name__=='__main__':run()

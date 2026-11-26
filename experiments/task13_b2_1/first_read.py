"""Explicit original-document judgments by the main coding reviewer.
These are adjudications, not parser output or ground-truth training labels.
"""
from read_sources import *
D=[
('RECOVERABLE','UP','2022','9-11%','11-13%',True,[11],[11],'Annual organic growth sentence omits literal sales/revenue; separate annual from quarterly clause. Full-year source and predecessor agree.'),
('MISSING_PREVIOUS_SOURCE',None,'2024',None,'mid-single digits',True,[18,19],[8,9],'Current annual FY2024 forecast; predecessor only FY2023 quarterly forecast. No same-FY prior guidance in available parent.'),
('UNRESOLVED',None,'2024','up low-single digit','flat to up low-single digit',True,[63,76],[61,71],'Changed qualitative bounds; no invented numeric conversion or DOWN claim under unchanged B2 qualifier rules.'),
('NO_ANNUAL_REVENUE_GROWTH_GUIDANCE',None,'2022',None,None,False,[14,15,114],[11,108],'2022 guidance EPS and absolute COVID testing sales only; organic growth numbers are realized FY2021.'),
('OUTSIDE_B2_CONTRACT',None,'2023',None,'Core organic 7%',False,[37],[],'Core organic scope differs from fixed annual total organic revenue basis; no same-FY prior pair either.'),
('OUTSIDE_B2_CONTRACT',None,'2024',None,None,False,[14,32],[14,31],'Guidance concerns wireless service revenue and earnings, not total reported revenue growth.'),
('RECOVERABLE','UP','2022','5-7%','6-7%',True,[39,42],[39,42],'Explicit current/prior organic sales range with FY heading. Lower endpoint raised, upper unchanged.'),
('MISSING_PREVIOUS_SOURCE',None,'2023',None,'towards high end of 3-5%',True,[64,67],[39,42],'New FY2023 outlook; prior original concerns FY2022. Do not compare realized FY2022 or discard qualitative qualifier.'),
('RECOVERABLE','UP','2025','25-27%','28-30%',True,[25,26],[17,18],'Explicit year-over-year growth in net sales in annual FY2025 outlook paragraph; dollar table is supplementary, not primary.'),
('OUTSIDE_B2_CONTRACT',None,'2025',None,'$60-61 billion',False,[79,81],[74,76],'Absolute revenue only and FY rollover. Do not convert dollar range into primary growth or count parent FY2024 downgrade.'),
('NO_ANNUAL_REVENUE_GROWTH_GUIDANCE',None,'2023',None,None,False,[49],[],'Forward consolidated sales forecast is for first quarter FY2023 only, not annual. Full-year reported figures are realized FY2022.'),
('MISSING_PREVIOUS_SOURCE',None,'2023',None,'7-9%',True,[18],[12],'New annual FY2023 organic growth vs predecessor FY2022; annual prior unavailable.'),
('NO_ANNUAL_REVENUE_GROWTH_GUIDANCE',None,'2024',None,None,False,[237,241],[246,248],'Solid sales growth language and quantified EPS outlook, but no comparable annual organic sales-growth number/category. Actual organic4/5 not future guidance.'),
('OUTSIDE_B2_CONTRACT',None,'2022',None,None,False,[49,51],[47],'Current reported-sales table excludes vaccine sales; source explicitly changes scope relative to previous guidance. No total all-in consistent pair.'),
('OUTSIDE_B2_CONTRACT',None,'2023','at least high single digits ex-COVID','low double digits ex-COVID',False,[11],[10],'Annual organic excluding COVID testing is not fixed total organic basis; qualitative labels not converted.'),
('OUTSIDE_B2_CONTRACT',None,'2024','$42.3-43.3 billion','$42.4-43.3 billion',False,[32,33],[25,26],'Reported absolute revenue only, not fixed organic growth primary.'),
('OUTSIDE_B2_CONTRACT',None,'2024','$42.1-43.3 billion','$42.3-43.3 billion',False,[25,26],[35,36],'Reported absolute revenue only, not fixed organic growth primary.'),
('MISSING_PREVIOUS_SOURCE',None,'2022',None,'3-4%',True,[8,49],[46,49],'New annual FY2022 organic growth; prior FY2021 decline cannot serve as same-FY parent.'),
('RECOVERABLE','UNCHANGED','2023','2-4%','2-4%',True,[65,67,69],[48,51],'Original previous/current table identifies organic row separately from FX/net sales and matches preceding original outlook.'),
('OUTSIDE_B2_CONTRACT',None,'2024','$37.5-38.5 billion','$37.5-38.5 billion',False,[37,38,39],[48,51],'Same annual dollar sales outlook, but absolute revenue explicitly excluded by B2 growth contract.')]

def run():
 rows=[]
 for x,t in zip(P['stage1'],D):
  cat,direction,fy,old,new,present,ci,pi,note=t;o=packet(x);ev=[]
  for doc,inds in zip(o['documents'],[ci,pi]):
   if not doc.get('source'):continue
   # Evidence may be outside preview window; recover from original, never B2 parsed text.
   coll=json.loads((R/'runtime/task13_b2/collection'/f"{x['symbol']}.json").read_text());original=next(e for e in coll.get('parents',[])+coll['targets']if e['filing']['accessionNumber']==doc['accession']);bs=blocks(original);lookup={b['n']:b for b in bs}
   for i in inds:
    assert i in lookup,(x['event_id'],doc['role'],i)
    ev.append({'role':doc['role'],'accession':doc['accession'],'filingDate':doc['filingDate'],'URL':doc['source']['url'],'source_SHA':doc['source']['source_hash'],**lookup[i]})
  rows.append({**x,'category':cat,'direction':direction,'FY':fy,'prior_literal':old,'current_literal':new,'in_contract_current_guidance':present,'reason':note,'evidence':ev,'review_stage':'MAIN_ORIGINAL_READING_BEFORE_SECOND_READER_RESPONSE','PIT_scope':'Source/FY/basis audit only; earliest IR, corporate actions, prices and H20 independence not verified'})
 p=B/'stage1_first_read.json'
 if p.exists():assert json.loads(p.read_text())==rows
 else:p.write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 print('FIRST_READ_SAVED',len(rows))
if __name__=='__main__':run()

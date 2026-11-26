from pathlib import Path
import json,hashlib,datetime
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_b3_repair';B.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan={'task':'13-B3_TECHNICAL_COMPLETION','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_plan_SHA':sha(R/'runtime/task13_b3/plan.json'),'original_signal_SHA':sha(R/'runtime/task13_b3/signal_events.json'),'original_signal_seal_SHA':sha(R/'runtime/task13_b3/signal_seal.json'),'original_evaluation_SHA':sha(R/'runtime/task13_b3/evaluation.json'),'original_B3_manifest_SHA':sha(R/'runtime/task13_b3/artifact_manifest.json'),'max_technical_attempts':2,'technical_attempt_started':1,'max_corrected_evaluations':1,'hypothesis_direction_H60_controls_and_12companies':'UNCHANGED; original all thresholds, outcome cutoff, cost interpretation, analysis functions retained','correction':'Reconcile R0 native listing mask with issuer-level listing lifetime vs exchange/ticker change. Four verified continuity overrides, other native masks remain inherited/fail-closed. R0 original files/operating states never rewritten. AliasSGI is TPX before2025-02-18. No price interpolation/return-based exclusion.','HTTP_max':16,'per_response_max_bytes':12000000,'total_download_cap_bytes':50000000,'internal_LLM_calls':0,'new_price_downloads':0,'training':0,'operating_changes':0,'bounds':'New research-only identity overlay, not new market-universe/alpha contract; cannot assert full historic universe or independent OOS','official_sources':{
'KMB_TRANSFER':'https://www.investor.kimberly-clark.com/news-releases/news-release-details/kimberly-clark-transfer-us-stock-exchange-listing-nasdaq',
'KMB_2019_COVER':'https://www.sec.gov/Archives/edgar/data/55785/000005578519000064/R1.htm',
'HLT_IPO':'https://ir.theice.com/press/news-details/2013/Hilton-Worldwide-Celebrates-Initial-Public-Offering-on-the-New-York-Stock-Exchange/default.aspx',
'HLT_TRANSFER':'https://ir.hilton.com/sec-filings/all-sec-filings/content/0001585689-26-000045/projectrepositionrelease.htm',
'PLTR_TRANSFER':'https://www.nasdaqtrader.com/TraderNews.aspx?id=DTN2024-30',
'PLTR_HISTORY':'https://www.sec.gov/Archives/edgar/data/1321655/000132165525000059/fy2024palantirarsa.htm',
'SGI_RENAME':'https://somnigroup.com/newsroom/news-details/2025/Tempur-Sealy-International-Inc.-to-Change-its-Name-to-Somnigroup-International-Inc/default.aspx',
'SGI_IPO_HISTORY':'https://somnigroup.com/investor-resources/investor-faqs/default.aspx',
'TPX_2019_10K':'https://www.sec.gov/Archives/edgar/data/1206264/000120626420000079/tpx-20191231x10k.htm'}}
p=B/'plan.json'
if not p.exists():p.write_text(json.dumps(plan,indent=2));(B/'plan.sha256').write_text(sha(p))
else:assert sha(p)==(B/'plan.sha256').read_text()
print('PLAN',sha(p))

from pathlib import Path
import json,shutil,sys
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.portfolio import aggregate
from quant_harness.investment.store import Store
from quant_harness.investment.research import digest
b=R/'runtime/task8';w=Path('/home/ansy/app/quant-diligence/task8-vibe-work');native=json.loads((w/'native_portfolio.json').read_text());shutil.copy2(w/'native_portfolio.json',b/'native_portfolio.json');r=json.loads((b/'comparison.json').read_text());cfg=json.loads((R/'config/task8_portfolio.json').read_text());raw=native['native_hrp_weights'];preview=aggregate([{'capital_fraction':1,'weights':raw}],gross_cap=cfg['gross_cap'],single_name_cap=cfg['single_name_cap'],sector_caps={'SEMIS':cfg['sector_cap'],'CLOUD':cfg['sector_cap']},sectors={'NVDA':'SEMIS','CRWV':'CLOUD'})
r['comparisons']['E_VIBE_PLUS_MINIMAL']={'native_weights':raw,'native_proposal_only':native['original_cash_rebalance'],'risk_preview':preview,'gated_decision':r['comparisons']['D_INTEGRATED']['decision'],'difference':'Native HRP does not establish expected net edge. Existing cash account native proposal is also cash; QH gates identify unvalidated signals and raw HRP concentration before any simulated execution. No return superiority measured.','performance':'PENDING_FORWARD'}
r['outcome_comparison']='B,C,D,E gated decisions are cash; no measurable portfolio alpha increment in this run. Nonzero/conflict behavior is tested separately with explicit fixtures.'
store=Store('postgresql://quant_task8_research@127.0.0.1:55432/quant_task3_task8_research','TASK8_RESEARCH_ONLY');store.put('task8_comparative_result',r);store.export(b/'research_records.jsonl');(b/'comparison_final.json').write_text(json.dumps(r,indent=2,default=str));print(json.dumps({'native_weights':raw,'gate_violations':preview['violations'],'gated_weights':r['comparisons']['D_INTEGRATED']['decision']['weights']},indent=2))

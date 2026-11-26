"""Conservative reproducible inventory; reference absence is not deletion proof."""
from pathlib import Path
import ast,json
ROOT=Path(__file__).resolve().parents[1]
files=list((ROOT/'src').rglob('*.py'))+list((ROOT/'scripts').glob('*.py'))
refs={}
for path in files+list((ROOT/'tests').rglob('*.py')):
    try:tree=ast.parse(path.read_text())
    except (SyntaxError,UnicodeError):continue
    for node in ast.walk(tree):
        names=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
        for name in names:refs.setdefault(name,set()).add(str(path.relative_to(ROOT)))
active_scripts={'setup_operations_database','probe_operations_restore','run_autonomous_operations','run_common_experiment','backup_operations','classify_operating_sources','run_equity_cycle','run_review_daily','run_review_cycle','score_review_outcome'}
research_scripts={'run_investment_skill_ab','scan_equity_universe','run_independent_review_note','run_review_event','audit_equity_comparison'}
rows=[]
for path in sorted(files):
    rel=str(path.relative_to(ROOT));module='.'.join(path.relative_to(ROOT/'src').with_suffix('').parts) if path.is_relative_to(ROOT/'src') else ''
    references=sorted(set().union(*(v for k,v in refs.items() if module and (k==module or k.startswith(module+'.'))))) if module else []
    if '/investment/' in rel or path.stem in active_scripts or path.stem=='alpha_research_factory':category='ACTIVE';reason='Task3/4/5 operating or Factory entry/module; optional tools retain separate flags'
    elif path.stem in research_scripts:category='RESEARCH';reason='Explicit bounded diagnostic/analysis tool, not timer'
    elif any(s in rel for s in ('v69_','v79_','v84_','v87_','v89_','v101_','v102_','v103_','v104_','v104_2_')):category='BASELINE';reason='Frozen replay, contracts, shared gate or regression dependency; not approved new strategy'
    elif path.stem in ('run_v85_scheduler','docker_entrypoint') or '/v85_' in rel:category='LEGACY';reason='Former scheduling path; Compose now requires legacy-reference profile; preserve replay/tests'
    elif references:category='BASELINE';reason='Referenced helper/reproducibility dependency; preserve pending narrower audit'
    else:category='BASELINE';reason='No direct absolute Python import detected, but CLI/dynamic/config use or reproduction value unconfirmed; conservatively preserved, not proven UNUSED'
    rows.append({'path':rel,'category':category,'reason':reason,'direct_absolute_import_references':references,'delete_safe':False})
out=ROOT/'docs/development/05_source_inventory.json';out.write_text(json.dumps({'method':'AST absolute import references plus explicit current entrypoints; conservative, not runtime coverage','removed_sources':[], 'files':rows},indent=2))
from collections import Counter
print(json.dumps({'files':len(rows),'categories':dict(Counter(r['category'] for r in rows)),'removed':0}))

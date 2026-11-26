"""Freeze historical cohorts and validation budget before looking at outcomes."""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from experiments.research_references import source
from experiments.task13_f1_r4.replay import ROOT, load, save, sha

OUT = ROOT/'runtime/task13_f1_r6'
R5 = ROOT/'runtime/task13_f1_r5'
CAP = 500_000_000_000
STARTS = {'A': ('20230331','2023-04-03','2025-12-30'), 'B': ('20251230','2026-01-02','2026-11-18')}
BOARDS = {'KOSPI':35,'KOSDAQ':25}


def screen(rows):
    return rows[rows.cap.ge(CAP)&rows.volume.gt(0)]


def sample(rows, count):
    ordered = rows.sort_values(['cap','code'],ascending=[False,True])
    if len(ordered) < count:
        raise ValueError('historical stratum too small')
    return ordered.iloc[((2*pd.RangeIndex(count)+1)*len(ordered))//(2*count)]


def main():
    OUT.mkdir(exist_ok=True)
    if (OUT/'contract.json').exists():
        raise FileExistsError('R6 already sealed')
    roster_file = R5/'roster_snapshots.csv'
    r5_manifest = load(R5/'artifact_manifest.json')
    assert sha(roster_file)==r5_manifest[roster_file.relative_to(ROOT).as_posix()]
    roster = pd.read_csv(roster_file,dtype={'date':str,'code':str})
    assert not roster.duplicated(['date','code']).any()
    vintage = {d:rows for d,rows in roster.groupby('date')}
    original = source(ROOT,'runtime/task13_f1_r2/collection_plan.json')
    old = {s[:6] for s in load(original)['symbols']}
    panels, pilots = [], []
    for arm,(stamp,_,end) in STARTS.items():
        pool = screen(vintage[stamp]).sort_values(['board','cap','code'],ascending=[True,False,True]).copy()
        selected = [sample(pool.loc[pool.board.eq(board)],n) for board,n in BOARDS.items()]
        selected_codes = set(pd.concat(selected).code)
        pool['reference_60'] = pool.code.isin(old)
        pool['cap_sample'] = pool.code.isin(selected_codes)
        pool['arm'] = arm
        panels.append(pool)
        for board in BOARDS:
            nonprior = pool.loc[pool.board.eq(board)&pool.cap_sample&~pool.reference_60]
            if len(nonprior):
                pilots.append({**nonprior.iloc[0].to_dict(),'kind':'OUTSIDE_OLD_60','cutoff':end.replace('-','')})
        # Supplemental integrity probes, never feed the economic candidate selection.
        last = end.replace('-','')
        missing = pool.loc[~pool.code.isin(vintage[last].code)].sort_values(['cap','code'],ascending=[False,True])
        for row in missing.head(3).to_dict('records'):
            pilots.append({**row,'arm':arm,'kind':'EXIT_INTEGRITY_ONLY','cutoff':last})
    candidates = OUT/'entry_cohorts.csv'
    pd.concat(panels).to_csv(candidates,index=False)
    pilot = OUT/'pilot_plan.json'
    save(pilot,pilots)
    cost = ROOT/'config/task3_equity_contract.json'
    paths = [roster_file, original, candidates, pilot, Path(__file__), cost,
             ROOT/'experiments/task13_f1_r4/execution.py',ROOT/'experiments/task13_f1_r5/run.py',
             R5/'contract.json',R5/'universe_name_audit.csv',R5/'benchmarks.csv']
    save(OUT/'contract.json',{
        'id':'TASK13_F1_R6','sealed_at':datetime.now(timezone.utc).isoformat(),'periods':STARTS,
        'period_B':'EXPOSED_HISTORICAL_STRESS','archive_comparison_class':'SURVIVOR_RESEARCH',
        'screen':'Official entry-cutoff KRX KOSPI/KOSDAQ code, cap >= 500bn KRW, strictly positive volume on cutoff. This is a preliminary trading pool; positive single-day volume is not sustained executable ADV and does not authenticate common equity.',
        'old_rule':'R0 current sector/common/listing, cap and sector-round-robin then R2 stage, cannot substitute current industry. Try cutoff official security identity metadata.',
        'fallback':'Separate entry cohort sensitivity, 35 KOSPI and 25 KOSDAQ per cutoff, board-level market-cap percentile midpoints by integer positions floor((2*i+1)*N/(2*n)), cap descending then code ascending. Lock codes with no replacement after outcome or availability. A/B union at most 120 names. Official security type/source eligibility must precede evaluation.',
        'diagnostic_pilot':'Largest cap sampled outside prior 60 per board per period. Plus largest cap three preliminary eligible codes absent at each known endpoint. Future absence used exclusively for integrity diagnostics, never selection.',
        'data_gate':'100% locked candidates have authoritative identity and security class or objectively ineligible under a gate fixed before returns. Require each non-ineligible name to have full expected sessions including at least 64 causal warmup closes, exact sell/terminal handling or authoritative no-trade states, splits/merger/security transitions, and original R4/R5 lagged validity gate. For V87 compare the open/high/low/close of available official matched checkpoints and retain preexisting revision logic. Missingness must not selectively prune exiting issuers. Any unresolved terminal settlement or materially incomplete panel blocks evaluation; no renormalization from a provider-only survivor subset.',
        'policy':'Preserve MOM63 positive ranked top 4 each 20%, total 80%, 5 sessions plus KODEX 200 MA63 transitions, previous session inputs then next eligible nominal open, unchanged R4 execution constraints/costs. R2 T+1 eligibility is required even when no FLOW5 amount enters score. No new FLOW5 research.',
        'continuity':'A inherits R4 cold start and schedule. B requires earned pre-2026 account state and rebalance phase under certified earlier membership rules if chained; distinct entry-cohort B from cash only would be separately labeled, never substituted for R5 continuity.',
        'benchmarks':'Carry original KOSPI, KOSDAQ, KODEX 200, 35:25 market mix and same-date lagged equity exposure benchmark.',
        'requests_cap':40,'max_valid_evaluations':{'A':1,'B':1},
        'max_liquid_reference_sample_union':len(set(pd.concat(panels).query('cap_sample').code)),
        'sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in paths}})


if __name__=='__main__':
    main()

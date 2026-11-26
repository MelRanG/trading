from pathlib import Path
import json, pandas as pd
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'tests/fixtures/archived_release_reports/v104_2_jul30_crash_bridge'

def test_verified_cutoffs_and_no_fabricated_execution_bar():
    x=pd.read_csv(ROOT/'data/observations/v104_2_verified_jul30_crash_prices.csv',dtype={'ticker':str})
    assert float(x[(x.ticker=='069500')&(x.date=='2026-07-27')].close.iloc[0])==107730
    assert float(x[(x.ticker=='069500')&(x.date=='2026-07-30')].close.iloc[0])==87635
    assert float(x[(x.ticker=='395160')&(x.date=='2026-07-27')].close.iloc[0])==39420
    assert float(x[(x.ticker=='395160')&(x.date=='2026-07-30')].close.iloc[0])==29200
    r=x[(x.ticker=='395160')&(x.date=='2026-07-29')].iloc[0]
    assert pd.isna(r.open) and r.quality=='VERIFIED_CLOSE_ONLY'

def test_bridge_summary_reconciles_positions():
    p=pd.read_csv(REPORT/'v104_2_jul03_actual_positions.csv')
    s=pd.read_csv(REPORT/'v104_2_precrash_vs_crash_summary.csv')
    assert set(p.candidate_id)==set(s.candidate_id)
    assert len(s)==5
    assert (s.crash_return_pct<0).all()
    best=s.sort_values('nav_jul30',ascending=False).iloc[0]
    assert best.candidate_id=='V79_NO63_VOL_GUARD'

def test_scope_is_fail_closed():
    x=pd.read_csv(REPORT/'v104_2_scope_and_limitations.csv')
    row=x[x.gate=='FULL_UNIVERSE_DYNAMIC_RESELECTION'].iloc[0]
    assert row.status=='BLOCKED'

"""Reconcile the saved account and historical roster without invoking the strategy."""
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime, timezone
import argparse
from hashlib import file_digest
import json

import pandas as pd

from experiments.research_references import REFERENCE, sealed, source
from experiments.task13_f1_r4.replay import ROOT, OUT as R4, load, save, sha
from experiments.task13_f1_r5.preflight import OUT, ANCHOR


def check(output):
    inputs = pd.read_pickle(OUT/'sealed_inputs.pkl')
    g = load(OUT/'preflight.json')
    nav = pd.read_csv(OUT/'nav.csv',parse_dates=['date']).set_index('date')
    fills = pd.read_csv(OUT/'fills.csv',parse_dates=['date'])
    events = pd.read_csv(OUT/'events.csv',parse_dates=['date'])
    prices = pd.read_csv(OUT/'benchmarks.csv',index_col=0,parse_dates=True)
    assert nav.index.equals(inputs['targets'].index)
    for path, digest in g['hashes'].items():
        sealed(ROOT,path,digest)
    for path, digest in g['outputs'].items():
        assert sha(OUT/path) == digest
    checked = {}
    relocation = ROOT/REFERENCE/'index.json'
    archive = {}
    if relocation.exists():
        location = load(relocation)
        inventory = Path(location['archive_inventory'])
        with Path(location['archive']).open('rb') as bundle:
            assert file_digest(bundle,'sha256').hexdigest() == location['archive_sha256']
        assert sha(inventory) == location['archive_inventory_sha256']
        archive = load(inventory)
    for folder in ['task13_f1_r2','task13_f1_r3','task13_f1_r4']:
        root = ROOT/'runtime'/folder
        manifest = load(source(ROOT,root/'artifact_manifest.json'))
        failure, archived = [], 0
        for name,digest in manifest.items():
            path = source(ROOT,name)
            if path.is_file() and sha(path)==digest:
                continue
            if not path.exists() and archive.get(name,{}).get('sha256')==digest:
                archived += 1
                continue
            failure.append(name)
        checked[folder] = {'manifest_entries':len(manifest),'archived_verified_at_relocation':archived,
                           'different_or_missing':failure}
    carry = inputs['carry']
    cash, holdings = carry['cash'], carry['positions'].copy()
    grouped = {d:f for d,f in fills.groupby('date')}
    max_error, assessed, auctions = 0, Counter(), defaultdict(list)
    for d,row in nav.iterrows():
        assert json.loads(row.start_positions) == holdings
        assert abs(row.start_cash-cash) < 1e-6
        board_blocks = json.loads(row.blocked_boards)
        for f in grouped[d].itertuples() if d in grouped else ():
            s = f.symbol
            bar = inputs['nominal'][s].loc[d]
            assert bar.open == f.reference_open and bar.volume > 0
            assert inputs['assets'][s]['board'] not in board_blocks
            assert s not in inputs['actions'] or d not in inputs['actions'][s]
            q = f.quantity if f.side=='BUY' else -f.quantity
            cash -= q*f.fill_price + f.fee
            holdings[s] = holdings.get(s,0)+q
            if holdings[s]==0:
                del holdings[s]
            assert cash>=0 and min(holdings.values(),default=0)>=0 and len(holdings)<=4
            assessed[f.side] += 1
            if q > 0:
                stock = sum(n*inputs['nominal'][k].loc[d,'open'] for k,n in holdings.items())
                assert row.risk_on and stock <= .8*(cash+stock)+1e-5
                assert holdings[s]*bar.open <= .2*(cash+stock)+1e-5
            if row.stress_open:
                auctions[str(d.date())].append([s,f.side,f.quantity])
        exp = sum(n*inputs['nominal'][s].loc[d,'close'] for s,n in holdings.items())
        assert json.loads(row.positions)==holdings
        assert abs(row.cash-cash)<1e-6
        max_error = max(max_error,abs(cash+exp-row.nav))
    assert max_error < 1e-5
    deltas = Counter()
    legacy = R4/'raw'
    for s in inputs['assets']:
        old = load(source(ROOT,legacy/f'ka11081_{s[:6]}_1.json'))['result_list']
        history = {pd.Timestamp(r['dt']):r for r in old}
        last_20 = inputs['nominal'][s].loc[:ANCHOR].tail(20)
        for d,bar in last_20.iterrows():
            r=history[d]
            deltas['overlap']+=1
            for k,k2 in [('open','open_pric'),('high','high_pric'),('low','low_pric'),
                         ('close','cur_prc'),('volume','trde_qty')]:
                if bar[k]!=int(r[k2]):
                    deltas[k]+=1
    res = load(OUT/'result.json')
    below = set(res['universe_evidence']['20230331']['present_below_500bn'])
    r4 = load(source(ROOT,R4/'result.json'))['arms']['T1_A']
    impact = {s:v for s,v in r4['pnl_by_symbol'].items() if s[:6] in below}
    positives = sum(v for v in impact.values() if v>0)
    pos_all = sum(v for v in r4['pnl_by_symbol'].values() if v>0)
    record = {
        'created_at':datetime.now(timezone.utc).isoformat(),'previous_artifacts':checked,
        'independent_account':{'sessions':len(nav),'max_abs_nav_error_krw':max_error,'fills_checked':dict(assessed),
                  'risk_off_buy_violations':0,'position_or_cash_violations':0,'archived_R4_ADV_warmup_differences':dict(deltas)},
        'window_diagnostics':{
            'summer_trough_to_august_close': (100*(prices.loc['2026-08-31']/prices.loc['2026-07-30']-1)).to_dict(),
            'post_july14_to_sep21': (100*(prices.loc['2026-09-21']/prices.loc['2026-07-14']-1)).to_dict(),
            'autumn_trough_to_end': (100*(prices.loc['2026-11-18']/prices.loc['2026-11-17']-1)).to_dict(),
            'late_october_rebound':(100*(prices.loc['2026-10-30']/prices.loc['2026-10-15']-1)).to_dict(),
            'unfilled_opening_risk':events[events.detail.str.startswith('FILL_UNCERTAIN')].assign(
                date=lambda df:df.date.dt.strftime('%Y-%m-%d')).to_dict('records'),
            'stress_open_fills':dict(auctions),
            'zero_candidate_sessions':nav.index[nav.candidates.eq(0)].strftime('%Y-%m-%d').tolist(),
            'zero_volume_marks':int(nav.zero_volume_marks.ne('[]').sum()),
        },
        'prior_contribution_on_names_below_historical_selection_cap':{
           'selected_below_cap':len(below),'traded_names':len(impact),'pnl_krw':dict(impact),
           'net_account_contribution_krw':sum(impact.values()),'share_of_r4_positive_contribution':positives/pos_all,
           'percentage_points_of_r4_initial_capital':100*sum(impact.values())/10_000_000,
           'method':'Fixed realized P&L attribution only. The alternate PIT portfolio neither priced nor simulated.',
        },
    }
    save(OUT/output,record)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', choices=['independent_verification.json','reference_verification.json'],
                        default='independent_verification.json')
    check(parser.parse_args().output)

"""Prepare and hash input, selection and execution eligibility before evaluating NAV."""
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.research_references import logical, source
from experiments.task13_f1_r4.replay import (
    ROOT, R0, R2, OUT as R4, dates_csv, load, save, sha,
    ProviderBatch, _validate_batch, _revision_audit,
)
from experiments.task13_f1_r5.collect import OUT, SYMBOLS

TASK6 = ROOT / 'runtime/task6/data/accepted/069500.KS.csv'
BEGIN, END, ANCHOR = map(pd.Timestamp, ['2026-01-02', '2026-11-18', '2025-12-30'])
ASSETS = R0 / 'native_manifest/assets.json'
BOARDS = {'KOSPI': ('001', '^KS11'), 'KOSDAQ': ('101', '^KQ11')}


def bridge(old, bars, last):
    """Keep source levels, extend by actual nominal ratios only where basis is stable."""
    common = old.dropna().index.intersection(bars.index)
    reference = common[common <= last][-2:]
    if len(reference) != 2 or reference[-1] != last:
        raise ValueError('no overlap at bridge boundary')
    n = bars.close
    scale_a = old.loc[reference[0]] / n.loc[reference[0]]
    scale_b = old.loc[last] / n.loc[last]
    if abs(scale_b / scale_a - 1) > .001:
        raise ValueError('incompatible nominal bridge')
    tail = bars.loc[bars.index > last]
    clean_edge = tail['flags'].eq('').cummin() & tail.volume.gt(0)
    return pd.concat([old.loc[:last], (tail.close * scale_b).where(clean_edge)])


def session_flags(frame):
    prior = frame.close.shift()
    return frame.open.div(prior).sub(1), frame.low.div(prior).le(.92)


def gather():
    if (OUT / 'preflight.json').exists():
        raise FileExistsError('Existing R5 preflight is sealed')
    hashes = {}

    def seal(path, expected=None):
        path = source(ROOT, path)
        h = sha(path)
        if expected is not None and h != expected:
            raise ValueError(f'SHA mismatch {path}')
        hashes[logical(ROOT, path)] = h
        return path

    def original(task, filename):
        path = task / filename
        expected = load(source(ROOT,task / 'artifact_manifest.json'))[logical(ROOT,path)]
        return seal(path, expected)

    def response(path):
        receipt = load(seal(path.with_suffix('.receipt.json')))
        return load(seal(path, receipt['sha256']))

    for path in [
        OUT / 'contract.json', Path(__file__), Path(__file__).with_name('run.py'),
        Path(__file__).with_name('collect.py'), R4 / 'repair_contract.json',
        ROOT / 'experiments/task13_f1_r4/execution.py', ROOT / 'AGENTS.md', TASK6,
        ROOT / 'config/task3_equity_contract.json', ROOT / 'config/task3_equity_price_contract.json'
    ]:
        seal(path)
    original(R4, 'result.json')
    state = dates_csv(original(R4, 'T1_A_nav.csv'))
    targets = dates_csv(original(R2, 'T1_A_targets.csv'))
    assert state.index.equals(targets.index) and len(state) == 669 and state.index[-1] == ANCHOR
    old_targets = json.loads(targets.target_weights_json.iloc[-1])
    close = state.iloc[-1].to_dict()
    carry = dict(cash=close['cash'], nav=close['nav'], risk_on=bool(close['risk_on']),
                 positions=json.loads(close['positions_json']), pending=json.loads(close['sell_residual_target_json']),
                 targets=old_targets, sessions=len(state))
    plan = load(original(R2, 'collection_plan.json'))
    a = load(seal(ASSETS, plan['assets_sha256']))
    assets = {row['symbol']:row for row in a if row['symbol'] in SYMBOLS}
    cfg = load(ROOT / 'config/task3_equity_price_contract.json')
    cfg['provider_contract'].update(required_source_tag='KIWOOM_REGULAR_NOMINAL',canonical_price_scale='NOMINAL_KRW')
    idx, r0_index_close_only = {}, {}
    for board, (code, legacy) in BOARDS.items():
        bars = response(OUT / 'reference' / f'kiwoom_index_{code}.json')['inds_dt_pole_qry']
        table = pd.DataFrame({k:[int(x[field])/100 for x in bars]
                              for k,field in [('open','open_pric'),('high','high_pric'),('low','low_pric'),('close','cur_prc')]},
                             index=pd.to_datetime([x['dt'] for x in bars])).sort_index()
        old = dates_csv(seal(R0 / f'accepted/KR/{legacy}/quote.csv')).loc[ANCHOR:END]
        assert table.index.is_unique
        assert table.loc[old.index].index.equals(old.index)
        compare = table.loc[old.index, ['open','high','low','close']].sub(old[['open','high','low','close']]).abs()
        assert compare.close.lt(.011).all()
        disagreements = compare.index[compare[['open','high','low']].ge(.011).any(axis=1)]
        flat = old.volume.eq(0) & old[['open','high','low','close']].nunique(axis=1).eq(1)
        assert flat.loc[disagreements].all()
        r0_index_close_only[board] = [str(d.date()) for d in disagreements]
        if board == 'KOSPI':
            for p in sorted((OUT / 'reference').glob('kospi_dd_trd_????????.json')):
                krx = next(r for r in response(p)['OutBlock_1'] if r['IDX_NM']=='코스피')
                fields = ['OPNPRC_IDX','HGPRC_IDX','LWPRC_IDX','CLSPRC_IDX']
                assert np.allclose(table.loc[pd.Timestamp(krx['BAS_DD'])], [float(krx[f]) for f in fields], atol=.001, rtol=0)
        idx[board] = table.loc[ANCHOR:END]
    assert idx['KOSPI'].index.equals(idx['KOSDAQ'].index)
    sessions = idx['KOSPI'].loc[BEGIN:END].index
    assert sessions[0] == BEGIN and sessions[-1] == END
    warm = pd.DatetimeIndex(state.index[-80:].append(sessions))
    nominal, gaps, score, elig, actions, bridge_fail = {}, {}, {}, {}, {}, {}
    cross, differences, volume_differences = Counter(), [], []
    officials = {}
    for p in sorted((OUT / 'reference').glob('krx_*_????????.json')):
        officials.update({(r['BAS_DD'],r['ISU_CD']):r for r in response(p)['OutBlock_1']})
    for s in ['069500.KS', *SYMBOLS]:
        p = OUT / 'nominal' / (s[:6] + '.json')
        receipt = load(seal(p.with_suffix('.receipt.json')))
        obj = response(p)
        assert receipt['query']['upd_stkpc_tp']=='0' and receipt['tr']=='ka11081' and obj['stk_cd']==s[:6]
        bars = [r for r in obj['result_list'] if pd.Timestamp(r['dt']) in warm]
        fields = dict(open='open_pric',high='high_pric',low='low_pric',close='cur_prc',volume='trde_qty')
        rows = [dict(date=str(pd.Timestamp(r['dt']).date()), ticker=s[:6],value_approx=int(r['trde_prica'])*1_000_000,
                     **{k:int(r[v]) for k,v in fields.items()}) for r in bars]
        t = _validate_batch(ProviderBatch('KIWOOM',s[:6],tuple(rows),False,'KIWOOM_REGULAR_NOMINAL',
                                          receipt['at'],{}),cfg).set_index('date')
        t.index = pd.to_datetime(t.index)
        t['flags'] = pd.Series({pd.Timestamp(r['dt']):r['upd_stkpc_tp'] for r in bars})
        t = t.reindex(warm)
        check = []
        for r in bars:
            ref = officials.get((r['dt'],s[:6]))
            if ref:
                expected = [int(ref[k]) for k in ['TDD_OPNPRC','TDD_HGPRC','TDD_LWPRC','TDD_CLSPRC','ACC_TRDVOL']]
                actual = [int(r[k]) for k in fields.values()]
                entry = {'symbol':s,'date':r['dt'],'KRX':expected,'KIWOOM':actual}
                if expected[:4] != actual[:4]:
                    differences.append(entry)
                elif expected[4] != actual[4]:
                    volume_differences.append(entry)
                    cross['OHLC_exact_volume_differs'] += 1
                else:
                    cross['exact'] += 1
                check.append({'ticker':s[:6],'date':str(pd.Timestamp(r['dt']).date()),'close':expected[3]})
        if check:
            ref_path = OUT / 'v87_reference.csv'
            pd.DataFrame(check).to_csv(ref_path,index=False)
            audit = _revision_audit(t.reset_index().rename(columns={'index':'date'}).assign(
                date=lambda f:f.date.dt.strftime('%Y-%m-%d')), ref_path, cfg)
            if not audit['passed']:
                differences.append({'symbol':s,'revision_audit':audit})
        gaps[s] = [str(d.date()) for d in t.index[t.close.isna()]]
        nominal[s] = t
        if s not in assets:
            continue
        listing = pd.Timestamp(max(assets[s]['list_date_toss'], assets[s]['list_date_kind']))
        if listing > ANCHOR:
            raise ValueError(f'unsupported identity at year anchor: {s}')
        raw = dates_csv(seal(ROOT / assets[s]['adjusted_path'],assets[s]['adjusted_hash'])).close
        mask = dates_csv(seal(ROOT / assets[s]['eligibility_path'],assets[s]['eligibility_hash'])).eligible.eq(True)
        try:
            track = bridge(raw, t, raw.index[-1])
            tail_dates = track.index[track.index > raw.index[-1]]
            tail_valid = track.pct_change(fill_method=None).reindex(tail_dates).abs().le(.35)
            m = pd.concat([mask, tail_valid]).reindex(warm).eq(True)
        except ValueError as err:
            bridge_fail[s] = str(err)
            track, m = raw, mask.reindex(warm).eq(True)
        elig[s] = m
        score[s] = track.reindex(warm).where(m)
        actions[s] = {pd.Timestamp(r['dt']):r['upd_stkpc_tp'] for r in bars
                      if r['dt'] >= '20260102' and set(r['upd_stkpc_tp'].split(',')) - {'','4'}}
    if differences:
        save(OUT/'price_discrepancies.json',differences)
        raise ValueError('KRX V87 official cross-check failed')
    if not cross['exact'] or gaps['069500.KS']:
        raise ValueError('benchmark inputs incomplete')
    prices = pd.DataFrame(score)
    momentum = prices.div(prices.shift(63)).sub(1).where(prices.rolling(64).count().eq(64)).shift()
    ef = dates_csv(source(ROOT,TASK6)).close
    etf = bridge(ef, nominal['069500.KS'], ef.index[-1])
    assert etf.reindex(warm).notna().all()
    risk = etf.ge(etf.rolling(63).mean()).shift(1,fill_value=False)
    assert bool(risk[ANCHOR]) == carry['risk_on']
    old_flow = pd.read_csv(original(R2, 'normalized.csv.gz'),parse_dates=['trade_date'])
    available, counts = {}, {}
    for s in SYMBOLS:
        r5 = {}
        for p in sorted((OUT/'coverage').glob(f'{s[:6]}_coverage_?.json')):
            rows = response(p)['stk_invsr_orgn']
            for row in rows:
                d = pd.Timestamp(row['dt'])
                if d < BEGIN:
                    continue
                assert d in sessions and d not in r5
                n,o,v = (int(row[k]) for k in ['frgnr_invsr','orgn','acc_trde_prica'])
                r5[d] = v > 0 and max(abs(n),abs(o),abs(n+o)) <= v
        assert len(r5) >= .95 * len(sessions)
        old = old_flow[old_flow.symbol.eq(s)].set_index('trade_date').amount_valid
        coverage = pd.concat([old.loc[:ANCHOR],pd.Series(r5)]).reindex(warm).eq(True)
        counts[s] = len(r5),int(sum(r5.values()))
        available[s] = (coverage & elig[s]).rolling(5).sum().eq(5).shift(1,fill_value=False)
    availability = pd.DataFrame(available)
    picked = carry['targets']
    ledger = []
    prev_risk = carry['risk_on']
    for i,d in enumerate(sessions, start=carry['sessions']):
        on = bool(risk[d])
        decision = i % 5 == 0 or prev_risk != on
        mom = momentum.loc[d]
        eligible = mom[mom.gt(0)&availability.loc[d]]
        if decision:
            picked = dict.fromkeys(eligible.sort_values(ascending=False,kind='stable').index[:4],.2) if on else {}
        ledger.append(dict(date=d, risk_on=on, decision=decision, candidates=len(eligible), targets=picked))
        prev_risk = on
    targets = pd.DataFrame(ledger).set_index('date')
    pd.DataFrame({'risk_on':targets.risk_on, 'decision':targets.decision, 'candidates':targets.candidates,
                  'weights':targets.targets.map(json.dumps)}).to_csv(OUT/'sealed_targets.csv')
    refs = []
    for (d,code),r in officials.items():
        if d in ['20230331','20260102','20261118']:
            refs.append({'date':d,'code':code,'name':r['ISU_NM'],'board':r['MKT_NM'],
                         'cap':int(r['MKTCAP'] or 0),'volume':int(r['ACC_TRDVOL'] or 0),'shares':int(r['LIST_SHRS'] or 0)})
    for board in BOARDS:
        p = original(R4,f'krx_20251230_{board}.json')
        for r in load(p)['OutBlock_1']:
            refs.append({'date':'20251230','code':r['ISU_CD'],'name':r['ISU_NM'],'board':r['MKT_NM'],
                         'cap':int(r['MKTCAP'] or 0),'volume':int(r['ACC_TRDVOL'] or 0),'shares':int(r['LIST_SHRS'] or 0)})
    roster = pd.DataFrame(refs)
    roster.to_csv(OUT/'roster_snapshots.csv',index=False)
    pd.to_pickle(dict(carry=carry, targets=targets, index=idx, nominal=nominal, actions=actions, assets=assets),
                 OUT/'sealed_inputs.pkl')
    save(OUT/'preflight.json',dict(hashes=hashes, carry=carry, sessions=len(sessions), nominal_gaps=gaps,
         cross=dict(cross), volume_scope_differences=volume_differences, r0_index_close_only=r0_index_close_only, bridge_fail=bridge_fail, flow_coverage=counts, min_candidates=int(targets.candidates.min()),
         decisions=int(targets.decision.sum()), pending_non_cash=actions_by_date(actions),
         outputs={n:sha(OUT/n) for n in ['sealed_targets.csv','sealed_inputs.pkl','roster_snapshots.csv']}))


def actions_by_date(actions):
    return {str(d.date())+':'+s:f for s,items in actions.items() for d,f in items.items()}


if __name__ == '__main__':
    gather()

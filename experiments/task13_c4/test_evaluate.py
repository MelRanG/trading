"""Synthetic tests of the frozen C4 statistic and failure behavior."""

import json

import numpy as np
import pandas as pd
import pytest

from experiments.task13_c4 import evaluate as stats


OLD_PRIMARY = [{'test': f'TEST{i}', 'p': .1 + i / 20} for i in range(10)]


def _rows():
    rng = np.random.default_rng(42)
    groups = []
    for year, size, effect in [(2020, 31, .9), (2021, 47, .5), (2022, 37, .75)]:
        price = rng.normal(size=(size, len(stats.CONTROLS)))
        feature = np.round(rng.normal(size=size), 1)
        outcome = effect * feature + .2 * price[:, 0] + rng.normal(scale=.3, size=size)
        group = pd.DataFrame(price, columns=stats.CONTROLS)
        group['CIK'] = [str(i) for i in range(size)]
        group['symbol'] = [f'SYM{i}' for i in range(size)]
        group['sector_current'] = ['Tech' if i % 2 == 0 else 'Health' for i in range(size)]
        group['filed_year'] = year
        group['feature'] = feature
        group['outcome'] = outcome
        groups.append(group)
    return pd.concat(groups, ignore_index=True)


def _oracle(rows):
    annual = []
    for _, year in rows.groupby('filed_year'):
        ranked = year.loc[:, list(stats.VALUE_COLUMNS)].rank(method='average')
        raw = ranked[['feature', 'outcome']].to_numpy()
        z = np.column_stack((np.ones(len(ranked)), ranked.loc[:, list(stats.CONTROLS)]))
        residual = raw - z @ np.linalg.pinv(z) @ raw
        annual.append(np.corrcoef(residual.T)[0, 1])
    return annual


def _evaluate(rows):
    return stats.evaluate(rows, task14_primary_tests=OLD_PRIMARY, c1_primary_p=.3)


def test_primary_is_equal_filing_year_mean_and_uses_frozen_family():
    rows = _rows()
    result = _evaluate(rows)
    annual = _oracle(rows)
    assert [r['partial_RankIC'] for r in result['annual'].values()] == pytest.approx(annual)
    primary = result['summary']['primary']
    assert primary['mean_partial_RankIC'] == pytest.approx(np.mean(annual))
    assert primary['mean_partial_RankIC'] != pytest.approx(np.average(annual, weights=[31, 47, 37]))
    assert primary['valid_draws'] == primary['requested_draws'] == 5000
    assert primary['p_positive'] == pytest.approx(1 / 5001)
    assert primary['CI95'][0] > 0
    assert result['multiplicity']['Holm40_primary_p'] == pytest.approx(40 / 5001)
    assert result['multiplicity']['reserved_p1_slots'] == 28
    assert result['multiplicity']['slots'][10] == {'slot': 'Task13-C1:US', 'p': .3}
    assert all(result['decision_gates'].values())
    spreads = [row['quintile']['gross_top_minus_bottom'] for row in result['annual'].values()]
    assert result['summary']['quintile']['gross_top_minus_bottom'] == pytest.approx(np.mean(spreads))
    json.dumps(result, allow_nan=False)


def test_bootstrap_and_sensitivities_rerank_their_filing_subsamples(monkeypatch):
    monkeypatch.setattr(stats, 'BOOTSTRAP_DRAWS', 25)
    rows = _rows()
    result = _evaluate(rows.sample(frac=1, random_state=2))
    primary = result['summary']['primary']
    observed = primary['mean_partial_RankIC']
    sensitivity = result['sensitivity']
    assert sensitivity['leave_one_issuer_out']['0']['mean_partial_RankIC'] == pytest.approx(
        np.mean(_oracle(rows[rows['CIK'] != '0']))
    )
    assert sensitivity['leave_one_year_out']['2021']['mean_partial_RankIC'] == pytest.approx(
        np.mean(_oracle(rows[rows['filed_year'] != 2021]))
    )
    sector = sensitivity['leave_one_current_sector_out']['Tech']
    assert sector['mean_partial_RankIC'] == pytest.approx(
        np.mean(_oracle(rows[rows['sector_current'] != 'Tech']))
    )
    assert sector['excluded_rows_by_year'] == {'2020': 16, '2021': 24, '2022': 19}
    names = np.array(sorted(rows['CIK'].unique()))
    groups = {name: rows[rows['CIK'] == name] for name in names}
    rng = np.random.default_rng(stats.BOOTSTRAP_SEED)
    means = np.array([
        np.mean(_oracle(pd.concat([groups[names[i]] for i in rng.integers(len(names), size=len(names))])))
        for _ in range(25)
    ])
    assert primary['CI95'] == pytest.approx(np.quantile(means, [.025, .975]))
    assert primary['p_positive'] == (1 + np.count_nonzero(means - observed >= observed)) / 26


def test_degenerate_year_cannot_be_silently_removed():
    rows = _rows()
    rows.loc[rows['filed_year'] == 2021, 'feature'] = 0
    result = _evaluate(rows)
    assert result['annual']['2021']['partial_RankIC'] is None
    assert result['annual']['2021']['partial_unavailable_reason'] == 'CONSTANT_OR_SPANNED_RANKS'
    assert result['annual']['2021']['feature_residual_variance_fraction'] == 0
    assert result['summary']['primary']['mean_partial_RankIC'] is None
    assert result['summary']['primary']['valid_years'] == 2
    assert result['multiplicity']['Holm40_primary_p'] is None
    assert not any(result['decision_gates'].values())
    json.dumps(result, allow_nan=False)


def test_paired_inputs_fail_closed_and_tied_quintiles_share_weight():
    rows = _rows()
    with pytest.raises(ValueError, match='one filing'):
        _evaluate(pd.concat([rows, rows.iloc[:1]]))
    rows.loc[0, 'MOM63'] = np.inf
    with pytest.raises(ValueError, match='Nonfinite'):
        _evaluate(rows)

    score = np.array([0, 1, 1, 2, 3, 4, 5, 6, 6, 7])
    y = np.arange(10)
    assert stats._tail_mean(score, y, 2, top=True) == 8.25
    assert stats._tail_mean(score, y, 2, top=False) == .75

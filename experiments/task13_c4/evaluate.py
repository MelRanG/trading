"""The C4 H252 statistic on the admitted, frozen paired rows."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from experiments.task14.stats_eval import corr, holm


CONTROLS = ('REV5', 'MOM20', 'MOM63', 'LOWVOL20', 'beta')
VALUE_COLUMNS = ('feature', *CONTROLS, 'outcome')
IDENTITY_COLUMNS = ('CIK', 'filed_year', 'symbol', 'sector_current')
BOOTSTRAP_DRAWS = 5000
BOOTSTRAP_SEED = 130401
HOLM_FAMILY = 40
ROOT = Path(__file__).resolve().parents[2]


def _partial(ranks):
    # Use the same intercept and controls for both rank projections.
    y = ranks[:, [0, -1]]
    design = np.column_stack((np.ones(len(ranks)), ranks[:, 1:-1]))
    coef, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ coef
    centered = y - y.mean(axis=0)
    full_ss = np.sum(centered ** 2, axis=0)
    residual_ss = np.sum(residual ** 2, axis=0)
    fractions = np.divide(residual_ss, full_ss, out=np.zeros(2), where=full_ss > 0)
    result = {
        'partial_RankIC': None,
        'feature_residual_variance_fraction': float(fractions[0]),
        'outcome_residual_variance_fraction': float(fractions[1]),
        'control_design_rank': int(rank),
        'partial_unavailable_reason': None,
    }
    if len(ranks) - rank < 2 or rank != design.shape[1]:
        result['partial_unavailable_reason'] = 'CONTROL_DESIGN_SINGULAR_OR_TOO_FEW_RESIDUAL_DF'
    elif np.any(fractions <= np.finfo(float).eps):
        result['partial_unavailable_reason'] = 'CONSTANT_OR_SPANNED_RANKS'
    else:
        result['partial_RankIC'] = float(np.clip(
            residual[:, 0] @ residual[:, 1] / np.sqrt(residual_ss.prod()), -1, 1,
        ))
    return result


def _rank_correlation(x, y):
    value = corr(x, y)
    return value if np.isfinite(value) else None


def _tail_mean(feature, outcome, size, *, top):
    # Share a boundary position equally across all issuers with a tied score.
    ordered = feature if top else -feature
    threshold = np.partition(ordered, len(ordered) - size)[len(ordered) - size]
    inside = ordered > threshold
    tied = ordered == threshold
    return float((outcome[inside].sum() + (size - inside.sum()) * outcome[tied].mean()) / size)


def _year_stats(values):
    ranks = rankdata(values, method='average', axis=0)
    result = _partial(ranks)
    result['observations'] = len(values)
    result['simple_RankIC'] = _rank_correlation(ranks[:, 0], ranks[:, -1])
    result['feature_baseline_rank_overlap'] = {
        name: _rank_correlation(ranks[:, 0], ranks[:, i])
        for i, name in enumerate(CONTROLS, start=1)
    }
    result['baseline_RankIC'] = {
        name: _rank_correlation(ranks[:, i], ranks[:, -1])
        for i, name in enumerate(CONTROLS, start=1)
    }
    result['baseline_IC'] = {
        name: _rank_correlation(values[:, i], values[:, -1])
        for i, name in enumerate(CONTROLS, start=1)
    }
    size = len(values) // 5
    top = _tail_mean(values[:, 0], values[:, -1], size, top=True) if size else None
    bottom = _tail_mean(values[:, 0], values[:, -1], size, top=False) if size else None
    result['quintile'] = {
        'nominal_names_per_tail': size,
        'top_mean_gross_outcome': top,
        'bottom_mean_gross_outcome': bottom,
        'gross_top_minus_bottom': top - bottom if size else None,
    }
    return result


def _mean_complete(scores):
    return float(np.mean(scores)) if scores and all(score is not None for score in scores) else None


def _partial_only(values):
    if not len(values):
        return None
    return _partial(rankdata(values, method='average', axis=0))['partial_RankIC']


def _bootstrap(cohorts, issuer_count, observed):
    result = {
        'method': 'issuer cluster resampling with replacement; keep filings together; rerank within each filing year',
        'scope': 'Conditional on observed filing years; no correction for overlapping H252 calendar windows or shared market shocks.',
        'seed': BOOTSTRAP_SEED,
        'requested_draws': BOOTSTRAP_DRAWS,
        'valid_draws': 0,
        'invalid_draws': 0,
        'CI95': None,
        'p_positive': None,
    }
    if observed is None:
        result['unavailable_reason'] = 'PRIMARY_UNAVAILABLE'
        return result

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    means = []
    for _ in range(BOOTSTRAP_DRAWS):
        drawn = rng.integers(issuer_count, size=issuer_count)
        counts = np.bincount(drawn, minlength=issuer_count)
        scores = [_partial_only(np.repeat(values, counts[issuer_ids], axis=0))
                  for _, values, issuer_ids, _ in cohorts]
        value = _mean_complete(scores)
        if value is not None:
            means.append(value)

    result['valid_draws'] = len(means)
    result['invalid_draws'] = BOOTSTRAP_DRAWS - len(means)
    if result['invalid_draws']:
        result['unavailable_reason'] = 'SOME_DRAWS_LOST_IDENTIFIABLE_FROZEN_ANNUAL_ESTIMAND'
        return result
    means = np.asarray(means)
    result['CI95'] = np.quantile(means, [.025, .975]).tolist()
    result['p_positive'] = (1 + int(np.count_nonzero(means - observed >= observed))) / (BOOTSTRAP_DRAWS + 1)
    return result


def _sensitivity(cohorts, annual, labels):
    year_scores = [row['partial_RankIC'] for row in annual.values()]
    observed = _mean_complete(year_scores)

    def summary(scores):
        mean = _mean_complete(scores)
        return {
            'mean_partial_RankIC': mean,
            'delta_from_full': mean - observed if mean is not None and observed is not None else None,
            'valid_years': sum(x is not None for x in scores),
            'required_years': len(scores),
        }

    issuer = {}
    for issuer_id, cik in enumerate(labels):
        scores = [score if issuer_id not in ids else _partial_only(values[ids != issuer_id])
                  for score, (_, values, ids, _) in zip(year_scores, cohorts)]
        issuer[cik] = summary(scores)

    year = {str(yr): summary([score for j, score in enumerate(year_scores) if j != i])
            for i, (yr, _, _, _) in enumerate(cohorts)}
    sectors = sorted({sector for _, _, _, membership in cohorts for sector in membership})
    sector_rows = {}
    for sector in sectors:
        scores = [score if sector not in names else _partial_only(values[names != sector])
                  for score, (_, values, _, names) in zip(year_scores, cohorts)]
        counts = {str(yr): int(np.count_nonzero(names == sector))
                  for yr, _, _, names in cohorts}
        sector_rows[sector] = {'excluded_rows_by_year': counts, **summary(scores)}
    return {
        'leave_one_issuer_out': issuer,
        'leave_one_year_out': year,
        'leave_one_current_sector_out': sector_rows,
        'sector_scope': 'Descriptive with current sector labels; historical point-in-time sector data unavailable.',
    }


def _multiplicity(p, task14_tests, c1_p):
    if task14_tests is None:
        task14 = ROOT / 'runtime/task14/validation.json'
        task14_tests = json.loads(task14.read_text())['primary_tests']
    if c1_p is None:
        c1 = ROOT / 'runtime/task13_c1/evaluation.json'
        c1_p = json.loads(c1.read_text())['US']['local_family1_p']
    prior = [{'slot': f"Task14:{test['test']}", 'p': float(test['p'])} for test in task14_tests]
    if len(prior) != 10 or len({test['slot'] for test in prior}) != 10:
        raise ValueError('Expected ten distinct stored Task14 primary tests')
    prior.append({'slot': 'Task13-C1:US', 'p': float(c1_p)})
    if any(not 0 <= test['p'] <= 1 for test in prior):
        raise ValueError('Historical primary p-value outside [0, 1]')
    reserved = HOLM_FAMILY - len(prior) - 1
    slots = prior + [{'slot': f'reserved-{i + 1}', 'p': 1.0} for i in range(reserved)]
    slots.append({'slot': 'Task13-C4:US', 'p': p})
    ps = [test['p'] for test in slots]
    adjusted = holm(ps)[-1] if p is not None else None
    return {
        'family_size': HOLM_FAMILY,
        'reserved_p1_slots': reserved,
        'slots': slots,
        'Holm40_primary_p': adjusted,
        'scope': 'Reserved historical family; older adaptive trials are incompletely enumerated.',
    }


def evaluate(rows: pd.DataFrame, *, task14_primary_tests=None, c1_primary_p=None):
    """Calculate the US C4 H252 diagnostics without changing the paired sample."""
    columns = list((*IDENTITY_COLUMNS, *VALUE_COLUMNS))
    rows = rows.loc[:, columns].copy()
    identity = rows.loc[:, list(IDENTITY_COLUMNS)]
    if rows.empty or identity.isna().any().any():
        raise ValueError('Paired rows and complete identity fields are required')
    for column in ('CIK', 'symbol', 'sector_current'):
        rows[column] = rows[column].astype(str)
        if rows[column].str.strip().eq('').any():
            raise ValueError(f'Empty paired-row field: {column}')
    if not pd.api.types.is_integer_dtype(rows['filed_year']):
        raise ValueError('filed_year must be integer')
    if rows.duplicated(['CIK', 'filed_year']).any():
        raise ValueError('Expected no more than one filing per CIK and filing year')
    if not np.isfinite(rows.loc[:, list(VALUE_COLUMNS)].to_numpy(dtype=float)).all():
        raise ValueError('Nonfinite paired feature, control, or outcome')

    rows = rows.sort_values(['filed_year', 'CIK'], kind='stable')
    labels = sorted(rows['CIK'].unique())
    issuer_codes = {cik: i for i, cik in enumerate(labels)}
    cohorts = [(int(year), group.loc[:, list(VALUE_COLUMNS)].to_numpy(dtype=float),
                group['CIK'].map(issuer_codes).to_numpy(dtype=int), group['sector_current'].to_numpy())
               for year, group in rows.groupby('filed_year', sort=True)]
    annual = {str(year): _year_stats(matrix) for year, matrix, _, _ in cohorts}
    yearly = list(annual.values())
    primary = _mean_complete([row['partial_RankIC'] for row in yearly])
    bootstrap = _bootstrap(cohorts, len(labels), primary)
    multiplicity = _multiplicity(bootstrap['p_positive'], task14_primary_tests, c1_primary_p)
    sensitivity = _sensitivity(cohorts, annual, labels)

    def all_positive(diagnostics):
        return all(row['mean_partial_RankIC'] is not None and row['mean_partial_RankIC'] > 0
                   for row in diagnostics.values())

    ci = bootstrap['CI95']
    adjusted = multiplicity['Holm40_primary_p']
    return {
        'sample': {'rows': len(rows), 'issuers': len(labels), 'filing_years': list(annual)},
        'summary': {
            'primary': {
                'estimand': 'Equal filing-year mean of Pearson correlations of feature and outcome ranks after projection on intercept and all five control ranks in each year.',
                'mean_partial_RankIC': primary,
                'valid_years': sum(row['partial_RankIC'] is not None for row in yearly),
                'required_years': len(yearly),
                **bootstrap,
            },
            **{name: _mean_complete([row[name] for row in yearly]) for name in (
                'simple_RankIC', 'feature_residual_variance_fraction', 'outcome_residual_variance_fraction',
            )},
            **{name: {control: _mean_complete([row[name][control] for row in yearly])
                      for control in CONTROLS}
               for name in ('feature_baseline_rank_overlap', 'baseline_RankIC', 'baseline_IC')},
            'quintile': {
                'rule': 'Floor n/5 per tail with proportional weight on equal boundary scores; years receive equal weights.',
                **{name: _mean_complete([row['quintile'][name] for row in yearly]) for name in (
                    'top_mean_gross_outcome', 'bottom_mean_gross_outcome', 'gross_top_minus_bottom',
                )},
            },
        },
        'annual': annual,
        'multiplicity': multiplicity,
        'sensitivity': sensitivity,
        'decision_gates': {
            'positive_primary': primary is not None and primary > 0,
            'conditional_CI_lower_positive': ci is not None and ci[0] > 0,
            'conditional_Holm40_pass': adjusted is not None and adjusted < .05,
            'all_issuer_leave_one_out_positive': all_positive(sensitivity['leave_one_issuer_out']),
            'all_year_leave_one_out_positive': all_positive(sensitivity['leave_one_year_out']),
        },
        'limitations': [
            'Exposed historical survivor sample and few shared filing-year cohorts.',
            'Issuer cluster intervals and p-values condition on the observed years; market shocks and overlapping H252 calendar windows are not corrected by issuer clustering.',
            'Leave-one-year-out is a sensitivity analysis and supplies no calendar-dependence-adjusted interval or p-value.',
            'Gross cohort tail differences are event-outcome diagnostics without portfolio construction, trading costs or independent evidence.',
        ],
    }

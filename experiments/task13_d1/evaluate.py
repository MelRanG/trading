"""Frozen D1 statistics on already paired rows."""
import numpy as np
import pandas as pd

from experiments.task13_d0.precheck import CONTROLS
from experiments.task13_c4.evaluate import _tail_mean
from experiments.task14.stats_eval import block_mean, corr, holm, residual

BLOCK, DRAWS, SEED = 3, 5000, 130501


def partial(rows):
    rank = rows[["score",*CONTROLS,"H20"]].rank()
    z = rank[CONTROLS].to_numpy()
    x, _ = residual(rank.score,z)
    y, _ = residual(rank.H20,z)
    if np.linalg.matrix_rank(np.column_stack((np.ones(len(z)),z))) != len(CONTROLS)+1:
        return None
    value = corr(x,y)
    return float(value) if np.isfinite(value) else None


def calculate(paired, schedule, prior):
    groups, daily = {}, {}
    for date,bucket in paired.items():
        rows = pd.DataFrame(bucket["rows"])
        assert len(rows)>=50 and rows.symbol.is_unique
        assert np.isfinite(rows[["score",*CONTROLS,"H20"]].to_numpy()).all()
        rank = rows[["score",*CONTROLS,"H20"]].rank()
        x, _ = residual(rank.score,rank[CONTROLS])
        pc = partial(rows)
        if pc is None:
            raise ValueError(f"Primary unidentified on sealed date {date}")
        tail = len(rows)//5
        scores, target = rows.score.to_numpy(),rows.H20.to_numpy()
        top = _tail_mean(scores,target,tail,top=True)
        bottom = _tail_mean(scores,target,tail,top=False)
        daily[date] = {"n":len(rows),"partial_RankIC":pc,
                       "RankIC":float(corr(rank.score,rank.H20)),
                       "baseline_RankIC":{k:float(corr(rank[k],rank.H20)) for k in CONTROLS},
                       "overlap":{k:float(corr(rank[k],rank.score)) for k in CONTROLS},
                       "residual_rank_variance_fraction":float(np.var(x)/np.var(rank.score)),
                       "top":top,"bottom":bottom,"spread":top-bottom}
        groups[date] = rows
    series = pd.Series({d:v["partial_RankIC"] for d,v in daily.items()}).reindex(schedule)
    stats = block_mean(series,BLOCK,DRAWS,SEED)
    # Same RNG indices as block_mean, using availability only to count valid draws.
    n = len(series)
    starts = np.random.default_rng(SEED).integers(0,n,size=(DRAWS,int(np.ceil(n/BLOCK))))
    idx = ((starts[:,:,None]+np.arange(BLOCK))%n).reshape(DRAWS,-1)[:,:n]
    stats["valid_draws"] = int(series.notna().to_numpy()[idx].any(axis=1).sum())
    stats["requested_draws"],stats["seed"] = DRAWS,SEED
    # Library helper's count//block is not an effective independent sample count.
    stats.pop("nonoverlap_blocks_upper_bound",None)
    if stats["valid_draws"]<DRAWS or stats["std"]<=0:
        stats["p_positive"] = None
        stats["CI95"] = None
    p = stats["p_positive"]
    adjusted = holm([*prior,p])[-1] if p is not None else None
    years = {year:{"n":len(v),"positive":int((v>0).sum()),"mean":float(v.mean())}
             for year, v in series.dropna().groupby(lambda d:d[:4])}
    leave_date = {d:float(series.drop(d).mean()) for d in groups}
    leave_symbol = {}
    for sym in sorted({s for frame in groups.values() for s in frame.symbol}):
        values = [partial(frame[frame.symbol!=sym]) if sym in set(frame.symbol)
                  else daily[d]["partial_RankIC"] for d,frame in groups.items()]
        leave_symbol[sym] = float(np.mean(values)) if all(v is not None for v in values) else None
    ci = stats["CI95"]
    passes = (stats["mean"]>0 and ci is not None and ci[0]>0 and adjusted is not None
              and adjusted<.05 and len(years)==2 and all(v["mean"]>0 for v in years.values())
              and min(leave_date.values())>0
              and all(v is not None and v>0 for v in leave_symbol.values()))
    classification = ("HISTORICAL_RESEARCH_CANDIDATE" if passes else
                      "NO_INCREMENTAL_EVIDENCE" if stats["mean"]<=0 else "INSUFFICIENT_EVIDENCE")
    mean = lambda k:float(np.mean([v[k] for v in daily.values()]))
    submean = lambda k:{c:float(np.mean([v[k][c] for v in daily.values()])) for c in CONTROLS}
    return {"classification":"HISTORICAL_EXPLORATORY","decision":classification,
            "primary":stats,"RankIC":mean("RankIC"),"baseline_RankIC":submean("baseline_RankIC"),
            "overlap":submean("overlap"),"residual_rank_variance_fraction":mean("residual_rank_variance_fraction"),
            "gross_tails":{k:mean(k) for k in ["top","bottom","spread"]},
            "daily":daily,"years":years,"leave_date":leave_date,"leave_symbol":leave_symbol,
            "Holm41":adjusted,"family_p_values":[*prior,p],
            "inference_scope":"Conditional approximate circular-block inference on exposed date grid with gaps; common shocks and name repetition remain."}

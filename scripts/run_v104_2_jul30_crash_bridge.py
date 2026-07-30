from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OBS = ROOT / 'data/observations/v104_2_verified_jul30_crash_prices.csv'
POSITIONS = ROOT / 'reports/v104_2_jul30_crash_bridge/v104_2_jul03_actual_positions.csv'
OUT = ROOT / 'reports/v104_2_jul30_crash_bridge'

def run() -> pd.DataFrame:
    obs = pd.read_csv(OBS, dtype={'ticker': str})
    positions = pd.read_csv(POSITIONS)
    px = obs[obs.ticker.isin(['069500','395160'])].pivot(index='date', columns='ticker', values='close').dropna().sort_index()
    rows=[]
    for _, r in positions.iterrows():
        holdings=json.loads(r['holdings'])
        for date, p in px.iterrows():
            nav=float(r['cash'])+sum(float(q)*float(p[t]) for t,q in holdings.items())
            rows.append({'candidate_id':r['candidate_id'],'date':date,'nav':nav,'cumulative_return_pct':(nav/10_000_000-1)*100,'change_from_jul03_pct':(nav/float(r['nav'])-1)*100})
    path=pd.DataFrame(rows)
    path['running_peak']=path.groupby('candidate_id').nav.cummax()
    path['drawdown_pct']=(path.nav/path.running_peak-1)*100
    path.to_csv(OUT/'v104_2_daily_nav_bridge.csv',index=False)
    summary=[]
    for cid, g in path.groupby('candidate_id'):
        g=g.set_index('date')
        pre, post=float(g.loc['2026-07-27','nav']), float(g.loc['2026-07-30','nav'])
        summary.append({'candidate_id':cid,'nav_jul27':pre,'nav_jul30':post,'crash_loss_krw':post-pre,'crash_return_pct':(post/pre-1)*100,'cumulative_return_jul27_pct':float(g.loc['2026-07-27','cumulative_return_pct']),'cumulative_return_jul30_pct':float(g.loc['2026-07-30','cumulative_return_pct']),'change_from_jul03_to_jul27_pct':float(g.loc['2026-07-27','change_from_jul03_pct']),'change_from_jul03_to_jul30_pct':float(g.loc['2026-07-30','change_from_jul03_pct']),'bridge_max_drawdown_pct':float(g.drawdown_pct.min())})
    result=pd.DataFrame(summary).sort_values('nav_jul30',ascending=False)
    result.to_csv(OUT/'v104_2_precrash_vs_crash_summary.csv',index=False)
    return result

if __name__ == '__main__':
    print(run().to_string(index=False))

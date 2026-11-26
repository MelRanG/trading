"""V2.1 presentation fix: native 'excess' keys must contain actual excess.
Does not change factor signals, execution, fees, or frozen V2 returns.
"""
import numpy as np

def native_metrics(metrics,nav):
 benchmark=nav.exposure*nav.market_intraday
 gross=nav.gross_return;net=nav.net_return
 def relative_mdd(ret):
  relative=(1+ret).cumprod()/(1+benchmark).cumprod();peak=relative.cummax().clip(lower=1.)
  return float((relative/peak-1).min())
 delta=gross-benchmark;vol=float(delta.std(ddof=0))
 return {'IC':metrics['IC'],'RankIC':metrics['IC'],'ICIR':metrics['ICIR'],
 '1day.excess_return_without_cost.annualized_return':float(delta.mean()*252),
 '1day.excess_return_without_cost.max_drawdown':relative_mdd(gross),
 '1day.excess_return_without_cost.information_ratio':float(delta.mean()/vol*np.sqrt(252)) if vol else 0.,
 '1day.excess_return_with_cost.annualized_return':float((net-benchmark).mean()*252),
 '1day.excess_return_with_cost.max_drawdown':relative_mdd(net)}

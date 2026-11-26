import unittest
import pandas as pd
from native_metrics import native_metrics
class NativeMetricTests(unittest.TestCase):
 def test_identical_exposure_adjusted_market_is_zero_excess(self):
  f=pd.DataFrame({'exposure':[.8,.4,.8],'market_intraday':[.02,-.01,.01]});f['gross_return']=f.exposure*f.market_intraday;f['net_return']=f.gross_return
  r=native_metrics({'IC':.01,'ICIR':1.},f)
  self.assertAlmostEqual(r['1day.excess_return_without_cost.annualized_return'],0.);self.assertAlmostEqual(r['1day.excess_return_with_cost.max_drawdown'],0.)
 def test_fee_drag_is_net_excess_not_gross_alpha(self):
  f=pd.DataFrame({'exposure':[.8]*3,'market_intraday':[.02]*3,'gross_return':[.016]*3,'net_return':[.015]*3});r=native_metrics({'IC':.01,'ICIR':1.},f)
  self.assertAlmostEqual(r['1day.excess_return_without_cost.annualized_return'],0.);self.assertAlmostEqual(r['1day.excess_return_with_cost.annualized_return'],-.252)
if __name__=='__main__':unittest.main()

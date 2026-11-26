import unittest
import numpy as np,pandas as pd
from aligned import evaluate
class AlignmentTests(unittest.TestCase):
 def fixture(self):
  dates=pd.bdate_range('2024-01-01',periods=65);frames={}
  for i in range(6):
   # Large overnight repricing, but exactly zero intraday return.
   px=np.arange(65,dtype=float)+100+i;frames[str(i)]=pd.DataFrame({'open':px,'close':px,'volume':1e8},index=dates)
  score=pd.DataFrame(0.,index=dates,columns=list(frames));score.loc[dates[31],:]=np.arange(1,7)
  return dates,frames,score
 def test_no_overnight_pnl_and_exact_next_session(self):
  d,f,s=self.fixture();m,nav,fills=evaluate(s,f,start=str(d[25].date()),end=str(d[-1].date()));self.assertTrue((nav.gross_return==0).all());self.assertLess(m['return_pct'],0);self.assertEqual(set(fills.date),{str(d[32])});self.assertEqual(m['terminal_positions'],0);self.assertEqual(len(fills),4)
 def test_cash_reconciliation_both_sides(self):
  d,f,s=self.fixture();m,nav,fills=evaluate(s,f,start=str(d[25].date()),end=str(d[-1].date()));pnl=sum(x.quantity*(x.sell_price-x.buy_price)-x.buy_fee-x.sell_fee for x in fills.itertuples());self.assertAlmostEqual(nav.nav.iloc[-1],100000+pnl,places=7);self.assertTrue((fills.buy_fee>0).all() and (fills.sell_fee>0).all())
 def test_future_change_cannot_change_past(self):
  d,f,s=self.fixture();_,a,_=evaluate(s,f,start=str(d[25].date()),end=str(d[-1].date()));g={k:v.copy() for k,v in f.items()}
  for v in g.values():v.loc[d[45]:,'close']*=2
  _,b,_=evaluate(s,g,start=str(d[25].date()),end=str(d[-1].date()));pd.testing.assert_frame_equal(a[a.date<str(d[45])],b[b.date<str(d[45])])
if __name__=='__main__':unittest.main()

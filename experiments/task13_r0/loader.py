"""Thin DatasetH-compatible research adapter, same Task13 five causal features.
Native generation may consume OHLCV directly instead; no model training here.
"""
import pandas as pd,numpy as np

def supervised(data,H,cutoff='2022-12-31',warmup=63):
 data=data.loc[data.index.get_level_values('datetime')<=pd.Timestamp(cutoff)].sort_index();op=data['$open'].unstack('instrument');days=op.index;target=op.shift(-H-1)/op.shift(-1)-1;good=np.isfinite(data.iloc[:,:5]).all(axis=1).unstack('instrument')
 for j in range(1,H+2):target=target.where(good.shift(-j,fill_value=False))
 past=good.rolling(warmup,min_periods=warmup).sum().eq(warmup);past.iloc[:warmup]=False;target=target.where(past);parts=[]
 for symbol,g in data.groupby(level='instrument'):
  f=g.droplevel('instrument');r=f['$close'].pct_change(fill_method=None);x=pd.DataFrame({'ret1':r,'mom20':f['$close']/f['$close'].shift(20)-1,'mom60':f['$close']/f['$close'].shift(60)-1,'vol20':r.rolling(20,min_periods=20).std(),'relative_volume20':f['$volume']/f['$volume'].rolling(20,min_periods=20).mean()-1});x['instrument']=symbol;parts.append(x.set_index('instrument',append=True))
 X=pd.concat(parts).sort_index();y=target.stack(future_stack=True).rename('H'+str(H));index=X.index.intersection(y.dropna().index);X=X.loc[index];y=y.loc[index];valid=np.isfinite(X).all(axis=1)&np.isfinite(y);X=X.loc[valid];y=y.loc[valid];frame=pd.concat({'feature':X,'label':y.to_frame()},axis=1)
 end=pd.Series(days,index=days).shift(-H-1);maturity=frame.index.get_level_values(0).map(end);assert len(frame) and maturity.max()<=pd.Timestamp(cutoff)
 return frame,{'H':H,'rows':len(frame),'dates':frame.index.get_level_values(0).nunique(),'last_target':str(maturity.max()),'last_signal':str(frame.index.get_level_values(0).max()),'cutoff':cutoff,'normalization':'caller fits trainonly; no fit here','finite_features':True}

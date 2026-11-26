"""Small evaluation utilities, not a research/statistical service.

Circular-block indexing follows v103_review_feedback_agent.engine lines195ff;
retain missing calendar slots, add CIs and a centered-null test rather than
mislabel its positive-bootstrap frequency as a formal null p-value.
"""
import numpy as np,pandas as pd
from scipy.stats import spearmanr

def block_mean(series,H,samples=5000,seed=1401):
 x=pd.to_numeric(series,errors='coerce').to_numpy(float);n=len(x);good=np.isfinite(x);count=int(good.sum())
 if count<2:return {'mean':float(np.nanmean(x)) if count else None,'n':count,'CI95':None,'p_positive':1.0,'calendar_slots':n}
 mu=float(np.nanmean(x));rng=np.random.default_rng(seed);starts=rng.integers(0,n,size=(samples,int(np.ceil(n/H))));idx=((starts[:,:,None]+np.arange(H))%n).reshape(samples,-1)[:,:n]
 with np.errstate(invalid='ignore'):means=np.nanmean(x[idx],axis=1)
 means=means[np.isfinite(means)];centered=means-mu;p=(1+int(np.sum(centered>=mu)))/(len(means)+1)
 return {'mean':mu,'median':float(np.nanmedian(x)),'std':float(np.nanstd(x,ddof=1)),'positive_fraction':float(np.mean(x[good]>0)),'n':count,'calendar_slots':n,'nonoverlap_blocks_upper_bound':count//H,'CI95':np.quantile(means,[.025,.975]).tolist(),'p_positive':float(p),'block':H}

def holm(ps):
 a=np.array(ps,float);order=np.argsort(a,kind='stable');out=np.ones(len(a));running=0.
 for k,i in enumerate(order):running=max(running,min(1.,float((len(a)-k)*a[i])));out[i]=running
 return out.tolist()

def residual(x,z):
 x=np.asarray(x,float);z=np.asarray(z,float);design=np.column_stack([np.ones(len(z)),z]);beta=np.linalg.lstsq(design,x,rcond=None)[0];return x-design@beta,beta

def corr(x,y,rank=False):
 x=np.asarray(x,float);y=np.asarray(y,float);keep=np.isfinite(x)&np.isfinite(y);x=x[keep];y=y[keep]
 if len(x)<3 or np.ptp(x)<1e-12 or np.ptp(y)<1e-12:return np.nan
 return float(spearmanr(x,y).statistic if rank else np.corrcoef(x,y)[0,1])

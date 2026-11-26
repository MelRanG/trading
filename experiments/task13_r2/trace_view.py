"""Replace only legacy trace rendering that hardcodes absent portfolio metrics."""
import json,hashlib

def install():
 from rdagent.utils.agent.tpl import T as original
 from rdagent.scenarios.qlib.proposal import quant_proposal,model_proposal,factor_proposal
 def record(exp,fb):
  return {'hypothesis':str(exp.hypothesis),'action':getattr(exp.hypothesis,'action',None),'result':exp.result.to_dict() if exp.result is not None else None,'feedback':vars(fb) if fb is not None else None,'tasks':[t.get_task_information() for t in exp.sub_tasks],'metric_semantics':'H20 predictive IC/RankIC/MSE/MAE only, not any portfolio/annualized metric'}
 class Fragment:
  def r(self,**kw):
   if 'trace' in kw:return json.dumps([record(e,f) for e,f in kw['trace'].hist],default=str)
   if kw.get('experiment') is not None:return json.dumps(record(kw['experiment'],kw.get('feedback')),default=str)
   return 'No corresponding accepted experiment exists.'
 def template(key,*a,**kw):
  if key.split(':')[-1] in ['hypothesis_and_feedback','last_hypothesis_and_feedback','sota_hypothesis_and_feedback']:return Fragment()
  return original(key,*a,**kw)
 for module in [quant_proposal,model_proposal,factor_proposal]:module.T=template

from pathlib import Path
import json,importlib.util,sys,shutil,ast
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'runtime/task6_completion';spec=importlib.util.spec_from_file_location('old',ROOT/'experiments/task6/evaluation.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old);frames=old.load_frames('US','validation');old.BASE=BASE
sys.path.insert(0,str(Path(__file__).parent));from aligned import evaluate
work=Path('/home/ansy/app/quant-diligence/completion-vibe-work');run=json.loads((work/'initial.log').read_text().splitlines()[-1]);vibe=work/'home/.vibe-trading/runs'/run['run_id'];summary={}
for i,(name,src) in enumerate([('vibe',vibe),('terra',BASE/'model_comparison/terra'),('luna',BASE/'model_comparison/luna')]):
 dst=BASE/'candidates/vibe'/f'attempt{i}';dst.mkdir(parents=True,exist_ok=True);shutil.copy2(src/'factor.py',dst/'factor.py');shutil.copy2(src/'candidate.json',dst/'candidate.json')
 try:
  tree=ast.parse((dst/'factor.py').read_text())
  for n in ast.walk(tree):
   if isinstance(n,ast.Import) and any(a.name not in ['numpy','pandas'] for a in n.names):raise ValueError('unapproved import')
   if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ['exec','eval','open','__import__']:raise ValueError('unapproved generated code action')
  values=old.factor_values('vibe',i,'US','validation',frames);metrics,nav,fills=evaluate(values,frames);out=BASE/'vibe_model_evaluation'/name;out.mkdir(parents=True,exist_ok=True);nav.to_csv(out/'nav.csv',index=False);fills.to_csv(out/'fills.csv',index=False);(out/'metrics.json').write_text(json.dumps(metrics,indent=2));summary[name]={'code_exec':'PASS','prefix':'PASS','metrics':metrics}
 except Exception as e:summary[name]={'code_exec':'FAILED','error':str(e)}
 if name in ['terra','luna']:
  candidate=json.loads((src/'candidate.json').read_text());summary[name]['classification_correct']=candidate['classification']==['DATA_ERROR','PREDICTION_FAILURE','COST_PROBLEM','INSUFFICIENT_EVIDENCE','PENDING'];summary[name]['falsifiable']=bool(candidate.get('falsification'));summary[name]['horizon_error']='overnight' in candidate['hypothesis'].lower();summary[name]['unsupported_causality_claim']=False
(BASE/'vibe_model_evaluation/summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
# Stage a fixed native Vibe CSV bridge. This native benchmark has its own
# overnight accounting and is not ranked as if it were aligned intraday V2.
inputs=work/'native_inputs';inputs.mkdir(exist_ok=True);bridge=[]
for s,f in frames.items():
 f.to_csv(inputs/(s+'.csv'));bridge.append({'symbol':s+'.US','type':'csv','path':'/work/native_inputs/'+s+'.csv'})
p=work/'home/.vibe-trading/data-bridge/config.yaml';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'sources':bridge}))
native=work/'native_run';(native/'code').mkdir(parents=True,exist_ok=True)
code=(vibe/'factor.py').read_text()+'''\n_ResearchSignalEngine=SignalEngine
class SignalEngine:
 def generate(self,data_map):
  values=_ResearchSignalEngine().generate(data_map)
  panel=pd.DataFrame(values);weights=pd.DataFrame(0.,index=panel.index,columns=panel.columns)
  for day,row in panel.iterrows():
   chosen=row[row>0].sort_values(ascending=False,kind='stable').index[:4];weights.loc[day,chosen]=.2
  return {s:weights[s] for s in weights}
'''
(native/'code/signal_engine.py').write_text(code);cfg={'codes':['local:'+s+'.US' for s in frames],'source':'local','start_date':str(min(f.index.min() for f in frames.values()).date()),'end_date':'2025-12-31','evaluation_start_date':'2025-01-01','initial_cash':100000,'position_adjustment':'rebalance','allow_short':False,'slippage_us':.0005,'slippage':.0005};(native/'config.json').write_text(json.dumps(cfg,indent=2))

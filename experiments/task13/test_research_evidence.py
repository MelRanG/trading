"""Acceptance checks on actual new native artifacts, not mock alpha success."""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13'
def read(p):return json.loads((B/p).read_text())
def test_sealed_new_native_sources_and_boundary():
 seal=read('candidate_seal.json');assert len(seal['candidates'])==5
 for c in seal['candidates']:
  p=Path(c['source']);p=p if p.is_absolute() else R/p
  assert hashlib.sha256(p.read_bytes()).hexdigest()==c['code_hash']
 f=pd.read_csv(B/'generation_input/panel.csv',parse_dates=['datetime']);assert f.datetime.max()<=pd.Timestamp('2024-12-31');assert not any('label' in c for c in f)
 assert not Path('/tmp/quant-task13.sock').exists()
def test_real_target_endpoints_use_market_sessions():
 for m in ['US','KR']:
  f=pd.read_csv(B/'nominal_inputs'/m/'panel.csv',parse_dates=['datetime']).set_index(['datetime','instrument']);opens=f.open.unstack('instrument');ds=opens.index
  for c in ['V_ROC20','V_LOWVAR20','Q0','Q1']:
   p=pd.read_csv(B/'diagnostics'/(c+'_'+m+'_paired.csv'),parse_dates=['datetime']).set_index(['datetime','instrument']);g=p.dropna()
   for (d,s),row in g.iloc[::max(1,len(g)//20)].iterrows():
    i=ds.get_loc(d);assert row.target==__import__('pytest').approx(opens.iloc[i+21][s]/opens.iloc[i+1][s]-1)
   assert p.loc[p.index.get_level_values(0)>ds[-22],'target'].isna().all()
def test_actual_fit_purge_checkpoint_and_parity():
 for m in ['US','KR']:
  d=read('models/'+m+'/metrics.json');t=d['training'];assert pd.Timestamp(t['max_fit_target'])<pd.Timestamp('2024-07-01');assert pd.Timestamp(t['min_validation_signal'])>=pd.Timestamp('2025-02-01');assert t['parameter_count']==6 and t['fit_dates']>=500
  assert hashlib.sha256((B/'models'/m/'model.pth').read_bytes()).hexdigest()==t['checkpoint_hash']
  p=pd.read_csv(B/'models'/m/'RD_SMALL_paired.csv');assert np.mean((p.prediction-p.target)**2)==__import__('pytest').approx(d['RD_SMALL']['mse'])
  assert all(d['causality'].values())
def test_failures_and_proposals_not_removed_or_promoted():
 proposals=[json.loads(p.read_text()) for p in (B/'native/quanta').glob('Q*/all_proposed_tasks.json')];assert sum(len(x['tasks']) for x in proposals)==6
 assert (B/'native/quanta/failure_initial_multi_task.json').exists();assert not (B/'native/quanta/Q2/factor.py').exists();assert read('research_stopped.json')['LLM_relay_stopped']
 for engine in ['quanta','rd']:
  reservations=[json.loads(p.read_text()) for p in (B/'model_calls'/engine).glob('*.reserved.json')];limit=read('contract.json')['budgets'][engine];assert len(reservations)<=limit['calls'];assert sum(x.get('measured_tokens',0) for x in reservations)<=limit['tokens'];assert all(x['model']=='gpt-6.1-terra' for x in reservations)
def test_actual_formula_and_future_perturbation_evidence():
 d=read('diagnostics/initial_diagnostics.json');assert all(x['max_absolute_error']<1e-10 and x['complete_cross_section_dates']>50 for x in d['native_formula_parity'])
 for cid in ['V_ROC20','V_LOWVAR20','Q0','Q1']:
  for m in ['US','KR']:
   a=read('calculations/'+cid+'/nominal_'+m+'/calculation.json');assert a['prefix_match'] and a['future_perturbation_match']
 assert d['no_economic_backtest'] and d['no_formal_hypothesis_test']

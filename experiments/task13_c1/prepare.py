"""Phase A/B: audit and freeze features, no H5 numerical outcome access."""
from pathlib import Path
import json, sys, numpy as np, pandas as pd
from common import R, B, S, sha, write, now, read_before, bool_col, loaded, numeric_geometry
from factor import features, forward_valid


def blocks(positions):
    last = -100; count = 0
    for pos in positions:
        if pos >= last + 5:
            count += 1; last = pos
    return count


def main():
    if (B / 'seal.json').exists():
        raise RuntimeError('Already frozen; do not regenerate')
    # Predeclared without viewing C1 returns or changing inherited eligibility.
    contract = {
        'id': 'TASK13_C1_IDIOSYNCRATIC_REVERSAL', 'at': now(),
        'mechanism': 'Temporary issuer-specific selling pressure may partially reverse; permanent bad news may not.',
        'direction': 1, 'H': 5, 'formula': '-sum(t-4..t, logreturn_i-beta*logreturn_market)/(sqrt(5)*sigma)',
        'beta': 'OLS slope with intercept on paired logreturns t-125..t-6 inclusive120 slots, >=110 valid pairs; covariance/variance; positive market variance.',
        'sigma': 'Sample SD(ddof=1) of demeaned OLS daily residuals on same paired estimation rows; >0. No fitted intercept subtracted from the five-day shock, per requested formula.',
        'masks': 'Frozen R0 native eligibility intersect basic quality, no B3 overlay. Both return endpoints valid; no missing-session bridging. Existing63 continuous-session feature warmup; shock requires5 valid paired returns. H5 requires all6 forward sessions valid.',
        'US_universe': 'All176 admitted R0 US CORE survivors; no additions or restoration of rejected identities.',
        'KR': 'CORE only; block unless time-specific KOSPI/KOSDAQ membership proven. Current board not projected backward.',
        'fit': '2017..2022 feature feasibility only; no outcome fitting or metric-based choice',
        'diagnostic': '2023-04-03..2024-12-31; exit date<=2024-12-31; exposed historical research',
        'label': 'close t signal; open(t+1) entry; open(t+6) exit; simple adjusted return; same Task12/R0 timing; no claimed executable price.',
        'baselines': {'REV5': '-(close/close.shift(5)-1)', 'MOM20': 'close/close.shift(20)-1', 'LOWVOL20': '-std20(simple daily returns, ddof=1)'},
        'primary': 'US average daily cross-sectional partial RankIC: average-tie rank candidate and target separately; each OLS-residualized on intercept+rankREV5+rankMOM20+rankLOWVOL20; Pearson correlation of residuals.',
        'beta_control': 'Report beta RankIC/overlap; adding ranked beta is secondary diagnostic only, cannot rescue primary.',
        'minimum': {'names_daily': 50, 'signal_dates': 100, 'nonoverlap_H5_intervals': 25},
        'increment_gate': 'REV5-only partial mean>0 and CI lower>0, all baseline abs mean rank overlap<.95; no control weights optimized.',
        'bootstrap': {'function': 'experiments/task14/stats_eval.py:block_mean', 'samples': 5000, 'seed': 130301, 'block': 5, 'NaN_calendar_slots': 'preserve', 'CI': 'percentile95', 'p': 'centered-null positive one-sided +1 correction'},
        'family': {'method': 'Holm39 at0.05', 'slots': {'Task14_reserved':18, 'R1_four_candidates_two_markets':8, 'R1_2_one_two_markets':2, 'R2_four_arms_two_markets':8, 'B2':1, 'B3':1, 'C1_US_primary':1}, 'p_source': 'Task14 ten observed primary p; all other reserved older slots conservatively1; C1 US primary p. Local family C1 alone also shown. Earlier Task6..10 and unlogged historical selection not exhausted: no campaign-wide/independent confirmation claimed.'},
        'stability': '2023/2024; leave each issuer out and drop top1/top3 spread-contribution names; drop5 largest absolute partialIC dates; diagnostics only, no candidate selection. Concentration gate: all LOO means>0 and dropping top3 names/top5days leaves positive primary. Same eligible >=50 names rule on each recomputation.',
        'spread': 'Equal-date top/bottom quintile mean rawH5 difference; floor(n/5), stable symbol tie-break. Contributions sum exactly. Gross diagnostic only, no trading/account return.',
        'duplicate': 'Compare actual previous Q0/Q3 overnight-intraday20, Q1conditional recovery10 and momentum, R1.2downside share20, R2liquidity range interaction. None has this120-lagged market-residual5/sigma formula. Record daily rank overlap with baselines; abs mean corr>=.95 flags near duplicate, cannot be claimed novel without conditional info.',
        'decision': 'RESEARCH_CANDIDATE only if positive primary, CI lower>0, Holm39 p<.05, positive robust increment vsREV5, concentration and data gates; else no direction/horizon/universe change. Negative/nonpositive primary=>NO_INCREMENTAL_EVIDENCE; positive weak=>INSUFFICIENT_EVIDENCE.',
        'numeric_geometry': 'Only machine rounding tolerance8*eps*row_price; exact underlying quote geometry and adjustment scaling verified. No price or mask modification.',
        'limits': {'external_HTTP':0, 'research_LLM':0, 'training':0, 'economic_hypotheses':1, 'evaluations':1, 'CPU_target_hours':4},
        'protection': 'Factory/Paper/Forward/Shadow/Champion/Live/Team2 read-only; no registration, orders, promotion, Task15 or follow-on research.'}
    write('contract.json', contract)
    refs = [Path('AGENTS.md'), Path('runtime/task13_r0/native_manifest/assets.json'), Path('runtime/task13_r0/native_input_contract.json'), Path('runtime/task14/validation.json'), Path('experiments/task14/stats_eval.py'), Path('experiments/task12/evaluation.py'), Path('experiments/task13_r0/loader.py')]
    names = ['11_research_architecture_audit','12_alpha_data_readiness','13_native_alpha_research','14_alpha_signal_validation','13_R0_research_data_expansion','13_R1_quanta_native_research','13_R1_1_quanta_quality_review','13_R1_2_quanta_generation_recovery','13_R2_rd_agent_differential_research','13_B0_new_information_feasibility','13_B1_information_research_bridge','13_B2_guidance_alpha_pilot','13_B2_1_guidance_extraction_audit','13_B3_alpha_research_prioritization','13_B3_technical_completion','06_research_completion_report','07_market_company_research_report','10_adaptive_quant_walk_forward']
    refs += [Path('docs/development')/(x+'.md') for x in names]
    for p in sorted((R/'runtime').glob('task13*/**/*ledger*.json')):
        if 'task13_c1' not in str(p):refs.append(p.relative_to(R))
    for cid in ['Q0','Q1','Q2','Q3']:
        refs.append(Path('runtime/task13_r1/native/quanta')/cid/'all_proposed_tasks.json')
    write('campaign.json', {'id': contract['id'], 'attempt': 1, 'classification':'HISTORICAL_EXPLORATORY_SURVIVOR_RESEARCH','prior_evidence': {str(p):sha(R/p) for p in refs}, 'not_duplicate_reason':contract['duplicate'], 'earlier_findings': ['Q0/Q3 overnight-intraday20 had missing controls/near duplication; no market-beta residual.', 'Q1 original momentum-like/new conditional recovery variants did not establish incremental alpha.', 'Task14 RETURN_TO_TASK13; overlapping labels, weak/duplicated signals; no independent holdout.', 'B2 insufficient independent directional events; no new event/price fetch.', 'B3 repair valid only in own task; H60 residual increment absent; its overlay not imported.', 'RD full controller unverified; component factor/model loop exists but no consistent simple-model increment.', 'Task6/7 execution/horizon/cost problems not repaired by gross spread; Task10 isolated feedback improvement is not forward alpha.']})
    assets=json.loads((S/'native_manifest/assets.json').read_text());us=[a for a in assets if a['market']=='US' and a['cohort']=='CORE'];assert len(us)==176
    indexdir=S/'accepted/US/^GSPC';iq=json.loads((indexdir/'quality.json').read_text())
    inputs={}
    def bind(p,expected=None):
        h=sha(p)
        if expected is not None and h!=expected:raise ValueError('SOURCE_HASH_MISMATCH: '+str(p))
        inputs[str(p.relative_to(R))]=h
    bind(S/'US_regimes.csv')
    for name in ['quality.json','quote.csv','quality_mask.csv']:
        bind(indexdir/name,iq['output_hashes'].get(name))
    market=read_before(indexdir/'quote.csv');days=market.index;mg=bool_col(read_before(indexdir/'quality_mask.csv').reindex(days))
    assert (days.dayofweek<5).all() and days.min()==pd.Timestamp('2017-01-03')
    allfeatures=[];details=[];rounding=[];fitcounts=pd.Series(0,index=days,dtype=int);devcounts=fitcounts.copy()
    exits=pd.Series(days,index=days).shift(-6)
    for a in us:
        path=R/a['adjusted_path'];q=json.loads((path.parent/'quality.json').read_text())
        bind(path,a['adjusted_hash']);bind(R/a['eligibility_path'],a['eligibility_hash']);bind(path.parent/'quality_mask.csv',q['output_hashes']['quality_mask.csv']);bind(path.parent/'quality.json');bind(path.parent/'quote.csv',q['output_hashes']['quote.csv'])
        frame,g=loaded(a,days)
        finite=np.isfinite(frame).all(axis=1)&(frame>0).all(axis=1)
        geometry=numeric_geometry(frame)
        strict=(frame.high>=frame[['open','close','low']].max(axis=1))&(frame.low<=frame[['open','close','high']].min(axis=1))
        quote=read_before(path.parent/'quote.csv').reindex(days)
        assert not (g&~numeric_geometry(quote)).any(),a['symbol']
        factor=frame.close/quote.close
        assert np.allclose(frame.loc[g,['open','high','low']],quote.loc[g,['open','high','low']].mul(factor[g],axis=0),rtol=1e-12,atol=0),a['symbol']
        for d in frame[g&~strict].index:
            rounding.append({'symbol':a['symbol'],'date':d.date().isoformat(),'high_minus_close':float(frame.loc[d,'high']-frame.loc[d,'close']),'close_minus_low':float(frame.loc[d,'close']-frame.loc[d,'low'])})
        assert not (g&~(finite&geometry)).any(),a['symbol']
        f=features(frame.close,g,market.close,mg)
        fg=np.isfinite(f[['signal','REV5','MOM20','LOWVOL20','beta','sigma']]).all(axis=1)
        # Availability gate only, no H5 numerical label or future-return aggregate.
        pathok=forward_valid(g)&forward_valid(mg)
        fit=fg&pathok&(days<='2022-12-31')&exits.le('2022-12-31')
        dev=fg&pathok&(days>='2023-04-03')&exits.le('2024-12-31')
        fitcounts+=fit.astype(int);devcounts+=dev.astype(int)
        f=f.loc[(days>='2023-04-03') & (days<='2024-12-31')].copy();f['label_path_eligible']=pathok.reindex(f.index);f['symbol']=a['symbol'];f['date']=f.index.strftime('%Y-%m-%d');allfeatures.append(f.reset_index(drop=True))
        details.append({'symbol':a['symbol'],'first_native_valid':str(g[g].index.min().date()) if g.any() else None,'last_native_valid':str(g[g].index.max().date()) if g.any() else None,'fit_feature_and_mature_path_rows':int(fit.sum()),'development_feature_and_mature_path_rows':int(dev.sum()),'price_quality':'PARTIAL_SURVIVOR_RESEARCH','identity_policy':'R0 conservative listing/transfer lower bound unchanged; unadmitted names not restored'})
    valid=devcounts>=50;positions=np.flatnonzero(valid);nb=blocks(positions)
    fitgood=fitcounts>=50
    gate={'at':now(),'numerical_H5_outcomes_read':False,'US':{'universe':len(us),'valid_signal_dates':int(valid.sum()),'nonoverlap_H5_intervals':nb,'min_names':int(devcounts[valid].min()) if valid.any() else 0,'median_names':float(devcounts[valid].median()) if valid.any() else 0,'max_names':int(devcounts.max()),'first':str(days[valid].min().date()) if valid.any() else None,'last':str(days[valid].max().date()) if valid.any() else None,'valid_symbol_dates':int(devcounts[valid].sum()),'fit_dates_ge50':int(fitgood.sum()),'fit_nonoverlap_intervals':blocks(np.flatnonzero(fitgood))},'KR':{'status':'BLOCKED_HISTORICAL_BOARD_MAPPING_UNVERIFIED','reason':'R0 assets contain current board/selection only and identity_history=UNVERIFIED_HISTORICAL_CHANGE_TAPE. No time-specific KOSPI/KOSDAQ membership proof. No current board retroprojection; no KR outcomes calculated.'},'data_level':'PARTIAL_SURVIVOR_RESEARCH_NOT_GENERALIZED_PIT','known_limits':['Current survivors; no full historical listing/delist/merger tape','Provider adjusted OHLC and corporate actions not independently certified; known jumps/splits/zero volume excluded by immutable masks','Provider-index observed sessions, not independently certified full exchange calendar','Current native listing/transfer boundaries may conservatively omit historical observations; no B3 repair generalized','All historical study periods previously exposed; no independent holdout'], 'pass':bool(valid.sum()>=100 and nb>=25)}
    write('numeric_rounding_audit.json',rounding);write('phase_a_gate.json',gate);write('asset_audit.json',details);write('input_hashes.json',inputs)
    pd.DataFrame({'fit_names':fitcounts,'diagnostic_names':devcounts}).to_csv(B/'coverage.csv',index_label='date')
    if not gate['pass']:
        write('completion.json',{'status':'DATA_INSUFFICIENT','gate':gate});return
    pd.concat(allfeatures,ignore_index=True).to_csv(B/'features.csv.gz',index=False,float_format='%.17g',compression={'method':'gzip','mtime':0})
    paths=[Path(__file__),R/'experiments/task13_c1/factor.py',R/'experiments/task13_c1/common.py',R/'experiments/task13_c1/evaluate.py',R/'experiments/task13_c1/test_c1.py',R/'experiments/task14/stats_eval.py']
    code={str(p.relative_to(R)):sha(p) for p in paths}
    bound=['contract.json','campaign.json','phase_a_gate.json','asset_audit.json','input_hashes.json','coverage.csv','features.csv.gz','preflight_tests.json','numeric_rounding_audit.json','pre_evaluation_fixes.json']
    write('seal.json',{'at':now(),'status':'FEATURES_FROZEN_BEFORE_H5_OUTCOMES','code_hashes':code,'artifacts':{x:sha(B/x) for x in bound},'candidate_fingerprint':sha(R/'experiments/task13_c1/factor.py'),'input_set_hash':sha(B/'input_hashes.json'),'no_target_columns':True,'one_evaluation_only':True})
    write('attempt_ledger.json',{'id':contract['id'],'attempts':[{'attempt':1,'status':'SEALED_READY','phase_a':True,'new_economic_hypotheses':1,'outcome_queries':0,'research_LLM_calls':0,'research_tokens':0,'HTTP':0}]})
    print(json.dumps(gate,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

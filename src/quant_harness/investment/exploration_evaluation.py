"""Independent exposure/cost attribution. No portfolio or order mutations.

Cash-heavy probes must not be called stock-selection failures merely because
an unmatched fully invested index outperforms. Preserve both comparisons.
"""
from .research import digest
from .discovery import instant


def matched_metrics(initial_capital,entry_exposure,nav,recorded_cost,benchmark_entry,benchmark_mark):
    if initial_capital<=0 or not 0<=entry_exposure<=1 or min(benchmark_entry,benchmark_mark)<=0 or recorded_cost<0:raise ValueError('invalid evaluation basis')
    net=nav/initial_capital-1;gross=(nav+recorded_cost)/initial_capital-1;benchmark=benchmark_mark/benchmark_entry-1;matched=entry_exposure*benchmark
    return {'version':'EXPLORATION_PRICE_EVAL_V1','observed_entry_exposure':entry_exposure,'portfolio_net_price_return':net,'portfolio_gross_before_recorded_cost':gross,'benchmark_full_price_return':benchmark,'benchmark_capital_matched_gross_return':matched,'gross_selection_difference':gross-matched,'recorded_cost_drag':recorded_cost/initial_capital,'net_difference_vs_gross_control':net-matched,'cash_interest':0,'fx_combination':False,'net_benchmark_comparability':'NOT_ESTABLISHED_NO_VERIFIED_ETF_EXECUTION_COST','investment_alpha_proven':False}


def observe(root):
    import json,psycopg
    from pathlib import Path
    from .exploration import research_store,account_store
    root=Path(root);store,cfg=research_store(root);out=[]
    with psycopg.connect(store.url) as conn:plans=conn.execute("SELECT r.record_id,r.payload FROM investment_record r LEFT JOIN investment_run s ON s.run_id=r.record_id WHERE r.kind='exploration_plan' AND COALESCE(s.status,'ACTIVE')<>'SUPERSEDED_UNFILLED'").fetchall()
    for plan_id,plan in plans:
        with psycopg.connect(store.url) as conn:
            entered=conn.execute('SELECT payload FROM investment_record WHERE record_id=%s',(plan_id+':entry',)).fetchone();marks=[r[0] for r in conn.execute("SELECT payload FROM investment_record WHERE kind='exploration_mark' AND payload->>'plan_id'=%s ORDER BY created_at",(plan_id,)).fetchall()]
        if not entered or not marks:
            result={'plan_id':plan_id,'status':'PENDING','reason':'NO_ACTUAL_ENTRY_OR_COMPLETED_SESSION_MARK','target_exposure':sum(plan['weights'].values())};store.put('exploration_evaluation',result);out.append(result);continue
        account=account_store(cfg,plan['market']);entry=entered[0]
        with psycopg.connect(account.url) as conn:
            nav=conn.execute('SELECT positions_value FROM stock_nav WHERE decision_id=%s',(plan['paper_decision_id'],)).fetchone();fills=conn.execute('SELECT symbol,side,quantity,price,fee,event_hash FROM stock_fill').fetchall()
        costs=0;latest=marks[-1]
        for symbol,side,qty,price,fee,event_hash in fills:
            event=next(e for e in account.get(event_hash)['events'] if e['symbol']==symbol)
            if instant(event['event_at'])>instant(latest['available_at']):continue
            slippage=(float(price)-event['price'])*float(qty)*(1 if side=='BUY' else -1);costs+=float(fee)+slippage
        latest=marks[-1];metrics=matched_metrics(entry['initial_capital'],float(nav[0])/entry['initial_capital'],latest['nav'],costs,entry['benchmark_entry']['price'],latest['benchmark_price']);result={'plan_id':plan_id,'session':latest['session'],'completed_sessions':latest['completed_sessions'],'status':'OBSERVED_PRICE_ATTRIBUTION' if latest.get('corporate_actions_verified') else 'PROVISIONAL_PENDING_CORPORATE_ACTIONS','metrics':metrics,'source_mark_hash':digest(latest)};store.put('exploration_evaluation',result);out.append(result)
    folder=root/'runtime/task8b/forward';folder.mkdir(parents=True,exist_ok=True);(folder/'evaluations.json').write_text(json.dumps(out,indent=2));return out

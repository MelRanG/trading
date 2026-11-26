from shared import *
rows=[];transitions=[]
for m in ['US','KR']:
 fs=frames(m);mapping=json.loads((R/'runtime/task6/split_manifest.json').read_text())['markets'][m]['aliases'];case=json.loads((B/'accounts'/m/'summary.json').read_text())['research_event'];cap=C['strategy']['capital'][m]
 for arm in ['STATIC','ADAPTIVE','MOM63']:
  folder=B/'accounts'/m;n=pd.read_csv(folder/(arm+'_nav.csv'),parse_dates=['date']).set_index('date');fills=pd.read_csv(folder/(arm+'_fills.csv'),parse_dates=['date']);held={};pnl={};cost={};maxw={};hh=[]
  for day,r in n.iterrows():
   after=json.loads(r.holdings_json);prior_index=next(iter(fs.values())).index;previous=prior_index[prior_index.get_loc(day)-1];ws=[]
   for s in set(after)|set(held):
    old=held.get(s,0);new=after.get(s,0)
    if old:pnl[s]=pnl.get(s,0)+old*(fs[s].open.loc[day]-fs[s].close.loc[previous])
    if new:pnl[s]=pnl.get(s,0)+new*(fs[s].close.loc[day]-fs[s].open.loc[day]);w=float(new*fs[s].close.loc[day]/r.nav_krw);maxw[s]=max(maxw.get(s,0),w);ws.append(w)
   if ws:hh.append(sum((w/sum(ws))**2 for w in ws))
   held=after
  for f in fills.itertuples():cost[f.ticker]=cost.get(f.ticker,0)+f.fee_krw+f.half_spread_cost_krw+f.impact_cost_krw
  error=abs(sum(pnl.values())-sum(cost.values())-(n.nav_krw.iloc[-1]-cap));assert error<1e-5,error
  rows.append({'market':m,'arm':arm,'ledger_attribution_error':error,'mean_invested_sleeve_HHI':float(np.mean(hh)) if hh else None,'max_observed_single_name_weight':max(maxw.values(),default=0),'sector_mapping':'UNVERIFIED_PIT_SECTORS_NOT_FABRICATED','positions':[{'alias':s,'symbol':mapping[s],'gross_pnl_currency':float(v),'cost_currency':float(cost.get(s,0)),'net_contribution_initial_capital':float((v-cost.get(s,0))/cap),'max_weight':maxw.get(s,0)} for s,v in sorted(pnl.items(),key=lambda z:-z[1])]})
  if case and case['local_status']=='REPLAY_ADOPTED':
   day=case['effective_session'];decision=next(x for x in json.loads((folder/(arm+'_decisions.json')).read_text()) if x['effective_date']==day);d=fills[fills.date==day];transitions.append({'market':m,'arm':arm,'date':day,'observation_date':decision['observation_date'],'target_symbols':{mapping[s]:v for s,v in decision['targets'].items()},'fills':[{k:(v.date().isoformat() if isinstance(v,pd.Timestamp) else v) for k,v in r.items()} for r in d.to_dict('records')],'strategy_version_is_not_order_authority':True})
freeze(B/'evaluation/position_attribution.json',rows);freeze(B/'evaluation/transition.json',transitions);print('LEDGERATTRIBUTION_PASS')

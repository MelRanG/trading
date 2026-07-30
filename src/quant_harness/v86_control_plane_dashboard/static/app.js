const won = new Intl.NumberFormat('ko-KR',{style:'currency',currency:'KRW',maximumFractionDigits:0});
const num = new Intl.NumberFormat('ko-KR',{maximumFractionDigits:2});
const esc = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
const pct = value => value == null ? '-' : `${num.format(Number(value))}%`;
const money = value => value == null ? '-' : won.format(Number(value));
const cls = value => Number(value)>0?'positive':Number(value)<0?'negative':'';
function table(headers,rows){return `<table><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')||`<tr><td colspan="${headers.length}" class="empty">데이터가 없습니다.</td></tr>`}</tbody></table>`}
let currentData=null;
function roleBadge(role){return `<span class="role-badge ${esc(role)}">${esc(role)}</span>`}
function renderStrategies(data){
  const selected=data.selected_strategy_id;
  const select=document.querySelector('#strategy-select');
  select.innerHTML=data.strategies.map(s=>`<option value="${esc(s.strategy_id)}" ${s.strategy_id===selected?'selected':''}>[${esc(s.role)}] ${esc(s.label)}</option>`).join('');
  document.querySelector('#strategy-cards').innerHTML=data.strategies.map(s=>{
    const a=s.account_summary||{};
    const source=s.created_by==='FeedbackAgent'?'Feedback 후보':s.account_available?'독립 Paper 계좌':'연구 전략';
    return `<article class="strategy-card ${s.strategy_id===selected?'selected':''}" data-id="${esc(s.strategy_id)}">
      <div class="card-head">${roleBadge(s.role)}<span class="scope">${esc(source)}</span></div>
      <h3>${esc(s.label)}</h3><p>${esc(s.status)}${s.parent_strategy_id?` · 부모 ${esc(s.parent_strategy_id)}`:''}</p>
      <div class="card-numbers"><div class="card-number"><small>누적수익률</small><strong class="${cls(a.return_pct)}">${pct(a.return_pct)}</strong></div><div class="card-number"><small>최대낙폭</small><strong>${pct(a.max_drawdown_pct)}</strong></div></div>
    </article>`;
  }).join('');
  document.querySelectorAll('.strategy-card').forEach(card=>card.onclick=()=>load(card.dataset.id));
}
function renderSelected(data){
  const d=data.selected||{}, s=d.strategy||{}, a=d.account;
  document.querySelector('#selected-title').textContent=s.label||'전략 상세';
  const badge=document.querySelector('#selected-role'); badge.className=`role-badge ${s.role||'SHADOW'}`; badge.textContent=s.role||'-';
  const metrics=a?[['총자산',money(a.latest_nav_krw),''],['누적수익률',pct(a.return_pct),cls(a.return_pct)],['MDD',pct(a.max_drawdown_pct),''],['현금',money(a.cash_krw),'']]:[['상태','연구·Shadow',''],['부모 전략',s.parent_strategy_id||'-',''],['실행 계좌','미생성',''],['승격','검증 전','']];
  document.querySelector('#selected-metrics').innerHTML=metrics.map(x=>`<div class="mini"><small>${esc(x[0])}</small><strong class="${x[2]}">${esc(x[1])}</strong></div>`).join('');
  const back=s.backtest_metrics||{};
  document.querySelector('#selected-meta').innerHTML=[
    ['전략 ID',s.strategy_id],['상태',s.status],['생성 주체',s.created_by],['부모 전략',s.parent_strategy_id||'독립 부모'],['실행 호환',s.runtime_compatible?'예':'아니오'],['최근 세션',a?.latest_session||'-'],['백테스트 수익률',back.return_pct==null?'-':pct(back.return_pct)]
  ].map(x=>`<div class="meta-row"><span>${esc(x[0])}</span><strong>${esc(x[1])}</strong></div>`).join('');
  const curve=d.equity_curve||[], values=curve.map(x=>Number(x.nav_krw));
  if(!values.length){document.querySelector('#equity-chart').innerHTML='<div class="empty">Paper 계좌가 생성되면 NAV가 표시됩니다.</div>';}else{
    const lo=Math.min(...values), hi=Math.max(...values), range=Math.max(1,hi-lo);
    const sampled=curve.filter((_,i)=>i%Math.max(1,Math.floor(curve.length/180))===0 || i===curve.length-1);
    document.querySelector('#equity-chart').innerHTML=sampled.map(x=>`<div class="bar" title="${esc(x.session)} · ${money(x.nav_krw)}" style="height:${Math.max(3,(Number(x.nav_krw)-lo)/range*100)}%"></div>`).join('');
  }
  document.querySelector('#holdings').innerHTML=table(['종목','수량','종가','평가액'],(d.holdings||[]).map(h=>`<tr><td><strong>${esc(h.ticker)}</strong></td><td>${num.format(h.quantity)}</td><td>${money(h.close_krw)}</td><td>${money(h.market_value_krw)}</td></tr>`));
  document.querySelector('#fills').innerHTML=table(['세션','종목','방향','수량','체결가','비용','Impact'],(d.fills||[]).slice(0,30).map(f=>`<tr><td>${esc(f.session)}</td><td><strong>${esc(f.ticker)}</strong></td><td class="${f.side==='BUY'?'positive':'negative'}">${esc(f.side)}</td><td>${num.format(f.quantity)}</td><td>${money(f.execution_price)}</td><td>${money(f.fee)}</td><td>${num.format(f.impact_bps)}bp</td></tr>`));
}
function renderSystem(data){
  const runtime=data.strategies.filter(s=>s.account_available).length, shadows=data.strategies.filter(s=>s.role==='SHADOW').length;
  const readiness=data.readiness||{}, forward=readiness.forward_governance||{};
  document.querySelector('#system-strip').innerHTML=[['운영 계좌',`${runtime}개`],['등록 전략',`${data.strategies.length}개`],['Shadow 후보',`${shadows}개`],['Forward 단계',forward.next_stage||'READ_ONLY']].map(x=>`<div class="system-item"><small>${x[0]}</small><strong>${x[1]}</strong></div>`).join('');
  const op=data.operations||{}; document.querySelector('#operation-status').textContent=op.status||'NOT RUN';
  const stageNames=['DATA_SYNC','DATA_VALIDATE','UNIVERSE_RESOLVE','PLAN','RISK_GATE','EXECUTE','RECONCILE','FEEDBACK','BACKUP'];
  document.querySelector('#stages').innerHTML=stageNames.map(name=>`<div class="stage"><strong>${name}</strong><span>${op.stages?.[name]?'DONE':'WAIT'}</span></div>`).join('');
  const h=data.data_health||{};
  document.querySelector('#data-health').innerHTML=[['상태',h.available?'AVAILABLE':'MISSING'],['기간',h.start?`${h.start} ~ ${h.end}`:'-'],['행 수',h.rows??'-'],['티커',h.ticker_count??'-'],['중복',h.duplicates??'-'],['가격 스케일',(h.price_scales||[]).join(', ')||'-']].map(x=>`<div class="health"><small>${esc(x[0])}</small><strong>${esc(x[1])}</strong></div>`).join('');
  const g=data.governance||{};
  document.querySelector('#governance').innerHTML=[
    ['후보 생성','FeedbackAgent는 새 전략을 Registry의 Shadow 후보로 추가할 수 있습니다.'],['원본 보호','챔피언·챌린저를 제자리에서 덮어쓰지 않습니다.'],['계좌 격리','Paper로 승격된 전략마다 별도 계좌와 원장을 가집니다.'],['최종 귀결','선정된 챔피언이 기본 화면이 되며 과거 후보는 비교·감사용으로 보존됩니다.'],['실전 승격',g.automatic_live_promotion?'자동':'자동 승격 금지']
  ].map(x=>`<div class="policy"><strong>${esc(x[0])}</strong><p>${esc(x[1])}</p></div>`).join('');
  document.querySelector('#alerts').innerHTML=(data.alerts||[]).length?(data.alerts||[]).map(a=>`<div class="alert ${esc(a.severity)}"><strong>${esc(a.code)}</strong><p>${esc(a.message)}</p><small>${esc(a.at||'')}</small></div>`).join(''):'<div class="empty">최근 경보가 없습니다.</div>';
}
function render(data){currentData=data;renderSystem(data);renderStrategies(data);renderSelected(data)}
async function load(strategyId=null){
  const q=strategyId?`?strategy_id=${encodeURIComponent(strategyId)}`:'';
  const r=await fetch(`/api/control-plane${q}`,{cache:'no-store'}); if(!r.ok) throw new Error(await r.text()); render(await r.json());
}
document.querySelector('#strategy-select').onchange=e=>load(e.target.value).catch(err=>alert(err.message));
document.querySelector('#refresh').onclick=()=>load(currentData?.selected_strategy_id).catch(err=>alert(err.message));
load().catch(err=>{document.querySelector('#strategy-cards').textContent=`로드 실패: ${err.message}`});
setInterval(()=>load(currentData?.selected_strategy_id).catch(()=>{}),30000);

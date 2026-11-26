from common import *
import pandas as pd

def load(p):return json.loads((B/p).read_text())
def tab(h,rs):return '| '+' | '.join(h)+' |\n| '+' | '.join(['---']*len(h))+' |\n'+'\n'.join('| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in row)+' |' for row in rs)+'\n'
def pct(v):return '미산출' if v is None else f'{100*v:+.2f}%'
def pp(v):return f'{100*v:+.2f}pp'
s=load('evaluation/summary.json');months=load('evaluation/monthly_NAV.json');h=load('evaluation/horizons.json');usage=load('usage.json');post=load('evaluation/post_change.json');ab=load('evaluation/ablation.json');similarity=load('evaluation/alpha_similarity.json');versions=load('source_versions.json');quality=load('evaluation/model_quality_v2.json')
cases=[load('experiments/'+p.name+'/event.json') for p in sorted((B/'experiments').iterdir()) if (p/'event.json').exists()]
t='''# Task10 — 적응형 퀀트 Walk-Forward 검증

## 핵심 결론과 완료 판정

**네이티브 연구→주간 Review→공식 Factory 격리 실험→채택/기각→이후 운용을 실제 실행했다. 미국에서는 고정 전략 대비 개선됐지만 시장을 넘지 못했고, 한국은 후보를 기각해 적응형의 증분이 없었다. 일반화된 투자 우위는 미입증이다.**

| 시장 | STATIC | ADAPTIVE | MOM63 | 시장 가격지수 | 적응형-고정 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 미국 USD | -9.04% | +1.62% | +0.50% | S&P500 +1.98% | +10.66pp |
| 한국 KRW | +1.45% | +1.45% | -2.95% | KOSPI -28.92% | 0.00pp |

2026-05-18 실제 시가부터11-13종가까지의 연속 연구용 계좌, 비용 포함·배당 제외다. 미국 초기자본$100,000, 한국1,000만원이다. 기존 Paper/Live 계좌나 새 Forward 실적이 아니다.

| 판정 | 결과 | 실제 근거와 한계 |
| --- | --- | --- |
| Quant Research | PASS — 원본 구성요소 / PARTIAL — 전체 native controller | Quanta 원본 planner·proposal·DSL·EvolutionController mutation·feedback, RD 원본 model hypothesis/experiment/CoSTEER 및 Qlib GRU 학습·재학습. full AlphaAgentLoop/Qlib runner·full fin_quant 자율 선택기는 미사용 |
| Feedback Loop | PASS — 격리된 제한 순환 | 미국7/15·한국7/7 자연 약화 조건에서 실제 연구·공식 예약·평가·결과·후속 관측 요청. 주간 손실을 곧바로 오류로 확정하지 않음 |
| Adaptive Execution | PASS — 연구 계좌만 | 미국7/16부터 신규 버전, 과거 NAV/체결 변경0. 한국 후보 기각 후 기존 버전 유지. 공식 Champion·운영 Paper·Live 승격0 |
| Economic Value | PARTIAL | 미국STATIC대비+10.66pp·MDD개선, 시장대비-0.36pp. 한국증분0. 사후분해에서RD재학습의투자증분은좋지않았음 |
| Generalization | INSUFFICIENT_EVIDENCE | 1회·6개월·현재 생존 표본·재사용 검증·LLM 역사 지식·부분 PIT 자료. 독립 Forward·통계적 초과수익 입증 없음 |

**운영 연결의 별도 차단점:** 현재 코드가 사용하는 `runtime/alpha_research_factory/task4/` 원장 경로가 없다. Task4/5 과거 백업만 확인했다. 이를 오늘의 예산 사용0으로 취급하거나 새 원장을 만들어 초기화하지 않았다. 기존 운영을 복원·승격하지 않았으며, 실제 실행 성공은 아래의 **격리 연구 DB/Factory** 범위다.

## 1. 기존 기능 실사와 이번 연결

Task6~9.4의 실행·실패 기록과 Task7 비용/평가 진단을 재사용했다. 초기 성과를 높이려고 기존 동결 후보나 역사 결과를 고치지 않았다.

| 역할 | 실제 재사용 | 이번 최소 연결 / 미완료 |
| --- | --- | --- |
| QuantaAlpha | `EvolutionController`, planner, `AlphaAgentHypothesisGen`, expression/parser, native feedback | 한 방향 초기경로→후속 mutation 1개. 기존 whole-loop 대신 명시적 공통 평가 bridge, crossover는이번예산범위외 |
| RD-Agent | `QlibModelHypothesisGen/2Experiment`, `ModelMultiProcessEvolvingStrategy`, 원본 `GeneralPTNN.fit/predict` | 새 GRU코드→시장별 학습→시장별1회확장학습. 원본전체fin_quant의자동모델선택완주아님 |
| Review | `process_review`, `score_mature_outcome`, 기존분류체계 | 결과를보지않는과정seal과성숙NAV채점, 연구용지속약화룰. 경제적원인확정은UNDETERMINED, 독립Review LLM은호출하지않음 |
| Factory | 공식 register/reserve/record·예산/중복/해시·Store/Queue | 실제 격리PG 예약→외부native실행→평가→DONE/후속관측. 운영원장복원·운영dispatcher배포미실행 |
| 실행/평가 | 기존 `replay_targets` 및 V77 비용·참여율·정수주·D-1 sizing | 연구targets adapter와버전선택만추가. 새백테스터·실주문·팀2변경없음 |

'''
t+=tab(['엔진','고정 원본'],[[k,v['commit']] for k,v in versions['upstreams'].items()])
t+='''
[실제 source/version](../../runtime/task10/source_versions.json), [초기 계약](../../experiments/task10/contract.json), [재생·연결 코드](../../experiments/task10/replay.py), [원본 연구 worker](../../experiments/task10/native_worker.py), [기존 실행기](../../src/quant_harness/investment/research.py).

## 2. 데이터·PIT·실험 예산

기존 Task6의 **미국38·한국20개 개별주식 고정 다업종 표본**을 그대로 사용했다. SPY/069500은 시장 위험 지표·비교 기준으로만 사용하고 보유하지 않았다. 전종목 DB를 만들지 않았다. 표본 기업은 초기200세션 가격과 과거 상장 메타데이터가 있지만, 이 표본이 과거 전시장과 상폐 기업을 대표한다는 증거는 없다. **현재 생존 표본의 선택 편향이 남는다.**

기존 adjusted 자료를 그대로 명목 체결 가격이라고 부르지 않고, 기존 Toss에서adjusted=false로초기200세션(약2025년7월~2026-05-15)과평가구간을회수했다. Toss120/Yahoo60/Naver20=**200요청**으로사전상한을지켰다. 가격별두공급자0.5%합의·OHLC형식·revision gate를확인했고불일치/결측을보간하지않았다. Yahoo원문2개형식오류도보존했다. 최종대사한source는별도의`TASK10_RECONCILED_RAW_OBSERVED`이며운영canonical을대체하지않았다.

- 같은 원가격 prefix를 부모/후보에 제공했고 source hash와 candidate code/checkpoint hash를 보존했다.
- 연구 LLM 컨테이너에는 익명 학습 prefix만 mount했다. 미래 테이프·운영DB·브로커 인증·호스트Docker socket은 제공하지 않았다.
- 모델 학습은 매 cutoff 이전에 실현된 target만 사용한다. 정상화는 fit만, early-stop도 fit내부에서 하고 외부80세션을분리했다. label종료가검증경계를넘지않도록purge/embargo했다.
- 미래 특징을 이용한 **동결 모델 추론 worker**와 가설/학습 worker를 분리했다. 실제 채택시점의 prefix와 전체테이프의동일시점출력이일치함을추가실행했다.
- source 최초 관측은 현재다. 과거 최초 수집 원본으로 표시하지 않았다. 전체기간의공식거래소휴장원본인증은없으며관측한local가격세션테이프를사용했다.
- 재무·거시의정량PIT필드를이번모델계약에안전하게이식하지못해OHLCV만사용했다. 팀2와새자료인프라를필수화하지않았다.

'''
t+=tab(['예산/비용','실측'],[['사전 모델 상한','Quanta12/650k, RD4/180k, Review2/100k tokens'],['실제 모델',f"Terra {usage['calls']}회, 성공{usage['successful']}, 실패{usage['failed']}"],['토큰',f"총{usage['total_tokens']:,}=입력{usage['input_tokens']:,}+출력{usage['output_tokens']:,}; cache입력{usage['cached_input_tokens']:,}(입력에포함)"],['scope',f"Quanta{usage['scopes']['quanta']['calls']}회/{usage['scopes']['quanta']['tokens']:,}, RD{usage['scopes']['rd']['calls']}회/{usage['scopes']['rd']['tokens']:,}, Review LLM0"],['모델 실측 경과',f"relay기록합계{usage['model_elapsed_seconds']:.1f}초; 전체개발시간이나CPU사용시간과다름"],['훈련','성공4job×5epochs, 초기KR실패1job별도. CPU2·4GB제한, GRU16·20세션입력·seed42'],['금액','기존Codex구독·별도유료API/데이터구매없음. 증분USD단가불명. native gpt4oalias 비용표시는 실제Terra청구액아님']])
t+='''
[사용량](../../runtime/task10/usage.json), [소스 대사 계약](../../runtime/task10/price_resolution_contract.json), [원문·형식 오류·합의 자료](../../runtime/task10/data/), [채택시점 causal실행](../../runtime/task10/causality_adoption_probes.json).

## 3. 초기 native 알파·모델·운용 규칙

Quanta의 초기 식은 `RANK(FILTER(TS_SUM(return*volume,20)/TS_MEAN(volume,63), mean_volume63>0))`다. 원본 DSL이 실행 코드를 만들었다. 후속 mutation은 당일 overnight gap을 과거20일 gap분포로 표준화한 **음의 gap 이상치 순위**다. 단순 MOM63을 엔진알파로 이름만바꾸지않았다. 기존알파와의일별순위상관은아래와같으며, 이것만으로독립경제메커니즘을증명하지않는다.

'''
t+=tab(['시장','쌍','평균순위상관'],[[x['market'],x['pair'],round(x['mean_daily_score_rank_correlation'],4) if x['mean_daily_score_rank_correlation'] is not None else '미산출'] for x in similarity])
t+='''
RD는 원본이 새로 생성한 단층 GRU16과 선형 head를 원본 Qlib CPU trainer로 학습했다. 5개 causal 입력(수익·gap·고저가/종가·상대거래량)을20세션창으로제공했다. 생성파일의추가closing-pressure helper는자동으로학습feature에포함하지않았으며, 이를별도의검증된RD팩터라고세지않았다. 두엔진의최종순위50/50결합은**전략 계층의 공통 adapter**다.

초기 모델·알파는 인과성/코드/입력·학습 실행이검증된연구후보이지수익우위승인전략이아니다. 초기조건을성과에맞춰고르지않도록50/50구성을미리정했다. 두계좌는동일초기버전에서출발했다.

- close t관측 → open t+1진입 → 계획된5세션후open t+6평가. 미래target종료가cutoff뒤면학습/IC에서제외한다.
- 시장별5거래세션마다복기·리밸런싱한다. 휴장때문에달력의매주금요일과일치하지않는다.
- 상위positive중4종목, 목표각20%·목표총80%, long-only·레버리지0. 가격드리프트에따른실제노출은별도기록했다.
- 광역ETF가격이과거63세션MA아래면다음세션cash라는동일결정론적riskgate가양계좌에서작동한다. 위험청산은계획된5세션보유를단축할수있고, 계속선정된종목은연속보유할수있다.
- 기존V77의수수료·spread·ADVimpact·현금·정수주·참여율을양계좌에동일하게적용한다. 실제브로커호가/세금실측이아니며매일LLM매매판단은없다.

[초기 봉인](../../runtime/task10/initial_strategy_seal.json), [과정평가 봉인](../../runtime/task10/process/), [모델·체크포인트](../../runtime/task10/models/), [native trace와pool](../../runtime/task10/native_full/).

### 실제 학습과 실패 복구

'''
tr=[]
for p in sorted((B/'models').glob('*/*/training.json')):
 if 'attempt1' in str(p):continue
 x=json.loads(p.read_text());tr.append([p.parent.parent.name,p.parent.name,x['asof'][:10],x['train_rows'],x['internal_early_rows'],x['outer_rows'],x.get('effective_batch_size',256),f"{x['outer_mse']:.6f}"])
t+=tab(['모델버전','시장','cutoff','fit','내부early','외부검증','batch','외부MSE'],tr)
t+='''
KR 최초240fit가batch256보다작아Qlib drop_last에서optimizerbatch가0이었고loss가NaN이었다. 실패checkpoint·log를남기고, 표본수에따른기계적batch상한규칙으로128을사용해실제finite학습을확인했다. 수익을보고batch를탐색한것은아니다. 후기재학습은표본수가늘어batch256을사용했으므로재학습효과를순수한새자료효과로만해석하지않는다.

초기외부검증수익US+25.94%/IC.07298,KR+38.20%/IC-.02824는해당개발구간의진단이다. 뒤의6개월성과와연결해독립우위로세지않았다. [훈련 복구](../../runtime/task10/training_recovery.json).

## 4. 실제 주간 Review·Factory 실험

Review는 최소20세션관측과연속2회조건을요구했다. rolling20비용후matched대조대비-2pp이하+성숙IC음수, 또는IC지속저하를연구트리거로사용했다. 단일음의손익으로새알파를강제하지않았다. **실제 trigger 기준선은 기존SPY/069500 matched proxy**다. 사전문서의`index`표현보다구체적인실행차이이며S&P500/KOSPI는아래에서별도대사했다. 원래계약을사후에수익유리한지수로바꾸지않았다.

'''
rc=[]
for m in ['US','KR']:
 x=load('accounts/'+m+'/summary.json');rc.append([m,x['five_session_reviews'],* [x['review_status_counts'][k] for k in ['MAINTAIN','MONITOR','RESEARCH','RISK_ACTION','DATA_ISSUE']]])
t+=tab(['시장','Review','MAINTAIN','MONITOR','RESEARCH','RISK_ACTION','DATA_ISSUE'],rc)
t+='''
RESEARCH가여러번나와도사전연구상한시장별1회를지켰다. 이후요청상태는관측하되무한탐색하지않았다. causes는`UNDETERMINED`를기본으로신호약화·비용·데이터·노출을구분했고정상적인확률적손실가능성을배제하지않았다.

'''
case_rows=[]
for e in cases:
 v=load('experiments/'+e['market']+'_'+e['source_asof']+'/validation.json');r=load('reviews/'+e['market']+'/'+e['source_asof']+'.json');case_rows.append([e['market'],e['source_asof'],pp(r['rolling20_active']),round(r['rolling_mature5session_IC'],5),f"{v['parent']['return_pct']:+.2f}% → {v['candidate']['return_pct']:+.2f}%",f"{v['parent']['IC']:.5f} → {v['candidate']['IC']:.5f}",e['official_status'],e['effective_session'] or '유지'])
t+=tab(['시장','자연trigger','20일active','성숙IC','동일80세션net','동일기간IC','공식Factory','새버전효력'],case_rows)
t+='''
**US7/15:** 원본mutation으로새gap-reversion식을만들고RD모델을확장학습했다. net·MDD(−15.43%→−5.00%)·IC양수·비중복블록12이상·leave-one-name-out양성60%이상·causality/coverage가모두통과했다. 공식상태는`FORWARD_REQUIRED`이고독립Forward0이다. 사용자가지정한격리계좌에서만`REPLAY_ADOPTED` overlay를적용했다.

**KR7/7:** 미국mutation의기준일7/15보다이르므로그미래버전을쓰지않았다. 초기Quanta와KR재학습모델한개만비교했다. IC는양수였지만비용후수익이기존보다낮아`REJECTED`했다. 이를나중수익으로번복하지않았다.

공식함수는운영과같은3제안/1실험/UTC일·중복·해시·변경불가계약을사용했다. **기존PostgreSQL서비스내새격리DB `quant_task3_task10_replay`**와`runtime/task10/factory`만사용하고코인DB/운영DB는수정하지않았다. 모의replayclock7/7·7/15의실제연구실행이지운영예산갱신을기다려생산실험이실행된것은아니다. 각결과에서후속관측요청까지실제Queue DONE을확인했다. 새로운운영dispatcher를배포하지않았다.

[주간 Review](../../runtime/task10/reviews/), [US실험·예약·평가·결과](../../runtime/task10/experiments/US_2026-07-15/), [KR실험](../../runtime/task10/experiments/KR_2026-07-07/), [공식Factory원장](../../runtime/task10/factory/), [DB기록](../../runtime/task10/research_records.jsonl).

## 5. 실제 변경 시점·주문·체결·계속 운용

US는7/15종가이후의검증결정을7/16시가부터사용했다. 이미발생한7/15까지NAV와체결이STATIC/ADAPTIVE에서완전히동일했고, 이후주간Review는신규버전을기록했다. KR은전기간두계좌가동일하다.

'''
trans=load('evaluation/transition.json');t+=tab(['계좌','적용일','관측일','실제 목표 종목','당일 체결수'],[[x['arm'],x['date'],x['observation_date'],', '.join(f'{s} {w:.0%}' for s,w in x['target_symbols'].items()),len(x['fills'])] for x in trans])
t+='\n'+tab(['7/16~11/13','구간수익','구간손익 USD'],[[x['arm'],pct(x['return_effective_to_end']),f"{x['postchange_dollars']:,.2f}"] for x in post])
t+='''
새전략도변경후구간에서약0.99%손실이었다. 기존고정구성의약11.38%손실을줄였다는의미이며항상수익을낸다는증거가아니다. 이전주손실에새식을소급적용하지않았다.

[과거 원장 불변 대사](../../runtime/task10/experiments/US_2026-07-15/no_retroactive_rewrite.json), [실제 targets/fills/NAV](../../runtime/task10/accounts/), [종목별손익·현금/NAV독립대사](../../runtime/task10/evaluation/position_attribution.json).

## 6. 누적·중간기간·월별 NAV

'''
t+=tab(['시장/계좌','net','gross같은체결','시장지수','광역ETF','MDD','연변동성','Sharpe rf0','평균주식노출','체결','회전배수','비용'],[[x['market']+'/'+x['arm'],pct(x['net_return']),pct(x['gross_same_executed_fills']),pct(x['index_price_return']),pct(x['broad_ETF_price_return']),pct(x['MDD']),pct(x['volatility_annualized']),round(x['Sharpe_rf0'],3) if x['Sharpe_rf0'] is not None else '미산출',pct(x['mean_close_exposure']),x['fills'],round(x['turnover_initial_multiple'],2),f"{x['cost_currency']:,.2f}"] for x in s])
t+='''
비용의통화는US USD/KR KRW다. gross는같은실제체결수량에누적수수료·spread·impact현금을더한진단이며, 비용이없어추가주식을살수있던별도계좌와같지않다. 종목별20%/총80%는배분목표다. 리밸런싱사이시장가격변동으로실제비중이드리프트했고관측최대비중을별도보존했다. 이것을매순간하드캡이검증됐다고표현하지않는다. 업종별PIT분류를확보하지못해업종집중은정량완료하지않았고종목HHI·최대비중만대사했다.

'''
t+=tab(['시장/계좌','1개월net','3개월net','약6개월net'],[[m+'/'+arm,*[pct(next(x for x in h if x['market']==m and x['arm']==arm and x['horizon']==hor)['net_return']) for hor in ['1m','3m','6m']]] for m in ['US','KR'] for arm in ['STATIC','ADAPTIVE','MOM63']])
t+='\n월별마지막적격세션의평가금액(미국달러/한국원):\n\n'
monthlyrows=[]
for m in ['US','KR']:
 for month in sorted({x['month'] for x in months if x['market']==m}):
  group=[x for x in months if x['market']==m and x['month']==month];a=next(x for x in group if x['arm']=='ADAPTIVE');monthlyrows.append([m,month,a['last_session'],*[f"{next(x for x in group if x['arm']==arm)['NAV']:,.2f}" for arm in ['STATIC','ADAPTIVE','MOM63']],pct(a['cumulative_return'])])
t+=tab(['시장','월','마지막세션','STATIC NAV','ADAPTIVE NAV','MOM63 NAV','ADAPTIVE누적'],monthlyrows)
t+='''
중간평가는6/18·8/18·11/13종가다. 마지막은정확히11/18까지의6개월이아닌약6개월이다. 유리한날짜만연결하지않았고현금포함연속계좌를계산했다. 배당·분배금은주식·ETF·지수에서모두제외했으므로Total Return우위를주장하지않는다. 시장은S&P500/KOSPI,ETF SPY/KODEX200은동일지수로오인하지않았다.

[전체지표](../../runtime/task10/evaluation/summary.json), [월별NAV](../../runtime/task10/evaluation/monthly_NAV.json), [기간별성과](../../runtime/task10/evaluation/horizons.json), [MA63국면별진단](../../runtime/task10/evaluation/regimes.json).

## 7. 동일 노출·구성요소·예측력 진단

'''
inc=[load(m) for m in ['evaluation/US_adaptive_increment.json','evaluation/KR_adaptive_increment.json']]
t+=tab(['시장','적응형증분','평균노출차이','interval-matched지수기여차이','잔여증분'],[[m,pp(x['ADAPTIVE_minus_STATIC']),pp(x['mean_exposure_difference']),pp(x['interval_matched_index_difference']),pp(x['residual_increment'])] for m,x in zip(['US','KR'],inc)])
t+='''
D-1실제종가노출을지수일간수익에적용한계약기준대조와, overnight/장중보유노출을나눈추가대조를둘다보존했다. 후자는미국결과를본뒤의**사후분해**이며채택에쓰지않았다. 지수+현금기준선은gross로비중조정비용이없으므로완전한같은실행위험의투자가능대체계좌가아니다. US증분이단순노출증가만으로설명되지는않지만위험조정알파의인과증명은아니다.

원본구성을고정한추가사후반사실비교(실제ADAPTIVE를교체하지않음):

'''
t+=tab(['미국구성','누적net','분류'],[['고정초기두엔진',pct(next(x for x in s if x['market']=='US' and x['arm']=='STATIC')['net_return']),'실제STATIC'],*[ [x['arm'],f"{x['metrics']['return_pct']:+.2f}%",'POST_HOC,채택·Factory재선택에미사용'] for x in ab],['mutation+재학습',pct(next(x for x in s if x['market']=='US' and x['arm']=='ADAPTIVE')['net_return']),'실제ADAPTIVE']])
t+='''
이번표본에서는mutation의기여가더컸고재학습단독은나빴다. 이사후비교를보고Q-only를당시채택했다고기록하지않았다. 모델손실·IC와포트폴리오수익의효과는별개였다.

'''
qr=[x for x in quality if x['market']=='US' and x['period']=='post_research'];t+=tab(['7/15이후미국예측','MSE','MAE','RankIC'],[[x['model'],f"{x['MSE']:.6f}",f"{x['MAE']:.6f}",round(x['mean_RankIC'],5)] for x in qr])
t+='''
재학습이MSE를줄여도top4순위변환·riskgate·거래비용·신호조합의투자수익을늘린다고보장하지않는다. 모델품질파일의`pre_initial_validation`은전체prefix(학습포함)진단이지독립외부검증이아니다. 실제outer검증은각training.json을사용한다. 모델품질V1말미미성숙6세션처리를V2로분리교정했고이로전략채택·계좌결과는바뀌지않았다.

[동일노출대조](../../runtime/task10/evaluation/), [사후ablation](../../runtime/task10/evaluation/ablation.json), [예측품질V2](../../runtime/task10/evaluation/model_quality_v2.json).

## 8. 정합성 보완·재시작·검증

- 후보CSV의기본float parser가ULP차이를내어최초재개에서검증freeze가충돌했다. 실패로그를보존하고round_trip parser로기존봉인실수를복원했다. 선택기준·알파수식·과거성과를변경하지않았고원래검증과같음을시험했다.
- 채택후일반Review NAV-horizon이계좌시작5/18을유지하는버전범위오류를발견했다. 원래Review/DB를남기고**V2는새버전7/16부터만채점**한다. 첫7/22는5marks뿐이어서5interval결과PENDING이다. Native5세션IC·첫trigger·Factorygate·매매성과에는영향없었다. 과거손익을개선한수정이아니다.
- 공식Factory의입력/worker/예산/중복/변경불가결과검사,실제PG lease만료후재claim·중복enqueue·오너검사를수행했다. budget/lease주입시험은경제적자기개선성과에합산하지않았다.
- 연구DB dump를새임시DB에실제복원해기록·Queue상태를대사했고시험DB만제거했다. 운영·코인DB나기존원장복원은하지않았다.
- AGENTS필수안전24개+신규walk-forward12개=**36개통과**,실패/오류/skip0. compileall통과. 이는알파성공판정과다르다.

[테스트집계](../../runtime/task10/test_results.json), [새시험](../../runtime/task10/walk_forward_tests_final.xml), [안전시험](../../runtime/task10/safety_tests.xml), [Review V2대사](../../runtime/task10/review_outcome_v2_audit.json), [DB복원](../../runtime/task10/restore_check.json), [복구가능한DBdump](../../runtime/task10/research.dump).

## 9. 한계와 다음 우선순위

1. **운영Factory권위복구가먼저다.** 기본원장경로부재를해결하지않은채운영등록하면과거예산·연구이력을잃을위험이있다. 백업을곧바로최신원장으로간주하지말고과거보고·DB·현재서비스경로와대사해야한다. 이번에는임의복원이나운영승격을하지않았다. [정정된운영관측V2](../../runtime/task10/operating_factory_observation_v2.json).
2. 현재생존cohort·짧은fit/80일검증·한후보/시장·LLM역사지식으로일반화는판단불가다. 기존Task6~9.4에서이미본기간이며새로운독립최종Holdout이아니다. 모델·인간코디네이터의사전역사지식을익명티커로제거했다고주장하지않는다.
3. validation의일부기간은Review의약화근거와겹친다. 이는과거개발검증이며미래독립평가가아니다. 이후구간의계좌를순차적용했지만본질적으로현대모델의역사적진단이다. 비중복블록도IID를증명하지않는다.
4. Quanta는제한된원본진화구성요소, RD는원본생성·학습·재학습구성요소다. 전체native Qlib루프·fin_quant 자율스케줄러를완주했다고하지않는다. 무한주간탐색·상시운영배포도이번완료범위가아니다.
5. ETFproxytrigger와공식지수의역할을명시하고다음계약에서instrument를더정확히고정해야한다. 공식전체휴장·정정·배당·기업행사·PIT업종·상폐범위도미완성이다. 현재가격합의·코드인과성만으로완전한시장재현이라부르지않는다.
6. 새Forward에서는Qmutation효과와RD재학습효과를사전에분리비교할가치가있다. 사후Q-only우수결과를지금승격하지않는다. 재학습MSE개선과최종순위/비중/비용개선사이의연결이우선연구과제다.

## 10. 재현·보존 경로

주요실행명령은아래와같다. 모델재호출·재학습은새실험이므로현재동결자료의검산에는필요하지않다.

```bash
# 완료된계좌와증거검산: 추가LLM·운영쓰기없음
PYTHONPATH=src .venv/bin/python experiments/task10/analyze.py
PYTHONPATH=src .venv/bin/python experiments/task10/ledger_attribution.py
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q experiments/task10/test_walk_forward.py
# 실제진행당시명령: prepare_data.py / run_initial_components.py /
# initial_evaluate.py / find_first_review.py / prepare_first_experiment.py /
# run_worker.sh quanta q mutation / first_retrain.py / validate_candidate.py /
# finish_first.py / replay.py US / replay.py KR / version_outcomes_v2.py
```

`runtime/task10/`에초기seal·각sourcehash·generatedcode·모델/checkpoint·Review·Factory·Queue·targets/fills/NAV·실패·usage를보존했다. 원본checkout/venv와재개에필요한연구pool/workspace도유지했다. 임시relay와소켓만종료/정리하고,기존Task6~9.4성과·운영전략·공식Paper·Live hardlock은변경하지않았다. [진행기록](10_adaptive_progress.md), [전체실험코드](../../experiments/task10/), [전체증거manifest](../../runtime/task10/artifact_manifest.json).
'''
p=R/'docs/development/10_adaptive_quant_walk_forward.md';p.write_text(t);print(p,len(t))

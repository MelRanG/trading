from pathlib import Path
import json
B=Path('runtime/task6_completion');W=Path('/home/ansy/app/quant-diligence');usage=json.loads((B/'evidence/model_usage.json').read_text());events=json.loads((W/'completion-quanta-work/events.json').read_text());rd=json.loads((W/'completion-rd-work/training_metrics.json').read_text());models=json.loads((B/'vibe_model_evaluation/summary.json').read_text());native=json.loads((W/'completion-vibe-work/native_result.json').read_text())
s='''# Task 6 마무리 — 핵심 연구 엔진·평가·Factory 연결

## 1. 결론과 완료 판정

**HYBRID_MINIMAL을 유지한다. 세 엔진의 핵심 기능과 공식 Factory 격리 연결은 실제 실행됐다. 투자 우위·운영 전략 승격은 아직 입증·허용하지 않았다.** 기존 source/전략/Paper/Live 설정은 변경하지 않았다. 아래 PASS는 명시된 기능의 실증이며 모든 native 환경·투자 효능의 완전 검증을 의미하지 않는다.

| 항목 | 판정 | 실제 완료 범위 / 남은 범위 |
|---|---|---|
| A QuantaAlpha | **PASS — 진화 제어기** | 원본 planner→EvolutionController→초기·mutation·crossover→원본 가설/DSL/template→격리 평가→원본 feedback→pool 재개. native AlphaAgentLoop/Qlib backtest 전체는 사용하지 않고 공통 평가 adapter 사용. 원본 round 상한 결함·지표 alias 교정 이력은 아래에 공개 |
| B RD-Agent | **PASS — 모델 학습·팩터 결합** | 원본 CoSTEER 생성 GRU를 원본 Qlib 학습기로 학습·예측. 기존 native RD 팩터 추가 비교, 원본 model feedback→후속 모델/팩터 가설. 전체 fin_quant 선택 제어기는 **PARTIAL**, 별도 controller 완주 아님 |
| C Vibe | **PASS — 실제 데이터·연구 경로** | 실제 train 통계/CSV 읽기→가설/코드→원본 backtest/Research Lab→실측 피드백/NO_CHANGE→원본 goal 복구. 첫 feedback CLI는 구독 quota로 exit1, 산출물은 저장됐으며 한도 갱신 후 terminal만 재개해 exit0 확인 |
| D Factory | **PASS — 허용된 격리 실증** | 기존 공식 함수+PostgreSQL Queue에서 등록/차단/모의 날짜 갱신/예약/격리 평가/기록/장애 재개/원본 후속 가설까지. 실제 운영 등록은 **BLOCKED**, 정상 일일 예산 대기 |
| E 평가 정합성 | **PASS — V2/V2.1** | 예측과 보유기간 정렬·양방향 비용·노출/선택효과·독립 대사 시험. V1 불변. native excess 지표 이름의 매핑 문제를 V2.1에서 교정; 이전 LLM 피드백을 교정 후 재실행한 것은 아님 |
| F 모델 효율 | **PASS — 제한 비교** | 같은 동결 요청으로 Terra/Luna 실제 호출·실행·분류·usage 비교. 1쌍이므로 일반 우열/기본 연구 모델 변경 근거 부족 |

Task7의 기업·산업 연구를 별도 adapter로 시작할 준비는 됐다. 전문 연구 엔진은 선택 실행하고 운영 도입·자동 승격은 보류한다. 원본 full fin_quant, Quanta native AlphaAgentLoop, 교정된 지표로의 후속 독립 반복, 실제 Factory 예산 갱신 후 운영 실행, 새로운 PIT/Forward 투자 검증은 남는다.

## 2. 원본·격리·고정 조건

기존 PRE/Task6를 재조사·재설치하지 않고 재사용했다.

- Vibe `0025531f005d4a7aac3fb884cda2fba9318e7158` / 기존 vibe-env.
- Quanta `b7ceb27b1001261d7a95b209a963664ae1f8ab23`, quantaalpha0.1.0 + **rdagent0.8.0**.
- 별도 RD `484776c211e4fbbeef03e0ec00d6bbee7362a4f4`, **rdagent1.0.0**, pyqlib0.9.7.
- 모델 학습에 필요한 **torch2.8.0+cpu**만 기존 격리 RD venv에 추가. 운영 .venv 변경 없음. pip check 정상, `evidence/torch_install.log`, `rd_post_torch_environment.log`.
- CPU2/메모리4G/PID256, network=none, user1000, cap-drop ALL/no-new-privileges. 설치 단계만 다운로드 허용. worker에는 운영 DB/브로커/인증/호스트 Docker socket을 제공하지 않았다.
- host Codex 구독 인증을 임시 UNIX transport로 사용. 실제 research는 Terra, 비교 Luna scope만 gpt-6-luna. 원본의 gpt-4o 표시는 호환 alias이며 실제 실행 모델 아님. 유료 API 결제 없음. 임시 중계는 종료·소켓 제거.

새 계약은 `experiments/task6_completion/contract.json`, 별도 결과는 `runtime/task6_completion/`이다. 이전 Task6 예산·성과를 초기화하거나 덮어쓰지 않았다. 같은 기존 미국38 train≤2024와 반복 검증2025만 사용. 2026 파일은 추가 worker에 mount하지 않았으며 이미 확인된 역사 결과를 새 Holdout으로 취급하지 않았다. 현재 survivor cohort·조정주가/기업행사·모델 과거지식 한계는 유지된다.

## 3. Quanta 원본 진화형 연구

실제 경로: `quantaalpha/pipeline/planning.py:generate_parallel_directions` → `pipeline/evolution/controller.py:EvolutionController` → 원본 MutationOperator/CrossoverOperator → `AlphaAgentHypothesisGen`/`AlphaAgentHypothesis2FactorExpression`/`FactorParsingStrategy` → 별도 network-none 코드 실행 → V2 평가 → `AlphaAgentQlibFactorHypothesisExperiment2Feedback` → `report_task_complete`/`save_state`/`load_state`.

`quanta_loop.py`는 원본 제어기와 operator를 직접 호출하며 parent/단계/선택 로직을 대체하지 않는다. Qlib runner 대신 `dispatch_evaluation.py`가 외부 평가를 연결한다. 생성 코드는 인증·relay 없는 별도 evaluator에서 실행하고 prefix 불변을 검사했다. 연구 worker는 train HDF만 읽으며 평가 요약만 돌려받는다. 두 planning 방향은 실제 LLM 생성이며 fallback=False. semantic consistency LLM guard는 기존처럼 비활성화했으므로 전체 semantic validator 통과라고 주장하지 않는다.

| node | phase/round | 실제 parent IDs | 2025 IC | V2 net% |
|---|---|---|---:|---:|
'''
for i,e in enumerate(events):s+=f"| {i} | {e['phase']}/{e['round']} | {', '.join(e['parents']) or '없음'} | {e['metrics']['IC']:.5f} | {e['metrics']['return_pct']:.2f} |\n"
s+='''
초기 경로는 volume-backed decline reversal과 장기 추세 방향 등 서로 다른 연구 경로다. 각 mutation/crossover의 입력은 parent trajectory의 hypothesis/factor/code/실제 metric/feedback이며, 실제 전달 guidance와 새 공식·코드는 `native/quanta/events.json`, `node*/{request,factor,feedback,metrics,state}.*` 및 `model_calls/quanta/`에 보존했다. crossover는 실제 두 parent를 결합했지만 통계적 독립성·우수성은 입증되지 않았다. 전 경로의 IC·비용 후 결과가 부정적이어도 연구 실패를 삭제하지 않았다.

**원본 상한 결함:** max_rounds=3을 지정했으나 crossover→mutation 내부 전환이 외부 상한 확인을 건너뛰어 round3 node가 추가됐다. 실제6개(초기2/mutation3/crossover1)를 그대로 보존했다. 원본을 수정하지 않았고, 향후 adapter에는 사전 계획 5개를 넘지 않는 외부 hard stop을 추가했다. 실행 당시 source와 이후 교정 source를 분리 보존한다. pool6개를 새 controller에서 재로딩한 결과도 일치했다. 실제 사용24call은 사전 상한24 이내이며 추가 예산을 열지 않았다.

## 4. RD 실제 모델·팩터 연구

기존 native GRU 가설/명세를 출발점으로 **원본 ModelMultiProcessEvolvingStrategy**가 `model.py`를 생성했다. 고정 단층 GRU hidden16/20세션, flexible feature 수, CPU2threads/seed42/5epochs. 원본 코드의 출력은 [B]이고 Qlib loss는 [B,1]을 요구하므로 tensor shape adapter를 사용했고, 손실이 표본 간 잘못 broadcast하지 않는지 독립 MSE와 확인했다. 모델의 수식·파라미터를 성과에 맞춰 튜닝하지 않았다.

원본 `qlib.contrib.model.pytorch_general_nn.GeneralPTNN.fit/predict`를 DatasetH adapter와 사용했다. train21,052행, 내부 early-stop5,244행, 2025 예측9,462행. 내부 경계2024-06-13, 학습 label 최종2024-06-12, 내부 검증 label 최종2024-12-31. 외부2025를 정규화·학습·조기 종료에 쓰지 않았다. 원본의 결측 ffill/bfill time-series loader를 사용하지 않고 완전한 causal window만 전달했다.

기본5개(과거 수익·갭·고가/종가·저가/종가·상대거래량)와 기존 native RD close-location 팩터를 추가한6개를 각각 같은 고정 조건으로 학습했다. 이 비교는 팩터→모델 결합의 실제 실행이며 새 joint controller 전체를 뜻하지 않는다.

| 구성 | train MSE 첫→마지막 epoch | 2025 MSE / MAE | IC | V2 net% |
|---|---:|---:|---:|---:|
'''
for key in ['baseline','factor_augmented']:
 r=rd[key];s+=f"| {key} | {r['loss_history']['train'][0]:.8f} → {r['loss_history']['train'][-1]:.8f} | {r['validation_mse']:.8f} / {r['validation_mae']:.6f} | {r['aligned']['IC']:.5f} | {r['aligned']['return_pct']:.2f} |\n"
s+='''
팩터 추가 시 MSE/MAE는 악화됐으나 해당 반복 표본의 IC/net은 개선됐다. 이를 일반화·알파로 승격하지 않았다. 원본 model feedback은 이 차이·비용·반복2025 한계를 읽고 추가 reversal 팩터 가설을 제안했고, 원본 ModelHypothesisGen은 hidden-state mean pooling 후속 모델 가설을 생성했다. 후속 가설의 새 코드/추가 학습과 full fin_quant adaptive scheduler는 미실행이다. 기존 제안의 분기 재학습/확장-window 예측 정책도 이번 고정 모델 증명 범위 밖이다.

코드·checkpoint SHA·정규화 통계·epoch loss·예측 CSV·native feedback·후속 명세: `native/rd/`, 원본 work의 `baseline.pth`, `factor_augmented.pth`. CPU 설치/학습 오류 해결 뒤 새로운 train 결과이며 과거의 모델 가설만 생성한 결과와 분리했다. 후속 template의 gross metric key 누락은 로그를 보존하고 재학습·재코딩 없이 기존 실제 metric으로 재개했다.

## 5. Vibe 실제 관측·원본 평가·복구

공식 CLI가 실제 train 통계 `observations.json`과 `training/US001.csv`를 read_file로 열었다. 관측 근거는 mean intraday2.7031829bp, median20세션 변동성0.01558834, 2022-02-02 open151.25/close148.0 등이며 원본 파일과 대조 가능한 숫자다. 이 숫자는 반전 가설을 증명하는 상관 결과가 아니므로 모형도 동기를 제한적으로 서술했다.

신규 hypothesis `hyp_45868856c790`: 장중 하락을 과거 변동성으로 조정한 다음 세션 반전, 실행 코드 생성. 기존 고정 경로로 original backtest runner를 실행하고 Autopilot goal `goal_4be192543486`, linked run, Research Lab cost job `024bd04b26114d38b712c2f67e9d0103`을 저장했다.

- native overnight/carry 회계 total return **+0.5076%**, 고정 비용 stress **−15.5429%**. Research Lab job completed.
- 동일 신규 코드의 공통 intraday V2는 **−17.6345%**, gross **+5.7243%**, IC **−0.03363**, 비용 **22,673.94USD**. 서로 다른 보유·비용 계약이므로 수익을 직접 동등 비교하지 않는다.
- native wrapper는 점수를 positive top4×20% target으로 변환한다. 최초 benchmark alias(underscore)·top-level alias assignment가 원본 validator에 거부돼 공식 symbol 규칙과 허용 class 구조로만 수정했다. 원본 변경이나 알파 수정은 아니다. 실패 로그 보존.

실제 피드백은 예측 부진·비용·불확실성을 나누고 **NO_CHANGE**를 남겼다. 구독 quota 오류는 마지막 terminal 응답 단계에서 발생했으며 feedback.json/hypothesis는 이미 저장됐다. 이 CLI를 성공으로 덮어쓰지 않았다. 중단 후 확인하여 원래 session ID로 GoalStore를 복구하고 feedback hash/evidence를 연결했다. 한도 갱신 후 실제 CLI를 읽기·최종 응답만 재개해 run `20261113_093440_68_48c9af`/exit0 확인. 가설/전략 재생성이나 평가 반복은 없었다. 초기 실패·재개 성공·goal lookup의 session scope 차이는 모두 보존했다.

## 6. 평가 V2와 native 표기 V2.1

`aligned.py`: close t의 score → **open t+1 진입, close t+1 전량청산**, label도 close/open−1. 당일 포지션0, 양방향 fee/spread/ADV impact, 정수 수량·최소 주문·cash cap 적용. 종목 positive top4×20%, 초기 USD100k, 기존 US 비용 가정 고정. 체결량 기반 실제 노출/양방향 회전·시장 proxy 수익·선택효과를 따로 저장한다. 시장 proxy는 전달된 panel 평균이며 Quanta/Vibe 평가 panel은 US38+SPY, RD 학습 panel은 US38이다. 따라서 시장/선택 분해의 기초 basket 차이도 명시하고 그 분해만으로 엔진 간 우열을 주장하지 않는다.

미래 변경 불변, 신호 다음 세션 체결, overnight PnL 미혼입, 양방향 비용과 fill→NAV 대사 시험3개 통과. 같은 과거 Task6 Vibe0를 V2로 평가하면 V1 −8.7147%→V2 −7.7939%다. 신호는 동일해도 보유기간·비용이 달라진 결과이지 버그 수정으로 과거 성과를 개선한 것이 아니다. 기존 Task6 final/성과 파일은 그대로다.

**native alias 표시 교정:** 최초 원본 feedback adapter의 `excess_return...` key에 절대 gross/net 평균을 전달한 문제가 있어, 실제 raw 전략 수익은 그대로 두고 V2.1 `native_metrics.py`에서 노출에 맞춘 market proxy 대비 초과수익/relative drawdown/IR로 변환했다. 두 독립 시험(동일 market 노출의 excess=0, 비용 drag는 net excess에만 반영) 통과. native controller의 기존 피드백을 교정 수치로 다시 실행했다고 주장하지 않는다. 해당 과거 해석·후속 가설에 미친 영향은 미검증이다. 실제 실행 source는 `evidence/executed_sources/`, corrected export8개는 `native_metric_exports_v2_1/`에 보존하고 미래 worker는 corrected mapping을 사용한다.

이 표기 문제 때문에 원본 Qlib benchmark 초과성과나 엔진 우위는 주장할 수 없다. canonical V2의 실제 체결/수익/IC와 표시 correction의 의미를 분리한다. 반복 검증2025는 개발 진단이며 최종 선택·성과 입증 자료가 아니다.

## 7. 공식 Factory·PostgreSQL 큐

실운영 제안3/일·실험1/일 한도를 변경하지 않았다. 현재도 사용3/1, 다음 UTC reset2026-11-14 00:00(한국09:00). 기존 Task5→기존 Task6→추가 후속 순서를 보존하고 기존 원장을 다른 namespace/date/옛 결과로 대체하지 않았다. 실제 운영 Task6 등록은 정상 대기다.

사용자가 허용한 격리 검증은 **같은 기존 PostgreSQL 서비스의 새 DB `quant_task3_completion_test`**와 기존 Store/Queue, 별도 시험 Factory directory에서 수행했다. 코인 DB/운영 DB 수정 없음. `register_review_proposal`/`reserve_review_experiment`/`record_review_experiment`를 직접 사용하며 clock을 시험 디렉터리 안에서만11/13→11/14로 주입했다. 실제 기다려 운영 날짜가 바뀐 결과가 아니다.

1. 공식 seed 예약으로 당일 예산 소진, 실제 연구 제안은 등록하되 예약 차단.
2. 시험 날짜 갱신 후 예약. 실행 직후 죽은 worker의 lease를 재현하고 새 Store/Queue로 재개, 같은 예약 재사용.
3. 실제 Quanta node0 frozen code output을 V2로 격리 평가. snapshot/worker hash 검증 후 공식 `INSUFFICIENT_EVIDENCE` 기록. duplicate 등록·결과·claim 차단.
4. `Queue.observe` 후속 요청→원본 Quanta HypothesisGen 호출→새 가설 저장→후속 job DONE. duplicate followup claim 차단. 결과를 투자 우위로 채택하지 않음.

`factory_test/{result,followup_result,records}.json[l]`, 공식 registry/contracts/reservations, `factory_probe.py`, `drain_followup.py`, `factory_followup.py`가 증거다. 기술 오류/예측 실패/비용 문제/불충분한 통계/미성숙 결과를 분리하도록 source result와 원본 feedback을 전달했다. 이 연결은 격리 기능 완주이며 새 생산 scheduler 배포나 실제 운영 budget reset 완료가 아니다.

## 8. Luna vs Terra와 운영 정책

동일 JSON body·동결 관측·연구 목표로 각1회 요청. 코드 및 5개 gold audit 분류를 평가했다. 두 코드 실행/prefix 통과·분류5/5·반증문 작성. 경험적 성과를 날조한 문장은 없었다. Terra는 intraday 반전 가설, Luna는 변동성 가설을 제안했으나 **목표는 intraday인데 가설은 overnight 보상으로 설명**했고 반증은 고정 top4와 다른 quintile 비교를 제안했다. 연구 설계 정합성 오류를 코드 실행 성공으로 감추지 않았다.

| 모델 비교 scope | 실제 모델 | tokens | 실행/분류 | 해석 |
|---|---|---:|---|---|
| terra | gpt-6.1-terra | 24,364 | 성공 /5·5 | 1개의 비교 후보이며 일반적 품질 증명 아님 |
| luna | gpt-6-luna | 17,691 | 성공 /5·5 | 측정 tokens27.39% 절감, 예측기간·평가규칙 오류 |

실비 배분은 알 수 없어 금액은 null. 따라서 유효 연구1건의 금전 비용은 추정하지 않고 실제 token/성공·오류를 제시한다. tokenizer/system overhead가 모델마다 달라 이 차이를 사용자 프롬프트 압축만의 효과로 귀속하지 않는다. 이 작은 표본으로 Luna의 기본 연구 모델 채택은 보류한다. 가설·경제적 해석·복잡한 모델 코드는 Terra, 정해진 분류/요약은 Luna shadow 후보. `model_policy.json`에서 project scope별 모델을 선택할 수 있고 model 변경은 cache fingerprint에 포함하도록 보완했다. 반복 전체 history 대신 실제 통계/metric/참조 경로를 전달한다.

### 전체 추가 실행 사용량

| scope | 호출(성공/실패) | 실측 tokens | 비고 |
|---|---:|---:|---|
'''
for e,u in usage.items():s+=f"| {e} | {u['calls']} ({u['success']}/{u['failed']}) | {u['measured_tokens']:,} | "+('quota 실패1회 usage 미확인; 복구2회 포함' if e=='vibe' else '동일 사전 budget 내')+' |\n'
s+='''
모든 call/request/response/trace 보존. subscription quota는 프로젝트별 budget과 별개였고 결제·다른 인증으로 우회하지 않았다. native RD가 출력하는 gpt-4o 요율 기반 금액은 실제 Terra 구독 비용으로 취급하지 않는다. 중계 cache 때문에 원본의 중복 동일 요청은 실제 model call을 추가하지 않았다.

## 9. 시험·재개·남은 범위

- AGENTS 최소4파일 **24 passed** (`safety_tests.log`). 과거 Task6 통과 수를 이번 통과에 합산하지 않음.
- 평가 신규 시험 **5 passed** (`evaluation_tests_final.log`), compileall 성공. prefix는 실제 생성6 Quanta+Vibe/Terra/Luna3개 실행에서 통과.
- native Quanta controller exit0/state restore6, RD worker/실제 학습 성공, Vibe initial/native Research Lab 성공. Vibe feedback CLI 최초 exit1/quota, terminal recovery exit0를 각각 보존.
- pytest/LLM 중단 뒤 로그·프로세스를 확인해 완료 모델학습·진화·비교를 다시 실행하지 않았다. 운영 tracked diff 시작/종료 동일, 세 원본 checkout 변경0.
- 운영 경로 변경이 없어 Task3~5 전체 DB/Live/Forward 시험을 무의미하게 반복하지 않았다. 신규 isolated test DB는 재개를 위해 남겼다. 이번 연구를 신규 Paper 주문으로 연결하지 않음.

재현 진입점:

```bash
PYTHONPATH=experiments/task6_completion .venv/bin/python -m unittest discover -s experiments/task6_completion -p 'test_*.py' -v
# 실제 실행한 원본/격리 진입점. LLM 재실행 전 계약·quota·cache·상태/기존 output을 확인한다.
bash experiments/task6_completion/run_worker.sh quanta quanta_loop.py
.venv/bin/python experiments/task6_completion/dispatch_evaluation.py
bash experiments/task6_completion/run_worker.sh rd rd_model.py
bash experiments/task6_completion/run_training.sh
bash experiments/task6_completion/run_vibe.sh
.venv/bin/python experiments/task6_completion/evaluate_vibe_models.py
# 공식 Factory 격리 시험: 이미 저장한 결과/DB를 읽어 재개; 운영 budget clock 변경 금지.
PYTHONPATH=src .venv/bin/python experiments/task6_completion/factory_probe.py
PYTHONPATH=src .venv/bin/python experiments/task6_completion/drain_followup.py
```

이 명령은 실행 경로의 기록이며 과거 mutable output에 새 연구를 덮어써도 된다는 의미가 아니다. 실제 최초 실행 source와 후속 metric/round-bound 교정 source를 구분한다. 새 연구에는 새 run namespace/계약을 사용한다. 앞으로 필요한 것은 corrected native metric 전달로 새 개발 episode를 검증하고, native full fin_quant/AlphaAgentLoop의 이득이 추가 환경 비용보다 큰지 제한 비교하는 것이다. 운영 Factory 정상 갱신 이후의 실제 실행과 PIT/Forward 투자 성과는 여전히 대기·미검증이다.

## 10. 보존·중복 제거

재사용할 기능은 원본 planner/operator/CoSTEER/Qlib trainer/Vibe Research Lab과 기존 Factory/Queue/Store다. 같은 기능을 운영 서비스로 복제하지 않았다. 새 코드는 평가/shape/입출력/큐 경계 adapter와 독립 시험이다. 별도 상시 scheduler/gateway를 배포하지 않는다.

`runtime/task6_completion/`은 Git 제외이므로 원본 checkout·환경·raw split·native model checkpoint/state·LLM trace·실패 로그와 함께 보존해야 한다. 정리할 수 있는 것은 이번 pytest 전체 복사본·CPU wheel cache·중복 평가 중간 HDF뿐이다. 삭제 목록·bytes는 `evidence/cleanup.json`, 최종 파일/해시는 `evidence/artifact_manifest.json`에 기록한다. 원장·원본 연구·기존 Task6 final을 삭제하지 않았다.
'''
Path('docs/development/06_research_completion_report.md').write_text(s)
print('report written')

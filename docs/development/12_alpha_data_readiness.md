# Task 12 — 팀3 알파 연구 입력·국면·공통 검증 준비

2026-11-16 KST · HYBRID_MINIMAL · 신규 알파 연구/학습/경제성 백테스트 없음

## 핵심 판정

**`READY_FOR_TASK13_S` — 미국 38개·한국 20개의 기존 OHLCV에서 제한된 알파 생성·계산·모델 연구를 시작할 수 있다. B는 미완료다. B 확보를 기다리며 S 연구를 중단할 이유는 없다.**

- 기본 63세션 warmup과 기존 원가격 학습 구간에서는 **5·20세션 label이 유효**하다. 60세션은 학습 label이 0개다. 더 짧은 사전 선언 warmup 또는 적격한 별도 입력이 필요한 제한이며, 모든 알파를 5세션으로 축소하지 않는다.
- QuantaAlpha·RD-Agent·Vibe/Qlib의 기존 격리 환경에서 대표 원본 구성요소를 실행했다. 새 가설 생성·학습·전체 controller 완주나 엔진 우열을 검증한 작업은 아니다.
- 순수 예측력 → 고정 노출 → 같은 신호의 위험 관리 효과를 분리하는 얇은 연결을 만들었다. 기존 Qlib 지표와 Quant 실행기를 호출하며 새 백테스터는 만들지 않았다.
- Forward의 **실패 attempt가 재시도를 차단하는 결함을 재현·수정**했다. 초기 계약·모델·전략 계산·과거 계좌 기록은 보존했다. 정규 스케줄러의 수정본 호출을 확인했으며, 다음 완료 세션과 성숙 결과는 **PENDING**이다.
- 신규 외부 데이터 요청 **0**, LLM 호출 **0**, 학습 **0**, 설치 **0**. 필수 안전 53개, 복구/기존 Forward 17개, 입력·평가 5개 시험 통과. 투자 우위나 자기개선의 경제적 성공 판정은 없다.

주 계약은 [contract.json](../../experiments/task12/contract.json), 사용 입력/엔진별 경계는 [task13_inputs.json](../../runtime/task12/task13_inputs.json), 전체 원본 경로·hash·결측·label 수는 [readiness.json](../../runtime/task12/readiness.json)에 있다. Task11의 [평가·다중비교 계약](11_research_architecture_audit.md#7-task1217-공통-평가-계약)을 이어받는다. 이 보고서의 범위 제한이 엔진 전체에 대한 기각을 의미하지 않는다.

## 1. 미국·한국 S/B 데이터 적격성

| 항목 | 미국 S | 한국 S |
|---|---|---|
| 기존 개별주식 / 비교용 ETF | 38 / SPY | 20 / KODEX200 |
| 주 입력 | `runtime/task10/tape/US/` | `runtime/task10/tape/KR/` |
| 시장 세션 범위 | 2025-07-31~2026-11-13, 326세션 | 2025-07-21~2026-11-13, 322세션 |
| 시장 달력에 정렬한 OHLCV 결측 | 0행 | 19행, 16종목. 해당 특징/label/거래는 제외·차단 |
| 가격 기준 | 기존 두 공급자 대사 원가격, 명목 OHLCV | 동일. 당시 완전한 공식 PIT 자료라는 뜻은 아님 |
| B | `NOT_READY` | `NOT_READY` |

B의 일별 적격 50종목/시장과 역사적 상장 구성·상폐·기업행사 조건을 충족하지 못했다. 현재 생존 코호트로 광범위 시장 성능을 확증할 수 없다. 전체 시장 DB를 새로 만들거나 단순히 12·30종목을 추가해 B로 승격하지 않았다.

**입력 품질은 항목별로 판정한다.** 파일 hash·OHLCV 구조와 저장된 revision gate 통과는 확인됐다. V87 초기 `NO_REFERENCE`는 자체 최초 snapshot의 통과이며, 과거 원본과의 동일성 인증이 아니다. 역사적 유니버스·거래정지·상폐 처리와 최초 관측의 완전성은 `UNVERIFIED`, 기업행사는 `PARTIAL`이다. vendor `firstTradeDate`도 완전한 상장 증명이 아니며 한국 017670·009150에는 값이 없다. 이를 추정해 채우지 않았다.

공급자가 선언한 주 입력 기간 내 split은 없지만, 이는 모든 기업행사가 없었다는 증명이 아니다. 배당 이벤트가 있어도 label은 **명목 가격 수익률**이다. 배당/분할/권리·티커 변경 대사가 필요한 종목은 경제성 계산 전에 차단하거나 별도 적격 track으로 분리한다. 수정주가로 체결했다는 가정을 하지 않는다. Task6의 2022-02-02~2026-11-12 조정주가 자료는 별도 참고 입력이며 원가격 execution panel에 이어 붙이지 않았다.

모델용 공유 입력은 시장별 하나만 준비했다: [US.csv](../../runtime/task12/fit_inputs/US.csv) 4,066행, [KR.csv](../../runtime/task12/fit_inputs/KR.csv) 2,200행. 익명 alias·OHLCV·과거 return만 있고 label/evaluator tail은 없다. 원문은 복사하지 않고 hash로 참조한다. 향후 연구 worker에는 이 fit 입력만 read-only mount하고 평가 전용 전체 tape/성과 디렉터리는 전달하지 않는다. 이는 입력 분리 계약이며 OS 전체 사용자 권한으로 과거 자료가 접근 불가능하다고 주장하지 않는다.

### 시각과 노출 이력

가격 날짜, 실제 다운로드 시각, 가상 역사 cutoff는 서로 다르다. 이 자료는 2026년 11월 관측한 **backfill**이다. 2025년에 실제 보유했던 관측 원본으로 표시하지 않는다. S는 가격 공개 가능 시점을 가정한 제한 역사 진단이고, 실제 Forward는 source receipt와 완료 세션 시각을 모두 요구한다.

Task6~10 및 Task9.x가 이미 본 2021~2026 결과는 노출된 개발 자료다. `fit_end=2025-12-31`, 진단 validation은 2026-01-01 이후로 명시했지만, 이름을 validation으로 바꿔 독립 Holdout이 되지는 않는다. 최신 LLM의 역사 지식 편향도 남는다. 신규 독립 확증은 봉인 뒤 Forward 또는 별도 적격성이 확인된 미노출 자료에서 해야 한다.

## 2. label·warmup·결측 계약

가설 생성 전에 `alpha_kind`, 경제 메커니즘, primary horizon, 유효 warmup, feature/label 시각, 공개 지연, source hash, 후보 fingerprint를 선언한다. 공통 일봉 label은 다음과 같다.

`close t 이후 점수 → open t+1 진입 → open t+H+1 청산`, `y=open(t+H+1)/open(t+1)-1`.

자체 종목의 다음 유효 행으로 날짜를 건너뛰지 않고 **같은 시장 세션**에 정렬한다. 진입~청산 사이 필요한 open에 하나라도 결측/비양수가 있으면 label을 무효화한다. 미래 cutoff 이후 자료를 먼저 잘라낸 뒤 생성하며, 마지막 H+1개 signal 세션은 미성숙이다. fit label의 종료는 fit 경계보다 엄격히 이전이어야 한다. 정규화/전처리는 fit에서만 학습하고, 분할 시 겹치는 label purge 및 primary horizon·공개 지연 이상의 embargo를 적용한다.

| H / 기본 warmup 63 | US fit label | KR fit label | US 전체 성숙 label | KR 전체 성숙 label |
|---|---:|---:|---:|---:|
| 5 | 1,406 | 820 | 9,766 | 5,030 |
| 20 | 836 | 520 | 9,196 | 4,655 |
| 60 | **0** | **0** | 7,676 | 3,681 |

단위는 상관된 **종목×세션**이며 독립 표본 수가 아니다. 전체 성숙 수는 노출된 진단 기간을 포함한다. H60의 전체 label 존재가 적절한 학습 구간을 보장하지 않는다. 예를 들어 warmup20을 명시한 경우 H60 fit은 US950/KR235개지만 매우 짧은 시계열이며, 이를 보고 warmup을 낮춰 성공시키면 안 된다. warmup126/252는 현재 fit prefix에서 사용 불가다. 각 원본 수식/모델의 실제 입력 길이가 우선이며 기본63은 전 후보 강제값이 아니다.

횡단면 최저 유효 종목 수·분위 수·동률 처리·변동 없는 신호·산업중립 여부도 사전 선언한다. 업종 분류가 PIT 적격하지 않으면 산업중립 결과는 `INSUFFICIENT_EVIDENCE`다. 누락 수급·재무·vintage를 0이나 현재 값으로 채우지 않는다. 현 숫자 packet의 DECK 매출 한 건은 기간·단위·공개일·원문 hash 검증을 통과했지만 **58종목 PIT 재무 feature panel은 아니다**: [financial_source_probe.json](../../runtime/task12/financial_source_probe.json).

## 3. 시장 국면: 실제 확보 범위와 사용 경계

[regime_coverage.json](../../runtime/task12/regime_coverage.json)은 지수/대용 ETF별 원본 hash·기간·상태 수·연속 구간을 보존한다. [index_window_checks.json](../../runtime/task12/index_window_checks.json)은 사전 선택한 달력 구간의 시작/종료 세션·가격 변화·상태 수를 계산했다. 종목 수익률로 기간을 고르지 않았다. 서로 다른 snapshot을 조용히 이어 붙이지 않았다.

| 확보한 계열 | 실제 범위 | 사용 제한 |
|---|---|---|
| 레거시 KOSPI `data/all_prices_long_v62_9_expanded.csv`의 KS11 행 | 2018-01-02~2026-10-02, 2,144행 | 지수 국면 참고. 같은 파일의 혼합 가격 종목 행을 새 nominal 거래에 사용하지 않음 |
| Task6 SPY 조정 가격 | 2022-02-02~2026-11-12, 1,200행 | 미국 시장 **대용 ETF**, S&P500 가격지수와 구별 |
| Task9.1 S&P500 / KOSPI | 2025-06-30~2026-07-10, 259 / 253행 | 기존 노출 backfill, 부분 공급자 근거 |
| Task10 S&P500 / KOSPI | 2026-05-14~2026-11-13, 128 / 124행 | 별도 tail snapshot. 위 자료와 자동 병합 안 함 |

### 국면 후보와 저장 가격의 확인값

다음은 **지수/대용계열의 종가 변화**이며 전략 성과가 아니다. 구간 전체를 단일 국면이라고 지정한 것도 아니다.

| 달력 평가 후보 | 한국 KOSPI | 미국 자료 | 범위 판정 |
|---|---:|---:|---|
| 2018 | 1/2~12/28 **-17.69%** | 적합한 기존 계열 미확인 | 한국 지속 하락 참고, 미국 `INSUFFICIENT_EVIDENCE` |
| 2020 급락 후보 2~3월 | 2/3~3/31 **-17.19%** | 미확인 | 한국 EX_POST CRASH 3/5~3/16, REBOUND 3/17~4/3 등이 검출됨 |
| 2020 반등 후보 4~8월 | 4/1~8/31 **+38.01%** | 미확인 | 한국 반등·상승 참고 |
| 2022 | 2/3~12/29 **-17.41%** | SPY 2/2~12/30 **-16.38%** | 하락 후보, 미국 index 자체와 구분 |
| 2023~2024 | 1/3~12/30 **+8.15%** | SPY 1/3~12/31 **+53.90%** | 한국 순환/횡보·미국 상승 참고; 주 입력 종목 panel은 이 시기 미포함 |
| 2026-02-27~03-31 | **-19.08%** | S&P500 **-5.09%** | 한국 급락, 미국 하락을 같은 강도/전환점으로 취급하지 않음 |
| 2026-03-31~04-08 | **+16.23%** | S&P500 **+3.90%** | 각각 반등 관측. 미국 저점 날짜를 3/31로 확정하지 않음 |

**AS_OF_REGIME**는 과거 MA126·63세션 return·5/10세션 변화·과거 drawdown만 사용한다. 순서는 CRASH(5세션≤-10%), REBOUND(10세션≥8%, 과거 급락), UP/DOWN(63세션 ±10% 및 MA126 방향), SIDEWAYS(|63세션|≤5%), TRANSITION이며 MA warmup 이전은 WARMUP이다. HIGH_VOL은 과거20세션 연율 변동성≥30%로 중첩 태그다. 이 분류는 분석용이며 기존 Forward MA63 위험 규칙을 교체하지 않는다.

**EX_POST_REGIME**는 이후20세션 ±10%/횡보±5%, 이후5세션 급락·사후 반등을 분류한다. 연구·학습·매매 입력에 넣지 않으며 마지막20세션은 PENDING이다. 2026년 한국 급락 때도 기존 강한 상승 때문에 AS_OF의 UP이 남고, 미국 3월이 이 고정 기준의 CRASH로 분류되지 않는다. 분류기를 사후 결과에 맞춰 바꾸지 않았다. prefix 미래 교란 시험으로 AS_OF 불변·EX_POST 민감성을 확인했다.

오래된 지수의 국면 존재와 해당 시기 종목 panel/최초 정보의 확보는 별개다. 원가격 S 종목은 2025년7월 이후만 있고, 급락·반등 표본이 짧고 중첩된다. 미국2018/2020, 종목별 다국면 B 일반화, 충분한 독립 episode는 **`INSUFFICIENT_EVIDENCE`**다. 장기간 지수 문맥 확보를 B 알파 검증 완료로 표시하지 않는다.

## 4. 연구 엔진 적격성 — 엔진과 알파를 분리

기존 checkout은 모두 tracked diff 없이 재사용했다: [engine_versions.json](../../runtime/task12/engine_versions.json). 네트워크 없는 기존 Docker image, CPU2/메모리4GB 제한, 원본·venv·체크포인트 read-only mount로 점검했다. 원본 전체 controller 실행과 구성요소/호스트 adapter 실행을 계속 구분한다.

| 엔진 / 고정 버전 | 이번 실제 확인 | Task13 사용 범위·미검증 |
|---|---|---|
| QuantaAlpha `b7ceb27…`, bundled RD0.8.0 | 원본 EvolutionController가 기존6개 trajectory 및 controller state 복원. proposal/DSL coder/feedback API import | 경제 메커니즘·horizon을 받은 custom Scenario로 원본 planner/evolution 사용 가능. 새 mutation/crossover 및 **full AlphaAgentLoop는 이번에 실행 안 함**. 기존 Task6/10 native 결과 재사용 |
| RD-Agent `484776c…`, 별도 RD1.0.0 | QlibModelHypothesisGen·원본 model coder import, 기존 학습 GRU checkpoint read-only forward `[2]` 유한 예측 | 원본 코딩/학습 연결 재사용. 이번 fit/retrain/full fin_quant 없음. Task10 worker의 고정 H5/GRU16을 팀3 전체 정책으로 사용하지 않음 |
| Qlib0.9.7 / PyTorch2.8 CPU | LinearModel ridge 생성, LGBModel import, GRU/GeneralPTNN import. 원본 calc_ic를 공통 adapter에서 실행 | 선형·트리·시계열 후보 가능. **학습 성공/성능은 Task13에서 확인**, import로 대체 안 함. CatBoost/XGBoost optional 의존성 미설치 상태 유지 |
| Vibe `0025531…` | 원본 registry478개 로드, alpha101_012/009 실제120×4 계산·미래 교란 prefix 불변. Research Lab run callable | 기존 PRE Lab 실행 재사용. 이번 Lab 경제성 재평가·전체478개 계산 없음. 라이브러리/연구 기록 도구이며 기본 우승 엔진으로 지정하지 않음 |

실행 근거: [Quanta probe](../../runtime/task12/qa_probe.json), [RD/Qlib probe](../../runtime/task12/rd_probe.json), [Vibe probe](../../runtime/task12/vibe_probe.json), [probe runner](../../experiments/task12/run_probes.py). checkpoint·모델 code hash는 RD probe에 있다. 기존 원본 증거는 [Task6 completion](06_research_completion_report.md)과 [Task10](10_adaptive_quant_walk_forward.md) 참조.

### Vibe 실제 입력 요건

AST로 metadata478개를 읽었고 parse 실패0: GTJA191 191, Qlib158 154, Alpha101 101, fundamental20, academic12. **478개의 독립 전략이 아니다.**

- OHLCV만 필요하고 추가 extras/sector 요건이 없다고 선언한 항목은 **368**. 시장 태그까지 적용하면 US218/KR206이다. 실제 warmup·결측·수식 검사를 통과한 전체 수가 아니다.
- 추가 요건에 VWAP43개·amount40개·sector22개 등이 있다. close나 임의 업종으로 대체하지 않는다. 시가총액·재무·미시구조·sentiment를 요구하는 항목도 별도 차단한다.
- metadata 수식 문자열의 동일 복사 추가분은 **26개**. 기간별/실행 코드가 다른 경우도 있으므로 동일 계산값이라고 단정하지 않는다. 신호 중복·상관은 Task13/14 계산 뒤 측정한다.
- `alpha101_012` finite476, `009` finite460 / 총480셀로 warmup 차이도 확인했다. 두 사례의 prefix 불변은 나머지476개의 누수 안전성을 보장하지 않는다.

[factor_catalog.json](../../runtime/task12/factor_catalog.json)에 항목별 columns/extras/warmup/universe/theme/원본 경로·hash를 남겼다. 478개 전체 backtest나 설치는 하지 않았다.

### 최초18개·후속 후보의 필요한 역할

명단은 [Task11 §3](11_research_architecture_audit.md#3-최초-18개-후보-복원)의 복원18개를 재사용하며 다시 채우거나 재설치하지 않는다. Qlib/RD는 연구·학습용, FinRL-Trading/ai-hedge-fund/skfolio는 실제 결함 발생 시 전략/배분 대조 후보, vectorbt/Lean/Nautilus/Freqtrade는 회계·기업행사·누수·이벤트 실행 대조 후보로 남긴다. EdgarTools/KIS/tossinvest는 데이터·브로커 도구, Pandera는 스키마, LangGraph/Temporal/Langfuse는 기반 도구다. FinRobot/TradingAgents 및 후속 투자 스킬4종은 기업 연구/반론/복기이며 이번 팀3 독립 알파 엔진으로 세지 않는다. Hermes는 선택적 기억/위임, FinRL-X/EvoQuantLab 등의 후속 후보는 별도 미검증이다.

추가 도입 우선순위는 **① 필요한 종목의 기업행사·역사 membership 근거 ② 발표/개정 시각이 있는 정량 재무·거시 입력 ③ 기존 엔진으로 해결되지 않는 특정 기능**이다. 지금 새 엔진·서비스를 도입할 필수 사유는 없다. 재무·거시·수급 알파는 정렬된 vintage 입력이 없으므로 현 단계 `PARTIAL`이고, OHLCV의 추세·반전·변동성/유동성 연구는 가능하다.

## 5. Task13~15 공통 평가 연결

[evaluation.py](../../experiments/task12/evaluation.py)는 기존 label 계산, 원본 Qlib `calc_ic`, Quant `investment.research.replay_targets/metrics` 및 V77 ExecutionSpec을 연결한다. 기존 성과/평가 버전을 다시 쓰지 않는다. Task12에서는 합성 fixture의 연결만 검사했고 실제 후보 전략 수익은 산출하지 않았다.

| 계층 | 고정·분리할 것 | 지표·진행 조건 |
|---|---|---|
| L1 순수 예측 | 같은 source/session hash·적격 mask. 현금·위험·비중 없음. 각 가설 primary horizon 고정 | Pearson IC/Spearman RankIC/분위 spread·시장/산업 상대수익. 겹치는 label의 block/HAC 불확실성·유효 날짜/종목 수. ICIR을 무조건 √252 연율화하지 않음 |
| L2 팀3 단독 | 후보의 원래 horizon/정규화/선정·비중·거래주기 사전 고정, 기존 targets 실행 | gross/net·회전율·노출·현금·MDD·집중. 균등/MOM63/추세 및 같은 실제 노출의 지수+현금 대조. top4/H5/당일 청산을 강제하지 않음 |
| L3 위험 증분 | 같은 L2 신호와 비용 유지. 기존 MA63 위험 gate 유무 + **risk-only 기준선** | 현금 회피·상승장 기회비용·종목 선택·체결/비용을 별도 기여로 보고. 위험을 낮춘 성과를 알파로 세지 않음 |

연구 S 횡단면 대조의 제안은 생성 전 N/k/cap/기권 슬롯·80% 목표노출을 봉인하는 것이다. Task11의 **B 전용 상위20%·최소10종목/N≥50** 규칙을 S에 억지 적용하지 않는다. native 전략 평가와 공통 매핑이 다르면 둘을 보존하고 작은 동일 입력의 parity로 차이를 설명한다. 이벤트·시계열 후보에는 IC를 필수 primary로 강제하지 않는다. 기존 예측 오차·방향성/zero·linear 대조를 활용하고, 실제 사건 입력이 없으면 해당 track은 보류한다. 현재 thin IC adapter는 다른 alpha_kind를 명시적으로 거부한다.

비용은 기존 [Task3 시장별 가정](../../config/task3_equity_contract.json)을 재사용한다: 미국 매수/매도1bp, 한국1.5/21.5bp, 양쪽 half-spread5bp·impact10bp at1% ADV/최대50bp·D-1 ADV참여율1%. **실제 최신 세율·브로커 tariff·실측 spread라는 주장이 아니다.** 새 관측 근거는 별도 track으로 사전등록한다. gross/net은 동일 체결 비용 addback인지 비용0 재생인지 표시한다. 0/0.5/1/2배 비용 민감도는 진단이며 기본비용 실패를 덮지 않는다. 미국USD/한국KRW 계좌를 분리하고 ETF는 거래 알파가 아니라 비교용으로 쓴다.

미국 S&P500·한국 KOSPI가 기본 지수다. SPY/KODEX200은 대용/투자 가능 기준선으로 별도 표시하고, 배당 포함 ETF와 가격-only 종목/지수를 섞어 우열 판정하지 않는다. 산업 ETF·직접 경쟁군은 성과를 보기 전에 관련성·당시 적격성으로 지정하며 자료가 없으면 N/A다.

### 실패·재검증·선택 편향

Task11의 후보 전체 family 원장·Holm FWER5%·의존성 반영95% 구간·primary/secondary 분리를 유지한다. candidate generation/seed/모델/매핑 실패·중복·조회 이력도 예산/시도에 포함한다. 작은 S에서는 통계적 증거 부족이 정상 결과이며 후보 유지와 투자 우위 확증을 구별한다. PBO/DSR/CPCV는 필요한 전체 행렬·탐색/분할 이력이 있을 때만 검토하고, 도구를 사용했다고 자동 통과하지 않는다.

| 관측 | 다음 조치 |
|---|---|
| 예측력이 부족 | 다른 알파·특징량·모델 가설. 현재 한 후보의 실패를 엔진 전체로 일반화하지 않음 |
| 예측력은 있으나 net 부진 | horizon 정합성·회전율·비용/매핑 연구를 별도 후보로 |
| 하락장에서만 우수 / 상승장 불참 | 동일 노출·risk-only 대조로 신호와 현금 기여 분리 |
| 모델 성능 저하 | 충분한 drift 근거 후 재학습/모델 변경 후보 |
| 자료·시점 오류 | 원본·기존 결과 보존, 버그 수정과 전략 변경 분리, 새 평가 버전 |
| 불확실성 큼 | 추가 독립 관측, `INSUFFICIENT_EVIDENCE`; 사후 최고 horizon 선택 금지 |

Task17의 `TEAM3_STANDALONE`과 `TEAM3_WITH_FEEDBACK`은 같은 초기 신호/위험/비용에서 시작한다. 이번에는 피드백 경제성·재학습·교체를 실행하지 않았다.

## 6. Forward 장애 확인과 최소 복구

### 재현한 문제와 수정 범위

원본 `market_tick`은 수집 전에 attempt를 쓴 뒤, 같은 attempt가 있으면 재진입을 막았다. 수집 ConnectionError 후 두 번째 호출이 수집을 재개하지 못하는 실패를 [교정 전 재현 로그](../../runtime/task12/attempt_reproduction_confirmed.log)에 남겼다.

수정은 [기존 forward.py](../../experiments/task10_1/forward.py)에 한정했다. 새 Queue/스케줄러·모델·위험 규칙은 없다.

1. immutable attempt를 유지하면서 수집을 재개하고, accepted snapshot이 있으면 hash를 검증해 재사용한다.
2. 이미 봉인한 계획·부분 커밋된 계좌가 있으면 관측/복기 완료 단계만 이어간다. 완료 marker를 별도로 append하고 기존 NAV/fill은 바꾸지 않는다.
3. 공급자 달력·기존 봉인 next_session·accepted session을 합쳐 누락 세션을 확인한다. 확인 가능한 중단 구간은 늦은 관측 receipt로 저장하고 기존 봉인 계획만 replay한다. 사후 신호·위험 결정을 만들지 않는다.
4. 공식 완료 세션을 증명할 수 없는 장기 공백은 `FAILED_CLOSED`다. 평일 추정으로 채우지 않는다. 이전 복구 최대4건/호출로 제한하며 backlog를 남긴다.
5. 이미 봉인한 동일 날짜 Review는 재사용하여 재시도마다 약화 횟수/후속 요청이 늘지 않게 했다. 기존 source revision gate와 동시 실행 lock은 유지했다.

초기 계약은 observer 소스 hash까지 봉인했다. 단순히 새 hash로 초기 계약을 덮어쓰지 않고 [forward_patch.json](../../runtime/task12/forward_patch.json)에 사용자 Task12§7의 기술 수정 근거·이전/이후 hash·초기 계약 hash를 기록했다. [원본 bytes](../../runtime/task12/forward_before.py)를 보존하고 **choose/compute/validate_revisions/settle/process_seals의 AST 동일성**을 강제한다. 다른 모델/정책 source가 바뀌면 여전히 차단한다. 기존 manifest의 한 불일치는 이 명시적 기술 수정으로 남기며 과거 manifest를 재작성하지 않았다.

### 실제 관측과 남은 한계

[수동 정상 tick](../../runtime/task12/patched_observer_tick.log)은 US/KR 모두 `WAIT_NEXT_COMPLETED_SESSION`, 다음11/16, network0·fill0·LLM0·Factory0이었다. [기존 systemd 정상 호출 로그](../../runtime/task12/scheduler_readonly.log)에서도 같은 결과를 확인했다. 초기11/13 bootstrap의 완료 receipt만 추가됐고 역사 가격을 Forward NAV로 넣지 않았다. 타이머를 중단/교체하지 않았다.

재시작·부분 커밋·누락 세션·변조·멱등성은 **격리 장애 fixture**에서 검증했다. 실제11/16 정규장 완료 후 수집/체결·다음 주 성숙 IC·장기 장애 복구·실제 서버 재부팅은 이번 시점에 미검증/PENDING이다. 공식 달력 이력이 없는 긴 공백은 자동 복구 성공 대신 차단이 정상이다. 기존 prospective native 연구 executor 공백도 남으며 이번 범위에서 새 executor를 만들지 않았다.

## 7. 시험·보존·자원

| 이번 실행 | 결과 | 증거 |
|---|---|---|
| AGENTS 필수4+운영5 suites | **53 PASS**, fail/error/skip0 | [XML](../../runtime/task12/safety_tests.xml), [로그](../../runtime/task12/safety_tests.log) |
| 기존 Task10.1 Forward12 + 새 복구5 | **17 PASS** | [XML](../../runtime/task12/recovery_tests.xml), [시험](../../experiments/task12/test_forward_recovery.py) |
| label·누락·국면·typed metric·기존 실행3arm | **5 PASS** | [XML](../../runtime/task12/readiness_tests.xml), [시험](../../experiments/task12/test_readiness.py) |
| compileall src/scripts/tests + 변경 experiment | PASS | [로그](../../runtime/task12/compile.log) |
| 기존 V104 forward session 명령 | `NO_ENABLED_CANDIDATES`, append0, Live false | [로그](../../runtime/task12/v104_forward.log) |
| 네이티브 대표 probe3개 | exit0; 구성요소 실행만 | [상태](../../runtime/task12/probe_status.json) |

합계 **75개 최종 시험 통과**. 기존 데이터 종료≤7/3일 때 기대하는 `NO_NEW_SESSION_AFTER_V104_FREEZE` 문구를 이번 결과로 꾸미지 않는다. 실제 결과는 위와 같다.

초기 실패도 있었다: 재현 fixture의 임시 root 경로 오류 후 실제 attempt 결함 재현, recovery fixture의 정책 파일 누락, ExecutionSpec fixture 인자 누락을 교정했다. RD 최초 실행은 `/log` 쓰기 권한 오류, 공통 spread 시험은 4종목 fixture가 최소8 조건을 못 채워 실패했다. 격리 작업 디렉터리/10종목 fixture로 교정했으며 알파/전략/의존성을 바꾸지 않았다. [권한 실패](../../runtime/task12/rd_probe_permission_failure.log), [소표본 fixture 실패](../../runtime/task12/rd_probe_small_fixture_failure.log), [초기 평가 시험 실패](../../runtime/task12/readiness_tests.log)를 보존했다. 초기 litellm import의 cost-map DNS 시도는 network-none에서 실패했으며, 이후 로컬 cost-map 설정으로 차단했다. 시스템 `python` 명령도 없어 실행기를 `.venv/bin/python`으로 고정했다. 이 실패들을 최종 통과 횟수에 숨겨 합산하지 않았다.

[preservation.json](../../runtime/task12/preservation.json): Task6 completion922/Task10 2,339파일 hash 전부 일치. Task10.1 840개 중839개 일치, 나머지1개는 위 기술 수정 observer이며 원본 bytes/hash와 초기 계약·과거 계획/계좌는 일치한다. 운영 Factory·Paper·Live·팀2를 수정하지 않았다. Git의 기존 tracked5파일 diff도 유지했다. 원본/실패/모델을 삭제하거나 새 checkpoint를 복사하지 않았다.

데이터 요청0/300, LLM0, 학습0. CPU4시간은 목표 상한으로 사용했고 제한된 원본 probe/검사만 수행했다. 전체 세션 누적 CPU 계측기는 없으므로 CPU 사용량을 임의로 정밀 산출하지 않는다. 개별 pytest시간은 XML, 각 native 실행은 로그에 남겼다. 새 파일/bytes/hash 목록은 [최종 manifest](../../runtime/task12/artifact_manifest.json)에 기록한다. 공유 fit CSV 두 개 외에 전체 데이터 복사본을 만들지 않았다.

### 재현 명령

```bash
PYTHONPATH=src .venv/bin/python experiments/task12/readiness.py
PYTHONPATH=src .venv/bin/python experiments/task12/prepare_inputs.py
PYTHONPATH=src .venv/bin/python experiments/task12/run_probes.py
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q \
  experiments/task12/test_readiness.py experiments/task12/test_forward_recovery.py \
  experiments/task10_1/test_forward.py
.venv/bin/python experiments/task12/preservation.py
```

`patch_forward.py`은 원본 hash에서만 동작하는 일회성 기술 수정 도구다. 현재 수정본에 재실행하지 않는다. 위 probe는 가설/학습/네트워크 호출 없이 기존 환경에서만 수행한다. AGENTS 9개 회귀 suite의 정확한 목록은 AGENTS.md와 safety XML에 있다.

## 8. Task13 착수 범위와 게이트

1. **같은 fit 입력과 격리 평가 경계**에서 OHLCV 추세·반전·변동성/상대 거래량 등 최소3개 메커니즘을 사전등록한다. H5/H20의 제한 S부터 시작한다. H60·장기 warmup·외부 특징은 별도 적격성 관문을 통과한 경우만 사용한다.
2. Quanta 원본 가설/진화와 RD 원본 특징/선형·트리·시계열 연구를 엔진별 별도 경로로 실행한다. Vibe는 기존 팩터 대조/Research Lab·기록 재사용으로 참여하며 선행 우승 엔진이 아니다. native 전체 제어기와 component+adapter/host 선택을 기록한다.
3. Task11 1차 상한을 유지한다: **최대12 unique 후보**(library4, Quanta original/mutation/crossover 목표5, RD 최대3). 경제 메커니즘과 적격성에 따라 미달할 수 있고 수를 채우지 않는다. 실패·중복·하위 호출도 전체 시도/예산 원장에 포함한다.
4. **Quanta≤24 calls/900k tokens, RD≤12/500k, Vibe 기본0(필요시≤4/160k)**, CPU2~4·메모리4~8GB, 총CPU24h 목표. Terra는 중요한 연구/코딩, Luna는 검증된 정리만 사용한다. 실제 호출 전 잔여 예산·모델 정책을 확인한다. 이번 Task12에서 이 예산을 소비하거나 다음 연구를 실행하지 않았다.
5. Task13은 생성/실행/학습/원본-공통 평가 의미 대사, Task14는 순수 예측력, Task15는 사전 고정 매핑의 비용 후 경제성이다. 실패 시 문제별 입력/가설/모델/실행 단계로 돌아간다. 피드백 없이도 팀3 단독 전략이 성립해야 한다.

**착수 허용:** 한정된 S 가격/거래량 기반의 다양한 native 후보 연구. **착수 불가/별도 보완:** B 일반화, PIT 재무·거시 횡단면 알파, 검증되지 않은 기업행사를 포함한 확증 경제성, 새 독립 Holdout 주장, 자동 Champion/Live 승격. 현재 Forward 관측은 병행 유지한다.

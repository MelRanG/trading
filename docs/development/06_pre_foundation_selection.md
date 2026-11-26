# Task 6-PRE — Vibe-Trading 기반 실사 및 선정

## 1. 핵심 결론

**최종 추천: `HYBRID_MINIMAL`. Vibe-Trading을 향후 연구·분석 작업자의 주력 재사용 기반으로 삼고, Quant Harness에서는 시점별 입력 보존·공식 Factory 승인·주식 Paper 원장·결과를 숨긴 복기의 필수 경계만 유지한다.** 이번 단계에서는 운영 시스템을 이전하거나 원장을 바꾸지 않았다.

선정 이유는 다음과 같다.

1. Vibe 원본의 Alpha Zoo, 원본 백테스트, 비용 민감도, 잠긴 train/select/test/holdout, 가설·목표·연구 revision 보존이 실제 실행됐다. 이 기능을 Quant 안에서 다시 만드는 개발은 중단하는 편이 낫다. 원본 선별 시험 **683 passed**, 독립 실행기에서 US/KR 백테스트 및 연구 상태의 새 프로세스 복구를 확인했다.
2. 원본의 연구 폭과 투자 우위는 별개다. 사전 고정한 원본 팩터 1개를 동일 위험·비용으로 평가했을 때 US **+10.001%**, KR **−47.331%**였다. 기존 MOM/균등 비중보다 낮았다. 이 결과는 그 팩터와 명시한 포트폴리오 매핑의 진단이며 478개 팩터·전체 연구 시스템의 성능을 대표하지 않는다.
3. 원본에도 SQLite 트랜잭션·revision 충돌 방지·원장 검산이 있다. 단순 데모로 치부할 근거는 없다. 다만 현재 주식 Paper의 시각/체결 계약, 독립적인 과정 봉인과 성숙 라벨, 운영 승인 권위까지 옮겨도 같다는 실증은 없다. 전체 전환의 이점과 이식 비용을 아직 증명하지 못했다.
4. **한국 미지원은 선정 이유가 아니다.** 원본에는 KoreaEquityEngine이 있고 기존 Toss snapshot을 실제 읽어 한국 백테스트를 완료했다. 한국 자료 수집기는 재사용 가능하다. 남는 문제는 데이터 관측 시점·조정주가·Paper 계약의 호환 비용이다.
5. 외부 전문 에이전트는 증분 효과가 입증될 때만 추가한다. Vibe 자체의 가치평가·위원회·연구 관리와 겹치는 기능을 먼저 재개발하지 않는다. 추가 에이전트의 실제 A/B, 원본 LLM 투자 분석 품질, 독립 Forward 초과수익은 **미검증**이다.

구성 A(전면 전환)는 원본 독립 실행으로, B(Quant 중심)는 원본 팩터→기존 공통 실행으로, C(최소 통합)는 동일 결과→해시가 고정된 권한 없는 제안 경계로 시험했다. **C의 최소 경계 실증이며 C 전체를 운영 배포한 결과는 아니다.** 가중 점수 합산으로 승자를 만들지 않았다.

## 2. 고정 원본·설치·실행

공식 원본: [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading). 분석 대상 [main 커밋](https://github.com/HKUDS/Vibe-Trading/tree/0025531f005d4a7aac3fb884cda2fba9318e7158)은 `0025531f005d4a7aac3fb884cda2fba9318e7158`, 2026-11-12T23:34:46+08:00이다. 최신 안정 [v0.1.19](https://github.com/HKUDS/Vibe-Trading/releases/tag/v0.1.19)는 `cb99dca528695ffe78429483a90399a89f61d614`, 2026-11-05 공개이며 main에는 이후 커밋 99개가 있다.

| 항목 | 안정 릴리스와 main 차이/이번 범위 |
|---|---|
| package version | main도 0.1.19로 표기하므로 버전 문자열만으로 구별 불가. 이번 설치는 **고정 main의 로컬 wheel**, PyPI 안정 바이너리 실측이 아님 |
| Research Lab | `agent/src/research_lab/service.py`는 안정 태그에 없음. main에서 동결 비용 재실행·walk-forward·holdout 제공 |
| Paper reconcile | `agent/src/tools/paper_trade/reconcile.py`는 안정 태그에 없음. 11월 main에서 독립 Decimal 원장 검사 추가 |
| 연구 revision/Korea engine | 안정 태그에도 존재. main에서 revision 비교·export 및 관련 오류 수정 추가 |
| 11월 수정 | 기간 경계·warmup·출력 target 중복 지연·부분 체결·Shadow 초기자본·truncated 응답 완료 판정 등. 목록/통계는 `main_since_release.log/.stat` |
| 안정 태그 실행 | 이번에는 별도 설치·실행하지 않음. 안정/main 소스 존재·diff 비교와 main 실행을 구분 |

원본 checkout: `/home/ansy/app/quant-diligence/vibe-original`(detached, 변경 0). 별도 venv: `vibe-env` 약 **1.1 GB / pip freeze 188 entries**. Quant .venv 약579 MB와 목적·의존성 범위가 달라 이 크기로 효율 승자를 정하지 않는다.

최초 read-only checkout 설치는 setuptools egg-info 작성 때문에 실패했다. 코드 수정 없이 별도 빌드 사본에서 설치해 성공했다. 설치 종료 전 시작한 첫 CLI probe의 not-found는 실사 순서 오류였다. 종료 확인 후 실제 CLI/Alpha Zoo/Research Lab이 성공했다. 실패 로그도 보존했다.

- 원본 CLI `--help`, `alpha list`(478개 catalog), `research-lab --help`: 성공.
- pip check: `No broken requirements found.`
- 원본 16파일: **412 passed / 203 warnings / 76.97초**. 가격/상태를 fixture로 주입한 시험 포함.
- PaperAccounts·GoalStore·ResearchArtifactStore: **70 passed / 5.08초**.
- 원본 valuation 디렉터리: **201 passed / 2.31초**.
- 합계 **683 passed**, 실패/스킵 0. 전체 upstream suite·프런트엔드·실거래를 시험한 수치는 아니다.

실행은 기존 python:3.12-slim의 user1000, cap-drop ALL, no-new-privileges, memory3G/CPU2/PID256 컨테이너에서 했다. 설치 단계만 패키지 다운로드 네트워크를 허용하고, 시험·원본 실행은 **network=none**이었다. 운영 repo/DB·Docker socket·`.env`·Codex 인증 폴더를 mount하지 않았다. 입력은 공개 가격의 별도 파일 snapshot이었다.

증거는 `runtime/task6_pre/evidence/versions.json`, `environment.lock`, `install_*`, `cli_help.log`, `upstream_{selected,state,valuation}.{log,xml,exit}`다. 원본 checkout/설치 환경과 증거를 재사용하면 완료 시험을 불필요하게 반복할 필요가 없다.

## 3. 7개 영역 — 주장과 실제 검증 수준

표의 **코드**는 구현 경로 확인, **시험**은 이번 원본 fixture 시험 통과, **실행**은 이번 고정 실제 가격/원본 모듈 실행, **미검증**은 실행/효능 증거 부족을 뜻한다. README의 저자 자체 성과표나 SPY/GLD fill 검산 주장은 이번 결과에 합산하지 않았다. `V/`는 고정 Vibe checkout, `Q/`는 현재 Quant repo를 뜻한다.

| 영역·주요 기능 | Vibe 원본의 실제 경로와 이번 증거 | Quant의 실제 경로와 차이 |
|---|---|---|
| 1. 가격·유니버스·외부 자료 | **코드:** `V/agent/backtest/loaders/{registry,local_loader,yfinance_loader,sec_frames,tushare_fundamentals,rsshub_events}.py`. Yahoo/SEC/뉴스 등 존재. **실행:** local CSV로 US/KR 입력 성공. 공개 제공자 실패·rate-limit·비용은 제공자별 구현이며 이번 외부 API 실측 없음 | `Q/investment/operations_data.py`(경로 접두사는 src/quant_harness): 최초 관측·원문 hash·revision 차단·수집/HTTP 예산. 실제 Toss는 Task5 근거 재사용. 전체 시장 PIT 생애주기는 양쪽에서 이번 미검증 |
| 신규 종목 발굴/기업 탐색 | skill·screening·swarm **코드**, LLM 자동 발굴 **미검증**. catalog와 factor universe가 실제 동적 발굴 성공을 뜻하지 않음 | bounded catalog/관심목록, A 신규 가격 적격성은 기존 Task5 실측. 기업 탐색 깊이·새 사실 증분은 미검증 |
| 2. 기업가치·수치 예측 | `V/agent/src/quantlib/valuation/{dcf,contracts,threestatement,comps,artifact}.py`: 필수 가정·basis·현금흐름·가치 bridge, **시험 201개**. `financial_research_artifact_tool.py`, financial-statement/valuation-model skills **코드**. 실제 기업의 전망 정확도 **미검증** | `Q/investment/{discovery,valuation}.py`: 제한 RSS/스킬·검산·기권. Task3 실제 Terra 코멘트는 있으나 구조화 원본 예측·실현 오차 부족. Vibe의 확장 valuation을 다시 만들 이유는 약함 |
| 독립 bull/bear·분석팀 | `V/agent/src/swarm/presets/{investment_committee,fundamental_research_team,equity_research_team,...}.yaml` 및 swarm 실행 코드. 일부 preset은 upstream_context를 순차 공유하므로 최초 판단 독립성은 preset별 별도 통제 필요. 원본 multi-LLM 실행은 **미검증** | 회사/퀀트 첫 입력 분리 및 회사 판단 비실행 경계 존재. 양쪽의 분석 품질 우열·동일 모델 A/B는 미검증 |
| 3. Alpha Zoo·팩터 | Registry AST catalog/lazy import, qlib158/alpha101/gtja191 등. **실행:** alpha101_012 원본 계산, 독립 식 오차0, 미래 원문 변형 후 과거 출력 불변 | 기존 고정 MOM/DEF·균등 비중과 공통 실행 가능. 478개 전부의 수학/수익 검증을 이번 한 팩터 결과로 대체하지 않음 |
| Walk-forward·비용·OOS | `V/agent/src/research_lab/{execution,studies,service}.py`: snapshot/strategy/config hash, train selection→선택 봉인→test/holdout. **시험:** `test_research_lab_execution.py`. **실행:** 2개 고정 비용 scenario 완료. 시장 국면 정책은 별도 연구 코드·skills이며 효능 미검증 | `Q/investment/operations_experiment.py`는 제한 adapter. 전체 연구 UI/비용·WF 기능을 새로 만드는 것보다 Vibe reuse 유리 |
| 생성 코드·연구 Autopilot | `V/agent/src/tools/autopilot_tool.py`: goal 생성, config/scaffold, run-card link; `strategy_discovery/`와 hypotheses·goal 런타임. **실행:** 수동 사전고정 가설→goal→원본 backtest link→새 프로세스 복구. LLM의 자율 가설 생성·코딩·반복 개선은 **미검증** | Factory의 예산/중복/사전등록/결과 해시는 실제 동작. 구현된 worker 종류는 좁고 연구 능력 자체를 증명하지 않음. 공식 승인과 연구 작업자의 편의 상태를 분리 |
| 4. 포트폴리오·위험 | 원본 BaseEngine/optimizers/constraints·다시장 엔진 **코드**, native US/KR 원본 runner **실행**. 기본 비용·수량·가격 제한이 서로 다름. 원본 factor와 공통 target의 mismatch0 | stock_targets의 고정 .2/name·.8 gross, D1 sizing. USD/KRW 별도 계정. 전세계 자본 통합·최적 전략은 미검증 |
| 5. Paper·대사·장애 | `V/.../paper_trade/{engine,accounts,state_hash,reconcile,corporate_actions,order_lifecycle}.py`. **시험:** determinism, fees/NAV, SQLite transaction·optimistic revision, 중단/동시성. daily saved account는 주로 cn_a/hk/us, 5m lifecycle은 A-share 중심. Korea backtest와 Korea saved Paper 지원은 구별 | `Q/investment/stockpaper.py`: 다음 fresh regular quote, 원자적 fill/cash/position/NAV·고정 ID·복구·코드 버전 veto. 기존 1건 KR Paper/복원 증거. 이번 외부 원본에 기존 원장을 전달하거나 양쪽 운영 계정으로 같은 주문을 발행하지 않음 |
| 기업행사·거래일·실시간 | Vibe paper corporate action 관련 **시험/코드**와 KRX tick·limit code 존재. 여러 broker/실시간 통합 **코드** 있으나 이 실사에서 WebSocket·실시간·분할/배당 전체 정확성 **미검증** | 공식 세션 adjacency·stale fail-closed는 기존 실증. split·배당 현금 원장 미완성. native 쪽이 상세한 시장 모델을 갖춘 부분도 있음 |
| 6. Shadow·매매 복기 | `V/.../shadow_account/extractor.py`: 이익 roundtrip의 clustering/규칙 추출; `backtester.py:_compute_attribution`은 반사실 PnL 분해이며 missed-signals는 residual. **원본 fixture 시험** 통과, 실제 손실 원인 판별 정확도 미검증 | `Q/investment/review.py`, review_engine: 당시 packet으로 과정 먼저 봉인, 사후 성숙 라벨 후 평가. 현재 오류 검출은 주로 provenance/규칙 감사이며 실제 미래 예측·경제적 원인 정확성 미검증 |
| 7. 장기 연구·자기개선 | hypotheses JSON, GoalStore SQLite, research artifact immutable revision, sessions/scheduled research **코드/시험**. **실행:** 동일 revision 중복 차단·새 process 검색/goal 회수. saved content가 verified/fresh라는 보증은 별도 | Factory 한 공식 사전등록/예산·holdout/proposal 경계, review queue lease·재시도·PENDING 기록. 이 기능을 제안자 작업 메모리와 동일 권위로 합치지 않음 |
| 지속 자동 운영 | Vibe schedules/worker/swarm 복구 관련 **코드·선별 시험**. 외부 main을 상시 서비스로 배포한 실측은 없음 | 기존 단일 user timer·PG 재시작/복원·실제 tick은 Task5. Task5 성숙/예산 갱신 대기는 계속 기존 흐름이 담당. 이번 판단에 완료로 가산하지 않음 |

원본 Paper의 `reconcile.py`는 수수료·현금·포지션·NAV 산술을 Decimal로 재생하지만 시장 가격 자체, stable order id 없는 중복 fill, 전체 fingerprint를 입증하지 않는다고 명시한다. 원본 saved account는 revision 비교와 transaction으로 별도 보호한다. 이 범위를 분리해 평가해야 한다.

Quant도 아직 독립적 경제 원인 oracle이나 검증된 투자 우위를 갖추지 못했다. 비교의 근거는 각 역할의 실행/계약/공백이며 익숙한 코드에 대한 가산점은 없다.

## 4. 동일 입력 백테스트·Paper/복기 검산

### 동결·사전등록

`experiments/task6_pre/export_inputs.py`가 Task3 원본 파일만 읽어 공개 가격 CSV를 export했다. 사전등록 hash는 `c1cc808b8e34a0c5b288fba517ecbc5a125a173d5803df58bb8bd5a42d39bd72`. 종목·기간·비용·초기자본·후보와 mapping을 결과 전에 고정했다. 파라미터 탐색 0, LLM/새 외부 API 0.

- US: 기존 8개 seed, 2022-05-09~2026-11-11, 1,133세션, USD100,000.
- KR: 기존 6개 seed, 2021-08-18~2026-11-12, 1,280세션, KRW10,000,000.
- 원본 팩터: `alpha101_012 = sign(Δvolume) × (−Δclose)`. 양수 top4×20%, 나머지 현금, D1 신호. **원본 팩터 + 이번에 명시한 mapping**이며 Vibe의 공식 추천 수익 전략이 아니다.
- Task5의 BLOCKED Factory 실험은 이 별도 사용자 승인 실사 PoC 결과로 완료 처리하지 않았다. 공식 연구 원장에 이번 실험을 대신 기록하지 않았다.
- 공통 replay: 기존 Quant `replay_targets`, 동일 D1 NAV/가격 sizing, 다음 open, 정수 수량, 수수료/스프레드/D1 ADV 충격·참여율·최소 주문. 벤치마크는 연구 비교용 ETF 보유만 모의하며 운영 ETF 주문을 활성화하지 않았다.

### 같은 실행·위험·비용 결과

#### US

| 후보 | 순수익 % | Sharpe | MDD % | 회전/초기자본 | 비용(USD) |
|---|---:|---:|---:|---:|---:|
| MOM63_STOCKS | +157.187 | 1.305 | -14.526 | 241.07 | 15,156.91 |
| DEFENSIVE_STOCKS | +151.593 | 1.312 | -15.002 | 223.52 | 14,047.34 |
| EQUAL_WEIGHT_STOCKS | +263.371 | 1.233 | -27.490 | 24.56 | 1,481.64 |
| VIBE_ALPHA101_012 | +10.001 | 0.212 | -32.651 | 880.06 | 54,857.39 |
| BENCHMARK_HOLD_0.8 | +77.904 | 1.001 | -15.994 | 0.79 | 48.17 |
| BENCHMARK_HOLD_1.0 | +97.568 | 0.998 | -18.571 | 0.98 | 60.48 |
#### KR

| 후보 | 순수익 % | Sharpe | MDD % | 회전/초기자본 | 비용(KRW) |
|---|---:|---:|---:|---:|---:|
| MOM63_STOCKS | +27.268 | 0.331 | -35.265 | 91.32 | 1,532,246.88 |
| DEFENSIVE_STOCKS | +32.450 | 0.379 | -29.638 | 77.06 | 1,291,868.46 |
| EQUAL_WEIGHT_STOCKS | +117.782 | 0.710 | -38.308 | 21.56 | 352,844.74 |
| VIBE_ALPHA101_012 | -47.331 | -0.681 | -50.775 | 453.42 | 7,587,280.40 |
| BENCHMARK_HOLD_0.8 | +100.367 | 0.623 | -44.111 | 0.80 | 5,694.90 |
| BENCHMARK_HOLD_1.0 | +125.223 | 0.655 | -46.877 | 1.00 | 7,178.90 |

균등 비중은 기존 seed 첫 4종목×20%의 일일 재배분이다. 전체 시장의 분산 균등 포트폴리오가 아니다. 벤치마크 80/100%는 최초 목표 후 drift를 허용해 주식 전략의 일별 총노출과 항상 같은 위험은 아니다. Sharpe는 기존 동일 정의이며 무위험 0·252일 기준이다.

기존 MOM/DEF/균등 수익은 원본 Task3 결과와 1e-6%p 이내로 재현했다. 비용 후 Vibe 팩터의 높은 회전과 비용을 기록했고, 성과가 낮다고 임계값이나 holding period를 고치지 않았다. 공통 US ETF 수익은 예전 독립 audit와 차이가 난다. 예전 audit는 최초 open으로 수량/예산을 잡았고 이번은 모든 경로에 같은 D1 close sizing을 적용했기 때문이다(`scripts/audit_equity_comparison.py:64-68`). 기존 성과 파일은 수정하지 않았다.

### 원본 실행과 산술 검산

| 항목 | US 원본 native | KR 원본 native |
|---|---:|---:|
| 비용 후 native 수익 | +22.0221% | −68.2173% |
| fills | 5,914 | 3,739 |
| 원본 기록 fee | 0 USD | 4,204,031.355 KRW |
| fills→현금/수량→close NAV 독립 최대 오차 | 2.33e−10 | 1.86e−9 |
| native vs 공통 target 최대 차이 | 0 | 0 |

신호/시점/종목 target은 일치했다. 수익 차이는 실행 계약 차이다. 원본 미국 native `GlobalEquityEngine.calc_commission`은 0, 소수점 0.01 share를 지원한다. 원본은 opening event sizing/rebalance, 고정 slip·KR tick/가격 제한을 사용하고, 공통 replay는 D1 sizing·정수·최소 주문·ADV 충격 등을 사용한다. 이 차이들의 개별 기여를 파라미터 재탐색으로 분해하지 않았다. **native 결과와 공통 결과를 같은 비용의 전략 우열로 섞지 않는다.**

`inspect_native.py`가 native fills를 별도로 합산해 NAV를 확인했고 `common_comparison.py`도 모든 공통 결과의 현금/NAV를 재구성했다. 원본 factor 독립 식 오차0, 원본 raw 미래 close/volume을 변경해 다시 계산해도 cutoff 이전 값은 불변이었다(`causality.json`). 한 팩터의 인과성 시험이며 전체 생성 코드/모든 팩터의 누출 방지 인증은 아니다.

Paper/Shadow는 원본 golden·fee·determinism·revision conflict·조건/시간창·동일 cache key 시험을 실제 실행했다. Quant의 기존 Paper 수치와 복구 근거는 Task3~5 결과를 재사용했다. 양쪽 Paper의 체결 시각/가격 계약이 달라 기존 원장을 보내 같은 주문을 양쪽에서 실행하지 않았다. **운영 Paper의 거래별 동등성·실제 독립 복기 정확도는 미검증**이다.

현재 survivor 소표본과 반복된 역사 구간의 결과이므로 독립 알파 검증·통계적 승격 근거가 아니다. QH 기존 전략의 우위가 미래에 지속된다고 해석하지 않는다.

## 5. 연구 워크플로·분석 인증의 확인 범위

원본 Research Lab 비용 연구는 base와 사전 고정 adverse(수수료 2배·추가 slip 5bps) 2개 scenario를 실제 완료했다. source config/code/price hash를 확인해 동결하고 별도 trial에서 재실행했다. 두 시장 원본 runner·가설/비용 시연을 포함한 PoC는 약25.224초였다. 추가 70개 상태 시험과 201개 valuation 시험은 별도 시간이다.

가설 `hyp_d296232a093d` → goal `goal_e7421774ac07` → 원본 US backtest link를 저장했다. 최초 harness가 존재하지 않는 Registry.get을 호출해 마지막 요약에서 실패했지만 원본에는 link가 저장돼 있었다. 전체 실험을 다시 만들지 않고 새 process에서 Registry.list/GoalStore로 회수했다. 이후 artifact를 동일하게 두 번 저장한 결과 같은 `ra_4fe677eac96b_r1`, 두 번째 created=false, reopen 검색1건, verification_status=unverified였다. 이 실사 오류는 원본 결함으로 집계하지 않았다.

이 흐름의 가설·adapter는 사람이 고정했고, goal은 active 상태다. **LLM이 스스로 좋은 가설을 발견하고 코드를 생성해 개선을 완결한 증거는 없다.** 시험의 loop/scaffold·검산 통과와 경제적으로 유효한 연구 성과를 구별한다.

원본은 [Codex native provider](https://github.com/HKUDS/Vibe-Trading/blob/0025531f005d4a7aac3fb884cda2fba9318e7158/agent/src/providers/openai_codex.py)를 제공한다. 코드상 Vibe 소유 token storage와 `import_codex_cli=False`로 기존 CLI의 rotating refresh token을 가져오지 않는다. 무인증 원본 CLI를 실제 호출한 결과 local CodexAuthenticationError/401 형식의 `not logged in`, exit1로 실패했다. 서버에서 401을 수신했다는 뜻은 아니며 컨테이너는 무네트워크였다. 별도 `provider login openai-codex` 인증과 해당 계정의 모델 제공 여부는 미검증이다. 기존 개인 인증을 공유하거나 별도 유료 API 결제를 하지 않았다.

따라서 원본 투자위원회·LLM 기업분석·동일 모델 비교·토큰당 유효 정보/예측 정확도는 이번에 비교하지 못했다. nonLLM 시연의 모델 호출/토큰은0이며 유효 투자 개선 가설도0이다. **검증된 투자 개선 1건당 비용·개입 시간은 양쪽 모두 산정 불가**다. 설치 크기나 기능 수로 그 경제성을 대신 계산하지 않는다.

## 6. A/B/C 구조 비교와 최소 연결 증거

| 구조 | 실제 최소 근거 | 줄일 수 있는 개발 | 추가 부담/불확실성 | 현재 판단 |
|---|---|---|---|---|
| A Vibe 중심 전면 전환 | 원본 local loader→native US/KR runner→연구 비용·goal·artifact, 원본 saved Paper 시험 | QH 연구·UI·state orchestration 대부분 중복 제거 가능 | 운영 ledger/time/fee 계약과 장기 원장·Factory/독립 복기 이전, 별도 모델 인증, 전체 전환 복구·업그레이드 검증 필요. 이번 원본 운영24h 실측 없음 | 향후 가능성 유지. 지금 전면 전환의 총부담이 더 낮다는 증거 부족 |
| B Quant 중심 부분 도입 | 원본 factor CSV→기존 QH common replay, target mismatch0·독립 NAV 일치 | 팩터 계산/일부 valuation 재사용 | QH에서 research UI/WF/goal 등을 다시 만들면 중복·유지비 증가. upstream 내부 API 부분 이식의 drift 관리 | 보수적 대조군으로 유지 |
| C 최소 통합형 | B 출력→input hash/버전/권한 없는 제안 packet. input 불일치·주문/승격 true·자가승인·shell 필드 5개 거부 시험. 공식 Factory/DB mutation0 | Vibe 연구·분석 자체를 재사용하고 QH는 실제 필요한 증거·실행·평가 경계만 남김 | data adapter와 evaluation contract, 독립 모델·holdout 권한 분리, native 연구 workspace와 공식 승인을 혼동하지 않도록 해야 함. 전체 운영 이행은 아직 안 함 | **추천 HYBRID_MINIMAL** |

PoC 경계는 `experiments/task6_pre/exchange_contract.py`와 `evidence/exchange_contract.json`에 있다. 이는 선언만 있는 설계가 아니라 실제 factor/target 결과를 사용한 거부 검증이지만, 거래 서비스/승인 endpoint를 새로 배포하지는 않았다.

최종 권위는 하나씩만 둔다.

- 수집/실행 일정: 기존 단일 운영 timer. Vibe schedules/Gateway를 같이 활성화하지 않음.
- 공식 데이터: accepted snapshot의 observation/revision hash. Vibe local/frozen loader는 이 자료만 읽음.
- 공식 주문·NAV: 현재 검증된 QH stock Paper. Vibe Paper는 연구 대조군으로만 남김. 추후 같은 계약의 이점이 입증되면 원장을 **단일 cutover**로 바꿀 수 있으며 영구 보존 자체가 목표는 아님.
- 공식 연구 승인: Factory. Vibe hypothesis/goal/artifact는 작업자의 탐색 메모리·근거 링크이며 자체 validated/completed가 승격 승인은 아님.
- 독립 평가: 제안자에게 최종 평가를 노출하지 않는 별도 worker. trusted deterministic 코드인 현재 QH worker도 모든 임의 생성 코드에 대한 OS sandbox를 뜻하지 않는다.

원본 Research Lab의 fold 분리/전략 봉인 시험은 유효하다. 그러나 기본 backtest 생성 코드는 로컬 파일/네트워크에 접근할 수 있다. 같은 run root에 전체 holdout을 둔 채 untrusted 생성 코드가 읽지 못한다고 가정해서는 안 된다. 향후에는 fold별 최소 파일 mount·무네트워크·비밀정보 없는 평가 worker로 실제 권한도 분리한다.

## 7. Task 6~10 확장 및 증분 효과 계약

현재 Vibe는 factor registry, quantitative valuation, fundamental/earnings/committee swarm, hypotheses·goal·versioned artifact를 이미 갖고 있다. Qlib Alpha158 기능이나 DCF·역할 프롬프트를 다시 붙이는 일부터 시작하지 않는다.

| 확장 후보 | 이번 실사의 결정/연결 계약 |
|---|---|
| QuantaAlpha, RD-Agent(Q), FinRL-X, Qlib | 아직 설치·효능 비교 안 함. 새 factor panel/동결 signal·target/코드 commit·학습/관측 범위·비용·소스 hash를 반환하는 research worker 후보. Vibe의 같은 기능보다 증분이 있어야 추가 |
| EvoQuantLab | 공개 실행 코드 검증 전에는 evaluator adapter 후보만 기록. 기능/성능 확인으로 쓰지 않음 |
| TradingAgents, FinRobot | Vibe 자체 committee와 동일 증거·모델·예산으로 비교. 최초 회사/퀀트 판단 독립성 유지. 논거·반증·수치 예측 계약/근거 시각을 데이터로 반환 |
| investor-harness / financial-services / equity-research-skill | Vibe의 기본 촉매/earnings/valuation 대비 필요한 차이만 A/B. 기존 스킬 검증 문서 재사용, 미검증 효과를 성과로 가산하지 않음 |
| InvestSkill | Shadow의 profitable 패턴 추출과 다른 과정 평가/오류 taxonomy의 증분 후보. 결과 비공개 blind packet과 성숙 결과를 분리 |
| 기존 Factory / 선택적 Hermes | Factory가 승인 권위. Hermes는 장기 탐색·기억/위임 증분 worker 후보이며 ledger/승격/주문 권한0. Vibe 자체 goal/session으로 충족하면 추가하지 않음 |

후속 4개 arm은 **동일 snapshot/시장/기간/모델/프롬프트 기록/전체 토큰·실패·재시도 예산/실행 비용·위험 계약**을 고정해 비교한다.

1. 원본 Vibe 단독 — 이번에는 원본 nonLLM 실행과 fixture가 있음.
2. 원본 Vibe+전문 worker — 미실행.
3. Quant+동일 전문 worker — 미실행.
4. 최소 통합형 — factor/target·data-only 경계만 실증, 운영/LLM 통합은 미실행.

증분 추정은 2−1, 3−현행 Quant, 4−1 및 같은 evaluator의 paired 차이를 분리한다. 성과는 순수익/시장·섹터 초과/Sharpe/MDD/회전·비용, 정보는 독립 검증 사실·오탐, 수치 예측은 성숙한 MAE/Brier, 연구는 반증 가능 가설·독립 검증 성공률/비용을 사용한다. 실패·기권·미완료를 분모에서 빼지 않는다. 손익과 사실 발견/예측을 한 점수로 합치지 않는다.

정책은 비교 전에 고정하고, untouched Forward/최종 평가의 데이터 권한을 별도로 둔다. 현 survivor 과거 표본은 기능 smoke에만 재사용한다. 외부 worker는 feature flag와 버전으로 분리해 같은 입력의 no-worker 대조군을 유지하며, 증분이 없으면 해당 worker만 비활성화할 수 있어야 한다. 이번에는 이러한 외부 worker를 실제 추가하지 않았다.

## 8. 보존·재사용·교체·정리 목록

| 대상 | 결정과 후속 범위 |
|---|---|
| QH 원문·관측·revision·공식 calendar/예산 | 최소 유지. Vibe frozen/local data bridge에 공급. native 부분이 같은 보호를 대체하면 추후 한쪽만 선택 |
| QH stockpaper/store·단일 예약·복원 | 현재 단일 권위 유지. 전체 이식·실행 개선 증거 전 운영 cutover 없음 |
| QH Factory/과정 봉인·성숙 scorer | 필요한 경계 유지·adapter 확장. Vibe workspace의 중복 승인·승격은 금지 |
| QH 자체 대규모 팩터/WF/valuation/연구 UI 신규 개발 | **보류하고 Vibe 우선 재사용**. 같은 기능을 재구현하는 Task 순서를 변경 |
| Vibe Alpha Zoo/Research Lab/quantlib valuation·goal/artifacts | 고정 원본 research worker로 재사용 후보 확정. 원본 소스 수정0, 파일 기반 경계 PoC. native paper/Shadow는 비교용 |
| 과거 V69~V104·ETF 진단 | 동결 재현용 보존, 신규 활성 경로의 주력으로 복귀시키지 않음. baseline archive로 분리 후 의존성 증명된 것만 향후 제거 |
| 두 개의 scheduler·동일 분석을 중복 호출하는 wrapper | 도입하지 않음. 이번 PoC는 일시 실행 컨테이너뿐 |
| 이번 설치 빌드 사본·cache·중복 로그 | 증거 archive/사본/해시 보존 후 안전하게 제거. 목록/절감량은 `evidence/cleanup.json` |

이번 작업에서 운영 코드 삭제/전략 변경은 없다. 향후 기능 교체가 실제 승인될 때 QH 중복 연구 코드를 제거해야 하며, 현재 기존 재현 의존성이 불명확한 파일을 임의 삭제하지 않았다. 새 PoC는 수백 줄의 격리 입출력/검산 코드이며 production migration 비용을 대표하지 않는다.

## 9. 안전·인증·비용·유지보수

- 원본 root LICENSE는 MIT. qlib158에는 별도 Apache-2.0 출처/고정 commit/NOTICE가 있으므로 재배포 시 함께 보존한다. dependencies의 재배포 조건/라이선스 전체 감사는 미실행이며 이 사실만으로 후보를 제외하지 않았다.
- dependency 설치는 main의 범위 조건을 풀어 받은 188-entry 환경이다. source pin과 package 버전 목록을 보존했지만 모든 wheel/hash를 포함한 공급망 감사는 아니다. 무분별한 upstream 자동 갱신은 하지 않는다.
- main은 안정 태그 뒤 99 commits이며 중요한 Research Lab/회계 기능도 최근 추가됐다. API/CLI/manifest·원본 선택 시험·독립 ledger·동일 비용 replay를 upgrade gate로 둔다. 내부 함수 부분 복사보다 pin된 worker와 좁은 데이터 boundary가 추적하기 쉽다.
- Vibe를 연구 worker로 사용하면 원본 환경 약1.1GB가 추가된다. 별도 PostgreSQL·벡터DB·브로커·상시 scheduler는0개 추가했다. SQLite는 독립 research workspace의 local state다.
- 생성 Python과 일부 swarm preset의 bash/write_file/read_url 권한을 운영 호스트에서 그대로 허용하지 않는다. 원본 SECURITY.md도 local generated-code 위험을 명시한다. 실사에서는 container 권한으로 제한했다.
- 모델은 Vibe의 별도 OAuth 로그인이 필요하고 기존 Codex CLI 인증을 자동 공유하지 않는다. 인증 갱신/지원 모델/실패·truncated completion·재시도 예산은 후속 실증 대상이다. 결제0, 유료 데이터0, 모델 호출0이며 실제 투자 연구당 모델비용은 미측정이다.
- 네트워크와 모델을 제거한 이번 성공을 실제 SEC/Yahoo 수집 안정성·미래 예측 정확도로 간주하지 않는다. Yahoo/Toss 기존 사용 조건과 SEC403 제한은 기존 정책을 유지한다.

운영 안전 근거: `safety_and_archive.json`에서 tracked operating diff가 실사 시작과 일치하고 원본 checkout은 clean이다. 실행 컨테이너에 운영 DB/개인인증을 제공하지 않았다. 기존 Task5 timer가 정상 운영으로 기록을 추가할 수 있으므로 전체 운영 DB가 시간 경과에도 동일하다고 주장하지 않는다.

## 10. 최종 판정·후속 구현 순서

**판정: HYBRID_MINIMAL.** 연구는 Vibe의 실제 기능을 우선 사용하고, 공식 데이터·실행·연구 승인·독립 평가에는 현재 필요한 QH 최소 경계를 남긴다. 이 판정은 미래 투자 초과수익이나 전체 운영 이행의 승인이 아니다.

후속 순서를 다음과 같이 재편한다.

1. **Task6 기반 정리:** 이번 pinned worker/local loader/data-only exchange를 작은 운영 연구 adapter로 정리. Vibe 신규 설치 대신 보존된 환경 활용. 모델 인증은 기존 개인 token 복사 없이 별도 허용된 경로로 검증. 동결 input 및 worker hash upgrade gate를 우선 구현.
2. **Task7 연구 엔진:** 기존 Research Lab·팩터·valuation을 실제 가설에 적용. 기존 strategy/reference와 untouched Forward를 분리. RD-Agent/Qlib 등을 추가하기 전에 Vibe 단독 대비 필요성을 평가.
3. **Task8 기업 분석:** Vibe 기본 earnings/committee와 기존 분석·투자 스킬을 같은 원문/모델/예산으로 비교. 실제 구조화 예측과 당시 반증 조건을 먼저 봉인.
4. **Task9 실행·복기:** native Paper/Shadow와 QH 계약 차이를 동일 event fixture로 검증한 뒤 단일 원장 정책 선택. 정상 손실·과정 위반·경제 원인·반사실 residual을 분리. 원장 이전은 별도 승인/복구 시험 필요.
5. **Task10 지속 검증:** 4개 arm의 독립 Forward·연구당 비용/개입·복구/증분을 측정하고 효과 없는 worker 제거. 자동 Champion/Live 승격은 계속 금지.

### 재현과 증거

- 진행/오류/재개: `docs/development/06_pre_progress.md`.
- 입력 및 버전: `runtime/task6_pre/evidence/{versions,preregistration,release_features}.json`.
- 원본 실행: `poc_execution.log`, `summary.json`; 요약 후처리 오류는 `research_recovery.{log,json}`로 회수했으며 실패 흔적을 지우지 않음.
- 공통 비교: `runtime/task6_pre/comparison/results.json`와 시장별 target/fill/nav CSV.
- 독립 검산: `native_inspection.json`, `causality.json`, `exchange_contract.json`.
- 공식 원본 실행 산출물·고정 input·study·local state: `original_execution_artifacts.tar.gz` 및 `safety_and_archive.json` hash.
- QH 최소 회귀: **24 passed / 21.00초**, compileall 성공. 기존 전체 회귀를 다시 돌리거나 운영 경로를 수정하지 않았다.

PoC 재현 entry는 `experiments/task6_pre/{export_inputs,vibe_probe,common_comparison,inspect_native,resume_research,causality_probe,exchange_contract}.py`다. runner는 container 안 `/venv/bin/python /poc-code/vibe_probe.py`, Quant common replay는 프로젝트 `.venv/bin/python experiments/task6_pre/common_comparison.py`로 실행한다. 당시 `vibe_probe` 후처리의 Registry.get 오류 로그는 보존했다. 재현 스크립트는 올바른 Registry.list 조회로 최소 수정했고, 같은 조회를 사용하는 `resume_research.py`에서 실제 상태 회수를 검증했다. 완료한 백테스트를 이 수정 때문에 다시 실행하지 않았다. 새 재현은 별도 빈 work 경로에서 시작해 가설/goal 재생성을 기존 연구 이력과 섞지 않는다.

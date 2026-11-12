# Task 1 · 주식 자동매매 시스템과 GitHub 기술 조사

2026-11-12 KST · 의사결정 자료 · 역사 결과와 운영 상태는 각각 표시했다.

## 결정

**기존 결정론적 전략·Paper 원장·Live 차단을 유지하고, 시점별 증거 수집과 실험 검증을 부분 개선한다.** 투자 판단의 첫 후보는 공식 공시의 조기 발견과 시점 증명이다. 기술 검증의 첫 후보는 입력 경계 테스트와 동일 세션 주문·체결 대사다. 현 시점에는 외부 매매 엔진이나 LLM 운용팀을 통째로 도입할 근거가 부족하다.

| 선택 | 기대 이점 | 비용·판정 |
|---|---|---|
| 현상 유지 | 동결 기준선과 현행 테스트 재사용 | 운영과 연구의 입력·증거 단절이 남는다. 비교군 A로 유지 |
| 부분 개선 | 새로운 공시 증거의 증분 가치와 운영 장애를 각각 측정 | 낮음~중간. 가장 작은 변경으로 반증 가능하므로 선택 |
| 실행 핵심 교체 | 이벤트 단위 시간·상태 복원, 멀티 전략 실행 계약 통합 | 높음. 기존 일봉 결과 재현 및 Toss 어댑터·원장 대사 통과를 조건으로 재평가 |
| 전면 재구축 | 버전별 엔트리포인트를 하나의 이벤트 계약으로 통합할 수 있음 | 매우 높음. KRX PIT 데이터와 미래 초과수익 근거는 별도로 확보해야 하며 기존 가드·회계 증명도 다시 필요 |

## 현재 시스템

| 영역 | 확인한 호출 경로와 상태 |
|---|---|
| 입력·장 마감 | `scripts/run_daily_paper_cycle.py:42` → `daily_paper_runtime.py:272,351,436` → Toss ETF/KS11 증분 → freshness/lock → preview → Paper execution → NAV. 기본 날짜 계산은 평일 추정(`:157`)이므로 KRX 휴장·지연 도착·수정 데이터는 별도 검증 필요. 실제 상시 실행이나 최신 거래일 수집 성공은 이번에 관측하지 않았다. |
| 선정·배분 | `paper_decision_runtime.py:251–258`의 일일 활성 경로는 V69_PARENT를 명시적으로 요구한다. `:263–287,469–474`의 후보 지정 경로는 연구/replay에서 V79 계열도 선택 가능하다. `v104_end_to_end_causal_challenger_audit/adapter.py:116–257`의 공유 경로는 V94 유니버스·가격/거래대금 특징 → V95 국면 → 후보 정책 → V100 target과 V102 증거다. 릴리스의 V99 계약명만으로 독립 프로세스나 독립 판단이 상시 실행된다고 해석할 수 없다. 입력은 ETF와 KS11 중심이며 Top200 개별주식 경로가 이 실행에 연결됐다는 근거를 찾지 못했다. |
| 주문·체결 | `paper_execution_runtime.py:418,467–531`에 별도 원장 대사와 실패 시 HOLD_ONLY가 있다. `historical_operational_replay.py:147,812–978`은 테스트 DB 격리, 후보별 preview 및 Paper 실행을 사용한다. 반면 V104 어댑터 자체 replay(`adapter.py:259–274`)는 V101 시뮬레이터 직접 경로다. 리서치 결과마다 실제 사용한 엔진과 체결·비용·수량 계약을 명시해야 한다. |
| Live·복구 | `v72_integration_ready/toss_read_only.py:61–122`는 GET 조회/스냅샷, `live_safety.py:7,33`와 `toss_openapi.py:154,570`은 권한 하드락을 보여 준다. Paper의 재시작 검증과 실제 브로커 접수 직후 응답 유실·재접속 복구는 별개의 검증이다. 라이브 주문은 조사 중 실행하지 않았다. |
| Forward | `forward_runtime.py:21,33,82,169,187`에 관측 분류·후보 게이트·영수증 검증·append가 있다. 현재 `config/v104_challenger_runtime_contract.yaml:7–46`의 3개 후보는 목록에 있으나 모두 `enabled_for_new_forward: false`, `adapter_status: NOT_RUN`, 관측 카운터 0이다. 릴리스의 과거 “구현·테스트됨”과 현재 등록 상태를 구분한다. |
| 복기·장기 기억 | `v103_review_feedback_agent/engine.py:143,231,430,505`는 시도 수집, 검증·다중비교, 승인 대기를 수행한다. Factory에는 append-only 시도와 해시 검증이 있으며 `runtime/alpha_research_factory/completion/final_decision_report.json`은 실제 replay 0/1과 합성 경로 통과를 기록한다. 전략 자동 승격 권한은 없다. 현재 기록을 다음 세션에서 반사실적 질문과 연결해 회수하는 운영 루프는 확인되지 않았다. |
| 연결되지 않은 기능 | `scripts/run_rss_news_shadow.py`, `run_pain_supply_shadow.py`는 분리 실행 경로다. 해당 출력과 SectorTheme이 위 일일 runner의 목표/주문을 바꾼다는 증거는 없다. `scripts/run_v85_scheduler.py` 존재는 예약 작업이 배포돼 정상 실행 중이라는 증거가 아니다. |

핵심 병목은 **① 증거의 최초 관측 시각과 시점별 종목 연결 ② 여러 실행 경로의 체결·NAV 비교 가능성 ③ 신규 Forward 관측 축적**이다. 현재 유니버스의 첫 관측일 프록시는 상폐·코드변경까지 포괄하는 PIT 구성 이력으로 사용할 수 없다. 과거 `runtime/contract_aligned_comparison_20261004_run2/`에는 2021-10-13~2026-07-31 비용 반영 replay가 있다. V69 +234.31%, V79_NO63_VOL_GUARD +378.70%, 069500 단순보유 +213.50%는 해당 결과의 역사 수치다. 이 기간은 이미 연구에 사용됐고, 순수 신규 표본은 확보가 필요하다.

## GitHub 후보 우선순위

아래 날짜는 2026-11-12 조사 당시 GitHub REST의 저장소 최근 push 날짜다. push는 릴리스 품질이나 지원 약속의 지표가 아니다. 외부 프로젝트 테스트는 소스/테스트 트리 열람 범위이며 로컬에서 재실행하지 않았다.

| 순위·용도 | 후보·라이선스·최근 push | 기능·근거·이식 판단 |
|---|---|---|
| 1 투자 증거 | [EdgarTools](https://github.com/dgunning/edgartools) · MIT · 11-12 | SEC 공시 파싱과 8-K 항목 추출. 국내 직접 사용보다 접수 시각 검증과 원본-정정 계보 패턴을 DART에 이식. 중간, 외부 데이터·권리·시점별 매핑 필요. [시각 결함과 재현 사례](https://github.com/dgunning/edgartools/issues/1501) |
| 2 운영 품질 | [Pandera](https://github.com/unionai-oss/pandera) · MIT · 11-11 | 컬럼/프레임 검사와 실패 집계. 기존 V87·freshness를 대체할 필요 없이 누락·순서·타입 검사 확장. 낮음, pandas 버전 호환 고정. [테스트](https://github.com/unionai-oss/pandera/tree/main/tests) |
| 3 투자 진단 | [Qlib](https://github.com/microsoft/qlib) · MIT · 11-04 | PIT 조회와 독립적인 데이터·모델·실험 기록 도구. 별도 연구 프로세스에서 점수만 교환. 중간~높음, 데이터 변환·의존성 비용. 공개 [벤치마크](https://github.com/microsoft/qlib/tree/main/examples/benchmarks)는 국내 ETF·Toss 실행 조건에서의 검증으로 전용할 수 없다. [PIT 소스](https://github.com/microsoft/qlib/blob/main/qlib/data/pit.py), [테스트](https://github.com/microsoft/qlib/tree/main/tests) |
| 4 실행 검증 | [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) · GitHub LGPL-3.0 표기 · 11-12 | 이벤트 실행 및 브로커 보고서 기반 복구. 독립 실행 대조군·복구 테스트 참고. 높음, Rust/Python 호환과 Toss/KRX 어댑터 및 배포 라이선스 검토 필요. [복구 모듈 구조·동작](https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/concepts/execution/reconciliation.md). 조사 중 개별 엔진·테스트 링크 열람 실패로 해당 코드와 테스트 일치는 미확인. |
| 5 운영 지속성 | [Temporal Python SDK](https://github.com/temporalio/sdk-python) · MIT · 11-11 | 워크플로 이력 replay와 재개. 현행 단일 작업보다 작업 간 복구 요구가 커질 때 시험. 중간~높음, 서비스·스토리지 추가와 결정론 제약. [Replayer 구현](https://github.com/temporalio/sdk-python/blob/main/temporalio/worker/_replayer.py), [replay 예제](https://github.com/temporalio/samples-python/tree/main/replay) |
| 6 투자 리서치 | [TradingAgents](https://github.com/TauricResearch/TradingAgents) · Apache-2.0 · 11-04 | 분석가·토론·결론 그래프와 체크포인트. 기존 검증 루프에서 독립 반론·공시 검색만 실험. 중간, 모델 비용과 공급자 드리프트·환각. [그래프](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/graph/trading_graph.py), [저자 연구](https://arxiv.org/abs/2412.20138). 논문 결과와 이 워크트리의 구현 버전·국내 시장 조건은 다르다. |
| 7 자기개선 | [RD-Agent](https://github.com/microsoft/RD-Agent) · MIT · 10-21 | 가설·팩터/모델 생성과 실험 루프. 기존 Factory와 중복되고 탐색 횟수·코드 실행 관리 비용이 크다. 문서·시나리오만 참고. [Qlib 시나리오](https://github.com/microsoft/RD-Agent/tree/main/rdagent/scenarios/qlib), [릴리스 및 저자 기술보고서 안내](https://github.com/microsoft/RD-Agent/releases). 외부 성과 재현과 실제 투자 효과 미확인. |
| 8 배분 연구 | [skfolio](https://github.com/skfolio/skfolio) · BSD-3-Clause · 11-10 | 상대적으로 좁은 범위의 포트폴리오 최적화 및 purged CV 도구. 기존 Factory의 날짜 분할 독립 대조에 부분 사용 가능. 중간, sklearn·최적화 스택과 공분산 추정 민감도. [분할 구현](https://github.com/skfolio/skfolio/tree/main/src/skfolio/model_selection), [테스트](https://github.com/skfolio/skfolio/tree/main/tests/test_model_selection). 예제는 도구 동작을 설명하며 시장 우위는 미검증. |

### 상위 후보 도입 지점

- **공시 증거.** EdgarTools의 `acceptance_datetime` 문제는 같은 원천 안에서도 날짜 필드와 공식 접수 시각이 다를 수 있음을 보여 준다. DART/거래소 증거에 원본 ID, 공식 접수·최초 수신·검증 시각, 원본 해시, 정정 계보와 당시 ETF 연결 근거를 묶는다. 실적 전망 변경·정정·중대 사건의 조기 발견은 평가 가능한 가설이다. 기업가치 예측은 당시 컨센서스나 공시와 연결되는 실측 후속 라벨 없이는 판단할 수 없다. [공시 메타데이터 구현](https://github.com/dgunning/edgartools/blob/main/edgar/entity/filings.py)
- **입력 계약.** Pandera를 도입한다면 첫 경계는 세션 입력/출력이다. 기존 코드에서 같은 검사를 더 단순하게 유지할 수 있으면 라이브러리 채택을 생략한다. 스키마 검사에 거래소 세션 ID, 중복, 소스별 관측 시각 및 데이터 해시 검사를 결합한다.
- **독립 점수 진단.** Qlib의 PIT 표현과 벤치마크 실행 구조를 빌리되 공급 데이터는 동일한 동결 KRX 입력으로 제한한다. 도구 자체가 상폐 이력이나 지연 수신 시각을 복원하지 않는다. 출력 점수·라벨·실험 ID를 현행 Factory의 veto와 연결하고 검증 후 기존 Paper 계약으로 평가한다.
- **운영 복구.** Nautilus의 시작 대사와 실행 중 대사 구분을 테스트 설계에 사용한다. 상태 불명 시 접수 응답과 체결을 먼저 확인하고, 합성 정정 이벤트 정책은 현재 원장 규칙과 대조한다. Temporal의 workflow replay는 주문 효과의 멱등성 검사를 대신하지 않으므로 외부 작업 키와 대사가 별도로 필요하다.
- Nautilus의 현재 Rust [ExecutionManager](https://github.com/nautechsystems/nautilus_trader/blob/develop/crates/live/src/execution/manager.rs)와 Pandera의 [DataFrameSchema](https://github.com/unionai-oss/pandera/blob/main/pandera/api/pandas/container.py)까지 확인했다. Nautilus의 실행 대사 테스트는 별도 검토가 남았다. 로컬 V85 스케줄러는 `compose.yaml:23`에 연결돼 있고 `scripts/run_v85_scheduler.py`에서 시간 간격으로 레거시 `run_operating_day`를 호출한다. 일일 PostgreSQL Paper 사이클을 이 스케줄러가 호출하는 경로는 확인되지 않았다.

## A/B 실험 계획

공통 A는 현행 일일 V69_PARENT의 동결 입력·설정·전략이다. 투자 연구에는 동일 경로에서 지정한 V79_NO63_VOL_GUARD와 비용 반영 069500도 비교 기준으로 둔다. 각 실험에서 D-1/PIT 가용 시각, 초기 1천만원, 주문 규모·위험 한도, 수수료·spread·impact, 데이터 및 호출 예산을 고정한다. 배분과 비용을 같이 바꾸지 않는다. 한 회차 최대 3개 가설, 운영형 replay 최대 1개. 아래 실험은 설계이며 관측된 개선 효과는 없다.

| B와 가설 | 반증 가능한 시험과 중단 기준 |
|---|---|
| 공시 증거 수집 추가 | 사전에 정한 중요 사건에서 최초 발견 지연·원문 인용 정합성·미발견률 측정. 현행 shadow 대비 더 일찍 발견하고 다음 의사결정 전에 이용 가능해야 한다. 같은 주·섹터 안 사건 날짜를 섞은 placebo, 원문 제거 ablation. 중대 사건 신규 진입 차단은 별도 계약으로 순수익·놓친 상승·거부 오탐을 동시 검증. |
| Qlib 연구 점수 추가 | 기존 점수와 같은 유니버스에서 사전 고정한 대표 점수 하나. 가격만/공시 추가 ablation, non-overlap rank IC·spread·블록 부트스트랩. 날짜 분할은 라벨 horizon만큼 purge/embargo하고 학습·튜닝 후 파라미터 동결. 개선이 단일 ETF나 기간에 집중되거나 2배 비용에서 사라지면 탈락. |
| Pandera 경계 검사 추가 | 정상 입력에서 target/order hash 동일. 누락 바·잘못된 시간대·중복·나중 정정 입력을 주입해 조기 차단과 오탐을 측정. 정상 데이터 오차단 또는 기존 검사와 동일한 탐지 성능이면 채택 우선순위를 낮춘다. |
| Nautilus식 이벤트 복구 대조 | 동일 합성 체결 스트림과 지연·중복·부분체결·역순·접수 직후 중단을 주입. 주문 중복, 현금/보유수량 차이, 상태 복구 시간, 설명 불가능한 차이 비교. 실제 Toss mutation 없이 기록 재생. |
| Temporal 복구 시험 | 동일 일일 작업에서 업데이트 직후·원장 쓰기 직전/직후 프로세스 중단. 재개 정확도, 중복 효과, 지연, 설정/유지 비용 비교. 기존 잠금과 재개 방식으로 목표 복구 시간이 충족되면 보류. |
| TradingAgents식 독립 반론 추가 | 동일 도구·토큰·검색 시간에서 단일 분석가와 다중 분석가 비교. 프롬프트에 없는 검증 가능한 사건 발견율, 근거 인용, 반론 품질과 비용을 블라인드 평가. 토론 제거 ablation. LLM 출력을 주문 결정에 직접 쓰지 않는다. |
| skfolio 배분 연구 | 먼저 A와 B의 분할 누수 검사 결과를 독립 대조한다. 배분 자체를 검증할 경우 후보·노출 상한·현금·비용을 고정하고 사전등록한 비중 계산 한 가지로 비교한다. 낙폭 개선이 초과수익·회전율 악화와 함께 나오면 각각 기록한다. |

실제 투자 후보는 기간별 순성과·낙폭·회복기간·turnover·꼬리손실을 함께 기록한다. 반복 사용된 역사 구간은 개발·검증 자료로 표시하고, 새로운 독립 표본과 동결 이후 Forward Paper를 구분한다. 복기에는 원 의사결정과 당시 원문, 판단하지 않았을 때의 사전 정의된 반사실, 비용과 불확실성을 함께 저장한다. 시장 수익은 별도 기준선이며 발견 성능이나 장애 복구 성능과 합쳐 승격 점수로 계산하지 않는다.

## 다음 단계 인계

1. 공식 공시 최초 관측 시각과 시점별 ETF 매핑을 확보한 범위에서 공시 발견 실험을 사전등록한다. 데이터 미확보 시 실시간 shadow 수집의 커버리지부터 측정한다.
2. 같은 세션·입력 해시에서 Paper와 역사 replay의 target → intent → order → fill → NAV를 대사한다. 결함 주입으로 하루 작업의 중복 방지·재시작·관측 가능성을 검증한 뒤 외부 실행 엔진을 재평가한다.
3. 외부 엔진 전체 교체, 자율 전략 생성·배포, LLM 포트폴리오 매니저는 현 단계에서 추천하지 않는다. 현재 기준선과 비교 가능한 개선 증거가 생기면 각각 별도 변경으로 검토한다.

조사 스냅샷은 HEAD `bf53346` (2026-07-30, P0 live hardlock completed), `git status --porcelain` 180행의 작업 트리였다. Git 이력과 현행 실행 파일을 분리해 해석했다. V104 challenger config SHA-256 `32788ddd773599a2e17fd93ad68f817d4c67b6e8b0124e4ad462fd478939f878`, 기존 모델 증거 export `runtime/current_model_evidence_audit/verified_exports_v3.json` SHA-256 `92ffcbd51b287adc1e3a6ca7adcdca0180394b74775b93629b0added8f0b44f5`. 외부 push·라이선스는 GitHub 저장소 메타데이터를 확인했다. Gemini API 환경 설정이 없어 deep-research 스킬의 외부 에이전트 대신 GitHub 원문을 직접 열람했다.

이번 검증에서 `python -m compileall -q src scripts tests`는 종료 코드 0이었다. AGENTS.md의 네 파일(V104, V104.2 crash bridge, V84, V89) 회귀는 pytest 진행률 100%를 출력했으나 종료 요약과 코드를 반환하지 않았다. V89 단독 실행도 종료 결과를 반환하지 않아 조사 중 시작한 두 테스트 프로세스를 중단했다. 이번 회귀 상태는 **종료 미확인**이며 과거 릴리스 통과 기록과 구분한다. 전체 테스트와 외부 프로젝트 설치·재현은 수행하지 않았다.

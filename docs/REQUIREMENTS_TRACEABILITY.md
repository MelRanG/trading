# REQUIREMENTS TRACEABILITY

## 1. 상태 정의

| 상태 | 의미 |
|---|---|
| `IMPLEMENTED_CONNECTED` | 활성 V104 실행 경로에서 호출되고 결과에 영향을 준다. |
| `IMPLEMENTED_SEPARATE` | 실행 가능한 구현이 있으나 활성 V104 경로와 연결되지 않는다. |
| `PARTIAL` | 일부 계약/기능만 구현됐거나 외부 상태 없이 synthetic하게 동작한다. |
| `DIAGNOSTIC_ONLY` | 결과를 기록·표시하지만 활성 부모 자본경로를 바꾸지 않는다. |
| `CONTRACT_ONLY` | schema/interface/validator만 있다. |
| `NOT_IMPLEMENTED` | 실행 가능한 구현을 찾지 못했다. |
| `HISTORICAL_ONLY` | 역사 연구·감사용이며 신규 Forward 증거가 아니다. |

## 2. 요구사항-구현 추적표

| ID | 요구사항 | 문서·설정 근거 | 실제 구현 근거 | 상태 | 감사 판정 |
|---|---|---|---|---|---|
| R-001 | 시스템은 Paper 연구 하네스로 실행돼야 한다. | `README.md:3-10`, `config/active_strategy.yaml:3-5` | V104/V84/V85/V88 결과 모두 Live false를 기록하며 V88 non-dry-run을 차단한다(`src/quant_harness/v88_order_reconciliation/engine.py:241-244`, `:330-338`). | IMPLEMENTED_CONNECTED | 정상 경로는 Paper only. |
| R-002 | 가격은 조정 OHLC만 허용한다. | `config/v77_corrected_price_allocation.yaml:11-15` | source tag 단일성·OHLC geometry를 검증한다(`src/quant_harness/v77_corrected_price_allocation/engine.py:91-111`). | IMPLEMENTED_CONNECTED | 활성 loader가 직접 강제. |
| R-003 | 거래 가격을 forward-fill하거나 open을 close로 대체하지 않는다. | `config/v77_corrected_price_allocation.yaml:14-15` | core open/close 누락을 차단하고 tradable pivot을 fill하지 않는다(`src/quant_harness/v77_corrected_price_allocation/engine.py:132-141`). | IMPLEMENTED_CONNECTED | 단, 비-core 누락은 V101 주문 시점에 차단. |
| R-004 | 실제 데이터는 V87 revision-safe ingestion을 거친다. | `docs/ARCHITECTURE.md:8-10`, `AGENTS.md:28` | V87 validator/output은 구현(`src/quant_harness/v87_actual_data_ingestion/engine.py:143-291`)됐으나 V104는 raw CSV를 직접 읽음(`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:111-125`). | IMPLEMENTED_SEPARATE | 문서상의 직렬 연결은 사실 아님. |
| R-005 | 시점별 유니버스를 보존한다. | `AGENTS.md:7-10`, `docs/CONTRACTS.md:5-13` | 관측 bar 기반 lifecycle와 D-1 gate(`src/quant_harness/v94_universe_agent/policy.py:38-78`). | PARTIAL | static 목록이며 상폐·기업행위 불완전(`:48-57`). |
| R-006 | 시장 상태는 D-1 정보만 사용한다. | `docs/CONTRACTS.md:7` | 모든 실행 필드 shift(1), cutoff 기록(`src/quant_harness/v95_market_regime_agent/policy.py:65-80`, `:109-127`). | IMPLEMENTED_CONNECTED | 강한 인과 통제. |
| R-007 | 후보선정은 D-1이며 sector 대표를 중복 제거한다. | `config/strategy_registry_v84.yaml:65-89` | V69/V79 selector와 V98 sector panel(`src/quant_harness/v69_dynamic_theme_leadership/engine.py:186-333`; `src/quant_harness/v98_candidate_selection_agent/policy.py:192-262`). | IMPLEMENTED_CONNECTED | runtime 모듈은 V99가 아니라 V69/V79+V98. |
| R-008 | V99 CandidateSelectionAgent가 활성 실행 엔진이다. | `RELEASE_STATE.json:42-45`, `docs/ARCHITECTURE.md:34-35` | V104 adapter import에는 V99가 없고 V98 helper를 직접 사용(`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:14-22`, `:190-206`). | PARTIAL | V99는 연구 버전/계약명이지 runtime 호출 단위가 아님. |
| R-009 | StrategyAgent가 목표비중과 hash를 생성한다. | `config/strategy_registry_v84.yaml:90-106` | V100 target builders 호출(`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:207-223`; `src/quant_harness/v100_strategy_agent/policy.py:43-179`). | IMPLEMENTED_CONNECTED | 확인됨. |
| R-010 | 부모와 후보는 동일 입력 hash를 사용한다. | `AGENTS.md:19`, `docs/CONTRACTS.md:8-10` | 데이터·설정 파일 hash 생성 및 Forward 비교(`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:77-105`; `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:85-89`). | IMPLEMENTED_CONNECTED | source code 자체는 hash에 포함되지 않음. |
| R-011 | 후보 fingerprint를 고정한다. | `AGENTS.md:19` | CandidateSpec 직렬화 hash와 contract 비교(`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:29-52`; `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:85-87`). | IMPLEMENTED_CONNECTED | spec 외 code version은 fingerprint에 미포함. |
| R-012 | 수급은 D-1이며 missing session을 보간하지 않는다. | `config/v102_market_evidence_contract.yaml:4-17` | reindex 후 shift, current flag(`src/quant_harness/v102_market_evidence_agent/policy.py:74-105`). | IMPLEMENTED_CONNECTED | 수급 원본의 당시 revision 상태는 미검증. |
| R-013 | 공시는 접수시각 기준 PIT이며 수정공시를 반영한다. | `config/v102_market_evidence_contract.yaml:18-34` | `received_at`→available date, cutoff 전 이벤트만 state에 반영(`src/quant_harness/v102_market_evidence_agent/policy.py:108-174`). | IMPLEMENTED_CONNECTED | ETF 구성 mapping은 effective-dated가 아님. |
| R-014 | 뉴스는 공식 critical event만 자본 veto할 수 있다. | `config/v102_market_evidence_contract.yaml:35-50` | validator와 action 분류(`src/quant_harness/v102_market_evidence_agent/policy.py:176-216`). | CONTRACT_ONLY | 역사 PIT 뉴스 데이터와 runtime 호출 없음. |
| R-015 | 부모 활성 MarketEvidence는 진단 전용이다. | `config/strategy_registry_v84.yaml:124-147` | `MARKET_EVIDENCE_DIAGNOSTIC_ONLY`에서 raw target 유지(`src/quant_harness/v102_market_evidence_agent/policy.py:230-299`). | DIAGNOSTIC_ONLY | 문서와 일치. |
| R-016 | 주문은 D-1 ADV, 비용, spread, impact, 현금을 반영한다. | `config/v77_corrected_price_allocation.yaml:31-47` | V101 sell/buy fill model(`src/quant_harness/v101_risk_execution_agent/engine.py:109-245`). | IMPLEMENTED_CONNECTED | synthetic 일봉 체결. |
| R-017 | 실제 브로커 order/fill lifecycle을 반영한다. | `docs/ARCHITECTURE.md:78-82`의 목표 구조 | V101은 synthetic; V88은 simulated gateway; 외부 계약 unverified(`src/quant_harness/v101_risk_execution_agent/engine.py:517-528`; `src/quant_harness/v88_order_reconciliation/engine.py:297-338`). | NOT_IMPLEMENTED | Live blocker. |
| R-018 | 주문 의도는 submit 전에 영속화되고 멱등해야 한다. | `AGENTS.md:14`, `docs/CONTRACTS.md` | V88 journal이 intent hash를 먼저 저장하고 중복 ID 변조를 차단(`src/quant_harness/v88_order_reconciliation/engine.py:189-206`, `:241-266`). | IMPLEMENTED_SEPARATE | 실제 Toss/V104 주문 경로와 연결되지 않음. |
| R-019 | 브로커 불일치 시 `HOLD_ONLY`로 전환한다. | `AGENTS.md:15` | V88 reconcile 결과는 mismatch→HOLD_ONLY(`src/quant_harness/v88_order_reconciliation/engine.py:269-290`). | IMPLEMENTED_SEPARATE | V104/V85 신규 주문 gate에 연결되지 않음. |
| R-020 | 부모 Paper 계좌 상태와 재시작 상태를 복구한다. | `docs/OPERATIONS.md` | V84/V85 SQLite, stage checkpoint, backup/restore(`src/quant_harness/v84_dual_paper_parity/engine.py:323-347`; `src/quant_harness/v85_operational_hardening/engine.py:46-67`, `:206-207`). | IMPLEMENTED_SEPARATE | 부모 2개 전용; 후보 3개 Forward와 분리. |
| R-021 | 후보마다 고유 Paper 계좌를 사용한다. | `docs/ARCHITECTURE.md:61-63` | Forward row에 account ID 문자열만 기록(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:90-112`). | PARTIAL | 후보 영속 account/state 없음. |
| R-022 | 역사 replay를 신규 Forward로 세지 않는다. | `AGENTS.md:20` | freeze end와 비교해 history를 append하지 않음(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:73-74`, `:108-136`). | IMPLEMENTED_CONNECTED | 확인됨. |
| R-023 | Forward는 60세션 평가, 120세션 승격 검토를 요구한다. | `RELEASE_STATE.json:135-142`, `config/v103_review_feedback_agent.yaml:17-33` | V89/V103 평가 gate 구현(`src/quant_harness/v89_forward_governance/engine.py:132-179`; `src/quant_harness/v103_review_feedback_agent/engine.py:321-360`). | IMPLEMENTED_SEPARATE | V104 observation stream과 자동 연결되지 않음; 현재 0세션. |
| R-024 | 피드백은 부모를 자동 변경하지 않는다. | `AGENTS.md:21`, `config/v103_review_feedback_agent.yaml:1-15` | lifecycle의 capital authority NONE, registry Live false(`src/quant_harness/v103_review_feedback_agent/engine.py:577-588`, `:663-682`). | IMPLEMENTED_SEPARATE | 안전 거버넌스는 존재. |
| R-025 | 피드백이 다음 실행의 후보 라우팅을 갱신한다. | `docs/ARCHITECTURE.md:22-23` | V104 priority는 config의 고정 목록이며 V103을 runtime에서 호출하지 않음(`src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:401-427`). | PARTIAL | 수동/릴리스 시점 라우팅; 온라인 closed loop 아님. |
| R-026 | 데이터·reconciliation gate가 통과한 Forward 행만 기록한다. | `data/contracts/v104_challenger_forward_observation_template.csv` | Forward builder가 두 필드를 실제 검사 없이 항상 True로 설정(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:108-112`). | DIAGNOSTIC_ONLY | 실제 gate라는 요구는 미충족. |
| R-027 | 실거래는 임의 활성화할 수 없어야 한다. | `AGENTS.md:12-15` | 정상 경로와 V88은 차단. 그러나 Toss client는 env flag만 확인(`src/quant_harness/v72_integration_ready/toss_openapi.py:108-140`, `:367-411`). | PARTIAL | 중앙 승격·계약 gate가 client에 없음. |
| R-028 | Control plane은 read-only여야 한다. | `docs/ARCHITECTURE.md:20-21` | API GET만 제공하고 POST 403(`src/quant_harness/v86_control_plane_dashboard/engine.py:446-488`). | IMPLEMENTED_SEPARATE | 확인됨. |
| R-029 | 시작 시 governance 실패를 은폐하지 않는다. | `AGENTS.md:16` | Docker entrypoint가 V85/V89 오류를 `|| true`로 무시(`scripts/docker_entrypoint.sh:4-9`). | NOT_IMPLEMENTED | 문서 규칙과 충돌. |
| R-030 | 기존 성과는 생성 명령·결과 경로와 연결돼야 한다. | `docs/VALIDATION.md`, `AGENTS.md:17` | 각 엔진이 CSV/JSON을 생성하나 V104 cache를 hash 검증 없이 재사용 가능(`src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:349-367`). | PARTIAL | release 증거는 있으나 cache provenance 강화 필요. |

## 3. 문서 기능과 실제 구현 대조 요약

### 문서와 일치

- D-1 정보 사용
- 거래 가격 무보간
- 비용·ADV·cash 제한을 포함한 synthetic replay
- 역사 replay/Forward 분리
- 자동 부모·Champion·Live 승격 금지
- read-only control plane
- V88 simulator 수준 멱등성·불일치 차단

### 문서보다 약한 구현

- 시점별 유니버스: 정적 목록+관측 lifecycle proxy
- 후보별 Paper account: account ID만 있고 영속 state 없음
- 실제 데이터 pipeline: V87 출력이 V104 입력으로 연결되지 않음
- Forward data/reconciliation gate: boolean이 hard-coded
- Live hard lock: 저수준 Toss client에 중앙 gate 없음
- feedback loop: 자동 학습/실행 연결이 아닌 릴리스 거버넌스

### 문서보다 강하거나 더 명확한 구현

- V104는 future mutation audit을 사전 파일로 강제한다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:341-347`).
- V101은 target 합계와 executable open 누락을 즉시 예외 처리한다(`src/quant_harness/v101_risk_execution_agent/engine.py:91-125`).
- V88은 동일 `client_order_id`의 다른 intent 재사용을 차단한다(`src/quant_harness/v88_order_reconciliation/engine.py:193-206`).

## 4. 추적성 결론

저장소는 연구·synthetic Paper 기능에 대해서는 높은 추적성을 가진다. 다만 `RELEASE_STATE.json:14-28`의 `runtime_path`는 **의존 모듈 목록 또는 목표 운영 순서**로 읽어야 하며, 하나의 실제 호출 chain으로 해석하면 안 된다. 실제 V104 Forward 호출 chain은 `SYSTEM_AS_IS.md`의 3절에 적은 모듈만 포함한다.

# SYSTEM AS-IS AUDIT

## 1. 감사 범위와 판정 표기

이 문서는 V104.2 Codex Clean Release 저장소의 **현재 구현 사실**을 정적 추적한 결과다. 코드는 수정하지 않았다.

- **확인됨**: 실행 코드·설정·테스트·현재 결과 파일로 직접 확인했다.
- **부분 구현**: 핵심 로직은 있으나 실제 운영 경로의 앞뒤 단계와 연결되지 않았거나 외부 상태를 사용하지 않는다.
- **계약/골격**: 인터페이스·스키마·검증기만 있고 실제 공급자 또는 실행기가 없다.
- **진단/장식성**: 보고서용 또는 시뮬레이션용으로 존재하며 실제 운영 사실을 검증하지 않는다.
- **미구현**: 저장소 안에서 실행 가능한 구현을 찾지 못했다.
- **추론**: 코드에서 직접 선언하지 않았지만 확인된 구조로부터 도출했다.

권위 우선순위는 실행 코드와 통과한 테스트가 문서보다 앞선다는 저장소 규칙을 따랐다(`AGENTS.md:57-66`).

## 2. 결론 요약

### 확인된 현재 시스템

현재 실질적인 V104 실행은 다음 두 종류다.

1. **역사 전체 결정론적 replay 및 후보 감사**  
   `scripts/run_v104_end_to_end_causal_challenger_audit.py:1-9` → `src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:334-503`
2. **동결 이후 신규 세션 확인용 Forward appender**  
   `scripts/run_v104_forward_session.py:7-19` → `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:117-160`

두 경로 모두 실제 브로커 주문을 제출하지 않는다. Forward appender도 브로커 상태를 이어받는 증분 실행기가 아니라, 봉인 입력으로 전체 기간을 다시 replay한 뒤 마지막 세션 한 행만 만든다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:44-56`, `:65-72`).

### 현재 가능한 것

- 조정 일봉 파일을 읽어 정적 ETF 목록에 대한 시점별 관측 가능성·유동성 gate를 계산한다(`src/quant_harness/v77_corrected_price_allocation/engine.py:81-146`, `src/quant_harness/v94_universe_agent/policy.py:9-79`).
- 모든 활성 가격·regime·selection 특성을 D-1로 이동해 당일 시가 체결을 모사한다(`src/quant_harness/v95_market_regime_agent/policy.py:46-51`, `:65-80`; `src/quant_harness/v101_risk_execution_agent/engine.py:248-293`).
- 부모 2개와 후보를 같은 입력 hash·후보 fingerprint로 전체 replay하고 비용·스프레드·시장충격·ADV 제한을 반영한다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:77-105`, `:250-288`; `src/quant_harness/v101_risk_execution_agent/engine.py:109-245`).
- 역사 결과와 2026-07-03 고정보유분의 2026-07-30 mark-to-market bridge를 재현한다(`scripts/run_v104_2_jul30_crash_bridge.py:11-32`).
- 별도 시뮬레이션에서 주문 멱등성, timeout-after-accept 복구, 부분체결, 불일치 시 `HOLD_ONLY`를 검증한다(`src/quant_harness/v88_order_reconciliation/engine.py:241-290`, `:297-338`).
- 부모 2개 Paper 상태를 SQLite에 저장하고 백업·복구를 시험하는 별도 운영 모듈이 있다(`src/quant_harness/v85_operational_hardening/engine.py:46-67`, `:138-211`).

### 현재 불가능한 것

- 실제 브로커 계좌·주문·체결·거절·취소 상태를 사용하는 end-to-end 실행
- V87 증분 적재 결과를 V104 판단기가 직접 소비하는 단일 데이터 파이프라인
- V104 후보 3개의 지속형 격리 Paper 계좌와 재시작 복구
- 실제 broker-state reconciliation을 통과한 Forward 관측
- 60/120 신규 Forward 세션 기반 승격 검토
- 중앙 권한 게이트를 거친 제한적 Live 주문

외부 브로커 계약은 명시적으로 `UNVERIFIED_EXTERNAL`이다(`config/v101_broker_execution_contract.yaml:1-24`).

## 3. 실제 활성 실행 흐름

```text
scripts/run_v104_forward_session.py
  → forward_runtime.append_new_forward_observations
    → forward_runtime.build_session_observations
      → adapter.replay_candidate(parent + enabled candidates)
        → adapter.build_candidate_ledgers
          → V77 raw adjusted CSV loader
          → V94 strict universe/features
          → V95 D-1 regime
          → V69/V79 selectors + V98 selection policy helpers
          → V100 target ledgers
          → V102 flow/DART evidence policy
        → V101 synthetic execution replay
      → latest replay row의 target/order/NAV 비교
    → 동결일 이후일 때만 CSV append
```

근거:

- Forward 진입점: `scripts/run_v104_forward_session.py:7-19`
- 부모·후보 전체 replay: `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:44-72`
- 데이터·에이전트 조립: `src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:108-247`
- 실행 replay: `src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:250-288`, `src/quant_harness/v101_risk_execution_agent/engine.py:248-293`
- 역사행 차단: `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:73-74`, `:108-136`

### 문서의 직렬 흐름과 다른 점

`docs/ARCHITECTURE.md:7-24`는 V87→V94→…→V85→V86→V88→V89가 하나의 직렬 운영 경로처럼 표현한다. 실제 import/call 경로에는 V87, V85, V86, V88, V89, V103이 포함되지 않는다. 이 모듈들은 독립 스크립트·리포트 집계·테스트 경로로 존재한다.

- V87은 자체 스크립트에서만 직접 실행된다(`scripts/run_v87_actual_data_ingestion.py:1-5`).
- V88 `OrderCoordinator`는 V88 자체 실행과 테스트에서만 사용된다(`src/quant_harness/v88_order_reconciliation/engine.py:297-338`).
- V89는 별도 observation 파일을 관리하며 V104 Forward appender가 호출하지 않는다(`src/quant_harness/v89_forward_governance/engine.py:40-65`, `:110-130`).
- V86은 보고서·DB를 읽는 read-only 화면이다(`src/quant_harness/v86_control_plane_dashboard/engine.py:355-413`, `:446-488`).

## 4. 단계별 경로 추적

### 4.1 데이터 입력

**활성 V104 경로 — 확인됨**

- `config/v77_corrected_price_allocation.yaml:5-15`의 기간·원본 태그를 사용한다.
- `data/toss_v19c_daily/universe.csv`와 각 `*_1d.csv`를 직접 읽는다(`src/quant_harness/v77_corrected_price_allocation/engine.py:81-103`).
- benchmark `KS11`은 별도 장기 파일에서 읽는다(`src/quant_harness/v77_corrected_price_allocation/engine.py:122-130`).
- core ETF와 benchmark 날짜의 교집합을 거래 index로 사용한다(`src/quant_harness/v77_corrected_price_allocation/engine.py:132-136`).
- 거래 가능 가격은 forward-fill하지 않는다(`src/quant_harness/v77_corrected_price_allocation/engine.py:137-141`).

**V87 — 부분 구현·비연결**

- 실제 provider protocol, CSV fixture provider, Toss gateway wrapper가 있다(`src/quant_harness/v87_actual_data_ingestion/engine.py:23-116`).
- 품질·revision gate와 canonical 출력이 구현돼 있다(`:143-186`, `:189-291`).
- 그러나 표준 `run()`은 실제 gateway가 아니라 기존 CSV를 다시 읽는 `CsvFixtureProvider`를 사용한다(`:294-307`).
- V104는 V87의 설정상 출력 경로 `data/canonical/v87_market_bars.csv`(Clean Release에는 생성 파일 없음)가 아니라 원본 `data/toss_v19c_daily/*_1d.csv`를 직접 읽는다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:111-125`, `src/quant_harness/v77_corrected_price_allocation/engine.py:81-146`).

판정: **V87은 실제 데이터 계약 검증기로 구현됐지만 활성 판단 경로의 ingestion 단계로 연결되지 않았다.**

### 4.2 유니버스

- 현재 목록 자체는 정적 파일 `data/toss_v19c_daily/universe.csv`다(`src/quant_harness/v69_dynamic_theme_leadership/engine.py:100-109`).
- V94는 실제 관측 bar의 최초·최종일, history, coverage, liquidity로 날짜별 gate를 만들고 한 세션 shift한다(`src/quant_harness/v94_universe_agent/policy.py:27-78`).
- listing은 `OBSERVED_FIRST_BAR_PROXY`이며 완전한 상폐·기업행위 원장이 아님을 코드가 명시한다(`:48-57`).

판정: **날짜별 eligibility는 구현됐으나 universe membership 원천은 완전한 PIT가 아니다.**

### 4.3 시장 상태

- benchmark MA120, breadth, 변동성 후보를 계산하며 실행 필드는 모두 D-1이다(`src/quant_harness/v95_market_regime_agent/policy.py:32-51`, `:65-100`).
- 활성 부모는 `D1_MA120_EXPLICIT`이다(`config/strategy_registry_v84.yaml:52-64`).
- decision record는 `information_cutoff`과 `decision_uses_same_day_close=False`를 기록한다(`src/quant_harness/v95_market_regime_agent/policy.py:109-127`).

판정: **구현 및 활성 경로 연결.**

### 4.4 후보선정

- 활성 V104 어댑터는 V99 엔진을 import하지 않는다. V69/V79 selector와 V98 policy helper를 직접 호출한다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:14-22`, `:190-206`).
- V69은 월간 선택·주간 이탈, V79는 주간 persistent trend sleeve를 구현한다(`src/quant_harness/v69_dynamic_theme_leadership/engine.py:186-333`; `src/quant_harness/v79_generic_trend_sleeve/engine.py:86-239`).
- sector별 대표는 정적 taxonomy에서 D-1 최고점 ETF를 선택한다(`src/quant_harness/v98_candidate_selection_agent/policy.py:192-262`).
- V99는 후보 연구·ablation·promotion audit 엔진이며 현재 runtime callable 자체는 아니다(`src/quant_harness/v99_candidate_selection_deep_research/engine.py:774-937`).

판정: **기능은 연결돼 있으나 문서의 “활성 V99 엔진” 표현은 논리 버전명이다. 실제 런타임 구현은 V69/V79+V98에 분산돼 있다.**

### 4.5 목표비중·신호

- V100 policy는 V69과 V79 목표비중을 생성하고 정규화된 target hash를 기록한다(`src/quant_harness/v100_strategy_agent/policy.py:18-83`, `:86-179`).
- V104는 부모·후보의 target ledger를 동일 경로로 만든다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:207-247`).

판정: **구현 및 연결.**

### 4.6 시장증거

- 수급은 KOSPI 값을 거래 index에 맞추고 5일 누적·z-score를 D-1로 이동한다(`src/quant_harness/v102_market_evidence_agent/policy.py:74-105`).
- DART는 `received_at`을 사용해 각 날짜 전일까지 도착한 최신 공시만 반영하고 수정공시가 과거 period state를 대체한다(`:108-174`).
- 뉴스 schema·validator는 있으나 역사 데이터는 없다(`:176-216`; `config/v102_market_evidence_agent.yaml:13-16`).
- 부모의 활성 정책 `MARKET_EVIDENCE_DIAGNOSTIC_ONLY`는 목표를 변경하지 않는다(`config/strategy_registry_v84.yaml:124-147`; `src/quant_harness/v102_market_evidence_agent/policy.py:230-299`).

판정: **수급·DART는 구현·연결, 부모 자본경로에서는 진단 전용. 뉴스는 계약/validator만 있고 data-blocked.**

### 4.7 주문 의도·체결·NAV

- V101은 target 합계, 시가 누락, 매도 우선, D-1 ADV 참여율, 최소 주문금액, 현금 제한, 수수료·spread·impact를 처리한다(`src/quant_harness/v101_risk_execution_agent/engine.py:91-245`).
- 날짜별 target을 같은 날 open으로 synthetic fill하고 close로 NAV를 계산한다(`:248-293`).
- 실제 거래소 order lifecycle이나 broker buying power는 사용하지 않는다. 코드 자체가 필요한 외부 항목을 `BLOCK_LIVE` gap으로 기록한다(`:517-528`).

판정: **현실성 있는 일봉 체결 시뮬레이터이며 실제 주문·체결 엔진은 아니다.**

### 4.8 주문 제출·브로커 대조

- 공통 `BrokerGateway` protocol은 존재한다(`src/quant_harness/v72_integration_ready/contracts.py:13-75`).
- Toss client는 quote/candle/account/order 메서드를 갖지만 endpoint·field map이 외부 검증되지 않았다(`src/quant_harness/v72_integration_ready/toss_openapi.py:25-80`, `:256-448`).
- V88은 `SimulatedBrokerGateway`로만 동작한다(`src/quant_harness/v88_order_reconciliation/engine.py:45-145`, `:297-338`).
- V88 submit은 `dry_run=False`를 즉시 `PermissionError`로 차단한다(`:241-244`).
- V88은 V101 intents 또는 V104 Forward 경로에서 호출되지 않는다.

판정: **브로커 계약과 시뮬레이션은 있으나 실제 end-to-end 주문 경로는 미구현.**

### 4.9 상태 저장·재시작·복구

- V84 `DualPaperStore`와 V85 `OrchestratorState`가 SQLite로 부모 2개 계좌·단계 상태를 저장한다(`src/quant_harness/v84_dual_paper_parity/engine.py:323-347`; `src/quant_harness/v85_operational_hardening/engine.py:46-67`).
- V85는 과거를 선택일 전까지 다시 replay한 뒤 현일을 처리하고 DB backup/restore를 검증한다(`src/quant_harness/v85_operational_hardening/engine.py:138-207`).
- V104 Forward는 지속 계좌 DB를 사용하지 않고 매번 전체 replay한다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:50-56`, `:65-66`).
- V104 후보 3개의 `paper_account_id`는 observation/contract의 식별 문자열이며 영속 계좌 state와 연결되지 않는다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:90-112`).

판정: **부모 2개용 상태복구는 별도 구현, V104 후보 Forward 상태복구는 미구현.**

### 4.10 피드백·승격

- V103은 과거 시도 원장, multiple-testing audit, shadow registry를 생성하며 자동 자본 권한을 금지한다(`src/quant_harness/v103_review_feedback_agent/engine.py:505-588`, `:610-682`).
- V104는 과거 promotion CSV를 스캔해 양의 결과 inventory를 만들고, 고정된 `forward_adapter_priority`를 실행한다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:143-189`, `:401-427`).
- V104의 ReviewFeedback 인과 감사는 priority 3개와 1개의 route 차이를 비교하는 governance proxy다. 실제 V103 정책 실행이나 자동 학습으로 부모를 갱신하지 않는다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:212-230`).
- Forward appender는 V103/V89 평가를 호출하지 않는다.

판정: **연구 메모리·승격 규칙은 구현됐지만 피드백은 폐쇄형 자동 개선 루프가 아니라 보고·라우팅 거버넌스다.**

## 5. 구현 상태 분류표

| 영역 | 판정 | 근거 |
|---|---|---|
| V77 조정 일봉 loader | 구현·연결 | `src/quant_harness/v77_corrected_price_allocation/engine.py:81-146`, `src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:108-125` |
| V87 provider ingestion | 부분 구현·비연결 | `src/quant_harness/v87_actual_data_ingestion/engine.py:23-116`, `:294-307` |
| V94 시점 gate | 구현·연결, 원천 제한 | `src/quant_harness/v94_universe_agent/policy.py:9-79` |
| V95 regime | 구현·연결 | `src/quant_harness/v95_market_regime_agent/policy.py:32-135` |
| V99 CandidateSelection | 연구 엔진; runtime 명칭과 구현 분리 | `src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:14-22`, `:190-206` |
| V100 target ledger | 구현·연결 | `src/quant_harness/v100_strategy_agent/policy.py:43-179` |
| V102 flow/DART | 구현·연결, 부모는 진단 전용 | `src/quant_harness/v102_market_evidence_agent/policy.py:74-174`, `:230-299` |
| V102 news | 계약/validator만 존재 | `src/quant_harness/v102_market_evidence_agent/policy.py:176-216` |
| V101 synthetic execution | 구현·연결 | `src/quant_harness/v101_risk_execution_agent/engine.py:109-293` |
| V88 broker journal/reconcile | 구현·분리·simulator only | `src/quant_harness/v88_order_reconciliation/engine.py:236-338` |
| V85 parent state recovery | 구현·분리 | `src/quant_harness/v85_operational_hardening/engine.py:138-211` |
| V86 UI | read-only 집계 | `src/quant_harness/v86_control_plane_dashboard/engine.py:377-413`, `:446-488` |
| V89 frozen governance | 구현·별도 observation stream | `src/quant_harness/v89_forward_governance/engine.py:40-182` |
| V103 feedback | 연구/거버넌스, 자본 권한 없음 | `src/quant_harness/v103_review_feedback_agent/engine.py:577-588`, `:663-682` |
| V104 candidate Forward | 전체 replay+CSV append, 0 신규 세션 | `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:44-160` |
| 실제 broker-state incremental runner | 미구현 | `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:50-56`; `src/quant_harness/v101_risk_execution_agent/engine.py:517-528` |
| 실제 Live 주문 | 활성 경로 미구현·기본 차단 | `config/active_strategy.yaml:3-5`; `src/quant_harness/v88_order_reconciliation/engine.py:241-244` |

## 6. 장식성·오해 가능 구현

1. `build_session_observations`는 외부 데이터 freshness나 broker reconciliation을 수행하지 않으면서 `data_gate_passed=True`, `reconciliation_passed=True`를 고정 기록한다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:108-112`). 이는 **결정론적 replay 내부 정합성 표식**이지 실제 운영 gate 결과가 아니다.
2. V104 adapter gate의 `adapter_implemented_and_tested`는 테스트 결과를 동적으로 조회하지 않고 `True`로 설정된다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:404-416`).
3. V104 후보의 `paper_account_id`는 식별자이며 독립 영속 계좌가 생성되는 코드는 Forward 경로에 없다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:90-112`).
4. V104 ReviewFeedback 인과성은 route list 길이 변화로 증명한다. 실제 feedback agent가 의사결정 결과를 학습해 다음 신호를 바꾸는 검증이 아니다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:221-230`).
5. Docker 시작 스크립트는 V85/V89 실패를 `|| true`로 무시한다(`scripts/docker_entrypoint.sh:4-9`). 화면은 계속 뜰 수 있으므로 readiness 실패를 서비스 시작 실패와 동일하게 취급하지 않는다.

## 7. 문서와 구현의 주요 충돌

| 문서 주장 | 구현 사실 | 판정 |
|---|---|---|
| V87부터 V89까지 하나의 직렬 실행 흐름 (`docs/ARCHITECTURE.md:7-24`) | V104 adapter import와 Forward 호출은 V77/V94/V95/V69/V79/V98/V100/V102/V101만 조립하며 V87/V85/V86/V88/V89를 호출하지 않음 (`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:14-22`, `:108-288`; `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:44-72`) | 문서 과장 |
| 활성 CandidateSelection 버전 V99 (`docs/ARCHITECTURE.md:34-35`) | V104 runtime은 V69/V79 selector와 V98 helper를 직접 사용 (`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:14-22`, `:190-206`) | 논리 버전명; 코드 모듈 불일치 |
| V104 후보가 고유 Paper account를 사용 (`docs/ARCHITECTURE.md:61-63`) | Forward row에는 account ID 문자열만 기록되고 전체 replay 결과에서 관측을 생성함 (`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:44-56`, `:90-112`) | 부분 구현 |
| 주문 submit 권한이 차단 (`README.md:9`) | V88은 차단하지만 Toss client는 `TOSS_ALLOW_LIVE_ORDERS=true`이면 non-dry-run을 허용함 (`src/quant_harness/v88_order_reconciliation/engine.py:241-244`; `src/quant_harness/v72_integration_ready/toss_openapi.py:367-411`) | 기본 상태는 맞지만 절대적 하드락 아님 |
| V85→V88이 상태·주문 정합성을 연결 (`docs/ARCHITECTURE.md:19-23`) | V85는 V84 `DualPaperStore`를 사용하고 V88은 자체 `SimulatedBrokerGateway`를 생성함 (`src/quant_harness/v85_operational_hardening/engine.py:138-207`; `src/quant_harness/v88_order_reconciliation/engine.py:297-338`) | 비연결 |

## 8. 현재 Live 차단 판정

### 확인된 차단

- 활성 설정: `runtime_mode: PAPER`, `live_execution_allowed: false` (`config/active_strategy.yaml:1-5`).
- Registry: `live_execution_allowed: false` (`config/strategy_registry_v84.yaml:1-4`).
- V104 config와 runtime contract: Live false (`config/v104_end_to_end_causal_challenger_audit.yaml:1-6`; `config/v104_challenger_runtime_contract.yaml:51-53`).
- V88 coordinator: non-dry-run을 무조건 차단 (`src/quant_harness/v88_order_reconciliation/engine.py:241-244`).
- V86: POST를 403으로 거절 (`src/quant_harness/v86_control_plane_dashboard/engine.py:487-488`).
- compose 기본 환경: `TOSS_ALLOW_LIVE_ORDERS=false` (`compose.yaml:12-16`, `:28-31`).

### 잔여 위험

저수준 `TossOpenApiClient`는 `TOSS_ALLOW_LIVE_ORDERS=true`이면 non-dry-run 주문과 취소를 허용한다(`src/quant_harness/v72_integration_ready/toss_openapi.py:108-140`, `:367-411`, `:436-448`). 이 client는 현재 활성 실행 경로에서 호출되지 않으므로 **현재 시스템은 Live를 실행하지 않는다**. 다만 중앙 설정·사람 승인·broker contract status를 client 내부에서 재검증하지 않기 때문에 **환경변수 오설정에 대한 방어층은 충분하지 않다**.

## 9. 최종 AS-IS 판정

Quant Harness V104.2는 **상당히 정교한 일봉 기반 연구·synthetic Paper replay 하네스**다. D-1 causal feature, 비용, ADV, 후보 fingerprint, input hash, future mutation, 역사/Forward 분리 규칙은 실제 코드로 존재한다. 그러나 실제 데이터 증분 적재, 지속형 후보 계좌, 주문 journal, 실제 broker polling/reconciliation, 상태복구, Forward 승격이 하나의 운영 transaction으로 연결된 시스템은 아니다.

따라서 현재 정확한 표현은 다음과 같다.

> **“7-agent 논리 경로를 결정론적으로 replay하는 연구·Paper 분석 시스템이며, 실브로커 통합 전 단계의 독립 운영 모듈과 계약 검증기가 함께 존재한다. Live 자동매매 시스템은 아직 아니다.”**

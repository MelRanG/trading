# IMPLEMENTATION ROADMAP

## 1. 원칙

이 로드맵은 전략·알파·임계값을 바꾸지 않고, 현재 분리된 데이터·상태·브로커·Forward 경로를 연결하기 위한 순서다.

- 버그 수정과 전략 변경을 같은 작업에서 수행하지 않는다(`AGENTS.md:10-12`).
- 각 단계는 이전 단계의 immutable evidence와 회귀 테스트를 요구한다.
- Live는 마지막 단계이며 자동 승격하지 않는다.
- 역사 성과를 개선하는 작업보다 운영 사실성과 fail-closed를 우선한다.

## 2. 우선순위 개요

| 단계 | 목적 | 현재 출발점 | 완료 산출물 | Live 상태 |
|---|---|---|---|---|
| P0 | 기준선 봉인·감사 재현 | V104.2 Clean Release | source/config/data manifest, clean test baseline | BLOCKED |
| P1 | 단일 authoritative data path | V87와 V104 비연결 | V87→canonical manifest→V104 | BLOCKED |
| P2 | 증분 결정 engine | 전체 replay Forward | session-scoped deterministic runner | BLOCKED |
| P3 | 지속형 Paper state | V85 부모 2개 DB | 부모+후보 account/state recovery | BLOCKED |
| P4 | 실제 broker read-only | Toss 골격 | quote/account/order 조회 검증 | BLOCKED |
| P5 | dry-run order integration | V88 simulator | V101→V88→broker dry-run transaction | BLOCKED |
| P6 | 실제 Paper reconciliation | 없음 | fills/account reconciliation·HOLD_ONLY | BLOCKED |
| P7 | 신규 Forward 검증 | 0세션 | 60/120 session evidence | BLOCKED |
| P8 | 제한적 canary 준비 | 미구현 | signed approval + hard limits | HUMAN DECISION |

## 3. P0 — 기준선 봉인

### 작업

1. 현재 `src/`, `scripts/`, `config/`, `data/`, `tests/` SHA-256 manifest를 별도 immutable artifact로 보존한다.
2. V104 candidate fingerprint와 input hash에 source code, benchmark, ETF mapping, dependency lock hash를 포함할 설계안을 작성한다. 현재 누락 근거는 `src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:77-105`다.
3. `.v104_cache`와 `.v101_cache`에 manifest hash를 저장하고 불일치 시 재계산하도록 별도 버그 수정 작업을 계획한다. 현재 V104 cache는 검증 없이 로드한다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:349-367`).
4. 현재 핵심 테스트와 Forward fail-closed 결과를 baseline으로 고정한다.

### 완료 조건

- 동일 manifest에서 동일 target/order/NAV
- source/config/data 하나라도 바뀌면 cache reuse 거부
- 전략 수치 변화 없음

## 4. P1 — V87을 authoritative ingestion으로 연결

### 작업

1. actual provider adapter와 credential-free fixture adapter를 명시적으로 분리한다(`src/quant_harness/v87_actual_data_ingestion/engine.py:23-116`).
2. V87 canonical output과 manifest를 session별 append-only로 만든다.
3. V104 active loader가 raw directory가 아니라 검증된 canonical manifest만 소비하게 하는 변경을 별도 작업으로 수행한다.
4. universe, benchmark, flow, DART, ETF mapping을 하나의 session input manifest에 포함한다.
5. stale/missing/revision failure면 session 실행을 시작하지 않는다.

### 완료 조건

- raw→archive→validate→revision gate→canonical→manifest→V104 한 경로
- V87 output을 건너뛰는 실행 불가
- 각 session의 source/retrieved_at/hash 보존
- 현재 역사 replay parity 유지

## 5. P2 — session-scoped 증분 결정 engine

### 현재 문제

Forward는 매번 전체 역사 replay를 수행한다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:44-56`, `:65-66`).

### 작업

1. 입력: `session`, frozen candidate IDs, prior state, authoritative input manifest.
2. 출력: universe snapshot, regime row, selection row, target ledger row, decision hash.
3. full replay와 incremental result의 동일 session parity test를 만든다.
4. session이 이미 처리됐다면 동일 결과만 허용하고 충돌 시 fail-closed한다.

### 완료 조건

- 부모·후보 target hash가 full replay와 일치
- 미래 session 파일 추가가 과거 result를 바꾸지 않음
- `data_gate_passed`가 실제 ingestion gate에서 계산됨

## 6. P3 — 부모·후보 지속형 Paper state 통합

### 작업

1. V84/V85의 SQLite account/state model을 부모 2개와 V104 후보 3개에 일반화한다(`src/quant_harness/v84_dual_paper_parity/engine.py:323-347`; `src/quant_harness/v85_operational_hardening/engine.py:138-207`).
2. account ID 문자열을 실제 state row와 foreign key로 연결한다.
3. decision, target, intent, fill, cash, holdings, NAV, checkpoint를 한 transaction schema로 정의한다.
4. backup/restore, WAL recovery, idempotent rerun, partial session rollback을 검증한다.

### 완료 조건

- 재시작 전후 holdings/cash/NAV 동일
- 후보별 state 완전 격리
- 중간 실패 후 중복 주문 intent 없음
- parent historical parity 유지

## 7. P4 — 실제 브로커 read-only 검증

### 작업

1. Toss endpoint/field map을 실제 문서와 sandbox response로 확정한다(`src/quant_harness/v72_integration_ready/toss_openapi.py:25-80`).
2. quote, calendar, account, holdings, list_orders만 활성화한다.
3. raw response archive와 schema/version을 저장한다.
4. unknown status/field/timezone/stale response는 fail-closed한다.
5. 계좌 allowlist와 read-only credential을 사용한다.

### 완료 조건

- actual account/holding/order snapshot 재현
- timestamp timezone과 freshness 검증
- 어떠한 create/cancel 호출도 불가능
- external contract status를 `VERIFIED_READ_ONLY`로만 변경

## 8. P5 — dry-run 주문 transaction 연결

### 작업

1. V101 final intent를 V88 `OrderIntent`로 변환한다.
2. `client_order_id = hash(environment, account, strategy, candidate, session, decision_hash, symbol, side)` 형태의 deterministic key를 사용한다.
3. V88 journal persist 후 broker dry-run/create validation endpoint를 호출한다.
4. timeout-after-accept, duplicate, partial, reject, unknown을 fixture로 검증한다.
5. V88와 Toss client가 동일 gateway interface를 구현하도록 한다.

### 완료 조건

- 동일 intent 재실행 시 broker submit 1회
- 다른 intent의 ID 재사용 차단
- transport unknown은 조회로만 복구하고 blind retry 금지
- Live flag false 유지

## 9. P6 — 실제 Paper 주문·체결·reconciliation

### 작업

1. 별도 Paper 계좌 또는 증권사 sandbox에서 최소 수량 주문을 사용한다.
2. order lifecycle을 `data/contracts/v101_execution_observation_template.csv` schema로 저장한다.
3. fills, fee, tax, buying power, settlement를 internal state와 대조한다.
4. mismatch·stale·unknown이면 `HOLD_ONLY`를 state에 영속화한다.
5. kill switch가 최종 submit gate에서 강제되도록 한다.

### 완료 조건

- `reconciliation_passed`가 실제 broker snapshot에서 계산
- restart 후 미완료 order 상태 복구
- mismatch 후 신규 주문 0건
- 수동 승인 없이는 HOLD_ONLY 해제 불가

## 10. P7 — 신규 Forward 증거 수집

### 작업

1. frozen code/config/data contract manifest를 생성한다.
2. 부모 2개+후보 최대 3개를 동일 session input으로 실행한다.
3. target/order/fill/cost/NAV/reconciliation을 매 세션 append-only 저장한다.
4. V89와 V103이 동일 observation stream을 읽도록 통합한다. 현재는 별도 파일을 사용한다(`src/quant_harness/v89_forward_governance/engine.py:59-65`; `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:14`).
5. changed decision, matured 20d/60d, data failures, reconciliation failures를 자동 계산한다.

### 완료 조건

- 최소 60 신규 session에서 평가 가능
- 권장 120 session과 최소 changed decisions 충족 전 promotion review 금지
- 역사 replay 행 0개
- fingerprint/input/source manifest conflict 0개

## 11. P8 — 제한적 canary 검토

이 단계는 구현 완료가 아니라 사람의 승인 단계다.

### 선행 조건

- broker contract verified
- P7 gate 통과
- 실제 비용·세금·capacity calibration
- 중앙 live authority service
- signed promotion decision
- 계좌·종목·일일 notional·손실·주문수 제한
- emergency kill switch와 독립 모니터링

### 권장 단계

1. `READ_ONLY`
2. `ORDER_DRY_RUN`
3. `MANUAL_CONFIRM_EACH_ORDER`
4. 소액 canary
5. 확대 여부 재심사

자동 Champion/Live 승격은 계속 금지한다.

## 12. 별도 결함 수정 backlog

다음은 전략 변경 없이 별도 티켓으로 처리해야 한다.

| ID | 결함 | 근거 | 우선순위 |
|---|---|---|---|
| B-01 | V104 Forward의 data/reconciliation flag hard-coded | `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:108-112` | P0 |
| B-02 | V104 cache provenance 미검증 | `src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:349-367` | P0 |
| B-03 | V104 input hash에 benchmark/mapping/source code 미포함 | `src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:77-105` | P0 |
| B-04 | V87 canonical이 V104에 비연결 | `src/quant_harness/v87_actual_data_ingestion/engine.py:267-307`; `src/quant_harness/v77_corrected_price_allocation/engine.py:81-146` | P1 |
| B-05 | V104 후보 persistent account 없음 | `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:90-112` | P3 |
| B-06 | V88가 V101/Toss에 비연결 | `src/quant_harness/v88_order_reconciliation/engine.py:236-338` | P5 |
| B-07 | Toss live authority가 env flag 하나에 의존 | `src/quant_harness/v72_integration_ready/toss_openapi.py:140`, `:367-411` | P4/P5 |
| B-08 | V89/V103/V104 observation streams 분리 | `src/quant_harness/v89_forward_governance/engine.py:59-65`; `src/quant_harness/v103_review_feedback_agent/engine.py:264-266`; `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:14` | P7 |
| B-09 | Docker startup governance 오류 은폐 | `scripts/docker_entrypoint.sh:4-9` | P0 |
| B-10 | current taxonomy/mapping을 역사 전체에 적용 | `src/quant_harness/v98_candidate_selection_agent/policy.py:192-208`; `src/quant_harness/v102_market_evidence_agent/policy.py:108-130` | 데이터 사업 |

## 13. Codex 인수 권장 첫 작업

첫 Codex 개발 작업은 전략 개선이 아니라 다음 하나의 vertical slice가 적합하다.

> **“V87 canonical manifest를 입력으로 사용해 한 신규 session의 부모·후보 target을 증분 생성하고, persistent Paper state에 저장하되 주문 제출은 하지 않는 경로.”**

이 작업은 P1~P3의 최소 연결을 검증하며, 현재 알파·임계값·성과 기대값을 바꾸지 않는다.

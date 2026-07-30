# BROKER INTEGRATION GAPS

## 1. 현재 브로커 관련 구현 층

### 1.1 공통 계약

`src/quant_harness/v72_integration_ready/contracts.py:13-75`에 quote, holding, account, order dataclass와 `BrokerGateway` protocol이 있다.

판정: **계약 골격 구현.**

### 1.2 Toss OpenAPI client

`src/quant_harness/v72_integration_ready/toss_openapi.py`는 다음 메서드를 가진다.

- token/HTTP transport: `:143-232`
- health: `:233-255`
- quote: `:256-276`
- daily candles/calendar: `:277-331`
- account: `:332-366`
- create order: `:367-411`
- list/cancel: `:413-448`

endpoint와 field map은 JSON override가 가능하며 기본 mapping은 외부 계약 검증 결과가 아니다(`:25-80`).

판정: **저수준 client 골격은 있으나 실제 증권사 계좌에서 검증되지 않았다.**

### 1.3 V101 execution

V101은 목표비중을 synthetic fills로 바꾸는 backtest/Paper 모델이다(`src/quant_harness/v101_risk_execution_agent/engine.py:109-293`). `BrokerGateway`를 호출하지 않는다.

판정: **브로커 실행 아님.**

### 1.4 V88 reconciliation

V88은 persist-before-submit, idempotent client ID, timeout recovery, partial fill, position reconciliation을 구현한다(`src/quant_harness/v88_order_reconciliation/engine.py:147-290`). 표준 실행은 `SimulatedBrokerGateway`만 사용한다(`:297-338`).

판정: **broker lifecycle 설계 검증용 simulator.**

## 2. 현재 활성 주문 경로

실제 활성 V104 경로는 다음에서 끝난다.

```text
V100 target ledger
 → V101 synthetic order/fill/account DataFrame
 → V104 target/order signature/NAV observation
```

근거: `src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:250-288`, `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:90-113`.

다음 연결은 없다.

```text
V101 intent
  -X→ V88 OrderCoordinator
  -X→ TossOpenApiClient
  -X→ broker account polling
  -X→ V85/V104 state commit
```

저장소 검색상 `OrderCoordinator`는 V88 자체 코드와 테스트에서만 생성되며, `TossOpenApiClient`는 다른 실행 모듈에서 instantiate되지 않는다.

## 3. Live 차단 상태

### 강하게 차단된 경로

- active config Paper/false: `config/active_strategy.yaml:1-5`
- registry Live false: `config/strategy_registry_v84.yaml:1-4`
- V88 non-dry-run은 무조건 예외: `src/quant_harness/v88_order_reconciliation/engine.py:241-244`
- V86 POST 403: `src/quant_harness/v86_control_plane_dashboard/engine.py:487-488`
- compose env false: `compose.yaml:12-16`, `:28-31`

### 잠재 우회

`TossOpenApiClient`는 `TOSS_ALLOW_LIVE_ORDERS=true`일 때 non-dry-run을 허용한다(`src/quant_harness/v72_integration_ready/toss_openapi.py:140`, `:367-411`). 다음을 재확인하지 않는다.

- `config/active_strategy.yaml`의 mode
- `RELEASE_STATE.json`의 broker contract status
- V89 60/120 session gate
- signed human approval
- account allowlist/notional limit
- kill switch state
- V88 reconciliation mode

판정: **현재 활성 시스템은 Live를 호출하지 않지만, 저수준 client는 중앙 정책으로 하드락돼 있지 않다.**

## 4. 필수 통합 공백

### G-01 실제 endpoint·field mapping 검증

- 현재 계약 상태: `UNVERIFIED_EXTERNAL` (`config/v101_broker_execution_contract.yaml:1-24`).
- 필요한 증거: sandbox/real account의 raw response, status enum, timestamp timezone, reject codes.
- 완료 조건: quote/account/order/list/cancel fixture가 실제 response와 round-trip되며 unknown field/status는 fail-closed.

### G-02 V101 intent→V88 journal 변환

- V101 intent에는 requested/cap/final/reason이 있다(`src/quant_harness/v101_risk_execution_agent/engine.py:165-171`, `:220-226`).
- V88 `OrderIntent`에는 strategy, client ID, symbol, side, quantity, reason, dry_run이 있다(`src/quant_harness/v88_order_reconciliation/engine.py:25-35`).
- 두 schema를 연결하는 mapper와 deterministic client order ID 생성기가 없다.

완료 조건: 동일 decision hash+session+strategy+symbol+side가 항상 동일 ID를 만들고 다른 intent는 충돌해야 한다.

### G-03 persist-before-submit의 실제 gateway 적용

V88 coordinator는 simulator gateway에만 연결된다(`src/quant_harness/v88_order_reconciliation/engine.py:297-305`). Toss client가 V88의 gateway protocol과 실제로 호환되는지 통합 테스트가 없다.

완료 조건: timeout-after-accept를 실제 sandbox fixture로 재현하고 broker `list_orders`로 단일 주문을 회수한다.

### G-04 실제 order lifecycle

현재 synthetic fill에는 exchange timestamps, partial remaining, cancel/reject가 없다. 필요한 schema는 `data/contracts/v101_execution_observation_template.csv`에 정의돼 있다.

완료 조건: NEW→ACCEPTED→PARTIAL→FILLED/CANCELED/REJECTED/UNKNOWN 전이를 append-only event로 저장하고 평균가격·잔량을 재구성한다.

### G-05 broker account reconciliation 연결

V88 mismatch→HOLD_ONLY는 구현돼 있지만 별도 simulator 결과다(`src/quant_harness/v88_order_reconciliation/engine.py:269-290`). V104 Forward의 `reconciliation_passed`는 항상 True다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:108-112`).

완료 조건:

- 주문 전 account freshness 확인
- 주문 후 order/fill/account polling
- internal cash/holdings와 broker 값을 tolerance 내 비교
- mismatch/unknown이면 다음 신규 주문 차단
- 수동 해제 전까지 `HOLD_ONLY` 지속

### G-06 증분 상태와 재시작 복구

V85 SQLite는 부모 2개 synthetic state용이고 V104 후보와 broker order journal이 분리돼 있다(`src/quant_harness/v85_operational_hardening/engine.py:138-207`).

완료 조건: 하나의 session transaction이 decision→intent→submit→poll→reconcile→NAV→feedback checkpoint를 갖고 재시작 시 미완료 단계부터 재개한다.

### G-07 market session·tick·price limit

V101은 adjusted open 기준 시장가형 synthetic price를 사용한다. 실제 tick size, auction, halt, price limit, session window가 없다. 코드도 Live blocker로 열거한다(`src/quant_harness/v101_risk_execution_agent/engine.py:517-528`).

### G-08 fee/tax/settlement

설정의 bps는 backtest 가정이다(`config/v77_corrected_price_allocation.yaml:31-47`). 실제 account/product/date별 수수료·세금·결제·reserved cash를 reconciliation해야 한다.

### G-09 data freshness와 quote/account as-of

V104 input은 일봉 파일 hash로 봉인하지만 주문 전 quote/account timestamp gate가 없다. V101 gap register도 freshness를 요구한다(`src/quant_harness/v101_risk_execution_agent/engine.py:525-527`).

### G-10 kill switch의 중앙화

V85 risk config에 kill switch가 있으나 V88/Toss client가 이를 읽지 않는다(`src/quant_harness/v85_operational_hardening/engine.py:93-113`; `config/v85_operations.yaml`).

완료 조건: 주문 client 직전의 최종 권한 gate가 kill switch, mode, contract status, approval, account, daily loss, reconciliation 상태를 모두 확인한다.

## 5. 부분 구현·장식성 판정

| 기능 | 현재 모습 | 실제 준비도 |
|---|---|---|
| Paper account ID | V104 contract에 문자열 존재 | 영속 broker/Paper account 아님 |
| reconciliation passed | V104 row에서 True 고정 | 실제 broker 대조 아님 |
| adapter tested | V104 gate에서 True 고정 | 테스트 실행 상태를 runtime이 확인하지 않음 |
| broker gateway | Protocol+Toss client+simulator | 하나의 production adapter로 연결 안 됨 |
| order idempotency | V88 SQLite에서 검증 | Toss 실주문 경로 미적용 |
| state recovery | V85 부모 DB backup/restore | 후보·주문·broker state와 transaction 통합 안 됨 |
| canary eligibility | V89 계산 가능 | V104 Forward observations와 자동 연동 안 됨 |

## 6. 보안·운영 관찰

1. Control plane은 read-only여서 직접 주문 위험은 낮다(`src/quant_harness/v86_control_plane_dashboard/engine.py:446-488`).
2. remote bind는 env flag가 필요하지만 compose가 이를 true로 둔다(`src/quant_harness/v86_control_plane_dashboard/engine.py:496-502`; `compose.yaml:17`). 현재 read-only라 주문 위험은 없으나 운영 정보 노출 통제는 별도 인증이 없다.
3. Docker entrypoint는 V85/V89 실패를 무시하고 UI를 시작한다(`scripts/docker_entrypoint.sh:4-9`). readiness가 실패해도 컨테이너 health가 살아 있을 수 있다.
4. Toss live flag 하나가 최종 submit 방어선이 될 수 있으므로 secret/env 관리 실수에 취약하다.

## 7. Live 진입 전 절대 blocker

- 실제 broker contract verified
- 중앙 mode/approval/kill-switch gate
- actual-data incremental ingestion과 freshness
- deterministic client order ID
- persist-before-submit 실제 통합
- timeout recovery와 duplicate prevention
- partial/reject/cancel/unknown state machine
- account/order/fill reconciliation
- mismatch HOLD_ONLY의 다음 session 지속
- crash-safe transaction recovery
- 최소 60 신규 Forward 세션, 120세션 promotion review
- 실제 비용·세금·capacity calibration
- 사람 승인

현재는 위 조건 중 설계·simulator 수준 일부만 충족한다. 따라서 **Live는 계속 차단해야 한다.**

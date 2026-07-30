# Contracts

Markdown는 계약을 복제하지 않고 의미와 원본 위치만 설명한다. 실제 필드·임계값은 아래 YAML·JSON·CSV·Python 정의를 따른다.

## 시스템 불변조건

- D-1 또는 해당 시점에 실제 이용 가능했던 입력만 사용한다.
- 부모와 후보는 동일 session·동일 input hash를 사용한다.
- candidate fingerprint, target hash, order signature를 보존한다.
- 누락·stale·revision 불명·시점 불명 데이터는 보간하지 않고 차단한다.
- 역사 replay는 신규 Forward 관측이 아니다.
- 내부 상태와 브로커 상태 불일치 시 신규 주문을 차단한다.
- 자동 부모 변경·Champion 승격·Live 승격은 금지한다.

불변조건의 실행 원본은 V104/V88/V89 코드와 다음 설정이다.

- [`config/v104_end_to_end_causal_challenger_audit.yaml`](../config/v104_end_to_end_causal_challenger_audit.yaml)
- [`config/v104_challenger_runtime_contract.yaml`](../config/v104_challenger_runtime_contract.yaml)
- [`config/v88_order_reconciliation.yaml`](../config/v88_order_reconciliation.yaml)
- [`config/v89_forward_governance.yaml`](../config/v89_forward_governance.yaml)

## 데이터 입력과 시점 기준

- V87 원본 계약: [`config/v87_actual_data_ingestion.yaml`](../config/v87_actual_data_ingestion.yaml)
- 시장 데이터 원본: `data/toss_v19c_daily/`
- 시점 유니버스 원본: `data/toss_v19c_daily/universe.csv`; 현재 listing lifecycle은 observed-first-bar proxy이며 완전한 공식 PIT 원장이 아니다.
- MarketEvidence 계약: [`config/v102_market_evidence_contract.yaml`](../config/v102_market_evidence_contract.yaml)
- 통합 관측 템플릿: `data/contracts/v102_market_evidence_observation_template.csv`
- 뉴스 템플릿: `data/contracts/v102_news_evidence_template.csv`
- 실행 관측 템플릿: `data/contracts/v101_execution_observation_template.csv`
- 후보 Forward 템플릿: `data/contracts/v104_challenger_forward_observation_template.csv`

V87의 required columns, revision gate, 조정가격 정책과 품질 임계값은 설정 원본을 그대로 사용한다. MarketRegime과 선택 판단은 same-day close를 사용하지 않으며 미래변조 검사로 확인한다.

## 주문 요청 계약

Python 원본:

- [`src/quant_harness/v72_integration_ready/contracts.py`](../src/quant_harness/v72_integration_ready/contracts.py): `BrokerGateway`, `BrokerOrder`, `BrokerAccount`
- [`src/quant_harness/v88_order_reconciliation/engine.py`](../src/quant_harness/v88_order_reconciliation/engine.py): `OrderIntent`, `OrderJournal`, `OrderCoordinator`
- [`src/quant_harness/v101_risk_execution_agent/engine.py`](../src/quant_harness/v101_risk_execution_agent/engine.py): target-to-order/fill replay

주문은 양의 정수 수량, 명시적 side·symbol·reason·`client_order_id`를 요구한다. V88은 intent를 submit 전에 저장하고 dry-run이 아닌 요청을 거부한다.

## 브로커 응답 계약

브로커 응답의 정규화 원본은 `BrokerOrder`와 `BrokerAccount` dataclass다. 실제 Toss endpoint/field map은 [`src/quant_harness/v72_integration_ready/toss_openapi.py`](../src/quant_harness/v72_integration_ready/toss_openapi.py)가 외부 JSON map을 읽도록 돼 있다.

외부 확인 목록과 현재 상태는 [`config/v101_broker_execution_contract.yaml`](../config/v101_broker_execution_contract.yaml)이 원본이다. 현재 `status: UNVERIFIED_EXTERNAL`, `broker_name: UNMAPPED`, `live_execution_allowed: false`다.

## 주문 멱등성

- 동일 `client_order_id`는 같은 주문 의도를 식별한다.
- submit 전에 journal에 저장한다.
- transport error 후 broker order 목록에서 같은 ID를 조회한다.
- 이미 수락된 주문을 중복 submit하지 않는다.
- 동일 session/candidate Forward 행이 다른 내용으로 재입력되면 idempotency conflict로 중단한다.

구현 원본은 V88 `OrderCoordinator.submit`과 V104 `append_new_forward_observations`다.

## 체결·포지션·NAV 정합성

- expected holdings/cash와 broker account를 대조한다.
- 수량 허용오차와 현금 허용오차는 [`config/v88_order_reconciliation.yaml`](../config/v88_order_reconciliation.yaml)이 원본이다.
- material mismatch는 `HOLD_ONLY`, 자동 재주문 금지다.
- 음수 현금, 미확인 ADV, 누락 open, 비정상 gap, risk limit 위반은 실행을 차단한다.
- 후보 관측은 target hash, order signature, NAV, cash, data gate, reconciliation 결과를 함께 기록한다.

## 환경 분리

- 활성 전략 설정: [`config/active_strategy.yaml`](../config/active_strategy.yaml)
- 운영 설정: [`config/v85_operations.yaml`](../config/v85_operations.yaml)
- Docker 기본값: `QUANT_HARNESS_MODE=PAPER`; `TOSS_ALLOW_LIVE_ORDERS`는 현재 build에서 권한을 부여하지 않는다.
- Paper 계정과 후보 계정은 각각 고유 ID와 상태 저장소를 사용한다.
- Live 계약 인터페이스는 build capability, 검증된 broker contract, account allowlist, 주문 금액·횟수 제한, 정상 reconciliation, 정상 kill switch, 명시적 승인, idempotency key, Paper/Live 환경 분리를 모두 요구한다.
- 현재 release는 build capability와 최종 Live 권한을 항상 `false`로 평가하므로 환경변수·credential·저수준 Toss client 호출로 주문할 수 없다.

## Fail-closed 정책

다음 중 하나면 주문 또는 승격을 중단한다.

- 시점·출처·원본 hash가 불명확한 데이터
- 후보 fingerprint 또는 부모/후보 input hash 불일치
- stale quote/account, 누락된 fee/tax/reject/cancel mapping
- broker/internal holdings·cash 불일치
- 동일 키의 다른 내용 재입력
- frozen strategy/config hash 변경
- 동결 이후 신규 관측 부족
- `UNVERIFIED_EXTERNAL` 계약 또는 Live flag 차단

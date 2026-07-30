# Architecture

## 현재 구현 구조

### 실행 흐름

```text
원본/계약 데이터
  └─ V87 Actual Data Ingestion: provider·조정 OHLCV·revision·품질 검사
       └─ V94 UniverseAgent: 시점별 eligibility
            └─ V95 MarketRegimeAgent: D-1 시장 상태
                 └─ V99 CandidateSelectionAgent: 리더·sleeve 후보 선택
                      └─ V100 StrategyAgent: 목표비중·target hash
                           └─ V102 MarketEvidenceAgent: 수급·공시·뉴스 증거
                                └─ V101 RiskExecutionAgent: 주문 의도·비용·체결 replay
                                     └─ V104 Registry Adapter: 부모/후보 실행 dispatch
                                          ├─ V84 공통 Paper replay
                                          └─ V104 후보별 격리 Paper observation
                                               └─ V85 운영 상태·위험·백업
                                                    └─ V86 Control Plane
                                                         └─ V88 주문 journal·멱등성·대조
                                                              └─ V104 ReviewFeedback governance
                                                                   └─ V89 Frozen Forward governance
```

활성 Registry는 [`config/strategy_registry_v84.yaml`](../config/strategy_registry_v84.yaml)이며 V69/V79 부모를 `quant_harness.v104_end_to_end_causal_challenger_audit.adapter`로 dispatch한다. `build_strategy_ledgers_legacy`는 부모 parity 확인용으로만 남아 있다.

### 활성 에이전트와 권한

| 에이전트 | 버전 | 현재 역할 | 자본 권한 |
|---|---|---|---|
| UniverseAgent | V94 | 시점별 거래 가능 유니버스 | 목표 변경 가능 |
| MarketRegimeAgent | V95 | D-1 기준 risk-on/off | 목표 변경 가능 |
| CandidateSelectionAgent | V99 | 리더·sleeve 선택 | 목표 변경 가능 |
| StrategyAgent | V100 | 목표비중 생성 | 목표 변경 가능 |
| MarketEvidenceAgent | V102 | 수급·공시·뉴스 결합 | 활성 정책은 진단 전용; 감사 후보에서 인과성 검증 |
| RiskExecutionAgent | V101 | 주문·비용·체결·NAV 변환 | 목표는 유지하고 주문·NAV만 변경 가능 |
| ReviewFeedbackAgent | V104 | 귀속·연구 원장·후보 라우팅·승격 거버넌스 | 부모 자본 변경 금지 |

SectorTheme은 CandidateSelection에, PainSupply·DisclosureFundamental·News는 MarketEvidence에 병합돼 있다.

### 상태 저장

- Paper 계좌: `data/runtime/v85_dual_paper.db`
- 오케스트레이터 단계: `data/runtime/v85_orchestrator.db`
- 주문 journal·reconciliation: `data/runtime/v88_order_journal.db`
- 운영 경보: `data/runtime/v85_alerts.jsonl`
- 백업: `data/runtime/backups/`
- 신규 후보 Forward 관측: `reports/runtime/v104_forward_observations.csv`
- V89 동결 계약·관측: `reports/v89_forward_governance/`
- 재현 가능한 연구·게이트 증거: `reports/v104_end_to_end_causal_challenger_audit/` 및 `reports/v104_2_jul30_crash_bridge/`

Runtime DB·로그·WAL/SHM은 배포 ZIP의 상태 원본이 아니며 실행 중 생성된다.

### 백테스트 경로

V104 adapter는 봉인된 후보 사양과 입력 hash로 전체 기간을 결정론적으로 재생한다. 부모·후보 각각 target ledger → orders/fills → account/NAV를 생성하며, 미래변조 검사와 부모 parity를 별도 검증한다. 역사 결과는 screening 전용이고 Forward 승격 증거가 아니다.

### Paper 경로

- V84/V85는 시뮬레이션 계좌와 일봉 실행 모델을 사용한다.
- V104 후보 3개는 고유 paper account·fingerprint·input hash를 사용한다.
- `run_v104_forward_session.py`는 현재 실제 broker-state 증분 실행기가 아니라 sealed input 전체 replay 후 새 session만 append하는 방식이다.
- V88 gateway는 실제 브로커가 아니라 멱등성·transport recovery·부분체결·대조를 검증하는 시뮬레이션이다.

### 현재 브로커 추상화

[`src/quant_harness/v72_integration_ready/contracts.py`](../src/quant_harness/v72_integration_ready/contracts.py)에 `BrokerGateway`, `BrokerOrder`, `BrokerAccount`, `BrokerHolding`, `BrokerQuote` 계약이 있다. Toss client는 읽기/주문 method 골격과 endpoint/field map을 제공하지만, 실제 계좌·주문 endpoint와 상태 매핑은 외부 검증되지 않았다.

## 목표 구조

아래는 현재 설정과 게이트가 선언한 다음 단계이며, 구현 완료 상태가 아니다.

```text
검증된 외부 원본 및 거래 캘린더
  → V87 revision-safe 증분 ingestion
  → 봉인된 7-agent 일일 판단
  → Paper/Live 완전 분리된 broker adapter
  → persist-before-submit + client_order_id
  → broker order/fill/account polling
  → 내부 holdings/cash/NAV reconciliation
  → 불일치 시 HOLD_ONLY·kill switch
  → 60/120 신규 Forward session 평가
  → 사람 승인
  → READ_ONLY → ORDER_DRY_RUN → 제한적 canary
```

목표와 현재의 차이:

- 실제 브로커 endpoint·필드·수수료·세금·거절·취소 계약이 미검증이다.
- broker-state 기반 증분 runner가 없다.
- 완전한 PIT 유니버스·ETF holdings·뉴스 원장이 없다.
- 신규 Forward 60/120세션이 수집되지 않았다.
- 자동 승격과 Live 권한은 구현 목표가 아니라 명시적으로 금지된 정책이다.

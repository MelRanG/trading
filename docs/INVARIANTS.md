# SYSTEM INVARIANTS AUDIT

## 1. 강제 수준

- **HARD_RUNTIME**: 위반 시 실행 중 예외·차단·append 거부가 발생한다.
- **RUNTIME_LOCAL**: 특정 독립 모듈 안에서는 강제되지만 전체 운영 경로에는 연결되지 않는다.
- **TEST_OR_REPORT_GATE**: 테스트·리포트에서 확인하지만 runtime transaction을 직접 막지 않는다.
- **CONFIG_DECLARATION**: 설정값으로 선언됐으나 모든 저수준 경로가 재검증하지 않는다.
- **NOT_ENFORCED**: 문서 요구는 있으나 현재 코드 강제가 없다.

## 2. 인과·데이터 불변조건

| 불변조건 | 강제 수준 | 코드 근거 | 감사 결과 |
|---|---|---|---|
| 당일 의사결정에 당일 close를 사용하지 않는다. | HARD_RUNTIME | V95 shift 및 flag(`src/quant_harness/v95_market_regime_agent/policy.py:65-80`, `:112-124`), V69/V79 cutoff(`src/quant_harness/v69_dynamic_theme_leadership/engine.py:303-306`; `src/quant_harness/v79_generic_trend_sleeve/engine.py:211-215`) | 활성 feature는 D-1. |
| 거래 가능 가격을 forward-fill하지 않는다. | HARD_RUNTIME | `src/quant_harness/v77_corrected_price_allocation/engine.py:132-141` | core 누락 차단, V101도 주문 대상 open 누락 예외(`src/quant_harness/v101_risk_execution_agent/engine.py:121-125`). |
| 유니버스 eligibility는 관측 bar와 D-1 history만 사용한다. | HARD_RUNTIME | `src/quant_harness/v94_universe_agent/policy.py:27-78` | membership 목록 자체는 static proxy. |
| 수급은 직전 거래일 자료가 없으면 current=false다. | HARD_RUNTIME | `src/quant_harness/v102_market_evidence_agent/policy.py:74-105` | no forward-fill. |
| 공시는 `received_at` 이후에만 사용한다. | HARD_RUNTIME | `src/quant_harness/v102_market_evidence_agent/policy.py:108-142` | cutoff는 calendar D-1; 장중 공시 세션 처리 규칙은 없음. |
| 부모·후보는 동일 input hash를 사용한다. | HARD_RUNTIME | hash 생성(`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:77-105`), 비교(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:85-89`) | data/config는 bind, source code는 bind하지 않음. |
| 후보 spec은 fingerprint로 고정한다. | HARD_RUNTIME | `src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:29-52`, `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:85-87` | spec 변경은 차단. 구현 code 변경은 별도. |
| 미래 데이터 변조가 과거 target을 바꾸지 않는다. | TEST_OR_REPORT_GATE | `src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:291-304`, 통합 실행 선행 요구 `src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:341-347` | 지정 후보 5개에 검사. 모든 데이터 종류의 future mutation은 아님. |

## 3. 목표·주문·체결 불변조건

| 불변조건 | 강제 수준 | 코드 근거 | 감사 결과 |
|---|---|---|---|
| target weight 합계는 1이다. | HARD_RUNTIME | `src/quant_harness/v101_risk_execution_agent/engine.py:91-96` | 위반 시 예외. |
| 실행 대상에는 양의 조정 open이 있어야 한다. | HARD_RUNTIME | `src/quant_harness/v101_risk_execution_agent/engine.py:121-125` | 누락 시 예외. |
| 매도 후 매수 순서를 사용한다. | HARD_RUNTIME | sell loop `:148-186`, buy loop `:187-236` | cash 재사용을 synthetic하게 반영. |
| 주문량은 요청량을 넘지 않는다. | HARD_RUNTIME + REPORT | cap logic `:148-160`, `:187-214`; gate `:558-566` | 확인됨. |
| 참여율은 D-1 ADV 한도를 넘지 않는다. | HARD_RUNTIME + REPORT | `:152-159`, `:191-198`, gate `:562` | 모델 ADV 기준. |
| 현금보다 많은 매수를 하지 않는다. | HARD_RUNTIME + REPORT | `_buy_fill_terms` 호출과 cash cap `:204-231`; negative cash gate `:560` | synthetic replay에서 확인. |
| 같은 target·미완료 상태는 재실행 trigger를 유지한다. | HARD_RUNTIME | `src/quant_harness/v101_risk_execution_agent/engine.py:129-144`, `:237-245` | pending 모델 구현. |
| 동일 client order ID는 동일 intent여야 한다. | RUNTIME_LOCAL | `src/quant_harness/v88_order_reconciliation/engine.py:189-206` | V88 journal 내부만 강제. |
| submit 전에 intent를 영속화한다. | RUNTIME_LOCAL | `src/quant_harness/v88_order_reconciliation/engine.py:241-258` | 실제 Toss 경로와 비연결. |
| timeout-after-accept 시 중복 제출하지 않는다. | RUNTIME_LOCAL | `src/quant_harness/v88_order_reconciliation/engine.py:259-266`, 자체 검증 `:306-325` | simulator에서만 검증. |
| broker/internal mismatch 시 `HOLD_ONLY`다. | RUNTIME_LOCAL | `src/quant_harness/v88_order_reconciliation/engine.py:269-290` | V104/V85 transaction에 연결 안 됨. |

## 4. Forward·승격 불변조건

| 불변조건 | 강제 수준 | 코드 근거 | 감사 결과 |
|---|---|---|---|
| 역사 세션은 신규 Forward 행으로 append하지 않는다. | HARD_RUNTIME | `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:73-74`, `:108-136` | 확인됨. |
| Forward 행 `(session,candidate_id)`는 멱등하다. | HARD_RUNTIME | `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:139-154` | 값 충돌 시 예외. |
| 후보별 최신 데이터 cutoff가 동일해야 한다. | HARD_RUNTIME | `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:67-72` | 확인됨. |
| 60세션 전에는 평가하지 않는다. | RUNTIME_LOCAL | V89 `src/quant_harness/v89_forward_governance/engine.py:132-169`, V103 `src/quant_harness/v103_review_feedback_agent/engine.py:321-342` | V104 appender와 자동 연결되지 않음. |
| 120세션·changed decisions 전에는 promotion review가 아니다. | RUNTIME_LOCAL | `src/quant_harness/v103_review_feedback_agent/engine.py:333-342` | 현재 0세션. |
| 역사 결과만으로 승격하지 않는다. | CONFIG + REPORT | `config/v103_review_feedback_agent.yaml:1-15`; `src/quant_harness/v103_review_feedback_agent/engine.py:343-360` | V103 안에서는 강제. |
| 부모를 자동 mutation하지 않는다. | CONFIG + REPORT | `src/quant_harness/v103_review_feedback_agent/engine.py:577-588`, V104 gate `src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:453-455` | 자동 mutation 경로 없음. |
| 후보는 자동 capital authority를 얻지 않는다. | CONFIG + REPORT | `src/quant_harness/v103_review_feedback_agent/engine.py:385-388`, `:577-588` | 확인됨. |

## 5. Live·환경 불변조건

| 불변조건 | 강제 수준 | 코드 근거 | 감사 결과 |
|---|---|---|---|
| 활성 모드는 Paper다. | CONFIG_DECLARATION | `config/active_strategy.yaml:3-5`, `compose.yaml:12-16` | 기본 실행은 Paper. |
| V88 non-dry-run submit은 금지한다. | HARD_RUNTIME | `src/quant_harness/v88_order_reconciliation/engine.py:241-244` | 무조건 차단. |
| Control plane에서 주문을 제출할 수 없다. | HARD_RUNTIME | `src/quant_harness/v86_control_plane_dashboard/engine.py:446-488` | GET-only. |
| 실제 broker contract가 unverified면 Live를 차단한다. | TEST_OR_REPORT_GATE | `src/quant_harness/v101_risk_execution_agent/engine.py:558-566`; `config/v101_broker_execution_contract.yaml:1-24` | V101 report gate에는 존재. 저수준 client에는 없음. |
| Live 활성화에는 사람 승인과 중앙 gate가 필요하다. | NOT_ENFORCED | V89 결과는 사람 승인 필요를 기록(`src/quant_harness/v89_forward_governance/engine.py:170-179`) | `TossOpenApiClient`는 env flag만 확인(`src/quant_harness/v72_integration_ready/toss_openapi.py:367-411`). |
| Paper와 Live 상태·계정을 완전 분리한다. | NOT_ENFORCED | 문서 규칙 `AGENTS.md:13` | 실제 Live state store가 없으므로 분리 구현도 없음. |

## 6. 상태·복구 불변조건

| 불변조건 | 강제 수준 | 코드 근거 | 감사 결과 |
|---|---|---|---|
| 운영 단계는 재시작 시 완료 상태를 확인한다. | RUNTIME_LOCAL | `src/quant_harness/v85_operational_hardening/engine.py:46-67`, `:145-150` | V85 부모 경로만. |
| 동일 session plan은 idempotent하게 commit한다. | RUNTIME_LOCAL | `src/quant_harness/v84_dual_paper_parity/engine.py:323-347`, V85 rerun digest `src/quant_harness/v85_operational_hardening/engine.py:223-240` | 부모 2개 DB에서 검증. |
| DB backup은 restore 후 integrity check를 통과해야 한다. | RUNTIME_LOCAL | `src/quant_harness/v85_operational_hardening/engine.py:116-130`, `:206-207` | 후보 Forward에는 적용 안 됨. |
| 시작 전 governance 실패는 숨기지 않는다. | NOT_ENFORCED | Docker가 `|| true` 사용(`scripts/docker_entrypoint.sh:4-9`) | `AGENTS.md:16`과 충돌. |

## 7. 약한 불변조건과 보강 필요 사항

1. **source code freeze 부재**  
   V104 input hash는 설정·가격·수급·DART를 묶지만 Python source는 포함하지 않는다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:77-105`). V89 freeze도 registry·execution config·data contract 세 파일만 묶는다(`src/quant_harness/v89_forward_governance/engine.py:51-57`). 같은 candidate fingerprint로 코드가 달라질 수 있다.
2. **cache provenance 미검증**  
   V104는 `.v104_cache/<candidate>.pkl`이 있으면 현재 input hash와 비교하지 않고 로드한다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:349-367`). stale cache가 남는 환경에서는 결과 불변조건이 약해질 수 있다.
3. **Forward gate boolean의 실체 부족**  
   `data_gate_passed`와 `reconciliation_passed`가 실제 검사 없이 True다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:108-112`).
4. **실브로커 중앙 권한 gate 부재**  
   Toss client는 `TOSS_ALLOW_LIVE_ORDERS`만 확인한다(`src/quant_harness/v72_integration_ready/toss_openapi.py:140`, `:367-411`). release state, broker contract, signed approval, account allowlist를 함께 확인하지 않는다.
5. **완전 PIT universe 불변조건 미충족**  
   listing/delisting/corporate action 정보가 proxy로 명시된다(`src/quant_harness/v94_universe_agent/policy.py:48-57`).

## 8. 불변조건 우선순위

실제 Codex 이전 작업에서는 다음 순서를 깨지 않아야 한다.

1. Live 차단과 broker contract fail-closed
2. 역사/Forward 분리와 source/config/data freeze
3. D-1 causal cutoff와 무보간
4. target·order·state 멱등성
5. broker/internal reconciliation
6. 성과·승격 gate

전략 변경은 위 불변조건 보강 작업과 같은 변경 단위에 포함하지 않는 것이 저장소 원칙과 일치한다(`AGENTS.md:10-12`, `:25-28`).

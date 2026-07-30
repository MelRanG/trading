# Validation

## 백테스트 프로토콜

V104는 봉인된 후보 설정을 동일 엔진에서 전체 재생하고, 부모·후보별 target ledger, orders/fills, account/NAV를 독립 생성한다. 역사 데이터 결과는 후보 screening에만 사용하며 자동 승격 근거로 사용하지 않는다.

현재 핵심 재현 명령:

```bash
PYTHONPATH=src python scripts/run_v104_end_to_end_causal_challenger_audit.py
PYTHONPATH=src python scripts/run_v104_future_mutation_check.py V69_PARENT
PYTHONPATH=src python scripts/run_v104_future_mutation_check.py V69_VOL_GUARD
PYTHONPATH=src python scripts/run_v104_future_mutation_check.py V79_PARENT
PYTHONPATH=src python scripts/run_v104_future_mutation_check.py V79_NO63
PYTHONPATH=src python scripts/run_v104_future_mutation_check.py V79_NO63_VOL_GUARD
```

결과 원본은 `reports/v104_end_to_end_causal_challenger_audit/`다.

## 개발·검증·Forward 분리

- 개발·검증·purged 검증 구간과 purge session은 각 버전 설정 및 결과 CSV가 원본이다.
- V104 역사 데이터 종료일은 2026-07-03이다.
- 2026-07-03 이하 재생은 `historical_replay_only=true`이며 Forward 통계에 포함하지 않는다.
- 신규 Forward 평가는 최소 60세션부터 시작하고, 권장 120세션과 변경 결정 최소 10건을 요구한다.
- 2026-07-30 crash bridge는 2026-07-03 수량을 고정한 mark-to-market이며 동적 Forward 거래가 아니다.

## 비용·세금·슬리피지·미체결

비용·spread·impact·참여율·최소 주문 처리의 실제 원본은 V77/V101 설정과 코드다. 일봉 replay는 미체결·부분체결·거절·취소·호가 queue·broker outage를 완전히 모사하지 않는다. 실제 수수료·세금·tick·settlement는 외부 미검증이므로 Live gate를 통과하지 못한다.

## 편향 검사

- Look-ahead: D-1 판단, same-day decision 0건, 미래 가격 변조 시 cutoff 이전 target hash 변화 0일을 검사한다.
- Survivorship: observed-first-bar 기반 PIT proxy를 사용하지만 공식 상장·상폐·기업행위 원장이 없어 제한이 남는다.
- Multiple testing: 실패 후보와 연구 시도를 원장에 보존하고, 역사 결과 재사용을 승격 증거로 인정하지 않는다.

## 성능 비교 기준과 생성 근거

아래 수치는 `PYTHONPATH=src python scripts/run_v104_end_to_end_causal_challenger_audit.py`가 생성한 `reports/v104_end_to_end_causal_challenger_audit/v104_candidate_metrics.csv`의 역사 screening 결과다.

| 후보 | 누적수익률 | 종료 NAV |
|---|---:|---:|
| V69_PARENT | 667.974656% | 76,797,465.62원 |
| V69_VOL_GUARD | 755.021309% | 85,502,130.92원 |
| V79_PARENT | 750.753420% | 85,075,342.01원 |
| V79_NO63 | 907.221585% | 100,722,158.53원 |
| V79_NO63_VOL_GUARD | 990.469585% | 109,046,958.52원 |

부모 parity는 같은 명령이 생성한 `v104_parent_parity.csv`에서 V69/V79 모두 0원 오차다. 에이전트 인과성은 `v104_agent_causal_audit.csv`, 미래변조는 `v104_future_mutation_audit.csv`, 전체 게이트는 `v104_quality_gates.csv`가 원본이다.

V104.2 crash bridge 수치는 다음 명령과 결과 파일을 사용한다.

```bash
PYTHONPATH=src python scripts/run_v104_2_jul30_crash_bridge.py
```

- 결과: `reports/v104_2_jul30_crash_bridge/v104_2_precrash_vs_crash_summary.csv`
- 범위 제한: `reports/v104_2_jul30_crash_bridge/v104_2_scope_and_limitations.csv`
- 일별 NAV: `reports/v104_2_jul30_crash_bridge/v104_2_daily_nav_bridge.csv`

이 결과는 동적 재선정·신규 주문 성과가 아니라 고정보유 평가다.

## 회귀 테스트

```bash
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/test_v104_end_to_end_causal_challenger_audit.py \
  tests/test_v104_2_jul30_crash_bridge.py \
  tests/test_v84_dual_paper_parity.py \
  tests/test_v89_forward_governance.py
python -m compileall -q src scripts tests
```

문서 clean release에서는 V85/V88/V101/V102/V103 계약 테스트도 함께 실행한다. 실제 clean release 결과는 `RELEASE_STATE.json`의 `codex_clean_release_validation`을 따른다.

## 현재 통과한 게이트

- V104 품질 게이트 14/14
- V69/V79 부모 NAV parity 0원
- 자본 인과 에이전트 6/6, 거버넌스 인과 에이전트 1/1
- 우선 후보 5개 미래변조 검사 통과
- same-day decision 0, 음수 현금 0
- 후보 adapter 3개 구현·테스트
- V104.2 고정보유 crash bridge 및 누락 시세 무보간
- 자동 Champion 승격과 Live 실행 차단

## 실패·미완료 게이트

- 신규 Forward 0세션
- 실제 브로커 계약 `UNVERIFIED_EXTERNAL`
- 25개 ETF 전체 2026-07-30 PIT 동적 재실행 차단
- 역사 PIT 뉴스, effective-dated ETF holdings, 완전한 lifecycle 원장 미완료
- 실제 체결·거절·취소·세금·capacity 검증 미완료
- P2+P3 봉인 실행 규칙 없음

## Paper 진입 조건

후보 adapter 구현·fingerprint 일치·부모와 동일 input hash·target 또는 order/NAV 변화·미래변조 불변·음수 현금 없음·reconciliation 통과가 필요하다. 현재 후보 3개는 Paper adapter 단계까지 통과했지만 신규 Forward 수집은 시작 전이다.

## Live 진입 조건

V89의 60/120세션 기준, 주문 대조·백업 복구·critical alert 0건, 실제 브로커 계약 및 비용·capacity 확인, 사람 승인이 모두 필요하다. 자동 Live 승격은 금지돼 있으며 현재 Live는 차단 상태다.

## 알려진 한계

- 역사 후보 결과는 연구자 관찰 편향과 재사용 데이터 영향을 받는다.
- 일봉 실행 모델은 실제 주문장과 broker 장애를 완전히 재현하지 않는다.
- 유니버스·ETF 구성종목·뉴스·외부 vendor revision lineage가 불완전하다.
- 큰 자본은 ADV 제약과 tracking error가 커질 수 있다.

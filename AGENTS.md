# Coding Agent Rules

이 파일은 Codex와 모든 코딩 에이전트의 필수 작업 계약이다. 요청 범위를 벗어난 변경을 하지 말고, 현재 사실이 충돌할 때는 아래 권위 순위를 따른다.

## 절대 규칙

1. 의사결정 시점 이후의 가격·수급·공시·뉴스·유니버스 정보를 사용하지 않는다.
2. 상장·상폐·코드변경과 관측 가능 시점을 포함한 시점별 유니버스를 보존한다.
3. 필수 데이터가 누락·stale·불일치하면 추정·보간하지 말고 fail-closed 한다.
4. 백테스트 결과를 개선하려고 사후에 임계값·기간·유니버스·비용 가정을 바꾸지 않는다.
5. 버그 수정과 전략·알파 변경을 같은 작업에서 수행하지 않는다.
6. Live 또는 실제 브로커 주문 권한을 임의로 활성화하지 않는다.
7. Paper와 Live의 계정·상태·환경변수·로그·주문 경로를 분리한다.
8. 주문의 `client_order_id`와 동일 요청의 멱등성을 유지한다.
9. 브로커 계좌·주문·체결 상태와 내부 상태가 불일치하면 신규 주문을 차단하고 `HOLD_ONLY`로 전환한다.
10. 테스트 실패, 미실행, timeout, skipped 결과를 통과로 표현하거나 은폐하지 않는다.
11. 기존 성과 수치를 생성 명령과 원본 결과 파일 재생성 없이 수정하지 않는다.
12. 요청 범위 밖의 리팩터링, 이름 변경, 포맷 일괄 변경, 의존성 갱신을 하지 않는다.
13. 부모·후보는 동일 session 입력 hash를 사용하고 candidate fingerprint를 고정한다.
14. 역사 replay를 동결 이후 신규 Forward 증거로 집계하지 않는다.
15. 자동 부모 변경·Champion 승격·Live 승격을 추가하지 않는다. 승격은 계약된 기간과 사람 승인을 요구한다.

## 변경 단위

- 문서 작업에서는 `src/`, `scripts/`, `config/`, `data/`, `tests/`를 수정하지 않는다.
- 버그 수정은 재현 테스트와 최소 수정만 포함하고 전략 변화는 별도 작업으로 분리한다.
- 전략 연구는 사전등록된 후보, 고정된 데이터 분할, 비용 포함 결과, 실패 후보 원장을 남긴다.
- 실제 데이터 추가는 원본을 보존하고 V87 계약과 revision gate를 먼저 통과한다.

## 변경 후 검증

최소 검증:

```bash
python -m compileall -q src scripts tests
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/test_v104_end_to_end_causal_challenger_audit.py \
  tests/test_v104_2_jul30_crash_bridge.py \
  tests/test_v84_dual_paper_parity.py \
  tests/test_v89_forward_governance.py
```

계약·운영 경로 변경 시 추가 검증:

```bash
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/test_v85_operational_hardening.py \
  tests/test_v88_order_reconciliation.py \
  tests/test_v101_risk_execution_agent.py \
  tests/test_v102_market_evidence_agent.py \
  tests/test_v103_review_feedback_agent.py
PYTHONPATH=src python scripts/run_v104_forward_session.py
```

현재 데이터 종료일이 2026-07-03 이하라면 마지막 명령은 `NO_NEW_SESSION_AFTER_V104_FREEZE`와 0개 append를 반환해야 한다.

## 권위 우선순위

1. 실행 코드와 통과한 테스트
2. YAML·JSON·CSV 계약 원본 및 데이터 스키마
3. `RELEASE_STATE.json`
4. `README.md`, `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`, `docs/VALIDATION.md`, `docs/OPERATIONS.md`
5. 현재 V104/V104.2 결과 파일
6. 이전 버전 보고서와 역사 설명

Markdown과 코드가 충돌하면 코드와 테스트를 현재 사실로 사용하되, 코드를 추측으로 수정하지 말고 충돌을 보고한다.

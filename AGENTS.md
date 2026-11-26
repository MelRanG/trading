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

## Feedback 에이전트 필수 설계 원칙

이 섹션은 Feedback 에이전트의 설계·구현·검증 작업에만 적용한다. 향후 Task16·17의 Feedback 관련 범위와 모든 Feedback 작업지시서는 작성하거나 받아 실행하기 전에 아래 원칙을 필수로 검토하고 반영한다.

Feedback은 지나치게 보수적인 판단이나 손실 합리화를 해서는 안 된다.

1. 시장 전체의 하락, 대형주의 높은 지수 비중, 장기투자 논리만으로 개별 종목의 지속적인 손실이나 부진을 정당화하지 않는다.
2. 절대수익뿐 아니라 동일 노출·위험 수준의 시장, 업종, ETF 및 대체 투자 기회와 비교한다. 지수 적립식 투자 대비 기회비용도 평가한다.
3. 반복적인 부진에는 재평가 기한과 추가 증거 요구 조건을 둔다. 근거 없는 MAINTAIN/MONITOR의 무기한 반복을 허용하지 않는다.
4. 불타기·물타기·비중 축소·청산·재진입을 모두 연구 가능한 의사결정으로 취급한다. 무조건 보유하거나 무조건 손절하는 정책은 지양한다.
5. 반대로 정상 변동을 과잉 해석해 불필요한 매매와 전략 변경을 반복하지 않는다.
6. 위 원칙은 반드시 과소 대응·과잉 대응 사례로 검증하고, 비용 후 성과 및 위험 개선이 확인되지 않으면 운영에 반영하지 않는다.
7. 실시간 매수·매도는 Python 알고리즘이 수행한다. LLM은 비실시간 진단·연구·개선 검증에만 사용한다.

Task16 연구 Feedback은 출처 해시·가용시각·단계를 봉인한 연구 결과와 기존 실패 이력을 읽는다. 예측력 비교에는 거래 원장이 없어도 되며, 투자 손실의 원인 귀속에는 당시 의사결정·체결·동일 위험 비교가 필요하다. 데이터 차단, 과거 사양 기각, 유망하지만 미승인인 상태를 구분한다. 비실시간 모델의 해석은 자문으로 보존하고 Python이 증거·중복·경로·예산·권한을 판정한다.

기업 공시·재무 근거는 Team2, 정량 정책의 적격성은 Team3의 허용된 기존 작업자로 전달한다. 검증된 연결 범위는 격리 Factory의 진단 등록·예약·결과 재수신까지다. 등록은 경제성 평가나 운영 Queue·전략 승인과 분리한다. 진단 최대 한 건·파라미터 탐색 0회이며, 동일 사양은 기존 결과를 재사용한다. Task15·17이나 자본 변경에는 기존 독립 검증·사람 승인 관문을 적용한다.

## 변경 단위

### 개별주 투자와 시간축

- 최종 투자 대상은 한국·미국 개별주식이다. ETF는 종목 발굴·시장 및 업종 분석·동일 자본과 현금흐름의 성과 기준에 사용한다. ETF 자체 매매나 빈 비중을 ETF로 채우는 정책은 별도 승인 범위다.
- 중장기 종목 선정·추세·위험 연구와 장중 진입·청산 연구는 각각 검증된 시간축으로 평가한다. 일봉으로 장중 가격 경로나 체결을 복원하지 않는다. WebSocket 운영 가능성과 역사적 분봉·틱·호가의 검증 가능성을 구분한다. 실시간 판단과 주문은 Python이 담당하고 LLM은 비실시간 연구와 복기에만 사용한다.

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

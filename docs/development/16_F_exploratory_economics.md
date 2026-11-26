# Task16 탐색적 경제성 실행 경로

**공식 사전등록 완료. 역사 자료 평가 미실행. `ALPHA_NOT_VALIDATED`.** 등록 ID `REVIEW-cc8630ae4ff206cb3ebdae46`는 사용자 승인에 따른 단일 오프라인 정책 사양을 고정한다. 2026-11-26 UTC 일일 예약은 Cycle 3의 00:00:15 UTC 진단이 이미 사용했다. 실제 경제성 실행 요청은 예약 검사에서 차단됐다. 해시·날짜·한도를 바꾸거나 다른 원장을 열지 않았다. 최초 다음 예약 가능 시점은 **2026-11-27 09:00 KST**이며 그 시점의 실제 잔여 슬롯에 따른다. 경제성 결과나 경제성 기반 Feedback은 아직 없다. [실제 차단 기록](../../runtime/task16_economics/current_utc_reservation.log) · [선행 예약](../../runtime/task16_cycle3/isolated_factory/experiment_reservations.jsonl)

## 승인과 실행

승인 원문 출처와 구절, worker, 입력 해시, 실험 1회 및 탐색 0회를 기존 Task4 설정의 구체적인 사양에 연결했다. 별도 서명 방식은 Task4 코드·설정에 존재하지 않는다. 등록은 승인 범위와 worker 해시가 일치할 때만 가능하다. 실행은 공식 원장에서 예약하며 앞서 사용한 격리 Task16 예약도 집계한다. 별도 예약 원장은 없다. 시작 마커를 배타적으로 남긴 뒤 허용된 연구 worker만 호출한다. 경제 결과 유형은 별도 증거 등급을 요구하고 체결 worker가 남긴 출력과 대사한다. 초기 실행 실패나 음의 결과도 기록 대상이다. 등록·예약·기록에는 기존 Task4 메서드를 쓰며, 기존 두 평가 유형과 승격 설정을 유지한다. 해당 경제성 사양의 승격 권한은 `NOT_ELIGIBLE`이다. [공식 승인과 정책](../../config/task4_review_contract.json) · [Factory](../../src/quant_harness/alpha_research_factory.py) · [실제 등록 원장](../../runtime/alpha_research_factory/task4/attempt_registry.jsonl)

## 고정된 연구 사양

- **후보**는 5일째 종가를 본 뒤 6일째 적격 시가부터 청산을 요청한다. 기존 위험 OFF 강제청산은 후보와 기존 정책에 공통이다. 원래 Cycle 3 종가 경매 사양과 구분한다.
- **표본**은 R5 위험 ON의 지정 의사결정일 중 21세션이 성숙한 29개 진입 후보, 2026-01-12~10-08이다. R5 사전 체결 후보와 위험 신호는 전일 신호를 사용했다. 원화 장부의 초기 진입은 1,000만원, 납입 0원이며 각 비용 경우에서 동일 정수 수량을 모든 팔에 복제한다. 달력의 21세션 블록은 최대 8개다.
- **대조군**은 동일 바스켓을 단순 보유하는 방식과 R5의 원래 종목 목표 및 매도 위험 신호를 적용하는 조건부 기존 정책이다. 대체 매수와 독립 에피소드 합산은 제외했다. 21세션 시가에 공통 청산을 시도하고 남는 수량은 동일 날짜 명목 종가로 표시한다. 체결 실패·잔량·비용·현금은 일별로 남긴다.
- **체결 모형**은 기존 R4의 명목 시가·유동성·수수료 계산을 재사용한다. D−1까지의 ADV, 29% 이상 극단 시가 갭 차단, 거래량 0의 모의 체결 금지, 미체결 잔량 추적을 고정한다. 거래량 0 여부는 사후 체결 유효성 판단에만 쓴다. 일봉 고저로 경로를 복원하지 않는다. 수수료에 포함된 매도세는 기존 모형의 대용치다. 비용 두 배와 알려진 기업행사·결측 검사도 고정했다.
- **결과**는 양 대조군 대비 비용 후 수익·하방 위험·노출·놓친 상승과 회피 손실을 비교한다. 전일 노출을 적용한 KODEX 200 가격 기준은 별도 진단이다. 기간 중 증가한 연구 표본은 생존 중심이고 독립적인 홀드아웃이 아니다. 에피소드 표본에서 연속 계좌 CAGR을 계산하지 않는다. [계약](../../experiments/task16_economics/contract.json) · [봉인](../../runtime/task16_economics/snapshot.json) · [실행기](../../experiments/task16_economics/worker.py)

슬롯이 생기면 아래 명령은 같은 등록을 확인하여 한 번의 예약과 실행을 수행한다. 성공 시 실제 원장·경제성 결과를 입력으로 기존 Task16-B의 보고를 생성한다. 이미 공식 슬롯이 소진됐다면 예약 오류를 반환한다. 대기 시간을 넘는 작업을 자동 예약하지 않았다.

```bash
PYTHONPATH=src:. .venv/bin/python experiments/task16_economics/run.py run
```

## 검증 결과

- 합성 worker와 기존 Review 회귀 22건 통과. 실제 테스트 DB·Task3 읽기 소스 연결을 요구하는 6건은 미실행이다. 첫 합성 테스트는 30% 갭을 넣고 체결을 기대해 실패했다. 29% 차단 기준을 유지하고 합성 체결 시가만 수정했다. [첫 검증](../../runtime/task16_economics/targeted_first.log) · [최종 검증](../../runtime/task16_economics/targeted.log)
- 현 작업 트리의 안전 회귀 42건 통과·11건 실패. 실패는 모두 이전에 삭제된 V83·V85·V101~V103 보고서 참조에서 발생했다. 현재 결과로 그대로 남기고 보고서를 복원하지 않았다. [안전 회귀](../../runtime/task16_economics/safety.log)
- compileall 및 diff 검사 통과. V104 Forward 검사는 `NO_ENABLED_CANDIDATES`였고 append는 0이다. [Forward 확인](../../runtime/task16_economics/forward_zero_append.json)

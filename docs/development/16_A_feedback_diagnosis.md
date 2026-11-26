# Task16-A — Feedback 원인 진단과 연구 판단

**MINIMAL_EXTENSION_REQUIRED · DIAGNOSIS_VALIDATED · RESEARCH_POLICY_VALIDATED · ECONOMIC_SELF_IMPROVEMENT_NOT_TESTED.** 진단·연구 판정은 사전 봉인 주입 사례와 실사례 행동 관문에 한정한다. 실제 시장의 근본 원인 정확도는 추정할 수 없다. [판정](../../runtime/task16_a/result.json)

## 기존 기능과 실행 범위

Task4에는 읽기 전용 의사결정 패킷, 결과를 차단한 증거 Review, 별도 체결·성숙 라벨 검사와 제한된 제안 기능이 있다. 실제 코디네이터는 Queue·Factory 등록과 예약까지 지원한다. 기존 실행 원장에서 제안·Factory ID와 PENDING 결과를 대사했고, 이번 격리 시험에서는 기존 순수 Review와 좁은 재현성 연구 제안 함수를 직접 호출했다. [Review](../../src/quant_harness/investment/review.py) · [기존 Factory 연결](../../src/quant_harness/investment/review_engine.py)

Task10의 주간 Review는 성숙 IC, 동일 노출 상대성과, 연속 약화를 기준으로 유지·관측·연구 상태를 선택한다. 초기 Review를 봉인 정책으로 다시 호출해 입력·정책 해시 및 지적 사항이 일치했다. 저장된 Review V2는 미국 새 버전의 평가 진입을 2026년 7월 16일로 복구했고 V1 원본 해시가 일치했다. V103은 연구 기억·중복·후보 라우팅 거버넌스이며, 저장 결과는 39개 시도 행, Forward 관측 0, 자본 권한 없음이었다. 독립 V75 bounded controller는 현재 소스, 경로 및 확인한 Git 기록에서 찾지 못했다. [주간 Review](../../experiments/task10/weekly_review.py) · [Review V2](../../experiments/task10/version_outcomes_v2.py) · [V103 코드](../../src/quant_harness/v103_review_feedback_agent/engine.py) · [구현·실행 근거 대사](../../runtime/task16_a/implementation_checks.json)

이번 추가는 실험 폴더의 사후 증거 어댑터와 결정 규칙이다. 동일 사례 기록에서 A는 기존 Review와 성숙 판정의 원래 입력 경계를 따르며, B는 같은 출력에 사후 체결·비용·유니버스·기각 증거를 결합한다. 실사례 8건 중 같은 스키마로 보존된 원 의사결정 패킷은 Task10 한 건이다. 나머지 7건은 A에 EVIDENCE_MISSING을 남겼다. 진단의 숫자 신뢰도는 규칙의 강도 표시이며 통계적으로 보정된 확률은 아니다. [비교 계약](../../runtime/task16_a/contract.json) · [사례별 구조화 출력](../../runtime/task16_a/case_results.json)

## 실제 기록의 판단

| 사례 | 확인한 근거와 B 판단 |
|---|---|
| A. R2 7종목 | 목표 4종목, 청산 미체결 4종목, 신규 매수 3종목, 최종 7종목. 장부·체결 상태 DATA_ERROR. 기존 R4 수정 후 최대 4종목을 확인해 현재는 MAINTAIN 및 기존 회귀 유지. |
| B. FLOW5 | T+1 일별 목표 종목이 412세션에서 달랐다. 명목 집행 복구 후 결합 +66.17%, MOM63 +157.26%, 차이 −91.08%p. 고정 50:50 가설 REJECT_HYPOTHESIS. |
| C. 여름 급락 | 계좌 −29.22%, KOSPI −25.17%, 노출 혼합 기준 대비 −14.02%p. 현금화는 급락 12세션 뒤였고 이후 반등을 놓쳤다. 종목 선정 손실 가능성과 게이트 지연을 구별했으나 각각의 인과적 기여는 UNDETERMINED. MONITOR. 게이트 변경을 검토할 경우 당시 신호로 다른 기간의 손실·재진입도 함께 반증해야 한다. |
| D. 가을 급락 | 첫 5% 급락 하루 전인 10월 12일 전량 현금화. 계좌 +0.96%, KOSPI −25.89%. 마지막 저점 이후 ETF +2.08%에는 미참여. MAINTAIN. |
| E. R6 생존편향 | 435개 예비 후보, 봉인 표본과 기존 60종목의 교집합 6개, 적격 경제 평가 0회. PIT·정산·마스크 결손은 DATA_ERROR로 기록하고 알파 판단은 INSUFFICIENT_EVIDENCE. |
| F. Task10 미국·한국 | 미국 STATIC −9.04%, ADAPTIVE +1.62%, MOM63 +0.50%, 지수 +1.98%. 한국 STATIC·ADAPTIVE +1.45%, MOM63 −2.95%, 지수 −28.92%. 한국 STATIC·ADAPTIVE의 평균 현금 72.19%, 같은 노출 지수 −6.61%. 미국 고정 대비 개선과 지수 성과, 한국 현금 방어와 종목 기여를 각각 대사했다. MONITOR. |
| G. Team2 | Task9.2의 EPS 4행 금액·주당 단위 오류는 LLM 전에 발견·수정했다. DATA_ERROR와 Team2 선정·가치판단의 경제적 효과는 별도다. E2에는 적격 공통 결과가 부족하다. |
| H. Task10 V2 | 미국 변경 버전이 종전 계좌 시작일에 연결된 라벨 오류를 확인했다. 수정된 V2와 소급 NAV·체결 불변 기록을 재사용했다. |

실사례 행동 관문 8개는 모두 충족했다. 시장 원인의 정확도에는 정답 라벨을 부여하지 않았다. 기존 Task13~14의 부정적 연구 기록 및 R6의 미평가 상태를 유지했다. [사례의 원천 SHA](../../runtime/task16_a/source_manifest.json) · [Task14 결과](14_alpha_signal_validation.md)

## 통제 사례 및 시점 검사

개발 2건과 평가 12건을 분리하고, 구현 전에 입력과 정답의 SHA를 기록했다. 같은 작업에서 만든 소규모 통제 자료로 외부 독립 채점은 없다. 개선분에는 기존 Review의 경계 밖에 있던 사후 증거를 결합한 효과가 포함된다. [사전 봉인 주입 자료](../../experiments/task16_a/fixtures.json)

| 지표 | A 기존 Review | B 사후 증거 결합 |
|---|---:|---:|
| 원인·행동 모두 일치 | 2/12 | 12/12 |
| 행동 일치 | 4/12 | 12/12 |
| 명확한 기술 결함 미탐 | 3/3 | 0/3 |
| 비결함 기술 오탐 | 0/9 | 0/9 |
| 제안 적중 / 놓침 | 0 / 2 | 2 / 0 |
| 불필요 제안 / 기존 기각 재제안 | 0 / 0 | 0 / 0 |

B는 단위 1,000배, 사용된 미래 입력, 미체결 상태 갱신을 잡았다. 미사용 미래 입력은 상태 판단에 반영하지 않았고, 평가 기준시각 이후 증거는 격리했다. H20/H60 미성숙 사례는 양쪽 모두 보류했다. 모델 오차만 늘어난 사례에는 MONITOR. 두 제안 초안은 동일 노출에서 비용만 반복 악화되거나 성숙 IC가 반복 저하된 통제 사례에 한정했고, 변경 한 부분·반증 조건·자료·예산·승인 요건을 저장했다. V102와 FLOW5 기각 ID를 재사용하고 이름만 바꾼 단순 수급 증거도 제안하지 않았다. 일반적인 의미 기반 중복 탐지는 미검증이다. 추가 경계 회귀 4건과 compileall 통과. LLM·시장 요청·학습·백테스트·공식 예약·등록 모두 0회. 진단 계산 CPU 약 1.60초이며 테스트 시간은 별도다. [평가 출력](../../runtime/task16_a/result.json) · [경계 회귀](../../runtime/task16_a/feedback_tests.log)

## 현재 작업 트리와 Task17

사용자가 삭제한 reports/의 Git 추적 파일 309개를 확인했다. 현재 트리는 13 통과·11 실패다. V104·V104.2·V84의 10건은 생성 보고서 파일 로드에서 실패했다. V89 한 건은 생성된 V85 운영 및 V88 대사 요약이 없어 readiness 게이트 두 개가 닫혔다. 앞의 10건은 테스트 자료 의존성이고 V89는 배포 준비를 입증할 자료의 공백이다. 이번 시험으로 실제 주문·정산 장애가 관측되지는 않았다. Git HEAD 자료를 일회성 임시 검증 위치에만 복구한 동일 시험은 24 통과였다. 공식 운영 경로와 삭제 상태의 전후 Git 상태가 일치했다. [현재 트리](../../runtime/task16_a/safety_current.log) · [격리 시험](../../runtime/task16_a/safety_validation.json) · [V89 게이트](../../src/quant_harness/v89_forward_governance/engine.py)

Task17 판단에는 독립 검증 가능한 초기 전략, 같은 시점·종목군·비용·리스크에서 봉인된 A/B 계좌, B의 사전 승인·예산·변경 효력 규칙, 성숙 NAV가 필요하다. R6의 유니버스·정산 결손과 MOM63 독립 알파 미입증이 남아 있다. 이번 진단 결과를 투자 성과 검증으로 집계하지 않았다. [Task17 설계](11_research_architecture_audit.md)

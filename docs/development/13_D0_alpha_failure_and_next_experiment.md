# Task13-D0 알파 연구 실패 원인과 다음 실험

## A. 실패 원인

반복해서 확인된 문제는 **측정 가능한 기술적 성공이 기존 팩터 대비 예측 정보로 이어지지 않았다는 점**이다. C1과 Task14 일부는 신호 중복이 컸다. B3와 C4는 입력 문제를 보완한 뒤에도 양의 증분을 뒷받침하지 못했다. B2와 C2는 표본 부족으로 가설 평가 자체와 구분해야 한다. 다음 실험에서 개선할 수 있는 부분은 수익률을 열기 전에 중복도와 관측 단위를 검증하고, 짧은 주기의 무조건 매매 대신 경제 메커니즘에 맞는 예측 기간을 고정하는 것이다.

| 연구 | 주요 원인 | 부차 원인 | 대사한 증거 |
|---|---|---|---|
| Task6–7 | `EXECUTION_COST` | `EVALUATION_LIMITED`, `DATA_LIMITED` | Task6 미국 MOM63 회전 61.06배, 비용 $3,849. Task7 QUANTA_NODE0 동일 체결 gross +15.35%, net −7.41%, 비용 중 spread 약 78%, IC −0.0192. V1 목표와 기존 보유 구간 불일치는 V2에서 교정됐다. spread는 가정치이고 피드백 오류의 인과효과는 `UNKNOWN`. 두 기업 사례의 원문 해석 비교는 거래 성과 증거와 분리했다. [Task6](../../runtime/task6/evaluation/final/US/results.json) · [Task7 정량 진단](../../runtime/task7/quant/diagnosis.json) · [기업 비교](../../runtime/task7/comparison/evaluation.json) |
| Task10 | `EVALUATION_LIMITED` | `EXECUTION_COST` | 미국 ADAPTIVE +1.62%, STATIC −9.04%, 가격지수 +1.98%. 적응형 동일 체결 gross +3.65%, 회전 32.32배. 한국은 두 계좌 동일 +1.45%. 고정 전략 대비 개선은 해당 과거 경로의 관측이며 독립 증분은 `UNKNOWN`. [평가 집계](../../runtime/task10/evaluation/summary.json) |
| Task12 / R0 | `DATA_LIMITED` | `EVALUATION_LIMITED` | US 176·KR 126의 조정가격 연구 패널을 확보했다. 현재 생존 종목, 관측 달력, 불완전한 역사 상장·기업행사 이력이다. 2023–24는 개발 구간, 2025–26 역시 노출 구간이다. 알파 성패 판정은 해당 없음. [준비도](../../runtime/task12/readiness.json) · [R0 계약](../../runtime/task13_r0/native_input_contract.json) |
| Task13–14 | `SIGNAL_REDUNDANT` | `EVALUATION_LIMITED` | Q1과 MOM20이 크게 겹치고 Q0의 조건부 근거가 약하다. 저장된 실제 primary 10개는 무보정 .05도 통과하지 못했고 예약 슬롯 포함 Holm18에서도 통과 0개였다. [후보 원장](../../runtime/task13/attempt_ledger.json) · [검정](../../runtime/task14/validation.json) |
| R1–R2 | `HYPOTHESIS_WEAK` | `ENGINE_LIMITED`, `EVALUATION_LIMITED` | R1 전체 생성자는 Conda 환경 필드 검사에서 차단됐고 제한된 원본 구성요소로 진화 연구를 했다. R1.2는 충실한 생성까지 확인했으나 개발 구간 양 시장 RankIC가 음수였다. R2 전체 루프는 미검증이고 제한 구성에서는 미국 C−A RankIC 개선 +0.0105의 구간이 0을 포함했다. 같은 분석의 양의 잔차 진단은 잠재 단서로 남는다. 엔진을 확장했을 때 효과는 `UNKNOWN`. [R1 실행](../../runtime/task13_r1/full_probe.json) · [R1.2 분석](../../runtime/task13_r1_2/analysis.json) · [R2 실행](../../runtime/task13_r2/result_summary.json) · [R2 비교](../../runtime/task13_r2/analysis.json) |
| B1–B2.1 | `DATA_LIMITED` | `EVALUATION_LIMITED` | B1의 비교 가능한 하향 사례는 1기업 1건. B2 300건 중 UP 18·DOWN 1, B2.1 40건 감사에서 회복 가능한 UP 6·유지 4·DOWN 0. 하향 반응 가설의 성패는 `UNKNOWN`. [B1](../../runtime/task13_b1/research_candidates.json) · [B2](../../runtime/task13_b2/classification_summary.json) · [B2.1](../../runtime/task13_b2_1/result_summary.json) |
| B3 및 repair | `HYPOTHESIS_WEAK` | `DATA_LIMITED`, `EVALUATION_LIMITED`, `ENGINE_LIMITED` | 원 평가의 종목 마스크 불일치를 수정한 뒤 10기업·105건에서 partial Spearman −0.00147. 이익률 1%p당 효과 +0.071%p, CI 약 [−0.441, +0.583]%p. 작은 기업 군집과 공통 시기 의존성이 남는다. [수정 및 통계](../../runtime/task13_b3_repair/result_summary.json) |
| C1 | `SIGNAL_REDUNDANT` | `EVALUATION_LIMITED` | 미국 REV5 평균 순위 상관 0.9342. partial RankIC +0.00429, 95% 구간 [−0.01892, +0.02804], Holm 보정 1. 한국 전이 평가는 역사 지수 매핑 부족으로 차단됐다. [평가](../../runtime/task13_c1/evaluation.json) |
| C2–C3 | `DATA_LIMITED` | `EVALUATION_LIMITED` | C2 발생액 구조 일치 상한 15기업·80건으로 후보 0개. C3 원문 대사 52기업·163기간, H252 마스크상 151건. 자료 병목은 일부 해소됐고 생존편향과 H252 겹침은 남았다. 알파 성패 판정은 해당 없음. [C2](../../runtime/task13_c2/candidate_data_audit.json) · [C3](../../runtime/task13_c3/completion.json) |
| C4 및 repair | `HYPOTHESIS_WEAK` | `EVALUATION_LIMITED`, 초기 `ENGINE_LIMITED` | import 실패와 보존 라벨을 사용한 단일 재개를 구분했다. 52기업·151건에서 일반 RankIC −0.0242, partial −0.0400. 고정 bootstrap 5,000회 중 1회 식별 실패로 CI·p·Holm40 미산출. 양의 증거가 없으며 통계적 기각이나 시장 초과수익 판정은 불가하다. [원 실패](../../runtime/task13_c4/execution.json) · [재개 원장](../../runtime/task13_c4_repair/execution.json) · [실제 통계](../../runtime/task13_c4_repair/result.json) |

## B. 검토한 정보 경로

| 후보 | 경제적 근거 | 정보 차별성 | 데이터 준비도 | 검증 설계 | 경제적 활용성 |
|---|---|---|---|---|---|
| **중기 상승 경로의 고른 상승일 분포** | PARTIAL | PASS | PARTIAL | PASS | PARTIAL |
| **한국 신규 공급계약의 기존 매출 대비 추가 수주** | PARTIAL | PARTIAL | FAIL | PARTIAL | UNKNOWN |

첫 후보는 같은 중기 상승폭이라도 완만하게 나뉜 상승이 눈에 띄는 급등보다 투자자의 주의를 늦게 끌 수 있다는 가설이다. 측정값은 상승일 수와 하락일 수의 차이다. 뉴스 인지나 자금 흐름은 직접 관측하지 않으며, 변동성·스타일·수익률 비대칭이 대안 설명이다. 최근 급락의 시장 잔차를 쓰는 C1, 전체 상승폭을 쓰는 MOM, 야간·장중 분해와 하방분산을 쓰는 R1, 범위·상대거래량을 쓰는 R2와 계산 대상이 다르다. V79의 52주 고가 근접은 이미 코드와 역사 시험이 있어 신규 후보에서 제외하고 비교 통제로 사용했다. 20세션 단위 순위가 유용하다면 매일 거래할 필요가 줄 수 있으나 회전·비용은 아직 측정하지 않았다. [52주 고가 기록](../research/03_candidate_validation.md) · [R2 수식](../../experiments/task13_r2/feature_oracle.py)

두 번째 후보의 예정 변수는 공시 시점에 확인 가능한 순수 추가 계약액을 이전 연결 연매출로 나눈 값이다. 수주가 미래 매출에 미치는 정보는 OHLCV 밖에 있으나 재공표·계약기간 연장·VAT·원가·매출 인식으로 크기가 왜곡될 수 있다. 저장본에는 같은 계약의 원본·후속 변경 3건과 기타 최초 계약 3건만 있다. 최초 시장 공개와 신규 경제적 범위가 확인되지 않았다. 공시 익일 진입 후 H20 양의 조건부 효과가 없으면 중단하는 설계는 가능하지만 현재 표본으로는 집행하지 않는다. 이 경로를 별도 검토할 최소 보완은 기존 표본을 포함해 **30개 분리된 계약 사건·12개 기업**의 원본과 이전 계약·정정 계보 및 당시 연결 매출을 확인하는 것이다. 현재 최대 4개 계약 계보를 모두 쓸 수 있다고 가정해도 최소 26개가 추가로 필요하다. 문서 1~3개씩 **26~78회 원문 요청과 3~6시간의 범위·공시 시점 검산**을 초기 계획치로 본다. 이는 실측 비용이 아니며 검색·정정·가격 적격성에 따라 늘 수 있다. 기존 3건의 기타 최초 계약은 첫 정보 공개 미인증이다. [계약 원문 연결표](../../runtime/task13_b1/contract_events.json)

## C. 최종 결정

**`NEXT_EXPERIMENT_READY` · 선정 1개, 중기 상승 경로의 고른 상승일 분포.** 제한 역사 진단에 배정할 가치가 있다는 판단이다. 독립 투자 우위는 미측정이다.

훈련 구간의 실제 조정 종가만으로 특징량을 **1회** 계산했다. 2018–2022년 분기 말 20개 모두 동일 표본 최소 50종목을 충족했다. 각 날짜 55~138개, 전체 고유 종목 165개다. 순위 상관의 절댓값이 가장 큰 통제는 같은 형성기간 수익률 **0.412**였고, REV5 −0.029, MOM20 −0.005, MOM63 +0.153, LOWVOL20 +0.056, 하방분산비 −0.024, 52주 고가 근접 +0.198이었다. 7개 통제 후 신호 순위 잔차 분산 중앙값은 **69.6%**로 사전 중복 문턱을 통과했다. 이는 정보의 수치적 분리이며 예측력은 미평가다. [실행·입력 SHA와 날짜별 결과](../../runtime/task13_d0/precheck.json)

R0의 US CORE 176개 전체에서 가격·native 마스크·기본 마스크 SHA와 공급자 USD 주식·티커·거래소 식별 정보를 확인했다. NYQ 117, NMS 59다. 현재 식별자와 R0 역사적 하한을 유지했으며 CIK 전수 역사 연계, 이전·상폐·모든 기업행사 확인은 R0의 잔여 한계다. 개발 구간의 가격 값은 읽지 않고 날짜·마스크만 확인했다. 21세션 간격 격자에서 마스크상 50종목 이상 가능 날짜는 19개다. **2023–24의 실제 적격 상승 종목 수는 이 수치의 하위 집합**이며 수익률을 열기 전에 확인해야 한다.

## D. 다음 행동과 실행 계약

단일 H20 계약은 [사전 초안](../../runtime/task13_d0/screen_plan.json)에 남겼다. 종가 t에서 최근 20세션을 건너뛴 126개 일간 조정 종가 수익을 사용한다. 형성기간 누적수익이 양수일 때 `(상승일−하락일)/126`을 계산하고, 0인 날은 0으로 센다. 높은 값이 높은 이후 순위를 예측한다는 방향을 고정한다. 20세션은 점진적 반영을 확인할 한 달 규모이며 이미 본 성과로 선택한 기간이 아니다.

후속 승인 작업에서는 현재 [특징량 함수](../../experiments/task13_d0/precheck.py)를 동일하게 사용하고 C1의 해시 봉인·평가 예약 방식을 재사용한다. 기존 Task12 라벨과 같은 t+1 시가에서 t+21 시가까지의 수익률을 사용하되, 먼저 **≥50 완전 적격 승자 종목·≥15 성숙 날짜**를 확인하고 각 날짜 통제 회귀의 식별성을 검사한다. 모든 가격·마스크·사건·코드를 봉인한 뒤 1회만 평가한다. primary는 7개 통제에 대해 후보와 결과의 평균 동률 순위를 각각 잔차화한 뒤 계산하는 날짜별 partial RankIC의 동일 가중 평균이다. [라벨 경로](../../experiments/task12/readiness.py) · [순위 통제·bootstrap·Holm](../../experiments/task14/stats_eval.py) · [C1 단일 실행 증거](../../runtime/task13_c1/evaluation_attempt.json)

겹치지 않는 H20 간격도 공통 시장 충격과 종목 반복을 제거하지 않는다. 기존 40슬롯에 한 슬롯을 더한 Holm41, 3개 격자 관측을 한 블록으로 하는 5,000회 bootstrap, 고정 seed 130501을 사용한다. 과거 탐색 전체를 열거하지 못했으며 작은 날짜 수로 추론은 취약하다. 사전 표본·식별성 통과 후에도 양의 partial RankIC, 양의 95% 구간 하한, Holm41 <.05, 두 신호 달력 연도 모두에서 양의 효과가 필요하다. 실패 시 방향·기간·종목·통제를 바꾸지 않고 중단한다. 통과 시에도 약 15개 비중첩 월 구간의 새 사전 봉인 관측에서만 독립 검증을 검토한다. 경제성·비용 평가는 별도 승인 단계다.

실측 특징량 검사 CPU 4.85초, 안전 회귀 자식 프로세스 CPU 3.29초다. 세션 전체 CPU·Codex 토큰은 미계측이다. 인프라 설치·내부 연구 LLM·하위 에이전트·SEC/API·다운로드·미래 수익률·RankIC·spread·학습·전략 백테스트는 모두 0회다. 초기 빈 종가 열의 dtype 오류는 실측 결과 생성 전에 float 지정 한 번으로 해결하고 증거를 보존했다. 실제 실행 경로와 합성 prefix·결측·통계 인터페이스 smoke test, compileall 및 AGENTS 회귀 24개를 통과했다. 연구·운영 설정·원장 쓰기는 D0 경로 외에 수행하지 않았다. 운영 코드·설정 Git 상태도 비교했다. [초기 실패](../../runtime/task13_d0/precheck_initial_dtype_failure.log) · [최소 수정](../../runtime/task13_d0/mechanical_fix.diff) · [smoke test](../../runtime/task13_d0/smoke.log) · [안전 회귀](../../runtime/task13_d0/safety_validation.json)

이번 작업으로 새 알파의 발견 확률을 수치화할 수는 없다. 실제로 좁힌 것은 다음 평가의 낭비 위험이다. 한 후보의 훈련 특징량 차별성을 수익률 없이 확인했고, 다른 후보는 원문 범위 부족으로 보류했으며, 남은 표본 중단 규칙을 결과 조회 전에 정했다. 후속 평가나 운영 등록을 시작하지 않았다.

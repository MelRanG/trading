# 시장·종목 추세에 따른 MA20 이격도 H20 검증

**전체 INCONCLUSIVE · 미국 INCONCLUSIVE · 한국 NO_INCREMENTAL_SIGNAL · ALPHA_NOT_VALIDATED.** 사전등록한 가설을 한 번 평가했다. 두 시장 모두 관문을 통과하지 못해 Task15 경제성 검증은 0회다. [사전등록 규격](../../experiments/task13_conditional_distance/contract.json) · [입력 봉인](../../runtime/task13_conditional_distance/seal.json) · [실행 예약](../../runtime/task13_conditional_distance/reservation.json) · [결과 원장](../../runtime/task13_conditional_distance/result.json)

## 1. 가설과 기존 연구

검정 대상은 가격의 20일선 이격도와 H20 수익률의 관계가 **종목의 앞선 추세와 당시 시장 국면**에 따라 달라지는가다. 양호한 상태일수록 이격도의 수익률 기울기가 커진다고 사전등록했다. MA20 터치 청산, ATR 손절, 충격 매수나 재진입 정책을 실행하지 않았다.

R4 수익에는 생존편향이 남아 있고 R5에는 급락 체결과 반등 미참여가 있었으며 R6의 시점별 경제성은 검증하지 못했다. FLOW5 50:50과 R1 순위 완충은 증분 가치가 확인되지 않았다. ST와 PTH×TO는 기존 차단·불충분 판정을 보존했다. Q0는 음의 20일 수익률에 20일 Amihud 계열 유동성 가중치를, Q1은 20일 수익률에 5일/20일 평균 거래량 비율을 곱한다. RD_SMALL은 수익률·모멘텀·변동성·상대 거래량을 쓰는 H5 모형이다. H1에서 실제 평가한 신호는 봉 내 종가 위치와 상대 거래량의 10일 상관이며 이번 공통 모형에 통제로 포함했다. [R5](13_F1_R5_mom63_stress_and_survivorship.md) · [R6](13_F1_R6_mom63_pit_universe.md) · [R1/ST](13_R1_ST_preflight.md) · [PTH×TO](13_PTH_TO_exploratory_close.md) · [Q0/Q1 코드](../../experiments/task13/diagnose_worker.py) · [Task14](14_alpha_signal_validation.md) · [H1](13_H1_native_mechanism_pilot.md)

V95는 전일 기준 MA120 이력현상·시장 폭 후보를 승격하지 않았고, 변동성 가드는 검증 기간의 변경일 0일로 관찰 전용이었다. V96 연속 위험점수와 급락 가드도 승격되지 않았다. 두 버전의 기존 결과는 Git HEAD에서 읽었다. 별도 팩터 시스템의 v0.28 원장과 기술적 분석 Deep Research 원문은 확인하지 못했다. v0.28의 단순 보유 열위와 재진입 지연은 사용자 제공 선행 결과로 반영했다. [V95 정책 코드](../../src/quant_harness/v95_market_regime_agent/policy.py)

ChartSchool의 이동평균은 과거 가격을 평활화하고 ADX는 방향과 분리된 추세 강도를 측정한다. Zakamulin·Giner는 이동평균과 모멘텀의 공통점과 차이를, Han·Zhou·Zhu는 여러 시간대 이동평균의 실증 결과를 다룬다. 이번에는 종목 방향과 경로의 일관성을 부호 있는 효율비 하나로 표현했다. 고점·저점 구조는 추세 전환, 상대강도는 시장 대비 위치, 변동성·거래량과 시장 폭은 추세의 강도 또는 참여 증거가 될 수 있다. 추가 지표 조합의 독립성은 시험하지 않았다. [ChartSchool 이동평균](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/moving-averages-simple-and-exponential) · [ChartSchool ADX](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-directional-index-adx) · [Zakamulin·Giner](https://doi.org/10.1080/14697688.2020.1716057) · [Han·Zhou·Zhu](https://doi.org/10.1016/j.jfineco.2016.01.029)

## 2. 데이터와 절차

- H1의 미국 176·한국 119종목 R0 CORE 조정 패널, 적격 마스크와 AS_OF 상태의 해시를 확인했다. 거래소 시점별 편입·상폐, 과거 원본 관측 시각, 실제 명목가격 체결은 확인하지 못했다. 신규 시세 요청은 0회다.
- 이격도 D는 log(종가/SMA20)를 최근 일별 로그수익률 표준편차의 √20배로 나눴다. 종목 추세 T는 최근 20일을 뺀 앞선 63세션의 부호 있는 로그 가격 변화량을 절대 로그 변화량 합으로 나눴다. 84일 연속 유효 종가가 필요하다. 시장 M은 종가 기준 기존 AS_OF의 상승·반등 +1, 하락·급락 −1, 횡보·전환 0이다. **이격도 순위 × (T+M)/2** 한 항을 검정했다. 시장마다 자체 상태를 사용했고 VIX는 제외했다.
- 가산 OLS의 동일 단면 통제는 REV5, MOM20·63, D, D², T, VOL20, H1이다. 두 모형을 2023년에 적합하고 2024년에는 계수를 고정했다. 2023년 H20 만기는 모두 2024년 전에 끝났다. 두 기간 모두 과거 연구에 노출됐다.
- 종가 t 신호, t+1 시가부터 t+21 시가까지 H20을 평가했다. 21개 시가가 모두 유효한 공통 평가 표본을 사용했다. 신호 순위는 당시 적격 종목으로 계산했다. 미래 종가 교란 및 입력 절단 전후 과거 특징값이 일치했다. 시장 상태 단독은 같은 날 종목을 순위화하지 못하므로 상태별 평균 H20을 별도 집계했다. [봉인](../../runtime/task13_conditional_distance/seal.json)

| 시장 | 2023 적합일 / 종목·일 | 2024 평가일 / 종목·일 | 평가 범위 |
|---|---:|---:|---|
| 미국 | 167 / 28,111 | 231 / 39,564 | 1월 2일~11월 29일 |
| 한국 | 162 / 16,184 | 130 / 13,723 | 5월 21일~11월 28일 |

## 3. 증분 예측력과 4. 경제성 관문

| 2024 같은 표본 | 미국 | 한국 |
|---|---:|---:|
| 가산 → 조건부 RankIC | 0.04884 → 0.04989 | 0.07712 → 0.07054 |
| **증분 RankIC / 95% 구간** | **+0.00105 [−0.00019, +0.00278]** | **−0.00658 [−0.01022, −0.00322]** |
| 양의 증분 단측 Holm p | 0.207 | 0.998 |
| 상위 20% 비용 전 H20 증분 | +0.025%p | −0.227%p |
| 단독 REV5 / MOM20 / MOM63 RankIC | −0.0142 / +0.0628 / +0.0290 | −0.0169 / +0.0472 / +0.0160 |
| 단독 이격도 / 추세 / H1 RankIC | +0.0495 / −0.0462 / +0.0009 | +0.0470 / +0.0270 / +0.0093 |

미국 조건부 모형은 가산 모형 대비 소폭 높았고, 순위 성과는 단순 MOM20에 못 미쳤다. 이격도와 MOM20의 일별 순위 상관 평균은 미국 0.808, 한국 0.817이었다. H20 중첩과 단면 동시성을 고려한 42세션 블록 재표집은 5,000회 중 미국 5,000회, 한국 4,997회가 유효했다. 한국 공백만 뽑힌 3회는 기존 함수가 경고 후 제외했다. 적격일 기준 비중첩 블록 수 상한은 5개·3개다. H1까지의 43개 이력 슬롯을 더한 보조 보정에서도 두 시장 모두 관문을 통과하지 못했다. 이 이력은 전체 과거 탐색을 포괄하지 않는다.

상위 20% 수익률은 비용 전 예측 단면 진단이다. 청산·재진입 정책이나 단순 보유·ETF 대비 비용 후 NAV, MDD는 Task15 관문 미통과로 평가하지 않았다. [Task12~20 관문](11_research_architecture_audit.md)

## 5. 시기·종목·국면 안정성

미국 상·하반기 증분 RankIC는 +0.00180·+0.00018이었다. 상승 59일에서 +0.00493이었고 횡보 81일은 −0.00018, 전환 91일은 −0.00036이었다. 미국 하락·급락·반등일은 평가 마스크 내에 없었다. 한국 상·하반기는 각각 −0.00762·−0.00630이었으며 한국 상반기 평가는 5월 21일 이후로 제한됐다. 한국 횡보 62일과 전환 65일 모두 약화했고 하락·급락·반등은 각각 1일이었다. 일시적 시장 충격과 개별 악재의 분리나 위기 매수는 판단할 수 없다. 순위 제곱오차 기여 절댓값이 큰 다섯 종목을 합계에서 빼도 미국의 작은 양의 방향과 한국의 음의 방향은 같았다. [미국 일별](../../runtime/task13_conditional_distance/US_daily.csv) · [한국 일별](../../runtime/task13_conditional_distance/KR_daily.csv) · [미국 상태별 꼬리 분포](../../runtime/task13_conditional_distance/US_state_tails.csv) · [한국 상태별 꼬리 분포](../../runtime/task13_conditional_distance/KR_state_tails.csv)

## 6–8. Feedback과 처분

기존 Task16-A의 원본 Review, 기본 판단, 확장 진단을 추가 규칙 없이 실행했다. 원본 Review는 의사결정 패킷 부재로 EVIDENCE_MISSING, 기본 판단은 INSUFFICIENT_EVIDENCE, 확장 진단은 원인 UNDETERMINED와 행동 MONITOR를 출력했다. 실제 패킷을 합성하거나 후속 검증을 자동으로 제안·예약하지 않았다. 관측된 차이는 **예측력 단계**에서 발생했다. 진입 지연·조기 청산·재진입·과소 노출·추가매수·비중·비용별 회피 금액이나 정상 변동과 정책 결함의 구분에는 거래 원장이 필요하다. 현재 Feedback에는 순위 예측 비교의 증분·신뢰구간·국면 범위·종목 집중도를 해석하고 재평가 조건을 제시하는 경로가 없다. 이는 Task16/17 별도 검증 항목이다.

이번 연구 처분은 **한국 고정 가설 종료, 미국 보류**다. 이 사양의 재개에는 새로운 독립 증거가 필요하다. [Feedback 실출력](../../runtime/task13_conditional_distance/feedback.json) · [기존 Task16-A](16_A_feedback_diagnosis.md)

## 9. 다음 한 가지

**공개시각이 확인된 실적 정보가 상대강도에 증분 정보를 주는지 데이터 적격성부터 확인**한다. 이번 이격도와 MOM20 사이의 높은 중복을 피할 정보원이다. B3/C4의 단순 영업마진 방향 가설을 반복하지 않도록 지표·공개시각·가설 차이를 먼저 확인한다. 기존 자료의 시점·커버리지 감사로 한정하며 후속 실험은 실행하지 않았다.

## 10. 재현과 안전 회귀

공식 실행은 해시 봉인 이후 한 번 수행했다. 원래 산출물을 보존하면서 재현하는 명령이다.

```bash
scratch="$(mktemp -d)"
for phase in seal evaluate; do
  PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 .venv/bin/python -c '
import sys
from pathlib import Path
from experiments.task13_conditional_distance import run
run.OUT = Path(sys.argv.pop(1))
run.main()
' "$scratch" "$phase"
done
PYTHONPATH=src:. .venv/bin/python -c '
import sys
from pathlib import Path
from experiments.task13_conditional_distance import feedback
feedback.OUT = Path(sys.argv[1])
feedback.main()
' "$scratch"
```

신규 연구 계약·코드, 본 보고서, 별도 결과 폴더만 추가했다. compileall과 필수 안전 회귀 24건이 통과했다. 추가 Task16-A·V95는 현재 작업 트리에서 6건 통과·2건 실패했다. 두 실패는 작업 전부터 삭제 상태인 V95 생성 보고서 경로를 요구했다. Git HEAD의 기존 보고서를 임시 디렉터리에 둔 격리 검증에서는 V95 4건이 통과했다. 운영 변경은 0건이다. [코드](../../experiments/task13_conditional_distance/run.py) · [Feedback 코드](../../experiments/task13_conditional_distance/feedback.py) · [안전 회귀](../../runtime/task13_conditional_distance/safety.log) · [추가 회귀](../../runtime/task13_conditional_distance/optional_current.log) · [산출물 해시](../../runtime/task13_conditional_distance/artifact_manifest.json)

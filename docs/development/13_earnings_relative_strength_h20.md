# 공시 EPS의 상대강도 대비 H20 증분 연구

## 1. 기존 연구와 차별성

새 가설은 **미국 8-K 원본 실적 발표의 GAAP 희석 EPS 전년 동기 변화가 기존 가격 신호보다 H20 시장 상대수익 예측을 개선한다**는 것이다. B2의 전망 변경, B3의 10-Q 영업이익률 변화와 H60, C4의 연간 재무 발생액과 H252와 구별된다. 가격 반응은 기준선에 포함했다. R1·ST·PTH×TO·MA20의 기존 결정을 보존했다. [B2](13_B2_guidance_alpha_pilot.md) · [B3](13_B3_technical_completion.md) · [C4](13_C4_cash_accrual_h252.md) · [이전 MA20 평가](13_conditional_distance_h20.md)

Livnat·Mendenhall은 분석가 예측과 시계열 비교에서 발표 후 수익 지속의 강도가 다름을 보였다. Novy-Marx는 실적·가격 모멘텀의 중복을 보고했다. Martineau는 대형주에서 발표 후 지속이 사라졌다는 반례를 제시했다. 별도로 언급된 Deep Research 원문은 저장소에서 확인하지 못해 논문 원문과 기존 B2/B3 증거를 사용했다. [Livnat·Mendenhall](https://doi.org/10.1111/j.1475-679X.2006.00196.x) · [Novy-Marx](https://www.nber.org/papers/w20984) · [Martineau](https://doi.org/10.1561/104.00000122)

## 2. 가용 데이터와 공개 시점

| 입력 | 실제 확인 범위와 결정 |
|---|---|
| 애널리스트 서프라이즈·전망 수정 | 회계기간·발표 버전·공개 전 관측시각이 함께 검증된 연속 이력을 찾지 못했다. Task9.2의 현재 가치평가 기대와 소수 과거 사례는 사용할 수 없다. |
| 가이던스 | B2 원문은 다수 확보됐으나 비교 가능한 이전/새 전망의 상·하향이 18/1로 불균형했다. 동일 사양을 재실행하지 않았다. |
| 회계 실적 | 미국 원본 EPS 후보 136건·16기업의 공시와 회계기간을 확인했다. 이 중 시계열·가격 마스크를 통과한 84건을 사용했다. 한국은 DART B0의 날짜 단위 연결 재무 4건·2기업, B1의 6개 회사 수집 기록만으로 비교 가능한 EPS 표본을 만들 수 없어 DATA_BLOCKED다. |
| 발표 후 상대강도 | 미국 종목과 S&P 500을 같은 세션 달력에 맞췄다. 발표일 전 종가부터 결정 종가까지의 시장 대비 반응은 가격 통제다. |

미국의 회계기간은 발표에 적힌 전년 동기와 당기 결산일이다. 원본 접수번호·SEC 승인 UTC·Item 2.02·첨부·원문 SHA·표 행을 기록했다. 기업 IR·보도자료의 실제 최초 공개는 별도 검증되지 않았다. 현지 공시일 이후 첫 완전 세션 종가까지 관측한 뒤 다음 세션 시가에 진입한 것으로 고정했다. 따라서 SEC 시각이 허용하는 가장 이른 거래보다 늦을 수 있다. 후속 공개된 비교값은 입력하지 않았다. 살아남은 R0 종목의 조정가격과 기존 마스크를 사용했으며 역사 편입·상폐 정산과 명목 체결은 확인하지 못했다. [원문 대사](../../runtime/task13_earnings_strength/eps_source_audit.json) · [적격 사건](../../runtime/task13_earnings_strength/events.json)

## 3. 사전등록

EPS 점수는 **(당기 EPS − 같은 발표의 전년 동기 EPS) ÷ (두 절댓값의 합)**이다. 같은 자료에 실린 전년 비교치여서 회계상 비교 재표시 가능성이 남으며, 애널리스트 추정치나 이전 공개 당시 수치를 복원하지 않는다. 가격 전용 OLS의 MOM20·시장 대비 RS63·REV5·VOL20·발표 반응에 EPS 한 항을 더했다. MOM20·MOM63·RS63·EPS 단독과도 비교했다. 상호작용과 대체 가설은 실행하지 않았다.

적합은 2022년 10월~2023년 11월 결정 36건·13기업, 평가는 2024년 1월~11월 결정 48건·16기업이었다. 평가 표본의 13기업은 적합 표본에도 있었다. 양쪽 모두 H20 라벨이 연도 경계를 넘지 않았다. 주평가는 2024년 사건을 합친 시장 상대 H20 Spearman의 증분이다. 같은 날 종목 횡단면이 드문 자료라 일별 RankIC로 해석하지 않는다. 2024년 서로 다른 공시일은 40일, 재표집 시간 클러스터는 두 달 단위 6개다. [사전규격](../../experiments/task13_earnings_strength/contract.json) · [최종 봉인](../../runtime/task13_earnings_strength/seal.json)

## 4. 증분 예측력

**미국 INCONCLUSIVE · 한국 DATA_BLOCKED · ALPHA_NOT_VALIDATED.** 미국에서 EPS 추가 후 전체 순위가 악화됐다. 상위 사건의 평균 개선은 아홉 건 중 한 건의 교체에서 전부 발생했다.

| 미국 동일 48개 사건 | Spearman | 상위 20% 시장 상대 H20 |
|---|---:|---:|
| MOM20 단독 | +0.2984 | −0.584% |
| MOM63 단독 | +0.1976 | +3.120% |
| RS63 단독 | +0.1583 | +3.178% |
| EPS 변화 단독 | −0.2097 | −1.278% |
| 가격 전용 모형 | +0.0613 | −0.586% |
| 가격 + EPS 가산 모형 | −0.0066 | +1.701% |
| **가산 − 가격 전용** | **−0.0680** | **+2.287%p** |

주 지표의 발행사×두 달 블록 95% 구간은 **[−0.2721, +0.1097]**였다. 5,000회 중 4,998회가 유효했다. 상·하반기 증분은 각각 −0.1146·−0.0168이었다. EPS와 MOM20·MOM63·RS63의 순위 상관은 각각 +0.321·+0.505·+0.432였고 발표 반응과는 +0.077이었다. 가산 모형은 상위군에서 단순 RS63에도 뒤졌다. 상위군 9개 중 8개는 가격 전용과 같았고 ELF 한 사건(−30.318%)을 BURL 한 사건(−9.737%)으로 교체한 것이 개선의 전부였다. 발행사별 순위손실 기여도는 합계가 음수였고, 절댓값 최대 5기업을 제외한 산술에서는 양수로 바뀌었다. BURL·ARMK·LOW·WMT·ELF의 영향이 컸다. [결과](../../runtime/task13_earnings_strength/result.json) · [상위군 교체 검산](../../runtime/task13_earnings_strength/independent_result_audit.json)

## 5. 한계

미국 300개 B2 원장 중 원문 부재 24건, 엄격한 분기 EPS 추출 미통과 140건, 시간·범위 20건, 가격 특징 경로 26건, 보유 경로 6건을 제외했다. 추출 미통과에는 표 형식이 다르거나 값이 모호한 사건이 포함된다. 16개 종목은 기존 공시 수집과 생존 표본에 제한된다. 손익은 조정 시가 기준 주식에서 가격지수 수익률을 뺀 값으로, 배당 기준 차이가 남는다. 여러 사건이 같은 시장 충격을 공유하며 시간 블록이 6개뿐이다. 이번 구간은 이미 연구에 노출됐고 구간 추정에 과거 전체 탐색을 보정하지 않았다. 실제 체결·비용·투자 성과나 상위군 결과의 재현성은 미검증이다. Task15 실행 0회다. [Task12~20 관문](11_research_architecture_audit.md)

## 6. Feedback 실제 출력

변경 없이 기존 Task16-A를 실행했다. 원본 Review는 실제 의사결정 패킷 부재로 EVIDENCE_MISSING, 기본 판단은 INSUFFICIENT_EVIDENCE, 확장 진단은 UNDETERMINED / MONITOR였다. 증분·구간·중복·시기·종목 집중·롱온리 결과와 재평가 조건을 함께 넘겼다. 기존 진단은 이를 자동 해석하거나 가설 폐기·재개를 판단하지 못한다. Task16/17에는 증거가 부족할 때 원인을 보류하고, 재평가 기준을 명시하는 연구 결과 입력 계약이 필요하다. 자동 조치와 진단 규칙 변경은 0건이다. [Feedback 실행 결과](../../runtime/task13_earnings_strength/feedback.json)

## 7–8. 연구 처분과 다음 작업

미국은 증분 순위 개선이 확인되지 않고 상위군 개선이 한 건에 의존해 **고정 가설을 보류하고 이번 탐색을 종료**한다. 한국은 공개 시점과 비교 가능한 EPS 표본 부족으로 보류한다. 두 시장 모두 현재 자료에서 가중치·변수·기간을 바꿔 재실행할 근거가 없다.

다음 한 가지는 **기존에 접근 권한이 있는 원천에서 소규모 표본의 발표 전 EPS 컨센서스와 발표 실제치의 동일 회계기간·동일 GAAP 기준·관측시각을 대사**하는 일이다. 시장 기대를 직접 관측하면 이번 전년 동기 비교와 구별된다. 새로 확보한 독립 기간의 데이터가 있고 적격 표본·승인 관문을 충족할 때만 별도 등록한다. 현재 평가를 반복하거나 Task15를 예약하지 않았다.

## 9. 재현과 회귀

공시·가격 데이터 신규 요청 0회. 공시 표의 날짜 형식을 보정한 두 사전점검은 미래수익 계산 없이 완료했고 이전 봉인·코드를 보존했다. 최종 봉인 뒤 첫 실행은 발행사 기여도를 집계하는 중 배열 형식 오류로 결과를 만들기 전에 중단됐다. 집계를 위한 Series 변환만 수정한 뒤 공시, 가격, 사전등록, 표본, 신호 바이트가 같음을 대사해 **유효 평가 1회**를 완료했다. compileall과 필수 안전 회귀 24건, 파서·Feedback 회귀 6건이 통과했다. 운영·주문·원장·Forward·Live 설정 변경은 0건이다. [집계 수정 diff](../../runtime/task13_earnings_strength/evaluator_repair.diff) · [실패 로그](../../runtime/task13_earnings_strength/attempt_1/evaluation.log) · [안전 회귀](../../runtime/task13_earnings_strength/safety.log) · [연구 회귀](../../runtime/task13_earnings_strength/research_tests.log)

기존 산출물을 보존하는 격리 재현 명령이다.

```bash
scratch="$(mktemp -d)"
for phase in seal evaluate; do
  PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 .venv/bin/python -c '
import sys
from pathlib import Path
from experiments.task13_earnings_strength import run
run.OUT = Path(sys.argv.pop(1))
run.main()
' "$scratch" "$phase" || break
done
PYTHONPATH=src:. .venv/bin/python -c '
import sys
from pathlib import Path
from experiments.task13_earnings_strength import feedback
feedback.OUT = Path(sys.argv[1])
feedback.main()
' "$scratch"
```

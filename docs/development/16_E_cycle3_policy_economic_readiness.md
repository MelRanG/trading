# Cycle 3 개별주 정책 경제성 연구

## 권한과 데이터

Factory의 기본 [제어 경로](../../config/alpha_research_factory.yaml)는 `DRY_RUN_ONLY`다. Task4 등록기는 `PROCESS_DIAGNOSTIC_ONLY`와 `PREREGISTERED_FORWARD`만 수락하고, UTC 하루에 제안 3건과 기존 진단 예약 1건을 허용한다. 등록과 예약은 권한을 부여하지 않는다. Task16-B의 작업자 두 종류도 시점·출처·목표 노출의 진단만 수행한다. 또한 기존 Task8b 탐색 계좌의 관측 기간·지정 종목 계약은 일반 오프라인 정책 replay에 적용되지 않는다. [Task4 계약](../../config/task4_review_contract.json) · [Factory 구현](../../src/quant_harness/alpha_research_factory.py#L185) · [Feedback 작업자](../../src/quant_harness/investment/research_feedback_dispatch.py#L74)

탐색적 신호와 진단에는 기존 노출 표본을 사용할 수 있다. 별도 경제성 평가에는 데이터와 집행 계약 및 사람의 연구 범위 승인이 필요하다. 확증은 동결 이후 독립 자료를 요구하며, Task19·20 운영 승인도 별개다. R4 명목가격 재현기의 체결 함수는 시가를 사용한다. 확인 가능한 과거 분봉·호가·경매패널은 없고, 역사적 시점별 전체 종목군과 실적 컨센서스도 불완전하다. [기존 관문](11_research_architecture_audit.md) · [명목 시가 재현기](../../experiments/task13_f1_r4/execution.py#L24)

## 가설 발굴 및 기준선

| 생성 경로 | 제안과 근거 | 판정 |
|---|---|---|
| Team2 C1 | 산업 수요 충격의 지속이 업종 상대수익을 설명 | 당시 산업소속·상폐를 포함한 비교 모집단 공백. 순위 방향을 별도로 정해야 함 |
| Team2 C2 | 시가 경매 검증 공백이 후보 정책의 비용 후 비교를 왜곡 | 기존 보존 원장의 경매 근거 진단으로 선택 |
| QuantaAlpha 1 | 최근 20일 고저 범위 중위값이 낮은 종목의 상대성과 | 고저 범위 추정의 차이는 있으나 기존 저변동성 가설과 메커니즘 중복. 추가 단일 팩터 평가의 우선순위 낮음 |
| QuantaAlpha 2 | 다음 시가 진입 후 5거래일째 종가 청산으로 보유기간 노출 통제 | 종가 경매·잔량 계약과 경제성 승인의 차단을 명시한 초안 보존 |

Team2는 기업·산업 메커니즘과 체결 진단을 독립 호출에서 제안했다. Team3는 QuantaAlpha 원본의 프롬프트, 계획 생성 함수와 응답 파서를 호출했다. 원본 버전의 깨진 기존 Python 경로와 호스트 의존성 때문에 모델 수송·로깅만 어댑터로 연결했다. 원본 계획 2개, 폴백 0개, 진화·학습 0건이다. RD의 모델 학습이나 Vibe의 레지스트리 재계산은 우선된 체결 문제 또는 승인 부족을 해결할 수 없어 이번 후보 생성에 추가하지 않았다. [Team2 결과](../../runtime/task16_cycle3/team2.json) · [Team3 결과](../../runtime/task16_cycle3/team3.json) · [선정 영수증](../../runtime/task16_cycle3/selection.json)

Cycle 2의 가격 합성은 하루별 횡단면 백분위 순위에 REV5, MOM20, MOM63을 양의 방향으로, MAX21과 VOL20을 음의 방향으로 더해 5로 나눴다. REV5는 5일 반전, MOM은 가격 수익률, MAX21은 일별 수익 최대치, VOL20은 모표준편차다. 단순 동일 가중치는 진단을 위한 고정 사양이다. H20 개별 RankIC +0.05159(MOM20), +0.05629(VOL20), +0.04622(MAX21)는 각 원 변수 증가 방향으로 계산됐다. 합성에는 뒤의 두 변수가 반대 부호로 들어갔다. 합성 −0.01980에서 왜도 추가 후 −0.01514였고, 두 합성은 같은 자료에서 음수였다. 상위 20% 총수익 진단에는 비용 후 주문·NAV 계약이 없었다. 이 부호와 동일 가중치는 변경하지 않았다. 정책 후속 비교의 기준은 동결 기존 정책과 동일 진입 단순 보유다. [기준선 대사](../../runtime/task16_cycle3/baseline_receipt.json) · [Cycle 2 산식](../../experiments/task16_cycle2/run.py#L116)

## 경제성 심사 초안

다음 연구는 동일한 R4 개별주 바스켓, 진입 수량·자본·위험과 비용을 고정해 보유기간 청산의 추가 가치만 평가하는 1건이다. 기존 정책의 매도·축소, 동일 종목 단순 보유, 이전 주식 노출을 적용한 KODEX 200과 현금, 동일 원금 KODEX 200 보유를 비교한다. 에피소드 비교를 먼저 사전등록하고, 연속 전략 CAGR은 별도 계약이 필요하다.

재개 최소 조건은 종가 경매의 제출·체결 시점, 가격제한·정지, 잔량, 허용 주문크기와 비용을 근거 있는 원천으로 검증하는 일이다. 종가를 익일 시가로 바꾸려면 별도 사전등록이 필요하다. 사람은 봉인된 입력과 연구 범위·승인 모델·1회 한도를 기존 연구 승인 절차에서 승인해야 한다. 현재 Task4 코드에는 이 초안을 경제 실험으로 예약할 수 있는 split이나 worker가 없다. [미승인 심사 초안](../../experiments/task16_cycle3/economic_review_draft.json)

## 재현 경로

`audit.py verify`는 새 실험 예약이나 모델 호출 없이 봉인 해시와 단일 예약의 결합을 검사한다. `audit.py run`은 Factory의 당일 한도 및 기존 등록을 확인하므로 재평가 명령으로 사용하지 않는다. 진단·영수증·원 모델 응답은 `runtime/task16_cycle3`에 보존한다. 체결 표시 분류는 사후 증거 품질 관리이며 매매 신호나 사후 수익률 표본 선택에 사용하지 않는다.

```bash
PYTHONPATH=src:. .venv/bin/python experiments/task16_cycle3/audit.py verify
```

## 실제 집행 근거 진단

**Factory 진단 1회 완료. 경제성 0회. `ALPHA_NOT_VALIDATED`.** 예약 ID `REVIEW-b6741dedd26358b4f3c1edc1`. 11월 25일 UTC에는 Cycle 2의 기존 예약 때문에 실행 전에 차단됐다. 날짜·한도를 변경하지 않고 실제 11월 26일 UTC 이후 같은 봉인으로 1회 예약했다.

| 기존 모의 원장 | 세션 | 모의 체결 건수 | 표시 구간 |
|---|---:|---:|---|
| R4 한국, 2023-04-03~2025-12-30 | 669 | 509건, 121세션 | 날짜별 경매 분류 필드 없음 |
| R5 한국, 2026-01-02~11-18 | 215 | 142건, 33세션 | 위험 표시 합집합 24세션, 그중 2세션에서 모의 체결 6건 |

R5의 충격 시가 19세션 중 1세션에서 모의 체결 4건, 시장 차단 플래그 12세션, 7월 13일 명시적인 주문 미체결 태그 2건을 확인했다. 표시가 없었던 191세션의 모의 체결 136건도 역사적 개시·종가 경매 체결 증명으로 사용할 수 없다. 경매 증명은 입력에서 **0건**이다. 이 날짜들을 빼서 NAV를 다시 계산하지 않았다. 비용 후 NAV, MDD, ETF 대비 성과와 초과수익은 미평가다. 이전 R4/R5 실적은 그대로 역사적 참고다. [봉인](../../runtime/task16_cycle3/seal.json) · [예약](../../runtime/task16_cycle3/claim.json) · [실제 진단 결과](../../runtime/task16_cycle3/result.json)

Task16-B는 원천 해시 및 실제 결과를 입력받아 `HOLD / INFORMATION_MISSING`을 출력했다. **개별 가설**은 시가·종가 경매 근거, 공통 비용 및 별도 연구 승인 조건을 확보할 때까지 보류한다. **전체 Cycle**은 실제 UTC 하루 한 건을 소진했고, 별개 후보의 산업 정보 및 조건부 체결 자료도 부족해 종료했다. 경제성 심사 초안은 운영 등록이나 승인 효력이 없으며 후속 실험은 0건이다. [Feedback 입력과 출력](../../runtime/task16_cycle3/feedback.json) · [전체 처분](../../runtime/task16_cycle3/disposition.json)

안전 회귀 24건, Factory·Feedback 27건, compileall 및 diff 검사 통과. 변경 범위는 격리 실험 파일과 보고서 및 연구 증거다. 운영 코드·설정·원장이나 Task12~20 관문에 변경 사항이 없다. [안전 회귀](../../runtime/task16_cycle3/safety_counted.log) · [Factory·Feedback 회귀](../../runtime/task16_cycle3/factory_feedback_tests.log)

모델 3회, 총 72,822토큰이다. Team2 24,205, QuantaAlpha 계획 24,159, Feedback 자문 24,458토큰이다. 자문이 위험 표시일의 희소한 모의 체결에 대해 시장 제약과 주문 발생 차이를 경쟁 설명으로 기록했다. 별도 과제 제안은 없었다. 청구 금액은 확인되지 않았다. 전체 작업은 약 16분이며 0시에 열린 UTC 예약 대기를 포함한다. [Feedback 자문](../../runtime/task16_cycle3/model_feedback.json) · [모델 호출 원장](../../runtime/task16_cycle3/model)

# 후보 블랙박스 검증과 도입 판정

기준 자료는 [후보 비교](02_repository_comparison.md)와 [초기 실측](03_candidate_validation.md)이다. 검증 대상은 수익률 후보 FinRL-Trading, 판단·복기 후보 TradingAgents, 연구 검증 후보 Qlib이다.

| 후보 | 실행으로 확인할 관문 | 도입에 필요한 추가 증거 |
|---|---|---|
| FinRL-Trading | 고정 가격·설정에서 결과 재현, 미래 가격을 바꿨을 때 과거 신호·비중 불변 | 저자 성과에 대응하는 커밋·데이터 복원, 동일 미국 가격·비용 기준선 대비 비용 후 성과 |
| TradingAgents | 고정 입력에서 그래프나 개별 구성요소의 실행, 시점별 기억과 재개, 근거 정정 전파 | 실제 모델에서 같은 검색·토큰 예산의 단일 분석가 대비 새로 발견한 정확한 근거와 복기 품질 |
| Qlib | 날짜 경계·정보 이용 가능 시각에서 미래 관측 차단, 같은 입력의 재현 | 국내 V79에 점수 한 가지를 붙인 사전등록 실험에서 비용 후 증분 효과 |

합성 입력의 통과는 실행 계약의 일부를 검증한다. 시장 성과 판정에는 별도의 동일 조건 비교가 필요하다. 18개 후보의 역할별 분류는 이전 비교표를 유지한다.

다음 실험은 기존 기록과 분리한다. 국내는 V79에 독립 점수 하나만 추가하고 동일 세션·초기자본·수수료·시장 충격·유동성 한도에서 비교한다. 미장은 FinRL 저자 조건 재현용 입력과 우리 기준선용 입력을 각각 해시로 고정한다. TradingAgents는 동일 시간·검색·토큰 예산에서 단일 분석가를 대조군으로 두고, 원문으로 검증된 신규 근거·오탐·정정 반영을 기록한다. 전략 승격은 동결 이후 별도 증거와 사람 승인에 따른다.

## 내부 비교 기준 검증

기존 역사 replay 테스트 함수 6개를 별도 임시 fixture로 직접 실행했고 종료 코드는 0이었다. 대상은 수량 변조 영수증 차단, fail-closed parity, challenger와 부모 reference 분리, 혼합 후보 ID·중복 날짜·공통 날짜 없음 차단이다. 전체 pytest 결과로 집계하지 않는다.

## FinRL-Trading · Terra

커밋 `4409abe925c904e570be78ebfb5e77ac3491dff8`의 `compute_residual_returns`와 `compute_residual_momentum` 함수 정의를 AST로 추출하고 pandas 합성 가격에서 실행했다. 동일 3일 입력의 결과는 반복해서 `0.01003103`이었다. 미래 행을 추가한 뒤 호출 전에 자르면 동일했고, 자르지 않으면 `1.323071369`로 변했다. 함수 자체에 기준일 통제가 없음을 확인했다. 일반 패키지 import는 `pandas_market_calendars` 부재로 실패했고 임시 설치는 PyPI DNS 해석 오류로 실패했다. 따라서 전체 전략·거래비용·실제 가격 성과는 이번 함수 검증 범위를 벗어난다. [고정 소스](https://github.com/AI4Finance-Foundation/FinRL-Trading/blob/4409abe925c904e570be78ebfb5e77ac3491dff8/src/strategies/adaptive_rotation/intra_group_ranking.py)

실제 `run()` 호출 경로는 `get_data_as_of_date()`로 기준일 이후를 제외한 뒤 순위화한다. 기본값은 기준일 가격을 포함하므로 장 마감 확정 전 판단 또는 당일 체결에 같은 종가를 사용한다면 시점 누수가 생길 수 있다. 전체 경로의 시간대·체결 지연은 별도 검증 대상이다. 임시 클론은 삭제했다. [실행 호출](https://github.com/AI4Finance-Foundation/FinRL-Trading/blob/4409abe925c904e570be78ebfb5e77ac3491dff8/src/strategies/adaptive_rotation/adaptive_rotation_engine.py#L191) · [데이터 절단](https://github.com/AI4Finance-Foundation/FinRL-Trading/blob/4409abe925c904e570be78ebfb5e77ac3491dff8/src/strategies/adaptive_rotation/data_preprocessor.py#L357)

## Qlib · Luna

임시 환경에 `pyqlib==0.9.7`을 설치했다. 합성 PIT 공급자를 연결한 실제 `P._load_internal`은 미래 관측을 추가해도 기존 cutoff의 결과를 유지했고, 미래 윈도우(`end_ws>0`)를 선언한 특징을 거부했다. 실제 `qlib.utils.split_pred`는 학습 마지막 날(2024-01-03)과 테스트 시작일(2024-01-04)을 분리했으나, 01-03 표본의 2세션 라벨이 01-04를 참조하는 경우를 제거하지 않았다. 따라서 Qlib의 이 도우미를 적용해도 라벨 종료 시각 기반 purge와 필요한 embargo는 기존 연구 계약에 남겨야 한다. 시장 데이터나 전략 학습 실행은 없었다.

## TradingAgents · Luna

커밋 `9fa1196fffbcfd9de5146d2dd2869df84ab99838`의 날짜 창 모듈을 오프라인 실행했다. 과거 조회 범위가 평가 시점으로 제한됨을 확인했다. 전체 그래프는 LangGraph 의존성 부재와 패키지 인덱스 DNS 문제로 미실행이다. 개별 날짜 함수의 검증으로 전체 그래프의 뉴스·기억 누수나 독립 분석가 대비 증거 품질을 판정할 수 없다. [고정 날짜 모듈](https://github.com/TauricResearch/TradingAgents/blob/9fa1196fffbcfd9de5146d2dd2869df84ab99838/tradingagents/dataflows/date_window.py)

## 도입 판단

TradingAgents의 같은 커밋에서 `memory/settlement.py`도 오프라인 실행했다. 합성 2세션 평가의 수익은 21.0000%, 벤치마크 대비는 19.0198%였고 해결일은 2024-01-04였다. 이후 극단 가격을 넣어도 동일했고, 가짜 저장소에서는 두 번째 처리에 변화가 없었다. 이 수치는 fixture 계산값이며 실제 SQLite 재시작은 미검증이다. 날짜 모듈은 기준일 이후 요청, 다음 UTC 자정 이벤트, 타임스탬프 없는 역사 이벤트도 각각 검사했다. [고정 settlement 소스](https://github.com/TauricResearch/TradingAgents/blob/9fa1196fffbcfd9de5146d2dd2869df84ab99838/tradingagents/memory/settlement.py)

- **Qlib은 연구 계층의 제한된 다음 실험 대상이다.** 기존 Factory를 유지하면서 하나의 독립 점수와 분할 검사를 시험할 수 있다. 라벨 경계 제어는 필수다.
- **FinRL-Trading은 미장 수익률 challenger로 유지한다.** 이번 함수 검증은 고정 소스 재현과 날짜 절단에 한정된다. 저자 성과 재현과 우리 기준의 비용 후 성과가 남았다.
- **TradingAgents는 판단·복기 Shadow 후보로 유지한다.** 동일 증거에서 신규 근거의 정확성과 정정 반영을 실제 그래프로 검증할 때 자리를 결정한다.

이번 회차 외부 후보의 신규 수익률 A/B는 0건이다. 운영 도입이나 전략 교체를 지지하는 신규 시장 성과는 없다.

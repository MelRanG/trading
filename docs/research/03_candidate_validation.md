# Task 2 후속 · 후보 실측과 도입 판정

## 실험 순서

1. 시장별 기준선을 먼저 동결한다. 한국은 V79_NO63_VOL_GUARD 연구 기준선과 V69_PARENT 운영 대조군, 비용 반영 069500을 사용한다. 미국은 날짜별 거래 가능 종목, 기업행사·상폐, 공시 관측 시각, 동일 비용과 거래 가능 시각이 확인된 별도 기준선을 요구한다.
2. 입력을 검증한다. 원본·정정·수신 시각, 공통 거래일, 시간대와 입력 해시를 남긴다. 미장 공시는 원천과 수집기의 차이를 먼저 확인한다. 한국 공시는 ETF 연결의 유효기간이 있어야 종목 신호에 활용할 수 있다.
3. 동일 조건에서 하나의 투자 판단만 바꾼다. 데이터 도구는 원문 정확도·시간·커버리지, 검증 도구는 알려진 누수나 데이터 결함의 검출률, 운용 도구는 장애 후 원장 일치율을 비교한다. 이 결과를 수익률로 환산하지 않는다.
4. 비용 후 초과수익, 비용 2배, 낙폭, 표본 불확실성 및 재현성을 확인한 뒤 도입을 판단한다. 역사 구간 재사용은 개발 증거다. 독립 기간과 Forward는 따로 기록한다. 새 수익 가설은 Factory의 사전등록과 회차당 최대 한 번의 운영 replay를 적용한다.

현재 보고서는 격리된 적합성 실험과 기존 동결 성과의 독립 재계산을 다룬다. 외부 도구를 전략에 연결한 새 운영 replay와 실제 주문 실행은 이 회차 범위에 포함하지 않았다.

## 기존 기준선 비교 독립 재계산 · Terra

`runtime/v79_high252_proximity_operational_replay/replays/*/daily_nav.csv`를 읽고 2021-10-13~2026-07-31의 같은 1,173거래일을 확인했다. 초기 1,000만원으로 최종 NAV와 누적수익률을 재계산했다.

| 경로 | 최종 NAV | 누적수익률 | MDD¹ | Sharpe¹ |
|---|---:|---:|---:|---:|
| V79_NO63_VOL_GUARD | 24,366,149원 | +143.66% | -26.87% | 0.946 |
| V79_HIGH252_PROXIMITY_VOL_GUARD | 24,105,396원 | +141.05% | -26.87% | 1.000 |

¹ 저장된 `comparison_metrics.csv` 값. 이 실험에서 challenger는 260,753원, 2.61%p 뒤졌다. 비용 2배는 기존 계약에서 비교 불가다. 다른 시점의 `contract_aligned_comparison_20261004_run2`와 기준선 수치가 달라 서로 섞지 않는다. 국내 과거 산출물 재계산이며 외부 GitHub 후보의 신규 수익률 실험으로 집계하지 않는다.

## 미장 데이터 준비도 · Luna

SEC Apple 10-Q accession `0000320193-26-000020`의 index와 header는 2026-07-31 06:01:02 ET에 일치했다. [공식 index](https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/0000320193-26-000020-index.html) · [공식 header](https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/0000320193-26-000020-index-headers.html)

같은 건의 submissions JSON 접수 시각은 네 시간 차이가 보고됐다. EdgarTools 6.0의 header 기반 `accepted_at`을 검토할 가치가 있다. SEC에는 실제 원문 최초 공개 시각 필드가 없으므로 접수 시각과 수신 시각은 분리한다. 저장소에서 미장 시점별 거래 가능 종목과 기업행사 포함 가격 입력을 확인하지 못했다. 공시 한 건이 정확해도 전체 수익률 A/B 준비가 된 것은 아니다. [EdgarTools 시간 이슈](https://github.com/dgunning/edgartools/issues/1501) · [SEC FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)

**설치한 PyPI 6.0.0 확인.** 공식 표본의 header 필드로 만든 오프라인 fixture에서 `IndexHeaders.load()`는 accession, 10-Q, 06:01:02를 정확히 파싱했으며 시각에 시간대가 없었다. 해당 설치 버전에는 문서의 `Filing.accepted_at` 속성이 없고 `Filing.index_headers`와 `IndexHeaders.acceptance_datetime`이 있었다. 패키지와 문서의 API 차이를 기록하고 실제 채택 시 ET 정규화와 버전 고정을 요구한다. SEC HTTP 요청용 연락처 설정이 없어 라이브 라이브러리 수집은 미검증이다. 임시 설치는 제거했다.

## 저자 결과 재현 준비도 · Terra

FinRL-Trading README의 Adaptive Rotation은 2018-01~2025-10 누적 4.80배, 연 22.32%, MDD -21.46%를 보고한다. 별도 2025-10~2026-03 저자 Alpaca Paper ensemble은 +19.76%다. 두 결과는 기간·구성이 달라 별개로 검증한다. 저자 결과를 후보 근거로 유지하고, 정확한 커밋·설정·종목 그룹 이력·VIX·공급자 데이터 스냅샷·실행 로그를 확보한 후 재현한다. 외부 backtest는 `bt` 기반이며 가격·비중 행렬과 비중 forward-fill이 우리 Paper 계약과 어떻게 다른지 확인해야 한다. 현재 환경에서 `bt`, Qlib, RD-Agent를 가져올 수 있는 설치 상태는 확인되지 않았다. Qlib은 고정 데이터로 소규모 점수 검증을 우선한다. RD-Agent는 외부 연구 루프 전체를 실행하기 전에 하나의 동결 가설로 증분 가치를 확인한다. [저자 결과](https://github.com/AI4Finance-Foundation/FinRL-Trading#results) · [엔진 코드](https://github.com/AI4Finance-Foundation/FinRL-Trading/blob/master/src/backtest/backtest_engine.py)

## 데이터 검사 실측 · Luna

Pandera 0.36.0을 임시 디렉터리에 설치해 정상 OHLC와 고가 오류 fixture를 기존 검사에 대조했다. 양쪽이 정상 데이터를 허용하고 고가 오류를 차단했다. 기존 updater는 중복 날짜도 차단했다. 26종 합성 freshness fixture는 정상·오래됨·불완전 상태를 각각 구분했다. 이 범위에서 Pandera의 추가 검출 이점은 관측되지 않았고 임시 설치는 제거했다. skfolio 비교는 미실행이다. updater pytest는 진행 표시 10개 후 종료 요약이 나오지 않아 중단했다.

## 현재 도입 판단

| 결정 | 후보와 다음 증거 |
|---|---|
| 미장 수집기 비교 | EdgarTools는 SEC 직접 수집과 시간·정정·원문 해시를 대조한다. 실제 데이터 어댑터 선정은 표본을 확장한 뒤 결정한다. |
| 수익 가설 유지 | FinRL-Trading은 저자 재현 후 같은 미국 유니버스와 비용으로 비교한다. Qlib은 국내 데이터에서 독립 점수 한 가지를 검증한다. RD-Agent와 ai-hedge-fund는 구체적인 가설 한 가지의 재현 입력을 확보하면 시험한다. FinRobot과 TradingAgents는 동일 공시 원문에서 누락된 증거를 추가로 찾는지 비교하고, 그 정보가 거래에 미치는 영향은 별도 측정한다. |
| 검증 기능 한정 | skfolio와 vectorbt는 각각 날짜 분할과 산식 대조 후보로 유지한다. Freqtrade는 누수 결함 fixture 설계에 활용 가능하다. Pandera는 이번 오류 시험에서 중복이므로 도입을 보류한다. |
| 운영 필요가 확인될 때 평가 | Lean, NautilusTrader, LangGraph, Temporal, Langfuse, KIS 및 tossinvest는 체결·관측·재시작·연동 요구와 별도 비교한다. |

미장 비교를 시작하는 최소 단위는 시점별 거래 가능 종목과 상폐를 포함하는 가격 표본, 공시 접수·실제 관측 시각의 구분, 가격 기반 기준선, 공시 가설 한 가지다. 전체 후보를 설치하는 것보다 이 공통 입력과 계약의 동결이 먼저다. 국내에서는 기존 V79 비교의 계약 불일치를 정리한 뒤 새로운 투자 판단 하나를 넣는 편이 수익 기여를 측정하기 쉽다.

## 내부 검증

`compileall -q src scripts tests` 종료 코드 0. Factory·diagnostics·robustness 세 파일의 테스트 함수 17개를 독립 임시 디렉터리를 제공해 직접 호출했고 모든 assertion이 성공했다. 이는 pytest 전체 러너의 성공과는 별개다. 같은 세 파일의 pytest는 100% 표시 뒤 종료 요약을 반환하지 않아 중단했다. 전체 회귀 미실행.

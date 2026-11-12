# 개별주식 시스템 · 외부 후보 최종 검증

2026-11-12 KST · [18개 후보 비교](02_repository_comparison.md) · [실제 가격 실험](05_market_pilots.md)

**최종 방향**은 현행 주문·원장을 유지하고, 주식 선정 연구와 복기 워크플로를 분리해 붙이는 것이다. 현 단계의 연구 우선순위는 FinRL 잔차 모멘텀 한 가지의 재검증이다. 판단 증거 수집은 SEC 공시 원문과 실제 관측 시각을 중심으로 하며, 복기는 TradingAgents의 정산/기억과 LangGraph를 제한된 Shadow에서 사용 가능하다. 실측된 외부 수익률만으로 운용 모델을 교체할 근거는 확보되지 않았다.

## 기준

주식 선정 후보는 동일 종목과 실행 계약에서 비용 후 순성과를 평가한다. 데이터·복기·운영 도구는 해당 기능의 정확성, 기존 대비 이점, 통합 비용으로 평가한다. 실제 시장 표본과 합성 fixture, 외부 코드 실행과 소스 점검을 구분한다.

## 운영 대조 실측

- 기존 코드의 V88 주문 복구, Paper 권한·유동성·가격 가드, Toss 조회 경계 관련 테스트 함수 17개를 직접 호출했고 종료 코드 0을 확인했다. 접수 응답 유실 후 중복 차단, 같은 ID의 intent 변조 차단, 부분 체결 및 HOLD_ONLY, GET 제한, 계좌 마스킹을 포함했다. 첫 실행은 Windows의 임시 SQLite 파일 정리에서 파일 잠금으로 종료 코드 1이었고, 재실행은 임시 파일 정리 오류 허용 상태로 검증했다. 전체 pytest 결과가 아니다.
- Temporal Python SDK 1.36.0을 임시 설치해 [고정 커밋](https://github.com/temporalio/sdk-python/tree/4733537c4a1d523fa1f0081c18512d895f4f88b8/tests/worker)의 워크플로와 두 기록을 실제 `Replayer`에 전달했다. 정상 기록은 성공했고 비결정적 기록은 `NondeterminismError`를 반환했다. 서버나 주문 연동 없이 시험했으며, 기존 일일 작업과 복구 시간의 우위를 측정한 결과는 아니다.
- LangGraph 1.0.10과 SQLite에서 별도 프로세스로 복기를 재개하고 중복 없이 두 결과를 저장한 테스트는 [실제 가격 실험](05_market_pilots.md)의 후속 검증에 있다. 현재 복기 범위에 Temporal을 추가할 운영 이점은 확인되지 않았다.
- tossinvest Python SDK 0.0.4의 [고정 커밋](https://github.com/ongjin/tossinvest/tree/6cf7fd248daf8fcc5ab17968d34644fa5d52e027/pytossinvest)에서 `tests/test_market_data.py`를 격리된 RESpx 모의 HTTP로 실행했다. 11개 진행 표시와 종료 코드 0을 확인했다. 종목 목록·수급·순위·시장지표 등 요청 계약 시험이다. 모의 토큰만 사용했으며 실제 Toss 승인과 계정별 응답은 미확인이다.
- Freqtrade의 [고정 소스](https://github.com/freqtrade/freqtrade/blob/5197bedab82559fac6be6c1539c64b94368fb91c/freqtrade/optimize/analysis/lookahead.py)에서 `analyze_indicators` 함수만 추출해 합성 주식 데이터의 전체/절단 입력을 비교했다. 미래 행을 참조하는 열만 탐지하고 인과적 이동평균은 탐지하지 않았다. 전체 Freqtrade 설치나 거래 실행은 이 결과에 포함되지 않는다.
- KIS의 [해외주식 일봉 예제](https://github.com/koreainvestment/open-trading-api/blob/3a9be59a3ed8745720dc3aa9d584bdf3b7830362/examples_llm/overseas_stock/dailyprice/dailyprice.py) 함수에 모의 응답을 넣었다. 두 페이지는 올바르게 합쳤으나 최대 페이지 깊이에서는 부분 데이터프레임을 정상 반환과 같은 형태로 돌려줬다. 도입 시 날짜 커버리지 검증이 필요하다. 실제 계정 호출은 없었다.

## 수치 검증 도구 실측

- **vectorbt 0.28.1**은 격리 환경에서 NumPy 2.2.6과 Plotly 5.24.1을 사용해 실행했다. 기존 Yahoo AAPL 21일 수정종가 표본에서 둘째 날 10주 매수, 마지막 날 10주 매도, 초기 $10,000과 편도 10bp를 적용했다. 실제 `Portfolio.from_orders`와 독립 현금·수량 계산의 일별 NAV 최대 차이는 표시 정밀도에서 0.0000000000달러였다. 최종 NAV $9,997.839532, 체결 2건. 독립 산식 검증의 근거이며 기존 운영 체결·세금·주문 상태까지 보장하지 않는다.
- **skfolio 0.15.1** 일반 import는 NumPy/SciPy 버전 경고와 CVXPY 타입식 오류로 실패했다. 설치 패키지에서 분할 모듈을 읽어 실행 시 쓰지 않는 타입 import만 제거하고, 60행·6 folds·2 test folds·purge 2·embargo 1로 실행했다. 15개 split의 테스트 fold 30개에서 주변 금지 구간의 학습 인덱스가 없었다. 종료 코드 0이며, 분할 함수 범위의 결과다. 전체 패키지 및 최적화는 미검증이다.

## 도입 결정표

### FinRL 실제 전략 엔진 실측 · Terra

고정 커밋 `4409abe925c904e570be78ebfb5e77ac3491dff8`의 실제 `AdaptiveRotationEngine`과 설정 v1.2.2를 Yahoo의 설정 종목 31개(주식·상품 ETF·시장지표 포함)에 적용했다. 2024-12-27 확정 종가 시점, 빈 포지션에서 risk-on과 META·NVDA·AMZN 각 1/3을 반환했다. 동일 입력 재실행과 12월 30~31일 가격을 3배로 바꾼 실행에서도 비중이 같았다. 이는 한 세션의 신호 검사이며, 전체 백테스트·주문·포지션 의존 경로나 저자 성과 재현으로 집계하지 않는다.

별도로 기존 6종목 비교에서 신호·가격·비용을 고정하고 교체 시점에 90%만 진입시키는 사후 민감도를 계산했다. 누적 +255.71%, MDD -19.10%로 원래 전액 진입의 +302.69%/-20.87%와 비교된다. 2020~22 +161.60%, 2023~24 +35.97%였다. 90%는 체결 시점 조건으로 보유 기간 중 가격 움직임에 따른 초과는 허용한다. 독립 OOS나 지속적 위험 상한 검증은 아니다. 원본 입력과 요약은 `runtime/candidate_market_pilot/finrl_final/`에 있다. 전략 엔진 재실행에는 고정 커밋과 별도 임시 의존성이 필요하다.

같은 업스트림 엔진의 실제 신호를 2024년 51회 생성해 다음 NYSE 거래일 수정 종가, 편도 10bp, 초기 $10,000으로 계산했다. 첫 체결일은 양쪽 모두 2024-01-08이다. 후보는 **+10.29%, MDD -15.67%, Sharpe 0.582**, SPY는 **+24.95%, MDD -8.41%, Sharpe 1.857**이었다. 후보 거래 leg 443개, 비용 $740.50. 업스트림 엔진에 매주 빈 포지션을 넘겨 현재 포지션 기반 손절·일간 위험 모니터링이 빠졌고, 휴장 금요일의 신호는 생략했다. 주식 이외 자산도 포함된 저자 설정과 별도 가상 체결을 사용했다. 따라서 이는 원래 저자 결과 재현이나 6종목 순위 실험과 같은 계약의 A/B가 아니다. 이 실행 구성은 수익률과 낙폭 양쪽에서 SPY를 넘지 못했다. `finrl_final/weekly_summary.json`에 원시 결과가 있다.

### 후보별 판정

Luna가 TradingAgents 고정 커밋 `9fa1196f`의 실제 upstream 그래프 테스트를 ScriptedModel과 모의 데이터 도구로 실행해 15개 통과를 확인했다. 라우팅·도구 호출·기억/정산 흐름의 증거이며 모델 판단 품질은 별도다. ai-hedge-fund `5c553b5`는 백테스트·리서치·원장·배분·리스크 테스트 107개 통과, Paper runner 포함 확장 실행은 114개 통과·2개 실패였다. 실패는 Windows 파일 rename 충돌과 stale PID 검사 오류였다. FinRobot은 외부 LLM 및 SEC/RAG 설정이 필요한 경로를 확인했고 에이전트 실행은 미실행이다. RD-Agent는 `fuzzywuzzy` 부재로 Qlib 테스트 수집 단계에서 막혔다. 두 후보 모두 수익 가설의 기각으로 판정하지 않는다. [실행 상세](../../runtime/candidate_market_pilot/agent_frameworks/validation_summary.json)

| 후보 | 기존 시스템에 넣을 범위와 판정 |
|---|---|
| FinRL-Trading | 잔차 모멘텀은 개별주식 연구 후보로 유지. 기존 6종목 탐색에서 단순보유보다 높은 누적수익을 보였으나 동일비중보다 낙폭·Sharpe가 나빴다. 투자 경로 승격 보류. |
| Qlib | Rank IC와 시점별 자료 검증의 독립 대조 도구로 유지. 검증 기간을 참조하는 학습 라벨 제거는 별도 수행. 실측한 20일 가격 모멘텀은 투자 신호로 제외. |
| TradingAgents | 실제 복기 코드와 LangGraph 체크포인트는 검증 전용으로 부분 사용 가능. 전체 판단 그래프의 증분 효과는 별도 판정. |
| FinRobot | SEC 공시 정보 추출 후보. EdgarTools와 같은 원문을 받아 수치·정정·인용을 비교하는 연구 입력 단계에 한정. |
| ai-hedge-fund | 논거와 투자 판단의 비교 후보. 전체 운용·포트폴리오 엔진 도입 보류. |
| RD-Agent | 가설 제안 후보. 기존 Factory와 중복되는 전체 자동 연구 루프 도입 보류. 저자 성과는 별도 재현 후보로 보존. |
| EdgarTools | 미국 공시 수집의 후보. 6.0.0 SEC 헤더 파싱 실측에서 시각은 맞았고 시간대는 없었다. 수신 시각·정정 검증 후 연구용 데이터 어댑터로 한정. |
| skfolio | 시계열 분할 검증 및 배분 독립 대조 후보. 배분 정책 변경은 별도 수익 검증 필요. |
| vectorbt | 탐색용 체결·회계 독립 대조 후보. 운영 원장 교체는 보류. |
| Pandera | 정상·불량 OHLC 대조에서 기존 검사와 동일한 결과. 중복 기능이므로 도입 보류. |
| LangGraph | 복기 워크플로의 격리 연구 경로에서 부분 채택 가능. 계좌 상태와 주문 멱등성은 기존 원장에 둔다. |
| Temporal | 정상·비결정 이력 구분 실측. 다중 장기 작업 복구 요구가 생길 때 평가. |
| Langfuse | LLM 호출 비교와 비용 관측 후보. 도입 보류. 실제 LLM 사용량과 운영 부하가 필요한 경우 검토. [평가 기능 소스](https://github.com/langfuse/langfuse/tree/main/web/src/features/evals) |
| Freqtrade | 시계열 누수 검사의 구조만 참고. 암호화폐 엔진은 현재 주식 실행 경로에서 제외. [누수 검사 소스](https://github.com/freqtrade/freqtrade/blob/develop/freqtrade/optimize/analysis/lookahead.py) |
| Lean | 미장 체결·기업행사 독립 대조 후보. 소스 확인 범위이며 KRX/Toss 원장 대체 보류. [주식 체결 모델](https://github.com/QuantConnect/Lean/blob/master/Common/Orders/Fills/EquityFillModel.cs) |
| NautilusTrader | 브로커 보고서 기반 복구와 이벤트 대사 참고. 소스 확인 범위이며 엔진 교체 보류. [실행 대사 코드](https://github.com/nautechsystems/nautilus_trader/blob/develop/crates/live/src/execution/manager.rs) |
| KIS Open Trading API | KRX·미국 주문·시세 계약의 브로커 선택지. 해외 일봉의 모의 페이지 처리까지 검증. 계정·실시간·데이터 권리 검증 전 도입 보류. [해외주식 예제](https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock) |
| tossinvest | 국내 종목·시장 데이터 어댑터 참고. 공식 Toss 계약 검증을 기존 read-only 경로에서 유지하고 주문 라이브러리 교체는 보류. |

저장소의 `compileall -q src scripts tests`는 종료 코드 0이었다. 전체 프로젝트 회귀는 실행 범위에 포함하지 않았다. Lean과 NautilusTrader는 이번 PC에서 `dotnet`·`cargo`가 확인되지 않았고 외부 엔진 빌드를 실행하지 않았다. Langfuse는 소스 확인 범위다. 표의 18개 판정은 각 후보가 적합한 연구/운영 역할과 확인된 증거 수준을 종합한 것으로, 외부 패키지 18개의 통합 테스트를 의미하지 않는다.

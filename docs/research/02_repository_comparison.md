# Task 2 · GitHub 교차 검증과 수익률 실험 우선순위

2026-11-12 KST · [Task 1](01_github_discovery.md) 후속

## 결정

**미장용 EdgarTools는 공시 데이터 계층의 부분 채택 1순위다. 수익률 검증 1순위는 같은 미국 종목·가격·비용에서 SEC 공시 신호를 한 가지 추가했을 때의 순초과수익이다.** SEC 원문 수집 도구의 가치는 재현 가능한 공시 입력을 만드는 데 있다. 매매 성과는 별도 실험 결과에 달려 있다. 한국에선 이미 있는 OpenDART를 사용한다. 미장 실행 어댑터와 장애 복구는 투자 가설의 우선순위 산정에서 분리했다.

현재 기준은 일일 Paper의 V69_PARENT와 연구 replay의 V69/V79 경로다. `paper_decision_runtime.py:251–258,469–474`는 이 둘을 분리하고, `config/v104_challenger_runtime_contract.yaml:20,33,46`은 신규 Forward 후보를 비활성화한다. `news_shadow_runtime.py:20,53`에 OpenDART 입력이 있고, `alpha_research_factory_completion.py:219–227`은 국내 공시 자료의 부분 커버리지 및 정적 ETF 구성 연결 문제를 기록한다. 기존 Factory의 계약 해시·중복 차단·예산·승격 승인과 Paper 원장은 외부 앱의 대화 로그나 단순 백테스트보다 현 저장소의 통제 요구에 가깝다.

## 교차 비교

저자가 공개한 성과와 독립 재현 결과는 증거 수준을 구분해 기록한다. 저자 보고만 있다는 이유로 후보를 제외하거나 후순위로 내리지 않는다. FinRL-Trading과 RD-Agent도 코드·설정·입력·비용·비교 기준선을 복원할 수 있으면 검증 후보로 유지한다. 재현 자료가 일부 부족하더라도 국내·미장에 적용할 수 있는 구체적인 가설이 있으면 동일 조건에서 축소 실험을 설계한다. 공개 이슈·재현 사례는 주장에 대한 검증 자료로 쓰고, 반박이 없다는 사실은 성과 증명으로 집계하지 않는다.

표는 두 목록의 합집합 18개를 다룬다. 날짜는 GitHub REST가 반환한 최근 push 날짜(2026년)다. 모두 archived=false였다. 구현 링크와 Git 트리를 확인했으며 테스트 실행 및 외부 성과 재현은 미수행이다. 경로 확인만 된 항목은 해당 기능의 정확성까지 확정하지 않았다. 라이선스는 저장소 메타데이터 기준이며 판정 미제공 시 패키지·파일 단위 검토가 필요하다. 순위는 투자 입력의 증분성, 편향 통제, 국내·미장 적용성과 준비 비용을 기준으로 했다.

| 후보 / 출처 | push · 라이선스 | 코드·성과 근거와 판정 |
|---|---|---|
| [EdgarTools](https://github.com/dgunning/edgartools) / Task 1 | 11-12 · MIT | **부분 채택 1순위**, 미장 SEC 공시 수집. [공시 구현](https://github.com/dgunning/edgartools/blob/main/edgar/entity/filings.py)과 [접수 시각 오차 이슈](https://github.com/dgunning/edgartools/issues/1501). 공식 문서 SGML 접수 시각과 자료 배포 가능 시각을 검증해야 한다. 한국은 설계 참고. 초과수익 근거는 확보되지 않았다. 중간 비용. |
| [Qlib](https://github.com/microsoft/qlib) / 공통 | 11-04 · MIT | **부분 채택 2순위**, [PIT 처리](https://github.com/microsoft/qlib/blob/main/qlib/data/pit.py)와 [벤치마크](https://github.com/microsoft/qlib/tree/main/examples/benchmarks)의 데이터·학습 분리. KRX/미장 둘 다 자체 PIT 데이터 필요. 독립 점수 산출로 한정하면 원장 교체 비용을 피한다. 중간~높음. |
| [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) / ChatGPT | 10-24 · Apache-2.0 | **부분 채택 검토 3순위**, [공시 파서](https://github.com/AI4Finance-Foundation/FinRobot/blob/master/finrobot_autogen/finrobot/data_source/filings_src/sec_filings.py), [에이전트 구성](https://github.com/AI4Finance-Foundation/FinRobot/blob/master/finrobot_autogen/finrobot/agents/workflow.py). SEC fixture 경로는 확인했다. 공시의 인용·정량 추출을 비교하는 용도이며 보고서 품질과 매매 수익은 별도로 평가. 국내 DART 전환 필요. 중간. |
| [skfolio](https://github.com/skfolio/skfolio) / 공통 | 11-10 · BSD-3-Clause | **부분 채택**, [분할 코드](https://github.com/skfolio/skfolio/tree/main/src/skfolio/model_selection)·[테스트 트리](https://github.com/skfolio/skfolio/tree/main/tests/test_model_selection). 양 시장 공통으로 purge/embargo를 독립 대조. 최적화 모형 도입은 별도 가설이 있어야 한다. 중간. |
| [TradingAgents](https://github.com/TauricResearch/TradingAgents) / 공통 | 11-04 · Apache-2.0 | **부분 채택 검토**, [토론·결론 그래프](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/graph/trading_graph.py)와 [저자 논문](https://arxiv.org/abs/2412.20138). 공시 기반 반론·누락 발견을 블라인드 평가할 가치. LLM 사전학습으로 역사 사건을 기억할 수 있어 역사 숫자만으로 결론을 내릴 수 없다. 중간~높음. |
| [FinRL-Trading](https://github.com/AI4Finance-Foundation/FinRL-Trading) / ChatGPT | 09-18 · Apache-2.0 | **보류**, [adaptive rotation](https://github.com/AI4Finance-Foundation/FinRL-Trading/tree/master/src/strategies/adaptive_rotation)과 [backtest 엔진](https://github.com/AI4Finance-Foundation/FinRL-Trading/blob/master/src/backtest/backtest_engine.py). README 미국 과거 결과는 저자 보고이며 동일 위험·수수료·데이터로 독립 재현 미완료. 미장 회전 전략 아이디어로만 후보화. KRX 이식 부담 높음. |
| [ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) / ChatGPT | 11-09 · MIT | **보류**, [백테스트 진입점](https://github.com/virattt/ai-hedge-fund/blob/main/hedge_fund/tui/backtest.py)과 [테스트](https://github.com/virattt/ai-hedge-fund/blob/main/hedge_fund/tui/test_backtest.py). 분석가 논거 포맷은 참고 가능. TUI 테스트가 PIT·회계·알파 검증을 대신하지 않는다. 미국 데이터 공급자 및 LLM 비용, 국내 어댑터 필요. |
| [RD-Agent](https://github.com/microsoft/RD-Agent) / 공통 | 10-21 · MIT | **보류**, [Qlib 실험 루프](https://github.com/microsoft/RD-Agent/tree/main/rdagent/scenarios/qlib). 공개 성과는 저자 기술보고서 수준으로 취급. 현 Factory와 중복되고 생성·수정 반복에 따른 연구 자유도가 크다. 연구 인력이 늘 때 후보 제안만 별도 검토. 높음. |
| [vectorbt](https://github.com/polakowo/vectorbt) / ChatGPT | 11-11 · GitHub NOASSERTION | **부분 채택 검토**, [포트폴리오 구현](https://github.com/polakowo/vectorbt/blob/master/vectorbt/portfolio/base.py)·[테스트](https://github.com/polakowo/vectorbt/blob/master/tests/test_portfolio.py). 양 시장 신호 스크리닝 또는 독립 산식 대조. 기존 주문 원장 대체 가치는 낮다. NumPy/Numba와 [정확한 라이선스](https://github.com/polakowo/vectorbt/blob/master/LICENSE.md) 조건 확인 후 사용. |
| [Pandera](https://github.com/unionai-oss/pandera) / Task 1 | 11-11 · MIT | **운영 부분 채택 검토**, [스키마 구현](https://github.com/unionai-oss/pandera/blob/main/pandera/api/pandas/container.py)·[테스트](https://github.com/unionai-oss/pandera/tree/main/tests). 양 시장 공통. 기존 freshness/V87 대비 잡아내는 추가 오류가 있을 때만 이득. 낮음. |
| [Lean](https://github.com/QuantConnect/Lean) / ChatGPT | 11-12 · Apache-2.0 | **미장 운영 보류**, [주식 fill 모델](https://github.com/QuantConnect/Lean/blob/master/Common/Orders/Fills/EquityFillModel.cs)·[브로커 테스트](https://github.com/QuantConnect/Lean/tree/master/Tests/Brokerages). 미국 주식의 체결·기업행사 독립 대조 우선, Toss/KRX 적용과 데이터 비용 별도. 높음. |
| [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) / 공통 | 11-12 · LGPL-3.0 표기 | **운영 보류**, [이벤트 대사 코드](https://github.com/nautechsystems/nautilus_trader/blob/develop/crates/live/src/execution/manager.rs). 한국·미장 어댑터 비용에 비해 일봉 알파에 직접 기여할 근거 부족. 초단기 또는 이벤트 기반 모델에서 대사 재검토. 높음. |
| [LangGraph](https://github.com/langchain-ai/langgraph) / ChatGPT | 11-12 · MIT | **보류**, [Postgres 체크포인트](https://github.com/langchain-ai/langgraph/tree/main/libs/checkpoint-postgres) 및 패키지 테스트 트리. 연구 대화 상태를 저장할 때 사용 가능. append-only 계약·금융 원장은 기존 경로 유지. 중간. |
| [Temporal Python](https://github.com/temporalio/sdk-python) / 공통 | 11-11 · MIT | **보류**, [workflow replay](https://github.com/temporalio/sdk-python/blob/main/temporalio/worker/_replayer.py) 및 [테스트](https://github.com/temporalio/sdk-python/tree/main/tests). 지속 실행 장애 비용이 확인될 때 평가. 서비스 운영 부담 높음. |
| [Langfuse](https://github.com/langfuse/langfuse) / ChatGPT | 11-12 · GitHub NOASSERTION | **보류**, [평가 기능](https://github.com/langfuse/langfuse/tree/main/web/src/features/evals)과 UI 테스트 파일 확인. 여러 프롬프트 비교·비용 분석에 유용하나 원문 보존·PIT 검증은 별도. 코어와 엔터프라이즈 조건을 분리 검토. 중간. |
| [Freqtrade](https://github.com/freqtrade/freqtrade) / ChatGPT | 11-12 · GPL-3.0 | **엔진 제외, 검사 참고**, [lookahead 구현](https://github.com/freqtrade/freqtrade/blob/develop/freqtrade/optimize/analysis/lookahead.py)·[결함 fixture](https://github.com/freqtrade/freqtrade/blob/develop/tests/optimize/test_lookahead_analysis.py). 암호화폐 거래 엔진 이식보다 날짜 절단 후 신호 불변 테스트를 주식에 적용. |
| [KIS Open Trading API](https://github.com/koreainvestment/open-trading-api) / ChatGPT | 10-27 · 루트 메타데이터 미제공 | **공식 어댑터 참고**, [해외주식 예제](https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock). 한국·미장 브로커 대안. 샘플과 실제 계정 지원·공식 계약·시장 데이터 권리를 각각 확인할 필요. 중간~높음. |
| [tossinvest](https://github.com/ongjin/tossinvest) / ChatGPT | 11-12 · 루트 메타데이터 미제공 | **어댑터 참고**, [Python 클라이언트](https://github.com/ongjin/tossinvest/blob/main/pytossinvest/src/pytossinvest/client.py)·[stream/API 테스트](https://github.com/ongjin/tossinvest/tree/main/pytossinvest/tests). 패키지 LICENSE가 별도로 있다. 공식 Toss 계약과 테스트를 대조할 때 가치. 현재 read-only 어댑터 교체나 미국 종목 범위는 미확정. |

Task 1이 놓친 후보 중 **FinRobot은 공시의 분석 품질**, **Lean은 미국 주식의 체결·기업행사 대조**, **KIS는 두 시장 브로커 선택지**, **Freqtrade는 미래정보 검사 설계**에 실질적 가치가 있다. Task 1에서만 제시한 EdgarTools와 Pandera는 각각 입력과 검증의 좁은 문제를 푼다. 공통 후보라도 Qlib/skfolio는 독립 검증에 구체적인 역할이 있고 RD-Agent/Temporal은 현 단계의 중복 비용이 크다. TradingAgents·FinRobot·ai-hedge-fund를 한 번에 섞으면 수익 차이의 원인을 분리하기 어렵다. 원문 수집은 EdgarTools, 비교할 추출기 하나는 FinRobot, 독립 반론은 추출 효과를 확인한 뒤 TradingAgents를 검토한다. Lean·Nautilus도 각각 미국 일봉 체결 대조와 이벤트 복구에 목적을 한정한다.

## 최소 A/B 계약

### 1. 미장 SEC 공시의 수익 기여

- **A**는 미국 유니버스에서 사전 동결한 가격 기반 기준선이다. KRX V69/V79를 미장에 그대로 복제한 성과는 현재 확보되지 않았다. 동결 전에 미국 시장 baseline의 시그널·체결 계약과 거래 가능한 비용 반영 benchmark를 지정한다.
- **B**는 동일 모델에 공시 기반 판단 하나만 추가한다. 첫 가설은 공식 중요 공시의 단일 유형이 다음 거래 가능한 시점 이후 비용 후 성과에 증분 정보를 주는지다. 사건 정의·신호 방향·노출 변경 한도·평가 horizon은 결과를 보기 전에 등록한다. 결정 시점에는 공식 접수와 당시 이용 가능 시각이 확인된 원문만 사용한다. 공식 접수 시각만 있는 경우 실제 배포 지연을 재현할 수 있는 범위를 표기하고 신규 shadow에서 최초 수신 시각을 별도 기록한다.
- 먼저 표본 공시의 원문/정정 연결, CIK와 거래 가능 종목의 시점별 연결, 개장 전후 사건 분류를 확인한다. 가격에는 상폐·코드변경·기업행사·배당을 포함하고, 매수 가능 가격·비용·환전/환율 기준을 양쪽에 동일하게 적용한다. 소스가 불충분하면 해당 구간의 수익 검증을 보류한다.
- 1차는 동일 종목·날짜에서 비중복 수익·이벤트 이후 spread와 블록 부트스트랩 신뢰구간을 본다. 동일 섹터·월 안 사건 날짜를 섞은 placebo, 공시 제거 ablation을 포함한다. 통과 후에만 동일 실행 경로에서 비용 후 연환산 초과수익, MDD, turnover, 수익 집중도 및 2배 비용 스트레스를 비교한다. 배당·최종 청산 처리도 동일하게 둔다. 반복 사용한 기간은 개발로 분류하고 purge/embargo 후 동결한 독립 기간 및 Forward Shadow를 따로 집계한다.

### 2. FinRobot이 실제 새 정보를 발견하는지

A는 동결한 구조화 공시 추출기, B는 동일 EdgarTools 원문에 FinRobot식 추출을 추가한 경로다. 같은 시간·호출 예산으로 당시 원문이 뒷받침하는 신규 정보 발견률, 오탐·누락, 근거 인용 정확도, 지연과 비용을 블라인드 비교한다. 이후 동일 신호 계약과 원장에서 순초과수익을 측정해야 추출 방식에 투자 가치를 귀속할 수 있다. LLM 평가에는 공개 역사 사건 기억의 영향을 줄이도록 동결 이후 자료를 별도로 사용한다.

### 3. Qlib/skfolio와 KRX 연구

동일 일봉과 V79 기준선에서 B는 사전등록한 점수 하나만 제공한다. skfolio는 분할·embargo 독립 대조에만 사용한다. 동일 유니버스·비용·ADV·최소주문금액·초기자본을 적용하고 V79 점수 중복, 비중복 IC/spread, 비용 후 성과를 본다. 기존 실패 가설의 재포장과 여러 모델 순위 경쟁을 Factory의 계약·예산으로 차단한다. 국내 공시 실험은 OpenDART의 시점별 ETF 연결이 확인된 범위에서 별도 수행한다.

## 조사 결과와 다음 작업 경계

이번 단계는 저장소 원문과 트리, 기존 코드, 공개 성과 자료를 대조하고 실험을 설계했다. **A/B 실행 및 신규 수익률 실측은 0건**이다. 외부 저장소 테스트 통과와 미래 초과수익은 미검증이다. 먼저 미국 기준선·기업행사·상폐 포함 가격·공시 관측 시각 확보 가능성을 확인하면, 전량 다운로드나 브로커 연결 없이 소규모 데이터 검증을 시작할 수 있다. 데이터 준비는 중간 이상이며 실험 코드 연결보다 시점별 유니버스와 이용 가능 시각을 확보하는 일이 크다. Gemini API 환경 설정 없이 GitHub 원문 및 REST 메타데이터를 사용했다.

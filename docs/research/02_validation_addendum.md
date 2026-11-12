# Task 2 보완 · 검증 미완료 후보 재평가

2026-11-12 KST · [후보 비교](02_repository_comparison.md) · [이전 최종 판정](06_candidate_final_decision.md)

## 수정한 결론

**FinRL 잔차 모멘텀의 단독 1순위를 철회한다.** 재실행하기 쉬운 후보로 남기되, 실적 변화·공시 이벤트와 같은 정보 기반 가설도 같은 주식·비용·위험 조건에서 비교한다. 현행 주문·원장은 Paper 연구의 대조군으로 유지하고, 재시작·사전 대사·저장 경계에 결함이 확인되면 해당 부분을 우선 교체한다. TradingAgents는 복기와 독립 반론을 비교할 후보, RD-Agent는 실험을 반복 개선하는 연구 후보로 각각 유지한다.

등급은 A 실제 시스템과 유사한 통합 검증, B 핵심 기능 실행, C 소스·테스트 구조, D 문서 주장이다. 기능별로 매겼으며 이번 외부 후보의 **자본 경로 A는 0건**이다. 실제 가격을 사용한 구성요소 시험도 그 사실만으로 A가 되지 않는다. Gemini 키가 없어 고정 GitHub 소스·격리 테스트를 직접 대조했다.

## 우선 후보 재검토

| 후보와 등급 | 실행·실패 원인 | 코드가 실제로 제공하는 기능과 한계 |
|---|---|---|
| RD-Agent **B 연결 / C 실제 연구 반복** | 누락된 `fuzzywuzzy`를 임시 설치해 재시도했다. 이후 `tiktoken` 누락으로 수집 종료 코드 2. 원본 `RDLoop`의 5개 메서드를 모의 개발기·평가기·요약기와 실행해 기록까지 도달, 종료 코드 0. 실제 코드 생성·Qlib 평가 미실행. | `_propose`는 trace와 plan을 읽고, `_exp_gen` → `coding` → `running` → `feedback` → `record`가 실험·피드백을 DAG와 이력에 저장한다. `QlibFactorRunner.develop`는 기존·신규 특징을 평가 작업공간에 넘기고 결과를 받는다. 실제 연구 반복 구조가 있고 기존 Factory의 단일 고정 검증보다 탐색 범위가 넓다. 반복 탐색의 과적합과 생성 코드 격리가 핵심이며, 주문이나 승인 권한은 기존 경로가 담당한다. [루프](https://github.com/microsoft/RD-Agent/blob/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/rdagent/components/workflow/rd_loop.py) · [평가기](https://github.com/microsoft/RD-Agent/blob/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/rdagent/scenarios/qlib/developer/factor_runner.py) |
| TradingAgents **B 판단 연결·복기 / C 실제 판단 효능** | 앞서 원본 그래프 테스트 15개 통과. ScriptedModel·모의 도구 사용. 별도 Yahoo 주식 복기와 SQLite 재개 확인. 실제 LLM 판단과 수익은 미실행. | 분석가·기억 조회 → Bull/Bear → Research Manager → Trader → 리스크 토론 → Portfolio Manager. `_memory_step`에서 만기 판단을 정산하고 당시 이용 가능한 복기를 프롬프트에 넣는다. 수익을 평가해 기억을 수정하는 흐름은 작동한다. 동일 모델의 상관된 오류, 다수 의견 추종, 결과를 본 뒤 만든 서사, 사전학습의 역사 사건 기억, 개별 판단 수익과 계좌 손익의 괴리를 통제해야 한다. 자체적으로 새 전략의 독립 검증이나 배포를 완결하지 않는다. [그래프](https://github.com/TauricResearch/TradingAgents/blob/9fa1196fffbcfd9de5146d2dd2869df84ab99838/tradingagents/graph/setup.py) · [기억 연결](https://github.com/TauricResearch/TradingAgents/blob/9fa1196fffbcfd9de5146d2dd2869df84ab99838/tradingagents/graph/trading_graph.py#L309) |
| FinRobot **C SEC/RAG 구조와 산출물** | Desktop `test_sec_provenance.py` 수집은 `aiosqlite` 누락으로 실패. 기존 임시 의존성을 연결한 재시도는 `pydantic_ai` 누락으로 실패. AutoGen 데모의 외부 모델·SEC/RAG 자격 조건과 별개인 환경 차단이다. | AutoGen 데모 외에도 Desktop은 `EdgarToolsProvider` → XBRL 수치·10-K/10-Q/8-K·섹션별 RAG → 결과 provenance 경로가 있다. 따라서 단순 대화 프레임워크 평가를 수정한다. 현재 Shadow 대비 구조화 재무 수치와 원문 위치를 늘릴 후보. 조회·청크의 filing date만으로 당시 이용 가능 시각이나 정정 이력을 보장하지 않는다. [공시 공급자](https://github.com/AI4Finance-Foundation/FinRobot/blob/63e1884a42ea7b729551a5424b4bd6a65af636e0/finrobot_desktop/finrobot/engine/data/providers/edgar_provider.py) · [산출물 테스트](https://github.com/AI4Finance-Foundation/FinRobot/blob/63e1884a42ea7b729551a5424b4bd6a65af636e0/finrobot_desktop/tests/audit/test_sec_provenance.py) |
| ai-hedge-fund **B 핵심 함수 / Windows 실패 2건** | 기존 107개 통과, runner 포함 114개 통과·2개 실패. `ledger.py:141`의 기존 경로 rename 충돌, `runner.py:223`의 POSIX식 `os.kill(pid, 0)`에서 Windows 오류 87. 이번에는 코드 원인 대조를 했으며 수정·재시험은 하지 않았다. | 보유·배분·위험 제한 및 Paper 결정을 한데 비교하기 좋다. 현재 원장에는 고유 client order ID·DB 잠금·재대사가 있어 교체 효용은 미확인이다. 논거 및 종목 판단 후보로 별도 비교할 가치가 있다. [Paper 원장](https://github.com/virattt/ai-hedge-fund/blob/5c553b5222044f6a5527bd377b4104c50ee0ad28/hedge_fund/paper/ledger.py#L141) · [runner](https://github.com/virattt/ai-hedge-fund/blob/5c553b5222044f6a5527bd377b4104c50ee0ad28/hedge_fund/paper/runner.py#L223) |
| FinRL-Trading **B 순위·원본 엔진 신호 / C 저자 운용 성과** | 6개 생존 주식에서 63일 잔차 모멘텀 월간 단일 종목 회전 +302.69%, 동일비중 +147.32%. 별도 2024년 저자 설정 31심볼 주간 엔진 신호와 간이 체결은 +10.29%, 동기간 SPY +24.95%. | 잔차 순위와 전체 전략의 그룹 강도·국면·위험·배분은 다른 판단이다. 월간/주간, 집중도, 종목군, 기간이 모두 다르고 주간 실험은 포지션 상태와 일일 손절이 빠졌다. 양 결과를 정반대의 전략 판정으로 해석할 수 없다. 저자 성과는 독립 검증 전 재현 후보로 유지한다. [고정 엔진](https://github.com/AI4Finance-Foundation/FinRL-Trading/blob/4409abe925c904e570be78ebfb5e77ac3491dff8/src/strategies/adaptive_rotation/adaptive_rotation_engine.py) · [실측](06_candidate_final_decision.md) |
| skfolio **B 정상 패키지 분할 / 최적화 미검증** | 0.15.1은 CVXPY의 `cp.trace` 타입식 오류와 NumPy/SciPy 경고가 있었다. 임시 환경에서 **0.15.4 + NumPy 2.2.6**으로 정상 import 및 15 split/30 test folds의 purge·embargo 검사 통과, 종료 코드 0. | 검증 분할 교차 대조에 사용 가능하다. 일수 고정 purge만으로 종목별 실제 라벨 종료일을 다룰 수 없는 경우에는 `[feature_date,label_end]` 구간과 검증 구간의 교집합을 직접 제거하고 embargo를 별도 적용한다. 간단한 경우 이 독립 함수와 경계 fixture로 대체 가능하다. [CVXPY 타입 수정 기록](https://github.com/skfolio/skfolio/blob/main/CHANGELOG.md) |

## 현행 주문·원장 판단

**FinRobot 추가 실측 · B(검색 구성요소), C(전체 분석).** 위 Desktop 테스트 수집 차단 뒤, `rank-bm25==0.2.2`만 임시 설치했다. 고정 소스의 `build_rag_chunks`, `chunk_text`, `BM25Index.search`를 저장소의 AAPL·JPM·BRK-B 10-K 텍스트 표본에 실행했다. 처음 고른 AAPL 섹션 JSON은 빈 배열이어서 fixture 실행을 중단했고, 보존된 텍스트 표본으로 바꾼 재실행은 종료 코드 0이었다. 총 228개 청크, 출처와 연속 청크 ID를 확인했다. `competition supply chain risk` 검색의 상위 3개 출처는 BRK-B, AAPL, AAPL로 반복 실행에서 일치했다. 이 실험은 검색의 재현성을 입증하며, 정답 인용률·기존 검색 대비 정보 증가·의사결정 개선은 다음 A/B의 측정 대상이다. [검색 구현](https://github.com/AI4Finance-Foundation/FinRobot/blob/63e1884a42ea7b729551a5424b4bd6a65af636e0/finrobot_desktop/finrobot/engine/primitives/rag.py)

- `daily_paper_runtime.py:351–460`은 일별 잠금, 시장 갱신·freshness, 판단과 intent, Paper 실행, NAV 저장을 연결한다. `paper_execution_runtime.py:290–405`는 개별 주문과 현금·포지션 행을 잠그고, `paper_runtime_store.py:116–155`의 고유 ID와 FK가 중복·연결 오류를 막는 기반이다. `reconcile_paper:418–461`은 주문 수량과 체결 합, 현금·포지션과 내부 ledger를 대조하고 실패 시 HOLD_ONLY로 바꾼다.
- 같은 모듈 `:464–531`은 주문마다 실행한 뒤 전체 대사를 수행하고, NAV는 일일 runner에서 별도 저장한다. **몇 건 체결 후 프로세스 종료**, **전체 체결 후 NAV 커밋 전 종료**, **동일 intent 동시 실행**, **재개 전 이미 불일치한 원장**에서 중복 없이 복구되는지는 추가 장애 주입이 필요하다. 내부 합계가 맞아도 체결 가격·수수료를 원천과 대조하거나 브로커 외부 상태와 일치했다는 의미는 없다.
- `v88_order_reconciliation/engine.py:237–269`의 응답 유실·브로커 상태 대조와 일일 PostgreSQL Paper 경로를 구분한다. 조회 snapshot과 Live hardlock은 있지만, 외부 접수·체결과 일일 원장이 한 경로에서 복구된 증거는 확보하지 못했다. V85 스케줄러와 실제 일일 Paper도 별도다. 과거 17개 단위 검사를 엔드투엔드로 세지 않는다. 이번에는 DB에 접속하지 않았고, `TEST_DATABASE_URL`을 요구하는 Paper 통합 검사는 미실행이다.

| 선택 | 판단 기준 |
|---|---|
| 유지 | 동결 대조군·내부 회계·안전 경계를 보존한다. |
| 부분 교체 | 사전 대사, 세션 재개, 주문-체결-NAV 상태 전이가 장애 시험에서 불일치하면 해당 경계만 개선한다. 우선 선택이다. |
| 전면 교체 | 동일 결함 주입에서 기존 경로와 부분 수정이 반복 실패하고, Lean/Nautilus 대안이 KRX·미장 제약 아래 동일 원장 재현 및 복구를 입증할 경우 검토한다. 지금은 두 외부 엔진도 소스 수준 C다. |

## 자율 개선과 다음 A/B

현재 Factory의 사전등록·hash·예산·실행 가능성 검사와 RD-Agent의 실제 가설→코드→평가→피드백 반복을 연결할 수 있다. TradingAgents가 제공하는 것은 판단·토론·만기 평가·기억이다. 단일 매매 복기와 반사실적 포트폴리오 평가를 분리하고, 복기 결과는 가설 후보로만 보내며 동일 위험·비용의 검증과 승인은 별도 단계에 둔다. FinRobot의 원문 추적, skfolio의 분할 대조, vectorbt의 단순 회계 대조는 이 흐름을 보조한다.

| 검증 | A / B 및 성공·실패 기준 |
|---|---|
| **주식 수익률** | 당시 거래 가능했던 종목과 상폐·기업행사, 동일 체결 시각·현금·종목 상한·비용을 고정한다. A는 동일비중 및 단순 가격 모멘텀, B는 잔차 모멘텀 또는 **실적 발표 후 드리프트** 한 가지다. 발표 당시 컨센서스와 실제치가 함께 있을 때만 실적 서프라이즈 사용. 자료가 부족하면 8-K/10-Q 정정·전망 변화의 정형 이벤트를 Shadow에서 먼저 수집한다. 같은 실험 예산, 날짜 분리, 비용 2배, 종목·연도 제외 민감도, 집중도·순성과를 보고한다. 현재 표본에서 1순위를 확정할 수 없다. |
| **FinRobot 정보 증가** | 동일 공시 원문에 A는 구조화 SEC/XBRL+단순 검색, B는 FinRobot 섹션 검색·추출. 블라인드 정답에서 원문 인용·수치·정정 정확도와 새 증거, 오탐·지연을 측정한다. 검색 개선이 발견돼도 매매 영향은 별도 검사한다. |
| **TradingAgents 판단·복기** | 동일 모델·증거·호출 예산에서 A 단일 분석가, B 토론+복기. 사전 정의한 사건·원문과 동결 이후 사례에서 인용 오류, 반증 발견과 비용 후 결과를 평가한다. 토론·복기를 각각 제거하고, 결과를 섞은 placebo에서 개선이 재현되면 실제 학습 효과로 집계하지 않는다. |
| **RD-Agent 자율 연구** | 동일 예산의 Factory 가설 제안과 RD-Agent trace 기반 제안을 비교한다. 3개 이하 제안, 중복 차단, 동결 평가, 운영 replay 최대 1개를 공통 적용한다. 완결률·신규 검증 가능 가설·오류와 비용을 보고하고, 최종 시험 구간을 다음 가설 제안에 노출하지 않는다. |
| **주문·원장** | 격리 PostgreSQL과 가짜 브로커 보고서로 기존 경로 대 최소 교체 경로를 비교한다. 접수 응답 유실, 중복·역순·부분체결, fill/NAV 사이 강제 종료를 주입한다. 중복 주문 0, 설명되지 않은 ledger/NAV 차이 0, 재개 후 동일 해시와 불일치 시 주문 차단을 요구한다. |

도입 순서는 **주식용 시점별 입력과 검증 분할 → 가격·공시 가설의 공정 비교 → 복기 Shadow와 주문 복구의 독립 검증**이다. RD-Agent와 FinRobot의 순위는 단순 의존성 실패만으로 내리지 않는다. 기존 전략·주문 코드·운영 설정은 그대로다.

실적 발표 후 드리프트는 기존 조사에서 검증 후보로 명시하지 않았던 가설이다. 역사 연구가 있다는 점과 현재 비용 후 우위는 별도로 평가한다. [Bernard & Thomas 원 연구](https://www.jstor.org/stable/2491062)

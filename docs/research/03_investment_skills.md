# Task 3 · 종목 발굴과 기업가치 예측 스킬 검증

2026-11-12 KST · [Task 1](01_github_discovery.md) · [Task 2](02_repository_comparison.md)

## 결론

우선 검증할 조합은 **investor-harness의 촉매 탐색·컨센서스 확인 → financial-services의 실적 시나리오 → equity-research-skill의 reverse DCF와 숫자 검산 → 독립 반론과 InvestSkill 복기**다. 스킬 전체를 연결하기보다 각 단계에서 한 기능씩 비교한다. 이번 실측은 수치 검산 기능에 한정되며, 여섯 후보 중 정보 발견·예측·투자 성과의 증분 효과가 실측으로 확인된 후보는 없다.

현재 `src/quant_harness/news_shadow_runtime.py:37,63,97`에는 OpenDART 관측 수집·보존과 Shadow 필터가 있고, `v102_market_evidence_agent/policy.py:74,125,176,230`에는 수급·재무·뉴스 근거와 적용 경로가 있다. 이 경로에는 기업 단위로 검색 범위를 넓혀 선행 변화를 발굴하고, 당시 컨센서스와 대조해 1·2·4분기 재무 예측을 기록하는 연결이 확인되지 않았다. 기존 리뷰·Factory의 시점·해시·검증 경계에 예측 평가를 붙일 수 있다.

## 여섯 후보의 코드 근거

| 후보 | 실제 확인한 기능 | 선행 변화·예측에 기여할 범위와 한계 |
|---|---|---|
| prompts.chat | 검색·분류하는 프롬프트 카탈로그. `prompt-lookup`이 키워드를 도구에 전달한다. | 역할 문구 수집용. 금융 정보 수집·검증·예측의 재현 경로를 이 스킬에서 확인하지 못했다. 분석 스택에서 제외. [고정 스킬](https://github.com/f/prompts.chat/blob/7330108d5fe161ba1d03ce7795eec1a421aad7b8/plugins/claude/prompts.chat/skills/prompt-lookup/SKILL.md) |
| ai-hedge-fund | 투자 스타일별 신호 구현과 포트폴리오·리스크 코드를 제공한다. Task 2에서 백테스트·리서치·배분 등 107개 통과, 확장 Paper Windows 2개 실패. | 같은 시점 데이터로 독립 스타일 대조군을 만들 수 있다. 스타일별 신호와 고정 유니버스의 실행 테스트는 새로운 기업 정보 발견, 경영 행동에서 재무 지표로 이어지는 예측, 시장 기대 역산을 입증하지 않는다. 전략 모방 프롬프트 여러 개를 중복 도입하지 않는다. [스타일 신호](https://github.com/virattt/ai-hedge-fund/blob/5c553b5222044f6a5527bd377b4104c50ee0ad28/hedge_fund/signals/druckenmiller.py) · [기존 실행 근거](06_candidate_final_decision.md) |
| anthropics/financial-services | `earnings-preview`는 이전 가이던스, 매출·EPS·부문 컨센서스, bear/base/bull과 주가 반응을 요구한다. 별도 기업 경쟁·산업 조사와 3-statement·DCF 스킬이 있다. | 분기별 추정과 기대치 대비 표준화에 적합. 가격 반응의 근거와 확률 보정, 관측 시각의 강제 검증은 별도 필요. 워크북·덱 제작 부분은 이번 평가에서 효용 낮음. [실적 프리뷰](https://github.com/anthropics/financial-services/blob/60565064557ca77b12f62aa7877f365d111c129d/plugins/agent-plugins/earnings-reviewer/skills/earnings-preview/SKILL.md) · [시장 조사 스킬](https://github.com/anthropics/financial-services/tree/60565064557ca77b12f62aa7877f365d111c129d/plugins/agent-plugins/market-researcher/skills) |
| rollingSirius/equity-research-skill | 원문·시세/밸류·컨센서스·업종 정보의 조사 경로를 지시한다. 실제 `dcf.py`에 현금흐름·시나리오, 희석, reverse DCF, 민감도 계산이 있다. 체크 스크립트는 업종 KPI·보고서 규약 등을 점검한다. | **시장 기대 역산의 첫 검증 후보.** 현재가를 정당화하는 매출 성장·FCF 마진과 고객·제품 근거를 비교한다. 할인율·마진 가정에 따라 역산값이 달라지므로 단일 숫자를 시장 컨센서스로 쓰지 않는다. 보고서 검사를 통과해도 전제의 진실성·발굴 성능은 미확인이다. [고정 스킬과 스크립트](https://github.com/rollingSirius/equity-research-skill/tree/3d94e64ff53b325d866ea4bff69ad81a5adca8f5) |
| InvestSkill | `trade-postmortem`은 종료된 thesis-tracker 파일을 읽어 결과와 과정, 계획 준수·편향·수익 원천을 구분한다. 경쟁사·포렌식·사실 확인 스킬도 있다. | **복기 평가 양식**에 적합. 저장된 판단 원본과 사후 사실을 분리하고, 예측이 맞아도 수익이 낮은 사례를 보존한다. 자체 점수는 모델 평정이므로 독립 채점과 실현치 수치 검사가 필요하다. 중복 DCF·종합 보고서 스킬은 보류. [고정 복기 스킬](https://github.com/yennanliu/InvestSkill/blob/cba40eebdfcca95f0ccbde7afadd96014dfe685d/plugins/us-stock-analysis/skills/trade-postmortem/SKILL.md) |
| investor-harness | `sm-catalyst-sweep`는 관측 종목→세부 산업→시장으로 검색하고 계약·규제·실적 공시를 분류한다. `sm-consensus-watch`는 컨센서스가 없으면 기대 차이 판단을 금지한다. `sm-red-team`은 유사 사례·업종 변곡·공매도 논거·기존 편향 기록을 요구한다. | **능동 발굴과 반론 설계의 첫 후보.** iFind와 중국 정책·공시 예시의 조회 범위는 KRX/미장 공시·IR·규제 원문으로 바꿔야 한다. 호출 예산이 큰 스캔, 업체 데이터 권한과 관측 시각은 실험에서 통제한다. 프롬프트의 검색 지시만으로 발굴이나 적중이 실행됐다고 세지 않는다. [촉매 탐색](https://github.com/joansongjr/investor-harness/blob/491cb380011a6533d56b6913d9c4424a9e4e1bdb/skills/sm-catalyst-sweep/SKILL.md) · [기대치](https://github.com/joansongjr/investor-harness/blob/491cb380011a6533d56b6913d9c4424a9e4e1bdb/skills/sm-consensus-watch/SKILL.md) · [반론](https://github.com/joansongjr/investor-harness/blob/491cb380011a6533d56b6913d9c4424a9e4e1bdb/skills/sm-red-team/SKILL.md) |

### 실제 실행과 판단 범위

- equity-research-skill 고정 커밋 `3d94e64ff53b325d866ea4bff69ad81a5adca8f5`을 임시 폴더에 받아 원본 `tests/test_check_research_output.py` 실행. **7개 통과, 종료 코드 0.** 업종 KPI 누락과 보고서 규약을 검사했다.
- 원본 `scripts/dcf.py --demo`는 Windows CP949 출력 오류로 먼저 실패했다. 임시 실행에 `PYTHONIOENCODING=utf-8`을 적용해 성공했다. 합성 입력의 현재가 100, 확률가중 가치 57.5, FCF 마진 20% 조건에서 현재가가 요구하는 매출 CAGR 약 34%가 나왔다. 이는 계산과 시나리오 민감도 시연이다.
- 나머지는 고정 소스·스킬 확인과 기존 Task 2 검증 재사용 범위다. 실제 동일 모델의 반복 분석, 새 정보 발견 비교, 미래 예측 채점, 투자 수익률 실측은 모두 미실행이다. Gemini 키가 없어 GitHub 원문과 로컬 실행으로 확인했다.

## 기존 에이전트에 붙일 위치

1. **Universe/MarketRegime → 관측 목록.** 당시 거래 가능 종목과 업종을 제공하고, 종목 발굴팀은 출발 목록 밖에서도 검색한다. 새 발견의 실제 주문 적격 여부는 기존 유니버스에 따로 확인한다.
2. **SectorTheme/SentimentNews → 발견 기록.** 규제 기관·공시·IR·고객/공급사·경쟁사에서 변화의 증거를 찾는다. 검색어, 원문 시각, 처음 수집한 시각, 회사 주장과 제3자 확인을 구분한다. 최초 실험은 투자 영향이 큰 증거만 남기는 investor-harness 촉매 탐색을 비교한다.
3. **CandidateSelection/Strategy 연구 Shadow → 인과·재무·기대치.** 수주 발표라면 구속력, 검수 조건, 생산 여력, 인식 일정, 단가와 마진, 운전자본을 연결한다. 실적 시나리오의 분기별 단위·가정을 고정하고 reverse DCF로 요구 성장률 범위를 점검한다. 예를 들어 적자 기업은 고객 채택률과 현금 소진·희석을 같이 평가하고, 우량 기업도 시가에 내재된 성장 가정이 과하면 별도로 표시한다.
4. **독립 반론과 ReviewFeedback → 검증·복기.** 첫 반론은 원 논거를 보기 전에 같은 증거에서 작성한다. 그 뒤 가장 강한 반증과 다음 확인 일자를 봉인한다. 복기에서 미래 수익률, 예측 오차, 판단 과정, 노출·체결 효과를 각각 기록한다.

공통 스키마 하나로 시나리오·출처·반론을 관리한다. 중복 업종 요약, 인물 스타일 재현, 워크북/슬라이드, 여러 DCF와 여러 bull/bear 역할은 첫 실험에서 제외한다. FinRobot BM25는 동일 공시 원문 검색의 대조군으로 쓸 수 있다. [Task 2 검색 실측](02_validation_addendum.md)

## A/B 실행 계약

| 분기 | 처리 | 비교에서 분리하는 효과 |
|---|---|---|
| A0 | 기존 분석/Shadow의 현재 입력과 결과를 동결 | 실제 기존 수준 |
| A1 | A0 방식에 공통 외부 원문·수치 묶음 추가. 정형 룰 또는 기존 분석 방식 | A1−A0는 데이터 추가 |
| B1 | 같은 데이터와 검색 후보 풀에서 스킬 기능 하나만 추가 | B1−A1은 조사·분석 방법 |
| B2 | B1과 별도 분석가의 반론을 추가. 모델·총 도구·토큰 예산을 양쪽에 동일 배정 | B2−B1은 예산당 독립 검증 |
| B3 | B2에 당시 이미 확정된 복기·연구 기록만 제공. 빈 기록·같은 길이의 무관 복기를 대조 | B3−B2는 실제 복기 가치 |

**두 시험을 분리한다.** 발굴 시험에서는 동일 시작 단서와 원천 범위에서 검색을 허용한다. A0는 현재 입력을 유지하며 A1/B에는 같은 도구 접근을 제공한다. 사건 정답은 후보 출력에 보이지 않게 하고, 서로 다른 원문의 같은 사실은 하나로 묶는다. 예측 시험은 발굴 결과를 공통 원문 묶음으로 고정한 뒤 같은 모델의 B1–B3를 비교한다. 비LLM A1을 선택하면 B1−A1에 모델 효과도 섞이므로, 같은 모델의 무스킬 대조군을 추가하거나 기존 LLM 방식의 A1을 병행한다.

| 평가 | 측정 계약 |
|---|---|
| 발견 | 시작 질문과 초기 근거에 없었던, 당시 확인 가능하고 재무에 중요한 사실 수. 블라인드 2인 판정으로 원문 일치·중복·오탐을 분리하고 적중/호출 및 최초 발견 지연을 계산. |
| 인과와 예측 | 원인→전달 변수→매출·이익·FCF·점유율의 경로와 경쟁 설명, 1·2·4분기 및 장기 시나리오를 기록. 단위·통화·확률 합·예측 범위·반증 기준을 동결. 정량은 MAE 또는 규모 정규화 오차, 이진 사건은 Brier, 구간은 커버리지와 폭. 장기 미성숙 라벨은 pending. |
| 기대 차이 | 당시 컨센서스의 날짜·범위·표본 수와 가격을 고정하고 실제 결과로 컨센서스 대비 오차를 계산. 없으면 기대 차이 미평가. Reverse DCF의 범위는 모델 역산으로 별도 표시. |
| 투자 | 동결된 후보 판단을 공통 보유 기간·위험 예산·비용에 적용. 시장·업종 대조군 대비 순성과·낙폭·turnover를 따로 보고. 예측 정확도와 성과를 합산해 우승자를 만들지 않는다. |
| 비용 | 토큰·검색·도구 호출, 소요 시간, 실패·기권율. 보고서 길이와 문체는 채점 제외. |

시점별 원문·정정·가격·당시 컨센서스 버전을 보존한다. 사전 정의한 미국·한국 개별주식 사례를 기술/산업재/소비재 등과 시장 국면에 걸쳐 뽑고, 수요 급성장·현금 소진·우량하지만 높은 기대 사례를 함께 넣는다. 첫 소규모 시험은 채점 일치율과 누락을 확인하는 용도다. 이후 짝지은 사례의 차이를 업종·기간 단위로 보고, 반복·중첩 라벨은 블록 단위로 불확실성을 추정한다. 공개 역사 사례는 모델이 기억할 수 있으므로 모델과 프롬프트를 동결한 뒤 Forward Shadow에 별도 수집한 사례를 최종 판단에 사용한다.

**실행 순서**는 같은 원문에서 촉매 발굴 정확도를 먼저 비교하고, 시점별 컨센서스가 확보된 사례부터 조건부 예측과 기대 차이를 채점하는 것이다. 그 다음 독립 반론·복기 제거 실험으로 기여를 분리한다. 실제 공시 관측 시각 또는 컨센서스 스냅샷이 없으면 해당 지표는 미확인으로 남긴다. 현재 소스·전략은 변경하지 않았다.

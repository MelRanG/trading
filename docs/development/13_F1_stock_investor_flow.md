# Task13-F1 — 종목별 수급 증분 알파 검증

**최종 판정 `DATA_ACCESS_BLOCKED`.** 공식 KRX 화면은 열렸지만 일별 개별종목 순매수대금 조회가 HTTP 403과 오류 HTML을 반환했다. 검증된 원천행 0건으로 가격 지표 대비 예측력, 비용 후 성과, 종목·시기별 효과는 모두 미평가다. [요청 원장](../../runtime/task13_f1/requests.jsonl) · [원천 응답 검증](../../runtime/task13_f1/verification.json)

| 사전 지정 종목 | 시장 | 2024년 4월 R0 적격 가격 | 실제 KRX 수급 결과 |
|---|---|---:|---|
| 삼성전자 `005930.KS` | KOSPI | 21/21세션 | 일별 순매수대금 요청 403 |
| POSCO홀딩스 `005490.KS` | KOSPI | 21/21세션 | 공통 조회 경로 403에서 중단 |
| 에코프로비엠 `247540.KQ` | KOSDAQ | 21/21세션 | 공통 조회 경로 403에서 중단 |

한국 CORE의 통신장비·철강·전지 업종에서 세 종목을 지정했다. ISIN과 가격·native 마스크 SHA를 대사했다. KRX 공식 화면 GET은 200이었고, 일별 추이의 거래대금·순매수 POST는 `text/html` 오류 페이지를 반환했다. 이 응답으로 403의 정확한 원인을 확정할 수 없다. 수급행이 없어 원화 단위·부호·투자자별 합계 및 공식값을 대사하지 못했다. 나머지 두 종목과 확대 표본은 조회하지 않았다. [공식 조회 화면](https://data.krx.co.kr/contents/MDC/MDI/outerLoader/index.cmd?screenId=MDCSTAT023) · [사전 지정 표본](../../runtime/task13_f1/pilot_plan.json)

프로젝트의 기존 KRX 경로에서 인증 세션이나 해당 원본 파일을 찾지 못했다. 점검한 기존 Python 환경에는 pykrx가 없었다. Toss 공식 API 명세상 종목별 역사 자료는 거래량과 등록외국인 기준이다. 원화 순매수 종목 순위는 최근 영업일만 제공하고, 원화 역사 시계열은 시장 합계다. 세 경로 모두 FLOW5의 원화 종목별 시계열 요건을 충족하지 않는다. [Toss 공식 OpenAPI 명세](https://openapi.tossinvest.com/openapi-docs/latest/openapi.json) · [기존 E2 출처 감사](13_E2_team2_increment_and_information.md)

V102는 시장 합계로 진입을 차단한다. V96은 시장 추세와 변동성으로 노출을 조절한다. F1은 개별종목 상대 순위 변경이므로 중복 연구에 해당하지 않는다. Task10에서 확인한 5세션 리밸런싱, MA63 위험 전환, 상위 최대 4종목, 종목당 20% 비중을 비교의 출발점으로 확인했다. 수급 입력을 확보하지 못해 A/B를 실행하거나 성과 평가 예약을 소비하지 않았다. [V102 정책](../../src/quant_harness/v102_market_evidence_agent/policy.py) · [V96 정책](../../src/quant_harness/v96_market_regime_extension/policy.py) · [Task10 실행 정책](../../experiments/task10/shared.py)

재개를 판단하는 데 필요한 최소 자료는 공식 경로의 **세 종목 한 달분**이다. 종목코드 또는 ISIN, 거래일, 외국인 합계 순매수 원화 대금, 기관 합계 순매수 원화 대금, 전체 원화 거래대금, 원천·수집 시점이 필요하다. 공식 원본에서 투자자 범위와 순매수 부호를 대사해야 한다. 기존 R0 가격 마스크와 결합할 때 사용자 지정 t+2 시가·H5·50:50 순위를 유지한다. 최초 공표 시각과 과거 판본 인증에 한계가 있으면 가능한 평가는 `HISTORICAL_EXPLORATORY`로 분류한다. [Task12 평가 계약](12_alpha_data_readiness.md) · [R0 데이터 계약](13_R0_research_data_expansion.md)

Python 원천 요청은 총 3회였다. 최초 화면 GET 뒤 로거의 메서드 조회 예외로 응답을 저장하지 못했다. 표준 `Request.get_method()`로 고친 뒤 화면 GET 한 번과 데이터 POST 한 번을 기록했다. 문서 조회는 별도였다. 신규 가격 요청·연구 LLM 호출/토큰·학습·성과 평가 모두 0회다. 계측된 파일럿과 해시 검사 CPU는 0.06초, 안전 검사 CPU는 3.35초였다. 첫 실패 시도의 CPU와 Codex 자체 토큰은 계측하지 못했다. AGENTS의 compileall과 필수 회귀 24건이 통과했다. Factory·Paper·Forward·Live 운영 경로에는 쓰기 작업이 없었다. [최초 실패](../../runtime/task13_f1/pilot_attempt_1.log) · [기계적 수정](../../runtime/task13_f1/pilot_repair.diff) · [안전 회귀](../../runtime/task13_f1/safety_validation.json)

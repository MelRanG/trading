# Task 9.2 — 재무 입력·기업가치 연구와 Forward·복기 연결

2026-11-15 KST. **HYBRID_MINIMAL 유지. 투자 우위·실거래 적격성을 입증한 작업이 아니다.**

## 핵심 결과와 독립 판정

| 영역 | 판정 | 실제 완료 / 남은 한계 |
|---|---|---|
| Research | **PARTIAL** | 같은 역사 시점의 입력 전후 실증, 수치·단위·기간·원문 locator 검증. 최신 DECK·삼양식품의 조건부3시나리오를 미래 stub 기간과 원본 Vibe FCFF/EV→equity 계산으로 확인. 현재 희석·리스·minority·자본 roll-forward는 미완전. 역사 초기 연간 DCF는 cutoff와 기간이 안 맞아 승인 목표가로 사용하지 않음 |
| Decision | **PASS — 계약 분리** | 연구 우선순위≠매수. 최신 DECK WATCH, 나머지3개 RESEARCH_INCOMPLETE. 양 시장 연구 정책 현금100%, 공식 Paper 적격·주문 없음. 확정적 투자 매력 부족과 정보 부족을 같은 상태로 합치지 않음 |
| Forward | **PARTIAL / 자연 대기** | 최신 기업 자료·가격·전망·판단2시장 봉인. 기존 단일 systemd 서비스와 자연 timer에서 새 dispatcher 실행, 실제 프로세스 재호출 중복0. 현재 주말이고 post-seal 정규장 관측·체결·1/3/6개월 결과 없음. 비거래 지수의 별도 실시간 adapter/정합 기준선·신규 INVESTABLE 진입 등록은 미완성 |
| Feedback | **PARTIAL / Factory BLOCKED** | 운영 연구 DB에서 과정 근거 복기2건 DONE, 자료 검증 실험의 공식 등록은 일일 예산 차단. 정상 다음 UTC일 재시도 경로 실제 배포. 같은 Factory 계약의 격리 시험에서88수치 검증·예약·기록·캐시 재개 확인. 이를 운영 실험이나 투자 개선으로 표시하지 않음 |

Terra 실제 **6회·313,665 tokens**, 전부SUCCEEDED, 최대6회/420,000 한도 유지. 별도 유료 API·새 프레임워크·상시 서비스·DB 서비스 설치 없음. 실거래·운영 전략·기존 Paper/Shadow 계획·Live 잠금은 변경하지 않았다.

## 1. 실제 코드와 원본 재사용

- 신규 `src/quant_harness/investment/financial_packet.py`: 정확한 원문 JSON/text locator, raw hash, Decimal 단위 변환, CFS/SFS·기간·공개일 검증, EPS 단위 오류 차단, 전체 수치 view 보존, 순위/적격 상태 분리, 일치하는 실현값 계약 채점 helper.
- 신규 `research_dispatcher.py`: 기존 Store/Queue/Review와 공식 Factory 함수를 사용. 단일 운영 CLI에 예외 격리 hook만 추가. 새 모델 프로세스나 임의 코드를 실행하지 않고 주문/원장 쓰기 API도 호출하지 않음.
- 변경 `scripts/run_autonomous_operations.py`: 기존 Task5/8/8b 뒤에 연구 dispatcher 호출. 기존 스케줄러·거래 판단·체결 경로는 유지.
- `experiments/task9_2/`: 제한 수집·검증된 packet·실제 원본 ChatLLM 호출·동일 사례 전후 비교·시점 보정·native 가치검산·봉인·시험·한정 감사. 운영 분석기/자체 백테스터를 새로 만들지 않음.
- 고정 Vibe `0025531f005d4a7aac3fb884cda2fba9318e7158`: 원본 ChatLLM, earnings-forecast/valuation-model 방법, 원본 `FCFFYear`·`equity_bridge` 실제 사용. 전체 CLI·Autopilot·자율 screening의 완주로 주장하지 않음. 후보 압축은 최근 공식 실적/사업 변화의 제한 조사이고 LLM은 실제 전망·가치 연구를 수행.
- QuantaAlpha `b7ceb27b1001261d7a95b209a963664ae1f8ab23`, RD-Agent `484776c211e4fbbeef03e0ec00d6bbee7362a4f4` 및 연구 환경 보존. 이번 신규 엔진 탐색·원본 Forward alpha 검증은 하지 않음.

실행 코드와 테스트를 문서 주장보다 우선했다. 기존6~9.1 결과를 재조사·재설치하지 않고 source·trace·데이터를 재사용했다.

## 2. 원문→수치→모델의 실제 수정

역사 사례는2025-06-30 기준 **SFM·LG이노텍(원문 충분), SMMT·서울보증보험(원문/업종별 핵심 자료 부족)**으로 사전 고정했다. 재조사 전에 모델6회/420k, 제공자별 제한을 계약에 남겼다.

단순 keyword나 snippet 존재를 PASS로 보지 않았다. 각 fact에 금액·통화·unit multiplier·CFS/SFS·회계기간·공개일·source hash·정확한 JSON path/문자 구간을 붙여 원문 값을 재검산했다. 기업별 허용 source mapping도 별도로 대사했다. 모델용 view에서 숫자/주식수/부채 필드를 서술 길이 때문에 버리지 않도록 보존 helper를 추가했다.

- SFM: USD 천 단위 재무표를 dollar로 정확히 환산. 2025Q1 매출 **2,236,436,000**, 순이익 **180,026,000**, 평균 희석주식 **99,719,000**. NI/주식수는약1.8054로 공시 EPS1.81과 반올림 일치. 영업현금299.089m−gross capex59.479m=239.610m은 **after-interest 현금 proxy**이며 FCFF라고 잘못 부르지 않음. revolver0과 전체 debt0을 구분해 finance lease 등8.243m 보존.
- LG이노텍: 2025Q1 CFS 영업이익125.117bn KRW·현금1,224.270bn·차입금2,433.557bn·리스22.974bn을 분리. 연간 재투자·CF 정보가 초기 packet에 없어서 당시 공개된 FY2024 CFS61개 fact를 추가. EPS4개를 통화 총액으로 표기한 초기 생성물은 모델 전달 전 PER_SHARE로 교정하고 V2/V3를 보존. 연간 ordinary23,667,107은 미래 완전 희석주식수와 같다고 주장하지 않음.
- DECK: 단위USD천, FY2027H1은2026년4~9월이다. OCF **-9.262m**·capex outflow37.176m → OCF−gross capex **-46.438m**. 음수 outflow를 한 번 더 빼서 현금 유입으로 바꾸지 않음. 운영리스539.520m과 차입금0의 의미를 분리. FCFF에서 임차료를 영업비용으로 남기면 운영리스를 다시 전액 차감하지 않음.
- 삼양식품: 최신3Q26 표의 **KRW100M**을 원으로 환산. cash823.0bn·총차입금700.7bn → net borrowings **-122.3bn**. 전체 부채1,204.3bn을 차입금으로 사용하지 않음. 과거H1 자료가 최신3Q 자본 수치에 덮어씌워지지 않게 분리. Q3 리스·NCI·희석의 빈칸은 남김.

원문 부족(SMMT 호스트 다운로드 실패), 업종별 자료 부족(보험 자본/지급여력), 추출/전달 누락(연간CF·재무표 뒷부분), 모델의 보수적 기권을 구분했다. 최신 첫 호출에서도 PDF 앞부분만 전달한 한계가 실제로 남아 있었고, 상세 재무표/연간 자료·typed capital facts를 보완한 별도 버전으로 재시도했다. 실패한 첫 결과를 덮어쓰지 않았다.

## 3. 실제 입력 개선 전후 결과

| 실제 호출 | 기업 수 | 연간 전망 수 | 시나리오 수 | 해석 |
| --- | --- | --- | --- | --- |
| history_before | 4 | 0 | 0 | 동일4개 입력 전후 |
| history_after | 4 | 3 | 3 | 동일4개 입력 전후 |
| history_lg_repair | 1 | 3 | 3 | 추가 근거/기간 교정 단계 |
| current_research | 4 | 12 | 0 | 추가 근거/기간 교정 단계 |
| current_repair | 2 | 6 | 6 | 추가 근거/기간 교정 단계 |
| current_timing | 2 | 0 | 6 | 추가 근거/기간 교정 단계 |

첫 역사 A/B는 같은4개 기업·시점·모델·분석 instruction이며 공통 input hash를 사용했다. SFM은0전망/0가치→3전망/3조건부 시나리오로 변했다. LG는 최초 수정에서도0/0이어서 실패 이유를 남긴 뒤 연간 수치·share 자료를 추가하고 FCFE를 사용해3/3을 생성했다. LG의 추가 호출은 새로운 보완 입력 버전이며 최초 A/B와 같은 완전 paired 결과로 합치지 않는다. SMMT·서울보증보험은 모두 빈 시나리오/기권을 유지했다.

SFM은 EBIT×(1−세율)+D&A−capex−ΔNWC의 FCFF, LG는 after-interest OCF−투자+net borrowing의 FCFE를 구분했다. FCFE에는 순차입금을 다시 차감하지 않았다. SFM의 첫 FY2025 EBIT는 회사 가이던스 범위에 가까운 guidance-anchored 시나리오다. 후속 연도의 가정과 구분하며, 가이던스 재현을 독립 예측 성공으로 세지 않았다. 전부 EPS×임의 배수의 대체물이 아니다. 다만 역사 최초 연간 값은 이미 지난 당해 연초~cutoff 현금흐름이 섞여 **시점 gate를 통과한 as-of 목표가가 아니다**. 별도 `valuation_annual_diagnostics.json`에 illustrative로 남기고 실제 투자/Forward에는 사용하지 않았다.

최신 DECK·삼양식품은 cutoff 이후의 첫 stub 종료일과 이후4개 연도 종료일을 명시하고 EBIT/세율/D&A/capex/ΔNWC 숫자를 각각 원본 Vibe FCFF bridge로 재계산했다. 실제 미래 날짜만 ACT365.25로 할인하고 EV에서 금융 청구권을 조정해 주당가치를 검산했다. 연말을1년으로 일괄 처리한 이전 계산도 보존했다. 이미 지난 성과를 보며 예측 정확도나 alpha가 개선됐다고 주장하지 않는다.

## 4. 최신 후보·조건부 가치·판단

미국 PH·DECK, 한국 KT&G·삼양식품을 최근 공식 실적·사업 변화에서 압축했다. TPR도 조사했으나 호스트 원문 접근 실패로 제외한 기록을 남겼다. 기존 관심 종목을 그대로 Forward 신호로 재사용하지 않았다. 가격은2026-11-13 완료일 기준 Yahoo/Toss를 확인했고 V87 gate를 통과시켜 별도 snapshot으로 보존했다. 두 시장은 별도 통화·판단이다.

| 기업 | 연구 우선순위 | 관측 가격 USD/KRW | 연구 상태 | 정책 비중 | 공식 Paper |
| --- | --- | --- | --- | --- | --- |
| PH | HIGH | 955.68 | RESEARCH_INCOMPLETE | 0% | NOT_ELIGIBLE |
| DECK | HIGH | 86.82 | WATCH | 0% | NOT_ELIGIBLE |
| 033780.KS | MEDIUM | 176,000.00 | RESEARCH_INCOMPLETE | 0% | NOT_ELIGIBLE |
| 003230.KS | HIGH | 1,210,000.00 | RESEARCH_INCOMPLETE | 0% | NOT_ELIGIBLE |

조건부 DCF 민감도(확률·승인 목표가·1년 수익 예측 아님):

| 기업 | Bear | Base | Bull | 현재 참조가격 | Base 괴리 | 가격 내재 전체FCFF 수준/Base |
| --- | --- | --- | --- | --- | --- | --- |
| DECK | 63.99 | 104.17 | 162.67 | 86.82 | +19.98% | 0.818x |
| 003230.KS | 440,597.34 | 975,067.02 | 1,396,200.62 | 1,210,000.00 | -19.42% | 1.243x |

- **DECK**: HOKA/UGG 성장, DTC comparable -6.4%, 비반복 tariff refund, 계절적 재고·CF를 함께 반영했다. Base value가 참조가격보다약20% 높아도 DTC 안정·현금 전환·희석 확인이 진입 조건이므로 WATCH/0%다. 공식 Paper 적격성을 만족했다고 표시하지 않음.
- **삼양식품**: 해외 수요/생산능력 성장과 원화 강세·지역별 유통·일회성 이익을 분리. Base보다 비싼 가격이라는 조건부 분석과, Q3 lease/NCI/희석·CF 미완성이라는 데이터 문제는 별개다. 최종 상태는 RESEARCH_INCOMPLETE이며 확정적 UNATTRACTIVE 판정으로 바꾸지 않음.
- **PH**: 인수로 증가한 차입과 현금·유기적 성장/조정 실적의 차이를 보존했다. 충분한 연간 정상화/자본 정보가 없어 전망은 생성했으나 완결 DCF는 미생성. 이를 매력 부족으로 단정하지 않음.
- **KT&G**: 영업 성장과 비영업/당기순이익 급감, 주주환원·treasury 정보의 차이를 기록했다. 현재 발행/유통/희석·정상화 이익과 적합한 배당/가치 모델 입력이 미완전하여 기권. 제조업 FCFF를 강제로 적용하지 않음.

가격 내재 FCFF는 할인율·terminal g·자본 청구권을 고정한 **전체 미래 현금흐름 수준의 역산 배수**다. 이를 매출 CAGR/확률로 바꾸지 않았다. 할인율·terminal g·미래 마진·재투자·capital roll-forward는 가정이고, 마지막 공시 cash가 현재 은행 잔액이라는 사실 주장은 아니다. 미래3개년 수치와 반증 조건은 모델原출력·봉인 판단에 보존되며 실제 실현값은 PENDING이다.

## 5. 기업·퀀트 경로와 Forward 범위

가격 기반 MOM63은 기업 분석 전에 기존 자료로 독립 계산했다. PH/DECK/KT&G/삼양식품의63세션 수익은 각각약-9.31/-3.65/-2.17/-3.51%다. 이것은 새로운 QuantaAlpha/RD-Agent의 검증된 alpha가 아니다. 기업 연구가 가격·모멘텀을 일부 같이 보았으므로 기업/퀀트 완전 블라인드 A/B로 주장하지 않는다. DECK 조건부 가치 상승 여지와 음의 가격 추세는 의견 차이로 기록했고, 한쪽이 다른 쪽의 판단을 자동 승인/기각하지 않는다.

2개 시장의 최신 연구 판단·회사별 수치 전망·가치·진입 조건·0% 정책·SP500/KOSPI 참조가격을 연구 DB에 봉인했다. **현재 모두 적격 매수 신호가 없으므로 새로운 Paper 주문/체결은0**이다. 원인은 DECK의 미충족 진입/검증 조건과 나머지 기업의 자료 부족이다. 단순 연구 우선순위 상위를 실제 매수 추천으로 해석하지 않는다.

기존 Task8b계획/계좌는 그대로 두었다. 새 시장 연구 정책은 별도 `RESEARCH_SHADOW_WATCH_POLICY_NOT_OFFICIAL_PAPER`이며 기존 계좌의 주문 권위를 대신하지 않는다. 새로운 INV​ESTABLE 판단의 Paper 등록까지 자동 완성한 상태는 아니다. 이번 비현금 실제 체결은 검증하지 못했다.

기존 systemd 단일 CLI에서 새 연구 dispatcher가 실제 실행됐다. 주말에는 공식 정규장 확인 전 I/O/새 주문 없이 WAIT. 정규장이 확인되면 종목 quote를 하루1회/시장 bounded budget으로 관측하고, 한국은 봉인 후 새 날짜의 DART 공시 notice를 제한 조회해 근거 복기 요청을 등록한다. 동일 날짜 공시는 봉인 이후 시각을 입증하지 못하므로 post-seal 사건으로 단정하지 않는다.

**개발 중 발견한 route 오류:** 비거래 지수를 stock quote endpoint에 보내면 안 된다. 이를 post-seal 관측 전에 V2로 수정하고 기존 dispatcher/manifest/proposal V1을 보존했다. 종목 quote schema는 실제 응답으로 확인했다. SP500/KOSPI의 별도 지속 지수 관측·동기화 baseline adapter는 아직 연결되지 않아 명시적으로 PENDING이다. 종목 관측이 지수 입력 오류 때문에 통째로 실패하지 않도록 분리했다. 주말 이전 quote를 새 Forward 결과로 사용하지 않았고 future regular-session routing은 격리 시험으로 구분했다.

따라서1/3/6개월 성과·기업행사 검증·새 전망의 실현값·수치 forecast helper의 운영 자동 채점은 아직 완료가 아니다. 한국은 공시 notice 관측까지, 미국 실현 재무 feed는 미연결이다. 보유/체결이 없는데 수익률·낙폭을 만들어 넣지 않았다.

## 6. 운영 복기·Factory·재실행

실제 경로:

`run_autonomous_operations.py` → `research_dispatcher.run_tick` → 기존 연구Store/Queue lease → source/숫자 실험의 공식Factory 등록·예약 → 근거Review / post-seal 관측 대기.

- 최초 실행: Factory budget BLOCKED, 2시장 WAIT, **실제 입력 전달 문제를 근거로 한 복기2건 DONE**. process review는 미래 결과를 접근하지 않고 source/trace/위험 계약을 평가한다. 주가 손실만으로 예측 오류를 추론하지 않고 cause UNDETERMINED를 유지한다.
- 같은 함수 재호출은 처리0건. 별도 systemd 프로세스 및 자연 timer 실행에서도 같은 registry/Queue를 읽어 중복0건이었다. 새 상시 서비스·Cron·Gateway 없음.
- 공식Factory는 현재 UTC일 제안3/3·실험1/1 소진으로 등록 차단. 다음 UTC일의 첫 정상 tick은 새 날짜 slot으로 재시도한다. 기존 공통 실험이 canonical tick에서 먼저 처리되어 기존 우선 경로를 우회하지 않음. 실제 다음 예산 예약·운영 실험은 아직 미실행이다.
- 같은 함수의 **pytest 임시 registry**에서 등록→예약→88원문 수치 검증→결과 기록→캐시 재개를 확인했다. 회사4개가 최소12독립 사례에 못 미쳐 `INSUFFICIENT_EVIDENCE`, 승격0이다. 임시 시험을 운영 예산 대체로 사용하지 않음.
- V2 worker fingerprint에 numeric validator 의존성도 포함했다. code/input이 바뀌면 기존 공식 실행 계약을 그대로 재사용하지 않음.
- 자동 handler는 신규 TASK92 Factory/Monitor/EvidenceReview만 지원한다. 구 Task91 등의 미지원 연구 job·LLM 재연구·새 alpha의 자동 실험 전체를 완성했다고 보고하지 않는다. 새로운 LLM 호출은 자동으로 열지 않으며 별도 예산과 새 입력을 요구한다.

## 7. 한국2025 수익률 제한 감사

| 항목 | 진입 2025-07-01 시가 | 청산 2026-07-01 시가 | 가격 수익 |
| --- | --- | --- | --- |
| LG이노텍 | 148,900.00 | 983,000.00 | +560.17% |
| KOSPI | 3,089.64 | 8,591.50 | +178.07% |

LG이노텍 exit983,000은907,000 **종가와 다른 시가**이며 Naver 재조회와 기존Yahoo가 일치했다. KOSPI는 두 날짜를 별도 Toss 지수 API에서도 확인했다. 기준은 사전 정의한 동일 날짜 open→open이므로 종가로 임의 교체하지 않았다. 2026H1 DART의 보통주23,667,107이 기존23,667,107과 같고 Yahoo 선언 split은 없었다. 해당 기간 DART 주요사항 검색은013(없음)이었으나 이를 모든 종류의 기업행사 완전성 증명으로 확대하지 않는다.

기존 균등 선정 gross 기여는 LG **+186.72%p**, NICE **-5.24%p**, LS에코에너지 **+17.51%p**였고 비용 약1.08%p 차감 후 **+197.93%**다. LG 한 종목 영향이 대부분이라는 사실을 확인했다. 제한 감사에서 수치 교정 근거가 없어 기존 결과·종목·기간·비용을 보존했다. 전체 PIT·기업행사/배당·일별 risk 감사가 완료된 것으로 판정하지 않는다. 기존 KOSPI+178.07%도 가격지수 기준이며 배당 포함 TR이 아니다.

## 8. 검증·비용·재현·보존

- 신규 **16 PASS**, 필수/추가 안전 **53 PASS**, DB/Paper/Review/운영 회귀 **55 PASS**, skips0. route 수정 후 필수24개를 다시 확인했다(중복 수를 독립 테스트 수로 더하지 않음). 시험 전용 DB만 초기화했고 운영 source는 읽기 전용으로 검증했다.
- compileall 통과. V104 Forward runner 실제 출력은 `NO_ENABLED_CANDIDATES`, rows_appended0, Live false다. AGENTS 예시의 `NO_NEW_SESSION_AFTER_V104_FREEZE` branch는 이번 실제 설정에서 실행되지 않았다. 예시 문자열과 다름을 숨기거나 후보를 활성화해 강제로 맞추지 않았다.
- 기존 quant-operations.service 수동 정상 실행·자연 timer 정상 실행에서 새 hook을 확인했다. actual reboot는 하지 않았다. 정상 미래 거래 세션의 post-seal live 데이터·체결은 미검증이다.
- 모델6회 실제usage313665/420000. hard CLI token cap은 없어 호출 전90k 여유 예약과 실제usage guard를 사용한다. 구독의 금액은null이고0원으로 단정하지 않는다. 최종6회 한도를 늘리지 않았다. 새 dispatcher 자체 LLM_calls는0이다.
- TPR 원문 HTTP 실패·KT&G 첫 호스트 TLS 실패를 보존하고, 공식 다른 IR 다운로드 경로에서 실제로 확보한 원문을 별도 저장했다. 인증 우회·SEC403 우회·인증정보 출력 없음.

재현(모델 호출을 다시 열기 전에6회예약·trace를 확인):

```bash
.venv/bin/python experiments/task9_2/value_check.py
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q experiments/task9_2/test_research.py
systemctl --user status quant-operations.timer
journalctl --user -u quant-operations.service --no-pager
```

핵심 근거:

- [experiments/task9_2/contract.json](../../experiments/task9_2/contract.json)
- [src/quant_harness/investment/financial_packet.py](../../src/quant_harness/investment/financial_packet.py)
- [src/quant_harness/investment/research_dispatcher.py](../../src/quant_harness/investment/research_dispatcher.py)
- [scripts/run_autonomous_operations.py](../../scripts/run_autonomous_operations.py)
- [runtime/task9_2/historical_numeric_packet_v3.json](../../runtime/task9_2/historical_numeric_packet_v3.json)
- [runtime/task9_2/financial_reconciliations.json](../../runtime/task9_2/financial_reconciliations.json)
- [runtime/task9_2/entity_scope_audit.json](../../runtime/task9_2/entity_scope_audit.json)
- [runtime/task9_2/model_seals.json](../../runtime/task9_2/model_seals.json)
- [runtime/task9_2/current_timed_valuations.json](../../runtime/task9_2/current_timed_valuations.json)
- [runtime/task9_2/current_expectations.json](../../runtime/task9_2/current_expectations.json)
- [runtime/task9_2/forward_decisions/US.json](../../runtime/task9_2/forward_decisions/US.json)
- [runtime/task9_2/forward_decisions/KR.json](../../runtime/task9_2/forward_decisions/KR.json)
- [runtime/task9_2/dispatch_first.json](../../runtime/task9_2/dispatch_first.json)
- [runtime/task9_2/dispatch_repeat.json](../../runtime/task9_2/dispatch_repeat.json)
- [runtime/task9_2/dispatch_migration.json](../../runtime/task9_2/dispatch_migration.json)
- [runtime/task9_2/operations_service.log](../../runtime/task9_2/operations_service.log)
- [runtime/task9_2/limited_historical_audit/result.json](../../runtime/task9_2/limited_historical_audit/result.json)
- [runtime/task9_2/unit_tests_v2.log](../../runtime/task9_2/unit_tests_v2.log)
- [runtime/task9_2/safety_tests.log](../../runtime/task9_2/safety_tests.log)
- [runtime/task9_2/ops_regression.xml](../../runtime/task9_2/ops_regression.xml)
- [runtime/task9_2/v104_forward.log](../../runtime/task9_2/v104_forward.log)
- [runtime/task9_2/persistence.json](../../runtime/task9_2/persistence.json)
- [runtime/task9_2/forward_forecast_status.json](../../runtime/task9_2/forward_forecast_status.json)

## 9. 다음 개선 우선순위

1. 최신 분기 cash/debt·lease/NCI·현재 희석·재투자와 원문 locator를 더 채워 조건부 수치와 실제 적격성 사이의 빈틈을 줄인다. 과거 prefix-style 요약을 다시 적용하지 않는다. 연간/stub/공시 capital date의 차이를 gate로 유지한다.
2. DECK의 DTC·재고·정상화 CF, 삼양식품의 lease/NCI·일회성/FX·capex, PH의 인수 후 debt/연간 CF, KT&G의 비영업 손익/treasury·환원 모델을 회사별로 해결한다. 부족한 자료 때문에 기권한 기업을 투자 매력 없다고 분류하지 않는다.
3. 비거래 지수의 실제 시간대·가격 기준 adapter, 새 전망과 일치하는 공식 실현 재무의 자동 매칭/채점, 실제 INV​ESTABLE의 기존 Shadow 등록·체결을 다음 실증 대상으로 둔다. 현금 결과만으로 배분 성공/실패를 주장하지 않는다.
4. 정상 Factory 예산 갱신 이후 실제 등록·예약·실행을 확인한다. notice 관측·단순 과정 점검과 전체 자율 연구/LLM 후속을 구분하고, 구 job handler를 단계적으로 연결한다.
5. 새 Forward 실적이 성숙한 뒤 예측·가치·선정·비중·실행을 분리 평가한다. 이번 입력 복구/민감도 계산 성공을 투자 능력 또는 초과수익의 성공으로 승격하지 않는다.

## 최종 증거 보존

- [검증 요약](../../runtime/task9_2/verification.json), [이전 연구 보존 검사](../../runtime/task9_2/prior_preservation.json), [임시 파일 정리](../../runtime/task9_2/cleanup.json), [전체 증거 manifest](../../runtime/task9_2/artifact_manifest.json).
- 기존 Task9.1 1,824개 및 Task9 가치연구 1,153개 파일은 원래 manifest의 SHA와 모두 일치한다. 이번 작업의 임시 모델 relay·socket·시험 복제본만 정리했다. 원문·실험·연구 DB dump·기존 checkout과 환경은 보존했다.

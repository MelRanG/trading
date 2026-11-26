# Task13-B1 — 투자 정보 → 연구 후보 최소 연결

**정보 수집 → 공개/버전 검증 → 변화 추출 → 시점별 연구 packet → 후속 계약 초안**을 실제 실행했다. 미국6·한국6개 사전 지정 기업을 조사했고, 원문 변화에서 후보2개를 만들었다.

- **B1_GUIDANCE_DOWNGRADE_H20: `RESEARCH_READY` — 원문·특징량 파일럿 범위.** 동일 FY/기준의 발행사 전망 변경을 원문 두 버전으로 대사하고 특징량을 계산했다. 현재 적격 하향 사건은1개 기업1건으로 **통계적 검정 준비 완료나 알파 성공이 아니다**. 첫 연구용 세션을 확인했지만 Nasdaq 종목별 최종 실행 달력 대사는 공식 경제성 검증 전에 추가해야 한다.
- **B1_CONTRACT_AMENDMENT_H60: `DATA_PARTIAL`.** 이전 계약 대비 명목 증액을 계산했다. 신규 공사 범위·가격/기간 변경·수익 인식의 분리가 남아 있어 경제적 순신규 수주로 승격하지 않았다.
- 새 정보 카테고리를 더 만들지 않고 **동일 가이던스 변경 유형의 제한적 알파 파일럿**을 다음 단일 작업으로 추천한다. Quanta/RD·학습·백테스트·내부 연구 LLM 호출은 **모두0**. Factory 등록/예약·운영 변경도0이다.

## 1. 기존 기능과 재사용 판정

Task11~14, R0~R2와 [B0](13_B0_new_information_feasibility.md), [SEC 복구](13_B0_sec_access_recovery.md)를 출발점으로 사용했다. 원본 엔진 실행과 투자 정보 우위를 혼동하지 않았다.

| 기존 자산 | 판정 | 지원하는 결정 / 실제 재사용과 한계 |
|---|---|---|
| 복구된 EDGAR submissions/companyfacts | READY | 기업/이벤트 탐색·재무 변화. 기존 `.env`와 `equities.fetch`로 정상 GET. 단, 모든 역사 이벤트의 PIT가 완성됐다는 뜻은 아님 |
| DART·B0 최초/잠정/정정 원문 | READY | 이미 알려진 실적·수주와 새 정보 구분. OpenDartClient·B0 원문을 재사용 |
| Task9.2 financial_packet | READY | 금액·단위·기간·CFS·출처 검증. 실제 원문 숫자83개를 대사 |
| Team2 Vibe earnings/valuation/macro/sector 방법 | PARTIAL | 연구 논리·비교 기준. 스킬은 원문/vintage DB가 아니며 이번 전체 Vibe CLI·LLM 실행 없음 |
| Vibe FRED tool | PARTIAL | API 기능은 있으나 현재 FRED 키 없음, 원본 구현에 realtime/vintage 고정 없음 |
| 날짜별 공식 FOMC 원문 | READY | 자금조달/할인 환경의 변화 맥락. 기업/계좌 비중 정책 아님 |
| DGS10·HY spread snapshot | PARTIAL | 금리·신용 위험 자료는 확보. 최초 vintage 미확인으로 역사 확정 입력에서 제외 |
| ALFRED vintage 키/ECOS 검증 adapter | MISSING | 조사 범위에서 설정·적격 경로 미확인. 새 계정/서비스 안 만듦 |
| 역사 컨센서스·투자자 수급 | MISSING | YoY=surprise, 거래량=기관 수급 같은 대체 금지 |
| 현재 거시 수정치를 과거 최초값으로 사용 | UNSUITABLE | 해당 사용 방식 차단 |
| 업종 노출·시장 국면 | PARTIAL | 기존 사업 분류·R0 세션·Task12 계약 사용. 역사 전 업종/ETF flow 패널은 아님 |
| Factory 계약·후보 전달 | READY(초안) | 기존 필수 필드·최소12 독립 사례·예산 형식 재사용. 실제 등록/실행 아님 |

공통 형식은 `runtime/task13_b1/data_contract.json`, 상세 자산표는 `asset_inventory.json`이다. 새 DB·상시 서비스·백테스터·운영 hook은 만들지 않았다. 추가 코드는 task-local 수집·검산·packet/draft 생성뿐이다.

## 2. 미국 — 정상 접근과 원래 제출본 수치 연결

SEC 접속은 이미 복구된 것으로 취급했다. MSFT submissions/companyfacts를 정상 GET으로 최소 재확인하고 동일 설정을 나머지 기업에 사용했다. 연락처·인증값을 기록하지 않았고, 접속 재진단·프록시·환경 변경은 없었다. SEC API의 CIK별 submissions/companyfacts 경로를 사용했다([공식 API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)).

| 사전 기업 | 업종 | 지정 분기 metadata | 검증 수치 / 원문 inline 대사 |
|---|---|---:|---:|
| MSFT | 소프트웨어 | 2024/2025년3월말, 2건 | 10 / 5 |
| PEP | 필수소비재 | 2024/2025년 Q1, 2건 | 12 / 6 |
| SFM | 식품 유통 | 2024/2025년 Q1, 2건 | 10 / 5 |
| PH | 산업 부품 | 2024/2025년3월말, 2건 | 9 / 4 |
| DECK | 소비재 | 2023/2024년12월말, 2건 | 10 / 5 |
| JPM | 은행 | 원 API 확보, 지정 역사 분기 metadata 미연결 | 0 / 0; 부분 성공으로 유지 |

6개 회사의 submissions/companyfacts를 확보했지만 **분기 정규화는5개**다. JPM은 제한한 역사 submissions 파일에서 목표 분기를 찾지 못했고, 은행 수익·예금/차입을 제조업 매출·총차입금으로 억지 대응시키지 않았다. 후보 확보 후 JPM 이력 파일을 계속 확장하지 않았다.

- `companyfacts` 행의 **accession·filed·보고기간·단위**가 선택한 제출본과 일치하는 값만 사용했다. JSON 원문 locator까지 `verify_fact`로 검산했다. 단순 최신값/`frame`만으로 과거를 복원하지 않았다.
- 신규 원문10-Q는 기업별 지정 최신 분기1개(총5개)를 확보했다. inline XBRL의 전체기업 context, 시작/종료/instant, scale·sign을 독립 계산해 **25개 수치**를 API와 대사했다. 나머지26개는 원본 API 행 출처 검증이며 동일 수준의 inline 대사를 완료했다고 쓰지 않는다.
- 총51개 수치에는 매출·영업이익·순이익·현금·차입 구성요소·표기된 기간의 OCF 등이 있다. 차입 구성요소를 총차입금으로 합성하지 않았고 OCF의 YTD를 임의 분기화하지 않았다. DECK은 연간/분기를 섞지 않도록 미리 다른 회계분기를 지정했다.
- API acceptance 문자열은 보존했으나 timezone/원문 header 미대사이므로 초·분 정밀도 공표 시각으로 승격하지 않았다. 연구 이용 상한은 확인한 제출일의 **뉴욕 현지 일말**이다. 회사의 더 빠른 IR이 있었을 수 있어 10-Q를 최초 실적 뉴스로 보지 않는다.

실제 결과: `US_collection.json`, `US_fundamentals.json`, `normalization_summary.json`. 회사 전체 API에는 미래 시점 수치도 있으므로 **역사 worker에 전체 companyfacts를 mount하지 않는다**.

## 3. 한국 — 선행 실적과 정정 계보 유지

| 사전 기업 | 업종 | 실제 사용 |
|---|---|---|
| LG이노텍 | 전자부품 | B0 2024/2025Q1, 더 이른 잠정실적 재사용 |
| 삼양식품 | 식품 | B0 2024/2025Q1 원문·수치 재사용 |
| 삼성E&A | 엔지니어링 | B0 최초 계약·부분 계약·정정 원문 계보 |
| 현대로템 | 철도/방산 | B0 최초 계약2건, 별도 고객/기간/조건 |
| KT&G | 담배 | 2024/2025Q1 원문과 선행 잠정공시 추가 |
| 삼성전자 | 반도체 | 2024/2025Q1 원문과 선행 잠정공시 추가 |

정규 분기8건의 CFS 수치 **32개**를 기간·원/백만원·원문 table 위치와 대사했다. B0 재사용 계약/정정6건과 잠정 공시6건을 합쳐 한국 원문20개에 대한 참조 경로가 있다. 서로 다른 기업 사건 수와 같은 기업 버전 수는 구분한다.

KT&G의 식별자 한 건은 계획 초안의 오기를 기존 catalog로 **첫 요청 전에** 교정해 별도 amendment에 남겼다(00244455). 계획을 결과에 맞춰 바꾸거나 다른 회사를 수집하지 않았다.

- LG 2025Q1 잠정 영업익125,116백만원과 정기보고서125,117백만원 차이를 그대로 보존했다. 최초값을 확정값으로 교체하지 않았다.
- KT&G는 2024-05-09/2025-05-08, 삼성전자는 2024-04-05/2025-04-08 잠정 공시가 뒤 분기보고서보다 먼저 있었다. 정기보고서 날짜에 새 실적 정보가 처음 발생했다고 표시하지 않는다.
- 신규 DART 조회는 `last_reprt_at=N`, 회사별 지정 기간과 원문 접수번호를 사용했다. 제출일만 있는 자료는 **서울 현지 일말 상한**이며, 과거에 실제 수집한 자료처럼 관측 시각을 소급하지 않았다.

`KR_collection.json`, `KR_fundamentals.json`과 B0 원문을 참조한다. DART API 성공과 최초 모든 공개 채널·분 단위 시각 완전성은 별개다.

## 4. 거시·시장 입력 3종과 실제 결합

| 자료 | 확보/변화 | PIT 판정 및 결합 |
|---|---|---|
| FOMC 목표금리 | 2024-06-12 5.25~5.50% 유지, 2024-09-18 4.75~5.00%로50bp 인하 | 공식 날짜별 원문과 14:00 EDT 발표 문구 확인. VERIFIED_DATED_RELEASE |
| DGS10 | 2024-06~2025-06, 유효268/결측13행 | PIT_PARTIAL; 최신 backfill, 최초 공개/vintage 미확인 |
| HY OAS(BAMLH0A0HYM2) | 같은 기간 유효282/결측3행 | PIT_PARTIAL; 동일 제한 |

[FOMC 6월](https://www.federalreserve.gov/newsevents/pressreleases/monetary20240612a.htm), [9월](https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm)의 실제 목표 범위·행동을 계산했다. 연구 처리 지연은 **가정5분**으로 명시했다. 실제 역사 수집 지연을 안다고 주장하지 않는다.

FRED API 키가 없어 기존 Vibe API를 실행한 것으로 표시하지 않았다. 공식 공개 CSV는 확보했지만 `observation_date`를 공표일로 바꾸지 않았다. [FRED API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html)의 realtime/vintage 조건과 [ALFRED 원칙](https://alfred.stlouisfed.org/help)을 충족한 자료가 아니므로 **DGS10·spread는 역사 worker 입력에서 제외**했다. 결측 보간도 없다.

실제 join:

- PEP 7월 전망에는 당시까지 공개된6월 FOMC, 10월 전망에는9월 FOMC만 연결했다.
- 삼성E&A 2024-12-05 정정에는9월 FOMC 맥락을 연결했지만 2025-12-15에는120일 freshness 한도를 넘겨 **None**이다. 과거 정책을 무한 carry하지 않았다.
- 이 맥락은 달러 할인/차환 환경에 관한 정보다. 특정 기업의 실효금리·한국 자금조달 조건 개선이나 국내 시장 국면을 증명하지 않으며 자동 비중·매매 규칙으로 바꾸지 않았다.

`macro_normalized.json`의 partial 자료와 `worker_packets/`의 적격 입력은 구분돼 있다. 국내 사건·시장폭·수급·완전한 업종 강도는 부족하지만 새 카테고리 수집을 완료 조건으로 삼지 않았다.

## 5. 후보1 — 발행사 전망 하향 변경, H20

**RESEARCH_READY: 제한적 원문/특징량 연구.** 통계적 예측력·매매 적격성 판정은 아니다.

PEP 공식8-K 첨부 원문을 실제 링크에서 받아 이전 전망을 대사했다.

| 공개일 / 원 제출번호 | FY2024 유기적 매출 성장 전망 | 해석 |
|---|---|---|
| 2024-07-11 / 0000077476-24-000043 | 약4%, 이전에는 최소4% | 하한 제거/완화. 임의 수치 하향폭을 만들지 않음 |
| 2024-10-08 / 0000077476-24-000054 | 낮은 한 자릿수, 이전 약4% | 이전 원문의 값과 정확히 연결되는 하향 변경 |

[2024-07-11 공식 첨부](https://www.sec.gov/Archives/edgar/data/77476/000007747624000043/q220248-kxexhibit991.htm) / [2024-10-08 공식 첨부](https://www.sec.gov/Archives/edgar/data/77476/000007747624000054/q320248-kxexhibit991.htm)

양쪽 원문은 **core constant-currency EPS 최소8% 성장 전망을 유지**한다. 수익성/비용 대응의 반대 근거를 삭제하지 않았다. FY·organic/non-GAAP·FX 기준을 동일하게 맞췄다. 이는 컨센서스 surprise가 아니라 **발행사 자체의 이전 공개 전망 대비 변화**다.

- 경제 가설: 약해진 매출 전망의 해석/주의력 제약으로 이후 상대수익에 음의 정보가 남을 수 있다. EPS 전망 유지·이미 반영된 시장 기대 때문에 효과가 사라질 수도 있다.
- 실제 특징량: `explicit_downward_guidance_revision=-1`, primary H20. 낮은 한 자릿수를 임의1~3%·중앙값으로 숫자화하지 않았다. 최초 원문 쌍1개/기업1개다.
- 이용 시점: 제출일 일말 상한 이후, 기존 지수의 **날짜 열만** 읽어 확인한 다음 관측 세션 **2024-10-09 09:30 ET**. [NYSE 2024 휴장표](https://ir.theice.com/press/news-details/2023/NYSE-Group-Announces-2024-2025-and-2026-Holiday-and-Early-Closings-Calendar/default.aspx)로 미국 정규 세션을 보조 확인했다. PEP는 Nasdaq 상장이므로 **종목별 Nasdaq 달력/체결 대사는 공식 경제성 평가 전에 별도 확인**한다. 현재 Paper/주문 적격성을 부여하지 않는다.
- 기준선: 동일 H20 S&P500, 사전 업종상 XLP(PEP 중복 노출 추후 계량), MOM20/REV5, 무변경 전망 사건. 방향/기간은 수익률 조회 전에 고정했다.
- 기각 기준: as-of/이전 전망 연결 실패, 같은 지표가 아님, OHLCV·업종 통제 후 증분 부재, 선택/다중검정·사건 의존성으로 소멸, 이후 비용 포함 경제성 소멸. 단일 사건의 가격 상승/하락으로 결론 내리지 않는다.
- 다음 실행 방식: **결정론적 Python → 기존 Qlib/Task12 평가**. 먼저 같은 정보 유형에서 독립30사건/12기업 목표를 정해 표본·누출·예측력만 검증한다. 별도 LLM·새 모델이 필수는 아니다.

원문/PIT/규칙 예제가 확보돼 파일럿을 시작할 수 있다는 의미의 READY다. 현재1건으로 예측력 검정이 가능하다는 뜻은 아니다. 미래 자료는 새로운 독립 Forward에서 쌓아야 하며, 이 역사 구간은 노출된 개발 자료다.

## 6. 후보2 — 기존 계약의 명목 증액, H60

**DATA_PARTIAL.** 동일 계약의 원래 금액과 정정 금액을 연결해 다음을 실제 계산했다.

| 정정일 | 이전 → 정정 계약금액(원) | 차액 | 이전 금액 대비 |
|---|---|---:|---:|
| 2024-12-05 | 496,272,700,000 → 758,830,600,000 | +262,557,900,000 | +52.9060% |
| 2025-12-15 | 758,830,600,000 → 873,400,000,000 | +114,569,400,000 | +15.0982% |

부가세·통화·이전 공시일·변경 전 금액을 대사했다. 2024년 입력에서2025년 정정을 제외했다. **공개 명목 금액의 차이이며 순신규 수주·추가 이익과 동일하지 않다.** 물량/범위 증가와 가격·기간·조건 변경을 원문 계약 조건으로 분리해야 한다. 다른 B0 삼성E&A 부분 계약1.232조원도 전체를 순증으로 사용하지 않았다.

가설 방향은 경제적 순증 범위/실행 가능성이 확인된 경우에만 양의 H60 연구로 전환한다. 현재 scalar 매수 신호를 만들지 않았다. 비교는 KOSPI·사업상 산업 대안·MOM/REV·경제적 범위 변화 없는 정정이다. KRX 역사 달력은 미대사이며, 관측된 후보 세션2024-12-06/2025-12-16은 provider 날짜 근거로만 남긴다. 이 조건과 독립 사례 부족을 해결하기 전 실행/통계 승격은 안 된다.

## 7. 실제 다음 연구 전달과 누출 검사

`research_candidates.json`과 기존 Factory 필수 필드에 맞춘 `factory_handoff_drafts.json`을 생성했다. 현재 운영 registry는 읽기만 했다(관측 당시7건, 당일0건). **등록0·예약0·dispatcher0·원장 쓰기0**이며 초안 생성 자체를 Factory 실행이라고 보고하지 않는다. 기존 최소12 독립 사례 및 `experiments=1/parameter_search=0` 예산 형식을 유지했다. 초안의 비교군은 연구 기준선이며 실제 Champion이 아니다.

세 개의 봉인 packet:

- `PEP_2024-10-08.json`: 그때까지 원문 두 개와 당시 FOMC만.
- `KR_2024-12-05.json`: 최초 계약+그때의 정정만. 2025 정정 없음.
- `KR_2025-12-15.json`: 해당 날짜까지 계보, stale 거시 맥락 없음.

각 packet에는 **원문 mount allowlist**와 SHA가 있다. 전체 companyfacts/current submissions·미래 정정·평가 자료·FRED 수정 backfill을 worker에 직접 주지 않는다. 실제 worker/알파 엔진은 시작하지 않았다. 소스 변경/부모 금액 불일치/미래 부모/다른 metric·basis는 fail-closed다.

검증은 신규6개 **PASS**: 실제83수치 출처, US25개 원본 inline 대사, 이전 전망 연결·회계 기준, 미래 정정 교란 불변, partial/stale 거시 차단, worker allowlist/봉인, Factory 초안 규칙을 확인했다. API JSON locator·DOM bullet·partial macro 분기·빈 달력 행 처리의 초기 오류4건은 로그에 보존했고, 새 원문 요청/LLM 추가 없이 교정했다. 최초 실패를 통과로 재표기하지 않았다.

필수4개 suite **24 passed** 및 compileall PASS. 이전 전체 프로젝트 복사로 `.venv/runtime`까지 복제하던 테스트 비용을 피하려고, **현재 src/scripts/tests/config/data/reports를 SHA 대조한 격리 snapshot**에서 원본 테스트를 변경 없이 실행했다. `.env`·runtime·가상환경은 복사하지 않았다. 임시 복제는 종료 후 제거했다(`safety_snapshot.json`). 운영 코드를 바꾼 시험이나 축소 테스트를 전체 통과로 표시한 것이 아니다.

## 8. 비용·보존·최소 보완

- HTTP **39/60**, 성공39/실패0. 약**48.64MB 다운로드**, 검증 후 gzip 보존. 압축/추출/결과를 합친 새 runtime은 약**17MB** 수준이다. 기존 B0 파일은 참조로 재사용했다.
- 요청 wall 합계 약14.37초. 전체 작업시간/CPU 청구액은 아니며, 신규 유료 계약·설치·상시 서비스 없음. 실제 청구 정보는 N/A.
- 공식 문서/달력 확인 web 도구3회/명령5개. 내부 요청 수는 제공되지 않아 Python HTTP 수와 분리했다. 부수 검색 결과의 가격/사후 성과는 입력·후보 선택·계산에 사용하지 않았다.
- 내부 연구 LLM **0회/0 tokens**, Quanta/RD **0**, 학습/백테스트 **0**. 구조화 수치는 Python으로만 처리했다.
- 기존 R0~R2·Task13/14·B0·SEC복구의 **4,616개 파일 해시 불일치0**, 운영 timer active. 전략·Factory 예산·Paper·Forward·Live·Team2 수정 없음. 새로운 금융 문서는 연구 격리 자료이며 V87 가격 스키마 통과/운영 편입으로 표현하지 않는다.

**다음 단일 작업:** `B1_GUIDANCE_DOWNGRADE_H20`의 동일 전망 변경 유형에서 표본/시점 계약을 먼저 봉인하고, 제한된 원문 확장과 Python 기반 증분 예측력 파일럿을 수행한다. 최소30독립사건/12기업은 추론 조건이며 현재 충족했다고 보지 않는다. 이전·개발 자료, horizon label의 purge/embargo, 같은 노출/업종·MOM 기준선, 다중검정·이벤트 의존성을 기존 Task12~14 계약으로 검증한다. 비용 후 경제성은 그 뒤 별도 승인된 작업이다.

추가 거시 카테고리·엔진 교체·전체 시장 수집은 선행 조건이 아니다. 계약 후보는 필요한 증액 범위/조건만 제한 보완한다. 이번 작업은 후속 알파 연구·Task15·Forward 변경을 자동 실행하지 않았다.

실행·재생 경로: `experiments/task13_b1/{collect,normalize,bridge,handoff,packets}.py`, `test_bridge.py`; 보존 목록은 `runtime/task13_b1/artifact_manifest.json`, 진행 기록은 `13_B1_progress.md`다. 수집기 재실행은 완료 receipt/hash를 재사용하며 모델/후속 실험을 실행하지 않는다.

완료 후 수집기를 실제 재실행해 request/source receipt SHA 불변, HTTP 39→39(신규0)을 확인했다. 재사용/재개 증거는 `resume_proof.json`.복구된 SEC 식별 설정 SHA도 작업 전과 같다.

# Task 9.0 — 역사적 투자 재현·연구 능력 검증

2026-11-14 KST / HYBRID_MINIMAL 유지. **실제 역사 자료 수집·다섯 시점의 제한 기업 연구·대표 A/B/C·실적 시나리오 채점은 실행했다. 그러나 신뢰할 수 있는 5년 투자 재현은 완료하지 못했다.**

## 핵심 결과와 완료 수준

| 판정 대상 | 결과 | 실제 증거와 한계 |
|---|---|---|
| 기술적 재현 | **PARTIAL** | 원본 Vibe 구성요소→봉인→원문 기반 실적 채점→Review 후속 작업은 연결. 기존 QH 매수·매도 리플레이는 합성 입력에서 확인. 실제 역사 기업 발굴→적격 체결→성과의 완결 사례는 없음 |
| 데이터 신뢰도 | **PARTIAL / 핵심 gate BLOCKED** | DART 원문 20건·가격지수 확보. 전체 PIT 종목군·코드 이력·상폐·기업행사·공식 역사 세션과 컨센서스 부족 |
| 연구 성능 | **제한 실측, 우위 미입증** | 3개 기업·6개 실적 시나리오 채점. 일부는 단순 연율화보다 나쁘고 소표본·LLM 과거지식 교란 존재 |
| 투자 성능 | **미검증** | 연구 후보와 당시 가격의 투자 매력·매수 가능성을 함께 인증하지 못함 |
| 포트폴리오 성능 | **미실행** | A/B/C 및 5년 계좌 수익률·지수 대비 초과수익을 생성하지 않음. 자료 부족으로 생긴 비중 0을 유효한 현금 전략 성과로 세지 않음 |
| 개선 연결 | **PASS — 제한 범위** | 별도 PostgreSQL에 근거·복기·후속 요청 보존, 공식 Factory 등록 시도. 등록은 정상 일일 예산 소진으로 BLOCKED, 공식 실험 미실행 |

실제 연구 모델 호출은 Terra **8회 성공·591,801 토큰**이다. 최초 두 작업은 요청 크기 preflight에서 거부돼 별도 입력 버전으로 축소했다. 이 두 작업을 LLM 실행으로 세지 않았다. 신규 시험 13개·AGENTS 필수 안전 시험 24개, **37개 통과**. 운영 `src/`, `scripts/`, `config/`와 기존 Forward·Paper 원장은 수정하지 않았다.

## 1. 실제 역할과 재사용 경로

[소스 경로·SHA·버전 실사](../../runtime/task9_historical/source_inventory.json). 원본 checkout은 모두 clean이다.

| 구성 | 이번 사용과 확인 범위 |
|---|---|
| Vibe `0025531f005d4a7aac3fb884cda2fba9318e7158` | 원본 `src.providers.chat.ChatLLM`을 기존 격리 환경에서 실행. 고정 원문 packet으로 기업 연구·수치 시나리오·시장 해석·대안 비교를 생성 |
| Vibe screener | `tools/market_screener_tool.py:_screen_market`는 현재 Eastmoney 조회이며 as-of 인자가 없다. 현재 screener를 2021년 시장 탐색처럼 실행하지 않음 |
| Research Autopilot / financial research | goal·이력·artifact 기능은 있으나 역사 종목군과 원문 버전을 인증하는 기능을 대신하지 못함. 이번은 full Autopilot 완주가 아니라 원본 연구 구성요소의 제한 실행 |
| valuation | 원본 DCF/EV→equity 계산 재사용 가능. 당시 주식수·청구권·실행 가격이 적격하지 않아 검증된 역사 목표가를 생성하지 않음 |
| macro / sector rotation / earnings revision | 코드·bundled 지시문 확인. FRED 도구는 관측 날짜 필터를 제공하지만 이 구현에는 vintage 고정이 없다. 섹터 예시는 A주 분류 중심이며 과거 US/KR 업종·흐름 자료가 아니다. revision 스킬 자체가 과거 증권사 컨센서스 데이터는 아님 |
| Quanta `b7ceb27b1001261d7a95b209a963664ae1f8ab23` | Task6 원본 planning/evolution adapter와 결과 재사용 가능성을 확인. 2026년에 생성된 survivor-cohort 팩터를 2021년 당시 신호로 사용하지 않음. 이번 새 진화 탐색은 미실행 |
| RD `484776c211e4fbbeef03e0ec00d6bbee7362a4f4` | 기존 원본 Qlib GRU 학습 경로 확인. 역시 당시 생성 신호가 아니므로 이번 역사 선택에 넣지 않음. 재학습 미실행 |
| QH 수집 | 기존 DART client, Toss candles, Yahoo normalization 및 V87 numeric/revision gate 사용. 기존 운영 canonical은 교체하지 않음 |
| QH 실행 | `investment.research.replay_targets`의 D-1 sizing·다음 open·비용 계산을 얇은 gate adapter로 연결하고 합성 매수·매도를 시험. 이 함수 자체에 배당/분할/상폐 event 처리가 없어, 해당 연결이 없는 구간은 별도 차단 |
| QH 평가·Review·Factory | 원문 공개시각·기간·단위·출처 및 봉인을 별도 실험 계약에서 검사. 기존 `Store`, `Queue`, `register_review_proposal` 재사용. 운영 계좌와 다른 DB 사용 |

사용자가 제시한 **마스터 프롬프트 V3의 핵심 원칙**을 실제 연구에 적용했다. 저장소에서 별도 V3 원문 전체는 찾지 못했으며 원문을 읽거나 그대로 재현했다고 주장하지 않는다. 기존 Task1~8b를 다시 설치하거나 과거 실험을 재실행하지 않았다.

## 2. 확보한 역사 데이터와 PIT 적격성

실행 전 [전체 계약](../../experiments/task9_historical/contract.json)과 [제한 원문 표본 계약](../../experiments/task9_historical/partial_corpus_contract.json)을 보존했다. 전체 시장을 확보하지 못하면 제한 공시 표본 연구로 낮추되 매매·성과는 fail-closed하도록 했다.

| 자료 | 미국 | 한국 | 적격성·중요한 공백 |
|---|---|---|---|
| 당시 전체 상장·상폐·코드 이력 | 미확보 | DART 월별 공시 첫 100행 확보 | **UNVERIFIED / PARTIAL**. 공시자 집합과 거래 가능 주식 전체는 다름. 현재 Nasdaq/DART 목록으로 대체하지 않음 |
| 역사 가격·거래량 | S&P 500 가격지수 | KOSPI 가격지수·대표 3종목 과거 일봉 | **PARTIAL**. 현재 재다운로드이며 수정·기업행사의 독립 완전성 인증 없음 |
| 공시 원문 | SEC 직접 접근 3종 실패 | 접수번호 고정 원문 20건 | 개별 원문·공개일은 확인하나 XML 복구·보고서 날짜 불일치·표본 범위는 **PARTIAL** |
| 공식 거래 세션 | NYSE 2021 연간 예정 달력 확보 | 역사 세션 chain 미확보 | 전체 다섯 시점 및 평가 기간의 실제 공식 세션 검증 미완료 |
| 배당·분할·상폐 현금·거래정지 | 미확보 | 미확보 | **UNVERIFIED**, 보간·누락 수익률 생성 금지 |
| 금리·환율·거시 최초 발표·개정 | 2021-11-03 Fed 공식 발표 | 2021-11-25 BOK 공식 발표 | 대표 시점의 두 발표만 확인. 광범위한 vintage DB·환율 이력은 미확보 |
| 뉴스·산업·경쟁사 당시 정보 | 완전 archive 없음 | 원문 사업·위험 내용 일부 | 공시 밖의 독립 정보 발굴 범위 제한 |
| 업종 상대강도·수급·ETF 흐름 | 미확보 | 미확보 | 현재 정보나 짧은 지수 이력에서 추정하지 않음 |
| 당시 컨센서스·추정 변경 | 미확보 | 미확보 | 현재 analyst 데이터로 과거 consensus를 채우지 않음 |
| S&P 500·KOSPI TR | 미확보 | 미확보 | 확보한 것은 가격지수이며 SPY/KODEX 200로 바꾸지 않음 |

[실제 HTTP 및 DART 응답](../../runtime/task9_historical/audit/): SEC 2021Q3 재무 ZIP, 2021Q4 master index, submissions 접근 진단은 모두 403이었다. 마지막 submissions는 접근 진단일 뿐 그 회사를 후보로 선정하지 않았다. KRX 역사 종목 조회도 403이었다. 유료 구매·403 우회·조작 응답은 사용하지 않았다.

SEC는 [원문·인덱스·정정 및 삭제 이력의 특성](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)을 설명하고 있다. 접근 가능성 문서와 이번 서버의 실제 수집 성공은 구분했다. DART는 [공식 공시검색 API](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001)의 `last_reprt_at=N`을 사용해 현재 최종 정정본만 남기는 필터를 피했다.

### 실제 발견한 시점·추출 문제

1. `TossOpenApiClient.get_market_calendar(start_date,end_date)`는 인자를 받지만 구현은 현재 previous/today/next snapshot을 요청한다. 과거 날짜 인자만 넣고 역사 달력이 확보됐다고 판정할 수 없다.
2. DART 현재 목록의 ‘와이앤넥스트’가 접수번호 `20260506000158`의 원문에는 ‘연이비앤티’였다. 현재 이름·시장 구분·코드 연결을 당시 사실로 자동 인정하지 않았다. 연구 입력에는 원문 회사명을 사용했다.
3. 일부 2021 XML은 UTF-8 선언과 달리 CP949였다. strict decoding으로 구분했고, 잘못 해독한 v0·원본 ZIP을 보존했다. DART 표시용 `&cr;`와 잘못 escape된 원문은 XML recovery가 필요해 경고 수를 기록했다. recovery 결과를 완벽한 표 구조로 인증하지 않았다.
4. 일부 요약재무 추출은 실제 본문 대신 목차를 잡았다. 2021 대표 입력을 별도 A3 버전으로 수리했고 A2 결과는 보존했다. 같은 알고리즘의 성과를 높이려고 기간·후보를 바꾼 것이 아니다. A2/A3는 입력 품질 차이가 있어 순수 분석 효과 비교로 부르지 않는다.
5. 동남합성의 CFS API는 `013`이었다. 원문의 ‘연결재무제표 해당사항 없음’을 구분하지 못한 scope 선택을 성공으로 덮어쓰지 않고, 이미 확보한 원문 별도 재무 요약의 명시된 단위·2025 첫 열로 평가했다.

## 3. 다섯 시점의 실제 기업 연구

각 달 공시 전체 건수는 2,955 / 3,316 / 3,203 / 3,259 / 3,302건이었다. 이 중 **날짜순 첫 100행씩 총 500행**을 관측했고, 각 달 첫 네 개의 서로 다른 법인·비정정 분기/반기 보고서 원문을 수집했다. 현재 생존 여부·상승률·관심 종목으로 선별하지 않았다. SPAC·비상장 회사도 입력에 남겨 모델의 제외 이유를 관측했다.

이는 공시를 이르게 제출한 회사에 치우친 **비확률·제한 표본**이다. 원문 20건은 서로 다른 20개 법인이지만 SPAC·비상장 등을 포함하므로, 20개 적격 투자 기업이나 시장 전체에서 AI가 발굴한 20개 유망주라는 뜻은 아니다.

| 연구 시점 | 원문 4개 회사 | 실제 A2 연구 우선순위·제외 |
|---|---|---|
| 2021-11 | 이미지스·JTC·DB금융8호SPAC·솔루엠 | 이미지스→JTC, 솔루엠 자료 추가, SPAC 제외 |
| 2023-11 | 앱코·와이엠텍·하나머스트7호SPAC·블루엠텍 | 와이엠텍→앱코, 블루엠텍 추가자료, SPAC 제외 |
| 2024-11 | 카페베네·코미팜·티에스아이·동남합성 | 동남합성→티에스아이, 코미팜 대기, 카페베네 제외 |
| 2025-11 | 미래에셋비전7호SPAC·닷밀·SM Life Design·노을 | 닷밀→노을, SM Life Design 대기, SPAC 제외 |
| 2026-05 | 연이비앤티·하이로닉·에스엠씨지·아이퀘스트 | 아이퀘스트→하이로닉→에스엠씨지, 연이비앤티 제외 |

모델은 원본 Vibe ChatLLM에서 실제 실행됐다. 미국의 역사 후보 발굴은 전체/제한 적격 pool 모두 확보하지 못해 **미실행**이다. 한국 연구 cutoff는 월말의 보수적인 civil clock이며, 공식 마지막 거래 세션을 확인한 것으로 표시하지 않았다. 따라서 이 표는 당시 투자 가능한 종목의 최종 선정표가 아니다.

자료·요청·응답·해시: [원문](../../runtime/task9_historical/originals/), [입력 packet](../../runtime/task9_historical/packets/), [실제 응답](../../runtime/task9_historical/research_outputs/), [봉인](../../runtime/task9_historical/seals/manifest.json). 가격·실적 평가 자료는 연구 container에 mount하지 않았다. 모델 도구·웹·호스트 파일 접근은 비활성화했다. 다만 **LLM 학습 중의 역사 지식은 제거하지 못했다.**

## 4. 대표 2021 시점 A/B/C 결과

동일 A3 기업 원문·선택 범위·위험 계약에서 A를 보존하고 B에 당시 공식 시장 정보를, C에 동일 회사 사이의 대안 비교를 추가했다. A3/B3/C3는 같은 기초 입력 hash와 공유 session hash로 묶었으며 각 모드 요청·출력 hash도 별도 보존했다.

- **A 기업 연구:** 이미지스의 매출·흑자 전환과 개발비 자산화, 솔루엠의 이익 대비 현금 유출·재고, JTC의 방일 관광 회복 가설·자금 위험, SPAC의 사업 부재를 구분했다.
- **B 시장 재평가:** [2021-11-03 Fed 공식 발표](https://www.federalreserve.gov/newsevents/pressreleases/monetary20211103a.htm), [2021-11-25 BOK 공식 발표](https://www.bok.or.kr/eng/bbs/E0000634/view.do?menuNo=400069&nttId=10067647&pageIndex=1)와 cutoff 이전의 제한 KOSPI 이력을 추가했다. 금리·유동성·여행 회복을 촉매/위험으로 해석했지만, 없는 수급·컨센서스·63일 업종 모멘텀을 만들지 않았다.
- **C 상대 대안:** 같은 네 회사에서 연구 비용을 우선 배정할 대상·대기·제외와 기회비용을 명시했다. 사후 상승 종목을 추가하지 않았다.

| 모드 | 실제 우선순위·판단 | 숫자 포트폴리오 | 확인된 증분 |
|---|---|---|---|
| A3 | 이미지스→솔루엠 연구, JTC 대기, SPAC 제외 | 적격 비중 산정 불가 | 본문 수리 후 솔루엠의 재무 검토 범위가 늘었음 |
| B3 | A3와 같음 | 전 종목 실행 비중 0·미실행 | 거시·촉매 설명 추가, 판단 변경 없음 |
| C3 | B3와 같음 | 전 종목 실행 비중 0·미실행 | 상대 비교·보류한 배분·기회비용 명시, 판단 변경 없음 |

대표 가격 진단은 사전에 선정한 접수번호의 코드로 Toss 과거 200일 일봉을 요청했다. 이미지스 2,140원, JTC 3,800원, 솔루엠 23,050원의 참조 종가를 얻었고 SPAC 요청은 실패했다. **현재 코드→과거 법인 연결·기업행사·공식 세션이 미검증**이므로 적격 체결 가격으로 쓰지 않았다. 이 값이 보인다는 이유로 주당가치·목표 비중을 강제하지 않았다.

가치평가·Reverse DCF·EV/주주가치·부채·희석 분석은 필요한 과거 자본 구조와 적격 가격이 부족해 검증된 숫자까지 완성하지 못했다. 시장 정보와 대안 비교가 투자수익률을 개선했는지는 **판별 불가능**하다. 이번 표본의 판단 불변은 해당 정보가 일반적으로 무가치하다는 실증도 아니다.

## 5. 미래 실적 시나리오의 실제 결과 채점

주가 결과와 분리해 A2에서 생성한 최초 수치 시나리오 6개를 3개 기업의 원본 후속 보고서로 확인했다. 첫 회사는 최초 숫자 전망이 있는 후보를 결과 조회 전에 선택했다. 추가 두 회사는 이미 생성된 2024 A2 숫자 전망 **전부**를 평가 대상으로 고정한 뒤 미래 자료를 조회했다. 결과를 보고 예측이나 후보를 고치지 않았다.

| 회사·예측 회계연도 | 지표 | Base 예측 | 실제 | 절대 상대오차 | 같은 자료의 단순 9개월 연율화 오차 |
|---|---|---:|---:|---:|---:|
| 이미지스 2022 | 매출 | 21,000 | 21,917.077 | 4.18% | 4.29% |
| 이미지스 2022 | 영업이익 | 1,000 | 1,551.364 | 35.54% | 18.06% |
| 동남합성 2025 | 매출 | 180,000 | 194,264.824 | 7.34% | 5.29% |
| 동남합성 2025 | 영업이익 | 9,000 | 9,365.332 | 3.90% | 미채점 |
| 티에스아이 2025 | 매출 | 250,000 | 264,652.707 | 5.54% | 6.47% |
| 티에스아이 2025 | 영업이익 | 12,500 | 8,245.033 | 51.61% | 미채점 |

단위는 모두 **백만원**, 기간은 각각 1/1~12/31이다. 모든 실제 값은 넓은 Bear~Bull 범위 안에 있었으나, 임의 스트레스 범위의 포함률을 보정된 확률 예측의 품질로 해석할 수 없다. Base 실적 오차와 주가 예측 정확도는 별개다. 일부 매출 오차의 근소한 개선만으로 기준선 우위를 주장하지 않는다.

이미지스·티에스아이는 재무 API의 접수번호가 원본 사업보고서와 일치하는지 확인하고 실제 수치를 원문과 대조했다. 동남합성은 CFS `013`을 보존하고 원문 별도 요약의 ‘천원’ 단위를 백만원으로 변환했다. 이 값은 원문 반올림 정밀도를 가진다. 과거 보고서를 현재 비교 재무로 대체하지 않았다. 공식 가이던스·당시 consensus의 적격 archive는 없어 그 두 기준선은 **미채점**이다.

이 전망은 회사 가이던스 복사가 아닌 **선언한 독립 시나리오**지만, 수주·계절성·경쟁 정보가 제한돼 단순 run-rate 부근의 판단적 가정에 가깝다. 완전한 선행 실적 예측 능력을 입증하지 않는다. [최초 채점](../../runtime/task9_historical/evaluation/forecast_scores.json), [추가 채점](../../runtime/task9_historical/evaluation/additional_forecast_scores.json), [평가 전용 원문·계약](../../runtime/task9_historical/evaluator_only/).

## 6. 지수 성과와 실제 미실행 범위

아래는 Yahoo에서 실제 수집한 **가격지수 자체**의 진단이다. 전략 계좌·ETF 체결 수익이 아니며 투자 초과수익 비교표도 아니다. 끝점은 모두 2026-11-13이다. 최초 5y 응답 시작은 2021-11-15이므로 11월 1일부터의 완전한 5년 자료라고 부르지 않는다.

| 관측 시작 | S&P 500 가격 변화 | KOSPI 가격 변화 |
|---|---:|---:|
| 2021-11-30 | +65.57% | +86.35% |
| 2023-11-30 | +65.54% | +108.68% |
| 2024-11-29 | +25.35% | +115.42% |
| 2025-11-28 | +10.40% | +34.74% |
| 2026-05-29 | −0.24% | −37.58% |

2021-11-30 시작 경로의 지수 CAGR은 각각 10.72%/13.39%, MDD는 −25.43%/−44.94%였다. 이는 vendor 가격 경로의 산술 진단이고 공식지수 원문과 모든 행을 독립 대사한 것은 아니다. 2026-05-29 시작은 6개월이 아직 차지 않은 관측 구간이다. 계산 파일에는 관측 기간·RF0/252 가정의 표본 Sharpe도 보존했지만 성숙 6개월 실적으로 표시하지 않는다.

배당을 포함한 TR과 가격지수는 다르다. [S&P 지수 설명](https://www.spglobal.com/spdji/en/indices/equity/sp-500/), [KRX TR 지수 설명](https://eindex.krx.co.kr/contents/GLB/05/0502/0502050600/GLB0502050600.jsp)에 따른 차이를 유지했다. SPY는 S&P 500 자체가 아니고 KODEX 200은 KOSPI 전체가 아니므로 대신 넣지 않았다. [계산 코드](../../experiments/task9_historical/benchmark_diagnostic.py), [지수 원문·수치·gate](../../runtime/task9_historical/evaluation/benchmark_diagnostic.json).

**미실행:** 미국 다섯 시점 독립 기업 발굴, 한국 전체시장 발굴, 대표 실제 적격 체결, A/B/C 누적수익·초과수익, 업종/균등/가치/모멘텀 매매 기준선, 20분기 연속운용, 종목별 손익·교체 기여·현금 기회비용, 노출을 맞춘 실제 포트폴리오 비교. 기록은 `null / BLOCKED_DATA_QUALITY`이며 0% 수익률로 채우지 않았다. [시장×시점별 gate](../../runtime/task9_historical/coverage.json).

기존 QH 리플레이는 배당·분할·상폐 event 처리기가 아니다. 새 얇은 adapter도 **인증된 기업행사 없는 구간만** 기존 계산기로 넘기고 그 밖에는 `BLOCKED_EXECUTION_ACTION_ADAPTER`로 막는다. 자료를 보유했다는 사실과 회계 처리가 구현됐다는 사실을 구분한다. 합성 입력의 매수·매도 성공을 실제 역사 거래로 집계하지 않았다.

## 7. 기능별 실패 원인·증분 가치

| 원인 | 판정 | 확인 근거 / 아직 모르는 것 |
|---|---|---|
| 데이터·시점 | **확인** | 현재 alias≠원문 이름, 달력 인자≠역사 조회, XML 인코딩·목차·scope 문제, 상폐/행사/consensus 공백. 전체 재현 차단의 직접 원인 |
| 기업 발굴 | **제한 확인** | 네 회사 안의 사업·재무 위험과 SPAC/비상장 제외는 관측. 전체 시장에서 유망 기업을 놓쳤는지는 미검증 |
| 미래 실적 예측 | **오차 실측, 일반 우열 미확인** | 일부 Base가 단순 연율화보다 열위. 소표본·판단적 범위·역사 지식 때문에 엔진 한계의 인과 판정은 불가 |
| 가치평가·시장 기대 | **DATA_LIMITATION** | 적격 주가·자본 구조·과거 consensus 부족으로 검증된 기대 주가수익까지 연결 실패 |
| 재평가·촉매·수급 | **UNDETERMINED** | 대표 B는 설명 추가·판단 불변. 전체 흐름·컨센서스 자료와 매매 결과가 없어 효능 판별 불가 |
| 상대 대안·비중·기회비용 | **UNDETERMINED** | C는 같은 후보 순위 유지. 실현 계좌가 없어 선택/비중 효과 분해 불가 |
| 퀀트 연구·비용 | **이번 미실행** | 과거에 적격하게 존재한 신호가 없어 새 알파·IC·비용 성과를 생성하지 않음. Task6 진단은 이전 결과로 유지 |
| 피드백 | **제한 연결 확인** | 단위·기간·원문 접수번호와 단순 기준선 오차를 후속 연구 요청에 전달. 성과에 맞춘 전략/시나리오 변경 없음 |

원본 대비 확인한 추가 가치는 **누출·정체성·회계·미실행 결과를 잘못된 성과로 해석하지 않도록 차단하는 것**이다. 더 높은 투자 수익이나 미래 예측력을 추가했다고 입증하지 못했다. 새 상시 서비스·스케줄러·대규모 프레임워크·전략 탐색을 만들지 않았다.

## 8. Factory·Review·복구·검증

`quant_task3_task9_history`의 별도 `Store/Queue`에 source snapshot, 개선 요청 3건, 실제 실적 오차 복기와 후속 Forward 예측 검증 요청을 저장했다. 한 연구 작업을 실제 claim→평가 기록→`PENDING_EVIDENCE`로 완료하고 후속 job을 생성했다. 이는 **사후 결과 복기**이며 결과를 숨긴 당시 과정 복기를 새로 했다고 표현하지 않는다.

공식 Factory의 source-integrity 제안은 `BLOCKED_REGISTRATION: Factory daily proposal budget exhausted`다. 기존 Task5~8b 대기·등록 작업을 우회하지 않았으며 실험 예약·실행·승격을 하지 않았다. 제안은 최소 12개 독립 원문의 과정 진단이고 투자 알파 검증을 대신하지 않는다. [정식 등록 시도](../../runtime/task9_historical/factory_handoff.json), [후속 연결](../../runtime/task9_historical/review_cycle.json), [DB 기록](../../runtime/task9_historical/research_records_final.jsonl).

모델 trace에는 실제 프롬프트·호출·usage·실패와 출력이 있다. representative 303,592 / five_dates 288,209 토큰, 합계 591,801이다. 금액 비용은 확인 불가이며 별도 유료 API를 사용하지 않았다. 문맥 크기 거부는 원래 요청과 로그를 보존한 뒤 새 V2 입력으로 재시도했다. 단계별 사전 예산 안에서 실행했으며 rolling 예산은 활성화하지 않았다.

8개 결과의 인용 **102/102개가 원문에서 문자 그대로 발견**됐다. 이는 숫자의 의미·기간·단위·인과 관계가 모두 맞다는 인증이나 오탐률 0%가 아니다. [출처 감사](../../runtime/task9_historical/evaluation/provenance_audit.json), [모델 사용량](../../runtime/task9_historical/model_usage.json).

| 시험 | 실제 결과 |
|---|---|
| 신규 source cutoff·정정·단위·기간·봉인·미성숙·gate 및 기존 리플레이 매수/매도·행사 차단 | **13 PASS**, [log](../../runtime/task9_historical/evidence/contract_tests_final.log) |
| AGENTS 필수 안전 4개 파일 | **24 PASS**, [log](../../runtime/task9_historical/evidence/mandatory_tests.log) |
| src/scripts/tests 및 실험 Python 컴파일 | 완료 결과는 `evidence/compile_final.log`에 보존 |
| 기존 Paper·Forward | 운영 소스·정책 변경 없음, 기존 timer 유지. 역사 수익을 Forward로 append하지 않음 |
| 재시작 | 새 프로세스에서 불변 DB payload/hash·queue 상태 확인. 실제 서버 재부팅은 미실행 |
| 연구 보존 | 개별 응답·원문·봉인·코드 버전·PostgreSQL dump 보존. 새 Task9 DB의 정기 백업 편입은 별도 후속 과제 |

재현 순서:

```bash
# 기존 원문을 우선 재사용. 새 수집은 계약의 호출 예산 내에서만.
.venv/bin/python experiments/task9_historical/collect_public.py
.venv/bin/python experiments/task9_historical/collect_dart_lists.py
.venv/bin/python experiments/task9_historical/collect_originals.py
.venv/bin/python experiments/task9_historical/reparse_originals.py
.venv/bin/python experiments/task9_historical/benchmark_diagnostic.py
PYTHONPATH=src:experiments/task9_historical PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
 .venv/bin/python -m pytest -rA experiments/task9_historical/test_contract.py
.venv/bin/python experiments/task9_historical/score_forecasts.py
.venv/bin/python experiments/task9_historical/score_additional.py
.venv/bin/python experiments/task9_historical/audit_results.py
```

모델 호출은 기존 결과가 있으면 재생성하지 않는다. `run_model.sh`·relay·준비 스크립트와 최초 입력을 보존했다. Factory 등록/Queue 처리는 단순 읽기 재현이 아니므로 무의미하게 반복하지 않는다. 모든 신규 파일은 [experiments/task9_historical](../../experiments/task9_historical/), 진행·중단 복구는 [09_historical_progress](09_historical_progress.md)에 있다.

## 9. 후속 Task 9의 우선순위

1. **source·identity·행사 회계가 먼저다.** 무료·적법한 원본 접근, 원문 종목 코드·상장구간·상폐·거래정지·정정·공식 세션을 재현 가능하게 확보한다. 확보되면 한 시점의 적격 매매를 먼저 완결한다. 불가능하면 광범위한 과거 알파 주장 대신 독립 Forward를 우선한다.
2. **추출 품질과 완전한 회사 분석을 분리 평가한다.** Vibe financial facts에 실제 본문·단위·기간·연결/별도·청구권을 연결하고, 12개 독립 원문의 과정 진단을 정상 Factory 순서로 수행한다. XML 경고나 목차 추출을 성공 보고서로 세지 않는다.
3. **새 Forward 실적 예측을 봉인한다.** 기존 3개 과거 사례를 튜닝하지 않고 새 기업·분기의 매출·영업이익·FCF와 가정·가이던스/consensus 출처를 기록한다. 단순 연율화보다 나은지 먼저 평가하고 이후 주가·가치평가를 분리 평가한다.
4. **A/B/C 투자 효능은 아직 판단하지 않는다.** 같은 적격 데이터·가격·비용·위험·노출에서 비현금 판단과 체결이 가능해진 뒤 비교한다. 그 전에는 설명의 증가를 투자 우위로 승격하지 않는다.
5. 대표 완전 재현이 통과한 뒤 다섯 시점·20분기로 확장한다. 지금의 불완전 입력을 반복하는 대량 LLM 연구는 자료 결함과 역사 기억 편향을 늘릴 수 있어 실행하지 않았다.

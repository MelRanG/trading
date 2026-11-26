# Task13-F1-R1 — 개별종목 수급 원천 복구

**`ACCESS_REQUIRES_USER_ACTION`.** 실제로 확인한 역사 자료는 Toss의 삼성전자 2024년 4월 거래량 21세션이다. FLOW5의 원화 대금 계약을 충족한 행은 **0종목·0세션**이다. 세 종목 확대와 F1 비용 후 비교는 보류됐고, 기존 단일 평가 예산은 사용하지 않았다. [접근 및 적격성 원장](../../runtime/task13_f1_r1/verification.json)

| 경로 | 실제 확인 | 미확인 또는 차단 |
|---|---|---|
| **A. KRX** | 기존 데이터 POST는 비로그인에서 HTTP 403 오류 HTML이었다. 이번 공개 랜딩 GET도 HTTP 403이었다. 보존된 공식 조회 화면에서 일별 추이·거래대금·순매수 옵션과 원 단위를 확인했다. 현재 화면 탭의 일별 원화 조회 식별자는 `MDCSTAT02302_OUT`이고 기존 시험은 `MDCSTAT02302`였다. | 서버에 정식 KRX 계정 연결이나 로그인 세션이 없다. 정확한 403 원인은 확정할 수 없으며 로그인 적용 개시일과 인증 후 재현은 미검증이다. 다른 화면 식별자를 써서 비로그인 데이터 POST를 반복하지 않았다. |
| **B. KIS** | 공식 예제 HTTP 200. `FHPTJ04160001`, `FID_COND_MRKT_DIV_CODE=J`로 KRX 지정, 기준일 파라미터와 `tr_cont` 연속조회를 확인했다. 일별 응답 매핑은 `stck_bsop_date`, `frgn_ntby_tr_pbmn`, `orgn_ntby_tr_pbmn`, `acml_tr_pbmn`과 외국인·기관별 매수·매도 대금을 정의한다. | 기존 자격증명이 없어 인증 호출은 실행하지 않았다. 실제 2024년 4월 응답, 금액 스케일, 페이지 크기, 2022~25년 최장 조회는 미확인이다. |
| **C. 키움** | 두 공식 명세 HTTP 200. `ka10059`·`ka10060`는 일자 및 연속조회 키를 지원한다. KRX 종목코드, 금액 모드 `amt_qty_tp=1`, 순매수 `trde_tp=0`에서 외국인·기관 순매수 및 전체 누적 거래대금이 **백만원** 단위다. | 기존 자격증명이 없어 인증 호출은 실행하지 않았다. 당시 값·외국인 합계 범위·최장 조회·정정 이력은 미확인이다. |
| **D. 공식 다운로드·보유 파일** | KRX 기존 drop zone과 프로젝트 자료에서 해당 원본 CSV를 찾지 못했다. KRX Open API 공개 목록에는 별도 종목×투자자 이력 API가 확인되지 않았다. 코스콤 카탈로그는 일별 종목별 투자자 매매동향 상품을 안내한다. | KRX 정상 다운로드에 필요한 세션과 코스콤 상품 이용권을 확인하지 못했다. 새 계정이나 계약을 개설하지 않았다. |
| **기존 Toss 단일 실조회** | OAuth와 시세 GET 모두 HTTP 200. 삼성전자 기준일 2024-04-30으로 30행을 내려받아 4월의 21행 전부를 R0 적격 거래일에 조인했다. 외국인·기관 각각의 매수주수−매도주수=순매수주수 42건이 일치했다. | 실응답에는 원화 순매수대금이 없다. 명세상 외국인은 등록외국인, 거래 범위는 KRX·NXT 통합 기준이다. 전체 거래대금 분모와 동일 범위의 원화 분자를 확정할 수 없다. |

[KRX 공식 화면](https://data.krx.co.kr/contents/MDC/MDI/outerLoader/index.cmd?screenId=MDCSTAT023) · [KRX 이용약관](https://data.krx.co.kr/contents/MDC/INFO/informationController/MDCINFO003.cmd) · [KRX 공개 API 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd) · [KIS 공식 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/investor_trade_by_stock_daily/investor_trade_by_stock_daily.py) · [KIS 응답 매핑](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/investor_trade_by_stock_daily/chk_investor_trade_by_stock_daily.py) · [키움 ka10059](https://openapi.kiwoom.com/m/guide/apiguide/01/ka10059) · [키움 ka10060](https://openapi.kiwoom.com/m/guide/apiguide/07/ka10060) · [코스콤 공식 카탈로그](https://datamall.koscom.co.kr/kor/main.do) · [Toss 조회 증거](../../runtime/task13_f1_r1/toss_probe.json)

## 가장 작은 재개 조건

**KRX에 정상 로그인해 2024-04-01~04-30의 삼성전자(005930)·POSCO홀딩스(005490)·에코프로비엠(247540) 자료를 공식 CSV로 제공**하면 첫 적격성 관문을 재개할 수 있다. 조회 화면에서 각 종목을 **일별 추이 → 거래대금 → 원**으로 조회한다. **순매수** 보기의 외국인·기관 합계와 **매수** 보기의 전체 거래대금이 함께 필요하다. 전체 순매수는 분모로 쓸 수 없다. 같은 날짜의 매도 보기 소표본과 다운로드 시각을 함께 보존하면 부호·합계 대사에 쓸 수 있다. 대안은 이 서버에 기존 KIS 또는 키움의 시세 조회 인증을 안전한 설정 경로로 연결하는 것이다. 세 종목 한 달은 파일럿 범위다. 실평가는 품질을 통과한 확대 패널에서 기존 FLOW5·t+2·H5·50:50 계약으로 1회 수행한다. [기존 F1 연구 조건](13_F1_stock_investor_flow.md)

## 실행과 보존

Python 외부 요청 8회는 공식 문서·랜딩 6회, Toss OAuth 1회, 종목 시세 1회다. 공개 웹 문서 조회는 별도로 수행했다. 시세 응답 원본 36,713바이트와 SHA를 보존했고 OAuth 응답 원문은 저장하지 않았다. 기존 F1 파일 15개 해시를 재검증했다. 연구 수치 평가·외부 가격 조회·연구 LLM 호출·주문 요청은 0회다. 계측된 Toss/로컬 검사 CPU 약 0.09초, 격리 안전 검사 CPU 3.42초였다. 문서 조회 CPU와 Codex 세션 토큰은 별도 계측값이 없다. compileall 및 필수 회귀 24건을 통과했다. 운영 경로에 대한 쓰기는 없었다. [요청 기록](../../runtime/task13_f1_r1/public_document_receipts.json) · [키움 명세 요청 기록](../../runtime/task13_f1_r1/kiwoom_documents.jsonl) · [안전 회귀](../../runtime/task13_f1_r1/safety_validation.json)

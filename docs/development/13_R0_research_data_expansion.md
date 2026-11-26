# Task13-R0 — 퀀트 연구 데이터 확장 및 엔진 입력 준비

작성: 2026-11-16. **최종 판정: `PARTIAL_RESEARCH_READY`.** 미국 **176개**, 한국 **126개(핵심119 + 별도 중소형7)**의 마스킹된 장기 조정 OHLCV에서 네이티브 엔진 연구를 시작할 입력을 확보했다. 최초 데이터는 2017년, 최종 관측은 2026-11-13이다. 모든 종목이 전 기간을 갖는 균형 패널은 아니다. H60의 유효 학습 자료도 확보했다.

현재 시총·펀드 구성·상장기업에서 출발한 **`SURVIVOR_RESEARCH`**다. 역사적 전 시장 구성, 상장폐지, 기업행사 및 실제 원가격 체결 기준을 충분히 복원한 PIT B 패널은 아니다. 이번 결과는 데이터·입력 준비이며 알파 예측력, 경제성, 독립 Holdout 성공을 뜻하지 않는다. 다음 Quanta/RD 연구는 자동 실행하지 않았다.

## 1. 재사용 경로와 변경 범위

Task11~14 보고서, Task12 평가·국면 계약, Task13 실제 입력·실행 환경, Task14 후보 중복·소표본 문제를 먼저 확인했다. 기존 322개 source receipt를 조사했고, 기존 5년 Yahoo 자료와 가격 기준이 혼재한 레거시 CSV를 보존했다. 레거시 `data/all_prices_long_v62_9_expanded.csv`의 68종목 자료는 원본 hash와 범위를 [별도 감사](../../runtime/task13_r0/legacy_csv_audit.json)에 남겼으며 새 조정 패널에 병합하지 않았다. 기존 성공분을 삭제·덮어쓰기 하지 않았다. 새 요청은 긴 기간 또는 새 연구 대상에 한정했다.

기존 `quant_harness.investment.equities.fetch/normalize_chart`, `TossOpenApiClient`, V87 `_validate_batch/_revision_audit`, Task12 `readiness.regimes`, Task13의 인과적 특징량 정의를 재사용했다. 추가 코드는 [experiments/task13_r0](../../experiments/task13_r0/)의 배치·검증·얇은 입력 adapter다. `src/`, 기존 수집기 계약, Factory·Paper·팀2·Champion·Live·Forward 모델은 변경하지 않았다. 신규 DB·서비스·설치·LLM 연구·모델 학습은 없다.

[동결 핵심 계약](../../runtime/task13_r0/contract.json), [유니버스](../../runtime/task13_r0/universe.json), [기존 자료 조사](../../runtime/task13_r0/existing_sources.json), [입력 접근 계약](../../runtime/task13_r0/native_input_contract.json)이 재현의 기준이다.

## 2. 실제 출처와 사용 조건

- 가격: 기존 Yahoo chart 수집 경로, `2017-01-01 <= session <= 2026-11-13`, 일봉 OHLCV 및 provider 배당·분할 이벤트. 원문·HTTP 수집 시각·SHA-256을 보존했다. [Yahoo 조정종가 설명](https://help.yahoo.com/kb/SLN28256.html)은 분할·배당 조정을 설명하지만 이 데이터의 모든 기업행사·체결 원가격을 독립 인증하지는 않는다.
- 미국 후보: 기존 Nasdaq 현재 종목 디렉터리 재사용, iShares IVV/IJH의 공식 현재 holdings에서 common stock·산업 분산 표본. Nasdaq 목록은 [현재 거래일 기준](https://www.nasdaqtrader.com/trader.aspx?id=symbollookup)이며 과거 구성 자료가 아니다. 대형/중형은 펀드 소속 proxy로 실제 역사 시총 계층이 아니다.
- 한국 후보: KRX KIND 현재 상장표(KOSPI829/KOSDAQ1833)와 Toss 공식 bulk stock info/prices. 현재 가격×현재 주식수로 시총 범주를 구성했다. 이는 현재 메타데이터 점검이며 전종목 장기 가격 수집이 아니다.
- 유동성: Toss 공식 `MARKET_TRADING_AMOUNT` 1개월 상위100의 실제 거래대금과, 수집 후 최근60일 `Yahoo quote close × volume` proxy를 구분했다. 이 proxy를 실제 시장 체결 거래대금으로 표시하지 않는다.
- Toss 공식 [API 명세](https://openapi.tossinvest.com/openapi-docs/latest/openapi.json)와 [사용 조건](https://home.tossinvest.com/ko/terms/v2?id=752)을 확인했다. 등록된 기존 인증만 사용했으며 새 계정·결제·우회는 없었다. 구체적 권한·쿼터는 서비스·계정별이므로 보편적인 무료 한도를 가정하지 않았다. `MARKET_DATA_CHART`와 일반 market-data 권한도 동일하다고 가정하지 않았다.
- 공식 [KRX OPEN API](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd)는 인증·서비스 승인 경계가 있다. 이 실행 환경의 KRX key 변수는 확인되지 않았으며 새 승인을 신청하지 않았다. 기존 공식 자료 접근 제약을 이유로 비공식 우회를 추가하지 않았다.

최초 iShares CSV 주소가 HTML을 반환해 공식 페이지의 변경된 `latest-holdings.csv` 링크를 사용했다. Naver 시총 페이지는 JS 응답으로 표 파싱에 실패해 오류를 보존하고 공식 Toss bulk metadata로 전환했다. 이 실패를 수집 성공으로 집계하지 않았다. [최초 스키마 실패](../../runtime/task13_r0/metadata_initial_schema_failures.json), [메타데이터 근거](../../runtime/task13_r0/universe_metadata.json), [Toss 근거](../../runtime/task13_r0/toss_universe_metadata.json)를 참조한다.

## 3. 한국 시총 기준 재검토와 별도 연구군

사용자 추가 지시에 따라 **5,000억원 이상 핵심군을 유지**하고, **1,000억~5,000억원을 별도 연구군**으로 추가했다. 실제 매매 적격 종목을 확정하는 작업이 아니므로 작은 기업을 시총만으로 연구 전에 일괄 배제하지 않는 것이 목적이다. 시총 하한을 계속 낮추거나 목표 수를 맞추는 방식은 사용하지 않았다.

핵심 유니버스 한국120개(KOSPI70/KOSDAQ50)는 그대로 보존했다. 중소형은 기존 현재 메타데이터의 KOSPI290/KOSDAQ502 후보에서 최대20개, 시장별 최대10개만 단계적으로 조사했다. 실제 월간 거래대금이 확인된 후보를 먼저 두고 나머지는 산업 분산 표본으로 **수집을 위한 staging**만 수행했다. 실제 상위100 거래대금과 이 시총대의 교집합은 1개뿐이므로 나머지의 유동성이 사전 확인됐다고 주장하지 않는다.

다운로드 전 [별도 계약](../../runtime/task13_r0/smallcap_contract.json)을 봉인했다. 저장 후 연구 입력 편입 조건은 유효 이력500세션 이상, 최근60세션 중55개 이상 유효, 거래대금 proxy의 최근60일 중앙값 **5억원/일 이상**, 하위10% **1억원/일 이상**이다. 거래대금과 데이터 품질을 함께 사용했다. 현재 값으로 역사적 편입·제외를 재현한 것은 아니다.

| 구분 | 동결 수집 대상 | 구조 검사 후 저장 | 최종 연구 입력 |
|---|---:|---:|---:|
| 미국 핵심 | 180 | 180 | 176 |
| 한국 핵심 ≥5,000억원 | 120 | 119 | 119 |
| 한국 별도 1,000억~5,000억원 | 20 | 18 | 7 |

별도군 최종7개는 **알멕(354320), KBI메탈(024840), 포스코엠텍(009520), 하이록코리아(013030), 남선알미늄(008350), KG스틸(016380), 금호건설(002990)**이다. 이는 투자 추천이나 우수 알파 선정이 아니다. 개별 거래대금 proxy와 탈락 이유는 [admission 결과](../../runtime/task13_r0/smallcap_admission.json)에 있다. 저장된 나머지11개는 유동성·이력 미달로 입력에서 제외했다. 실패·탈락한 자리를 다른 종목으로 채우지 않았다. 초기 시장 편중 표본안도 다운로드 전에 양시장 최대10개로 교정했고 초안은 기록으로 보존했다.

핵심군에도 동일한 최근 유동성 진단값을 기록했다. 핵심의 쿠쿠홈시스(284740)는 최근60일 중앙 거래대금 proxy 약3.13억원으로 별도군의 5억원 조건 미달이다. 핵심군에는 이 조건을 소급 강제하지 않았으며 연구 가능성과 거래 적격성을 구분했다. 실행 경제성 단계에서는 종목·날짜별 실제 유동성·참여율 검증이 추가로 필요하다.

별도군7개만으로는 최소8종목 횡단면 진단 기준을 충족하지 못한다. 한국 통합 입력에서는 cohort를 별도 평가자 매핑으로 보존하며, 작은 군을 독립적인 충분한 횡단면으로 표현하지 않는다.

## 4. 성공·실패·품질 및 PIT 경계

핵심 한국 `491000.KQ`, 별도군 `179880.KQ`는 구조적으로 유효한 이력이500일 미만, 별도군 `377460.KQ`는 Yahoo404로 실패했다. 미국 PLTR·HLT·KMB·SGI는 저장은 성공했으나 현재 문서상 listing/가능한 시장 이전 경계를 보수적으로 적용한 뒤 각각493·7·368·439개 유효 세션만 남아 연구 입력에서 제외했다. 현재 listDate가 IPO인지 이전인지 완전한 역사적 정체성으로 해석할 수 없어서 기존 장기 가격을 추정 연결하지 않았다. 이 보수적 기준이 실제 계속 상장 이력을 과소인정할 수 있다는 제한도 남긴다.

구조적으로 저장한 주식317개의 관측행은733,247개다. 이력 내부의 지수 관측 세션 대비 누락은321개, 조정종가 일변화 절댓값35% 초과46개, 거래량0은3,343개다. 이 통계는 이슈별 중복 가능성이 있으며 모두 가격 오류라는 뜻이 아니다. 정상 급등락·거래정지 여부가 확인되지 않은 행은 `UNVERIFIED`로 마스킹했으며 삭제·보간·가격 보정하지 않았다. 원문에 기록된 분할124건·배당6,273건도 공급자 주장으로 보존했으며 독립 인증 건수가 아니다. [coverage 자산별 결과](../../runtime/task13_r0/coverage.json), `accepted/{market}/{symbol}/quality.json`, `quality_mask.csv`가 상세 근거다.

검증은 종목·통화·날짜 중복, 양수 가격, OHLC 관계, volume 음수, 범위 밖 날짜, 원본 정체성, 현재 문서상 상장 경계, 원본 hash, V87 구조·revision gate를 사용했다. 변경 원본은 revision fail-closed이며, 결측 날짜는 지수 관측 세션에 재정렬해 NaN으로 유지한다. 종목별 유효성+과거63개 연속 유효 세션+미래 label 전체 경로 유효성을 함께 적용한다. `quality.json`의 초기 관측 수보다 최종 `native_eligibility.csv`와 coverage의 값이 연구 적격 수의 권위다.

자료별 수준은 다음과 같다.

| 자료/검증 | 수준 및 의미 |
|---|---|
| 보존한 행의 수치·OHLC 구조·hash | 해당 검사 범위 `VERIFIED` |
| 장기 OHLCV·조정계수·거래량·기업행사 | `PARTIAL`, 연구용 |
| 현재 종목·ISIN·산업·시총·상장일 | 현재 메타데이터이며 역사 구성의 증거가 아님 |
| 역사적 전체 상장·상폐·티커 변경 tape | `UNVERIFIED` |
| 과거 최초 관측시각·수정 전 vintage | `UNVERIFIED`; 이번은 현재 backfill |
| 미래 label 경계·결측 마스크 | 실제 계산·시험으로 검사, 독립성 주장은 별도 |

Toss에서 미국 NYSE45/NASDAQ104개 상폐 메타데이터를 찾았다. 그러나 사전 지정한5개(HARP/NBSE/MACK/ERF/NSS)의 Yahoo 역사는 모두404였다. 이149개를 실제 확보한 상폐 가격이나 학습 종목에 포함하지 않았다. 한국 상폐 조회0건도 역사 상폐가 없다는 뜻이 아니다. [상폐 시험](../../runtime/task13_r0/delisted_result.json)과 [정체성 근거](../../runtime/task13_r0/extra_identity.json)를 보존했다.

`quote.csv`는 Yahoo provider quote이며 분할 조정이 포함될 수 있어 인증된 명목 체결가격이 아니다. `adjusted.csv`는 기존 normalizer의 `adjclose/quoteclose`를 OHLC 전체에 적용하고 거래량은 공급자 값을 유지했다. 알려진 분할 당일은 가격·거래량 기준의 불확실성 때문에 보수적으로 제외한다. 다른 날짜의 기업행사·거래량 정합성이 완전히 해결됐다는 뜻은 아니다. 배당조정 가격과 현금배당을 동시에 더하지 않으며 이번에는 투자 수익률·체결 원장을 만들지 않았다.

## 5. 학습·검증 자료와 국면 coverage

가격을 무단 연결하지 않고 새 조정 연구 track으로 분리했다. Fit은2017~2022, validation 신호는2023-04-03 이후이며 label 종료는2024-12-31 이하다. 2025~2026은 이미 노출된 평가·진단 자료다. 2017~2024 역시 새로 받았다는 이유로 미노출 독립 Holdout이 되지 않는다.

H는 t일 종가 이후 신호, t+1일 open 진입, t+H+1일 open 종료의 H거래일 수익이다. Task12 기본 warmup63을 줄이지 않았으며 마지막 fit label도2022년 말 이전에 성숙해야 한다. 60세션보다 긴 fit/validation 간격과 split 밖 label 제거를 유지했다. 기업행사·결측 구간을 뛰어넘는 label은 만들지 않았다.

| 연구군 | H | Fit 종목×날짜 | Fit 날짜(8종목 이상) | Validation 종목×날짜 | Validation 날짜(8종목 이상) |
|---|---:|---:|---:|---:|---:|
| US_CORE | 5 | 225,996 | 1441 | 74,280 | 434 |
| US_CORE | 20 | 222,956 | 1426 | 71,525 | 419 |
| US_CORE | 60 | 214,932 | 1386 | 64,211 | 379 |
| KR_CORE | 5 | 112,520 | 1173 | 41,104 | 421 |
| KR_CORE | 20 | 105,871 | 1113 | 38,156 | 406 |
| KR_CORE | 60 | 88,902 | 953 | 30,409 | 366 |
| KR_SMALLER | 5 | 6,690 | 0 | 2,491 | 0 |
| KR_SMALLER | 20 | 6,285 | 0 | 2,341 | 0 |
| KR_SMALLER | 60 | 5,231 | 0 | 1,941 | 0 |

미국 핵심 유효 종목×세션409,521개, 한국 핵심257,950개, 별도 중소형15,171개다. 종목×날짜 수를 독립 사례 수로 사용하지 않는다. H60 fit 날짜 산술 환산은 미국 약23개·한국 날짜 전체 약17개 60일 블록에 불과하며, 이 값도 유효 독립 표본량의 추정치가 아니다. Validation의 H60 약6개 블록 역시 통계적 확증에 충분하다고 선언하지 않는다.

| 연도 | 미국 유효 이름 중앙값 | 한국 핵심 중앙값 | 한국 핵심 날짜/50개 이상 날짜 |
|---|---:|---:|---:|
| 2018 | 155.0 | 96.0 | 244/244 |
| 2020 | 162.0 | 101.0 | 248/246 |
| 2022 | 168.0 | 114.0 | 244/233 |
| 2026 | 176.0 | 119.0 | 212/212 |

2018·2020·2022·2026년에 지수뿐 아니라 실제 종목 자료가 있다. 다만 한국2020년 최소12개, 2022년 최소1개까지 줄어드는 날짜가 있어 전 날짜를 폭넓은 횡단면으로 간주하면 안 된다. 공급자 index 세션과 종목 자료 불일치는 독립 공식 달력·상장상태 대사가 남은 이슈이며, 임의로 휴장일이나 거래정지로 판정하지 않았다.

Task12의 동결 국면 함수를 그대로 적용했다. 지수 입력을2017년부터 확장했으며 `AS_OF_REGIME`은 과거 가격만, `EX_POST_REGIME`은 평가에만 쓴다. 기존 Task12 국면 파일은 수정하지 않았다. 아래는 누적 세션 수이며 서로 독립인 경제 episode 수가 아니다.

| AS_OF 국면 | 미국 날짜 / 유효 이름 중앙값 | 한국 핵심 날짜 / 중앙값 |
|---|---:|---:|
| UP | 319 / 166.0 | 444 / 118.0 |
| DOWN | 98 / 161.0 | 153 / 114.0 |
| CRASH | 11 / 160.0 | 29 / 119.0 |
| REBOUND | 14 / 161.0 | 28 / 119.0 |
| SIDEWAYS | 1057 / 168.0 | 880 / 110.0 |
| TRANSITION | 857 / 167.0 | 755 / 110.0 |

각 시장 초기125세션은 국면 WARMUP이다. 고변동성·EX_POST·연도별 종목 수는 `coverage.json` 및 `US/KOSPI/KOSDAQ_regimes.csv`에 있다. 한국 통합군의 요약 국면은 KOSPI 기준이며 KOSDAQ 자체 경로도 별도 저장했다. 달력은 미국2,481개, KOSPI/KOSDAQ 각2,414개의 공급자 지수 관측 세션이다. Toss 공식 현재3세션 일정도 확인했지만2017~2026 전체 거래소 달력의 독립 인증으로 대체하지 않았다.

## 6. 엔진 입력과 실제 실행 수준

기존 고정 checkout·가상환경·Docker 이미지를 재사용했다. 원본 커밋은 [resources](../../runtime/task13_r0/resources.json)에 있다: Vibe `0025531f005d4a7aac3fb884cda2fba9318e7158`, Quanta `b7ceb27b1001261d7a95b209a963664ae1f8ab23`, RD `484776c211e4fbbeef03e0ec00d6bbee7362a4f4`.

공유 train-only HDF는 미국176개/265,760행, 한국126개/185,346행이다. NaN 마스크를 유지했으며 모두 값이 유효한 OHLCV 행은 각각240,143/156,094개다. 미국 마지막 세션2022-12-30, 한국2022-12-29이며 미래 label·현재 시총·현재 업종을 컬럼으로 넣지 않았다. 실제 종목코드는 alias로 바꾸고 cohort/원본 매핑은 신뢰된 평가자 측 파일에 보존했다. [inputs.json](../../runtime/task13_r0/native/inputs.json)이 파일 hash를 고정한다.

| 엔진 | 이번 실제 실행 | 하지 않은 일/남은 일 |
|---|---|---|
| Qlib | `DatasetH.prepare` 호환 adapter, feature/label 계층 입력, Ridge 객체 생성 | 모델 fit·예측 경제성 평가 없음 |
| RD-Agent | 원본 model proposal·CoSTEER model coder import, Qlib용 H5/H20/H60 supervised 입력 | fin_factor/fin_model/fin_quant 전체 controller·학습·공동 연구 실행 아님 |
| QuantaAlpha | 원본 `DELAY/RANK` DSL로 알려진 고정 입력 fixture 계산, EvolutionController import 가능 | 신규 가설·planner·mutation/crossover·feedback 실행 없음 |
| Vibe | 원본 registry의 `qlib158_roc20`, `qlib158_std20`을 양시장 train 자료에서 실제 계산 | 478개 전부 평가·성과 순위·새 알파 생성 없음 |

[원본 ABI probe](../../runtime/task13_r0/native/probe.json), [Quanta probe](../../runtime/task13_r0/native/quanta_probe.json), `native_probe.log`, `native_quanta.log`가 근거다. 알려진 대표 수식 계산은 입력 적격성 시험이며 새 연구 시도·알파로 집계하지 않는다. RD import 성공을 새 모델의 학습 성공이라고 표현하지 않는다.

[loader.py](../../experiments/task13_r0/loader.py)는 기존 Task13의 ret1/mom20/mom60/vol20/relative-volume20 입력을 사용한다. H5/H20/H60 각각 실제 feature/label frame을 만들고 Qlib 형태로 전달했다. 미국 유효 supervised 행은225,996/222,956/214,932개, 한국 통합119,210/112,156/94,133개다. 마지막 목표일은 모두2022년 말 이전이며 정규화 fit은 수행하지 않았다. 모델 복잡도·경제 메커니즘·특징량 연구는 다음 작업에서 별도 사전등록해야 한다.

**접근 경계:** 이번 `run_inputs.py`는 네트워크가 차단된 신뢰된 ABI 검사로 프로젝트를 읽는다. 이를 실제 연구 worker의 미래 정보 차단 환경으로 주장하지 않는다. 후속 연구자는 선택한 `*_train.h5` **파일만** mount해야 한다. 전체 `/repo`, `native/` 디렉터리, private mapping, current cap/sector, accepted 전체 자료, coverage·평가 결과를 주면 안 된다. validation HDF는 미생성이고 검증된 immutable source reference만 준비했다. 신뢰된 평가자가2024년 말 cutoff·warmup·성숙 label로 별도 구성해야 한다. 별도 연구자의 실제 sandbox 검증은 후속 연구 시작 조건이다. [입력 계약](../../runtime/task13_r0/native_input_contract.json)에 이 제한을 명시했다.

## 7. 자동 수집·재개·시험 증거

Python 직렬 수집, 요청 간1초, 최대3회 유한 backoff, 전체500 application HTTP 시도 상한을 사용했다. 25개 배치마다 checkpoint를 기록했다. 성공 원본은 URL receipt와 hash로 재사용한다. 401/403/429는 circuit, 영구400/404/410/422는 동일 동결 run에서 재호출하지 않는다. 공통 schema/identity 오류가 연속3개면 전체 확장을 멈추며 단일 종목의 실패는 격리한다. 정상 행 CSV는 임시파일 후 rename하고 원문은 남긴다. source revision 불일치는 gate에서 거절한다. [network.py](../../experiments/task13_r0/network.py), [collect.py](../../experiments/task13_r0/collect.py), [quality.py](../../experiments/task13_r0/quality.py)를 참조한다.

[초기 확장 기록](../../runtime/task13_r0/expand_collection.json), [별도군 기록](../../runtime/task13_r0/small_collection.json), [pilot gate](../../runtime/task13_r0/pilot_quality_gate.json)을 보존했다. 최초 미국5/한국5개를 통과한 뒤 확장했다. 대표 원문 검사의 개선은 저장 원문에서 수행했으며 재다운로드하지 않았다. 핵심300+별도20 재실행 시험은 성공317개 그대로 재사용·실패3개 캐시 재확인·**추가 HTTP0회**, 기존 quality hash 불변이었다. [resume_audit.json](../../runtime/task13_r0/resume_audit.json)이 근거다. 실제 수집 프로세스를 강제 kill하지는 않았으며 강제 중단 시점별 모든 복구 상황을 시험했다고 주장하지 않는다.

신규 검사3개는 실제 원문의 중복·정체성·OHLC/조정식 검증, 캐시 무결성·영구 실패 재호출 차단, next-open label·warmup·결측 경로·미래 교란 불변성을 확인했다. **3개 통과**, AGENTS 필수4 suite **24개 통과**, compileall 정상이다. 운영 경로 변경이 없어 추가 운영 suite와 V104 Forward 명령은 재실행하지 않았다. 실제 다음 거래 세션·Forward 성과를 이 시험으로 대신하지 않았다.

초기 검증에서 시스템 `python` 명령 부재로 패치가 실행되지 않아 영구404 캐시 시험1개가 실패했다. `.venv/bin/python`으로 패치를 적용한 뒤 재시험 통과했으며 [초기 실패](../../runtime/task13_r0/tests_initial_failure.log)를 보존했다. 스키마 변경·Naver·상폐404·짧은 이력 실패도 성공 건수에 합산하지 않았다.

```bash
# 기존 성공 원본 재사용; 현재 동결 run의 영구 오류는 새 요청하지 않음
PYTHONPATH=src .venv/bin/python experiments/task13_r0/collect.py expand
PYTHONPATH=src .venv/bin/python experiments/task13_r0/collect.py small
.venv/bin/python experiments/task13_r0/coverage.py
.venv/bin/python experiments/task13_r0/run_inputs.py build
.venv/bin/python experiments/task13_r0/run_inputs.py probe
.venv/bin/python experiments/task13_r0/run_inputs.py quanta
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q experiments/task13_r0/tests
.venv/bin/python -m compileall -q src scripts tests experiments/task13_r0
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q \
  tests/test_v104_end_to_end_causal_challenger_audit.py \
  tests/test_v104_2_jul30_crash_bridge.py \
  tests/test_v84_dual_paper_parity.py \
  tests/test_v89_forward_governance.py
.venv/bin/python experiments/task13_r0/final_audit.py
```

자료는 이미 생성돼 있다. 위 명령은 재현용이며 원본 build를 반복할 필요는 없다. 후속 연구 전에 최초 계약·현재 source hashes·캐시 상태를 먼저 확인한다.

## 8. 요청량·저장량·보존 감사

실제 application HTTP 시도는 **383/500**이다: data328, universe metadata8, provider documentation2, Toss bulk metadata41, OAuth4. wire redirect는 별도 계측하지 않았으며 요청 예약 수를 성공 응답 수로 표현하지 않는다. 가격·정체성·요청 실패도 원장에 포함한다. 한 종목마다 모델을 부르거나 오류를 재질문한 적이 없다.

**연구 LLM 호출0·연구 LLM 토큰0·모델 학습0.** 이 코딩 대화 자체의 토큰은 별도 측정하지 않았으므로 전체 Codex 사용량0이라는 뜻은 아니다. 누적 CPU는 세션 계측기가 없어 정밀 산출하지 않았고 ABI Docker를 CPU2/메모리4GiB/network-none으로 제한했다. 유료 데이터·API 구매는 없다.

최종 보고서 전 스냅샷은 파일3,085개, 논리424,541,632bytes(약405MiB), inode 중복 제거 실제 할당432,164,864bytes(약412MiB)였다. 공유 train HDF 두 개는23,316,702bytes다. 원문과 quote/adjusted/V87 reference/마스크·현재 메타데이터는 서로 다른 보존·검증 목적을 갖는다. 과거 모델·DB 복사본은 만들지 않았으며 평가용 중간 가격을 매 엔진별 전체 복제하지 않았다. 최종 파일별 목록·hash는 [manifest](../../runtime/task13_r0/artifact_manifest.json), 자원 스냅샷은 [resources](../../runtime/task13_r0/resources.json)에 있다.

신규 source/output/input hash **2,194개 검사 모두 일치**. 기존 Task12 69개, Task13 435개, Task14 36개 manifest도 모두 일치했다. Task10.1 840개 중839개는 일치하고 `forward.py`1개는 이번 변경이 아니라 Task12에서 승인·보존한 retry 수정이다. 현재 hash가 기존 `runtime/task12/forward_patch.json`의 수정본 hash와 같음을 재확인했다. [기존 증거 대사](../../runtime/task13_r0/old_evidence_audit.json), [현재 무결성](../../runtime/task13_r0/integrity.json)을 참조한다. 기존 tracked5파일187삽입/1삭제 diff도 유지했다.

기존 `quant-operations.timer`가 active이며 동일 운영 흐름으로 계속 예약되는 것을 읽기 확인했다. Forward·Factory·Paper·Live 기록을 이 작업에서 갱신하거나 중단하지 않았다. 시점별 새 Forward 성과의 성숙 여부를 이번 수집 결과로 판정하지 않는다.

## 9. 다음 최소 보완과 연구 범위

가격 확장으로 기존38/20보다 실제 연구 횡단면176/126과 긴 fit·H60 입력을 확보했다. 다만 현재 구성 편향이 없어지지 않았으며 **`READY_FOR_TASK13_B`나 일반화된 PIT 투자 성과**로 승격하지 않는다. 이 제한을 명시한 모델·팩터 개발은 가능하다. 작은군 전용 횡단면, 전체시장 대표성, 정식 원가격 체결·독립 기업행사 검증은 아직 준비되지 않았다.

가격 이후 추가할 정보는 우선 두 가지로 제한한다.

1. **기존 DART 원문 기반 공표일·정정 계보를 갖는 재무/실적 이벤트.** Task9.2 numeric packet의 수치·기간·연결/별도·단위·최초 공개 시각 검사를 재사용한다. 현재 재작성 재무를 과거 최초 수치로 사용하지 않고 원문에 존재하는 버전부터 제한 도입한다. 미국 SEC403은 이 작업에서 해결했다고 주장하지 않으며 기존 공식 IR·SEC 접근 적격성이 확인된 자료만 추가한다.
2. **기존 Toss 실제 거래대금·수급의 제한된 날짜별 입력.** 이번 명세·현재 거래대금 경로를 출발점으로 역사 접근 범위·발표/관측 시각·단위·거래정지 의미를 먼저 소량 검증한다. 현재 1개월 집계 값을 과거 매매 시점의 feature로 소급하지 않는다. 무료 기존 권한으로 충분한 역사가 없으면 기능을 강제로 만들지 않는다.

후속 네이티브 연구는 train-only 입력 파일 hash·cutoff·cohort·primary horizon·자원 예산을 먼저 고정하고 실행한다. 평가자는 validation을 별도로 만들며 current-cap·미래 label 접근 차단을 검증해야 한다. H60 자료가 생겼다는 이유로 복잡한 모델·LLM 예산을 자동 확대하지 않는다. 광범위 PIT 경제성에는 역사적 구성·상폐 및 기업행사 보완이 선행한다. 이번에 알파 생성·모델 재학습·새 백테스트·전략 승격은 수행하지 않았다.

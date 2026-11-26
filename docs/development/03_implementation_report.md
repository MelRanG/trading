# Task 3 · 구현·실측 보고서

2026-11-13 KST · **미국 개별주식 우선 / 한국 개별주식 병행**. 사용자 후속 지시에 따라 신규 운용에서 ETF를 제외했다. ETF는 벤치마크 데이터만 사용하며 주문 대상으로 넣지 않는다. Task 1·2의 ETF 중심 초기 설계는 이 범위로 대체된다.

## 핵심 결과

- 미국 비ETF 상장 증권 목록 7,455건, DART의 종목 코드가 있는 기업 4,016건을 실제 수집했다. 미국 일반주 여부를 추가 필터링하며 DART 목록 자체를 완전한 상장/상폐 이력으로 해석하지 않는다. 미국 8개·한국 6개 주식의 고정 seed와 별도 목록 순회 수집을 구현했다.
- 가격·공시/RSS 수집, 독립 퀀트·기업 분석, 봉인 판단, 통화별 PostgreSQL Paper 원장과 Task 4용 내보내기를 연결했다. 국내는 판단 이후 Toss 가격으로 **개별주식 1건 Paper 매수·NAV 저장·재대사**를 실행했고 반복 호출에서 추가 체결은 0건이었다. 미국은 신선한 후속 가격을 기다린다. 브로커 주문 API 호출은 0건이다.
- 개별주식 전략 3경로를 동일 시장·seed·기간·D-1 판단·다음 시가·비용 산식으로 비교했다. 미국 모멘텀/추세는 이 표본에서 주식 바스켓보다 낮은 수익·작은 MDD였고, 국내 두 전략은 비용 반영 벤치마크에 뒤졌다. **생존 편향이 있는 작은 역사 표본이며 수익 우위 검증이나 전략 승격을 하지 않았다.**
- 최소·운영 안전·DB 수용·신규 인과/통화/ETF 차단/장애 시험 **166 passed, skipped 0**. 컴파일·pip check 성공. 미국·한국 6개 전략 NAV를 체결에서 독립 재구성했고 오차는 미국 최대 약 2.1e-10 USD, 국내 약 1.4e-8 KRW였다. DB와 원문 백업을 새 격리 DB/디렉터리에 복원·재대사했다.
- **미완료:** SEC 직접 API는 HTTP 403, EdgarTools 실제 호출은 TransportError. 기업가치 기반의 정량 예측·검증된 매매 규칙은 아직 Shadow이며, 미국 실제 후속 이벤트 체결·독립 Forward 성과·상시 예약 운영은 미검증이다. 기술 연결 및 역사 스크리닝을 투자 효능 완료로 표현하지 않는다.

## 1. 실제 구현·변경

| 파일/영역 | 변경 |
|---|---|
| `scripts/run_investment_cycle.py`, `run_equity_cycle.py` | 미국 기본·한국 선택 단일 CLI. `.env`는 신규 프로세스에서만 읽고 기존 DART/Toss 별칭을 호환 처리. 계좌/주문 권한 활성화 없음 |
| `src/quant_harness/investment/equities.py` | Nasdaq 종목 목록, DART corp 코드, Yahoo 가격 원본, Toss 개별주식 페이지 수집, SEC 메타데이터·선택 EdgarTools 확인, 시장별 RSS, 독립 주식 분석·역사 비교 |
| `stockpaper.py`, `store.py` | USD/KRW 별도 DB, 불변 입력/프롬프트/판단 기록, advisory lock, 결정론적 주문 ID, 원장 재대사, **체결·현금·포지션·NAV 단일 트랜잭션**. 신규 체결은 계약/코드 fingerprint 불일치 시 차단; 완료 회계는 업그레이드 후에도 멱등 복구 |
| `discovery.py`, `valuation.py` | 실제 Codex 호출, 출처 인용·필수 논거 검증, 7일 뉴스의 현재 최초 관측, 시나리오 수치 계약·reverse DCF 계산. 모델에는 DB/API 인증 환경을 제거하고 shell/web 도구를 비활성화. 모델 논거의 사실 정확성을 자동 인증하지 않음 |
| `research.py`, `portfolio.py` | 기존 V77 비용·현금제약 산식 재사용; 미투자 현금을 지원하는 공통 역사 평가. 별도 sleeve 중복/총노출/섹터 위험 preview. 통합 자본 배분 계좌는 아직 실행하지 않음 |
| `config/task3_equity_contract.json`, `task3_equity_price_contract.json` | 주식/시장/통화·고정 규칙·위험/비용 가정과 새 가격 소스 계약. 기존 활성 전략/config를 변경하지 않음 |
| `scan_equity_universe.py`, `run_investment_skill_ab.py` | seed 밖 종목의 bounded 순회·cursor 및 고정 자료의 스킬 제거 비교. 새 발견은 Shadow; 자동 전략 변경 없음 |
| `audit_equity_comparison.py`, `task3_database.py`, `compose.task3.yaml` | 독립 NAV·국면·비용 벤치마크, 전용 DB 초기화/백업/새 DB 복원 점검 |
| `requirements.lock`, `pyproject.toml`, `requirements-equity.lock` | 필요한 psycopg 3.3.9·dotenv 1.2.4 고정. EdgarTools 6.0.0은 선택 의존성으로 설치·실호출 확인 |
| 신규 테스트 2파일 | 인과성, 출처/인용, 가격 수정·US ticker 보존, ETF/통화/위험 차단, 중복/동시 실행, 트랜잭션 중단·재시도, 코드 변경 차단과 기존 완료 회계 복구 |

기존 `src/` 운영 모듈·알고리즘·주문 경로·Live 잠금은 수정하지 않았다. 이번 작업에서 먼저 만든 ETF 실행 연결은 후속 범위 변경에 맞춰 제거했다. 기존 ETF 비교는 `run_task3_legacy_comparison.py`의 **과거 진단 전용**으로 남겼으며 신규 운용 판단에 적용하지 않는다. 삭제돼 있던 `docs/research/`는 복원하지 않았다.

## 2. 전략 비교와 선정·보류

신규 주식 계약은 과거 ETF 계약과 별도 사전등록이며 결과를 보고 기간·임계값·비용을 최적화하지 않았다. 모멘텀 63일·추세 120일, 최대 4종목·종목당 20%·목표 총노출 80%, 롱온리·일별 재평가다. 목표 노출과 보유 중 가격 상승에 따른 실제 노출은 다르다. Forward Paper는 체결 시점과 비용 반영 후 실제 한도를 다시 검사한다. LLM은 위험·손절·익절을 바꾸지 못한다.

D-1 신호와 sizing, 다음 적격 가격의 체결을 분리했다. 역사 비교는 같은 원본을 모든 경로에 고정하고 동일 정수 수량·최소 주문·참여율·수수료/스프레드/충격을 적용했다. 미국·한국 비교 기간이 다르므로 시장 간 우열을 직접 판단할 수 없다. 기존 V69는 ETF 신호이므로 이 주식 비교에서 동등한 기존 전략이라고 이름을 바꿔 넣지 않았다.

### US · 2022-05-09~2026-11-11 · 1133세션

| 경로 | 비용 후 수익 | Sharpe | MDD | 회전/초기자본 | 총비용 |
|---|---:|---:|---:|---:|---:|
| MOM63_STOCKS | +157.19% | 1.305 | -14.53% | 241.07× | 15,156.91 USD |
| DEFENSIVE_STOCKS | +151.59% | 1.312 | -15.00% | 223.52× | 14,047.34 USD |
| EQUAL_WEIGHT_STOCKS | +263.37% | 1.233 | -27.49% | 24.56× | 1,481.64 USD |
| SPY 비용 반영 단순보유, 초기 100% 노출 · **비교 전용** | +99.08% | 0.998 | -18.75% | — | 초기 61.43 USD |
| SPY 비용 반영 단순보유, 초기 80% 노출 · **비교 전용** | +79.04% | 1.001 | -16.15% | — | 초기 48.88 USD |

원본: `runtime/task3/us/final/comparison/`; 국면별 진단·독립 재구성·벤치마크 비용은 `independent_audit.json`. 지수 원시 수익률은 +84.79%이며 비투자가능·배당 제외 참조다.

### KR · 2021-08-18~2026-11-12 · 1280세션

| 경로 | 비용 후 수익 | Sharpe | MDD | 회전/초기자본 | 총비용 |
|---|---:|---:|---:|---:|---:|
| MOM63_STOCKS | +27.27% | 0.331 | -35.26% | 91.32× | 1,532,246.88 KRW |
| DEFENSIVE_STOCKS | +32.45% | 0.379 | -29.64% | 77.06× | 1,291,868.46 KRW |
| EQUAL_WEIGHT_STOCKS | +117.78% | 0.710 | -38.31% | 21.56× | 352,844.74 KRW |
| 069500.KS 비용 반영 단순보유, 초기 100% 노출 · **비교 전용** | +125.22% | 0.655 | -46.88% | — | 초기 7,178.90 KRW |
| 069500.KS 비용 반영 단순보유, 초기 80% 노출 · **비교 전용** | +100.37% | 0.623 | -44.11% | — | 초기 5,694.90 KRW |

원본: `runtime/task3/kr/run3/comparison/`; 국면별 진단·독립 재구성·벤치마크 비용은 `independent_audit.json`. 지수 원시 수익률은 +69.98%이며 비투자가능·배당 제외 참조다.

`EQUAL_WEIGHT_STOCKS`는 **seed의 첫 4종목을 20%씩 매일 재배분**하는 비교군이다. 미국은 AAPL/MSFT/NVDA/AMD에 집중돼 있어 강한 선택·업종 편향이 있다. 8개/6개 표본 전체 또는 전체 주식시장의 분산 포트폴리오 성과가 아니다. ETF 단순보유의 노출은 초기값으로 이후 drift를 허용하며, 두 노출 기준을 함께 표시했다. 가격 수정/배당 처리와 실제 거래 수수료·세율·시장충격은 독립 인증되지 않았다.

모멘텀·추세는 FinRL에서 검토했던 순위/회전 논리를 독립 구현한 **연구 후보**이며 upstream 엔진/성과 재현이 아니다. 과거 FinRL 미국 6종목 결과를 이번 신규 표본의 우위 근거로 사용하지 않았다. 두 후보의 정책·기간은 유지하고 Shadow/Paper 기록만 축적한다. 높은 수익의 주식 바스켓 역시 생존 편향 때문에 승격하지 않는다.

| 기존/외부 후보 | 현재 결정과 근거 |
|---|---|
| V69/V79 | 기존 ETF 역사 비교를 동결 진단으로 유지. 주식 신규 운용에는 연결하지 않음 |
| FinRL 회전/모멘텀 | 필요한 논리를 주식에서 동일 조건 평가. 전체 프레임워크 미설치, 수익 우위 인증 아님 |
| ai-hedge-fund | 시점별 재무·가치 스타일 입력이 부족해 주식 동일 조건 수익 비교 미실행. 불리한 결과로 기각한 것이 아님 |
| Qlib | 학습형 모델·라벨·독립 데이터 분할이 없는 현재 seed 진단과 구별. 모델 훈련/투자 효능 비교 미실행 |
| TradingAgents | 독립 논거·반론의 구조만 참고. 전체 그래프·수익률 대결은 미실행 |
| RD-Agent/Hermes | 이번에 중복 런타임을 설치하지 않음. Task 4가 공식 기록/가설 등록 경유로 연결할 후보 |

## 3. 수집·독립 발굴의 실제 증거

- `runtime/task3/us/final/`: 미국 일반주 seed 8개 + 비교용 지수/ETF 가격 10개 수집·새 raw 계약/V87 검사. 종목 목록·가격과 입력 해시를 PostgreSQL에 보존. 퀀트 후보 생성 및 다음 가격 대기. SEC 원문 수집은 403 때문에 실패 기록을 보존했다.
- `runtime/task3/kr/run3/`: 국내 6개 주식 + 비교용 ETF의 Toss 수정 OHLC를 각 7페이지 수집, 기존 V87 품질/수정 gate 재사용. KOSPI는 별도 지표 endpoint로 수집. Yahoo 국내 데이터는 OHLC geometry 오류로 거절했고 보간하지 않았다.
- 기업 분석은 퀀트 출력 없이 공시/RSS만 읽는다. 국내는 선행 변화·재무 전달 경로·예측·반증을 포함한 연구 후보를 만들었다. 미국도 별도 probe에서 미검증 클라우드 계약 관련 후보가 생성됐으나, 더 넓은 최근 자료의 최종 분석은 근거 부족으로 기권했다. 모든 응답과 기권을 보존한다. 제목 기반 추론은 공식 사실·적격 종목 매핑으로 승격하지 않는다.
- `scan_equity_universe.py`는 미국 목록에서 seed 밖 A/AA/AAC/AACP/AADX/AAL/AAME/AAMI를 실제 수집했다. 일부 입력 부족으로 전체 배치는 ABSTAIN, A/AAMI는 진단 후보로 기록했다. 데이터 누락이 있는 배치에 주문 권한을 주지 않았다. cursor로 다음 배치를 이어갈 수 있다.
- 원본 응답과 `available_at`, source hash, revision 검사를 저장한다. 이번에 받은 역사 데이터는 이번 수신 시점의 관측이며 과거 최초 관측·신규 Forward 기간으로 위장하지 않는다. 기존 누락 runtime/분봉/canonical 백업은 조사한 경로에서 찾지 못했고 동결 자료를 덮어쓰지 않았다.

### 투자 스킬 4종 적용·비교

`runtime/task3/us/skill_ab/`에 같은 고정 미국 뉴스·동일 모델로 무스킬/촉매/실적/기대 역산/복기 양식을 각각 1회 호출한 과정 pilot을 남겼다. 촉매·실적은 기권, 무스킬·기대 역산·복기 양식은 연구 후보를 반환했다. **후보 개수는 정확도나 성과가 아니다.** 하드 토큰 예산·독립 사실 채점·실현 라벨이 없어 엄격한 동등 예산 A/B 또는 효능 통과로 판정하지 않는다.

- investor-harness: 촉매·컨센서스 결측 시 기권·반증 조건 체크를 선택 적용.
- financial-services: bear/base/bull와 부족한 수치의 기권 계약. 숫자 근거 부족으로 정량 예측 정확도는 미평가.
- equity-research-skill: 기대 역산 체크와 별도 결정론적 reverse DCF·단위/가정 검사. 실제 가격·주식 수·부채·FCF 등 입력 묶음이 없어 종목별 DCF는 NOT_EVALUATED. 합성 산식 시험을 투자 성과로 취급하지 않음.
- InvestSkill: thesis·원인/과정·무효화·미확인 항목의 저장 양식. 사후 복기/자기개선 자체는 Task 4에 남김.

원본 번들을 통째로 실행한 것이 아니라 기존 고정 버전에서 선정한 기능을 축약한 adapter다. 별도의 초기 pilot은 미래 cutoff를 잘못 지정해 중단했고 `ABORTED_INVALID_FUTURE_CUTOFF`로 보존했다. 이후 미래 cutoff 거절을 추가하고 별도 실험으로 재실행했다.

## 4. Paper·DB·안전 검증

- 전용 `quant-task3-postgres`, loopback 55432, `quant_task3_test`/`stocktest`와 USD `us`·KRW `kr` DB를 분리했다. 기존 서비스 DB/운영 설정은 변경하지 않았다. 로컬 trust 인증인 개발·연구 DB로서 외부 노출/production 배포를 승인한 구성이 아니다.
- 국내 실제 관측 기반 Paper: `068270.KS` 9주 BUY, **브로커 전송 없음**. 기록된 평가 NAV는 9,998,775.4683 KRW, 재대사 일치. 이는 가상 체결 비용을 반영한 시점 평가이며 투자 성과 검증이 아니다. `runtime/task3/kr/recovery_final/task4_records.jsonl`과 `stock_fill/stock_nav`에서 확인 가능하다.
- 미국은 `1632759bcb9f9efcd9e13fffb9cbffb77855da766582664497f8dfd871739424` 판단을 봉인했고 체결 0건이다. 최초 가격 응답을 사후 재사용하지 않고 다음 신선한 정규장 가격을 요구한다. 초기 개발 중 코드 fingerprint가 부족했던 미체결 판단은 무효화·재봉인했고, 이미 완료된 국내 원장은 수정하지 않았다. 그 초기 국내 기록은 코드 버전 완전성 측면에서 성과 승인 근거로 제한한다.
- 166개 pytest 통과, skipped 0: AGENTS 최소/운영 묶음, PostgreSQL 기존 수용 47개, 신규 주식/인과/스킬 산식 22개 및 뉴스/Factory 검증 포함. 전체 저장소 테스트 전체를 실행한 것은 아니다. `compileall`, `pip check`, `git diff --check`도 성공.
- V104 Forward runner: 실제 출력은 `NO_ENABLED_CANDIDATES`, append 0, Live false. 기대 문구를 억지로 `NO_NEW_SESSION_AFTER_V104_FREEZE`로 바꾸지 않았다. 기존 카운터에 이번 관측을 합치지 않는다.
- 원문·코드/계약·DB dump는 `runtime/task3/backups/task3_final_20261113/`에 해시와 함께 보관했고 새 restore DB에 복원했다. 원 DB와 복원된 USD/KRW 계좌 모두 cash/position/fill 재대사 성공. DB별 일관 백업이며 여러 DB 사이 원자 snapshot은 아니다. 상시 백업 스케줄은 아직 배포하지 않았다.

재실행 예시(모두 전용 DB):

```bash
.venv/bin/python scripts/task3_database.py init
TASK3_US_DATABASE_URL=postgresql://quant_task3@127.0.0.1:55432/quant_task3_us \
  .venv/bin/python scripts/run_investment_cycle.py --market US --compare --output runtime/task3/us/NEW_RUN
TASK3_KR_DATABASE_URL=postgresql://quant_task3@127.0.0.1:55432/quant_task3_kr \
  .venv/bin/python scripts/run_investment_cycle.py --market KR --resume DECISION_ID
.venv/bin/python scripts/audit_equity_comparison.py runtime/task3/us/final
.venv/bin/python scripts/audit_equity_comparison.py runtime/task3/kr/run3
```

진행 중 판단이 있으면 `--resume`으로 먼저 완료/검사한다. 계약/알고리즘이 달라진 미체결 판단은 재봉인이 필요하다. 과거 실험 디렉터리에 다른 입력을 덮어쓰면 등록 충돌로 차단한다. 개발 DB 초기 생성에는 `docker volume create quant_task3_pgdata`, `docker compose -f compose.task3.yaml up -d`가 필요하며 기존 컨테이너를 재생성/삭제할 필요는 없다. 현재 로컬 DB는 이미 실행 중이다.

## 5. Task 4 연결 계약

`investment_record(record_id, kind, payload, payload_hash, created_at)`와 시장별 `task4_records.jsonl`이 연결 지점이다. collection/catalog/price validation → company/quant analysis → frozen stock decision → stock quote events → fill/NAV/outcome의 ID와 해시를 보존한다. 모델·프롬프트 원문/해시·스킬 고정 revision·분석 시각·응답·실패/기권·수집 비용 및 토큰 이벤트가 포함된다. 모델 호출 금액 미상은 0원으로 기록하지 않는다.

Task 4는 당시 입력으로 과정 평가, 성숙한 실제 결과로 예측·수익/비용 채점을 분리하고, 원인·불확실성을 명시한 제안을 기존 Factory에 등록해야 한다. 현재 기록의 `PENDING_TASK4`, `PENDING`, `NOT_CREATED`는 처리 완료가 아니다. 거래/원문/판단을 수정하지 않고 새로운 복기·제안 레코드에서 원 ID를 참조한다. 기존 Factory의 중복·예산·사전등록·Forward·사람 승인 경계를 유지한다.

## 6. 남은 공백과 판정

**Task 3의 수집→독립 분석→격리 Paper 회계 연결은 실제로 실행했지만, 투자 효능·완전한 운용 수용은 완료되지 않았다.** 미국 후속 가격 체결, 기업가치 전략의 검증된 정량 입력/실행 정책, SEC 수집 복구, 더 넓은 시장 표본/PIT 상장·상폐·코드변경·기업행사, 실제 비용/세금·환율 계약, 연속 세션의 장애·휴장·운영 복구가 남는다. 통합 sleeve 배분 계좌는 preview만 있고, 독립 계좌 NAV를 합쳐 포트폴리오 성과로 표현하지 않는다.

SEC는 API key가 없는 공개 공시 API지만 이 서버의 접근이 거절됐다. 제공된 식별 이메일은 요청자 연락처용이며 광고/정보 구독 신청을 하지 않았다. 참고: [SEC 공개 API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [EdgarTools identity](https://github.com/dgunning/edgartools/blob/main/docs/quickstart.md). 접근 원인은 네트워크/서비스 응답 이상으로 확정하지 않았고 다른 신분이나 우회 서비스로 대체하지 않았다.

새 전략은 모두 연구 Shadow/Paper다. 현재 데이터·동결 결과·이전 성과를 신규 Forward 증거로 집계하지 않으며 자동 부모 변경·Champion/Live 승격은 없다.

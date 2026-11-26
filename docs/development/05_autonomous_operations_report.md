# Task 5 — 주식 Paper 통합 운영·실험 기반

기준: 2026-11-13 Ubuntu 서버. **운영 코드와 실제 실행은 추가했지만, Task 5 전체 완료로 판정하지 않는다.** 새 공통 전략 A/B 실행은 기존 Factory 일일 예산으로 차단됐고, 실제 보유기간 Forward 결과도 아직 미성숙하다. 이를 우회하거나 과거 성과를 새 실측으로 표시하지 않았다.

## 핵심 결과

- **단일 운영 실행 구현·실행:** 공식 KR/US 달력 → 선택적 가격 수집·불변 입력 → 기존 독립 분석/주식 Paper → Task 4 복기 → Factory 대기/재시도 → 백업. `quant-operations.timer`를 user systemd에 설치·활성화했다. 프로세스 종료 후 5분 간격, 동시 실행은 PostgreSQL advisory lock으로 차단한다.
- **실제 데이터:** 승인된 미국 주식 8개+SPY, 한국 주식 6개+069500을 수집했다. 추가 발견한 미국 `A`도 연구용 가격 적격성을 확인했다. 합계 미국 2,000봉·한국 1,400봉, 고유 원문 22개/689,680 bytes. ETF는 벤치마크이며 주문 대상이 아니다.
- **실제 Paper·복기:** 기존 미국 판단은 다음 정규장 가격 이벤트 대기, 한국 완료 거래는 재사용했다. 누적 체결 US 0건/KR 1건을 유지하고 두 계정은 `ACTIVE`·대사 일치다. 실제 판단 6건을 복기에 연결했으며 결과는 `PENDING`이다. 새 매매를 성공 사례로 만들기 위해 거래하지 않았다.
- **반복·복원:** 동일 세션 반복 실행은 추가 데이터 API 호출 없이 0.908초. 4개 DB를 새 격리 DB에 실제 복원하고 immutable record hash와 USD/KRW 원장을 검사했다. 원문/Factory/코드 archive도 새 디렉터리로 복원했다.
- **검증:** 정리 전 190 passed, 변경 후 기존 회귀 190 passed, 추가 운영 시험 15 passed. 실패·스킵 0건(시험 기준). 실제 수집에서는 국내 신규 후보 1개가 실패했고, 새 공통 A/B는 `BLOCKED`다. 시험 통과와 기능의 투자 효능을 구분한다.
- **안전 보존:** Task 3 전략 계약·알고리즘·`equities.py`/`stockpaper.py`·기존 주문 계산·Live hardlock·승격 정책은 수정하지 않았다. 실주문 0건. 별도 코인 DB 접속·변경, 유료 데이터 구입, 외부 프레임워크 설치는 없다.

## 1. 실제 통합 구조와 책임

```text
systemd user timer (단일 예약)
  run_autonomous_operations.py / operations.tick
    ops DB의 공통 lock
    KR/US별 독립 오류 경계
      공식 달력 + 확인된 다음 거래 세션
      관심목록 / catalog 순회 탐색 (가격 전체 수집 금지)
      Toss adjusted/raw 일봉 → V87 수치·형태 gate → revision 대조
      동결 snapshot → 기존 analyze_stocks / 독립 company_discover
      기존 stockpaper.seal → 이후 정규장 관측 quote → execute/reconcile
      관측된 close NAV → 성숙 라벨 → Task4 run_cycle
    기존 Factory 예산으로 동결 공통 실험 재시도
    일일 DB·근거 백업 / 수집·실행·용량·모델 사용량 기록
```

| 파일 | 구현 책임 |
|---|---|
| `src/quant_harness/investment/operations_data.py` | 달력 파싱·연속 세션 증명, immutable 원문/snapshot, 예산·회로 차단, watchlist, 최초/증분 수집, 실제 HTTP/OAuth 시도 관측 |
| `src/quant_harness/investment/operations.py` | 한 번의 bounded tick, 시장별 복구, 기존 결정 채택, 만료 후속 기록, 봉인 전 manifest, quote/완료 회수, 라벨·복기·Factory·백업 연결 |
| `src/quant_harness/investment/operations_experiment.py` | 7개 팀 공통 계약, 동결 주식 A/B adapter, 사전등록·예산·worker hash·결과 cache·Factory 연결 |
| `src/quant_harness/investment/operations_backup.py` | 기존 container 확인, 4개 DB dump, 근거 archive, 새 DB 복원·해시·Paper 대사 |
| `scripts/run_autonomous_operations.py` | 현재 단일 운영 진입점 |
| `scripts/run_common_experiment.py` | 기존 Task3 미국 원문만 읽는 동결 전략 실험 요청 |
| `scripts/setup_operations_database.py` / `scripts/install_operations_timer.sh` | 기존 DB에 제한 역할 구성·단일 user timer 설치. 초기화/삭제 없음 |
| `scripts/backup_operations.py` / `scripts/probe_operations_restore.py` | 실제 복원·재개 검사 |
| `config/task5_operations.json` / `deploy/systemd/quant-operations.*` | 수집/모델 예산·관심목록 상한·보존·예약 |
| `tests/test_autonomous_operations.py` | 실제 격리 PG를 사용하는 운영 계약·장애 경계 시험 |

작업 진행은 immutable 기록과 mutable pointer로 분리한다. 가격 snapshot, 분석 입력, 결정, lineage, 원문은 수정하지 않는다. seal 직후 checkpoint 전에 중단되면 기존 `stock_decision`/상태를 조회해 회수하고, 봉인 전 manifest로 누락 lineage를 복구한다. 체결 커밋 후 재호출은 기존 stock_nav를 회수한다. 금요일에 월요일 판단을 미리 봉인하는 경우도 봉인 날짜 대신 할당된 거래 세션을 복구 키로 사용하며, 해당 중복 판단 방지 회귀 시험을 추가했다. 판단 만료는 원본 수정 없이 후속 기록+`EXPIRED` 상태로 남긴다. 전략 설정 hash가 바뀌면 운영을 차단한다.

미국·한국 계정은 각각 USD/KRW다. 각 계정의 기존 종목/총노출 한도를 적용하며, 환율을 추정해 통합 NAV·전 세계 포트폴리오 위험을 계산하지 않는다.

## 2. 소스 정리와 연구 복구

Git `26d5722`에서 `docs/research/`의 문서 11개를 원본 그대로 복구했다. `05_research_restoration.json`에 원본 Git blob을 기록했다. 삭제 전 미커밋 내용은 복구됐다고 주장하지 않는다. 복구 문서의 과거 실패/진행 상태는 최신 development 보고서와 구분한다.

`05_source_inventory.json`은 Python import AST, 명시한 진입점과 보존 의존성을 기록한다. 이는 runtime coverage가 아니다. 상대 import·동적 호출·shell/설정 경유를 모두 증명하지 못하므로 **참조 없음만으로 UNUSED/삭제 가능 판정을 내리지 않았다.** 세부 개수는 생성된 JSON과 실행 출력을 기준으로 한다.

- ACTIVE: 현재 investment 운영/복기 모듈, 공식 Factory, 현재 진입점.
- BASELINE: 동결 V69~V104 재현, 안전 gate, 테스트 및 의존성이 불명확한 보존 대상. shared import가 있다고 신규 승인 전략으로 보지 않는다.
- RESEARCH: 투자 스킬 진단, 제한 탐색, 독립 모델 note 등 별도 도구.
- LEGACY: V85 scheduler 및 관련 구형 운영 경로. 재현 코드는 보존한다.
- UNUSED: 안전하게 기능·재현 가치가 없다고 증명한 파일 없음. 삭제 0개.

`compose.yaml`의 구형 scheduler와 제어판을 `legacy-reference` profile로 옮겨 기본 예약에서 제외했다. 코드 이동/삭제 없이 중복 운영 진입점을 분리했다. Hermes의 기존 별도 백업·모델 감사 timer는 이 프로젝트의 거래 scheduler가 아니며 수정하지 않았다. Hermes Gateway/Cron을 추가하지 않았다.

## 3. 데이터 제공자·저장 정책과 실측

| 항목 | 현재 정책·측정 |
|---|---|
| 미국 | 승인 seed 8, 벤치마크 1, 연구 적격 A 1 → 가격 snapshot 10개/2,000봉 |
| 한국 | 승인 seed 6, 벤치마크 1 → 7개/1,400봉 |
| 관심목록 상한 | US 150 / KR 100, 현재 12/11. 목표 수를 맞추기 위한 전체 가격 수집은 하지 않음 |
| catalog 탐색 | 하루 갱신 시 메타데이터 4개 순회, 신규 후보 가격 검증은 시장별 완료 세션당 최대 1개 |
| 실제 신규 발견 | A: `DATA_QUALIFIED_RESEARCH_ONLY`; 032600.KS: Toss 오류로 `DATA_INSUFFICIENT`/차단. 어느 쪽도 매매 전략에 편입 안 함 |
| 가격 수집 | 최초 200봉, 이후 8봉. 기존 accepted snapshot과 겹침/수정 검사, 130봉 이상·정확한 마지막 완료 세션 요구 |
| 결측·수정 | OHLC/통화/중복/유한값/V87 검사. 기존 OHLC·volume/raw_close 수정 또는 증분 overlap 단절은 차단. split 등은 임의 보정하지 않음 |
| 관측 시점 | 원문 hash·실제 receipt 시각 보존. 뒤늦게 받은 과거 봉은 신규 Forward 관측으로 소급하지 않음 |
| 보존 | 실제 판단 snapshot·원문·모델/전략/프롬프트·Factory·NAV 영속 저장. 동일 세션/실험 재실행은 snapshot 사용 |
| 측정 | 첫 bootstrap 논리 요청 US 19 / KR 16, 후속 탐색 후 US 21 / KR 17(실패 1). wire 계측 추가 이후 OAuth 포함 US 3 / KR 2(실패 1). 초기 wire 재시도 수는 미계측 |

DB는 JSONB immutable snapshot과 pointer를 사용한다. 원문은 content hash 파일로 보존한다. 아직 실제 용량/성능 문제를 관측하지 않아 별도 시계열 DB·파티셔닝·벡터 DB를 추가하지 않았다. 4개 운영 관련 DB는 각각 약 8.4~10.2 MB이고, 실제 값은 `runtime/task5/metrics.json`에 남겼다. 백업 dump 총량과 archive 크기는 각 manifest를 기준으로 한다.

Yahoo 기존 수집기·동결 원문은 보존·재사용한다. 다만 [Yahoo 약관](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html)의 자동 접근 제한과 허가 미확인 때문에 새 반복 Yahoo 수집은 활성화하지 않았다. **미국의 새 일일 가격도 인증된 Toss 경로를 사용한 정책 차이**를 명시한다. Yahoo 자동 수집 권한을 확인하면 기존 adapter를 별도 검증해 다시 선택할 수 있다.

Toss는 [공식 Open API 약관](https://home.tossinvest.com/ko/terms/v2?id=752)과 [공식 overview](https://openapi.tossinvest.com/openapi-docs/overview.md)를 확인했다. 2026-11-13 문서의 클라이언트×그룹 TPS는 MARKET_INFO 3, MARKET_DATA 15, MARKET_DATA_CHART 20이며 일부 IP에는 더 낮은 제한이 있을 수 있다. 신규 transport는 최소 약 1.05초 간격, quota/Retry-After 헤더·HTTP 상태를 기록한다. 기존 client의 최대 4회 GET 재시도도 wire 예산에 집계한다. OAuth token 본문/인증 헤더는 저장하지 않는다.

일일 시장별 논리 요청 100·wire 요청 200은 **운영 자체 예산이지 제공자가 보장한 한도는 아니다.** 실패도 예산을 소비한다. 일반 실패는 cooldown, 인증 거부는 24시간 회로 차단한다. SEC는 기존 403을 우회하지 않았다. 미국 공식 공시 의존 분석은 계속 제한 운영이며, 이번 자동 경로는 제한 RSS를 사용한다. OpenDART의 기존 collector는 국내 catalog에 재사용한다. DART 기업 코드 목록은 상장 생애주기/PIT 유니버스의 증명이 아니다.

## 4. PostgreSQL·재시작·실제 운영

기존 `quant-task3-postgres` 1개, **127.0.0.1:55432**, 기존 영속 volume을 재사용했다. 새 서비스·코인 DB는 사용하지 않는다. `quant_task3_ops`만 같은 인스턴스에 추가했다.

| DB | 역할 | 권한 |
|---|---|---|
| quant_task3_us | 미국 주식 Paper | quant_paper_us |
| quant_task3_kr | 한국 주식 Paper | quant_paper_kr |
| quant_task3_review | 독립 복기·연구 작업 | quant_review |
| quant_task3_ops | 수집·일정·작업·실험 참조 | quant_ops |

4개 역할 모두 superuser/createdb/createrole=false. 실제 검사에서 미국 역할의 한국 stock_account SELECT와 그 반대는 false였다. 시험 DB는 기존 별도 DB+개발 관리 역할이며 운영 실행의 초기화 대상이 아니다. 단, 기존 loopback trust는 유지했다. 같은 호스트의 신뢰 경계까지 강화한 비밀번호/mTLS 인증이라고 표현하지 않는다.

`compose.task3.yaml`과 실제 container의 restart policy를 `unless-stopped`로 맞췄다. Docker 부팅 활성화, user systemd manager·linger=yes를 확인했다. 실제 서버 재부팅은 수행하지 않았다. DB 장애 시 tick은 실패하고 다음 예약이 재시도한다. 원장 불일치 시장은 `HOLD_ONLY`이며 다른 시장의 복기까지 일괄 성공으로 처리하지 않는다.

user timer/service 설치 후 실제 oneshot 실행 결과 `Result=success`, `ExecMainStatus=0`. 기존 한국 체결은 1건 유지, 미국은 정규장 이후 가격을 기다린다. 현재 동일 세션 반복은 snapshot과 기존 판단을 회수한다. 새 세션에 생성되는 기업 분석은 기존 Terra adapter를 1회/시장/UTC일로 제한하며, 측정 input+output 40,000 token 초과는 기권·회로 차단한다. Codex CLI의 hard token cap은 제공하지 못하므로 이것은 **사후 측정 한도**다. Task5 실제 tick에서 새로운 LLM 호출은 0건이며 비용 금액은 미확인(null)이다. Task3의 기존 LLM 성공과 혼동하지 않는다.

실제 상태: `runtime/task5/latest_tick.json`, API/가격/DB 실측: `runtime/task5/metrics.json`, journal: `journalctl --user -u quant-operations.service`.

## 5. 성숙 라벨·복기 연결

공식 달력은 미국 KST 기준 응답의 regular open을 New York 날짜로 바꾼다. 현지 zone·offset을 유지하며 서머타임·조기 종료·휴장을 fixture로 검사했다. 정규장 외 세션은 구분하지만 Paper 체결은 기존 정규장 규칙만 사용한다.

달력의 previous/today/next는 전체 역사 달력이 아니다. 관측된 이웃 세션의 edge를 저장하고, 중간 달력이 누락되면 1·5·20세션을 달력 일수로 추정하지 않는다. 완료 후 최소 5분과 실제 봉·receipt·대사가 있어야 close NAV를 저장한다. 과거 close 이후 발생한 체결이 있으면 현재 포지션으로 그 과거 NAV를 소급하지 않는다.

관측 NAV와 달력 edge를 `labels_for`가 Task4 독립 scorer에 전달한다. 과정 복기는 계속 당시 정보로 먼저 봉인한다. 실제 6건은 아직 PENDING이며, 미래 날짜만으로 성숙시키지 않았다. fixture의 성숙 1세션 -10%, 미관측 NAV의 INSUFFICIENT_EVIDENCE, 달력 gap의 PENDING은 별도 시험으로 검증했다.

라벨의 제한:

- 현재 라벨은 실제 Paper 계정 연속 경로이며 개별 가설의 독립 인과 효과가 아니다. 이후 승인된 판단도 계정 경로에 포함된다.
- entry는 체결 NAV, 이후는 close NAV다. 동시점 벤치마크 entry가 없으므로 close 가격을 억지로 붙여 초과수익을 계산하지 않는다. 시장 초과성과는 해당 증거 확보 전 미채점, 섹터도 미채점이다.
- 배당 현금 권리·전체 corporate-action 원장은 미완성이다. split 조짐/수정은 차단한다. NAV는 거래비용 포함 가격 수익이며 total return 검증이 아니다.
- 원래 구조화된 수치 예측·사전등록 대체 행동이 없는 판단에 EPS/가격 목표/반사실을 사후 생성하지 않는다.
- 주문 변경이 없는 보유 판단은 `HOLD_NO_REBALANCE`와 계정 close mark를 남기며 새 체결 NAV를 만들지 않는다. 이러한 판단의 별도 entry 라벨 계약은 후속 보완 대상이다.

## 6. 공통 A/B와 외부 기술 연결

공통 계약은 team, adapter, 동결 snapshot hash, Baseline/Challenger, 모델/프롬프트/전략 버전, 기간, 지표, 실험 예산, 중단/승격 조건을 요구한다. 7개 team 값은 information/company/quant/portfolio/execution/review/research다. 현재 실행 adapter는 `STOCK_DAILY_FROZEN_V1` 하나이며, 미구현 evaluator는 `NOT_IMPLEMENTED`를 반환한다. 모든 팀 고급 평가기를 구현했다고 주장하지 않는다.

이번 요청은 **EQUAL_WEIGHT_STOCKS vs MOM63_STOCKS**, 동일 미국 Task3 원문·2026-11-11 cutoff·수수료/체결/위험 계약·토큰 0·추가 API 0의 역사 진단이다. 원문 파일 hash와 기존 Task3 preregistration input hash를 확인한 뒤 Factory에 사전등록했다.

- snapshot hash: `dbc20c1993bb2b8a455a83095da3ea7ec3fe7e0c2d6476848c03f711403da6aa`
- 실제 새 비교 실행: **미실행 / Factory 일일 실험 예산 소진으로 BLOCKED**.
- `runtime/task5/experiments/*/input.json`, `runtime/task5/common_experiment_console.json`, Factory 계약·attempt 원장에 근거가 있다.
- `experiment:pending` 요청과 매 UTC일 최대 1회 재시도를 영속 저장했다. 예산이 갱신돼도 입력/worker hash가 같아야 실행한다. worker 변경은 자동 수용하지 않는다.
- 결과가 생겨도 재사용한 survivor 역사 자료다. 신규 Forward·독립 holdout·장기 초과수익으로 집계하지 않으며 자동 Champion/Live 승격은 없다.

Task3 기존 비교에서 미국 MOM +157.187% vs 첫 4개 seed 균등 +263.371%라는 역사 결과가 있었지만, **이번 공통 실행기가 새로 측정한 수치가 아니다.** 선정/최적화 근거로 추가 사용하지 않았고 원본 결과를 수정하지 않았다.

외부 기술은 설치하지 않았다. investor-harness는 촉매/반론, financial-services는 수치 시나리오, equity-research-skill은 reverse DCF, InvestSkill은 복기 기록/평가, FinRL/Qlib/ai-hedge-fund는 strategy adapter 후보, TradingAgents/RD-Agent는 독립 판단/연구 worker 후보, Hermes는 권한 없는 Shadow 연구 후보로 유지한다. 기존 Task3/4 적용 근거는 복구 research와 development 보고서에 보존했다. 공통 snapshot/버전/예산/평가 결과 계약에 맞춰 증분 A/B를 붙일 수 있지만 미검증 효능을 전제하지 않는다.

## 7. 시험·백업·재현

| 실행 | 결과/구분 |
|---|---|
| 정리 전 `scripts/check_task4.sh` | 190 passed, 95.49초 |
| 변경 후 동일 필수 안전·Paper·Factory·DB·Task3/4 회귀 | 190 passed, 140.12초 |
| `tests/test_autonomous_operations.py` | 15 passed, 실패/스킵 0. 실제 PG + calendar/수집 장애 fixture |
| `python -m compileall -q src scripts tests` | 통과 |
| `scripts/run_v104_forward_session.py` | `NO_ENABLED_CANDIDATES`, rows_appended=0. 현재 데이터/설정 경로 결과이며 `NO_NEW_SESSION_AFTER_V104_FREEZE`를 출력했다고 바꾸지 않음 |
| 실제 provider tick / 동일 세션 재실행 | 실제 KR/US 관측 성공, 추가 탐색 KR 1건 실패, 동일 세션 재사용 성공 |
| systemd oneshot | Result=success, ExecMainStatus=0; timer enabled/active |
| 4개 DB dump→새 DB restore / 원문 archive 해제 | 실제 실행, record hash 및 Paper 원장 대사 일치 |
| 서버 실제 재부팅·실제 DB 장애 강제 종료 | 미실행. connection 종료/중복 lock/재개는 격리 시험으로 검사 |
| 실제 성숙 Forward·새 공통 전략 A/B 측정 | 각각 PENDING / BLOCKED, 통과로 집계하지 않음 |

백업은 공통 운영 lock 아래 24시간 간격으로 생성한다. DB별 일관 dump이며 4개 DB에 걸친 단일 트랜잭션 snapshot이라고 주장하지 않는다. 다른 수동 writer까지 막는 전체 서비스 일시정지는 아니다. 백업 근거는 `runtime/task5/backup_restore*_console.json`과 각 `runtime/task5/backups/*/manifest.json`이다. 최소 14일 보존 정책이며 현재 자동 삭제는 없다. `.env`·token·계좌 인증정보는 archive 대상이 아니다. 새 DB 복원은 같은 기존 PostgreSQL에서 검증했으며 새 서버 전체 복원과 구분한다. `probe_operations_restore.py`로 복원 DB의 동결 입력·과정 복기를 다시 읽고 한국 완료 Paper를 회수했다. 복원 전후 US 체결 0→0, KR 1→1이며 API 재조회는 0건이다. 근거는 `runtime/task5/restore_resume_console.json`이다.

```bash
# 기존 회귀 (각각 격리 DB)
TEST_DATABASE_URL=postgresql://quant_task3@127.0.0.1:55432/quant_task3_test \
TASK3_STOCK_TEST_DATABASE_URL=postgresql://quant_task3@127.0.0.1:55432/quant_task3_stocktest \
TASK4_TEST_DATABASE_URL=postgresql://quant_task3@127.0.0.1:55432/quant_task3_review_test \
TASK4_SOURCE_KR_URL=postgresql://quant_task3@127.0.0.1:55432/quant_task3_kr \
bash scripts/check_task4.sh

TASK5_TEST_DATABASE_URL=postgresql://quant_task3@127.0.0.1:55432/quant_task3_ops_test \
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest \
-o addopts='' -q tests/test_autonomous_operations.py

PYTHONPATH=src .venv/bin/python scripts/run_autonomous_operations.py
PYTHONPATH=src .venv/bin/python scripts/backup_operations.py --restore-check
PYTHONPATH=src .venv/bin/python scripts/run_common_experiment.py
```

새 운영 시험은 전용 `quant_task3_ops_test` schema만 초기화한다. 운영/코인 DB에서 실행하지 않는다. JUnit: `runtime/task5/regression_operations.xml`, 기존 회귀 로그: `runtime/task5/task4_regression_console.txt`.

## 8. 다음 고도화와 미완료 기준

| 영역 | 남은 핵심 검증/구현 |
|---|---|
| 정보 수집 | SEC 403/공식 공시 제한 해소 여부, DART 종목 생애주기·티커 변경, RSS 사실 검증·증분 효용 |
| 기업가치·예측 | 새 자동 세션의 실제 LLM 호출·실패/예산 전환 관측, 구조화 수치 예측·시나리오·reverse DCF 입력, 스킬별 공정 A/B |
| 퀀트 전략 | **등록된 공통 비교의 예산 갱신 후 실제 실행**, 별도 Forward, 투자 가능 시장/섹터 benchmark와 배당 조건 통제 |
| 통합 판단·위험 | 승인된 sleeve 결합, USD/KRW 환율·통합 위험 계약, 회사 분석의 실행 승격은 별도 검증 |
| 실행·원장 | 여러 세션 Forward, corporate-action/배당, 실제 재부팅·장애 운영 관측. Live는 계속 차단 |
| 독립 복기 | 실제 1/5/20 성숙 라벨, 동시점 시장·섹터 초과성과, 수치 예측 실현값, 원인 분류 독립 정답 |
| 자율 연구 | 공통 adapter 확대, 신규 최종 결과 격리, Hermes/RD-Agent 등의 증분 가치 검증. 자동 승격 없음 |

따라서 현재 증명한 범위는 **통합 운영 코드·실제 제한 수집·기존 Paper/복기 재개·예산 차단·백업 복원·예약 설치**다. 완료 기준 7의 새로운 공통 A/B 실측과 지속 Forward 효과는 남아 있으며, 7개 팀의 투자 효능·장기 초과수익·실거래 적합성을 완료로 표시하지 않는다.

<!-- TASK5_FOLLOWUP_START -->
## 9. Task 5 마무리 실증 — 자동 관측

관측 시각(UTC): 2026-11-22T01:57:14.198502+00:00. 기준 시각: 2026-11-13T02:03:58.978493+00:00.

- 공통 A/B: `FORWARD_REQUIRED`. Factory 오늘 예약 0건. 다음 UTC 예산 갱신: 2026-11-23T00:00:00+00:00. 기존 원장과 동일 input hash만 확인한다.

- 반복 사용량 증분: `{"logical_calls": 1842, "wire_calls": 2907, "input_tokens": 0, "output_tokens": 0, "journal_bytes": 20528895, "raw_bytes": 338098, "database_bytes": {"ops": 21839872, "review": 73728, "US": 24576, "KR": 237568}, "record_counts": {"ops": 12385, "review": 42, "US": 10, "KR": 6}}`. DB 증가는 page 할당·VACUUM 영향을 포함한다.

- 신규 사후 평가: `{"PENDING": 19, "MATURED": 0, "INSUFFICIENT_EVIDENCE": 0}`. 미성숙/불충분 결과를 완료로 간주하지 않는다.

- 실제 서버 재부팅 관측: 미검증(기준 이후 boot ID 변화 없음). PG start: 2026-11-13T02:06:10.991148+00:00.

- US 다음 세션 2026-11-13 / open 2026-11-13T14:30:00+00:00: `SESSION_TIME_REACHED_REQUIRES_EVENT_EVIDENCE`; 새 판단/기업분석/체결·상태: `{"fills": 0, "new_decisions": 0, "new_company_analyses": 0, "new_analysis_results": [], "states": [["DECIDED", 1], ["INVALIDATED_VERSION", 1]]}`.

- KR 다음 세션 2026-11-16 / open 2026-11-16T00:00:00+00:00: `SESSION_TIME_REACHED_REQUIRES_EVENT_EVIDENCE`; 새 판단/기업분석/체결·상태: `{"fills": 1, "new_decisions": 1, "new_company_analyses": 1, "new_analysis_results": [["stock_company_analysis", "FAILED", "FileNotFoundError", "2026-11-13 06:38:01.337930+00:00"], ["stock_quant_analysis", "CANDIDATES", "PREREGISTERED_RULE_EVALUATED", "2026-11-13 06:38:00.806042+00:00"]], "states": [["COMPLETE", 1], ["HOLD_NO_REBALANCE", 1], ["NO_TRADE", 3]]}`.

실제 공통 A/B 결과(재사용 역사 진단, 신규 Forward 아님): `{"api_calls": 0, "cases": 1133, "evidence_class": "REUSED_HISTORICAL_DIAGNOSTIC_CURRENT_SURVIVOR_UNIVERSE", "independent_forward_cases": 0, "input_hash": "dbc20c1993bb2b8a455a83095da3ea7ec3fe7e0c2d6476848c03f711403da6aa", "limitations": ["Current survivor seeds, not historical point-in-time membership", "Repeated historical tail is not independent holdout", "Dividend and total-return conventions not harmonized", "No automatic selection or promotion"], "model_tokens": 0, "paired_metrics": {"EQUAL_WEIGHT_STOCKS": {"cost_in_account_currency": 1481.63879138436, "currency": "USD", "fills": 3499, "mdd_pct": -27.489994306153154, "return_pct": 263.3710422733519, "sharpe": 1.2334697493964542, "turnover_multiple_initial": 24.555981914900848}, "MOM63_STOCKS": {"cost_in_account_currency": 15156.911395941712, "currency": "USD", "fills": 3313, "mdd_pct": -14.52574864446252, "return_pct": 157.1870036948449, "sharpe": 1.3050307843483426, "turnover_multiple_initial": 241.06680372708135}}, "period": ["2022-05-09", "2026-11-11"], "promotion_status": "NOT_ELIGIBLE", "status": "FORWARD_REQUIRED", "team": "quant", "worker_hash": "588616040bd983a7094228090f46ddce9079f68ca28baec82fc18d5a16678445"}`

최근 실제 tick: `{"at": "2026-11-22T01:57:11.852408+00:00", "markets": [{"market": "US", "phase": null, "last_complete_session": null, "decision_id": null, "paper_status": null, "status": "HOLD_ONLY_OR_ABSTAIN", "reason": "price revision quarantined"}, {"market": "KR", "phase": null, "last_complete_session": null, "decision_id": null, "paper_status": null, "status": "HOLD_ONLY_OR_ABSTAIN", "reason": "PROVIDER_OR_DATABASE_FAILURE"}]}`

근거: `runtime/task5/verification/{baseline.json,samples.jsonl,latest.json}`. 이 관측기는 조회·기록만 수행하며 주문·모델·외부 API·Factory 실행을 추가하지 않는다.
<!-- TASK5_FOLLOWUP_END -->

## 10. 마무리 실증 수동 확인 — 2026-11-13 11:08 KST

**완료된 확인과 아직 도래하지 않은 관측을 구분한다. 이번 추가 작업으로 Task 5 전체 완료를 선언하지 않는다.**

| 요청 | 현재 판정 | 실제 근거·후속 시점 |
|---|---|---|
| BLOCKED 공통 A/B | 자연적인 예산 대기 | 기존 UTC일 실험 예약 1건 유지. 2026-11-14 09:00 KST 이후 기존 단일 운영 tick이 같은 등록 입력/worker로 실행할 예정. 이번에 예산을 추가하거나 새 비교를 실행하지 않음 |
| 다음 미국 세션 | 자연적인 거래 세션 대기 | 공식 달력 2026-11-13 23:30~11-14 06:00 KST. 아직 미래이며, 체결을 강제하지 않음 |
| 다음 한국 세션 | 자연적인 거래 세션 대기 | 공식 달력 2026-11-16 09:00~15:30 KST. 현재 11-13 세션 종료 후 수집/분석도 기존 tick에서 관측 예정 |
| 실제 성숙 라벨 | 자연적인 데이터 대기 | 다음 공식 세션과 적격 NAV가 필요. 신규 수치 예측·결과를 만들지 않음. 최초 가능한 1세션 라벨도 실제 체결/close mark 계약 충족 여부에 따라 달라짐 |
| 동일 입력 반복 비용 | 완료, 짧은 cache 진단 | systemd 서비스 5회 실제 반복. 아래 실측. 거래 세션/모델 호출이 발생한 장기 표본과 구분 |
| 프로젝트 DB 재시작 복구 | 완료 | 전용 container만 실제 restart, PG 시작 시각 변경 확인, timer 재개 성공, 원장/판단 hash 보존 |
| 실제 서버 재부팅 | **미검증** | 호스트 boot ID는 동일. user timer enabled/active·linger 및 DB restart policy 확인은 재부팅 실증의 대체가 아님 |

### 반복 실행 실측과 예약 간격 판단

측정 구간: 2026-11-13 02:06:52~02:07:00 UTC. 동일 완료 세션 snapshot을 사용하는 systemd oneshot 5회, 모두 exit 0.

- tick 평균 **0.762초**, 프로세스·관측기 포함 서비스 호출 약 **1.64초/회**.
- 외부 논리 API **+0**, OAuth/재시도 포함 wire **+0**, 모델 input/output **+0 token**, 원문 파일 **+0 bytes**.
- 해당 서비스 journal 출력 **+30,310 bytes**. ops DB **+16,384 bytes / 기록 +5개**. US/KR/복기 DB 증가 **0 bytes / 기록 +0개**.
- 별도 관측 JSONL은 측정 전후 수동 표본을 포함한 7개 표본에서 **16,831 bytes**를 추가했다. 위 journal/DB 증가량에 포함하지 않았으며 삭제하지 않고 실증 근거로 보존한다.
- 같은 cache 상태만 하루 288회 지속된다는 단순 환산은 journal 약 **1.75 MB/일**, ops DB 약 **0.94 MB/일**이다. 짧은 구간의 page 할당 실측을 환산한 참고값이며 실제 하루 측정/예측으로 주장하지 않는다. 수집·LLM·백업·새 session 및 관측 JSONL 저장량은 별도다.
- 이 측정에서 과도한 반복 API/모델 사용이 없고 비용이 작아 **5분 간격을 유지**했다. 새로운 세션·일일 예산 갱신 이후의 사용량은 다음 관측으로 확인한다. 5분마다 모델을 호출하거나 전 종목 가격을 새로 받는 설정은 추가하지 않았다.

근거: `runtime/task5/verification/repetition_result.json`. 5회는 진단 호출이며 5개의 독립 Forward 관측으로 집계하지 않는다.

### 재시작 실증과 추가 구현 범위

`quant-task3-postgres`의 label/loopback 포트를 확인하고 기존 timer를 잠시 정지했다. 전용 DB container만 재시작한 후 연결 수용 상태와 원장을 확인하고 timer를 다시 시작했다. PostgreSQL 시작 시각은 `2026-11-12 23:32:38.509371 UTC` → `2026-11-13 02:06:10.991148 UTC`로 바뀌었다. 시작 직후 `pg_isready`는 일시적으로 rejecting을 반환했고 이후 accepting을 확인했다. 이를 무중단이라고 표현하지 않는다.

US/KR의 `stock_account/position/fill/nav`, `investment_run`, immutable record ID/hash 전체의 재시작 전후 hash가 일치했다. US 체결 0→0, KR 1→1이며 이후 실제 운영 oneshot은 success/exit 0, timer는 enabled/active다. 근거: `runtime/task5/verification/restart_{before,after,result}.json`.

추가 코드는 **조회 전용 후속 관측기** `operations_verification.py`, 기존 CLI의 관측기 호출, 관측기 단위 시험 2개다. 기존 투자/주문 알고리즘·Live/승격·Factory 계약/연구 원장은 변경하지 않았다. 새 scheduler는 없다. 기존 oneshot 종료 직전에 관측기를 호출해 다음을 보존한다.

- `runtime/task5/verification/baseline.json`: 이번 실증 기준 시각·누적 사용량·대상 세션.
- `samples.jsonl` / `latest.json`: DB/원문/journal·토큰 증가, 신규 분석/판단/체결/복기 상태, 실제 Factory 동일 입력 결과, host/PG 재시작 관측.
- 보고서 **9절의 전용 marker 구간**: 다음 실제 실행에서 자동 갱신. 기존 본문과 이 수동 실측 기록은 보존한다. 시각 도래만으로 세션 검증 완료 판정을 하지 않는다.

관측기는 외부 데이터·LLM·브로커·Factory 실행 API를 호출하지 않는다. PostgreSQL 연결에는 `default_transaction_read_only=on`을 사용한다. 실제 A/B 실행은 기존 `operations.tick`의 예산 예약 경로만 사용한다. 미래 예산·세션 결과는 이 문서를 작성한 시점에 아직 관측하지 못했으며, 자동 기록이 생긴 뒤에만 실측으로 판단해야 한다.

### 영향 범위 시험

- compileall: 통과.
- 새 관측기 2개 시험 + AGENTS의 최소/운영 안전 회귀 9개 파일: **55 passed, 39.30초**, 실패/스킵 0. 이미 완료된 190개 전체 suite는 반복하지 않았다.
- 필수 V104 Forward 명령 재실행: 결과는 `runtime/task5/verification/v104_forward_console.txt` 원문 기준. 새 Forward를 만들어내거나 후보를 활성화하지 않았다.
- 관측기 실제 호출, systemd 5회, DB 재시작은 실제 실행이다. 미래 거래 세션·성숙 결과·Factory 예산 갱신 이후 A/B는 여전히 대기다.

추가 완료 조건은 **등록된 A/B의 실제 결과 원장**, **다음 KR/US 세션에서의 수집/독립 분석 또는 기권/체결 또는 미체결/복기 기록**, **적격 성숙 라벨 또는 근거 있는 대기**, **새 세션의 자원 증가량**이다. 현재 시간이 지났다고 가정해 이 항목을 완료 처리하지 않는다.

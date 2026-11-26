# Task 4 · 독립 복기·자율 연구·검증 구현

2026-11-13 KST · 미국 개별주식 우선 / 한국 병행 · Task 3 원장은 읽기 전용으로 사용했다.

## 핵심 결과

- **실제 판단 → 결과 비공개 과정 복기 봉인 → 성숙 여부 확인 → 가설 → 공식 Factory 등록 → 별도 프로세스 A/B → 판정**을 한 번 완결했다. 실제 국내 Paper 판단과 후속 미국 판단을 사용했다. 수익이나 현재 NAV를 과정 평가에 전달하지 않았다.
- 발견한 문제는 국내 초기 판단의 **알고리즘 버전 해시 누락**이다. 수익·종목 선정이 틀렸다는 판정이 아니라 재현성 결함으로 `UNDETERMINED`를 기록했다. 기존 JSON 무결성 검사와 필수 버전 검사 추가안을 비교했다.
- 실제 기록 2건에서 누락 검출 진단 정확도는 **0.5 → 1.0**, 놓친 결함은 **1 → 0**이었다. 두 경로 모델 호출/토큰은 각각 0이다. 사전 기준 12건에 못 미쳐 결과는 **INSUFFICIENT_EVIDENCE**이며, 투자 효능·독립 사람 채점·신규 Forward 개선을 입증하지 않는다.
- 실제 6개 판단을 일일 진입점에서 점검했다. 모든 보유 기간 결과는 **PENDING**이다. SEC 수집 실패는 별도 정보원 검증 과제로 등록했다. Factory에는 **가설 2건, 실행된 격리 실험 1건**이 있으며 반복 실행해도 추가 실험은 발생하지 않았다.
- 독립 복기 모델은 **gpt-6.1-terra**, 1회 실제 호출했다. Luna는 사용하지 않았다. 코멘트는 별도 비검증 기록이며 자동 원인 확정·전략 변경의 권한이 없다.
- **190 passed, 실패 0, skipped 0**. 신규 복기 시험 24개와 기존 안전/Paper/DB/Factory 회귀를 포함한다. 실제 프로세스 중단·lease 회수, 별도 프로세스 재실행, DB/Factory 백업 복원도 확인했다. Task 3 미국·국내 데이터 6개 테이블의 해시는 이전 백업과 모두 일치했다.

**구현 완료 범위는 복기·연구 등록·제한된 실험의 연결이다. 투자 수익을 스스로 개선했다는 증거는 아직 없다.** 성숙한 시장 라벨 수집, 정보원/프롬프트/전략별 평가 worker 확장, 다중비교 통계, 지속 운영은 아래 공백으로 남긴다. 기존 운용 전략·주문 경로·Live 잠금과 승격 설정은 변경하지 않았다.

## 1. 실제 코드와 저장 책임

| 파일 | 구현 |
|---|---|
| `investment/review.py` | Task 3 읽기 전용 Source, 당시 정보의 whitelist packet, 과정 평가·봉인 계약, 성숙 세션별 수익/초과수익/MDD·제한된 Sharpe·등록된 예측 MAE/Brier·반사실 평가 |
| `investment/review_execution.py` | 과정 봉인 후에만 원본 fill/quote를 연결해 비용·슬리피지·quote→commit 시간을 계산 |
| `investment/review_engine.py` | 일일/단일 판단 처리, 즉시 사건 연구, 가설 생성/NO_CHANGE, Factory 연결, 별도 프로세스 평가와 durable 결과 cache |
| `investment/review_jobs.py` | PostgreSQL 작업 큐, 고정 job ID, lease·소유권·최대 재시도, 실패/대기/완료·후속 관측 상태 |
| `investment/review_experiment.py` | 필드 추적성 진단의 Champion/Challenger/Evaluator. 같은 입력, 고정 worker hash, 0회 모델 호출; 생성 코드를 실행하지 않음 |
| `investment/review_access.py` | 제안자에게 과정 복기만 제공. 최종 결과/holdout과 evaluator 입력은 API에서 거부 |
| `investment/review_model.py` | 결과를 숨긴 독립 Terra 코멘트. 프롬프트/응답/버전/토큰 이벤트 저장, 도구 비활성화·인증 환경 제거 |
| `investment/review_shadow.py` | Hermes 호환 Shadow packet/응답 검증. 허용 연구 ID·입력 해시 검사, 주문/승격/스케줄 변경 거부 |
| `alpha_research_factory.py` | 기존 기능을 유지하고 review-origin 등록 API 추가. 필수 계약·의미 중복·일일 예산·실행 전 예약·해시·결과 불변성·승격 제한 |
| `config/task4_review_contract.json` | 전략별 평가 세션 1/5/20 등, 오류 분류, 일일 제안 3건·실험 1건, 최소 사례 12건, 허용 트리거·lease·Shadow 권한 |
| `run_review_cycle.py`, `run_review_daily.py`, `run_review_event.py` | 단일 판단, 미국/국내 일일 점검, 중요 사건의 즉시 연구 등록 CLI. 새 cron/Gateway는 배포하지 않음 |
| `score_review_outcome.py` | 봉인된 정책/입력을 그대로 사용해 명시적 세션 라벨을 평가·후속 작업 등록. 라벨이 없거나 미성숙하면 대기 |
| `backup_review_state.py`, `probe_review_restart.py`, `check_task4.sh` | 전용 DB/Factory·코드 백업/새 DB 복원, 실제 중단 시험, 재현 가능한 검증 묶음 |

위 `investment/` 경로는 `src/quant_harness/investment/`, CLI는 `scripts/` 아래다. 원본 Task 3 DB에는 연결 옵션 `default_transaction_read_only=on`을 강제하며, 복기 DB는 별도 `quant_task3_review`다. `investment_record`의 기존 불변 기록 API를 재사용하고 신규 `review_job`을 추가했다. 거래 테이블을 새로 복제해 권위 원장을 만들지 않는다.

과정 packet에는 결정 시점 이전 분석·인용·원본 해시·계약·목표·intents만 포함된다. fill·NAV·실현 수익·나중 가격은 가져오지 않는다. 기존 자료에 없는 과거 기업 정보를 채우지 않았다. 과정 기록과 정책 snapshot, worker hash를 먼저 저장한 뒤 evaluator가 체결/NAV를 읽는다. 사후 자료가 섞인 packet, 잘못된 의사결정 ID, 정책/입력 불일치, 미래 라벨, 결측 평가 가격은 차단한다.

## 2. 실제 Task 3 복기

| 대상 | 결과 |
|---|---|
| KR `4389b058…90ac` | `algorithm_hash`가 없어 `PROVENANCE_GAP`. 분류 UNDETERMINED, 누락 자체의 확신 1.0, 수익 영향은 미확인 |
| US `1632759b…9424` | 버전 해시는 있음. 투자 전략 변경 제안은 NO_CHANGE. SEC 실패는 별도 정보원 연구로 관리 |
| 그 외 기존 판단/기권 포함 6건 | 동일 daily 진입점에서 점검. 기존 가설 family를 참조해 중복 연구·실험을 만들지 않음 |
| 1/5/20세션 결과 | 공식 세션별 평가 라벨이 없어 모두 PENDING. 당일 비용 차감 NAV를 성숙 수익률로 대체하지 않음 |

기존 7개 원인 분류와 호환되도록 INFORMATION_MISSING, FORECAST_ERROR, SELECTION, TIMING, SIZING, EXECUTION, STOCHASTIC_LOSS 및 UNDETERMINED를 사용한다. 여러 원인과 개별 증거·확신을 기록할 수 있다. 확인된 입력/위험/권한/추적성 위반을 먼저 식별하고, 누락된 정보의 시장 전체 oracle·추론의 진실성·최적 타이밍은 자동 검증됐다고 주장하지 않는다.

성숙 평가에는 계약별 세션 calendar와 관측 시각·source hash가 필요하다. 세션 수는 전략 계약에서 읽으며 미래 calendar만 있다고 결과를 성숙 처리하지 않는다. 미성숙은 PENDING, 과거 세션이어도 필요한 NAV가 없으면 INSUFFICIENT_EVIDENCE다. 확률 예측은 Brier, 점 예측은 절대 오차, 대체 행동은 **당시 등록된 ID만** 채점한다. 현재 실제 판단에 수치 예측 계약이 없어 실제 예측 정확도는 미평가다. 정상 손실 표시는 낮은 확신의 가능성으로만 기록하며 단일 손실로 원인을 확정하지 않는다.

### 실행 비용과 독립 모델 코멘트

실제 국내 Paper 9주 매수의 수수료 **282.2913 KRW**, quote 대비 가상 체결 슬리피지 **942.2404 KRW**, 합계 **1,224.5317 KRW**를 원본 이벤트와 재연결했다. quote→DB commit은 약 **0.745초**였다. 이는 Task 3의 합성 Paper 체결 계약에 따른 비용으로 실제 거래소 체결이나 나쁜 판단의 증거가 아니다.

Terra는 이후 수익을 보지 않고 재현에 필요한 중간 계산/버전 자료 부족과 서로 다른 입력 해시의 범위가 불명확하다는 코멘트를 남겼다. 약 10.15초, CLI usage 입력 26,095·출력 296 tokens(캐시 입력 9,088)이었다. 금액은 미상이다. 모델의 높은 자체 확신을 사실 검증/원인 확정으로 승격하지 않았고, 모델 간 동등 예산 A/B나 독립 사람 채점은 수행하지 않았다.

## 3. 가설·공식 Factory·실험

공식 위치: `runtime/alpha_research_factory/task4/`. 기존 Factory의 JSON 계약·append-only registry·해시/중복·예산·권한 경계를 확장했으며 별도 승인 원장을 만들지 않았다. 새로운 review schema를 사용하므로 기존 고정 LLM 제안의 DRY_RUN/veto 동작은 유지한다.

| 가설 | 등록·검증 상태 |
|---|---|
| 필수 알고리즘/입력/계약 추적 검사 | 실제 버전 누락을 근거로 등록. attempt `dbe32b7424bda037159389555eec13776f22cafc49c6e3c5ba3bd4cc6ab1f62d`. 두 실제 기록의 격리 비교 실행, INSUFFICIENT_EVIDENCE |
| 공식 정보원 검증/수집 가용성 | 실제 SEC FAILED_CATALOG를 근거로 즉시 등록. PENDING_EVIDENCE, 실험 미실행. 접근/정답 자료 부족을 숫자로 채우지 않음 |

첫 실험의 Champion은 Task 3의 **JSON 무결성 확인 범위**, Challenger는 **필수 버전 필드의 존재 확인을 추가한 진단**이다. 투자 전략 Champion이나 최상의 복기 모델이라는 뜻이 아니다. 두 실제 원본의 schema 기준 누락 여부를 비교했으며, 복기 내용 전체의 정확성을 검증한 것도 아니다.

| 실측 지표 | Champion | Challenger |
|---|---:|---:|
| 사례 수 | 2 | 2 |
| 필드 누락 진단 정확도 | 0.5 | 1.0 |
| 놓친 누락 | 1 | 0 |
| 모델 호출/토큰 | 0/0 | 0/0 |

최소 사례 12건, 새 Forward 증거, 독립 검토가 부족하다. 편의 표본·재사용 자료·기계적 필드 기준의 진단이므로 투자 품질·수익 개선이나 통계적 일반화를 주장하지 않는다. 다중비교가 해소된 alpha 결과도 아니다. 실제 최종 상태는 INSUFFICIENT_EVIDENCE이고 자동 승격은 0건이다.

계약에는 문제 근거·변경 대상·예상 효과·반증·비교군·입력·worker hash·고정 분할·예산·중단 조건을 필수로 요구한다. 실행 전에 예산을 예약하며 파일 잠금/결과 cache와 DB job lease로 재실행을 방지한다. 입력·코드·결과 변경, 표본 기준 하향, 평가 결과를 품은 제안, APPROVED 상태를 거부한다. 같은 문제·방법에 새 데이터 hash만 붙여 새 가설을 양산하지 않고 기존 family의 후속 연구로 연결한다.

정보원/프롬프트/위험·전략/복기 문제에 대한 등록·후속 작업 라우팅은 있으나, **현재 실제 실행 가능한 A/B worker는 추적성 진단**이다. 나머지 유형의 전용 수집·예측/수익 evaluator와 검증 데이터는 추가 연결이 필요하다. 임의 LLM 생성 코드, 전략 탐색 grid, 미구현 worker를 실행·통과로 기록하지 않았다.

## 4. 재사용·권한·장기 연속성

- Task 3 Store·불변 원문/lineage·Paper 회계와 실제 기록을 재사용했다. source DB/계좌/활성 전략/원문은 수정하지 않았다. `runtime/task4/source_integrity_proof.json`은 Task 3 백업 대비 미국·국내 6개 테이블의 동일성을 기록한다.
- V103의 역사 연구 시도·승격/다중비교 영역은 유지한다. 신규 거래별 복기는 V103의 과거 보고서 집계를 대체하지 않으며, 기존 V103 회귀를 실행했다. 새로운 다중전략 통계 승격을 구현했다고 주장하지 않는다.
- TradingAgents의 독립 반론·과정/결과 분리, InvestSkill의 계획/반증 기록, RD-Agent의 가설→실행→평가 단계는 선택적으로 참고했다. 해당 프레임워크 전체나 자동 코드 생성 런타임을 설치·실행하지 않았다.
- Hermes는 허용 연구 ID/입력 hash만 포함한 Shadow adapter와 응답 검증을 구현했다. 권한·잘못된 기억 참조는 테스트에서 거절했다. **외부 Hermes 검색/위임 실제 실행과 비용·회수 개선 비교는 미실행**이다. 모델의 자체 실행 주장만으로 Hermes 실측을 인정하지 않는다. Gateway/Cron을 추가하지 않았다.
- 제안자 view는 봉인된 과정만 읽고 최종 평가/holdout 요청을 거부한다. 격리 worker는 allowlist의 신뢰 코드이며 인증 환경을 전달하지 않는다. 이는 임의 생성 코드에 대한 OS 보안 sandbox 검증을 뜻하지 않는다. 외부 생성 코드를 연결하려면 별도 계정/파일·네트워크 격리가 필요하다.
- `runtime/task4/backups/final_20261113/`에 복기 DB와 Factory·코드를 보관했다. 새 DB `quant_task3_review_restore_005907`에 **114개 기록 hash, 작업 44개**를 복원했다. 개발 중 버전별 이력을 포함하는 수치이며 44개 신규 투자 가설이라는 뜻이 아니다. 복원된 DB/Factory로 다시 실행해 기존 가설 참조·PENDING을 복구했고 실험을 재실행하지 않았다.

## 5. 검증과 재현

**190 passed / 0 failed / 0 skipped**, 약 65.46초. 전체 저장소 테스트 전부라는 뜻은 아니다. JUnit: `runtime/task4/regression.xml`. 신규 24개는 미래 결과 접근 거절, 성숙 전 PENDING, 확률적 손실/이익과 과정 오류 분리, 급락·반등, 등록 예측·대체 행동만 채점, 중복·lease·실행 cache, Factory 예산/변조/표본/승격, 실제 Task 3 읽기 전용 연결 등을 검사한다. 나머지는 AGENTS 최소·운영 추가 및 기존 Paper/DB·Factory/뉴스 회귀다. 컴파일·pip check·diff check도 성공했다.

실제 별도 프로세스 시험에서는 checkpoint 저장 직후 **주입한 종료 코드 23**으로 작업자를 종료했다. 다른 프로세스가 만료 lease를 회수하고 checkpoint를 다시 계산하지 않고 완료했다. 이 시험은 SYNTHETIC_CRASH_PROBE이며 Forward 투자 성과가 아니다. `runtime/task4/crash_probe.json`에 결과를 보존했다.

필수 환경 변수의 URL 값은 전용 로컬 연구 DB를 가리켜야 한다. 아래 명령은 이미 설정된 환경을 사용하며 `.env` 값을 출력하거나 Git에 추가하지 않는다.

```bash
# TASK4_SOURCE_KR_URL / TASK4_SOURCE_US_URL: 기존 Task3 DB, 코드에서 read-only 강제
# TASK4_REVIEW_DATABASE_URL: 별도 quant_task3_review
.venv/bin/python scripts/run_review_cycle.py \
  --decision-id 4389b05872e93e4097ab69f10896f4e83e8c88bc72495bc639a2de96a4b990ac \
  --compare-id 1632759bcb9f9efcd9e13fffb9cbffb77855da766582664497f8dfd871739424
.venv/bin/python scripts/run_review_daily.py
# 성숙 라벨 수신 시: 최초 봉인된 packet/policy를 사용, 원 복기는 수정하지 않음
.venv/bin/python scripts/score_review_outcome.py --process-id PROCESS_ID --labels VERIFIED_LABELS.json
# TEST_DATABASE_URL / TASK3_STOCK_TEST_DATABASE_URL / TASK4_TEST_DATABASE_URL / TASK4_SOURCE_KR_URL 필요
bash scripts/check_task4.sh
.venv/bin/python scripts/probe_review_restart.py
.venv/bin/python scripts/backup_review_state.py --output NEW_BACKUP_DIRECTORY --restore-check
```

최초 복기/실험은 `runtime/task4/cycle_result.json`, 최근 일일 결과/내보내기는 `runtime/task4/daily/`, 재시작 결과는 `runtime/task4/restart/`에 있다. evaluator 전용 재현 입력과 일치 worker는 `runtime/task4/private/`에 보존했다. V104 Forward runner는 `NO_ENABLED_CANDIDATES`, append 0, Live false를 반환했다.

## 6. Task 5에 남은 일

1. 공식 거래 세션·평가 NAV·시장/섹터·실적 라벨을 검증해 수집하는 자동 커넥터와 단일 일일 예약기에 연결한다. 현재 라벨 importer의 calendar/provenance 표시는 신뢰된 evaluator 입력 계약이며 외부 자료를 자동 인증하는 기능이 아니다.
2. 수치 예측 원본과 전략별 사전 대체 행동을 더 축적한다. 기존 서술 예측을 사후 수치로 바꾸지 않는다. 성숙 전 결과와 정상 손실을 오류·개선 성공으로 세지 않는다.
3. 정보원/프롬프트/매매/복기의 각 전용 worker, 독립 정답·채점자, 데이터 분할·다중비교·비용 제약을 연결한다. 실제 투자는 이미 사용한 역사 자료의 반복 최적화 대신 동결 후 Forward로 평가한다.
4. 중요한 문제가 없으면 NO_CHANGE, 기존 과제이면 후속 관측으로 유지한다. 후보가 생겨도 계약된 평가 기간·별도 사람 승인 전 활성 방식·Champion·Live를 바꾸지 않는다.
5. Hermes 또는 RD-Agent의 외부 작업자를 연결할 필요가 입증되면 기본 DB 작업자 대비 동일 업무·예산으로 Shadow 비교한다. 생성 코드의 hard sandbox, 상시 scheduler/Gateway 권한, 백업 주기/RPO·복구 시간을 검증한다.

현재 검증은 **복기/연구 경로의 기능적 연결과 제한된 감사 개선 실험**이다. 새로운 매매 전략의 초과수익, 예측 향상, 완전한 자율 alpha 연구의 효능은 미검증으로 남긴다.

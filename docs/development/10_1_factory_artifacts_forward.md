# Task10.1 — 운영 Factory 복구·산출물 보존·독립 Forward Shadow

## 핵심 결과

**운영 Factory의 최신 전체 백업을 DB 소비 기록과 대사하여 복구했다. 미국 3개·한국 2개 연구용 Shadow를 새로 봉인하고 기존 단일 타이머에 연결했다. 아직 새 거래 세션이 완료되지 않아 체결·Forward 수익·주간 연구 성과는 PENDING이다.**

| 완료 기준 | 판정 | 근거 / 제한 |
|---|---|---|
| Factory Authority | PASS — 대사한 snapshot 복구 | 제안 7·예약 3·결과 3건 복구, 계약/원장 해시·이전 백업 prefix·DB 완료 기록 일치. 로그에 없는 수동 쓰기의 부재까지 증명하지는 못함 |
| Artifact Hygiene | PASS — 감사·보존 정책 | 원본 9,573개 감사. 중복은 식별했지만 참조된 경로를 삭제하지 않음. 파괴적 증거 삭제 0 |
| Forward Readiness | 준비 완료 / 실제 성과 PENDING | 5계좌·모델·정책·첫 판단 봉인, 실제 원문 수집·동결 모델 추론 및 정상 타이머 호출 확인. 최초 적격 세션 2026-11-16 |
| Feedback Readiness | PARTIAL | 성숙도·IC·모델오차·동일 노출 평가와 분리 연구 요청 Queue 연결 구현. 미래 주간 Review 및 native 후속 연구 실제 실행은 아직 없음. prospective 연구 executor는 미활성 |

기존 Task10 역사 성과, 팀2, 공식 Paper 전략, Champion·Live 잠금을 바꾸지 않았다. 이 작업의 LLM 호출·재학습·신규 알파 승인·실주문은 모두 0이다. Task10의 **미국 +1.62% / Q-only +8.32%**를 새 Forward 실적으로 가져오지 않았다.

## 1. 운영 Factory의 권위와 복구

### 실제 경로와 저장 역할

- `quant-operations.service`의 WorkingDirectory는 `/home/ansy/app/trading`, 실행기는 `scripts/run_autonomous_operations.py`, EnvironmentFile은 `runtime/task5/service.env`다. 경로 변경·별도 Factory 환경변수 override 증거는 없었다. 인증 값은 출력하지 않았다.
- 공식 Factory 권위는 `runtime/alpha_research_factory/task4/`의 계약·attempt·예약·결과·state event 파일이다. PostgreSQL은 연구 기록/Queue의 권위지만 Factory 모든 제안·예약의 완전한 미러는 아니다.
- 조사 시작 시 위 경로는 실제 부재했다. 이를 예산 사용 0으로 해석하지 않았다. 기존 `authority_audit.json`의 `BLOCKED_AUTHORITY_UNRESOLVED`는 **복구 전 관측**으로 보존했다.
- Task10의 별도 `quant_task3_task10_replay` 성공을 운영 상태로 대체하지 않았다. 코인 DB와 기존 Paper 원장도 복원 대상으로 삼지 않았다.

### 최신 백업을 그대로 믿지 않고 확인한 내용

기존 `runtime/task5/backups/20261115T030249053499/evidence_code.tar.gz` 안에 **11월 15일 완료 기록까지 포함된 전체 Factory 원장**이 있었다. Task10 당시 감사에서 발견한 오래된 `restored_files/` 디렉터리와 구별된다.

1. archive 자체의 manifest SHA-256을 확인했다.
2. 11월 13~15일의 6개 archive에 대해 각각의 원장이 복구본의 byte prefix임을 검증했다. 이후 기록이 이전 기록을 바꾸지 않고 추가됐음을 확인했다.
3. 계약 7개와 attempt의 contract hash를 검증했다. 예약 3개·결과 3개가 연결되고, 공식 중복 등록·기존 예약 재호출·결과 재기록이 격리 복원본에서 불변임을 확인했다.
4. `quant_task3_review`, `quant_task3_ops`, `quant_task3_task8b_research`의 실제 완료 결과 3건이 모두 복구본과 일치했다. 운영 로그와 현재 dispatcher도 같은 경로·DB를 사용한다.
5. 복구 전에 위 3개 DB를 새 dump로 보존했다. review dump를 임시 DB에 실제 복원해 138개 기록을 확인하고 임시 DB만 제거했다. Factory 파일은 별도 staging에서 검산한 뒤 **부재한 경로에만 atomic rename**했다.
6. 실제 운영 경로를 다시 열어 Task9.2의 기존 numeric audit를 재호출했다. 결과는 기존 `INSUFFICIENT_EVIDENCE` 캐시였고, 등록·예약·결과 파일 hash 변화와 추가 실험은 0이었다.

복구 시각 UTC일(2026-11-15)의 사용량은 **제안 1건·실험 예약 1건**으로 유지했다. 다음 UTC일의 신규 연구를 앞당기거나 일일 한도를 초기화하지 않았다. 새 승인 이력도 만들지 않았다.

**복구 신뢰도의 한계:** 마지막 snapshot 이후 로그에 남지 않은 수동 파일 쓰기까지 없었다고 증명할 수는 없다. 확인 가능한 scheduler/DB 소비 결과는 모두 대사했다. 새로운 불일치가 발견되면 원장을 합성하지 말고 차단해야 한다. 실제 OS 재부팅은 하지 않았다.

근거: [초기 권위 감사](../../runtime/task10_1/authority_audit.json), [복구 결과](../../runtime/task10_1/recovery_result.json), [최종 권위/예산](../../runtime/task10_1/authority_current.json), [실제 재열기](../../runtime/task10_1/live_reopen_check.json), [복구 전 backup](../../runtime/task10_1/pre_recovery_backup.json), [복구 후 archive 검증](../../runtime/task10_1/recovered_backup_check.json).

## 2. Queue·운영 실행 상태

실제 Queue를 읽어 보니 다음 상태가 남아 있었다.

- Task4: 과정 복기 20 DONE·1 NO_CHANGE, 결과 복기 21 PENDING_LABELS, 사건 연구 4 PENDING_EVIDENCE.
- Task9.2: numeric audit는 11월 15일 실제 DONE, 근거 복기 2 DONE. 이전 BLOCKED 기록도 그대로 남아 있다.
- Task8b·Task9.x: `FACTORY_OPPORTUNITY_FOLLOWUP`, 가격 재평가, 과거 실험 후속 요청 등 READY/PENDING 작업이 있다. **모든 Queue kind에 실행 worker가 존재하는 것은 아니다.** 알 수 없는 작업을 임의 코드로 실행하지 않았다.

격리된 기존 연구 DB에서 lease 만료→새 owner claim→이전 owner 커밋 차단→완료→재열기 후 중복 차단을 실제 시험했다. 복구 원장의 복사본에서는 동일 등록 중복 방지와 **이미 소진된 당일 실험 예약의 차단**을 확인했다. 이 시험들은 합성 장애 시험이며 운영 연구나 Forward 성과가 아니다.

`quant-operations.timer`를 새로 추가하거나 기존 타이머를 교체하지 않았다. 정상 예약 실행 로그에서 `task101_quant_shadow`와 지수 기준선 observer의 호출을 확인했다. 기존 Paper tick은 그대로 실행된다.

근거: [Queue/예산 시험](../../runtime/task10_1/queue_budget_probe.json), [정상 예약 로그](../../runtime/task10_1/scheduled_tick.log), [운영 진입점](../../scripts/run_autonomous_operations.py).

## 3. 독립 Forward 계좌와 사전 봉인

| 시장 | 계좌 | 동결 구성 / 지위 | 초기 자본 |
|---|---|---|---:|
| US | INITIAL_STATIC | 초기 Quanta + 초기 RD, 50/50 순위 결합 | $100,000 |
| US | ADAPTIVE_COMBINED | Quanta mutation + US RD 재학습, **FORWARD_REQUIRED** | $100,000 |
| US | QUANTA_MUTATION_ONLY | mutation + 초기 RD. 역사적 사후 분해로 선택한 연구 가설 | $100,000 |
| KR | INITIAL_STATIC | 초기 Quanta + 초기 KR RD | 1,000만원 |
| KR | MOM63 | 단순 기준선. Quanta/RD 알파로 표시하지 않음 | 1,000만원 |

한국의 기각된 재학습 후보는 적용하지 않는다. ETF는 위험 지표와 비교용이며 매수 대상이 아니다. 신규 계좌는 파일 기반의 별도 연구 원장이고 공식 Paper 계좌에 전략을 등록하지 않았다.

- Task10의 US38·KR20 개별주식과 시장 ETF 각 1개의 기존 연구 유니버스를 유지했다. Nasdaq 현행 종목 목록/DART 코드 목록과 최신 완료 가격으로 58개 기업의 정체성과 접근 가능성을 확인했다. DART 코드 존재만으로 거래소 상장·거래정지를 완전 인증한 것은 아니며 그 한계는 유지한다.
- 초기/재학습 checkpoint, 생성 모델 코드, 두 Quanta 공식, 실행 비용 설정·위험 규칙·원문/입력 hash를 봉인했다. worker/model hash가 바뀌면 관측기가 차단한다. 모델을 복사하거나 재학습하지 않고 read-only mount했다.
- 종목별 목표 20%·총 목표 80%, 상위 positive 4개, 63세션 시장 ETF 위험 규칙, 5거래세션 리밸런싱을 유지했다. 가격 변화에 따른 실제 비중 drift는 가능하다.
- 결정은 봉인 이후의 다음 공식 정규장 시가에서만 모의 실행한다. 이미 시작된 세션에는 새 결정을 소급하지 않는다. 첫 세션과 이후 NAV·체결은 기존 `replay_targets`/V77로 계산하고 저장된 과거 결과와 충돌하면 차단한다.

원본 계약/계좌: [최종 사전 계약](../../runtime/task10_1/forward/contract.json), [계좌 등록](../../runtime/task10_1/forward/registration.json), [실제 최초 판단](../../runtime/task10_1/forward/plans/), [관측기 코드](../../experiments/task10_1/forward.py).

### 현재 실제 판단과 첫 관측

**최초 신호의 자료 종료일은 11월 13일, 최종 봉인은 11월 16일 07:26 KST경으로 양 시장의 다음 정규장 개장 전이다.** 11월 13일까지는 feature context이며 Forward 투자 실적이 아니다.

| 시장 | 시장 위험 ETF 종가 | 63세션 평균 | 최초 판단 | 첫 적격 정규장 KST |
|---|---:|---:|---|---|
| US | SPY 754.37 | 764.91 | 3계좌 모두 현금 100% | 11/16 23:30~11/17 06:00 |
| KR | KODEX200 83,115 | 100,412.22 | 2계좌 모두 현금 100% | 11/16 09:00~15:30 |

이는 **기존 위험 규칙의 결과**이며 모델 입력 부족이나 매수 인원 강제의 결과가 아니다. 해당 규칙을 바꿔 거래를 만들지 않았다. 현재 체결 0건, 미래 정규장 NAV 0개이며 수익률·1/3/6개월 결과는 **PENDING**이다. 현금만 유지되더라도 다음 완료 세션부터 계좌 성과와 지수 상승의 기회비용을 평가한다.

S&P500(`^GSPC`)·KOSPI(`^KS11`)는 별도의 비거래 가격지수 adapter로 준비했다. SPY/KODEX200과 같은 지수라고 표시하지 않는다. 실제 새 지수 mark와 성과는 첫 Forward 완료 세션을 기다린다. 배당 포함 Total Return과 동일하다고 주장하지 않는다.

## 4. 실제 수집·PIT·초기 실패 처리

새 대형 수집기나 전종목 가격 DB를 만들지 않았다. 60자산의 제한된 최신 일봉과 현행 가벼운 종목 메타데이터만 조회했다. 기존 HTTP·정규화·V87·원본 격리 기능을 재사용했다.

- 첫 미국 시도는 V87 ticker padding 전달 오류, 한국은 Toss 단일 원가격과 기존 봉인 가격의 불일치로 차단됐다. 캐시된 catalog를 다시 쓸 때 발생한 immutable conflict도 남겼다. 이 실패를 정상 수집/Forward 성공으로 세지 않았다.
- 미국 식별자 padding을 맞추고, 한국 가격은 기존 Task10과 **같은 고정 우선순위/0.5% 기준의 Yahoo·Naver·Toss 두 공급자 대사**로 처리했다. 임계값을 완화하거나 가격을 평균·보간하지 않았다. 기존 Task10 원본은 바꾸지 않았다.
- 최종 60자산의 각 OHLC 대사·V87/revision 검사와 prefix를 저장하고 동결 모델 추론을 실행했다. 겹치는 과거 자료의 원관측 값은 보존하고 신규 완료 bar만 추가한다.
- 현재 실제 관측 시각과 가격 날짜를 구분한다. Bootstrap의 과거 가격/모델 출력을 새 Forward NAV나 성숙 IC에 넣지 않는다. 미래 정보가 없는 최초 신호와 그 뒤 실제 세션만 성과 대상이다.
- 기업행사·상장/휴장 자료의 독립 인증 및 배당 현금 처리에는 한계가 있다. 명목 가격 성과로 제한하며 split/큰 revision 불일치는 차단한다.
- 이 작업의 wire 예약은 **142회**다. catalog 관련 최초/재시도 조회는 별도 receipt/원문으로 남아 있으며 142가 모든 metadata 내부 요청까지 센 완전한 네트워크 계측값은 아니다. 일별 연구 wire 상한은 160이며 기존 운영 Factory 예산과 별개다. 별도 유료 데이터/API 구매는 없다.

초기 시도와 과정 평가 정합성 보완본은 `failed_bootstrap_v1/v2`, `pre_entry_v3/v4/v5`에 보존했다. 실제 미래 진입 전에만 봉인 버전을 갱신했고 모델·알파·비중·위험 규칙 및 기존 역사 성과는 변경하지 않았다.

근거: [원문/대사](../../runtime/task10_1/forward/observations/), [최초 성공 tick](../../runtime/task10_1/forward_tick_v3.log), [최종 재시작 tick](../../runtime/task10_1/restart_forward_tick_final.log), [지수 대기](../../runtime/task10_1/benchmark_initial.log).

## 5. 주간 Review와 실제 연구 실행의 구분

기존 `process_review`를 최초 판단에 적용해 결과를 보지 않은 과정 평가를 봉인했다. 현재 5개 계좌 모두 과정 평가는 NO_CHANGE다.

향후 관측기는 새 완료 세션마다 저장된 사전 판단만으로 계좌를 이어 계산한다. 5세션마다 다음을 평가하도록 구현했다.

- 실현 계좌 수익·보유 노출·ETF와 동일 노출 대조, 거래비용과 체결
- 실제 봉인 점수에 한정한 성숙 5세션 open-to-open IC/RankIC
- 초기/재학습 모델의 같은 label 구간 MSE
- 기존 `score_mature_outcome`에 실제 저장된 원문 관측 시각을 전달한 5/20/60세션 성숙도 평가
- 최소 20세션 및 연속 두 번의 약화 조건 전에는 변경 연구를 강제하지 않음

약화가 지속되면 Quanta 단독 변경과 RD 단독 재학습을 **서로 다른 typed Queue 요청**으로 등록하고 같은 계열 요청은 중복 차단한다. 기존 공식 review DB를 사용하며 신규 DB·상시 서비스는 추가하지 않았다.

**미완료:** 그 요청을 받아 실제 prospective native 연구·공식 Factory 사전등록/예약/평가까지 수행하는 typed executor는 활성화하지 않았다. 현재 새 주간 성과 자체도 없으므로 실제 후속 연구 0건이다. Queue 요청을 완성된 자기개선 실험이라고 보고하지 않는다. 운영 예산·기존 승인·독립 평가 조건을 지키는 해당 worker가 다음 우선순위다.

근거: [주간 평가/성숙 처리](../../experiments/task10_1/forward.py), [분리 후속 요청](../../experiments/task10_1/queue_followups.py), [최초 후속 상태](../../runtime/task10_1/followup_initial.log).

## 6. Task6~10 파일·중복 감사와 보존 정책

감사 범위는 `runtime/task6`, `task6_pre`, `task6_completion`, `task7`, `task8`, `task8b`, `task9_1~9_4`, `task10`의 실제 연구 산출물이다. 전체 upstream checkout/venv·프로젝트 전체 디스크를 같은 수치로 표시하지 않는다.

| 항목 | 실제 감사 |
|---|---:|
| 파일 | 9,573개 |
| 논리 크기 | 397,837,582 bytes (379.41 MiB) |
| inode 중복을 제외한 할당 디스크 | 421,486,592 bytes (401.96 MiB) |
| 동일 SHA-256 추가 경로 | 2,466개 / 1,374개 그룹 |
| 중복 논리 크기 | 92,957,580 bytes (88.65 MiB) |
| 중복 추가 physical inode 할당 추정 | 98,779,136 bytes (94.20 MiB) |
| 보존 archive / active | 9,047 / 31개 |
| 재생성 가능하지만 참조 유지 | 493개 |
| 캐시 후보 | 2개, 모두 기존 manifest가 참조하여 보존 |
| 실제 과거 파일 삭제 / 절약량 | **0개 / 0 bytes** |

Task10 ZIP의 중복 604개와 다른 범위의 실제 디스크 감사다. hash가 같다는 사실을 삭제 승인으로 사용하지 않았다. device/inode와 symlink도 기록했고 물리 중복 수치를 ZIP 복사 수와 혼동하지 않았다. 원본 소스/manifest/DB 경로 참조를 점검했지만 동적 경로 의존성이 완전히 부재한다는 증명은 아니므로 불확실한 파일은 남겼다.

### 이후 적용 정책

- **RETAIN_ACTIVE:** 공식 Factory·예약·승인 이력, 현재 모델·전략/신호, 활성 판단과 Queue.
- **RETAIN_ARCHIVE:** 계약·봉인, LLM 원문, 원데이터·최초 관측 시각, 성공/실패/기각 증거, 학습 코드·환경·checkpoint, 체결·NAV·평가·DB backup.
- **REGENERABLE:** 입력용 복사본·파생 factor/prediction CSV·중간 통계. 현재 재현 코드·DB·manifest가 요구하면 그대로 보존.
- **DISPOSABLE:** 미참조 임시파일/캐시만, 사용 중 아님·참조 없음·source 존재·hash 검증 backup/격리 restore를 확인한 후 삭제.

이번에 복원 검증 없이 삭제한 원문·모델·실패·DB 파일은 없다. 새 observer는 계좌 간 원문을 공유하고 모델을 read-only mount하며, 같은 시장/세션의 추론을 재사용한다. 전체 수집을 5분마다 하지 않는다. 봉인된 다음 공식 세션이 끝나기 전에는 네트워크 호출 0이며, 그 뒤 calendar 캐시와 완료 세션 단위 가격/추론을 사용한다. 현재 worker가 요구하는 입력용 전체 context 복사본은 남아 있으므로 이를 제거했다고 주장하지 않는다. 이번 작업에서 새로 만든 큰 DB 감사 export 5개는 gzip 보관 후 격리 복원·SHA-256 검증을 거쳐 비압축본만 정리했다. 원 bytes는 복원 가능하며 28,131,710 bytes(26.83 MiB)를 절약했다. 이는 과거 Task6~10 원본 삭제와 구별한다. 새 Task10.1 산출물은 manifest 자체를 제외하고 캐시·코드·문서 포함 **853개, 약 24.65 MiB**이며, 최종 manifest 크기는 별도다. 새 checkpoint 복사·LLM 호출·학습은 0이다. [압축/복원 근거](../../runtime/task10_1/export_archive_receipt.json).

근거: [DRY_RUN](../../runtime/task10_1/hygiene_dry_run.json), [파일 inventory](../../runtime/task10_1/artifact_inventory.json), [중복 그룹](../../runtime/task10_1/duplicate_groups.json), [삭제 차단 근거](../../runtime/task10_1/cleanup_result.json), [보존 정책](../../runtime/task10_1/retention_policy.json).

## 7. 검증·재현·남은 차단점

- 기존 최소 안전 및 운영 경로 회귀, 신규 prospective 시점/재실행/변경 모델 차단/수집 revision/주간 성숙/분리 후속 요청 시험: **고유 65개 pytest 통과**, 실패·오류·skip 0. 중복 실행된 같은 시험은 합산하지 않았다.
- compileall 통과. V104 command는 `NO_ENABLED_CANDIDATES`, append 0, Live false를 반환했다. 이를 새 Forward 투자 성공으로 세지 않았다.
- 실제 Factory 재열기·중복 결과 불변, 격리 예산 차단·PG lease 재개, 임시 DB restore를 별도 실행했다. 합성 시험과 실제 새 시장 결과는 분리한다.
- 기존 Task10 manifest의 **2,339개 파일 hash 전부 일치**. 이전 역사 성과/연구 증거는 변경하지 않았다.

```bash
# 모델 호출/학습 없이 현재 등록 상태와 새 완료 세션을 관측
PYTHONPATH=src .venv/bin/python experiments/task10_1/forward.py
PYTHONPATH=src .venv/bin/python experiments/task10_1/benchmarks.py
PYTHONPATH=src .venv/bin/python experiments/task10_1/queue_followups.py
# 격리 fixture 시험
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q experiments/task10_1/test_forward.py
```

`recover_factory.py`는 완료된 일회성 복구 코드다. 현재 원장이 있으면 덮어쓰기를 거부한다. 다시 실행해 빈 원장을 만드는 도구로 사용하지 않는다. 감사와 새 연구 파일 생성량은 [진행기록](10_1_progress.md), [새 산출물 증가량](../../runtime/task10_1/new_artifact_growth.json), [증거 manifest](../../runtime/task10_1/artifact_manifest.json)에 남겼다.

**다음 순서:** 실제 11/16 완료 세션의 수집·NAV·지수 대사 → 충분히 성숙한 주간 label/모델오차 확인 → 분리 Quanta/RD prospective executor와 공식 Factory 검증 연결. 기존 READY 작업의 지원되지 않는 kind도 명시적으로 정리해야 한다. 배당/기업행사·거래정지·PIT 상장 검증과 새 원가격 불일치 시의 안전한 재개는 계속 보완 대상이다. 이번 작업으로 무인 투자 개선이나 투자 우위가 입증됐다고 판단하지 않는다.

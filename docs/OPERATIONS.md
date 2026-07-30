# Operations

## 설치

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.lock
```

Python 3.10 이상이 필요하며 Docker image는 Python 3.12를 사용한다.

```bash
docker compose up --build
```

Control Plane 기본 주소는 `http://127.0.0.1:8788`이다. 외부 bind는 `V86_ALLOW_REMOTE_CONTROL_PLANE=true`가 필요하지만 인증 기능이 문서상 보장되지 않으므로 신뢰된 네트워크에서만 사용한다.

## 환경변수

| 변수 | 용도 | 현재 안전 기본값 |
|---|---|---|
| `PYTHONPATH` | `src` import 경로 | Docker에서 `/app/src` |
| `QUANT_HARNESS_MODE` | 환경 표시 | `PAPER` |
| `TOSS_ALLOW_LIVE_ORDERS` | 레거시 요청 플래그(현재 build에서는 권한 부여 안 함) | `false` |
| `TOSS_CLIENT_ID`, `TOSS_CLIENT_SECRET`, `TOSS_ACCOUNT_ID` | 외부 API credential | 미설정 |
| `TOSS_ENDPOINT_MAP`, `TOSS_FIELD_MAP` | 검증된 endpoint/field JSON 경로 | 미설정 |
| `OPENDART_API_KEY` | OpenDART 수집 | 미설정 |
| `V85_SCHEDULER_INTERVAL_SECONDS` | scheduler 주기 | 최소 3600초 |
| `V85_SCHEDULER_ONCE` | scheduler 1회 실행 | `false` |
| `V85_RUN_ON_START` | 컨테이너 시작 시 운영일 실행 | `false` |
| `V89_GOVERNANCE_CHECK_ON_START` | 시작 시 frozen gate 확인 | `true` |

환경변수와 credential을 설정해도 현재 build의 중앙 Live hardlock을 해제할 수 없다.

## 실제 데이터 배치

1. 원본 파일을 덮어쓰지 말고 `data/raw/` 또는 별도 보존 위치에 저장한다.
2. [`config/v87_actual_data_ingestion.yaml`](../config/v87_actual_data_ingestion.yaml)의 provider·required columns·timezone·price scale을 맞춘다.
3. 상장·상폐·기업행위, D-1 신선도, 중복·비양수 가격·OHLC geometry를 확인한다.
4. 수급·공시·뉴스는 [`docs/CONTRACTS.md`](CONTRACTS.md)의 템플릿과 외부 계약 상태를 확인한다.
5. revision gate 실패, PIT 원장 부족, 누락 시세가 있으면 동적 실행을 중단한다.

```bash
PYTHONPATH=src python scripts/run_v87_actual_data_ingestion.py
```

## 백테스트 실행

```bash
PYTHONPATH=src python scripts/run_v104_end_to_end_causal_challenger_audit.py
PYTHONPATH=src python scripts/run_v104_2_jul30_crash_bridge.py
```

첫 명령은 V104 역사 screening·인과성·게이트를 재생한다. 두 번째는 2026-07-03 고정보유 bridge만 재현한다.

## 일일 분석과 Paper 실행

운영일 replay:

```bash
PYTHONPATH=src python scripts/run_v85_operating_day.py --session YYYY-MM-DD
```

후보별 신규 Forward session:

```bash
PYTHONPATH=src python scripts/run_v104_forward_session.py --as-of YYYY-MM-DD
```

- 데이터가 동결일 이하이면 `NO_NEW_SESSION_AFTER_V104_FREEZE`다.
- fingerprint/input/idempotency/reconciliation 오류는 즉시 중단한다.
- 실제 출력은 `reports/runtime/v104_forward_observations.csv`이며 release ZIP에는 사전 생성 상태를 넣지 않는다.

Scheduler:

```bash
PYTHONPATH=src python scripts/run_v85_scheduler.py
```

## 프로세스 재시작과 상태복구

- V85는 run ID와 stage hash를 `data/runtime/v85_orchestrator.db`에 저장한다.
- 동일 run manifest가 있으면 `--rebuild` 없이 기존 결과를 반환한다.
- Paper 계좌 DB는 `data/runtime/v85_dual_paper.db`다.
- 백업은 `data/runtime/backups/`에 생성되고 restore integrity를 검사한다.
- 재구성이 필요할 때만 `run_v85_operating_day.py --rebuild`를 사용하며, 기존 runtime 파일을 먼저 별도 보존한다.

## 로그와 감사 기록

- 운영 경보: `data/runtime/v85_alerts.jsonl`
- 운영 run manifest: `reports/v85_operational_hardening/runs/`
- 주문 journal: `data/runtime/v88_order_journal.db`
- reconciliation: `reports/v88_order_reconciliation/`
- frozen governance: `reports/v89_forward_governance/`
- V104 품질 게이트: `reports/v104_end_to_end_causal_challenger_audit/v104_quality_gates.csv`
- 후보 adapter registry: `reports/v104_end_to_end_causal_challenger_audit/v104_runtime_adapter_registry.csv`

## 장애 시 kill switch

1. scheduler와 control-plane container/process를 중지한다.
2. `config/v85_operations.yaml`의 `risk.kill_switch`를 운영 승인 절차에 따라 `true`로 설정한다.
3. 신규 주문을 생성하지 말고 내부·브로커 holdings/cash/order를 대조한다.
4. mismatch가 있으면 `HOLD_ONLY`를 유지하고 자동 재주문하지 않는다.
5. DB·로그·원본 데이터·설정 hash를 보존한 뒤 원인을 조사한다.
6. 복구 후에도 Paper 검증과 사람 승인 없이 Live를 재개하지 않는다.

현재 release의 `risk.kill_switch` 기본값은 `false`지만 Live 자체는 다른 다중 게이트로 차단돼 있다.

## 브로커 연결 전 확인사항

- `config/v101_broker_execution_contract.yaml`의 모든 null/빈 필드가 공식 계약으로 확인됐는가
- endpoint/field map이 실제 응답과 테스트됐는가
- account·holdings·order create/list/cancel이 sandbox에서 검증됐는가
- tick·가격제한·최소주문·수수료·세금·settlement가 effective-dated로 반영됐는가
- partial fill·reject·cancel/replace·transport recovery가 매핑됐는가
- client order ID 보존과 query retention window가 충분한가
- stale quote/account 차단과 reconciliation `HOLD_ONLY`가 확인됐는가
- Paper와 Live credential·DB·account가 분리됐는가
- V89 Forward 기준과 사람 승인을 충족했는가

하나라도 확인되지 않으면 `UNVERIFIED_EXTERNAL / LIVE_DISABLED`를 유지한다.

## 운영 체크리스트

- [ ] 입력 cutoff·source·hash·timezone 확인
- [ ] PIT universe와 D-1 데이터 확인
- [ ] 부모·후보 동일 input hash 확인
- [ ] candidate fingerprint·target hash·order signature 확인
- [ ] 누락 open/ADV, 음수 현금, risk limit 위반 없음
- [ ] 주문 journal persist-before-submit 및 멱등성 확인
- [ ] holdings/cash/NAV reconciliation 통과
- [ ] 역사 replay가 Forward로 집계되지 않음
- [ ] frozen strategy/config hash 유지
- [ ] 자동 승격 및 Live flag 차단 유지

## 호환성 파일

`docs/REAL_DATA_EXECUTION_CHECKLIST.md`는 기존 테스트가 직접 참조해 삭제하지 못한 비권위 호환성 파일이다. 실제 운영 계약은 이 문서와 [`docs/CONTRACTS.md`](CONTRACTS.md)를 사용한다.

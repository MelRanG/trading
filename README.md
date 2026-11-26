# Quant Harness V104.2 — Codex Clean Release

> 서버 이전 안내 (2026-11-12): 아래 V104.2 설명과 `RELEASE_STATE.json`은
> 해당 릴리스의 동결 기록이며, 이후 추가된 모든 연구·Paper 실행 경로의 현재
> 상태를 증명하지 않는다. 실행 코드와 테스트 및 각 계약 원본을 우선 확인한다.

## 현재 주식 Paper·연구 운영 (Task 5)

현재 운영 진입점은 `scripts/run_autonomous_operations.py`이며, 미국 개별주식 우선·한국 개별주식 병행입니다. ETF는 벤치마크 전용입니다. 기존 V104.2 이하 설명은 동결 릴리스의 재현 자료입니다.

- 단일 예약: `deploy/systemd/quant-operations.timer` (user systemd, 종료 후 5분).
- 데이터·예산·작업: `quant_task3_ops`, USD/KRW Paper: `quant_task3_us` / `quant_task3_kr`, 독립 복기: `quant_task3_review`. 모두 기존 PostgreSQL의 localhost:55432를 사용합니다.
- 실행: `PYTHONPATH=src .venv/bin/python scripts/run_autonomous_operations.py`. 서버 전용 DB 역할은 `runtime/task5/service.env`에 있으며 systemd가 읽습니다. `.env`의 인증정보는 출력하지 않습니다.
- 상태: `runtime/task5/latest_tick.json`, `systemctl --user status quant-operations.timer`, `journalctl --user -u quant-operations.service`.
- 백업·복원 검사: `PYTHONPATH=src .venv/bin/python scripts/backup_operations.py --restore-check`.
- 공통 A/B: `scripts/run_common_experiment.py`. 현재 동결 주식 비교가 Factory 일일 예산으로 대기 중이며 자동 승격은 없습니다.
- 구형 Docker V85 예약·제어판은 `legacy-reference` profile에 격리했습니다. 현재 systemd와 동시에 실행하지 않습니다.
- 새 일일 수집은 인증된 Toss를 사용합니다. 기존 Yahoo 수집기와 보존된 역사 자료는 재사용하지만, Yahoo 자동 조회 권한이 확인되지 않아 새 주기 수집은 활성화하지 않았습니다.
- 실제 성숙 Forward·전략 우위·실거래 적합성은 별도 검증 사항입니다. [Task 5 보고서](docs/development/05_autonomous_operations_report.md)를 확인하십시오.

## 서버 이전과 실행 안전

- 동결 릴리스의 Paper 진입점은 `scripts/run_daily_paper_cycle.py`다. 실계좌 조회와
  테스트 DB 설정을 포함한 실행 조건을 확인하기 전에는 실행하지 않는다.
  주문 실행 권한이 자동으로 활성화되는 것은 아니다.
- V69와 V79 관련 연구·replay 코드가 존재하지만, 연구 결과나 과거 replay는
  미래 수익 또는 실거래 적합성의 증거가 아니다. 실제 기본 경로와 활성 설정은
  실행 전 코드와 계약에서 확인한다.
- `runtime/`과 `data/toss_intraday_1m/`은 로컬 실행 상태·캐시이므로 Git에
  포함하지 않는다. 연구 원장, 체크포인트, 분봉 캐시가 필요한 작업은 별도로
  검증된 백업과 안전한 이전이 필요하며, 저장소 clone만으로 재현되지 않는다.
- `.env`와 변형 파일은 Git에 포함하지 않는다. 자격증명은 서버에서 별도로
  안전하게 설정하고 운영 DB와 테스트 DB를 분리한다.
- Live 주문 hardlock을 유지한다. 서버 이전이나 과거 Paper 성공만으로 Live를
  승인하지 않는다.

## 목적과 현재 상태

Quant Harness는 한국 ETF 중심 전략을 **시점 일관성·비용·체결·상태 정합성·Forward 검증**까지 추적하는 연구 및 Paper 실행 하네스다. 현재 런타임은 V104의 7개 에이전트 경로를 사용하며, V104.2는 2026-07-03 고정보유분을 2026-07-30까지 평가한 crash bridge를 포함한다.

- 연구: 구현 및 역사 재생 완료. 성과는 재사용된 역사 데이터의 screening 결과다.
- Paper: 부모 2개와 후보 3개 adapter가 구현됐으나, 동결 이후 신규 Forward 관측은 0세션이다.
- Live: 비활성화 상태다. 외부 브로커 계약은 `UNVERIFIED_EXTERNAL`이며 현재 build에는 Live capability와 최종 주문 권한이 없다. 환경변수·credential로 활성화할 수 없다.
- 2026-07-30 bridge: 고정보유 mark-to-market만 검증됐다. 동적 재선정·신규 주문 재실행은 완전한 PIT 데이터 부족으로 차단됐다.

## 설치와 최소 실행

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.lock

PYTHONPATH=src python scripts/run_v104_2_jul30_crash_bridge.py
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/test_v104_end_to_end_causal_challenger_audit.py \
  tests/test_v104_2_jul30_crash_bridge.py
```

Docker 실행은 `docker compose up --build`이며 기본 환경은 Paper다. `TOSS_ALLOW_LIVE_ORDERS`는 현재 build의 Live 주문을 활성화하지 않는다.

## 읽는 순서

1. [`RELEASE_STATE.json`](RELEASE_STATE.json)
2. [`AGENTS.md`](AGENTS.md)
3. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
4. [`docs/CONTRACTS.md`](docs/CONTRACTS.md)
5. [`docs/VALIDATION.md`](docs/VALIDATION.md)
6. [`docs/OPERATIONS.md`](docs/OPERATIONS.md)

과거 `reports/v77_*`~`reports/v103_*`는 코드·테스트·연구 원장의 기계적 증거다. 현재 운영 지침으로 사용하지 않는다.

## 아직 지원되지 않는 기능

- 검증된 실제 브로커 계좌·주문·체결·거절·취소 계약
- 실제 broker-state 기반 증분 production runner
- 자동 Champion 승격 및 자동 Live 승격
- 2026-07-03 이후 25개 ETF 전체 PIT 동적 재선정
- 완전한 상장·상폐·기업행위 원장, effective-dated ETF 구성종목, 역사 PIT 뉴스
- 봉인된 실행 규칙이 없는 P2+P3 비교

## 주요 명령어

전체 명령과 운영 절차는 [`docs/OPERATIONS.md`](docs/OPERATIONS.md), 검증 명령과 결과 경로는 [`docs/VALIDATION.md`](docs/VALIDATION.md)를 따른다.

## Task 8 Shadow 통합 연구

`config/task8_portfolio.json`의 별도 정책·USD/KRW Shadow DB에서 독립 연구 판단과 위험·기권을 기록합니다. 기존 Paper 전략·계좌는 유지합니다. 기존 단일 운영 CLI에 회사 실적 관측과 Shadow 현금 관측을 연결했으며, API 관측은 24시간 예약·출처 검증으로 제한합니다. 새 계좌의 자동 주문·승격은 없습니다. 실제 판단은 근거 부족으로 현금이며 기업 실적 정확도와 Forward 투자 우위는 미검증입니다. [실행 결과·제약](docs/development/08_portfolio_integration_report.md).

Task 8b에서는 미국·한국 14개 기업으로 탐색을 확대하고, 별도 탐색 Shadow 계좌에 4개 종목의 목표 비중을 봉인했습니다. 현재 체결·성숙 성과는 대기 중이며 공식 Paper 적격성은 유지합니다. [후보·조건부 가치평가·실행 증거와 한계](docs/development/08b_opportunity_discovery_report.md).

Task 9.0에서는 다섯 과거 시점의 제한 공시 연구, 대표 A/B/C와 3개 기업 실적 시나리오 채점을 실행했습니다. 전체 PIT 종목군·기업행사·거래 세션이 부족해 5년 연속 투자 재현과 초과수익 판정은 미완료입니다. [역사 검증 결과·데이터 한계](docs/development/09_historical_investment_replay.md).

Task 9.0 후속에서는 시총 하한을 둔 한국·미국 제한 코호트로 역사 가격 평가를 완결했습니다. AI A/B/C는 모두 현금을 선택했고, 별도 대조군의 솔루엠·ON 매수·63세션 보유·매도 및 지수 비교를 검증했습니다. AI 비현금 투자와 투자 우위는 미입증입니다. [첫 재현 결과·원장·자료 제약](docs/development/09_historical_replay_completion.md).

Task 9 투자 유용성 재평가에서는 미국 30개·한국 24개의 당시 후보군을 세 시점에서 검토하고, 18개 기업·시점의 심층 연구와 3·6·12개월 가격 성과를 측정했습니다. 선정 품질 포트폴리오와 현금 포함 AI 연구 정책을 분리했으며, 미국의 시장 우위는 확인되지 않았고 한국의 양호한 소표본 결과도 독립 알파로 판정하지 않았습니다. [실제 투자 유용성·예측·실패·자료 한계](docs/development/09_investment_utility_report.md).

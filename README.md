# Quant Harness V104.2 — Codex Clean Release

> 서버 이전 안내 (2026-11-12): 아래 V104.2 설명과 `RELEASE_STATE.json`은
> 해당 릴리스의 동결 기록이며, 이후 추가된 모든 연구·Paper 실행 경로의 현재
> 상태를 증명하지 않는다. 실행 코드와 테스트 및 각 계약 원본을 우선 확인한다.

## 서버 이전과 실행 안전

- 일일 Paper 진입점은 `scripts/run_daily_paper_cycle.py`다. 실계좌 조회와
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

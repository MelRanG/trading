# Task 1 · 시스템 기준선

2026-11-12 KST · 감사 대상 `master` / `26d5722` 및 현재 작업 트리. 이 문서는 설계 제안이 아니라 코드·설정과 이번 서버 검증의 구분이다. 기존 연구 및 이전 Windows 결과는 별도 근거로 표시한다.

## 핵심 결론

1. 실제 일일 진입점에는 ETF·KS11 갱신 → 시점·신선도 검사 → V69 부모 판단 → 읽기 전용 계좌 관측 → Paper 주문·내부 대사 → NAV 저장 경로가 있다. 다만 이번 서버에서 일일 사이클·실제 Toss·PostgreSQL은 실행하지 않았다. 활성 V69 고정, 역사 replay의 V79 후보, V104의 연구 adapter, V85 스케줄러는 서로 다른 경로다. 에이전트라는 이름이 독립 LLM 프로세스의 상시 실행을 뜻하지 않는다.
2. 자동 기업 발굴·시점별 예측과 독립 채점, 매매 복기에서 새 가설로 이어지는 전체 루프는 확인되지 않았다. 뉴스 Shadow, V103 연구 결과 집계, Factory는 각기 존재하나 일일 경로에 연결된 자율 개선 시스템이라는 증거는 없다. 과거 모의·합성 실험 및 역사 replay는 신규 Forward 성과가 아니다. 후보 계약상 신규 Forward 관측은 0, 후보 3개는 비활성·`NOT_RUN`이다.
3. Live 권한은 코드에서 잠겨 있고 Paper 주문은 내부 PostgreSQL 원장에 기록된다. 실제 브로커 주문·체결 계약, 외부 상태와의 장애 후 복구, 일일 NAV와 개별 주문 사이 원자성은 미검증이다. 테스트 DB와 실제 계좌 조회를 수반하는 일일 실행은 이번에 하지 않았다.
4. Ubuntu 격리 `.venv`를 구축했고 필수 안전 테스트 24개 통과, 컴파일 성공. PostgreSQL 수용 테스트 17개는 테스트 DB 미설정으로 모두 skipped다. `runtime/`, 분봉 캐시, V87 canonical 파일과 `.env`는 현재 없으며 Git 제외 대상이다. 복구 가능한 백업의 유무는 확인하지 못했다. 원본 데이터 유실과 단순 환경 미설정을 혼동하면 안 된다.
5. Task 2는 **공식 시점별 증거·연구 원장, 기업/퀀트 후보와 포트폴리오 경계, 복기→사전등록→독립 평가, 주문 복구·저장 권위, 스케줄러·장기 기억의 책임**을 결정해야 한다. 기존 엔진 전체를 전제하지 않고, 동일 계약에서 부분 교체 및 전면 재구축 비용을 비교한다.

## 1. 현재 실제 실행 구조

```text
run_daily_paper_cycle.py → 격리 TEST_DATABASE_URL 확인 → lock
 → Toss ETF/KS11 증분·canonical 반영 → freshness / cutoff
 → V69_PARENT preview + read-only snapshot → Paper intent
 → PostgreSQL 주문·체결·내부 대사 → NAV (불일치·오류 시 HOLD_ONLY)
별도: OpenDART/RSS/수급 Shadow; V103 연구 복기; Factory; V85 scheduler
별도: V104 adapter/replay 및 신규 Forward 계약
```

일일 runner는 시장 갱신과 DB 초기화 등 쓰기를 수행하고 기본 snapshot은 `real-read-only`다. 단순 스모크로 실행하지 않는다. Preview는 입력·후보·target 해시와 시점을 검사한다. V104 adapter는 V94 특징, V95 국면, V100 target, V101 체결 정책, V102 증거를 조합한다. ETF에 연결된 제한적 재무 위험 신호가 있다는 사실은 기업가치 발굴 시스템이 있음을 뜻하지 않는다. V85 scheduler는 레거시 `run_operating_day`를 호출하며 위 일일 PostgreSQL runner를 호출하지 않는다. Compose의 restart와 볼륨은 해당 서비스의 설정일 뿐 현재 프로젝트 서비스 배포·정상 작동의 증거가 아니다.

## 2. 기능별 구현·검증 상태

상태는 이 서버에서의 실행 근거를 우선한다. **실제 동작**은 이번에 실행해 관찰한 제한된 범위, **부분 구현**은 코드에 경로가 있으나 전체 연결·실운영은 미검증, **코드만 존재**는 별도 경로 존재만 확인, **미구현**은 감사한 경로에 필요한 기능을 찾지 못한 경우, **확인 불가**는 상태·자료가 없는 경우다.

| 기능 | 상태 | 근거·한계 |
|---|---|---|
| Codex LLM | 실제 동작 | 직전 Ubuntu 실험에서 로그인과 실제 응답 확인. 투자 효용과 무관. [최소 A/B](../research/05_minimal_ab_validation.md) |
| ETF/KS11 수집·신선도 | 부분 구현 | 일일 runner가 Toss 증분·canonical 및 실패 차단 호출. 실제 수집·KRX 전체 휴장·수정 이력은 이번에 미검증. |
| 국면·퀀트 ETF 선정 | 부분 구현 | adapter의 V94/V95 특징과 V69/V79 target. 일일 활성은 V69; 신규 Forward는 계약상 0. 24개 안전 테스트는 역사 입력/계약 검증이지 일일 운영 성공이 아니다. |
| 공시·뉴스·수급 | 부분 구현 | OpenDART·RSS·수급 Shadow는 별도 진입점. V102 재무/수급 증거는 adapter에 연결되나 Shadow 출력이 일일 판단에 반영된다는 경로는 확인하지 못함. 시점별 ETF 구성은 제한적. |
| 기업가치 기반 독립 종목 발굴·예측 | 미구현 | 조사한 일일 경로에 기업 후보 큐, 당시 컨센서스와 1·2·4분기 예측/채점 통합이 없음. 기존 재무 veto/진단과 구별. |
| 전략·진입/청산·위험 | 부분 구현 | target, 리밸런싱 밴드, 수량·현금·참여율 제약과 매도/매수 실행 코드. 개별주 전반의 통합 전략 플랫폼 또는 실제 운영 성과는 확인 불가. |
| Paper 주문·체결·원장 | 부분 구현 | client_order_id 기반 중복 확인, PostgreSQL 체결 및 내부 대사·HOLD_ONLY 코드. 이번 DB 수용 17개 skipped. 실제 브로커 체결은 아님. |
| Live 주문 | 코드만 존재 | read-only 어댑터와 권한 차단 존재. capability와 authority는 false. 실제 브로커 계약·실주문·외부 복구 미검증; 활성화하지 않음. |
| 복기·오류 분석 | 부분 구현 | V103은 기존 보고서의 연구 시도·중복·다중검정 및 Forward 생애주기를 집계. 일일 주문/판단별 독립 복기와 원인→가설 연결은 확인 못함. |
| Factory·A/B·승격 | 부분 구현 | 사전계약·해시·append-only 시도·전이·예산·인간 승인 경계 및 replay 경로 존재. 실제 반복 자율 연구와 새로운 Forward 검증 미확인. 과거 synthetic/replay 기록을 실운영으로 치지 않음. |
| 장기 기억·위임 | 확인 불가 | 프로젝트의 통합 장기 연구 재개 루프 미확인. 별도 Hermes 설치 파일은 존재하나 해당 서버 인스턴스의 설정·가동·프로젝트 연결은 확인하지 않음. 과거 Hermes 재개 실험은 scripted/mock. |
| 스케줄링 | 코드만 존재 | V85 스케줄러 및 Compose 정의; 현재 서비스 실행·거래소 일정·일일 Paper 연계 미확인. 다른 컨테이너의 존재는 이 프로젝트 배포 증거가 아님. |
| TradingAgents / RD-Agent | 코드만 존재 | 이전 격리 upstream 연구는 각각 모의 그래프·모의 연구 연결을 검증. 현 `src/`, `scripts/`, `config/`에서 직접 연동 호출은 찾지 못함. 실제 LLM 투자 우위나 Factory 통합 미검증. |

## 3. Ubuntu 환경·데이터와 보존

- Python 3.12.3, Git 2.43.0, Docker client/server 29.2.1. `origin`은 설정돼 있다. 이 프로젝트 컨테이너는 확인된 실행 목록에 없었다. Codex와 별도 Hermes 설치는 재설치하지 않았다.
- `.venv`는 Git 제외 프로젝트 전용 환경으로 생성했다. `requirements.lock` 설치 후 Paper 경로의 직접 import에 필요한 `psycopg[binary] 3.3.9`와 기존 연구 스크립트의 `python-dotenv 1.2.4`를 추가했다. 둘은 현재 lock과 `pyproject.toml`에 없다. 의존성 계약 자체는 바꾸지 않았고 이 추가 버전은 재현 가능한 고정 배포 계약이 아니다. `pip check` 및 일일 모듈 import 성공. Dockerfile도 lock만 설치하므로 Paper 경로에 같은 의존성 공백이 있다. 전체 스크립트 의존성 완전성은 미검증.
- 현재 프로세스에서 `DATABASE_URL`, `TEST_DATABASE_URL` 및 Toss 인증·계좌 관련 변수는 미설정, 프로젝트 `.env`도 없다. 값은 조회·출력하지 않았다. 코드상 일일 Paper는 `TEST_DATABASE_URL`이 필수이며, `DATABASE_URL`이 설정돼 있으면 두 값이 달라야 한다. 실제 read-only 모드에는 Toss credential 및 계좌/endpoint 계약이 필요하다. DB 서버의 존재·접속 권한·기존 데이터는 확인하지 않았다.
- Git 추적된 V84 가격/manifest, V85 universe 및 `data/opendart_quarterly_pit.csv`, 다수 전략 config는 존재한다. 반면 `/runtime/`, `data/toss_intraday_1m/`, `data/canonical/v87_market_bars.csv`, `data/raw/`, `data/runtime/`은 현재 없다. 앞 세 경로는 Git ignore에 명시돼 있다. 원본 연구 실행 결과·체크포인트·원장 복원 가능 여부와 별도 백업은 확인 불가다. 추적 파일의 존재는 최신성·완전한 PIT 이력을 증명하지 않는다.
- 재시작 보존: Compose는 `data/runtime`, reports, raw에 named volume을 선언하지만 `/runtime/` 및 분봉 캐시는 그 선언에 포함되지 않는다. 현재 실제 볼륨 사용·백업·복구 리허설은 미확인. Hermes 상태도 별도 설치에 속하며 이 저장소 clone으로 이전되지 않는다.
- 검증: `.venv/bin/python -m compileall -q src scripts tests` 성공. AGENTS 지정 네 테스트 파일 24개 통과(종료 0). `tests/test_daily_paper_cycle.py`와 `tests/test_paper_execution_runtime.py`는 `TEST_DATABASE_URL` 미설정으로 **17 skipped**, 통과가 아니다. 외부 API, DB 쓰기, 주문, scheduler 및 전체 회귀는 실행하지 않았다.

## 4. 재사용·보완·교체·삭제 후보

| 선택지 | 근거와 다음 검증 |
|---|---|
| 재사용 후보 | PIT·해시·receipt, Paper 멱등성·대사·HOLD_ONLY, Factory 계약과 인간 승인, 기존 고정 전략을 비교 기준으로 보존. 실제 운영 적합성은 DB·장애 주입으로 별도 검증. |
| 보완 후보 | 원문 수신 시각·정정·종목 매핑, 세션 캘린더, 주문/NAV 사이 복구, 독립 복기와 예측 채점, 격리된 데이터·비용·모델 기록. |
| 교체 비교 후보 | TradingAgents의 반론·복기, RD-Agent의 가설 제안, Hermes의 연구 기억·위임, 외부 엔진의 대사 구조. 이전 조사 결과를 재사용하고 동일 입력·권한·비용·장애 조건에서 기존 방식과 비교. 전체 통합을 기정사실화하지 않는다. |
| 삭제·통합 후보 | 중복 V85 스케줄러와 별도 일일 runner의 책임, 버전별 replay·보고서 생성 경로, 중복 복기/메모리 기능. 참조·보존·재현 의존성 검증 전 삭제하지 않는다. |
| 신규 필요 | 원문 provenance와 정정 계보, 당시 기대치·봉인 예측·성숙 라벨, 독립 기업가치/퀀트 후보 계약, 매매 복기의 증거→Factory 제안 연결. |

## 5. 목표 대비 공백

PIT 원문과 유니버스의 장기 보존, 자율적인 정보 탐색과 실증된 예측, 전략별 독립 후보·포트폴리오 충돌 해결, 거래별 독립 사후 복기, 사전등록된 반복 연구와 실제 Forward, 실패 복구 및 감사 가능한 장기 기억이 하나의 검증된 순환으로 연결되지 않았다. 기존 A/B의 실제 모델 호출은 재구성된 단일 사례이며 하드 토큰 예산·독립 채점이 없어 스킬 우위의 증거가 아니다. 코드 내 가드와 역사 테스트는 실제 브로커 실행·수익률을 증명하지 않는다.

## 6. Task 2 필수 결정

1. 원문·유니버스·컨센서스의 시점/정정/관측 계약과 원장 권위, 누락 시 차단 및 백업·복구 책임을 어떻게 나눌 것인가?
2. 기업가치와 퀀트 후보, 전략별 계정·위험·포트폴리오 충돌을 어떤 계약으로 연결하고 기존 V69를 어떤 비교 기준으로 둘 것인가?
3. 거래 기록→독립 과정·결과 복기→사전등록 Factory→동일 입력 A/B→Forward→사람 승인 경계를 어떻게 강제할 것인가?
4. 현행 PostgreSQL Paper와 별도 replay/스케줄러를 통합·부분 교체·재구축할 때 동일 체결·비용·중단 복구 테스트로 무엇을 비교할 것인가?
5. Hermes/TradingAgents/RD-Agent를 외부 연구 작업자로 둘지 선택적으로 이식할지, 기억과 스케줄러의 단일 권위 및 비용·권한을 어떻게 제한할 것인가?

## 코드와 기존 근거

- 일일 진입·격리: [run_daily_paper_cycle.py](../../scripts/run_daily_paper_cycle.py), [daily_paper_runtime.py](../../src/quant_harness/daily_paper_runtime.py); 전략·receipt: [paper_decision_runtime.py](../../src/quant_harness/paper_decision_runtime.py); 실행·대사: [paper_execution_runtime.py](../../src/quant_harness/paper_execution_runtime.py).
- 국면과 target 연결: [adapter.py](../../src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py); 신규 Forward 상태: [v104_challenger_runtime_contract.yaml](../../config/v104_challenger_runtime_contract.yaml); Live 잠금: [live_safety.py](../../src/quant_harness/v72_integration_ready/live_safety.py).
- 별도 경로: [run_v85_scheduler.py](../../scripts/run_v85_scheduler.py), [run_news_shadow_intake.py](../../scripts/run_news_shadow_intake.py), [V103 engine](../../src/quant_harness/v103_review_feedback_agent/engine.py), [Factory](../../src/quant_harness/alpha_research_factory.py), [Factory completion](../../src/quant_harness/alpha_research_factory_completion.py).
- 기존 연구: [시스템 조사](../research/01_github_discovery.md), [후보 검증 보완](../research/02_validation_addendum.md), [투자 스킬](../research/03_investment_skills.md), [설계](../research/04_final_architecture.md), [Hermes](../research/04_1_hermes_deep_validation.md), [최소 A/B](../research/05_minimal_ab_validation.md), [후보 판정](../research/06_candidate_final_decision.md). 이전 보고서의 `runtime/` 링크는 이 서버에서 현재 사용할 수 없다.

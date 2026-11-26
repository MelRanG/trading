# Task 6-PRE 진행·재개 기록

최초 시작: 2026-11-13. 현재 상태: **실사 및 최소 PoC 완료 / 최종 추천 HYBRID_MINIMAL**. LLM 품질·독립 Forward·운영 이전은 미검증이며 최종 보고서에 분리. 아래는 단계별 이력이다.

## 작업 계약

HKUDS/Vibe-Trading 원본 main/안정 릴리스 고정 → 실행 권한·라이선스·의존성 점검 → 격리 원본 실행/시험 → 기존 동결 자료의 동일 조건 비교 → A/B/C 최소 연결 증거 → 최종 기반 선정. 한국 기본 지원 여부는 감점하지 않는다. 투자 우위는 별도 Forward 증거 없이는 인정하지 않는다.

운영 코드·DB·Factory 원장·전략·Live 잠금 변경 금지. 새 운영 scheduler/Gateway 배포 금지. 외부 코드에 .env, 운영 DB 주소/인증, 개인 인증 폴더를 전달하지 않는다. 원본 저장소 수정 전 공식 경로를 먼저 실행한다. 생성 코드·shell은 무네트워크·무비밀정보 격리에서만 실행한다.

## 재개 절차

1. AGENTS.md와 사용자 Task 6-PRE 전체 지시, 이 파일을 확인한다.
2. `git status --short`, `git diff` 및 `/home/ansy/app/quant-diligence/` 설치·프로세스 상태를 확인한다. 기존 Task1~5의 대량 미커밋 변경은 이번 실사의 변경이 아니다. 임의 commit/reset 금지.
3. `runtime/task6_pre/evidence/` 원본 로그/버전/입력 hash를 확인한다. 로그 없는 성공을 신뢰하지 않는다.
4. 완료된 단계는 근거만 확인하고 미완료 단계부터 진행한다.

## 0. 완료 — 기존 범위·현재 상태 확인

- AGENTS, README, development 01~04 핵심 결과와 05 보고서/자동 관측 경로를 읽었다. 추가 세부 코드와 research는 아래 단계에서 관련 경로별 확인한다.
- Quant Harness는 실제 주식 수집/기존 Paper/봉인 복기/Factory/단일 timer/복원 증거가 있다. 장기 투자 우위·실제 수치 예측 정확도·성숙 Forward·새 공통 전략 A/B는 아직 증명하지 않았다.
- 기존 Task5 timer는 계속 운영 중이다. 이번 실사에 전달할 자료는 파일 snapshot만 사용하고 외부 원본에 운영 DB를 연결하지 않는다.
- 공식 GitHub connector metadata와 공식 README를 확인했다. main에는 11월 연구·백테스트·Paper 수정이 계속 올라오므로 릴리스 대비 차이를 실제 코드로 분석해야 한다. README 주장을 실행 성과로 취급하지 않는다.

## 1. 진행 — 원본 확보

- checkout 예정 경로: `/home/ansy/app/quant-diligence/vibe-original` (프로젝트 운영 경로 밖).
- 증거 경로: `runtime/task6_pre/evidence/`.
- clone 명령: `git clone --filter=blob:none https://github.com/HKUDS/Vibe-Trading.git /home/ansy/app/quant-diligence/vibe-original`.
- 다음: 커밋/태그/최신 안정 릴리스 pin, 라이선스·설치 정의·CLI·테스트·shell/network/모델 접근 조사, 격리 실행 선택.

## 최초 미완료 목록(이후 체크포인트에서 갱신)

원본 설치/CLI, 테스트, 연구/분석, 백테스트, Paper/Shadow, 재시작/기억, 동일 데이터 비용 통제 비교, A/B/C 최소 PoC, 최종 보고서. 아직 결론 없음.

## 1. 완료 — 원본 버전·보안 경계

- main pin: `0025531f005d4a7aac3fb884cda2fba9318e7158`, 2026-11-12T23:34:46+08:00.
- stable `v0.1.19`, published 2026-11-05T11:38:28Z, commit은 `runtime/task6_pre/evidence/versions.json`에 저장. main까지 99 commits. diff/stat/log 저장 완료. MIT 본문 및 개별 Alpha Zoo NOTICE도 후속 검토.
- 원본은 생성 Python을 subprocess에서 실행하며 원본 subprocess가 network-capable임을 SECURITY.md가 명시한다. 실행 컨테이너는 `--network=none`, cap-drop=ALL, no-new-privileges, user1000, memory3G/cpus2/pids256. 운영 repo·DB·Docker socket·인증 폴더 mount 없음.
- 실제 원본에 KoreaEquityEngine과 equity_kr factor metadata가 존재한다. 한국 미지원이라고 가정하면 틀림. 해당 시장 지원과 별개로 연구/회계 정확성을 시험한다.
- Codex OAuth native provider `agent/src/providers/openai_codex.py` 존재. 개인 인증정보를 원본에 직접 제공하지 않는 제한에 따라 현재 무인증 fixture/nonLLM 시험 우선. Codex 기존 개인 OAuth를 mount하지 않음.

## 2. 진행 — 격리 설치·첫 실행

- Docker 기존 `python:3.12-slim` 사용, 전용 `/home/ansy/app/quant-diligence/vibe-env` venv. Quant .venv와 분리.
- 첫 설치: read-only /repo에서 setuptools egg-info 생성 실패. 보안 mount 때문에 발생한 설치 조건 문제이며 알고리즘 결함 아님. 원본 코드 변경 대신 `/work/build-source`의 별도 빌드 사본에서 재시도.
- 재시도 pip 설치 종료코드 0. 로그: `vibe-work/install_retry.log`, 생성 wheel sha `235fc3fc3bc3ee62778cbf4e94107558c67b29832751acea463ae4faa9f4e8e6`.
- 설치 완료 전에 첫 CLI probe가 시작돼 entrypoint not-found를 반환했다. 이는 실사 실행 순서 오류이며 원본 CLI 결함으로 집계하지 않음. 설치 종료 확인 후 probe 재실행 중.
- 원본 checkout 변경 없음, 빌드 사본의 egg-info 등은 checkout과 분리.
- 다음: CLI 성공/실패 로그 확정, 원본 offline 테스트 선별 실행, frozen 파일 adapter·동일 비용 비교. 아직 기반 추천 없음.

## 2. 완료 — 공식 진입점 및 원본 시험

- 설치 이후 실제 CLI `--help`, `alpha list`, `research-lab --help` 성공. Alpha Zoo 478개 catalog, pip check 정상. 로그/environment.lock을 `runtime/task6_pre/evidence/`에 복사.
- original main 선별 16파일 **412 passed / 203 warnings / 76.97s**, exit0. 추가 PaperAccounts·GoalStore·ResearchArtifactStore 3파일 **70 passed / 5.08s**, exit0. 전부 credential-free, network-none container.
- suite 전체를 실행한 것이 아님. 모델 시험은 mocked/fixture; 투자 우위 증명이 아님. CLI 1차 설치경합/readonly 설치실패와 구분한다.

## 3. 완료 — 고정 입력 원본 실행·공통 비용 비교

- 추가 PoC 코드: `experiments/task6_pre/export_inputs.py`, `vibe_probe.py`, `common_comparison.py`, `inspect_native.py` (운영 코드 아님).
- 원본 입력 export/prereg hash `c1cc808b8e34a0c5b288fba517ecbc5a125a173d5803df58bb8bd5a42d39bd72`.
- US 1133세션(2022-05-09~2026-11-11), KR1280(2021-08-18~2026-11-12). Task3 원본 Yahoo/Toss 파일만 재사용. 네트워크/DB/Factory 호출 없음.
- 후보 1개 사전고정: 원본 Registry `alpha101_012`(volume 변화 부호 × 음의 close 변화), 양수 top4×20%, D1, long-only; 공식 전략이라고 부르지 않으며 adapter를 명시한다. 성과를 보고 후보/기간/비용을 바꾸지 않음.
- 원본 Registry factor vs 독립 식 maxerror0. 원본 runner local CSV 양 시장 실행 성공. 원본 native target와 common target maxdiff0.
- 원본 native 수익 US+22.0221%, KR-68.2173%; fill 5914/3739. 독립 NAV 재구성 maxerror US2.33e-10/KR1.86e-9. 미국 native 수수료0·소수수량, KR tick/limit 및 서로 다른 sizing/충격 모델 → native vs QH 숫자를 동일비용 순위로 쓰지 않음.
- 공통 QH execution에서 Vibe factor US+10.001%, KR-47.331%. 기존 MOM/DEF/EQUAL 수익은 frozen old reference 오차<1e-6pp로 재현. 공통 benchmark도 같은 D1 sizing 사용. 원본 Task3 benchmark와 US 숫자 차이는 entry open sizing vs D1 close sizing 차이이며 원본 수정하지 않음.
- 결과 `runtime/task6_pre/comparison/results.json`, `evidence/native_inspection.json`; 원본 로그 `/home/ansy/app/quant-diligence/vibe-work/poc_execution.log`와 `poc/summary.json`.
- 원본 Research Lab 비용 민감도 2개 고정 scenario 실제 completed, 총 PoC25.224s, model0/token0. run/input/strategy hashes 존재.

## 4. 진행 — 연구 상태 복구·기반 비교

- Hypothesis→Autopilot goal→native run link는 생성됨. PoC summary 마지막 조회에서 harness가 존재하지 않는 Registry.get을 호출해 AttributeError. 이 오류를 원본 결함으로 집계하지 않음. 상태 파일에는 goal/link 저장됨. 재실행 대신 새 프로세스에서 Registry.list 및 GoalStore로 회수·검증 중(`resume_research.py`).
- 원본 Shadow는 profitable roundtrip만 추출해 rule을 학습하므로 독립 blind process review와 동일한 기능이 아님. 반사실 PnL attribution의 missed-signals 항목은 residual임. 부호/합계가 맞는 것과 실제 원인 판정 정확성을 구분해야 함.
- 실제 native PaperAccounts는 SQLite transaction + optimistic revision conflict가 있어 단순 JSON/non-idempotent라고 평가하면 틀림. Quant와 지원 cadence/승인·평가 권위 차이를 조사 중.

## 다음 미완료

A/B/C 최소 연결의 상태/역할 구분과 증거, native LLＭ 미검증 범위 확정, 확장 모듈 계약·라이선스/의존성 비용, 원본 불변/운영 비변경 증명, 불필요한 Task6 빌드/임시 파일 정리, 최종 `06_pre_foundation_selection.md`. 아직 최종 판정 미확정.


## 4. 완료 — 연구 상태·추가 가치평가·모델 제한

- 새 원본 process에서 Hypothesis.list/GoalStore로 기존 가설/goal/run link를 회수. 기존 가설1개, run link1개, goal active. 동일 artifact 저장 두 번째 created=false·같은 revision·reopen검색1개, 상태unverified. 로그 `evidence/research_recovery.{json,log}`.
- 원본 valuation **201 passed / 2.31s** 추가. 총 원본 선별 **683 passed / 0 failures / 0 skipped**. 테스트/fixture와 실제 재무 예측 성과는 구분.
- `openai-codex` 무인증 원본 CLI 실제 실행 exit1: not logged in(local CodexAuthenticationError/401 형식). native source는 별도 Vibe token store와 import_codex_cli=False. 기존 개인 인증 복사·별도 결제·model call0. 기존 Codex CLI 구독의 성공 이력을 native Vibe 분석 성공으로 바꾸지 않음.
- 실제 원문 미래 close/volume 변형→원본 Registry 재계산 과거불변 US627/KR701행 확인.

## 5. 완료 — A/B/C 경계와 최종 추천

- A: original local loader/native US/KR runner, native 연구/상태/Paper fixture.
- B: original factor→공통 Quant execution. input/cost/risk 고정, frozen baseline 오차<1e-6pp, 모든 결과 cash/NAV 독립 일치.
- C: 실제 factor/target output→hash-bound data-only proposal. 주문/승격 true, 자가승인, hash변경, shellfield5건 거부. 운영 DB/Factory mutation0.
- B/C는 thin POC이며 통합 운영 배포가 아님. 전문 에이전트를 추가한 4-arm 실제 LLM/Forward 비교는 아직 미실행.
- 최종 보고서: `docs/development/06_pre_foundation_selection.md`. 추천 **HYBRID_MINIMAL**. 연구·분석은 Vibe 우선 재사용, QH는 필요한 관측/Factory/실행/독립 평가 경계만 유지. 기존 코드 보존이나 한 팩터의 성과만으로 선택하지 않았다.
- 후속 Task6~10 순서/교체·보존·미구현 및 선정 제한을 최종 보고서에 명시. 운영 이전/Live 활성화 없음.

## 6. 완료 — 검증·안전·정리

- QH 필수 최소 4파일 **24 passed /21.00s**, compileall 성공. 운영 코드/경로가 바뀌지 않아 전체190 suite 재실행 없음.
- original checkout clean, commit pin 유지. 실사 시작의 tracked git diff와 현재 byte 일치(`safety_and_archive.json`). Task5 timer의 정상 운영 기록은 계속되며 외부 원본에 운영DB/인증/원장을 제공하지 않음.
- `original_execution_artifacts.tar.gz`에 native 결과/inputs/studies/anonymous 연구상태 보존. sha256은 safety_and_archive.json. 원본 실행 실패·harness실패 로그도 보존.
- 빌드 source 사본·pytest/pyc cache·canonical evidence와 hash가 동일한 중복 work 로그·빈 디렉터리 24개 항목, 총212,812,101 bytes 제거. production source 삭제0. 상세 `evidence/cleanup.json`.
- canonical 실행 로그 위치는 **runtime/task6_pre/evidence/**. 초기 work 경로의 중복 로그는 정리했으므로 이 위치를 우선 확인한다.
- 보존: 원본 pin checkout, 설치 venv, 동결input, native 결과/연구state, 원본 시험XML/로그, PoC 재현 코드. 인증·유료키 없음.

## 현재 남은 작업(실사 이후 별도 범위)

별도 허용된 native OAuth 실제 분석, 수치예측 정확도, 전문 agent 증분 A/B, untouched Forward, production adapter/단일원장 전환·복구. 이를 완료로 표시하지 않았다. 이번 실사 보고서 및 최소 비교는 완료했다.

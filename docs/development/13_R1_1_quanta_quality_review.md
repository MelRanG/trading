# Task13-R1.1 — QuantaAlpha 연구 품질 진단

**최종 판단: `QUALITY_BLOCKED`.** 기존4개 수식의 원본 계산과 평가 결과는 재현됐다. 그러나 가설의 필수 조건이 수식에 누락돼도 연구가 진행됐고, 평가 후에도 생성 당시 “미평가” 문구가 남았다. 이번에는 이 문제를 **탐지·차단하고 귀속을 명확히 하는 최소 adapter**를 검증했다. 가설을 충실하게 구현하는 원본 생성 경로까지 정상화됐다는 뜻은 아니다. 신규 연구 LLM **0회/0tokens**, 신규 후보 **0개**이며 Phase C를 중단했다.

## 1. 핵심 진단과 근거

| 원인 | 판정 | 실제 근거·영향 |
|---|---|---|
| Semantic Quality Gate 비활성 및 실패해도 계속 진행 | FIXABLE | R1 `native_worker.py`는 converter를 `consistency_enabled=False`로 생성. 원본 `factors/proposal.py:480~500`은 gate 실패 시 warning만 쓰고 통과 여부를 강제하지 않으며 예외도 warning 처리. 옵션만 켜면 해결된다고 볼 수 없음 |
| Q0의 MOM20 횡단면 통제 누락 | FIXABLE(누락 차단), 구현 해결은 미완료 | 원래 가설·concise_specification은 similar MOM20/residual을 요구하나 실행 수식에는 raw divergence rank만 있음. 원본 converter가 반환한 첫 task를 검사 없이 채택 |
| Q1의 가중 조건부 평균·결측·통제 누락 | FIXABLE(차단), 구현 해결은 미완료 | 원본 task description 자체가 “not the specified volume-weighted conditional mean”이라고 인정. SUMIF는 충격일 recovery의 **합계**로 횟수와 강도를 혼합하며 no-shock=0. 원래 가설은 가중평균·no-shock missing·수익/변동성 통제를 요구 |
| Q2도 원래 가설의 수익·변동성 횡단면 통제 누락 | FIXABLE(차단), 구현 해결은 미완료 | Q2 concise_specification은 residualization을 요구하지만 수식은 두 rank의 차이. 기술적으로 다른 score 생성에 성공한 것과 원래 조건부 가설 검증은 다름 |
| 생성 당시 “This factor has not been evaluated.” 잔존 | FIXABLE | Q1 description이 실제 feedback user prompt에 그대로 포함됨. Q1 feedback은 실제 IC를 읽었으면서도 “metric cannot be attributed”라고 표현. code hash 일치만으로 의미적 귀속 검증까지 됐다고 볼 수 없었음 |
| 부모 정보 외 최신 방향 평가가 scenario 문맥에 남음 | FIXABLE·R1 후반 이미 교정 | R1 중단 Q2와 수정 후 입력을 구분. 수정본은 trajectory ID로 부모 평가를 선택하고 controller/pool을 복원. 이번에 원본4개 평가·부모·feedback hash를 다시 대사 |
| Q3의 다른 방향 Q0 재발견 | RESEARCH_LIMITATION + FIXABLE(전체 pool 검사) | 부모 Q1과 낮은 상관이어도 다른 Original Q0와 개발 미국0.957/한국0.949. 원본 AST 부분수식 중복은 score 상관과 다르며, converter마다 만든 regulator의 add_factor는 메모리 추가이지 controller pool 전체 score 검사가 아님 |
| 조정 가격·거래량 의미 | UNDETERMINED(영향 크기), DATA 한계 확인 | 아래 데이터 점검 참조. 경제적 야간 gap·유동성 압력으로 해석할 때 추가 주의 필요 |

원본 위치: `/home/ansy/app/quant-diligence/quanta-original`, commit `b7ceb27b1001261d7a95b209a963664ae1f8ab23`. 신규 clone/pull/설치는 없다. `factors/regulator/consistency_checker.py`에는 semantic checker, ComplexityChecker, RedundancyChecker와 FactorQualityGate가 존재한다. **원본 의미 검사 능력 자체는 이번에 LLM으로 시험하지 않았다.** 비LLM native probe에서 consistency를 끈 복잡도·중복 gate는 Q0~Q3 모두 PASS였다. [실측 native_probe.json](../../runtime/task13_r1_1/native_probe.json).

원본 semantic checker는 교정 제안을 낼 수 있으나 converter가 `passed=False`를 강제로 차단하지 않는 경로가 있다. 예외·일관성 실패를 전달받은 adapter가 fail-closed 해야 한다. 원본 설치 파일은 수정하지 않았다. 직접 regulator import 시 순환 import 실패도 있었고, 기존 pipeline/proposal 순서로 import해 probe를 완료했다. [최초 실패 로그](../../runtime/task13_r1_1/native_probe_initial_import_failure.log)를 보존했다.

## 2. 최소 수정과 기존4개 재검증

신규 [guard.py](../../experiments/task13_r1_1/guard.py)는 다음을 제공한다.

- 미리 명시한 필수 수식 구성·통제가 확인되지 않으면 `QUALITY_GATE_REJECTED`를 반환해 진행을 차단한다. 원본 실패/경고를 성공으로 처리하지 않는 admission 경계다.
- 부모만이 아니라 기존 전체 pool의 날짜별 rank 상관을 확인한다. 이번 `|corr|>=0.90`은 기존 자료의 **기술적 중복 진단 규칙**이며, 전향적 전략 선정 기준으로 검증됐다고 주장하지 않는다.
- ID·code hash·H20·실패 여부가 일치할 때만 현재 `EVALUATED` 상태를 생성한다. generation 원문을 보존하고 feedback용 현재 description에서 과거 “미평가” 문구를 제거해 현재 상태·ID·hash를 명시한다. 잘못된 후보/변경 코드에는 차단된다.

필수 구성 판정은 기존4개의 원문 가설·수식에 대한 명시적 검토표다. 임의의 새 가설을 자동 이해하는 범용 검사기를 만든 것은 아니다. 새 후보는 필수 구성·구현 증거가 다시 검토되기 전까지 통과시킬 수 없다. 이 adapter를 과거 R1에 소급 적용해 기존 기록을 수정하지 않았다.

[guard_replay.json](../../runtime/task13_r1_1/guard_replay.json): Q0 MOM20 통제 누락, Q1 가중평균/결측/통제 누락, Q2 횡단면 통제 누락을 차단했다. Q3는 Q0 중복으로 차단했다. 전체 pool 재검토에서 Q0/Q3의 대칭 중복도 표시하지만, 나중에 생성된 Q3를 과거 Q0의 판단에 사용한 것이 아니다. 기존 성과와 성공4 trajectory는 그대로 보존했다.

[feedback_views.json](../../runtime/task13_r1_1/feedback_views.json)은 과거 description과 현재 평가 상태를 함께 보존한다. 새 LLM feedback을 생성하지 않았으므로 “모델이 이제 올바르게 해석한다”까지 검증한 것은 아니다.

양시장 train 자료에서 기존4개 원본 `factor.py`를 실제 재계산하고 prefix/미래 교란 검사·동일 H20 라벨·50종목 최소 기준을 다시 적용했다. score/paired CSV16개가 기존 압축 원본과 SHA-256까지 같았고 지표도 허용오차1e-12 이내 일치했다. 이는 **기술적 재현**이며 신규 알파·독립 재검증 성과가 아니다. 동일 출력 복사본은 제거하고 [기존 archive 참조와 hash](../../runtime/task13_r1_1/replay_verification.json)를 남겼다. 계산 코드·가설·수식·부호·horizon·기존 결과는 바꾸지 않았다.

새 guard 회귀3개 PASS, AGENTS 필수4 suite **24개 PASS**, compileall PASS. 원본 환경 첫 import 실패와 LocalConf fixture 인자 누락은 별도 실패 기록을 보존했다. 운영 경로 변경이 없어 추가 운영 suite/Forward 실행은 재수행하지 않았다.

## 3. 환경·데이터 해석

원본 `get_factor_env`는 현재 설정에서 `python_bin` 속성이 있으면 `CONDA_DEFAULT_ENV`를 CondaConf에 전달한다. 현재 격리 venv에는 conda 실행파일과 해당 변수가 없다. 같은 ValidationError를 실제로 재현했다. 이름만 채워 실제 conda 환경이 있는 것처럼 처리하지 않았다. 기존 Python을 LocalConf로 지정하는 작은 **환경 adapter probe** 결과는 [environment_probe.json](../../runtime/task13_r1_1/environment_probe.json)에 별도 기록했다. 이것으로 전체 AlphaAgentLoop·Qlib runner를 검증했다고 주장하지 않는다. 원본 source-data 폴더와 기본 CN Qlib provider가 없으므로 단순 환경변수 설정만으로 원본 전체 실행이 완성되지는 않는다. 신규 환경/DB/백테스터 설치는 보류했다.

원본 `REGRESI`는 **instrument별 rolling time-series residual**이며, 매 날짜 횡단면의 MOM/변동성 통제와 같지 않다. 현재 원본 DSL에서 해당 다변량 횡단면 통제를 직접 수행하는 연산은 확인하지 못했다. 표준 SUMIF·WHERE·COUNT로 Q1의 가중평균 일부는 구성 가능하더라도 전체 필수 통제까지 구현됐다고 할 수 없다. custom code/별도 통제 adapter가 필요하면 그 연산과 가설의 의미를 먼저 검증해야 한다. 이번에는 부분 수식만 고쳐 새 알파로 내보내지 않았다.

동일 날짜 조정계수 A_t를 OHLC에 곱하면 장중 C_t/O_t는 계수가 상쇄된다. 야간 O_t/C_(t-1)는 A_t/A_(t-1)이 남으므로 배당·분할 조정이 야간 수익의 경제적 의미를 바꿀 수 있다. 거래량은 공급자 값 그대로라 volume shock도 장기 기업행사 기준이 완전히 인증된 것이 아니다.

현재 R0 admitted302개 전체 기간의 provider event 감사에서 배당6,096건 중5,952건은 일별 마스크상 eligible이고, 알려진 분할111건은 모두 해당 일자 제외됐다. [action_mask_audit.json](../../runtime/task13_r1_1/action_mask_audit.json). 이 수치는 전체2017~2026 이벤트이고 train에 한정된 영향 크기가 아니다. 배당일의 “정상/오류”나 알파 성능 영향까지 확인한 값도 아니다. 기존 warmup63/label 경로·zero volume/결측·35% jump 마스크는 유지했다. 데이터를 소급 보정하거나 새로운 날짜 제외로 성과를 바꾸지 않았다.

## 4. 신규 연구 여부·예산

**Phase C: NOT_RUN.** Q0·Q1뿐 아니라 Q2에서도 가설의 필수 통제가 빠졌고, 현재 DSL/원본 전체 실행 호환성을 정상화하지 못했다. “가설·수식 불일치가 계속 발생” 중단 조건을 적용했다. 차단 능력이 개선된 것과 faithful generation이 정상화된 것을 구분했다. 새 수식을 생성하면 같은 proxy 구현을 다시 평가할 가능성이 있어 호출을 배정하지 않았다. 기존 개발2023~2024·진단2025~2026도 추가로 조회하지 않았다.

Phase A/B/C 연구 LLM 호출 **0/0/0**, 토큰 **0**. 데이터 요청0·학습0·신규 후보0. 본 코딩 대화 토큰은 별도 미계측이다. 과거 R1의18회/488,713토큰은 이번 사용량으로 재집계하지 않았다. 코드 실행은 기존 network-none/CPU2/4GiB 컨테이너를 재사용했다. 누적 CPU 시간은 계측하지 않았다.

## 5. 추가 투자 가치

QuantaAlpha의 원본 가설·코드·계산·feedback·진화 기능이 존재하고 실행된 사실은 유지된다. 그러나 **실험한 가설과 실제 계산한 proxy가 다른 상태**여서 이번 약한 성과를 엔진의 알파 탐색 한계로 일반화할 수 없다. 반대로 실행 성공이나 Q1의 작은 양의 개발 RankIC를 경제적 알파 성공으로 승격할 수도 없다.

현재 추가 토큰 자동 투입은 중단하는 것이 적절하다. 재개 조건은 필수 횡단면 통제를 포함하는 실행 계약 검증, 실제 생성 단계의 fail-closed gate 연결, 현재 평가 상태만 전달하는 feedback view, 모든 기존 후보와의 score 중복 검사다. 새 모델·전종목 자료·추가 플랫폼보다 이 계약의 충족 여부가 먼저다. 본 작업은 수정 경계와 기존4개 재현을 확인했으며 새 faithful generation을 실증하지 못했으므로 최종 판단은 **QUALITY_BLOCKED**다. 경제성 검증·RD 연구·공식 전략/Forward 변경은 자동 실행하지 않았다.

환경 adapter 실측은 **PASS**였다. 기존 `/venv/bin/python`을 `LocalConf(default_entry='python main.py', bin_path='/venv/bin')`로 지정해 runtime 조회가 됐다. 따라서 CondaConf 첫 오류 자체는 환경 adapter로 우회 가능하지만, 원본 source-data 폴더는 여전히 없고 전체 runner/provider 호환성까지 해결된 것은 아니다. 첫 probe의 필수 인자 누락은 수정 후 재시험했고 실패 기록도 보존했다.

기존 R0 3,107개/R1 366개/Task13 435개/Task14 36개 manifest hash가 모두 일치했다. 운영 timer active·기존 tracked diff 유지. 이번 runtime은 약356KiB이며, 동일한 재계산 CSV는 검증 후 기존 압축 산출물을 참조해 중복 저장하지 않았다. [preservation.json](../../runtime/task13_r1_1/preservation.json), [최종 manifest](../../runtime/task13_r1_1/artifact_manifest.json).

재현 명령: `.venv/bin/python experiments/task13_r1_1/audit.py`, `PYTHONPATH=src:experiments/task13_r1_1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q experiments/task13_r1_1/test_guard.py`. 완료된 가격 재계산을 반복할 필요는 없으며 `replay_verification.json`의 원본 archive/hash를 우선 확인한다. `replay.py`는 실제 원본 재계산이 필요할 때만 사용한다. 신규 LLM·후속 Task를 시작하는 명령은 없다.

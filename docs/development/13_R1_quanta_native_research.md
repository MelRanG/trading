# Task13-R1 — QuantaAlpha 독립 연구·진화 검증

**원본 실행 판정: `NATIVE_PARTIAL`.** 원본 planner → 가설/수식 → DSL 코드 → 양시장 계산 → Qlib IC/RankIC → 원본 feedback → EvolutionController trajectory 저장을 Original2개와 Mutation2개에서 완결했다. 다만 전체 `AlphaAgentLoop` 및 원본 Qlib portfolio backtest는 실행하지 못했다. 현재 결과는 원본 controller/구성요소와 외부 평가 adapter를 연결한 실제 실행이며, 전체 원본 메인 루프 성공과 구분한다.

**알파 품질 판정: `INSUFFICIENT_EVIDENCE`.** 실제 연구 결과는 아래 수치와 별도로 판단한다. 후보4개·한 번의 진화·생존편향 역사 자료로 QuantaAlpha 전체 능력이나 독립 투자 우위를 판정하지 않는다. 공식 통합·Task15·RD 연구·Forward 교체를 자동 진행하지 않았다.

## 원본·실행 범위

기존 `/home/ansy/app/quant-diligence/quanta-original`의 commit `b7ceb27b1001261d7a95b209a963664ae1f8ab23`, 기존 `task6-quanta-env`, 기존 Docker 이미지를 재사용했다. clone/pull/설치/데이터 수집은0이다. 원본 README, docs/user_guide.md, configs/experiment.yaml/backtest.yaml, pipeline/factor_mining.py·loop.py·settings.py, factors/proposal.py·feedback.py·coder, pipeline/evolution을 확인했다.

전체 `AlphaAgentLoop` 실제 생성자 probe는 `QlibAlphaAgentScenario.get_runtime_environment`→RD `get_factor_env`→`CondaConf(conda_env_name=None)` ValidationError에서 실패했다. 원문 trace는 [full_probe.json](../../runtime/task13_r1/full_probe.json), [로그](../../runtime/task13_r1/full_probe.log). 현재는 conda가 아닌 격리 venv이며 원본 기본 template의 `~/.qlib/qlib_data/cn_data`와 CN benchmark/instrument 설정도 R0 익명 US/KR 조정 패널과 다르다. 이 probe 실패를 보고 원본 알고리즘을 수정하거나 새 conda/CN provider·백테스터를 설치하지 않고 component+adapter로 범위를 제한했다. 전체 runner·원본 포트폴리오 회계·거래비용 검증은 미실행이다.

실행한 원본 함수는 `generate_parallel_directions`, `AlphaAgentHypothesisGen`, `AlphaAgentHypothesis2FactorExpression`, `FactorParsingStrategy.implement_one_task`, 원본 `expr_parser/function_lib`, `AlphaAgentQlibFactorHypothesisExperiment2Feedback`, `EvolutionController.get_next_task/create_trajectory_from_loop_result/report_task_complete/save_state/load_state`다. 계산된 score에 원본 Qlib `calc_ic`를 적용했다. trajectory pool/controller 저장·재개도 실제 사용했다. 원본 FactorLibrary 전체 관리·등록 및 full pipeline backtest 성공은 주장하지 않는다.

## 데이터·실행 계약

[contract.json](../../runtime/task13_r1/contract.json), [입력 무결성](../../runtime/task13_r1/input_integrity.json)이 기준이다. R0 미국176·한국126(핵심119/별도7)의 adjusted source·적격 마스크604개 hash와 train HDF2개 hash가 일치했다. 과거 삭제된 Task6~12 로그는 복구하지 않았다. 현재 데이터·코드·계약을 이용했다. 다른 기존 후보·성과·Paper·Forward·Factory·팀2는 수정하지 않았다.

한국 핵심 유효 종목50개 미만 날짜16개를 조사했다. [kr_low_dates.json](../../runtime/task13_r1/kr_low_dates.json)에 날짜·영향 종목·이유를 기록했다. 여러 종목에서 `ZERO_VOLUME_UNCLASSIFIED` 또는 `SOURCE_DATE_MISSING`이 공통 발생했다. 실제 휴장·거래정지·기업행사로 독립 확인하지 못했으며 보간하지 않았다. 양시장 모두 **score/label 유효 이름50개 이상**, 과거63개 연속 적격 세션, label 경로 모든 세션 적격을 성과 조회 전에 고정했다. 나쁜 수익을 이유로 날짜를 제거하지 않았다. 따라서 이 기준은 한국의 문제 날짜와 그 영향이 남은 window를 보수적으로 제외한다.

Fit은2017~2022년이며 label 종료도2022년 말 이하다. H20을 모든 최초 가설에 사전 지정했고 방향은 높은 score→높은 미래 수익으로 고정했다. 신호는 t일 종가 후, target은 t+1 open→t+21 open이다. H5/H60 성과를 조회해 유리한 기간을 선택하지 않았다. 원본 TS_MEAN의 min_periods=1 및 FILTER(false)=0 의미를 바꾸지 않았고 raw score와 공통 유효 mask를 별도 보존했다.

연구 worker에 R0 `US_train.h5` 파일만 read-only mount했다. KR 원문·2023이후 가격·label·현재 시총/업종·private mapping·전체 repo는 연구 worker에 주지 않았다. 신뢰된 평가자는 US/KR train을 읽고 실제 지표만 전달한다. 따라서 가설은 US train 관찰 기반이고 KR은 전달된 평가 지표를 통한 전이 진단이다. 미래 결과를 아는 현대 LLM과 current-survivor selection의 한계는 남는다.

개발 검증은 후보4개의 code hash를 모두 동결한 뒤 2023-04-03~2024-12-31에서 별도로 계산했다. 과거63세션 입력을 위해2022년7월 이후 warmup을 포함하되 보고 지표는2023년4월 이후 신호만 쓴다. 마지막 target도2024년 말 이전이며 새 label이 경계를 넘지 않는다. 개발 결과를 보고 mutation/horizon을 다시 바꾸지 않았다. 2025~2026 추가 진단은 이번 예산에서 미실행했다. 모든 기간은 개발/노출된 역사 진단이고 독립 Holdout이 아니다.

## 연구 순서·실패·재개

최대2방향·4실행 후보, 원본 반환 순서 첫 task 실행, 초과 제안은 모두 보존하고 미실행으로 기록했다. Original은 야간/장중 비대칭과 유동성 충격 흡수라는 서로 다른 메커니즘에서 출발했다. 최초2개 완료 후 유효성 gate로 Mutation을 허용했으며 외부 평가 성과를 보고 후보를 선택하지 않았다.

최초 평가 adapter에서 잔차 Series와 target의 index가 달라 상관 계산이 실패했다. 수식·가설·horizon을 바꾸지 않고 정렬된 numpy 값으로 수정했다. 초기 실패 trace/metrics를 보존하고 원본 생성 요청은 cache로 재사용했다. Mutation 전에는 이전 방향의 최근 지표가 scenario 문맥에 남는 것을 발견해 부모 trajectory ID에 해당하는 지표만 주도록 수정했다. 이전 Q2 문맥 시도는 `native/quanta/aborted_Q2_context_guard/`로 보존하며 성공 후보로 세지 않았다. 재개 시 fresh_start로 pool이 빈 메모리에 들어간 실패도 기록했다. 이후 기존 pool과 controller 상태를 로드해 두 Original을 복구했다. 과거 pool·부모 수식·부모 score를 새 결과에 맞춰 변경하지 않았다.

[feedback_bindings.json](../../runtime/task13_r1/feedback_bindings.json)에서 후보ID·code hash·평가 hash·H20·feedback hash·trajectory ID·부모를 대사했다. feedback의 `IC`·`RankIC`는 실제 Qlib 의미이며 spread를 annualized excess return으로 전달하지 않았다. 원본 feedback의 부정 판정도 보존했다. 첫 Original 피드백은 “fit-only 평가됨·dev 미조회·조건부 가설의 통제 누락”을 명시했다. 두 번째 Original은 당시 첫 방향의 평가 문맥을 보았으므로, 초기 두 연구의 완전한 맹검 독립성을 주장하지 않는다.

Crossover는 `NOT_RUN`: 사전 실행4개 상한과 남은 예산 안에서 Original2/Mutation2를 우선했다. Crossover guidance/후보 생성이나 평가를 수행한 것처럼 집계하지 않는다. 상한을 채우기 위한 추가 연구는 하지 않았다.

## 실제 수식·평가 결과

[results.json](../../runtime/task13_r1/results.json)에 가설·원본 task·코드hash·부모·양시장 지표를 연결했다. 코드/수식은 변경하지 않았으며 아래는 실행한 첫 제안이다. 추가 제안은 각 node의 all_proposed_tasks.json에 미실행 상태로 보존했다.

**Q0 — original**, Overnight_Intraday_Divergence_20D

```text
RANK(TS_SUM(LOG($open / DELAY($close, 1)) - LOG($close / $open), 20) / TS_STD(LOG($close / DELAY($close, 1)), 20))
```

**Q1 — original**, Shock_Recovery_Intensity_10D

```text
SUMIF(($close-$low)/($high-$low+1e-8),10,$volume>2*DELAY(TS_MEDIAN($volume,20),1))
```

**Q2 — mutation**, Volume_Absorption_20_40

```text
RANK(TS_MEAN($volume,20)/(DELAY(TS_MEAN($volume,40),20)+1e-8))-RANK(TS_MEAN(ABS($return),20))
```

**Q3 — mutation**, Overnight_Intraday_Log_Difference_20D

```text
RANK(TS_SUM(LOG($open / DELAY($close, 1)) - LOG($close / $open), 20))
```

| 후보 | 구간 | 시장 | IC | RankIC | 상하위20% spread (%p/H20) | 날짜 | 종목×날짜 |
|---|---|---|---:|---:|---:|---:|---:|
| Q0 | fit | US | -0.00630 | -0.00722 | -0.095 | 1426 | 222,956 |
| Q0 | fit | KR | 0.00623 | 0.01144 | 0.173 | 1099 | 111,327 |
| Q0 | development | US | -0.00744 | -0.01702 | -0.161 | 419 | 71,525 |
| Q0 | development | KR | -0.05702 | -0.03775 | -2.446 | 322 | 36,492 |
| Q1 | fit | US | 0.00182 | -0.00136 | 0.142 | 1426 | 222,956 |
| Q1 | fit | KR | 0.00095 | -0.02118 | 0.394 | 1099 | 111,327 |
| Q1 | development | US | 0.01578 | 0.01153 | 0.842 | 419 | 71,525 |
| Q1 | development | KR | 0.03577 | 0.00915 | 1.806 | 322 | 36,492 |
| Q2 | fit | US | -0.02853 | -0.01253 | -0.821 | 1426 | 222,956 |
| Q2 | fit | KR | -0.03271 | -0.00078 | -1.161 | 1099 | 111,327 |
| Q2 | development | US | -0.09183 | -0.06808 | -2.093 | 419 | 71,525 |
| Q2 | development | KR | -0.00681 | 0.04385 | -0.817 | 322 | 36,492 |
| Q3 | fit | US | -0.00444 | -0.00752 | 0.082 | 1426 | 222,956 |
| Q3 | fit | KR | 0.00625 | 0.01011 | 0.235 | 1099 | 111,327 |
| Q3 | development | US | -0.00415 | -0.01400 | 0.052 | 419 | 71,525 |
| Q3 | development | KR | -0.05849 | -0.04475 | -2.493 | 322 | 36,492 |

Spread는 각 날짜 score 상하위 floor(N/5)의 **label 수익률 차이**이며 실제 포트폴리오 수익률·연율 초과수익·거래비용 차감 성과가 아니다. 현금·비중·매매 정책은 적용하지 않았다. 한국은 충분한 공통 label이 없어 개발322일만 평가된다. H20 중첩 label 때문에 419/322일을 독립419/322사례로 세지 않는다. 약20/16개의20일 산술 블록 수준이며 독립성·통계적 유의성을 확증하지 않는다.

## 단순 팩터 대비 추가 정보·진화의 의미

MOM20, REV5, LOWVOL20을 동일 시장·날짜·종목·H20에서 비교했다. MOM20은 방향을 맞춘 기존 Vibe/Qlib ROC20과 동일한 순위 메커니즘이다. LOWVOL20은 일수익 표준편차의 음수로, Vibe의 가격 표준편차/현재가와 수치적으로 동일하다고 주장하지 않는다. 세 기준선 각각을 날짜별 rank OLS로 통제한 잔차와 target rank의 상관을 진단했다. 새 결합 가중치나 기간을 최적화하지 않았고, 개별 통제는 세 변수를 동시에 통제한 인과적 증분 검증이 아니다.

| 후보 | 시장 | 개발 MOM20 통제 잔차상관 | REV5 통제 | LOWVOL20 통제 |
|---|---|---:|---:|---:|
| Q0 | US | -0.0069 | -0.0192 | -0.0177 |
| Q0 | KR | -0.0183 | -0.0362 | -0.0349 |
| Q1 | US | 0.0073 | 0.0086 | -0.0035 |
| Q1 | KR | -0.0089 | 0.0055 | 0.0123 |
| Q2 | US | -0.0613 | -0.0610 | -0.0462 |
| Q2 | KR | 0.0439 | 0.0468 | 0.0242 |
| Q3 | US | -0.0060 | -0.0179 | -0.0186 |
| Q3 | KR | -0.0267 | -0.0429 | -0.0381 |

Q1은 개발 양시장 작은 양의 RankIC와 spread를 보였지만, 미국 LOWVOL20 통제 후 음수이고 한국 MOM20 통제 후도 음수다. 초기 학습 RankIC도 양시장 음수였다. 단순 팩터를 넘어선 안정적 추가 정보로 판정하기 어렵다. 가설은 충격일 가중 평균·수익/변동성 통제를 말했지만 실제 첫 수식은 SUMIF 합계라서 조건부 가설을 완전히 구현한 것도 아니다. Q0도 처음 가설의 MOM20 통제가 수식에 없으며 평가측 잔차 진단으로만 확인했다. 수식을 사후 고치지 않았고 이 가설→수식 불일치를 연구 병목으로 남겼다.

Q2는 Q0 부모와 개발 순위상관 미국 약-0.011/한국-0.079로 다른 정보를 만들었다. 그러나 미국 RankIC가 더 악화됐다. 한국 RankIC는 양수이나 spread는 음수라 종목 순위 전체와 극단 분위의 결과가 일치하지 않는다. 부모와 다르다는 사실만으로 개선이라 할 수 없다. Q3는 Q1 부모와는 다른 신호지만 기존 Q0와의 개발 상관이 미국0.957/한국0.949다. 즉 부모와의 중복만 검사하면 다른 방향의 기존 알파를 재발견할 수 있다. 실제 pool 전체를 통제하는 중복 검사가 향후 필요하다. [상관 행렬](../../runtime/task13_r1/candidate_correlations.json).

시장 국면·연도별 실제 날짜 수와 RankIC는 [regime_stability.json](../../runtime/task13_r1/regime_stability.json)에 있다. Task12/R0 AS_OF/EX_POST 분류를 재사용했고 사후 국면은 평가에만 적용했다. 개별 episode 수·위험조정 경제성을 확증하지 않는다. 어떤 국면/시장만 골라 수식이나 부호를 바꾸지 않았다.

## 비용·호출·검증·보존

실제 Terra 호출 **18회**, 총 **488,713 tokens**다. input 479,307(cached 244,864, uncached 234,443), output 9,406. cached input은 input에 포함돼 있으며 두 번 더하지 않았다. 최초 Original2개는7회/191,028tokens로1차10회/350k 이내였고, 이후 유효성 gate에서2차를 허용했다. 모든 재개·중단 시도도 전체20회/650k 상한에 포함했다. 같은 요청의 response cache 재사용은 새 호출로 세지 않는다. API가 사전 hard token cap을 제공하지 않아 기존 relay의90k 예약 여유와 반환 usage로 차단했다.

모델 호출 경과시간 합계 약245.5초이며 전체 CPU 사용시간은 계측하지 않았다. 계산 컨테이너는CPU2/4GiB/network-none. 별도 유료 API 구매0, 데이터 요청0, 모델 학습0. 원본 요청/응답/trace/usage는 model_calls/에 보존했다. 금액은 provider가 반환하지 않아 임의 추정하지 않았다.

필수 회귀4 suite 24개 PASS, compileall PASS. 원본 계산 raw score→CSV 보존, prefix 대조, 미래 OHLCV 교란 시 과거 score 불변을4후보×2시장×fit/dev에서 검사했다. raw score를 공통 mask로 평가하며 원본 DSL의 결측 의미는 그대로다. 신규 계약·운영 경로 변경이 없어 추가 운영 suite·Forward 실행은 재실행하지 않았다. 과거 manifest의 삭제된 로그를 복구하거나 과거 성과를 재작성하지 않았다.

부모/후보 지표 귀속4개를 code/metric/feedback hash로 확인했다. 연구 worker에는 평가용 원문을 mount하지 않았으며 동결 후 LLM 호출0이다. 전체 algorithm 결과를 직접 뒷받침하는 것은 native/quanta/events.json, controller.json, pool.json, Q*/{generation,metrics,feedback}.json, 원본 factor.py, raw_scores/paired 자료다. 최초 실패·중단 기록도 보존한다.

## 다음 작업 판단

추가 대량 탐색 예산을 즉시 늘릴 근거는 부족하다. 현재는 **Quanta 엔진 전체 폐기나 전략 승격 모두 권고하지 않는다.** Original→실제 평가→원본 Feedback→Mutation→실제 재평가→trajectory 재개 경로는 재사용할 가치가 있다. 다만 첫 수식 선택이 가설의 핵심 조건을 누락하는 문제, 다른 방향까지 포함한 중복, 부모별 feedback context, 원본 full controller/Qlib provider 호환성이 먼저 보완돼야 한다. 이번에는 새 조건부 수식이나 horizon 탐색을 추가하지 않았다.

RD-Agent의 다음 독립 연구는 동일 R0 hash·cutoff·마스크·H20 label 또는 사전등록 native horizon, 동일 단순 기준선을 재사용할 수 있다. Quanta 수식의 안정적 경제성이나 우월성을 전제로 모델 입력에 채택하지 않는다. RD 자체 특징량/모델 연구를 별도로 평가하고 새 신호가 실제 추가 정보를 갖는지 확인해야 한다.

**Task15 자동 진행 없음.** Q1을 제한된 후속 진단 후보로 남길 수 있지만 현 단계에서 거래비용 후 경제성·독립 Forward 우위는 입증되지 않았다. 본 연구의 최종 알파 판정은 INSUFFICIENT_EVIDENCE이며, Mutation의 기능적 완결을 경제적 자기개선 성공으로 합치지 않는다.

## 최종 보존·제안 수 대사

완료된4개 trajectory의 converter 반환은 총8개 task였고, 사전 순서 규칙으로4개를 실행했다. 나머지4개는 미실행 제안이다. 중단된 문맥 시도의 반환 task 0개는 별도 aborted 폴더에 보존하고 성공 trajectory 수에 합산하지 않았다. 실제 호출 원장은18개의 서로 다른 요청이며 cached 재시도는 추가하지 않았다.

raw score/paired CSV32개를 gzip으로 보관하고 압축 해제 SHA를 검증한 뒤 비압축 복사본만 제거했다. 절약166,835,425bytes, 최종 runtime 약42MiB다. [복원 검증 목록](../../runtime/task13_r1/compression_receipts.json). 기존 R0 입력을 매 연구마다 복사하지 않았다. 새 평가용 HDF 약9MiB도 평가 후 제거했으며 기존 원본 references로 재생성 가능하다. gzip CSV는 pandas.read_csv로 직접 읽거나 gzip 해제하면 원래 bytes를 복구할 수 있다. `summarize.py`는 gzip도 직접 읽는다.

Task13-R0/Task13/Task14 manifest 전체 hash 불변을 확인했다. [preservation.json](../../runtime/task13_r1/preservation.json). 현재 운영 timer active이며 임시 연구 relay는 종료했다. 최종 신규 증거 manifest는 runtime/task13_r1/artifact_manifest.json에 보존한다.

재현: 기존 데이터 hash 확인→`prepare.py`는 새 캠페인에만 사용. 현재 완료 캠페인은 `native/quanta/events.json`, `candidate_seal.json`, `results.json`, `usage.json`부터 확인한다. 새 LLM 호출 없이 `summarize.py`로 저장된 평가를 요약할 수 있다. 원본 생성/수정 과정 재실행은 필수가 아니며 실제 기록을 반복 호출로 덮어쓰지 않는다.

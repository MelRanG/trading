# Task13-R1.2 — QuantaAlpha 생성 능력 정상화

**생성 능력: `FAITHFUL_GENERATION_VERIFIED` — 신규 가설 1개에 한정.** 원본 가설 생성·수식 변환·DSL coder, 실제 native semantic Quality Gate와 독립 수치 대조를 수행했다. Semantic 요청의 transport 실패 후에는 **실제 완료된 모델 응답을 동일 요청과 대사해 오프라인 재생**했다. 전체 AlphaAgentLoop 또는 임의 가설의 범용 생성 능력까지 검증한 것은 아니다.

**알파 결과: `NO_INCREMENTAL_ALPHA` — 이번 fit 진단에서 추가 정보의 일관된 증거 없음.** 미국·한국 모두 사전 방향의 RankIC가 음수였다. 부호·horizon을 바꾸거나 새 후보를 추가하지 않았다. Task15로 전달하지 않고 Quanta 반복 탐색을 중단한다. RD-Agent·Forward 변경은 실행하지 않았다.

## 1. A/B 선택과 동결 가설

A안의 기존 DSL을 선택했다. MIN·POW·TS_SUM·RANK로 계산 가능한 새로운 **하방 제곱수익 비중** 가설을 사전 정의했다. 기존 Q1에서 횡단면 통제나 가중 조건부 평균을 삭제해 다른 가설을 성공 처리한 것이 아니다. 충격일 회복 가설을 고치는 B안은 별도 연산·검증이 필요해 이번에는 보류했다. 경제적 메커니즘은 연구 담당자가 먼저 선정했고 Quanta는 원본 hypothesis/converter로 이를 표현·수식화했다. 자유로운 전 시장 자율 발굴 성능의 시험은 아니다.

가설: 최근20일 총 제곱수익 중 음의 수익이 차지하는 비중이 작을수록 지속적 매도 압력이 낮아 향후20일 수익이 높다. 변동성 **수준** 예측과 위험 비대칭 **구성** 예측을 구분했다. 필수 조건·방향·H20·window20·분모0 undefined·warmup63·최소50명은 [contract.json](../../runtime/task13_r1_2/contract.json)에 먼저 동결했다. 통제·사건 필터·추가 window는 요구하지도 허용하지도 않았다.

실제 원본 생성 수식 S0:

```text
-RANK(TS_SUM(POW(MIN($return, 0), 2), 20)
      / TS_SUM(POW($return, 2), 20))
```

독립 기준식은 `-percentile_rank(sum20(min(r,0)^2)/sum20(r^2))`다. 사용한 $return이 조정종가의 과거 단순수익과 일치하는지 별도 확인했다. 분모0은 NaN으로 유지하며 임의 epsilon·보간을 넣지 않았다. [원본 생성물](../../runtime/task13_r1_2/native/quanta/S0/generation.json).

미국176·한국126 R0 train-only HDF를 재사용했다. 연구 worker에는 US_train 파일만 주고, 신뢰된 평가자만 KR train과 label을 읽었다. Fit2017~2022·label 성숙≤2022년말, t+1 open→t+21 open, 기존63 연속 유효 window와50명 기준을 적용했다. 원본 raw rank를 보존하고 공통 적격 mask 적용 후 해당 시점 eligible population 안에서 음의 percentile rank를 산출했다. label 성숙 여부로 신호를 재순위화하지 않았다. 원문·현재 구성·기업행사/PIT 한계는 R0와 같다.

## 2. 실제 수정·원본 사용과 실패 보존

고정 원본 commit `b7ceb27b1001261d7a95b209a963664ae1f8ab23`, 기존 Quanta venv/image를 사용했다. 새 설치·clone·DB·DSL 엔진·백테스터는 없다. 원본 hypothesis generator, expression converter, FactorParsingStrategy, FunctionLib, FactorQualityGate/FactorConsistencyChecker와 Qlib `calc_ic`를 호출했다. 전체 planner/EvolutionController/AlphaAgentLoop를 이번에 실행했다고 주장하지 않는다.

첫 제안은 경제적 의미가 맞았지만 원본 AST 분석이 최상위 음수 `-RANK(...)`의 노드 수를0으로 계산해 구조 검사를 반복 기각했다. 원본 converter가 이에 따라4회 수식을 제안했고 중간 반환은 모두 모델 response에 보존했다. 선택·수정으로 수익을 높인 과정이 아니다.

[syntax_adapter.py](../../experiments/task13_r1_2/syntax_adapter.py)는 **AST 검사에만** 최상위 unary minus를 기존 `SUBTRACT(0,...)`로 정규화한다. 새 연산은 없으며 원본 실행 수식/코드는 음수 rank 그대로다. 실제 원본 함수 fixture로 두 표현이 같음을 확인했다. Python AST가 최상위 UnaryOp인 경우에만 적용해 `-RANK(x)+y` 전체의 부호를 잘못 바꾸지 않는다. [syntax_probe.json](../../runtime/task13_r1_2/syntax_probe.json): 노드0→16·구조 허용·native 수치 동일.

원본 semantic checker는 `strict_mode=True`, correction1회로 실행하고, 원본 gate 결과 False·검사 예외의 “Skipping check”·수식 자동교정을 adapter에서 차단했다. 그런데 실제 semantic 요청의 모델 출력은 완료됐어도 relay의 줄인18k per-call 한도보다 실제24,609tokens가 커 transport 실패가 됐다. 원본 checker는 이 오류를 is_consistent=True로 반환했고 **adapter가 실패로 차단했다**. [실패 gate](../../runtime/task13_r1_2/native/quanta/S0/semantic_gate.json)를 성공으로 바꾸지 않았다.

남은 모델 예산으로 새 요청을 보내지 않았다. 실제 trace에는 exit0·usage·완료된 semantic 응답이 있어 이를 회수했다. 오프라인에서 원본 checker가 만든 user/system prompt가 해당 원래 요청과 **문자열까지 동일함을 assert**하고, 그 완료 응답만 재생했다. 새 응답을 작성하거나 FAILED 원장을 SUCCEEDED로 고치지 않았다. 재생된 실제 응답은 원래 수식·필수 조건의 일치를 인정했다. [원본 checker 재생 결과·요청/trace hash](../../runtime/task13_r1_2/native/quanta/S0/semantic_gate_replayed.json), [복구 코드](../../experiments/task13_r1_2/recover_completed_response.py). Dummy key는 offline APIBackend 생성용 placeholder이며 실제 인증이나 외부 통신은 없다.

이는 실패를 무시한 통과가 아니라 **실패 기록 유지→완료 응답 출처/요청 검증→동일 원본 gate 재실행**이다. 재생 초기 placeholder 부재 오류도 보존했다. 향후 per-call 예산은 실제 CLI 기본 문맥 비용을 포함해 잡아야 한다.

## 3. 신규 가설의 의미·수치 검증

R1.1의 Q0~Q3 필수조건표를 S0에 재사용하지 않았다. [meaning.py](../../experiments/task13_r1_2/meaning.py)는 이번 동결 가설만 위한 독립 pandas 계산식이다. 실제 원본 생성 코드의 raw score와 양시장 전체 train 배열을 비교해 상대오차1e-10/절대오차1e-12 이내 일치를 확인했다. 영수익·혼합 부호 fixture, 부호가 잘못된 후보의 거절도 시험했다. 원본 TS_SUM의 min_periods=1은 raw 값에서 그대로 유지하되 평가에는63개 유효 과거 조건을 적용했다.

양시장 모두 raw 수치 일치·return 필드 대사·분모0 undefined·prefix 대조·미래 OHLCV 교란 시 과거 score 불변을 통과한 뒤에만 label/성과 계산으로 넘어갔다. [phase_b_numeric.json](../../runtime/task13_r1_2/evaluation/S0/phase_b_numeric.json). 이 oracle은 새 임의 가설의 범용 의미 검증기가 아니다. 미래 새 가설마다 별도 필수 조건과 검증을 선언해야 한다.

기존 R1.1의 범용 ID/hash/H20 귀속 검사는 새 S0에 재사용해 [feedback_packet.json](../../runtime/task13_r1_2/feedback_packet.json)을 생성했다. 원본 native LLM feedback·Mutation은 남은 token으로 정상 호출을 보장할 수 없어 **NOT_RUN**이다. 이 packet 생성을 원본 feedback 성공이라고 부르지 않는다.

## 4. 조건부 Phase C 결과

Phase B의 원본 semantic 응답 대사·독립 수치·인과성 검사가 통과한 **동일 S0 하나**를 평가했다. Phase B/C에 각각 새 후보가 생긴 것처럼 중복 집계하지 않았다. 여러 반환 제안·재시도 변형과 실제 실행1개를 구분해 [analysis.json](../../runtime/task13_r1_2/analysis.json)에 남겼다.

| 시장 | IC | RankIC | 상하위20% spread (%p/H20) | 유효 날짜 | 종목×날짜 |
|---|---:|---:|---:|---:|---:|
| US | -0.00917 | -0.00802 | -0.131 | 1426 | 222,956 |
| KR | -0.01471 | -0.04248 | -0.357 | 1099 | 111,327 |

| 시장 | MOM20 RankIC / score상관 / 통제 후 잔차상관 | REV5 RankIC / 통제 후 잔차 | LOWVOL20 RankIC / 통제 후 잔차 |
|---|---:|---:|---:|
| US | -0.0186 / 0.847 / 0.0138 | 0.0070 / -0.0057 | -0.0108 / -0.0127 |
| KR | -0.0462 / 0.860 / -0.0062 | 0.0188 / -0.0347 | 0.0094 / -0.0343 |

MOM20과 상관이 미국 약0.847/한국0.860으로 높다. 미국 MOM 통제 후에는 작은 양의 잔차 단서가 있지만 REV5/LOWVOL 통제 후 음수이고 한국도 음수다. 개별 기준선을 통제한 날짜별 rank OLS 잔차 진단이며 새 결합 가중치를 학습하지 않았다. 여러 기준선의 동시 인과적 증분 검증이 아니다.

기존 Q0~Q3 전체 pool의 같은 날짜·종목 score와 비교했다.

| 시장 | Q0 상관 | Q1 | Q2 | Q3 |
|---|---:|---:|---:|---:|
| US | -0.410 | -0.014 | 0.001 | -0.370 |
| KR | -0.461 | 0.343 | 0.033 | -0.439 |

사전 |평균 일별 rank상관|0.90 중복 기준을 기존 pool에서는 넘지 않았다. 다만 단순 MOM과 상당히 유사하고 사전 방향의 학습 예측력이 부진해 유망 알파로 판단하지 않았다.

20일 circular block bootstrap1,000회(seed42)의 **기술적 불확실성 진단**은 다음과 같다. 사후 추가한 기술 통계이며 새로운 독립 확증·사전등록 유의성 검정이 아니다.

- US: RankIC 평균의 기술적95% 구간 [-0.0355, 0.0182], 날짜 1426개 / 20일 산술블록 71개.

- KR: RankIC 평균의 기술적95% 구간 [-0.0710, -0.0134], 날짜 1099개 / 20일 산술블록 54개.

연도별·AS_OF/EX_POST 국면별 RankIC와 날짜 수는 analysis.json의 periods에 있다. EX_POST는 평가용이며 과거 판단에 쓰지 않았다. 중첩 H20 label과 current-survivor 표본 때문에 수십만 종목×날짜를 독립 수십만 사례로 세지 않는다. Spread는 H20 label 평균 차이이며 거래비용·노출·세금을 반영한 투자 수익률이 아니다. 원본 Qlib IC/RankIC는 의미 그대로 사용했고 annualized excess alias를 만들지 않았다.

Fit에서 양시장 사전 방향이 부진해2023~2024 개발 구간을 추가 조회하지 않았다.2025~2026 역시 미조회이며 기존 노출 자료를 새 Holdout으로 사용하지 않았다. 모델 재호출·부호 뒤집기·horizon 변경·Mutation으로 좋은 결과를 만들지 않았다.

## 5. 자원·검증·보존

실제 신규 연구 호출 **6회**, 전체 **165,296tokens**: input162,521(cached93,184, uncached69,337), output2,775. 캐시를 포함한 전체가8회/180k 안이다. transport성공5/실패1이며 실패한 semantic 호출의24,609tokens도 포함했다. 실패1의 실제 완료응답 재생은 추가 호출0이다.

첫 AST 버그로 converter가4회 제안해 예산 대부분을 소모했다. 최초40k per-call 여유 예약은 남은39,313tokens에서 짧은 semantic 요청을 막아18k로 줄였지만, Codex CLI 고정 문맥 비용을 과소평가했다. 실제 semantic 요청은24,609tokens였고 per-call soft cap에 걸렸다. 전체 상한은 올리지 않았으며 남은14,704tokens로 다음 호출을 강행하지 않았다. 모든 reservation/request/trace와 예산 변경 근거를 보존했다.

신규 데이터 요청0·학습0·설치0·신규 서비스0. 기존 Codex 인증을 사용했고 별도 유료 API 구매는 없다. 금액과 누적 CPU는 계측 불가이며 CPU2/4GiB/network-none 제한을 적용했다. 본 코딩 대화 자체 토큰은 위 연구 usage에 포함하지 않고 별도 미계측으로 둔다.

새 품질/오류 주입·수치 oracle·정규화 회귀3개 PASS, AGENTS 필수4 suite24개 PASS, compileall PASS. 최초 AST 기각/예산 실패·native semantic fail-open/adapter fail-closed·offline placeholder 오류·numpy bool 직렬화 실패도 로그에 보존했다. 기존 환경·원본 코드·R0/R1/R1.1 결과를 고치지 않았다.

## 6. 다음 단계 권고

원본 구성요소를 이용해 **구현 가능한 새 가설1개의 충실한 생성과 실제 계산**은 가능했다. 다음 연구의 의미 검증을 자동 면제하는 범용 성공 판정은 아니다. 이번에는 새 operator나 횡단면 회귀 기능을 만들 필요가 없었고, A안과 좁은 AST 정규화로 충분했다.

현재 신호는 유망성이 부족하므로 Task15 후보로 넘기지 않는다. Quanta의 같은 가격 가설 반복 탐색과 토큰 추가 투입을 중단한다. 이후에는 실제 새 경제적 정보·데이터의 가치가 있는지, 또는 RD-Agent가 같은 수식 재생성이 아닌 특징량·모델 상호작용 연구로 차별적 정보를 낼 수 있는지를 별도 작업으로 검토할 수 있다. 이번에 RD 연구·Task15·Forward 변경은 실행하지 않았다. 기존 Factory/Paper/Champion/Live/Team2도 변경하지 않았다.

## 最종 보존·재현 체크포인트

원본 converter의4회 실제 응답에서8개 제안이 반환됐다. 이들은 같은 동결 가설의 구현 변형이며8개 독립 알파가 아니다. 원본 반환 순서의 첫 후보 S0만 계산했다. AST 수정 후 같은 응답을 cache 재사용한 것은 추가 반환/실행으로 중복 집계하지 않았다.

시기별 RankIC는 미국2017/2019/2021 음수·2018/2020/2022 양수, 한국은2017만 양수·2018~2022 음수로 일관성이 약했다. 이 기간을 보고 사후로 좋은 연도만 고르지 않았다.

기존 R0 3,107/R1 366/R1.1 69/Task13 435/Task14 36개 manifest hash가 모두 보존됐다. 원본 checkout commit도 일치하고 운영 timer active다. [preservation.json](../../runtime/task13_r1_2/preservation.json). 신규 score/paired CSV4개는 압축 해제 SHA-256을 검증한 후 비압축 복사본만 제거해32,522,908bytes를 절약했다. 최종 runtime은 약8MiB다. [compression.json](../../runtime/task13_r1_2/compression.json). 모델 원문/실패/가설/수식/실행 증거는 보존하고 임시 relay는 종료했다.

재개 시 `contract.json`, `phase_b_verdict.json`, `analysis.json`, `preservation.json`, manifest부터 확인한다. 모델 호출이나 실제 가격 계산을 반복할 필요는 없다. 저장된 gzip을 직접 읽어 `.venv/bin/python experiments/task13_r1_2/analyze.py`로 통계를 재생할 수 있다. native_worker.py의 실패 경로는 historical 실패 증거가 남아 있으므로 무조건 재실행하지 않는다. `recover_completed_response.py`는 완료된 특정 응답을 exact-request 검증해 재생하는 이번 연구의 복구 도구이며 새 생성 성공을 만들어내는 일반 fallback이 아니다.

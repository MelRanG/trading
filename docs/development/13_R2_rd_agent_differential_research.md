# Task 13-R2 — RD-Agent 팩터·모델 독립 연구

판정: **NATIVE_PARTIAL / INSUFFICIENT_EVIDENCE**. 원본 팩터 생성 → Qlib 학습 → 원본 Feedback → 원본 후속 선택 → 모델 생성·학습 → Feedback의 실제 연결을 확인했다. 전체 `QuantRDLoop`는 실행하지 못했다. 신규 특징량의 미국 개발 구간 순위 정보에는 작은 단서가 있으나, 사전 경제적 방향·내부 검증·한국 이전 결과가 일관되지 않아 증분 알파 성공으로 판정하지 않는다. **Task15·추가 OHLCV 반복 탐색·전략 승격은 실행하지 않는다.**

## 1. 원본 실행 범위와 기존 RD_SMALL

- 원본 `microsoft/RD-Agent`, commit `484776c211e4fbbeef03e0ec00d6bbee7362a4f4`; 기존 checkout·`task6-rd-env`·`quant-research-task6:local` 재사용. 새 설치·수집 없음.
- 원본 `quant.py`, `quant_proposal.py`, `developer/feedback.py`와 QuantTrace를 조사했다. 팩터/모델의 coding/running/feedback 분기가 같은 연구 이력을 사용한다.
- 전체 controller 생성자는 기본 factor source 준비 중 Docker 환경 접근에서 실패했다. 격리 worker에 Docker socket을 제공하거나 환경을 재구축하지 않았다. 상세: `runtime/task13_r2/phase_a_probe.json`.
- 실제 사용: 원본 `QlibQuantHypothesisGen`, factor/model hypothesis converter, CoSTEER 구현 전략, factor/model Feedback, QuantTrace, Qlib `DatasetH`, `LinearModel`, `GeneralPTNN`. 호스트 adapter가 데이터·학습 결과 전달과 실행 순서를 담당했다. **전체 fin_quant 자율 controller 검증은 아니다.**
- 기존 RD_SMALL은 5입력 선형층+bias, 6개 파라미터였다. Task14의 미국 Ridge와 예측 상관 .9935는 독립적인 모델 계열의 차별성을 보여주지 않는다. 한국 부진의 원인을 구조만으로 확정할 수는 없다. 이번 B는 그 코드로 H20·확장 US 자료를 한 번 재학습한 비교군이며, 기존 H5 결과와 동일 조건 개선 비교가 아니다.

## 2. 입력·봉인·공정 비교

R0의 US176/KR126 **SURVIVOR_RESEARCH adjusted backfill**을 재사용했다. 원본 파일 SHA는 `runtime/task13_r2/contract.json`에 기록했다. 역사적 구성·상폐·기업행사 PIT 완전성이 없으며, 새로운 독립 Holdout이나 실거래 가격 자료가 아니다.

- H20: 신호일 이후 다음 세션 시가부터 21번째 세션 시가까지. warmup63, 특징량·label 경로 결측 제외, 날짜별 공통 적격 종목 ≥50. A/B/C/D는 동일 종목·날짜·target 교집합.
- fit: 2017~2020, label 종료도 2020-12-31 이하. 내부 검증: 2021-04-01 이후~2022, label 종료 2022-12-31 이하. 2021년 1분기 간격으로 label 중첩을 분리했다.
- US fit 141,110행/923일, 내부 68,673행/421일. KR 내부 32,071행/294일. KR 학습·정규화 fitting 없음. **모든 KR 결과는 미국 학습 모델의 이전 평가**다.
- 개발 조회는 코드·모델·scaler 동결 후 2023-04-03~2024 말의 성숙 label에 한 번 수행했다. US71,525행/419일, KR36,477행/322일. 2025~2026은 조회하지 않았다. 해당 개발 자료도 기존 노출 역사 자료다.
- worker는 US fit HDF만 받고, evaluator는 KR·내부/개발 자료를 별도 처리했다. 첫 가설 생성 때 mount가 2022까지 포함된 US 파일이었던 경계 결함을 기록하고 코딩 전에 fit-only로 좁혔다. 첫 LLM 입력은 2017년 첫 3행과 범위 metadata뿐이었고 2021~2022 실제 값·label은 전달하지 않았다. 최초 경계가 완벽했다고 주장하지 않는다(`worker_input/receipt.json`).
- 내부 결과는 US만 연구 Feedback에 전달했다. KR 및 개발 결과는 연구자에게 전달하지 않았다. 봉인과 동결 후 동일성: `candidate_seal_before_development.json`, `development_integrity.json`.

## 3. 실제 가설·코드·연구 반복

신규 특징량 한 개:

`F = -mean5( ((High-Low)/Close) / (Volume/mean20(Volume)) )`

상대 거래량 대비 장중 가격 충격이 작은 종목의 유동성·흡수 능력이 이후 수익과 연관된다는 가설이다. 사전 방향은 **F가 클수록 양의 H20**. 거래량 평균20일과 최종5일 모두 full window, 양의 가격·거래량·range, 무효 입력은 NaN으로 고정했다. OHLCV 대리변수이며 실측 호가 스프레드·기관 수급으로 취급하지 않는다.

원본 hypothesis → converter → factor CoSTEER 생성 코드와 독립 pandas oracle을 US/KR 전량 대조했다. prefix 재계산·미래 OHLCV 교란 후 과거 값 불변·결측 조건 검증을 통과했다(`training/factor_proofs.json`, `feature_oracle.py`). 표준 5특징량과 일별 순위상관 최대 절대값은 US .742/KR .692(주로 변동성). 완전 중복은 아니지만 독립 정보의 확증도 아니다.

비교군:

| 구성 | 입력·학습기 |
|---|---|
| A | ret1·MOM20·MOM60·VOL20·상대거래량20 + 원본 Qlib Ridge(alpha=1) |
| B | 동일5입력 + 기존 RD_SMALL 선형층+bias |
| C | 동일 Ridge에 F 한 개 추가 |
| D | RD가 생성한 6입력 + F×VOL20, F×상대거래량20의 두 상호작용 회귀 |

A/C는 각각 5/6개 학습 slope, intercept는 원본 Qlib 기본값 0 고정이다. metadata의 parameters 6/7은 고정 intercept 슬롯까지 포함한다. B/D는 6/9개 학습 파라미터다. B/D는 seed42·20epoch·batch256·lr.001·CPU2/4GiB, 원본 Qlib 내부 검증 최소 MSE checkpoint를 사용했다. 추가 seed·기간·학습률 탐색 없음.

1. 최초 원본 선택은 bandit의 factor 경로. 실제 C 내부 성과가 A보다 나빠 원본 factor Feedback은 **False**였다.
2. 팩터 실험과 평가를 QuantTrace에 넣고 **원본 LLM action selection이 model을 선택**했다. 호스트가 선택값을 대신 만들지 않았다.
3. Terra가 위 상호작용 모델 가설, Luna가 원본 converter/CoSTEER 모델 코드를 생성했다. 독립 tensor 연산 대사로 정확한 9파라미터 구조를 확인했다.
4. D를 한 번 학습하고 US 내부 실측값을 원본 모델 Feedback에 전달했다. Feedback은 **True**, 단 IC 음수·작은 RankIC·중첩 label 때문에 탐색적이라고 명시했다. 이 decision은 원본 내부 연구 판정이며 공식 승인·알파 확증이 아니다.
5. 두 실험이 공유 trace에 남았다(`native/rd/complete.json`). 다음 연구는 실행하지 않았다.

B/D wall 학습시간은 63.45/63.92초, Qlib best epoch(0-based)는 18/8, 내부 native validation MSE는 .00943552/.00932621. 저장 checkpoint·20epoch 손실 이력은 `training/B.pth`, `D.pth`, `histories.json`. Qlib 배치 집계 loss와 전체 표본 오차의 미세한 차이를 별도로 보존했다.

## 4. 실제 예측 결과

IC/RankIC는 날짜별 횡단면 상관의 평균, MSE/MAE는 수익률 소수 단위의 전체 행 오차다. 거래비용·포트폴리오 수익률이 아니다.

### 내부 검증(2021~2022)

| 시장 | 모델 | IC | RankIC | MSE | MAE |
|---|---|---:|---:|---:|---:|
| US | A | -.00150 | -.01405 | .00937446 | .072884 |
| US | B | -.00261 | -.01582 | .00943617 | .072857 |
| US | C | -.01399 | -.01796 | .00941542 | .072947 |
| US | D | -.00892 | .00427 | .00932779 | .072357 |
| KR 이전 | A | .03133 | .00597 | .01316204 | .083824 |
| KR 이전 | B | .03343 | .01548 | .01335603 | .085823 |
| KR 이전 | C | .02392 | -.01368 | .01361586 | .086210 |
| KR 이전 | D | 0.01685 | -0.00995 | 0.01349331 | 0.086372 |

### 동결 후 개발 진단(2023~2024, 한 번 조회)

| 시장 | 모델 | IC | RankIC | MSE | MAE |
|---|---|---:|---:|---:|---:|
| US | A | .03596 | .01935 | .00773668 | .065251 |
| US | B | .02478 | .00983 | .00721596 | .062754 |
| US | C | .05727 | .02985 | .00776204 | .065511 |
| US | D | .03181 | .00686 | .00719332 | .062495 |
| KR 이전 | A | -.00640 | -.06643 | .02134746 | .095829 |
| KR 이전 | B | -.01505 | -.06440 | .02149552 | .097572 |
| KR 이전 | C | .02561 | -.04425 | .02205023 | .098806 |
| KR 이전 | D | .02427 | -.05083 | .02159576 | .097836 |

해석과 불확실성(`analysis.json`):

- US C−A RankIC +.01051, 20세션 circular block bootstrap 95%구간 **[−.00116,+.02104]**. C 예측을 A에 당일 횡단면 잔차화한 진단 RankIC는 +.02838 [+.00441,+.05206]. 추가 순위 정보의 단서는 숨기지 않되, 사후 잔차 진단·반복 노출·다중 조회를 고려하면 확증은 아니다.
- C의 F 계수는 **−.01794**로 사전 단독 경제 방향과 반대다. 학습 모델의 개선을 최초 가설 적중으로 표현할 수 없다. US C RankIC는 2023 .06374/2024 .00227, A는 .05557/−.01013. 내부 구간에서는 C가 A보다 나빴다.
- D−B US RankIC **−.00298 [−.02539,+.01727]**. US 오차는 B보다 약 .31% 낮은 MSE이나 순위 성능은 개선되지 않았다. D−C RankIC −.022995 [−.04525,+.00106]. 모델 복잡화의 추가 알파를 지지하지 않는다. A/C의 고정0 intercept와 B/D의 학습 bias 차이도 있으므로, D−A의 오차 개선 전체를 새 특징량의 공헌으로 귀속하지 않는다.
- KR C−A RankIC +.02218 [+.00214,+.04123]이나 절대 RankIC가 음수다. 내부에서는 −.01966으로 방향이 바뀌었다. D−B 개발 개선도 +.01357 [−.00754,+.03403], 절대 순위 예측은 음수이며 MSE도 A/B보다 나쁘다.
- D의 실제 interaction 계수는 −.00299/−.00370, F 주효과 −.01090 (`trained_interaction_weights.json`). 연산은 존재하지만 효과의 인과적 증분은 입증되지 않았다. D와 C는 optimizer·bias·정규화도 달라 **D−C를 interaction만의 효과로 귀속하지 않는다**. 추가 ablation 학습은 하지 않았다.
- 421/419일 H20 기록은 독립 수만 개 사례가 아니다. 단순 비중첩 상한 약21/20개 구간, KR294/322일은14/16개 수준이다(정확한 유효 표본 추정 아님). 2,000회 block bootstrap은 기술적 진단 구간이며 다중비교 보정 확증이 아니다. 종목 생존편향·결측으로 시장 전체 일반화 불가.

따라서 **정보가 전혀 없다는 증명도, 유망 알파 확인도 아니다**. 현 실행은 `INSUFFICIENT_EVIDENCE`로 종료하고 같은 OHLCV·노출 구간에서 추가 모델/seed 탐색을 자동 권고하지 않는다.

## 5. 수정·실패 비용과 재현 경로

원본 checkout은 변경하지 않았다. 필요한 task-local adapter만 사용했다.

- 원본 모델 RAG의 478k/128k·GRU 권장을 실제 표본·H20·CPU·최대80파라미터 문맥으로 교체했다.
- 원본 Feedback의 연율수익 기본 항목 대신 실제 IC/RankIC/MSE/MAE를 전달했다. 원본 trace template가 존재하지 않는 연율수익을 강제해 실패한 후, 표시 fragment만 `trace_view.py`에서 실측 예측 지표로 바꿨다. 선택·가설 알고리즘은 원본이다.
- Luna의 factor task 응답은 LaTex 단일 backslash 때문에 JSON parsing 실패했다. 원본 converter의 같은 cache 5회 재시도도 실패 기록에 남겼다. `formulation` 문자열 escape만 복구했고 수식·숫자·코드는 변경하지 않았다. 새 모델 호출 없이 기존 원응답을 사용했다.
- CoSTEER task 속성/학습 mount/동적 모델 클래스 entrypoint 호환성 오류를 최소 수정했다. 최초 mount·entrypoint 실패는 학습 전에 발생했으며 로그를 보존했다. 모델 코드의 연산 변경이나 성과를 본 재학습은 없었다.
- 원본 model Feedback의 동일 요청 2회 호출을 실제 SHA로 확인했다. 첫 호출만 upstream, 두 번째는 exact memo였다(`model_feedback_invocations.json`). 다른 후보나 다른 결과를 cache로 대체하지 않았다.
- Qlib history 설명의 loss 부호를 원본 `metric_fn`과 대사해 positive MSE/lower better로 바로잡았다. 숫자는 변경하지 않았다.

핵심 실행 명령(중복 연구 재실행 금지, 기존 완료 파일 먼저 확인):

```bash
PYTHONPATH=src .venv/bin/python experiments/task13_r2/phase_a.py
# 기존 probe.py / run_native.py는 원본 환경·격리 worker에서 실행; model_calls 재사용
PYTHONPATH=src .venv/bin/python experiments/task13_r2/run_training.py factor
PYTHONPATH=src .venv/bin/python experiments/task13_r2/run_training.py model
PYTHONPATH=src .venv/bin/python experiments/task13_r2/run_development.py
# 완료 후에는 아래 읽기 전용 통계만 재생
.venv/bin/python experiments/task13_r2/analyze.py
```

초기 setup_transport.py는 최종 adapter를 덮어쓰지 못하도록 종료시킨 역사 bootstrap이다. 모델 호출 원문·native 산출물·checkpoint·실패 로그와 seal은 보존한다. 압축된 파일의 원해시/복구 명령은 `archive_receipt.json`; 코드 재실행에 필요한 `.pkl`/HDF는 먼저 복구한다. 기존 R0/R1/R1.1/R1.2/Task13/14 manifest 총4,169개 파일 해시가 모두 일치했다(`preservation_audit.json`).

검증: 신규 의미·결측·미래교란·JSON 원문 보존 테스트 **3 passed**, AGENTS 필수 회귀 4개 suite **24 passed**, 최종 compileall 성공. 선택적 미설치 CatBoost/XGB 경고는 해당 엔진 검증 성공으로 집계하지 않았다. 실제 원본 factor/model Qlib 실행 증거는 unit test와 별도다.

## 6. 모델 사용량·역할·다음 결정

| 내부 연구 모델 | 목적 | 실제 호출 | 입력(캐시 포함) | 캐시 부분 | 출력 | 총 토큰 |
|---|---|---:|---:|---:|---:|---:|
| gpt-6.1-terra | 최초 경제 가설·실측 Feedback 후 action 선택·후속 경제 가설 | 3 | 76,135 | 22,272 | 572 | 76,707 |
| gpt-6-luna | 팩터/모델 task·code·Feedback | 6 | 153,405 | 69,504 | 2,818 | 156,223 |
| 합계 | 실패 JSON 응답 포함 | **9/12** | **229,540** | **91,776** | **3,390** | **232,930/300,000** |

호출 CLI는 `model_reasoning_effort="medium"` 명시. cached는 input의 부분집합, reasoning은 output의 부분집합이며 중복 가산하지 않았다. global reservation은 두 role을 합산한다. 토큰 상한은 provider usage 사후 집계와 요청 전40k headroom으로 관리했고 실제 한도 이내였다. upstream wall 응답시간 약109.75초. 실제 금액 청구 정보는 없어 비용(달러)은 N/A. 파싱 실패 응답을 비용에서 제외하지 않았다. Codex 작업 모델 `gpt-6.1-sol`은 RD 내부 호출 모델과 별개이며 이 표에 작업 세션 사용량을 합산하지 않았다. 이번 배분은 모델 품질 우열 비교 실험이 아니다.

**역할 추천:** RD는 제한된 특징량→실측 Feedback→모델 선택의 연구 도구로 재사용 가치가 있다. 현재 증거로 Quanta보다 투자 예측력이 우수한 우선 엔진이라고 선정하지 않는다. Quanta는 DSL 가설·진화, RD는 특징량과 소형 모델의 결합 연구라는 기능상 차이를 유지한다. 양쪽의 현재 OHLCV 연구 결과로 우승 엔진을 정하지 않는다.

다음 검토는 새로운 PIT 실적/공시·산업 정보가 차별적 경제 가설을 제공할 수 있는지부터 시작하는 것이 적절하다. 이번에 추가 수집·RD/Quanta 재탐색·Task15·Forward 변경을 실행하지 않았다. 기존 운영 `quant-operations.timer`는 active, 운영 전략·계좌·권한 파일은 이 작업에서 수정하지 않았다. 임시 연구 relay는 종료했다. **경제적 투자 성과와 독립 Forward 일반화는 미검증**이다.

산출물 관리: task-local 33개 중간/예측/state 파일을 SHA-256 복원 대조 후 gzip 보관하여 89.06 MiB 절약했다. runtime은 현재 약 115.3 MiB이며, 기존 Task 파일은 정리하지 않았다. 최종 목록·해시는 `runtime/task13_r2/artifact_manifest.json` 참조.

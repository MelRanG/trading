# Task 13 — 팀3 네이티브 알파 생성·실행·초기 진단

2026-11-16 KST · HYBRID_MINIMAL · 노출된 역사 자료의 제한 연구

## 핵심 결과

**신규 다섯 후보를 미국·한국 실제 자료에서 계산/학습·예측했다. 실행 가능한 산출물 확보는 완료했지만, 유효한 투자 알파를 발견했다는 결론은 내리지 않는다.**

- Vibe 원본 팩터 2개, Quanta 원본 신규 가설/DSL 팩터 2개, RD 원본 CoSTEER 생성 선형 모델 1개다. 모델은 시장별로 따로 학습했다. 기존 Task6/10 결과를 새 성공으로 집계하지 않았다.
- Quanta의 두 original trajectory는 코드→실제 fit 진단→원본 feedback→pool 기록까지 실행했다. 이후 **mutation guidance·가설·수식은 생성됐지만 후보 상한에서 코드 생성 전에 차단**됐다. crossover/full AlphaAgentLoop는 미실행이다.
- 실행 후보는 5개지만, 원본 converter가 요청보다 많이 반환해 **실제 제안은 9개(Quanta6+Vibe2+RD1)**였다. Quanta5/전체8의 자체 사전 상한을 초과한 반환을 숨기지 않고 **4개 미실행 제안과 중단 이유를 보존**했다. 추가 호출로 수를 맞추지 않았다.
- 신호가 약하거나 시장별로 불안정하고, Quanta 추세 후보는 Vibe 추세와 높은 중복을 보였다. **전체 상태는 `INSUFFICIENT_EVIDENCE`**다. Task14의 제한 진단 입력으로는 넘길 수 있으나 독립 확증·Task15 경제성 통과·전략 승격은 아니다.
- Terra 실제 13회, **339,438 tokens**(cached input 포함), 신규 데이터 요청/설치 0. 공식 Factory·Paper·Champion·팀2·Forward·Live 경계는 변경하지 않았다. 최종 시험 **29 PASS**.

근거: [사전 계약](../../runtime/task13/contract.json), [최초 봉인](../../runtime/task13/preregistration.json), [모든 제안·실패 원장](../../runtime/task13/attempt_ledger.json), [후보 코드 봉인](../../runtime/task13/candidate_seal.json), [초기 진단](../../runtime/task13/diagnostics/initial_diagnostics.json), [Task14 전달 계약](../../runtime/task13/task14_handoff.json).

## 1. 학습 표본 점검과 별도 track

Task11·12와 AGENTS.md를 재확인했다. 기존 tracked 5파일 diff는 유지했고, 이번 변경은 `experiments/task13/`과 새 증거/보고서에 한정했다. 기존 원가격 S의 warmup63 fit은 다음과 같다.

| 시장 / H | 종목×날짜 label | 실제 날짜 | 유효 종목/일 | H 간격 비중첩 block 수의 상한 |
|---|---:|---:|---:|---:|
| US5 | 1,406 | 37 | 38 | 7 |
| US20 | 836 | 22 | 38 | 1 |
| KR5 | 820 | 41 | 20 | 8 |
| KR20 | 520 | 26 | 20 | 1 |
| 양시장60 | 0 | 0 | — | 0 |

block 상한도 통계적인 유효 독립 표본량이 아니다. 같은 시장의 종목과 겹친 label은 상관된다. 이 표본으로 복잡한 모델의 일반화 성능을 평가하지 않았다. warmup/horizon을 임의로 낮춰 fit 성공을 만들지 않았다.

대신 이미 수집한 Task6 **2022~2025년 조정주가 주장 자료를 별도 track으로 검토·재사용**했다. [sample_audit.json](../../runtime/task13/sample_audit.json)은 파일/receipt hash·날짜·중첩·소스 한계를 남긴다. [contract.json](../../runtime/task13/contract.json)의 `sources`는 원본 경로·공급자 최초 관측 시각·adjusted claim을 보존한다. 가격·volume의 구조, 중복 날짜와 양수 가격, 원본 receipt hash를 검사했다.

| track | 연구·학습 | 이후 진단 | 제한 |
|---|---|---|---|
| NOMINAL_S | Task12 원가격, 기존 fit2025/validation2026. 이번 두 엔진 연구 worker에는 전체 tape 미제공 | 팩터 4개를 동일한 2026년1월~11/13 원가격 S에서 계산 | current-survivor 코호트·기업행사/PIT 미완전. 모델은 이 짧은 fit에서 학습하지 않음 |
| ADJUSTED_RESEARCH | 익명 US38의 ≤2024 입력으로 Quanta/RD 생성. RD 학습은 시장별 아래 분할 | RD는 2025-02-01 이후 US/KR 별도 예측 | provider-adjusted claim, 독립 기업행사 인증 아님. nominal execution과 병합/손익 계산 안 함 |

조정 track의 warmup63/H5는 내부 분할 전 US663/KR678개 fit 날짜, H20은 US648/KR663개다. H60도 이 track에는 fit이 있지만 이번 후보의 primary로 선택하지 않았다. 원가격 H60 fit0이라는 사실을 조정 자료로 지우지 않는다.

원본 Qlib는 `valid`를 요구해 최초 실행이 학습 전에 중단됐다. 성과를 보기 전에 [내부 validation 보완](../../runtime/task13/inner_validation_amendment.json)을 기록했다: fit target **2024-07-01 이전**, 내부 checkpoint 선택은 **2024-08-01~연말**의 성숙 label, 외부 진단 signal은 **2025-02-01 이후**다. H5보다 긴 간격과 label purge를 확보했다. 모든 모델/기준선에 같은 fit과 fit-only 정규화를 사용했다.

| RD 실제 학습 | US | KR |
|---|---:|---:|
| fit 행 / 날짜 | 20,444 / 538 | 11,160 / 558 |
| fit target 마지막 | 2024-06-28 | 2024-06-28 |
| 내부 validation 행 / 날짜 | 3,800 / 100 | 1,880 / 94 |
| 외부 진단 행 / 날짜 | 8,512 / 224 | 4,360 / 218 |
| H5 비중첩 fit block 상한 | 107 | 111 |

이 규모는 5특징·6파라미터 선형 모델의 제한 학습에는 사용할 수 있지만 독립 시장 사례 수를 수만 개로 해석할 수 없다. 재무·거시·수급 vintage와 시점별 상장/상폐/거래정지의 완전성은 확보하지 않았다. 실제 다운로드는 2026년 backfill이며 과거 최초 관측으로 표시하지 않는다. 모든 2021~2026 연구 결과는 이미 노출됐고 현대 LLM의 역사 지식도 남는다.

## 2. 실제 원본 사용 범위

원본 버전과 환경은 Task12 [고정 버전](../../runtime/task12/engine_versions.json)을 재사용했다. 신규 설치·원본 checkout 수정은 없다.

| 엔진 | 이번 실행 | 이번에 실행하지 않은 것 |
|---|---|---|
| Quanta `b7ceb27…`, bundled RD0.8 | `generate_parallel_directions`, `EvolutionController`, native hypothesis→expression→`FactorParsingStrategy`, 실제 factor 계산, 원본 feedback/pool. mutation operator가 부모와 fit 결과를 읽어 새 방향·가설·수식 생성 | full AlphaAgentLoop/native Qlib backtest; mutation 코드/평가·완료 trajectory; crossover |
| RD `484776c…`, 별도 RD1.0 | 원본 model hypothesis/experiment/CoSTEER가 **새 선형 torch 코드** 생성. Qlib `GeneralPTNN`으로 시장별 실제 fit·예측·checkpoint | full fin_quant·GRU/대규모 architecture 탐색·새 재학습 루프 |
| Vibe `0025531…` | Alpha Zoo registry의 `qlib158_roc20`, `qlib158_std20` 원본 함수 실행 | 478개 전체 계산/경제성 평가, 새 LLM/Research Lab 백테스트 |
| Qlib0.9.7 | 원본 Pearson IC·Spearman RankIC, GeneralPTNN, LinearModel ridge, LGBModel | Qlib 전체 데이터/PIT 인증·새 플랫폼 설치 |

Vibe Research Lab의 과거 실사는 재사용하되 이번에는 Task15 범위인 매매 백테스트를 중복 실행하지 않았다. 계산은 기존 라이브러리·Qlib, source/label 연결은 한정 adapter다. **원본 구성요소+adapter 실행을 full controller 완주로 표시하지 않는다.**

연구 container는 네트워크 없음·CPU2·메모리4GB·원본/환경 read-only이며, 모델에 주는 입력은 **≤2024 fit prefix와 그 통계/fit feedback**뿐이다. 평가용 nominal tape·2025 진단 결과는 generation worker에 mount하지 않았다. 모델 transport는 기존 Codex 인증 relay를 재사용했고 호스트 도구·웹·agents를 비활성화했다. 이 호스트 전체가 과거 결과를 몰랐다는 뜻은 아니다.

## 3. 전체 후보·실패·중복 목록

성과 조회 전 Vibe 수식·부호·horizon을 선정했고, Quanta task/H·부모와 RD 모델 범위를 등록했다. 생성한 코드의 hash는 계산 전에 저장했다. 학습 후 weight hash·입력·평가 코드·horizon을 함께 묶은 시장별 `candidate_fingerprint`는 [handoff](../../runtime/task13/task14_handoff.json)에 있다. 최종 weight 결합 receipt를 최초 생성 전 봉인이라고 소급하지 않는다.

| 후보 / 원본 | 경제 가설·입력 | H / warmup | 실제 결과 |
|---|---|---|---|
| **V_ROC20** / Vibe | 20일 상대 추세 지속. 원본 `close[t-20]/close[t]`에 **사전 지정 -1** 부호 | 20 / 21 | 양시장 원본 score·literal formula 대사·prefix/미래 교란 통과 |
| **V_LOWVAR20** / Vibe | 낮은 과거 가격 변동계수의 **미래 수익 프리미엄**. `-std20(close)/close` | 20 / 20 | 양시장 score·수식 대사 통과. 변동성 예측을 수익률 예측으로 혼동한 실험 아님 |
| **Q0** / Quanta original | 20일 하락×평균 절대수익/거래대금의 liquidity-pressure reversal | 20 / 공통 보수적63 | 새 DSL/원본 코드·US fit feedback·양시장 nominal score 확보 |
| **Q1** / Quanta original | 20일 추세×5/20일 상대 거래량의 continuation | 20 / 공통 보수적63 | 위와 동일. 기존 추세와 높은 상관 확인 |
| **RD_SMALL** / RD CoSTEER | ret1·mom20·mom60·vol20·상대volume20을 사용하는 작은 return 모델 | 5 / 61 | 원본이 5계수+절편의 선형 모델 선택. 양시장 각각 실제 학습·예측·checkpoint |
| Q0 추가 / Quanta | downside-impact reversal 변형 | 20 | **미실행**. 원본의 두 번째 반환을 순서로 제외·보존 |
| Q1 추가 / Quanta | volume-confirmed momentum10 변형 | 20 | **미실행**. 순위/성과로 선택하지 않음 |
| Q2 mutation / Quanta | 부모 Q0와 다른 60일 overnight-minus-intraday log mean | 20 | native mutation guidance→가설→수식까지. **상한 차단, 코드/score 없음** |
| Q2 추가 / Quanta | 같은 60일 분해의 median 변형 | 20 | 위와 같이 **미실행** |

모든 제안의 이름·수식·부모·proposal hash·코드 유무는 [attempt_ledger.json](../../runtime/task13/attempt_ledger.json), 원본 trajectory는 [events.json](../../runtime/task13/native/quanta/events.json)에 있다. ZERO·QLIB_RIDGE·QLIB_TREE는 사전 지정 **기준선**이며 RD가 새로 발견한 알파 3개로 집계하지 않는다.

### 후보 수와 중단의 정확한 의미

1차 목표는 5개, 2차 조건부 목표는 추가 Quanta 최대3개/전체8개였다. 원본 converter가 매번 2개씩 반환했다. 처음에는 단일 후보 assert가 실패했고, [순서 선택 보완](../../runtime/task13/multi_task_amendment.json) 후 **첫 반환만 선택, 나머지도 제안 횟수에 포함**했다. 동일 request 재개는 relay cache를 사용했다.

두 original 및 Vibe/RD의 기술 실행이 확인된 뒤에만 [2차 유효성 gate](../../runtime/task13/native/quanta/phase2_authorization.json)를 열었다. 그러나 Q2 batch로 Quanta raw 제안이6개가 돼 **5개 상한을 넘었다**. 이 초과 반환 자체도 기록하고 추가 코딩/호출을 중단했다. 수를 채우거나 초과 제안을 숨겨 “5개 이내 생성”으로 보고하지 않는다. [중단 receipt](../../runtime/task13/research_stopped.json).

두 초기 방향은 metric 조회 전 planner가 제안했다. 다만 같은 Scenario를 이어 써 Q1은 Q0의 fit 요약을 보았으므로 두 original을 완전히 눈가린 A/B로 취급하지 않는다. 최소 세 경제 가설은 검토했지만, 별개 이름이 독립 알파를 뜻하지 않는다. 이 제한 연구로 엔진 전체 탐색 능력의 한계를 확정할 수 없다.

## 4. label·수식·누수 검사

공통 target은 close t까지 점수 → **open t+1 진입, open t+H+1 종료**의 H세션 return이다. 모델은 조정 주장 가격, 팩터 S는 nominal 가격으로 따로 계산한다. 실제 체결/매매 수익률이라고 표시하지 않는다.

- 같은 시장 세션에 정렬하고 필요한 중간 open이 없으면 label을 무효화한다. 종목의 다음 유효 행으로 미래를 당기지 않는다. 마지막 H+1 signal 세션은 미성숙이다.
- 팩터 4개×양시장에서 **prefix 재계산**과 **이후 가격×1.7·volume×2.3 교란**을 실제 실행했다. 과거 출력은 일치했다. 모델은 fit-only scaler·고정 checkpoint에서 이후 가격/volume 교란에 대한 과거 특징·예측 불변, `[B,1]` loss와 직접 MSE 일치를 확인했다.
- Vibe 출력은 원본 literal 공식과 대사했다. Q0/Q1은 US264/KR115개의 완전한 횡단면 날짜에서 직접 공식과 대사했고 최대 오차 **1.11e-16 / 0**이었다. DSL native raw result와 CSV score도 그대로 연결했다.
- **발견한 native 의미 차이:** Quanta `TS_MEAN`은 `min_periods=1`, `FILTER(false)`는 missing 대신0이다. task의 “완전한 window·otherwise missing” 설명과 다르다. 원본 함수를 바꾸거나 수식을 대체하지 않고 raw score를 보존했으며, 공통 평가에서 선언한 입력 window의 결측/비양수 mask를 엄격히 적용했다. Task14도 이 mask를 반드시 계승한다. 원본 전체의 missing 안전성이 검증됐다는 뜻은 아니다.
- Quanta feedback에는 실제 fit **IC/RankIC/spread**만 전달했고 annualized excess/수익률 alias는 만들지 않았다. 다만 Q1의 native feedback은 task 설명에 남은 “아직 평가하지 않았다” 문구 때문에 실제 첨부 metric의 귀속을 불명확하게 해석했다. [원문](../../runtime/task13/native/quanta/Q1/feedback.json)을 보존한다. **수치 전달 성공과 feedback 해석 정확성은 별개**이며 이 feedback을 경제적 승인으로 쓰지 않는다.

초기 [diagnostic v0](../../runtime/task13/diagnostics/initial_diagnostics_v0_maturity_mixed.json)는 미성숙과 성숙 구간의 가격 누락을 같은 결측 count로 묶었다. v1은 두 count를 분리했고 score·IC·수익 label 값은 변경하지 않았다. 기존 Task 결과를 수정한 작업이 아니다. 최종 [paired CSV](../../runtime/task13/diagnostics/)는 score/target을 함께 남겨 재계산할 수 있다.

이 검사는 코드의 주요 시점 오류를 탐지하는 기능 증거다. 생존편향·공급자 수정 이력·기업행사·LLM 역사 지식을 해소하거나 모든 누수가 없음을 증명하지는 않는다.

## 5. 최소 초기 진단 — 경제성/독립 검증 아님

### 팩터: 같은 nominal S, 2026년 signal 진단

평균 IC는 Pearson, RankIC는 Spearman이다. spread는 **각 시점 상위20%–하위20%의 H20 미래 가격수익 차이 평균**이며 거래 계좌 누적수익·비용 후 알파가 아니다. warmup·공통 입력 적격 mask를 적용했다.

| 후보 | US IC / RankIC | US spread | KR IC / RankIC | KR spread |
|---|---:|---:|---:|---:|
| V_ROC20 | -0.0099 / -0.0067 | +0.184%p | +0.0002 / +0.0080 | +2.766%p |
| V_LOWVAR20 | -0.0465 / -0.0509 | -1.309%p | +0.0815 / +0.0934 | +1.711%p |
| Q0 reversal | -0.0407 / -0.0315 | -1.754%p | +0.0073 / -0.0161 | -1.131%p |
| Q1 volume trend | +0.0060 / -0.0055 | +0.057%p | -0.0271 / -0.0156 | +1.167%p |

US各候補7,524 paired行/198日。KRは V_ROC20 **3,617行/191日**、V_LOWVAR20 **3,621/191**、Q0/Q1 **3,449/191**。不足 input window と label 区間の欠測を除外した結果で、無理に同じサンプル数へ補間しない。H20なら非重複 block は約9個の上限にすぎず、数千行を独立例としない。미성숙/성숙 구간 결측の正確な数は最終 JSON の `immature_label_cells` / `mature_window_missing_label_cells` にある。

**重複:** 日次横断面 Rank 相関平均は Q1↔V_ROC20 **US0.989 / KR0.961**、Q0↔V_ROC20 **-0.927 / -0.823**、Q0↔Q1 **-0.925 / -0.825**だった。取引量を追加しても現候補の順位は主に追随/反転で説明される。低変動候補は比較的異なるが米韓の符号が不安定だ。native mutation の新しい overnight 機構は計算されていないため、独立性や成績を推定しない。

### RDモデル: separate adjusted 2025 track、H5

| 市場 / モデル | MSE | MAE | IC / RankIC |
|---|---:|---:|---:|
| US RD_SMALL | 0.00224284 | 0.033138 | +0.0317 / +0.0342 |
| US zero | 0.00227781 | 0.033453 | 定数につきN/A |
| US Qlib ridge | 0.00224323 | 0.033143 | +0.0322 / +0.0368 |
| US Qlib tree | 0.00225983 | 0.033315 | +0.0040 / +0.0080 |
| KR RD_SMALL | 0.00319226 | 0.040396 | -0.0382 / -0.0256 |
| KR zero | 0.00274424 | 0.036703 | N/A |
| KR Qlib ridge | 0.00276338 | 0.036710 | +0.0345 / +0.0330 |
| KR Qlib tree | 0.00274973 | 0.036649 | +0.0165 / +0.0312 |

USのzero比MSE改善は約1.54%だが ridge とほぼ同等で、専門研究による明確な増分は確認できない。KRはzeroより約16.33%悪い。別市場で同じ architecture の係数を別々に fit した結果であり、US学習モデルのKR移植性能ではない。

selected checkpoint の実測 fit/internal MSEは US **0.00170167/0.00176042**、KR **0.00212465/0.00246774**。[US学習証拠](../../runtime/task13/models/US/metrics.json)、[KR](../../runtime/task13/models/KR/metrics.json)、コード/weight hash/予測/paired値を保存した。下流 tree control のエラーで最初のニューラル fit の epoch別履歴を保存し損ねたため、**その履歴は欠落**と記録した。同じ中間 checkpoint を回収し、selected loss を実測した。epoch別20行の履歴を捏造したり、履歴のためだけに再学習していない。

RDのH5 adjusted2025と他4候補のH20 nominal2026は**同一条件のエンジン順位比較ではない**。Task14では track/horizon/共通 maskを固定して評価する。今回の数値は正式な多重検定・国面一般化・Task15費用後成績ではない。

## 6. Task14への市場別受け渡し

| 候補 | US | KR | 次に確認すること |
|---|---|---|---|
| V_ROC20 | 技術PASS / INSUFFICIENT_EVIDENCE | 同左 | 弱いICとspreadの不一致、他候補との重複 |
| V_LOWVAR20 | 同左、初期符号は不利 | 同左、初期値は正 | 市場依存・国面/銘柄寄与・不確実性。KRの正値だけで採用しない |
| Q0 | 同左、開発fit後の診断は弱い | 同左 | 反転順位以外の増分、mask/PIT。train adjustedと診断nominalの差もあり原因を断定しない |
| Q1 | 同左 | 同左 | 既存trendとの高相関。独立アルファ数を水増ししない |
| RD_SMALL | 技術PASS / INSUFFICIENT_EVIDENCE | 同左、zeroより悪い | 単純ridgeとの差・小さな予測値の安定性・市場別学習条件。無条件再学習しない |

実測値・source/weight fingerprint・観測数・primary horizon・失敗原本を [task14_handoff.json](../../runtime/task13/task14_handoff.json) に固定した。入力/label/時点の主要検査を通ったため**限定診断の対象**にはできるが、現段階で `PROMISING` に自動分類する候補はない。Q2等4未実行は handed-off signal には含めない。

Task14で同じ履歴を使う場合は依然開発・診断である。HAC/block・family試行数・選択/失敗履歴を扱う正式検証はまだ行っていない。現金防御・リバランス・取引費用・最終戦略の順位は本Taskで評価しない。Task14/15を自動開始しない。

## 7. 実行失敗・資源・安全保全

**LLM:** Quanta10回/264,854 tokens、RD3回/74,584、Vibe0回。合計13回/339,438、そのうちcached input106,752。モデルは全て **gpt-6.1-terra**。native endpoint名`gpt-4o`は transport aliasで、ライブラリのGPT4o料金表示は実課金額ではない。現金費用は不明とした。[usage.json](../../runtime/task13/usage.json) と全 request/response/reservation/traceを保存した。最終統計・表作成のLLM呼出しはない。

計測した呼出し/トークン上限は守ったが、**raw提案数の上限超過は発生**し停止した。ニューラル fit は2市場の2回、中間 checkpoint を再利用した。基準線は固定設定であり失敗再実行を探索成功数に含めない。CPU2/メモリ4GBの各containerで実行し、全工程CPUの累計計測器はないため正確なCPU時間は主張しない。新データ取得・新依存性・新DB/常時サービス・公式研究登録/承認は0。

初期エラーは以下を保全し、修正後の成功と区別した。

- ホスト環境にPyTablesがなくHDF作成が失敗。CSV輸送と既存隔離環境のHDFを使用し、インストールしなかった。
- Quanta複数出力によるassert/提案上限停止。原本・未実行式・親/phaseを保全した。
- 原本Qlibのvalid必須、LGB dataset.segments、tracking初期化の接続不備。内部 split を事前補完し、既存Qlibの**ローカルMLflow file store**を明示opt-inした。新DB/サービスを作らず最終基準線fit/predictは完了。途中失敗ログは残した。
- Vibe venvにはQlibがなく初期評価import失敗。既存Quanta/Qlib環境に**原本Vibeソースをread-only mount**して算出した。Vibeアルゴリズムを代替実装に替えていない。
- 一度のlauncher改行/comment誤り、Q1 feedback帰属誤解、epoch履歴欠落も原本/原状を記録した。[失敗・中断一覧](../../runtime/task13/attempt_ledger.json)。

AGENTS最小4suite **24 PASS**、実新規artifactを使う受け入れ試験 **5 PASS**、compileall PASS。[安全XML](../../runtime/task13/safety_tests.xml)、[研究XML](../../runtime/task13/research_tests.xml)、[検査コード](../../experiments/task13/test_research_evidence.py)。原本score計算での未来交乱/数式大差も別途実行した。運用経路を変更していないため追加5運用suite/V104実行は今回は繰り返していない。初期失敗をこの29通過に混ぜて隠していない。

[preservation.json](../../runtime/task13/preservation.json) で Task6 completion922・Task10 2,339・Task12 69ファイルの既存manifest hash全件一致を確認した。既存ForwardソースはTask12修正版hashのまま、初期契約も保存されている。[既存timerの読み取り確認](../../runtime/task13/forward_readonly.log) は active、US/KRとも11/16完了セッション待ち、fill0/LLM0/Factory実験0だった。観測を止めず、未成熟Forwardを歴史研究の成功として計上していない。

Task13用一時relayとsocketは終了・削除した。原文・失敗・候補モデルは削除せず、共有入力は市場/trackごとに再利用した。最終manifestは [artifact_manifest.json](../../runtime/task13/artifact_manifest.json)。現時点の新規一式は約34MiBで、大部分は固定入力・検証用HDF/score・原本traceだ。最終件数/bytesはmanifestの実測値を正とする。

### 再現経路

```bash
# 原本・入力・候補・失敗を再利用する（LLMを再呼出ししない）
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q \
  experiments/task13/test_research_evidence.py
.venv/bin/python experiments/task13/finish_calculations.py
.venv/bin/python experiments/task13/final_audit.py
```

`prepare.py` は既存契約の上書きを拒否する。`run_native.py` は新研究の入口であり、**中断原本を確認せず全再実行しない**。native生成ログは [quanta初期/再開](../../runtime/task13/quanta_native_retry.log)、[RD](../../runtime/task13/rd_native.log)、学習は各 `models/{US,KR}/execution.log`。ソースは [experiments/task13](../../experiments/task13/) にある。

## 8. 次に必要な研究の具体的理由

1. **予測力検証の前提は整ったが不足証拠が多い。** この5候補に限定し、Task14で相関family・依存した観測・市場差と符号不安定を検証する。新規大量LLM生成を先行させない。
2. **volumeを足しても同じtrend順位だった。** 新しい名前より、異なる情報/特徴量・元仮説との増分を測る必要がある。財務・macroを使うならPIT vintageが先であり、欠測を埋めて作らない。
3. **RDは小モデルなら学習可能だが、現成果は単純線形と同程度。** 原本の固定巨大サンプル/GRU推奨boilerplateと実際の小規模Scenarioも区別する。epoch履歴保存・学習/基準線接続を最初から確実にし、直ちに大きなnetworkへ進まない。
4. **nativeの提案数・missing/window・feedback帰属を検査する必要がある。** これはアルファの経済的失敗とは別の実行/評価境界だ。次研究の前に出力上限とmetricのhash帰属を明示し、未実行mutation/crossoverを完了に数えない。

今回の判定は **生成・計算/予測=PASS、native evolution完走=PARTIAL、独立アルファ/経済的価値=未検証**。Task14に渡す範囲は上記固定候補の限定検証であり、公式戦略や実取引への自動適用ではない。

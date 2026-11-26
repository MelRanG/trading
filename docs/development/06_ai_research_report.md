# Task 6 — AI 자율 연구 엔진 구현·경쟁 검증

## 1. 핵심 결과와 추천

**`HYBRID_MINIMAL` 유지. Vibe를 기본 연구 작업자로 재사용하고 QuantaAlpha/RD-Agent는 선택 실행하는 격리 연구 후보로 둔다. 전문 엔진의 상시 운영·자동 전략 채택은 보류한다.** 원본 LLM 가설→실행 코드→공통 평가→원본 피드백→후속 연구가 실제 동작했다. 그러나 전문 엔진 추가의 일관된 투자 우위는 확인하지 못했다.

- 세 엔진에 같은 실제 모델(Terra), 같은 미국 train 입력, 같은 최대 호출·토큰·평가 기회를 제공했다. 원본 코드 변경 없이 공식 CLI/API를 실행하고 생성 코드·실패·usage·해시를 보존했다.
- 미국38·한국20개 주식과 벤치마크2개의 신규 backfill을 동결했다. 연구 worker에는 2024년까지의 미국 자료만 제공했고, 2025년 평가만 한 차례 피드백했다. 2026년 자료는 코드 동결 후 별도 evaluator가 평가했으며 연구 엔진에 반환하지 않았다.
- 미국 최종 구간에서 Vibe +12.59%, RD 후속 +10.25%, Quanta 후속 −6.56%, MOM63 +3.87%, 전체 주식 균등 최초 매수 +14.11%, 80% SPY 참고 계좌 +8.31%. 단순 결합은 Vibe보다 낮았다. 한국에서는 다른 순위가 나왔다. 전체 수치는 아래 표와 원본 CSV로 재현 가능하다.
- **전체 Task6의 모든 완료 조건을 충족한 것은 아니다.** RD의 실제 모델 학습·모델-팩터 공동 최적화, Quanta trajectory mutation/crossover 전체 제어기, 이번 생성물의 native Research Lab walk-forward, 공식 Factory 실험 등록·예약·실행은 미완료다. Factory는 실제 공용 일일 제안 예산에 차단됐으며 우회하지 않았다.
- 기존 운영 tracked diff는 작업 시작과 바이트 단위로 같다. Paper/DB/전략/Live/승격/예약을 바꾸지 않았다. 기존 PRE 683개 시험은 재사용 근거이며 이번 신규 시험 통과 수에 합산하지 않았다.

**투자 효능 한계:** 현재 명명 종목군으로 과거 membership·상폐 생애주기와 배당/조정 이력을 독립 입증하지 못했다. 신규 다운로드를 과거 최초 관측으로 취급하지 않는다. 최종 분할은 이번 작업자에게 숨긴 역사 자료이지 신규 Forward 또는 독립 PIT 알파 증거가 아니다. 모델의 과거 지식 가능성도 익명 티커만으로 제거되지 않는다.

## 2. 원본 버전·격리 환경·모델 인증

| 엔진 | 고정 원본 / 별도 환경 | 실제 확인 |
|---|---|---|
| Vibe | `0025531f005d4a7aac3fb884cda2fba9318e7158`, 기존 vibe-original / vibe-env | 공식 CLI 회사·연구·후속 실행 exit0. PRE Alpha Zoo/백테스트/Research Lab 상태·비용 시험 재사용 |
| QuantaAlpha | `b7ceb27b1001261d7a95b209a963664ae1f8ab23`, task6-quanta-env | quantaalpha0.1.0 + **rdagent0.8.0**, pyqlib0.9.7. 실제 native proposal/expression/template·feedback 실행 |
| RD-Agent | `484776c211e4fbbeef03e0ec00d6bbee7362a4f4`, task6-rd-env | **rdagent1.0.0**, pyqlib0.9.7. 실제 factor proposal/CoSTEER coder·feedback, model proposal 실행 |

세 checkout의 최종 Git 변경은 0. 두 specialist 설치와 `pip check`·핵심 import 성공. 별도 venv 두 개와 CPU image `quant-research-task6:local`만 추가했다. 설치 단계만 패키지 네트워크를 허용하고 연구/코드 실행은 `network=none`, user1000, cap-drop ALL, no-new-privileges, CPU2/memory4G/PID256로 제한했다. 운영 repo/DB·Docker socket·개인 인증 폴더를 worker에 mount하지 않았다.

**인증은 transport adapter다.** 신뢰된 host `codex exec`가 기존 ChatGPT 구독 인증으로 실제 `gpt-6.1-terra`를 호출했다. 외부 원본은 dummy scope key로 임시 UNIX relay에 요청했다. 원본 native Codex login 성공이나 실제 gpt-4o 실행을 주장하지 않는다. 원본 usage의 gpt-4o는 호환 tokenizer/provider alias다. host CLI의 shell/apps/web/MCP/multi-agent는 껐고 도구 제안은 worker에 데이터로 반환했다. 별도 유료 API 결제 없음. relay는 실행 종료 후 중지·소켓 제거했다.

`experiments/task6/model_relay.py`, `unix_forward.py`, `runtime/task6/evidence/versions.json`, `runtime/task6/native/*/{environment.lock,pip_check.log,probe.json}`, `runtime/task6/model_calls/`가 근거다. 요청을 실행 전에 예약하고 응답 cache와 실제 usage를 보존하므로 재시작으로 예산을 초기화하지 않는다. API가 hard token cap을 제공하지 않아 측정 후 차단이며 실제 사용은 한도 이내였다.

## 3. 실제 생성물·원본 기능의 검증 수준

| 엔진·시도 | 실제 가설/코드 | 결과·원본 범위 |
|---|---|---|
| Vibe 0 | 하락폭/과거20일 변동성, 과거평균 초과 거래량에 한정한 반전 | 공식 CLI가 hypothesis `hyp_f3aa2872196a`, goal `goal_484a3ee28ea9`, SignalEngine 코드 생성. 최초 /data read 권한 거부를 명시했고 실제 train CSV 내용은 읽지 못함. 제공 schema로 코드 작성 |
| Vibe 1 | 같은 코드, `NO_CHANGE` | 별도 CLI가 기존 hypothesis를 읽고 실제 validation을 invalidation_notes에 기록. 근거 없는 개선을 강제하지 않음. 원본 가설·목표 기록의 프로세스 간 지속성 확인 |
| Quanta 0 | 거래량 가중20세션 close location | native `AlphaAgentHypothesisGen` → `AlphaAgentHypothesis2FactorExpression` → `FactorParsingStrategy` 생성·실행 성공 |
| Quanta 1 | `close[t-5]/close[t]-1` | native feedback/Trace를 새 프로세스에서 읽고 후속 가설·DSL·코드 생성·실행 성공 |
| RD 0 | `1-close/open` | native `QlibFactorHypothesisGen`, `QlibFactorHypothesis2Experiment`, `FactorMultiProcessEvolvingStrategy` 생성·실행 성공 |
| RD 1 | 20세션 단순평균 close location | native feedback/Trace를 읽고 후속 생성·코드 실행 성공 |
| RD model | 20일 입력, hidden16 단층 GRU, train-only 표준화/분할·분기 재학습 제안 | native `QlibModelHypothesisGen`, `QlibModelHypothesis2Experiment` 실제 실행. **학습 코드/학습/성능 없음**. native ModelFBWorkspace readiness 실패, torch 미설치·Qlib conda 환경 없음. RD 호출10/10 소진 뒤 추가 coder를 실행하지 않음 |

각 factor 실행 exit0. Vibe 0/1은 동일 hash로 유효 고유 전략은 총5개이며 이를 서로 다른 성공 전략2개로 세지 않는다. 원본 모델 제안의 refit 주기도 아직 실행 정책이 아닌 제안이다.

**원본 전체와 구분:** specialist는 실제 US train HDF의 schema·샘플·실행 계약을 주는 `ResearchScenario` adapter 아래에서 원본 proposal/coder/feedback API를 호출했다. native Qlib dataset provider/calendar/instrument/features·중국 기본 벤치마크 전체 controller를 우리 미국 연구에 맞춰 완주한 것은 아니다. Quanta의 `pipeline/factor_mining.py` trajectory mutation/crossover는 코드 확인만 했으며 이번 2회 제한 루프는 그 재현이 아니다. expression consistency LLM guard는 `consistency_enabled=False`; DSL 파싱·원본 template 실행을 semantic guard 전체 통과로 표시하지 않는다. Vibe는 원본 Autopilot 가설/목표 bridge와 저장을 사용했으나 이번 새 코드의 native Research Lab walk-forward 전체 실행은 미검증이다. PRE 결과와 이번 공통 evaluator를 구분한다.

원본 경로는 Vibe `agent/src/tools/autopilot_tool.py`, Quanta `quantaalpha/factors/{proposal,feedback}.py`, `factors/coder/{evolving_strategy,function_lib}.py`, RD `rdagent/scenarios/qlib/{proposal,developer}`, `components/coder/{factor_coder,model_coder}`다. 이번 연결 코드는 `experiments/task6/{native_factor_stage,evaluate_worker,evaluation,research_bridge}.py`다.

## 4. 동결 자료·평가 계약

US40/KR20을 결과 확인 전에 고정했다. 현재 listing 검증 실패 V/SLB를 제외해 US38이 됐으며 유망 대체 종목은 넣지 않았다. 벤치마크는 SPY/069500.KS이며 **주문 대상 ETF 채택이 아닌 연구 참고 계좌**다. 총 logical request400/420, 종목당6페이지×200봉 상한. 기존 신뢰 host의 Toss 수집 경로만 사용하고 외부 엔진에 .env를 주지 않았다. 데이터는 대체로 2021/22~2026-11-12. source raw/hash/observed timestamp/receipt는 `runtime/task6/data/`에 보존했다.

`research_contract.json` → `split_manifest.json` → `candidate_freeze.json`이 입력·코드 동결 근거다. 첫 raw 수집 계약 hash 이후 시장 연구 전에 US-primary 범위를 명시한 amendment가 있었다. 두 hash를 같은 것으로 취급하지 않는다. 초기 US pagination 누락 가능성은 수익 확인 전에 중단·quarantine하고 provider nextBefore로 수정했으며 raw/실패 로그를 남겼다.

- Train ≤2024-12-31만 연구 worker에 mount. US38 익명 종목, 27,816행 OHLCV HDF. 관측하지 않은 VWAP/조정계수 proxy는 넣지 않음.
- Validation2025만 feedback, 한국은 같은 공식을 별도 적용. 연구 worker에 validation/final 경로·티커 원본 매핑을 mount하지 않음.
- Final2026은 모든 후보/평가 코드 hash 고정 후 단회 평가. 미국218·한국211개 공통 세션(2026-01-02~11-12). 최종 결과를 새 가설 생성에 주지 않았고 모델 relay도 종료.
- 같은 통화·시장 내 rank, positive top4·종목당20%·목표80% gross, 종가 t 신호→다음 적격 open, D-1 NAV/종가로 정수 수량 산정. 일별 재평가. 기존 MOM63/DEF120와 같은 실행 조건. 목표 exposure는 장중/종가 hard cap이 아니며 실제 노출은 각 results.json에 기록.
- 기존 `investment.research.replay_targets`의 fee/spread/ADV impact/참여율/현금 제약을 그대로 사용. 미국 매수·매도1bp, 한국1.5/21.5bp, halfspread5bp, 1%ADV impact10bp(최대50bp), 최소 주문 초기 NAV0.1%. 브로커 실제 요율 확정값 아님. 초기 USD100k/KRW10m, 환전 혼합 없음.
- IC는 다음 세션 `close/open-1`의 cross-sectional Spearman, ICIR은 일별 IC 평균/표준편차×√252. 평가 분할 마지막 라벨은 제외. 포트폴리오는 next-open 매수 후 보유하여 **예측 intraday와 overnight NAV 노출이 다름**. 이 매핑으로 연구 엔진 일반 성능을 대표하지 않는다.
- Prefix causal 검사(각6코드×2시장×validation/final)와 fill→cash/보유→NAV 독립 대사. 모든 대사 최대오차0. 원본 Quanta/RD 첫 공식의 수치도 독립 계산과 비교했다.
- 결합은 validation0 후, final 이전 명시한 **탐색적** 50:50 positive percentile rank. attempt1 고정, 최종 성과로 가중치/기간/종목/비용을 변경하지 않았다. 최적 결합이나 원본 Vibe 전체 능력의 검증이 아니다.

### 비용 후 수익·위험·예측 결과

다음 표의 Vibe/Quanta/RD는 각 최신 고정 시도1이며 시도0도 삭제 없이 results.json에 포함한다. `EQUAL_WEIGHT_STOCKS`는 기존 stock_targets의 최대4종목 기준선, `전체주식 최초균등보유`는 시장 cohort 전부에 최초80% 배분 후 보유하는 별도 비교다. 후자는 종목당20% 상한보다 작다. ETF100%는 노출이 달라 주 비교에서는80% 참고값을 쓴다.


**US — validation 250세션 / final 218세션. 비용 단위 USD.**

| 전략 | 2025 수익% | 2026 수익% | final SPY/KODEX80 대비pp | Sharpe | MDD% | 회전/초기자본 | 비용 | IC / ICIR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MOM63 | 23.74 | 3.87 | -4.43 | 0.30 | -30.28 | 61.06 | 3,849 | — |
| 방어형120 | 20.41 | 6.60 | -1.70 | 0.39 | -28.47 | 59.98 | 3,781 | — |
| 기존4종목균등 | 26.55 | 4.97 | -3.34 | 0.36 | -14.89 | 3.16 | 191 | — |
| 전체주식 최초균등보유 | 18.65 | 14.11 | 5.80 | 1.21 | -9.00 | 0.75 | 46 | — |
| Vibe (NO_CHANGE) | -8.71 | 12.59 | 4.29 | 0.76 | -12.63 | 284.73 | 18,077 | -0.0019 / -0.14 |
| Quanta 후속 | 8.76 | -6.56 | -14.87 | -0.15 | -26.81 | 160.66 | 10,128 | 0.0145 / 0.82 |
| RD 후속 | 7.72 | 10.25 | 1.94 | 0.67 | -15.54 | 100.62 | 6,388 | 0.0193 / 1.30 |
| Vibe+Quanta | 미평가 | -3.04 | -11.34 | -0.04 | -19.28 | 240.82 | 15,236 | 0.0162 / 0.96 |
| Vibe+RD | 미평가 | -9.87 | -18.18 | -0.54 | -23.51 | 207.58 | 13,158 | 0.0134 / 1.01 |
| alpha101_012 | -5.17 | -1.89 | -10.20 | 0.06 | -28.47 | 272.75 | 17,134 | -0.0106 / -0.76 |
| 벤치마크80% | 12.53 | 8.31 | 0.00 | 0.87 | -7.35 | 0.80 | 49 | — |
| 벤치마크100% 참고 | 15.58 | 10.29 | 1.99 | 0.88 | -9.09 | 0.99 | 61 | — |

**KR — validation 242세션 / final 211세션. 비용 단위 KRW.**

| 전략 | 2025 수익% | 2026 수익% | final SPY/KODEX80 대비pp | Sharpe | MDD% | 회전/초기자본 | 비용 | IC / ICIR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MOM63 | 12.16 | 13.06 | -18.39 | 0.55 | -43.12 | 65.59 | 1,106,244 | — |
| 방어형120 | 14.26 | 0.80 | -30.65 | 0.25 | -48.70 | 65.88 | 1,110,324 | — |
| 기존4종목균등 | 29.61 | 5.42 | -26.03 | 0.36 | -21.12 | 5.22 | 79,468 | — |
| 전체주식 최초균등보유 | 35.35 | 18.19 | -13.26 | 0.78 | -28.34 | 0.68 | 4,557 | — |
| Vibe (NO_CHANGE) | 7.38 | -12.69 | -44.14 | -0.50 | -25.35 | 165.05 | 2,794,535 | -0.0240 / -1.46 |
| Quanta 후속 | 9.32 | -2.71 | -34.16 | 0.09 | -25.13 | 133.53 | 2,251,713 | -0.0063 / -0.30 |
| RD 후속 | 5.47 | 12.44 | -19.01 | 0.57 | -37.43 | 79.96 | 1,349,957 | 0.0093 / 0.51 |
| Vibe+Quanta | 미평가 | -11.76 | -43.21 | -0.23 | -26.46 | 187.71 | 3,171,744 | -0.0069 / -0.37 |
| Vibe+RD | 미평가 | 5.29 | -26.16 | 0.35 | -37.16 | 166.44 | 2,817,759 | -0.0102 / -0.59 |
| alpha101_012 | -1.57 | 0.56 | -30.89 | 0.24 | -46.39 | 290.35 | 4,901,444 | 0.0120 / 0.71 |
| 벤치마크80% | 75.50 | 31.45 | 0.00 | 0.85 | -42.50 | 0.80 | 5,466 | — |
| 벤치마크100% 참고 | 94.30 | 39.31 | 7.86 | 0.92 | -46.85 | 1.00 | 6,874 | — |

최초 후보의 미국 validation은 Vibe −8.71%, Quanta −3.16%, RD −2.51%였다. 후속 개선은 final에 유지되지 않았다. 미국 결합의 Vibe 대비 증분은 Quanta −15.63pp, RD −22.47pp; 한국은 +0.93pp/+17.98pp지만 벤치마크80%보다 각각 −43.21pp/−26.16pp다. **전문 엔진 추가가 일관되게 좋아졌다는 근거 없음**이며, 다른 조합·훈련 모델 전체를 무효화하는 결과도 아니다.

`evaluation/{validation,final}/{US,KR}/results.json`에 시도 전체·시장 추세별 평균·실제 노출·IC 표본·월별 block bootstrap95% 구간을 저장했다. 일부 구간의 상·하한은 넓고 시장/기간이 두 개뿐이다. 선택/다중비교/생존편향과 사후적 종목/업종 membership 문제를 해소하지 못했으므로 유의한 알파를 판정하지 않았다. 업종별 PIT attribution은 입력에 없어 미실행. 비용은 재구성 순수 현금 비용이며 세금/배당/분할 이력의 독립 실사 부족을 숨기지 않는다.

## 5. 기업 분석 최소 실증

Microsoft 공식 FY2027Q1(2026-10-28) release를 신뢰 host가 수집하고 관측일/원문 hash와 함께 제한된 excerpt를 Vibe 공식 CLI에 제공했다. native run `20261113_045112_85_b35303`, 실제 Terra5회, exit0. 매출92,279m/영업이익45,915m/순익36,629m 등6개 핵심 수치의 원문 존재와 영업이익률49.756716% 산술을 독립 확인했다. 이것은 전체 재무 정확도 audit가 아니다.

다음 분기 bull/base/bear 매출100/95/90bn·마진51/50/46% 시나리오와 반증·하락 논거를 작성했다. **가정이며 실제 전망 정확도는 PENDING**이다. 할인율·현금흐름·순부채·주가·컨센서스가 없어 valuation은 abstain. DCF 수익성 검증이나 실제 투자위원회 다중 에이전트 debate 성공은 아니다. 공식 release를 제공한 사례이며 SEC 수집 성공을 뜻하지 않는다. source/result/native run은 `runtime/task6/company/`에 보존했다.

## 6. 효율·오류·원본 주장과의 차이

같은 engine별 최대10회/측정360,000tokens/실제Terra/2회 평가 기회. Vibe NO_CHANGE를 강제로 새 전략으로 바꾸지 않았고 RD는 남은2회로 모델 가설·명세만 생성했다. call수·총token은 cache 포함이며 달러 환산은 구독 실비 배분을 알 수 없어 null이다. cache를 제외한 금액 추정으로 가짜 비용을 만들지 않았다.

| scope | 실제 LLM 호출/성공 | 전체 tokens | output tokens | native 가설/코드 |
|---|---:|---:|---:|---|
| vibe | 7/7 | 328,196 | 3,521 | 2판단·고유코드1 |
| quanta | 6/6 | 164,230 | 2,555 | 가설/코드2 |
| rd | 10/10 | 254,607 | 3,173 | 팩터/코드2 + 모델 명세1 |
| company | 5/5 | 275,609 | 3,641 | 기업 사례1 |
| smoke | 1/1 | 23,580 | 106 | 인증 transport1 |

직렬 relay와 공통 host 경합 때문에 walltime으로 엔진 속도 승자를 정하지 않았다. 모델 error0은 원본 workflow error0을 뜻하지 않는다. 최초 구현 코드5개는 실행 성공했지만 다음 오류·제약을 별도로 보존했다.

1. **원본 수치 계약 결함:** Quanta TS_SUM min_periods=1 때문에 full-window20 요구와 달리 초기1,102개(58종목×19) 값이 생성됐다. 원본 수치 행동은 재현됐고 2025/26 평가는 warmup 이후라 수익은 바뀌지 않는다. 코드 수정·전략 재평가로 숨기지 않았다.
2. **근거 없는 연구 서술:** Quanta 후속 가설에 아직 시험하지 않은 equally-weighted 변경을 실패했다고 적은 문장이 있다. 실제 측정 근거가 없어 unsupported claim으로 분류했다. 최종 결과로 정당화하지 않는다.
3. **연결 오류:** 첫 feedback에서 implementation flag 누락, RD shallow-copy 결과 공유로 잘못된 피드백이 생성됐다. `feedback_adapter_rejected.json`을 남기고 Trace에서 제외, 정확한 상태/깊은 복사로 bounded 재호출. 두 회 재호출도 사용량에 포함. 원본 template이 요구하는 미산출 gross metric은 NaN으로 두고 net 결과를 gross로 바꾸지 않았다.
4. **후속 template 입력 실패:** Quanta code workspace 누락, RD no-cost metric key 누락. 공식 workspace 형식의 코드와 명시적 미산출 NaN key를 adapter에 제공해 재시도했다. 실패 로그 보존.
5. **환경·권한:** Vibe 최초 /data read_file 거부→공식 allowed roots 설정; 후속 LANGCHAIN_MODEL_NAME 누락→공식 환경변수만 추가; host/Vibe tables 누락→HDF를 기존 specialist 환경에서만 생성. 원본 수정/불필요한 설치 없음.
6. **모델 학습:** native ModelFBWorkspace는 conda/실행 python 경로 준비 실패와 torch 부재로 output 없음. 실제 GRU 모델 제안과 학습 성공을 구분한다. 정해진 RD 호출 예산도 소진됐으므로 추가 coder/학습을 억지로 진행하지 않았다.

[QuantaAlpha 논문](https://arxiv.org/abs/2602.07085)은 GPT-5.2/CSI300에서 IC0.0472, ARR4.68%, MDD11.8% 및 다른 시장 전이를 저자 실험으로 보고한다. [RD-Agent(Q) 논문](https://arxiv.org/abs/2505.15155)은 팩터-모델 공동 최적화와 자체 비교에서 더 높은 수익을 보고한다. 우리 모델·자료·포트폴리오·2회 탐색과 다르므로 이 숫자를 우리 성과에 옮기지 않는다. 이번에는 trajectory crossover/CoSTEER 반복 수리/모델 joint optimizer 전체를 재현하지 않았다. 기능의 가치 판단을 이 제한된 수익 표 하나로 일반화하지 않는다.

## 7. 최소 통합·Factory·Forward 상태

`research_bridge.py`는 원본 생성물/공통 evaluator hash를 동결하고 기존 `register_review_proposal` → `reserve_review_experiment` 경로로 handoff한다. 실제 호출 결과 **`BLOCKED_REGISTRATION: Factory daily proposal budget exhausted`**. 별도 registry·다른 날짜·작은 sample threshold로 우회하지 않았다. 기존 Task5 BLOCKED 실험을 이 결과로 대체하지 않았다.

`factory_handoff.json`의 제안/입력/fingerprint/중단조건을 보존한다. 오늘의 공통 연구 진단은 **Factory 공식 예약 실험이 아니며 승인·승격 효력이 없다**. 다음 적격 예산에서 동일 제안을 등록하고 별도 사전등록 Forward를 수행해야 한다. 예산 예약 전 실행 금지는 bridge의 공식 실험 경계에서 유지한다. source·계정·주문 권한 없는 연구 산출물 교환이며 신규 운영 scheduler/상시 gateway는 추가하지 않았다.

실제 최소 피드백은 원본 가설0 → 이번 공통 validation → 원본 feedback → 가설/코드1 → 별도 final 진단까지 완료했다. Vibe는 정상 NO_CHANGE. 연구별 원본 state.pkl/Trace, Vibe hypothesis/goal/native run, code/data hashes로 재시작 연속성이 보존됐다. 운영 거래 결과를 이번 역사 결과로 보충하지 않았다. 이번 연구 후보 모두 `SHADOW_ONLY / INSUFFICIENT_EVIDENCE / NOT_ELIGIBLE`이며 자동 Champion/Live 변경 없음.

후속으로 유지할 것은 Vibe 기본 worker·원본 상태관리, 공통 입력/출력 adapter와 선택적 Quanta/RD worker다. 추가 엔진 상시 실행·중복 scheduler·원본 백테스트 재구현은 하지 않는다. 필요한 다음 일은 (1) 공식 Factory 예산 처리, (2) 실제 PIT universe/corporate-action 입력 확보, (3) RD native CPU 모델 coder/학습 환경을 별도 예산에서 검증, (4) 다음 새로운 Forward 구간과 intraday 예측/보유기간 정렬 정책의 별도 사전등록이다. 이번 final을 반복 노출해 재최적화하지 않는다.

## 8. 시험·재현·보존

- compileall `src scripts tests` 및 `experiments/task6`: 성공.
- AGENTS 최소 4파일: V104 13 + crash3 + Paper parity3 =19개 최초 통과. V89 5개는 임시 UNIX socket을 fixture가 copytree하려다 실패. 모델 relay 종료/소켓 제거 후 영향받은 **V89만 재실행5개 통과**. 최종 합24통과, 최초 실패5건 로그 보존. 운영 코드와 시험을 고쳐 통과시킨 것이 아니다.
- 원본 생성·실행: specialist4건 exit0; Vibe 연구2건 exit0(NO_CHANGE 중복 포함); 회사1건 exit0. Native GRU학습·full controllers는 통과 아님.
- actual prefix probe24건, 독립 NAV/cash 대사, split180개 hash 점검 완료. 수치 계약 검사는 Quanta warmup 요구 위반1종을 발견했으므로 전부통과라고 표시하지 않는다.
- 운영 경로 변경이 없어 운영 DB/추가9파일/Forward 실행 전체를 반복하지 않았다. 이번 새 Paper 주문이나 서버 재부팅 시험도 하지 않았다. 기존 검증과 구분.

```bash
# 프로젝트 root, 기존 격리 환경·동결 데이터 사용. 원본 생성 반복 호출은 예산 확인 후만.
.venv/bin/python experiments/task6/verify_evidence.py
.venv/bin/python -m compileall -q src scripts tests experiments/task6
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q \
  tests/test_v104_end_to_end_causal_challenger_audit.py \
  tests/test_v104_2_jul30_crash_bridge.py \
  tests/test_v84_dual_paper_parity.py tests/test_v89_forward_governance.py
# validation reproduction (research者에게 final 전달 금지)
.venv/bin/python experiments/task6/evaluation.py --attempts 2
# final 원 명령: 같은 디렉터리 재실행은 guard가 차단. 단회 실행 결과 파일로 확인.
# .venv/bin/python experiments/task6/evaluation.py --attempts 2 --split final
# 공식 handoff 재개: 일일 예산·기존 Task5 대기 순서를 확인한 적격 시점에만
# .venv/bin/python experiments/task6/research_bridge.py
```

핵심 근거: `runtime/task6/{candidate_freeze,split_manifest,factory_handoff}.json`, `evaluation/*/*/results.json` 및 targets/fills/nav, `evidence/{model_usage,integrity_checks,incremental_effect,tracked_diff_integrity}.json`, `evidence/{safety_tests,safety_v89_after_relay_cleanup,safety_collection}.log`, `native/` 원본 로그·실행 결과, `model_calls/` 실제 호출 trace. 이 경로는 Git 제외 runtime이므로 보고서만 남기는 것으로 재현 보존을 대체하지 않는다. 원본 checkout/venv와 raw/state/artifact를 로컬 보존했다.

정리 내역/제거 파일 hash는 `runtime/task6/evidence/cleanup.json`에 별도 기록한다. 원본 checkout, 실험 입력·raw·판단·코드·Trace·usage·실패 로그·운영 원장은 보존하고 재생성 가능한 설치 사본·중복 평가 HDF/입력·임시 cache/소켓만 정리한다.

정리 실측: **18.82 GB** 제거. 대부분 이번 안전 시험 두 회차의 전체 프로젝트 복제 fixture(`/tmp/pytest-of-ansy/pytest-450`, `451`)이며, 설치 사본·중복 평가 중간 입력/HDF도 포함한다. 기존 pytest449 이하·운영 자료·설치 venv·원본/증거는 유지했다. 정리 후 180개 split hash·원본 공식 수치 검산을 다시 확인했다. 설치 사본 삭제 뒤 Quanta/RD import smoke도 별도 확인했으며 RD 첫 smoke의 기본 cwd `/` 로그 권한 오류는 작업 cwd를 `/tmp`로 지정해 재시도했다.

# BACKTEST AUDIT

## 1. 감사 결론

현재 백테스트는 당일 close 사용 방지, D-1 ADV, 비용·spread·impact, 미래변조 검사, 개발/검증/purged validation 구간을 갖춘 **일봉 결정론적 portfolio replay**다. 단순 수익률 계산기보다 훨씬 엄격하다.

그러나 다음 이유로 결과를 미사용 Forward 성과로 해석할 수 없다.

- 정적 현재 universe와 taxonomy
- 역사 수급의 사후 재구성 가능성
- adjusted data revision 시점 미보존
- 여러 버전·후보를 같은 역사구간에서 반복 탐색
- 2025~2026 `observed` 구간도 시스템 개발 과정에서 이미 반복 열람
- 실제 주문·broker state가 아닌 synthetic fill
- 신규 Forward 0세션

## 2. 백테스트 실행 경로

```text
V104 candidate spec
 → V77 market loader
 → V94 D-1 features/universe gate
 → V95 regime
 → V69/V79 selection + V98 policy
 → V100 target ledger
 → V102 evidence
 → V101 same-day-open synthetic execution
 → daily close NAV
 → metrics / parent delta / future mutation / causal audit
```

근거: `src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:108-288`.

V104 통합 감사는 모든 후보 replay, 지표, 역사 positive inventory, causal mutation, legacy parent parity, adapter gate를 만든다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:334-456`).

## 3. 데이터 구간

대표 실행 구간은 설정과 V101 metric 코드에서 다음과 같이 고정된다.

- 전체: 2018-01-02~2026-07-03 (`config/v77_corrected_price_allocation.yaml:5-6`)
- Development: 2018-01-01~2022-12-31
- Validation: 2023-01-01~2024-12-31
- Purged validation: validation 시작에서 60 sessions 제거 후 2024-12-31
- Observed: 2025-01-01~2026-07-03
- Recent 1Y: 2025-07-04~2026-07-03

근거: `src/quant_harness/v101_risk_execution_agent/engine.py:296-305`, `config/v101_risk_execution_agent.yaml:42-59`.

### 판정

구간 분리는 코드에 있다. 다만 `observed`는 릴리스 개발 중 반복 평가된 기간이므로 통계적 의미의 untouched forward가 아니다. 저장소도 역사 결과를 screening only로 선언한다(`RELEASE_STATE.json:106-125`).

## 4. Look-ahead bias 감사

### 확인된 방어

1. V94 eligibility와 liquidity는 shift(1) (`src/quant_harness/v94_universe_agent/policy.py:70-77`).
2. V95 benchmark·breadth·volatility는 shift(1) (`src/quant_harness/v95_market_regime_agent/policy.py:65-80`).
3. V69 momentum·trend와 selection record는 D-1 (`src/quant_harness/v69_dynamic_theme_leadership/engine.py:145-183`, `:303-306`).
4. V79 trend sleeve는 D-1이며 cutoff를 기록 (`src/quant_harness/v79_generic_trend_sleeve/engine.py:44-83`, `:211-215`).
5. 수급은 D-1이고 missing source current를 차단 (`src/quant_harness/v102_market_evidence_agent/policy.py:74-105`).
6. DART는 `received_at`의 전일까지 반영 (`src/quant_harness/v102_market_evidence_agent/policy.py:108-174`).
7. 실행은 목표 ledger를 same-day open에 체결하고 same-day close로 평가 (`src/quant_harness/v101_risk_execution_agent/engine.py:248-293`).
8. 미래 close/open을 변조해 cutoff 이전 target hash 불변을 검사 (`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:291-304`).

### 잔여 위험

- `universe.csv` 자체가 현재 목록이므로 과거에 사라진 ETF가 애초에 후보에 없을 수 있다.
- sector taxonomy가 현재 분류로 전 역사에 적용된다.
- adjusted OHLC가 사후 revision된 값인지 historical publication snapshot이 없다.
- 수급은 역사 재구성 파일이며 `downloaded_at`을 의사결정 gate에 사용하지 않는다.
- DART ETF mapping은 effective-dated가 아니다.
- future mutation은 가격 open/close에 한정되며 universe, taxonomy, flow, DART, mapping의 미래 변조를 각각 검사하지 않는다.

판정: **직접적인 same-day price look-ahead는 강하게 통제되지만 데이터 원천의 revision/PIT look-ahead는 완전히 제거되지 않았다.**

## 5. Survivorship bias 감사

### 확인된 방어

V94는 최초·최종 관측 bar와 실제 관측 count를 사용해 각 날짜의 eligibility를 만든다(`src/quant_harness/v94_universe_agent/policy.py:38-78`). 늦게 상장된 ETF가 상장 전부터 선택되는 문제는 방지한다.

### 확인된 제한

- 모집단은 `data/toss_v19c_daily/universe.csv`의 26개 현재 ETF로 시작한다.
- 코드가 `listing_source=OBSERVED_FIRST_BAR_PROXY`, `delisting_complete=False`, `corporate_action_verified=False`를 기록한다(`src/quant_harness/v94_universe_agent/policy.py:48-57`).
- 과거 상장 후 청산·합병·코드변경된 ETF의 완전 목록을 불러오는 경로가 없다.

판정: **상장 전 사용은 통제하지만 완전한 survivorship-safe universe는 아니다.**

## 6. Data leakage 감사

| 위험 | 확인 내용 | 판정 |
|---|---|---|
| 동일 날짜 close→open leakage | feature는 D-1, fill은 당일 open | 낮음 |
| future return을 selector가 직접 사용 | 활성 부모 policy는 사용하지 않음. V99 expected-value 후보는 mature된 사건만 walk-forward schedule에 포함(`src/quant_harness/v99_candidate_selection_deep_research/engine.py:156-218`) | 후보 연구에서는 통제됨 |
| 공시 발표 전 사용 | `received_at` cutoff 적용 | 낮음 |
| 수정된 과거 시장 데이터 | active input에 revision snapshot 없음 | 미해결 |
| 수급 revised history | 2026 다운로드 원본을 전 기간에 사용; 당시 최초판 미보존 | 미해결 |
| static ETF mapping/taxonomy | 현재 mapping/classification을 역사 전체에 적용 | 미해결 |
| cache leakage/staleness | V104 cache를 input hash 검증 없이 로드(`src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:349-367`) | 운영 재현성 위험 |

## 7. 사후 최적화·multiple testing 감사

### 구현된 통제

- V99는 development/validation/purged validation, bootstrap, family count 보정을 사용한다(`src/quant_harness/v99_candidate_selection_deep_research/engine.py:323-378`, `:568-652`).
- expected-value 후보는 outcome이 maturity position을 지난 사건만 학습한다(`:174-217`).
- V103은 역사 시도 원장을 재구성하고, 후보별 historical trial count와 familywise probability를 계산하며 역사 성과만으로 승격하지 않는다(`src/quant_harness/v103_review_feedback_agent/engine.py:143-185`, `:231-360`, `:430-459`).
- 자동 parent mutation과 capital authority는 false다(`src/quant_harness/v103_review_feedback_agent/engine.py:577-588`).

### 구조적 한계

1. V104 `_positive_inventory`는 여러 과거 버전의 `candidate_promotion.csv`를 스캔해 **양의 full delta 행**을 수집한다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:143-189`). 실패·중복 trial 전체를 immutable 원장으로 강제하지 않는다.
2. V104 forward priority 3개는 역사 결과를 본 뒤 config에 고정된 후보다(`config/v104_end_to_end_causal_challenger_audit.yaml`의 `forward_adapter_priority`; `src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:401-427`). Forward로 넘어갈 연구 후보를 고르는 것은 허용되지만, 역사 수치는 독립 검증 성과가 아니다.
3. V103 원장은 기존 report를 재구성한 release snapshot이며 append-only 외부 실험 registry가 아니다. 코드도 이를 `RELEASE_SNAPSHOT_ONLY`, `HISTORICAL_LEDGER_RECONSTRUCTED`로 기록한다(`src/quant_harness/v103_review_feedback_agent/engine.py:651-659`).
4. V99의 familywise 보정은 코드에 정의된 현재 후보 family count를 사용한다(`src/quant_harness/v99_candidate_selection_deep_research/engine.py:596-612`). 이전 릴리스에서 사람이 시도하고 폐기한 모든 아이디어 수를 자동으로 알 수 없다.
5. 2025~2026 observed 구간은 여러 후속 버전에서 반복 참고됐으므로 결과적으로 development set처럼 오염됐을 가능성이 높다. 이는 **추론**이지만 버전 V77~V104의 반복 연구 구조와 history inventory scan이 근거다.

판정: **사후 최적화 방지 규칙은 잘 설계됐으나, 이미 수행된 전체 연구 선택 과정을 완전히 봉인한 원장은 없다. 신규 Forward만이 최종 해법이다.**

## 8. 실행 현실성 감사

### 모델에 포함

- 매수·매도 수수료
- half spread
- participation 기반 impact
- D-1 ADV 1%/stress 0.5% cap
- 최소 주문금액
- 현금 cap
- 미체결 pending
- 정수 수량

근거: `config/v77_corrected_price_allocation.yaml:31-47`, `src/quant_harness/v101_risk_execution_agent/engine.py:109-245`.

### 미포함 또는 미검증

- 호가 tick size와 limit price rounding
- 장중 spread·quote freshness
- 가격제한·거래정지·동시호가
- broker reject/cancel/replace
- 부분체결 시간 경로
- 실제 세금·수수료 effective date
- 결제·미수·reserved cash
- 실제 market impact calibration

코드가 동일 항목을 Live blocker로 열거한다(`src/quant_harness/v101_risk_execution_agent/engine.py:517-528`).

## 9. 성과 수치의 해석 제한

- V104 후보 metrics는 같은 2018~2026 dataset을 전체 replay한 결과다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:369-378`).
- `historical_return_delta_pp`는 Paper entry gate의 필수 조건이 아니다(`config/v104_end_to_end_causal_challenger_audit.yaml`의 `paper_entry_gates`), 이는 역사 성과만으로 승격하지 않기 위한 올바른 설계다.
- 2026-07-30 crash bridge는 2026-07-03 당시 holdings를 외부 확인 종가로 평가한 것뿐이다. 신규 candidate selection·order는 실행하지 않는다(`scripts/run_v104_2_jul30_crash_bridge.py:11-32`).
- 현재 신규 Forward 관측은 0이고 역사 세션은 appender가 거부한다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:117-136`).

## 10. 재현성·감사 가능성

장점:

- target hash, order signature, candidate fingerprint, input hash
- 결과 CSV/JSON과 parent parity
- future mutation audit
- 코드·설정·데이터가 파일 기반으로 포함됨

공백:

- source code/version이 candidate input hash에 포함되지 않음
- benchmark와 ETF mapping이 input hash에 포함되지 않음
- cache 내용과 현재 input hash를 비교하지 않음
- 원본 공급자 response/retrieval metadata가 active V104 replay에 연결되지 않음

근거: `src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:77-105`, `src/quant_harness/v104_end_to_end_causal_challenger_audit/engine.py:349-367`.

## 11. 최종 위험 등급

| 항목 | 판정 |
|---|---|
| Same-day look-ahead | 낮음 |
| 가격 feature causality | 양호 |
| 공시 causality | 양호, 장중 cutoff 규칙 보완 필요 |
| Survivorship bias | 중간~높음 |
| Revision bias | 중간~높음 |
| Static taxonomy/mapping leakage | 중간 |
| Multiple testing/사후선정 | 높음, Forward 전까지 해소 불가 |
| Synthetic execution optimism | 중간~높음 |
| 실제 Live 준비도 | 미준비 |

현재 결과는 **연구 후보 screening 및 Paper engineering 검증**에는 사용할 수 있지만, 독립적인 실전 기대수익 추정치나 Live 승격 근거로 사용하면 안 된다.

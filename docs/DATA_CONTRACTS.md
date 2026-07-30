# DATA CONTRACTS AS-IS

## 1. 활성 V104 입력 원장

| 데이터 | 저장소 경로 | 소비 코드 | 실제 사용 방식 | 상태 |
|---|---|---|---|---|
| ETF 정적 목록·sector | `data/toss_v19c_daily/universe.csv` | `src/quant_harness/v77_corrected_price_allocation/engine.py:81-88`, `src/quant_harness/v69_dynamic_theme_leadership/engine.py:100-109` | 26개 ETF의 현재 목록·현재 sector taxonomy | 활성, PIT 원천 아님 |
| ETF adjusted OHLCV | `data/toss_v19c_daily/<ticker>_1d.csv` | `src/quant_harness/v77_corrected_price_allocation/engine.py:87-120` | source tag·OHLC 검증 후 pivot | 활성 |
| KOSPI benchmark | `data/all_prices_long_v62_9_expanded.csv` | `src/quant_harness/v77_corrected_price_allocation/engine.py:122-130` | `KS11` 행의 open/adj_close 사용 | 활성 |
| 시장 수급 | `data/historical_investor_flow/market_investor_flow_daily.csv` | `src/quant_harness/v102_market_evidence_agent/policy.py:74-105` | KOSPI, D-1 5일 합·z-score | 활성 |
| DART PIT 재무 | `data/opendart_quarterly_pit.csv` | `src/quant_harness/v102_market_evidence_agent/policy.py:108-174` | `received_at` 기준 수정공시 state | 활성 |
| ETF→주식 mapping | `data/agent_ready_v62_16/agent_etf_to_stock_mapping_v62_16.csv` | `src/quant_harness/v102_market_evidence_agent/policy.py:108-130` | ETF fundamental risk proxy | 활성, effective date 없음 |
| 뉴스 | `data/contracts/v102_news_evidence_template.csv` | `src/quant_harness/v102_market_evidence_agent/policy.py:176-216` | schema validation만 가능 | 데이터 없음 |
| V104 후보 정의 | `config/v104_end_to_end_causal_challenger_audit.yaml` | `src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:55-65` | candidate spec/fingerprint 원본 | 활성 |
| V104 runtime 후보 | `config/v104_challenger_runtime_contract.yaml` | `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:57-65` | enabled candidates·fingerprint·account label | 활성 |

## 2. 가격 데이터 계약

### 필수 필드

V77 active loader가 요구하는 필드는 `timestamp`, `open`, `high`, `low`, `close`, `volume`, `source`다(`src/quant_harness/v77_corrected_price_allocation/engine.py:91-95`). `ticker`는 파일명 기준으로 정규화된다(`:99-103`).

V87 canonical 계약은 `date`, `ticker`, `open`, `high`, `low`, `close`, `volume`, `value_approx`를 요구하고 `source`, `price_scale`, `provider`, `retrieved_at`을 추가한다(`src/quant_harness/v87_actual_data_ingestion/engine.py:143-186`).

### active date index

- 설정 기간: 2018-01-02~2026-07-03 (`config/v77_corrected_price_allocation.yaml:5-6`).
- 거래 index: core `069500`과 benchmark `KS11`의 관측일 교집합(`src/quant_harness/v77_corrected_price_allocation/engine.py:132-136`).
- 일부 원본 ETF 파일에 2026-07-03 이후 행이 있어도 active config end를 넘는 행은 잘린다(`src/quant_harness/v77_corrected_price_allocation/engine.py:103`, config 위 기간).
- non-core ETF의 tail이 짧아도 전체 index 자체는 유지되며, 날짜별 eligibility와 실행 open 검사에서 처리된다(`src/quant_harness/v94_universe_agent/policy.py:27-78`; `src/quant_harness/v101_risk_execution_agent/engine.py:121-125`).

### 품질 불변조건

- source는 정확히 `toss_openapi_1d_adjusted` 하나여야 한다(`src/quant_harness/v77_corrected_price_allocation/engine.py:96-98`).
- OHLC는 양수이고 high/low geometry가 맞아야 한다(`:104-111`).
- tradable price는 forward-fill하지 않는다(`:137-141`).
- ADV는 close×volume의 20일 median을 한 세션 shift한다(`:140-145`).

### 잔여 위험

1. active loader는 provider retrieval timestamp·revision lineage를 읽지 않는다.
2. adjusted OHLC 과거치가 공급자에 의해 나중에 재작성됐는지 active backtest 시점별로 재현할 수 없다.
3. V87 revision gate는 구현됐지만 V104 입력 앞단에 강제되지 않는다.

## 3. 유니버스·taxonomy 계약

### 실제 schema

`data/toss_v19c_daily/universe.csv`는 `ticker`, `name`, `sector`, `asset_type`을 가진다. 코드가 이 파일을 전체 역사에서 동일하게 사용한다(`src/quant_harness/v69_dynamic_theme_leadership/engine.py:100-109`).

V94는 다음 파생 정보를 만든다.

- `available_from`, `available_to`: 최초·최종 실제 관측 bar
- `status`: 데이터 끝까지 관측됐는지 여부
- `listing_source=OBSERVED_FIRST_BAR_PROXY`
- `delisting_complete=False`
- `corporate_action_verified=False`

근거: `src/quant_harness/v94_universe_agent/policy.py:38-57`.

### 계약 판정

- **날짜별 거래 가능성**: 구현됨.
- **역사 당시 전체 상장 ETF 모집단**: 보장하지 않음.
- **상장·상폐·코드변경·합병·청산**: 완전 원장 없음.
- **sector 분류 effective date**: 없음. 현재 taxonomy가 전 기간 sector dedup에 사용된다(`src/quant_harness/v98_candidate_selection_agent/policy.py:192-208`).

## 4. 수급 데이터 계약

원본 필드에는 `as_of_date`, market별 개인·외국인·기관 순매수, `source_id`, `source_url`, `downloaded_at`, `data_status`, `provenance_hash`가 있다. active builder는 이 중 KOSPI 날짜와 외국인·기관 값만 직접 소비한다(`src/quant_harness/v102_market_evidence_agent/policy.py:74-82`).

- rolling 값은 결측을 채우지 않는다(`:80-88`).
- source date가 직전 거래일과 같을 때만 current다(`:89-103`).
- repository snapshot의 원본은 `data_status=historical_reconstructed`이고 다운로드 시각이 역사 의사결정 시점보다 늦다. active code는 `downloaded_at`이나 revision history를 gate에 사용하지 않는다.

판정: **시계열 사용은 D-1 causal이지만 당시 최초 공표본을 재현하는 point-in-time revision 계약은 확인되지 않았다.**

## 5. DART·fundamental 계약

필수 schema는 `config/v102_market_evidence_contract.yaml:18-34`에 선언돼 있다. 실제 parser는 `ticker`, `corp_code`, `rcept_no`, `received_at`, 회계기간, 순이익, 자산을 사용한다(`src/quant_harness/v102_market_evidence_agent/policy.py:108-122`).

- `received_at`을 KST availability date로 변환한다(`:113-121`).
- 각 거래일의 전일까지 도착한 공시만 반영한다(`:135-142`).
- 같은 회계기간의 나중 공시가 이전 state를 대체한다(`:133-142`).
- ETF risk는 정적 ETF→주식 mapping의 최근 2분기 손실을 집계한다(`:125-174`).

잔여 제한:

- ETF 구성종목 mapping에 effective date와 weight가 없다.
- 장중 공시가 다음 세션부터 사용되는지, 당일 장전 공시를 당일 반영할지에 대한 거래시간 계약은 없다. 현재는 calendar `date-1 day` cutoff다(`:135-137`).
- report scope CFS/OFS는 읽지만 선택 우선순위·중복 처리 규칙이 명시적으로 강제되지 않는다.

## 6. 뉴스 계약

빈 template 경로: `data/contracts/v102_news_evidence_template.csv`.

필수 timestamps, source tier, document ID, correction chain, entity mapping은 `config/v102_market_evidence_contract.yaml:35-50`에 선언돼 있다. validator는 timestamp 순서·enum·event 중복·공식 critical veto를 검사한다(`src/quant_harness/v102_market_evidence_agent/policy.py:176-216`).

판정: **CONTRACT_ONLY / DATA_BLOCKED**. V104 adapter는 news dataset을 읽거나 validator를 호출하지 않는다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:108-129`).

## 7. 주문·체결 관측 계약

### synthetic V101 output

V101 replay는 다음 논리 필드를 생성한다.

- intents: requested, participation cap, cash cap, final quantity, decision reason (`src/quant_harness/v101_risk_execution_agent/engine.py:165-171`, `:220-226`)
- fills: reference open, execution price, fee, spread, impact, ADV participation (`:175-186`, `:229-236`)
- account: cash, NAV, holdings JSON, target JSON, pending, tracking error (`:281-292`)

이는 broker 원장 schema가 아니라 모델 결과다.

### 실제 broker observation template

`data/contracts/v101_execution_observation_template.csv`는 client/broker order ID, lifecycle timestamps, reject code, bid/ask, fill, fee/tax, broker cash/holding, quote/account as-of를 요구한다. 현재 데이터 행은 없다. 필요 항목은 V101 gap register 코드에도 열거돼 있다(`src/quant_harness/v101_risk_execution_agent/engine.py:517-528`).

## 8. Forward observation 계약

`data/contracts/v104_challenger_forward_observation_template.csv`의 필드는 `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:90-113`에서 생성된다.

강제되는 것:

- candidate fingerprint 일치
- parent/candidate input hash 일치
- 동일 cutoff
- target hash·order signature·NAV 기록
- history/forward 구분
- `(session,candidate_id)` idempotency

근거: `src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:65-89`, `:90-114`, `:117-154`.

강제되지 않는 것:

- 실제 데이터 ingest gate
- 실제 broker order/fill reconciliation
- quote/account freshness
- candidate account state recovery

`data_gate_passed`와 `reconciliation_passed`는 현재 항상 True다(`src/quant_harness/v104_end_to_end_causal_challenger_audit/forward_runtime.py:108-112`).

## 9. 데이터 provenance와 hash

V104 input hash는 다음을 묶는다.

- V69/V79/V95/V98/V100/V101/V102/V104 설정
- 정적 universe
- 모든 `*_1d.csv`
- 수급 파일
- DART 파일

근거: `src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:77-105`.

포함하지 않는 것:

- Python source code
- package/lockfile
- benchmark `data/all_prices_long_v62_9_expanded.csv`
- ETF→주식 mapping 파일
- V87 raw archive/retrieval metadata

특히 benchmark와 ETF mapping은 실제 결정에 영향을 줄 수 있지만 `_input_hash` 목록에 없다. 이는 Forward 동일 입력 계약의 공백이다.

## 10. 데이터 계약 최종 판정

현재 데이터 계약은 **파일 기반 역사 replay 재현성**에는 충분하지만, **실시간·증분·revision-safe·완전 PIT 운영**에는 부족하다. Codex 이전 후 가장 먼저 단일 authoritative ingestion output과 input manifest를 확립하고, V104가 그 manifest만 소비하도록 연결해야 한다. 전략과 임계값 변경 없이 가능한 인프라 작업이다.

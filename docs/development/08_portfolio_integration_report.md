# Task 8 — 투자 판단·포트폴리오 Shadow 통합

2026-11-14 KST / 실행 서버 시각 2026-11-13 UTC. **HYBRID_MINIMAL 유지. 기존 운영 전략·계좌·Live 잠금 유지.**

## 1. 핵심 결과: 기권까지 실제 결정·기록

독립 기업/퀀트 판단 계약, 추적 가능한 통합 판단, 위험·통화 경계, 기존 Paper로의 Shadow 연결, 공식 회사 발표 관측·후속 연구 계약을 구현했다. **이번 실제 판단은 B/C/D/E 모두 현금이다.** 기업 매출 전망을 기대 주가수익률로 바꾸지 않았고, 검증되지 않은 퀀트 신호를 자동 채택하지 않았다.

| 항목 | 판정 | 근거·남은 조건 |
|---|---|---|
| 8.1 Vibe 기업 분석 | PASS, 구성요소 범위 | 원본 earnings skill/ChatLLM을 실제 Terra 1회로 재실행, 2기업 수치 반환. full CLI grounding/fallback 자체는 수정·검증 완료로 표시하지 않음 |
| 8.2 독립 판단 계약 | PASS | 같은 input hash의 단독·통합 비교, 시점/기간/출처/불확실성/기권/비용 기록 |
| 8.3 위험·포트폴리오 | PASS, 기능 | 현금·비중·동일기간 충돌/상이기간 독립·중복 근거·종목/업종/상관 cluster/회전율 제약. 투자 효능 미입증 |
| 8.4 원본 대비 비교 | PASS, 제한적 | 실제 원본 HRP/IV/위험/현금 rebalance와 QH gate 비교. 회사 역사 신호가 없어 회사/통합 과거 수익률은 생성하지 않음 |
| 8.5 Shadow/원장 | PASS, 기권 사례 | 새 미국100,000USD/한국10,000,000KRW 계좌, NO_TRADE·NAV·재대사·멱등 복원. 비현금 실제 Forward 체결은 없음 |
| 8.6 기업 결과·복기 | PARTIAL | 기존 timer hook 실제 호출, CRWV 결과 링크 미발견 PENDING, NVDA 목록 접근 오류 PENDING_EVIDENCE. 합성 공식 발표의 SQL 채점·수정 이력·후속 연구 경로는 통과 |
| Task9 연결 | PASS, 최소 계약 | 실제 근거 부족 사건 3건과 후속 요청 저장. 연구 실행/예산 배분/전략 승격 자동화는 Task9 범위 |

**관련 회귀 51개(신규19 포함), AGENTS 안전·운영 회귀 53개 통과: 중복 제외 104개.** 실제 정량 예측 정확도·초과수익·위험조정 성과는 아직 미측정이다. 이전 Factory 예산 차단도 해제하지 않았다.

## 2. Vibe 기업 분석과 가치 판단 경계

원본 commit `0025531f005d4a7aac3fb884cda2fba9318e7158`, checkout clean. [버전·원본 경로](../../runtime/task8/source_version.json).

원본 `agent/src/agent/loop.py`는 grounding ledger를 도구 관측에 연결하고 마지막 iteration을 text-only로 제한하며, rejected draft 뒤 fallback을 반환할 수 있다. Task7의 CLI exit0과 유효 수치 분석 성공은 같지 않았다. 이 경로를 임의 완화하지 않고, **원본 `providers.chat.ChatLLM` + bundled `earnings-forecast/SKILL.md`**를 사용하는 최소 구성요소를 채택했다.

이번 실제 호출은 같은 Task7 동결 IR 원문·가격 packet으로 2기업을 한 batch 처리했다. 새 출력은 NVDA 매출 Bull/Base/Bear 114,000/108,000/100,000, CRWV 5,200/4,836/4,300 USD million이며 아직 가정이다. [새 응답](../../runtime/task8/company_response.json), [원본 실행](../../runtime/task8/evidence/native_component.log). Task7 최초 예측 8건은 그대로 별도 보존했다. 새 응답으로 과거 예측을 교체하지 않았다.

[company_analysis.py](../../src/quant_harness/investment/company_analysis.py)는 회사 identity, 인용 source ID, 유한한 숫자, 시나리오 순서·확률 합계, 목표 기간·반증 조건을 검사한다. 빈 facts의 CLI 기권/fallback, 미등록 출처는 실패로 처리한다. 이 gate는 형식/출처 적격성 경계이며 LLM 사실·경제 논리의 완전 자동 인증은 아니다. 실제 원문 수치 감사는 Task7 결과를 재사용했다.

기업 판단에는 가격·현금흐름·부채/희석·시장 기대가 필요하다. [decision.enterprise_to_equity](../../src/quant_harness/investment/decision.py)는 `주주가치 = EV - 부채 + 현금 - 기타청구권`, 주당 가치는 이를 주식수로 나누도록 분리한다. 예를 들어 CRWV의 Task7 가격/가중평균 주식수 대용치로 계산한 모형상 EV74,390.4는 주주가치가 아니다. 부채46,873/현금4,122를 반영하면 주주가치는31,639.4(USD million)이다. 이는 시장가격에서 역산한 항등식이며 적정가나 새 매수 근거가 아니다. 주식수·리스·기타 청구권을 완전히 검증하지 못하면 가치 신호는 기권한다.

독립 컨센서스가 없고 NVDA base는 회사 가이던스와 같다. CRWV base4,836은 연간 가이던스에서 9개월 실적을 차감한 midpoint와 같다. EBITDA·순이익·FCF도 구분한다. 따라서 실제 회사 판단의 expected equity return/downside는 `null`이고, 긍정적 성장 논거가 곧 투자 적격성을 뜻하지 않는다.

## 3. 독립 판단·통합 의사결정 계약

[정책](../../config/task8_portfolio.json), [결과 전 사전등록](../../experiments/task8/contract.json), [결정 엔진](../../src/quant_harness/investment/decision.py), [실제 입력·판단](../../runtime/task8/comparison_final.json).

기업 판단은 IR/기업 packet만, 퀀트 판단은 별도 가격 snapshot만 읽어 최초 결과를 생성한다. 각 결과는 team/engine/version, 종목·시장·통화, 관측/유효 시각, source hash, 기간, 가설/반증, expected return/downside/cost 또는 `null`, 유동성·업종·검증 수준을 갖는다. 기업 정성 판단을 임의의 확률·주가수익률로 변환하지 않는다.

- B/C/D는 **같은 전체 독립 입력 hash**를 사용하고 포함 team만 바꾼다. 최초 판단 생성 때 다른 팀 결과를 제공하지 않는다.
- 양쪽 LONG이어도 같은 사실/상관 근거를 중복 가산하지 않는다. 합의만으로 비중을 늘리지 않는다.
- 적격 의견이 같은 기간에 충돌하면 신규 배분을 보류하고 이유와 signal hash 쌍을 남긴다. 다른 기간은 별도 가설로 보존한다. 미검증 퀀트 의견이 적격 기업 판단을 자동 거부하지 않는다.
- 미래 관측·다른 통화·출처 hash 불량은 fail-closed. 신선도, 출처, 기대 순수익, 위험/유동성의 부족은 해당 판단 기권으로 기록한다.
- trace는 입력 포함/제외, 기권 원인, 충돌, 위험 cap이 실제 결정을 바꾼 이유를 보존한다. 기존 보유의 명시적 청산 규칙이 없으면 자료 부족을 이유로 자동 전량 매도하지 않고 HOLD_ONLY한다.

회사63세션/퀀트1세션은 이 연구 adapter의 명시적 연구 메타데이터이며 검증된 신규 보유 정책이 아니다. 회사 분기실적 목표와 주식 보유 기간을 같다고 가정하지 않는다. QuantaAlpha/RD-Agent 등도 동일 quant 계약의 engine/version/source hash로 연결할 수 있으나 이번에 대규모 알파 재탐색은 하지 않았다.

## 4. 실제 종목·비중·원본 대비 차이

실제 Toss GET으로 두 종목 각139개 완료 일봉과 quote를 수집했다. 현재 캘린더 응답에 완료 세션이 없어 최초 시도는 fail-closed했다. 이후 **기존 `ops_session`에 이미 공식 관측된 Nov12 완료 세션을 읽기 전용 재사용**해 과거 거래일을 추정하지 않고 진행했다. [원문·관측·해시](../../runtime/task8/market/inputs.json), [초기 오류](../../runtime/task8/evidence/market_collection_initial_failure.log).

63세션 가격 변화는 NVDA -26.19%, CRWV -46.23%였다. 이는 기대 수익률이 아니며 검증된 독립 예측도 아니다. 새로운 퀀트 판단은 연구 후보/기권으로 남겼다. 새 가격 자료의 기업행사·시점별 유니버스 독립 인증이 없어 canonical/운영 입력 승격을 하지 않았다.

| 구성 | 실제 결정 | 해석 |
|---|---|---|
| A 현금 기준/기존 동결 전략 | 새 Forward 현금 기준 등록, 기존 역사 성과는 Task6/7 원본 유지 | 회사 역사 신호와 날짜를 맞춘 비교 수익률 없음 |
| B 퀀트만 | NVDA0%, CRWV0%, USD현금100% | 예측력/양의 비용 후 edge 미검증, 위험·비용 수치 부족 |
| C 회사만 | NVDA0%, CRWV0%, USD현금100% | 성장 논거는 있으나 완전한 equity value/시장 기대/기대 수익 부족 |
| D 통합 | NVDA0%, CRWV0%, USD현금100% | 한쪽 부족한 근거를 다른 쪽 정성으로 보충하지 않음 |
| E Vibe 원본+최소 QH | 원본 HRP 약NVDA85.97%/CRWV14.03%, eligibility gate 후 현금100% | 아래 원본 범위와 위험 차이 확인. 수익 개선 증거 아님 |
| 한국 독립 계좌 | KRW현금100% | 적격 기업/퀀트 packet 미확보. 미국과 통화/계좌 통합 안 함 |

원본 Vibe `quantlib.portfolio.hierarchical_risk_parity`, inverse variance, `quantlib.risk.max_drawdown_analysis` 및 `portfolio.rebalance.propose_rebalance`를 **실제로 실행**했다. [결과](../../runtime/task8/native_portfolio.json). 138개 수익률 관측으로 HRP/IV가 동일 비중을 반환했으며 covariance 배분 자체에 alpha 검증·세금·비용·회전율 제약은 없다. 원본 현금 계좌 rebalance는 현금 유지를 반환하고, 보유하지 않은 NVDA 신규 target은 거부했다. 원본이 신규 종목 주문 전체를 제공한다고 과장하지 않는다.

같은 HRP target을 기존 QH `portfolio.aggregate`에 넣으면 총노출·종목·업종 한도 초과를 검출한다. QH가 추가한 실질적 차이는 **출처/edge 적격성과 위험 cap에 따른 실행 보류의 추적성**이다. 현금 유지에서 원본 대비 추가 수익·오류 예방의 금전 효과까지 측정한 것은 아니다. ai-hedge-fund/FinRL-X 신규 설치는 필요하지 않았다.

## 5. 위험·비용·실행·Shadow 원장

결과 전에 총노출80%, 종목20%, 업종35%, 고상관 cluster30%, 높은 상관 기준0.8, 양방향 변경량40%, 연구 기본종목비중10%를 고정했다. 결정론적 비중 제한과 미투자 현금을 지원하며 자료가 부족한 상관/위험은 보류한다. 이 정책은 Shadow 연구 계약이며 검증된 최적 배분·전략 승격이 아니다. 하방 위험은 적격성 입력으로 요구하지만 고급 CVaR 최적화나 상관의 인과 추정은 구현하지 않았다.

실제 quote에는 symbol/currency/lastPrice/timestamp만 있었다. **bid/ask가 없어 실제 spread는 미검증**이다. 기존5bp half-spread 등 비용을 관측값으로 바꾸지 않았고, Task7 비용·회전율 부진을 감안해 비용 후 edge가 없는 신호는 기권했다.

[shadow_portfolio.py](../../src/quant_harness/investment/shadow_portfolio.py)는 새 등록 계좌만 허용하고 portfolio/policy hash, 가격 출처·완료 세션·시점, 통화를 검사한다. 정책·코드가 달라진 미완료 판단은 HOLD_ONLY/재봉인 요구로 차단하며, 이미 커밋된 NAV는 기존 Paper 멱등 복구를 재사용한다. 기존 `stockpaper.py`/`equities.py`는 변경하지 않았다. 실행 fingerprint도 작업 전 마지막 운영 판단과 일치했다.

실제 새 DB:

- `quant_task3_task8_research`: 연구·Task7 예측 참조·결과·Task9 요청.
- `quant_task3_task8_shadow_us` / `quant_task3_task8_shadow_kr`: 각각 USD100,000 / KRW10,000,000, 포지션0·체결0·NO_TRADE NAV.
- 기존 운영 DB 및 다른 서버 코인 DB를 수정하지 않았다. 테스트/복원 DB도 별도다.

[실제 Shadow 실행](../../runtime/task8/evidence/shadow_run.log), [일일 현금 관측](../../runtime/task8/evidence/shadow_observation.log), [새 프로세스 복원](../../runtime/task8/restart_probe.json). 현금 관측은 시장별 현지 날짜와 최초 관측을 기록하되 공식 거래 세션이라고 표시하지 않는다. 비현금 보유가 생겼는데 새 적격 mark가 없으면 PENDING_FRESH_MARKS다. **현재 1회 현금 관측을 장기 Forward 성과나 Sharpe/MDD로 계산하지 않았다.**

별도 합성 fixture에서는 비중10%가 기존 SQL Paper의 실제 단일 체결·현금/NAV·대사로 연결되고 재실행 추가 체결0을 확인했다. 미래/정책 변경/통화·계약 변조도 시험했다. 이 fixture는 실제 시장 체결이나 투자 효능으로 집계하지 않는다.

## 6. Task7 실적 관측·복기와 정상 운영 연결

[company_outcomes.py](../../src/quant_harness/investment/company_outcomes.py), [forecast scorer](../../src/quant_harness/investment/company_forecast.py), [기존 단일 CLI hook](../../scripts/run_autonomous_operations.py), [실제 timer 증거](../../runtime/task8/evidence/scheduled_hook.log).

원본 Task7 forecast 8건의 봉인 시각·가정·analysis/input hash를 연구 DB에 그대로 참조 저장했다. 회사 가이던스와 같은 base/그 밖의 조건부 가정을 구분하고 독립적 예측 우위로 보지 않는다. 다음 경로를 구현했다:

`공식 IR 목록 → 해당 분기 링크 → 발행/최초 관측 시각·기간·USD million 표 → 불변 본문/hash → 최초 예측 오차/구간 → 후속 복기·Task9 요청`

24시간 전 I/O 예약을 기록해 오류·중단도 예산을 소비한다. 동일 내용은 최초 관측을 유지하고 새 본문 hash는 수정 이력으로 저장한다. 허용된 공식 host 밖 redirect는 차단한다. 정확한 timezone 포함 발표시각, 목표 분기/기간/단위 표가 없으면 채점하지 않는다. 날짜 경과/가이던스/LLM 추정치를 실현값으로 쓰지 않는다. 회사 forecast별 오류를 분리하며 공개가 봉인 이전인 자료를 독립 Forward label로 인정하지 않는다.

실제 결과는 CRWV Q4 링크 미발견으로 `PENDING`, NVDA 최초 목록404 및 제한된 진단의 redirect 허용목록 차단으로 `PENDING_EVIDENCE`다. [실제 관측](../../runtime/task8/latest_observation.json), [진단 로그](../../runtime/task8/evidence/nvda_index_final_diagnostic.log). URL 최소 수정은 남겼으나 예산을 초기화해 재시도하지 않았다. **NVDA 목록 host/정확 발표시각 파싱을 검증한 운영 수집 성공은 아직 아니다.** DART 한국 결과 adapter도 이번 두 미국 기업에 대해 실행한 범위 밖이다.

기존 systemd timer에서 새 Shadow 관측과 회사 관측 hook의 실제 호출을 확인했다. 반복 호출은 `ALREADY_OBSERVED` / `NOT_DUE, requests0`였다. 별도 timer/cron/gateway는 추가하지 않았다. 회사 관측의 오류는 별도 DB/try 경계로 기존 Paper 판단에 영향을 주지 않는다. 공개 결과가 없는 현재 정확도는 계속 `PENDING`이다.

합성 공식 Q4 문서로는 실제 PostgreSQL에서 매출4,900 대 예측4,800의 절대오차100, 다음 정상 예약의 수정치4,800에 별도 label/score 이력, 후속 큐를 검증했다. 이것을 실제 회사 실적으로 보고하지 않는다. 지금 지원하는 자동 label은 분기 매출이며 마진/EPS와 자유문장 반증 전체는 자동 채점하지 않는다.

## 7. Task9 사건·Factory 상태

실제 사건 3종을 `TASK9_RESEARCH_REQUEST_V1`로 저장했다: 가치평가 입력 부족, 퀀트 edge/비용 문제, 서로 다른 연구 기간의 검토 필요. 각 요청은 원본 evidence ID, 필요한 연구 종류, 이유, 예산 미배정, 자동 전략 변경 금지를 갖는다. 실제 Queue claim/finish로 `PENDING_EVIDENCE`를 확인했다.

새 공식 실현값이 생기면 등록 매출 구간 안/밖 사건, forecast/label/score ID, 원인 미확정, 후속 연구 요청을 저장한다. 작은 오차나 이익/손실만으로 연구 변경을 강제하지 않는다. 연구 엔진 선택·LLM 실행·예산 배분은 Task9에서 확장한다.

[Factory 점검](../../runtime/task8/factory_check.json): UTCNov13 공식 제안3/3·실험 예약1/1 소진, 기존 Task7 `BLOCKED_REGISTRATION` 유지. Task5/6 대기 순서를 보존했으며 예산 우회·새 namespace 실험·자동 승격을 하지 않았다. 정상 UTC 갱신 이후 등록/실험이 실행된 증거는 이번에 없다.

## 8. 테스트·재현·보존

[실험 runner](../../experiments/task8/), [신규 테스트](../../tests/test_portfolio_integration.py), [실행 로그](../../runtime/task8/evidence/).

| 검사 | 실제 결과 |
|---|---|
| compileall src/scripts/tests 및 Task8 | PASS |
| 기존 equity/operations/verification + 신규 통합 | 51 PASS, skipped0, exit0 |
| AGENTS 최소4파일 + 운영5파일 | 53 PASS, skipped0, exit0 |
| 최종 신규 경계/실제 PG 통합 재검사 | 19 PASS, 위51과 중복 집계 안 함 |
| V104 Forward 명령 | `NO_ENABLED_CANDIDATES`, rows_appended0, Live false |
| 실제 두 Shadow 계좌 대사/재개·timer hook | PASS |
| 실제 기업 실현값·비현금 Forward·장기 성과 | PENDING / NOT_RUN |
| 실제 서버 재부팅 | NOT_PERFORMED |

V104 명령의 문구는 AGENTS에 적힌 `NO_NEW_SESSION_AFTER_V104_FREEZE`와 다르다. 실행 코드 `forward_runtime.py:rows.empty`가 후보0개에서 먼저 `NO_ENABLED_CANDIDATES`를 반환한다. 문구를 맞추기 위해 후보를 활성화하거나 코드를 바꾸지 않았다. append0·Live차단은 유지됐다.

모델은 기존 구독 인증의 실제 Terra **1회, 입력48,277+출력2,455=50,732tokens**, 실패0. [사용량](../../runtime/task8/model_usage.json). CLI의 hard token cap은 없어 사후 실측이며 별도 유료 API/데이터 구매는 없었다. 실제 화폐 비용은 `null`이다. worker는 network-none, 더미 relay key만 받고 호스트 인증·브로커·DB 권한은 받지 않았다.

최소 재현(외부 호출 전에 기존 snapshot/모델 로그 우선):

```bash
.venv/bin/python scripts/setup_task8_databases.py
PYTHONPATH=src .venv/bin/python experiments/task8/run_shadow.py
PYTHONPATH=src .venv/bin/python experiments/task8/complete_comparison.py
PYTHONPATH=src .venv/bin/python experiments/task8/probe_state.py
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q tests/test_portfolio_integration.py
```

재실행의 새 판단은 새 관측으로 저장할 수 있으나 최초 Shadow 연결은 복구하며 같은 결정을 새 체결로 만들지 않는다. 안전 회귀·데이터/원본 실행 명령은 진행 기록/로그에 있다. 최초 캘린더 실패, native drawdown 호출 인자 오류와 수정, 신규 테스트 DB role 주입 오류의 실패 로그도 보존했다. 시장4회와 큐 관측2회, 목록 진단2회의 논리 HTTP 호출이 있었고, 최초 urllib 자동 redirect의 내부 wire 횟수는 별도로 계량하지 못했다. 현재 worker는 허용하지 않은 redirect를 따라가기 전에 차단한다.

최종 점검에서 Task8 이전부터 반복된 기존 운영 관측기의 datetime JSON 직렬화 `TypeError`도 확인했다. 실DB 읽기 전용+임시 보고 디렉터리에서 재현 후, `operations_verification.py`의 보고 출력 한 곳에 `default=str`만 추가한 **별도 최소 버그 패치**를 적용했다([전후 diff](../../runtime/task8/evidence/verification_format_fix.diff), [재현 실패](../../runtime/task8/evidence/verification_before_fix.log), [수정 후](../../runtime/task8/evidence/verification_after_fix.log)). 운영 DB 쓰기·API·모델·주문 없이 실제 자동 관측 보고 갱신도 성공했다([실행](../../runtime/task8/evidence/verification_live_refresh.log)). 관련 최종21개(신규19+기존보고2) 재검사 통과이며 위104개에 중복 합산하지 않았다.

새 연구/Shadow DB를 일회성 dump하고 새 격리 DB로 복원했다([최종26기록 복원](../../runtime/task8/backup_final/manifest.json)). 기존 자동 백업의 DB 목록에 이 새 DB들이 자동 포함된다고 주장하지 않는다. 정기 백업 편입은 후속 운영 과제다. 모델 trace·원문·수정 이력·소스/정책 hash는 보존하고, 새 시험 복사본·임시 relay/socket·bytecode만 정리한다.

## 9. 남은 한계와 다음 작업

- **투자 판단 통합의 기술 경로는 작동하지만 투자 증분 가치는 미입증**이다. 실제 비교 결과는 모두 현금이고 원본보다 수익이 좋아졌다는 결론이 없다. 정보가 부족한 시점에 주문을 하지 않은 것은 의도된 결과다.
- NVDA 공식 목록/redirect host 및 정확 발표시각·표 파싱의 실제 검증을 정상 수집 예산에서 마무리해야 한다. CRWV/NVDA 목표 결과가 관측되기 전까지 예측 오차를 만들지 않는다. 한국 기업 예측/공식 결과는 별도 적격 자료가 필요하다.
- 회사의 검증된 EV→equity/희석·시장 기대와 퀀트의 독립 예측·비용/유동성 근거를 보완해야 비현금 Shadow 후보를 만들 수 있다. 현재 기본 Shadow 정책이나 기존 운영 전략을 자동 승격하지 않는다.
- Task9는 사건별 적절한 연구 엔진·예산·중복/다음 관측 관리, Factory 정상 예약, 새 DB 정기 백업, 근거 있는 후보의 Forward 관측을 연결한다. 연구 수를 늘리는 것보다 실제 부족한 근거를 해결하는 작업을 우선한다.

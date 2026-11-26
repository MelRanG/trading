# Task 7 — 퀀트 성과 진단·기업 투자 기회 연구

작성: 2026-11-14 KST / 실제 실행 기준: 2026-11-13 UTC. 구조: **HYBRID_MINIMAL 유지**.

## 1. 핵심 결과와 판정

**비용·평가 계약·표본 제약은 확인했다. 연구 엔진 자체가 열등하다는 결론이나 신규 투자 우위는 입증하지 못했다.** 기업 탐색과 실제 원본 분석, 구조화 예측 저장까지 실행했으며 미래 실적 채점과 Factory 정식 실험은 대기한다.

| 작업 | 판정 | 실제 근거와 한계 |
|---|---|---|
| 7.0 기존 성과 원인 진단 | PASS, 범위 제한 | 추가 LLM 없이 기존 US38·2025 신호 9개, 사전등록 민감도 72회. 한국 재평가·시점별 업종 분석·더 큰 탐색 예산의 인과 비교는 미실행 |
| 7.1 자율 기업 탐색 | PASS, 제한된 탐색 | 원본 Vibe screener/RSS 및 LLM으로 6후보·여러 산업 발굴, NVDA/CRWV 심층 선정. CRWV는 기존 연구 유니버스 밖. 심층 2건은 AI 관련 산업에 집중 |
| 7.2 실적·가치 연구 | PARTIAL | 실제 IR로 Bull/Base/Bear 매출 예측·반증 조건 생성. 조건부 reverse DCF 실행. 독립 컨센서스·완전한 DCF·비교기업 가치평가 및 예측 정확도 미확인 |
| 7.3 전문 분석 비교 | PASS, 구성요소 시험 | 원본 TradingAgents bull/bear, FinRobot ExpertInvestor, 투자 스킬 부분 묶음 실행. 원본 전체 Graph/모든 도구의 성능 평가 아님. Vibe CLI grounding 실패와 원본 earnings 구성요소 baseline을 구분 |
| 7.4 공식 증거·복기 연결 | PARTIAL | 기존 Store/Queue로 새 격리 PostgreSQL에 8예측+8과정복기+1교정 기록, 후속 관측 예약·재개 검증. Factory 등록은 정상 일일 예산에 의해 BLOCKED, 정식 실험 미실행 |

**안전 테스트 24개, 예측 경계 테스트 11개 통과.** 기존 추적 파일의 Git diff hash는 작업 시작과 동일하다. 운영·Paper·Live·전략·스케줄러를 변경하지 않았고 주문은 0건이다. 임시 시험 복사본·설치 캐시 등 약 10.28GB를 정리했으며 원문·실패 로그·모델 기록·격리 환경은 보존했다.

## 2. Task 6 성과 부진: 실제 분해

입력·실행: [사전등록 계약](../../experiments/task7/contract.json), [진단 코드](../../experiments/task7/quant_diagnosis.py), [추가 귀속 분석](../../experiments/task7/refine_quant_attribution.py), [전체 결과](../../runtime/task7/quant/diagnosis.json). 원본 신호/체결/NAV hash를 결과에 보존했다. 기존 결과 파일은 수정하지 않았다.

close(t) 관측 → 다음 세션 open(t+1) 진입 → 같은 세션 close 청산인 V2 계약을 사용했다. top4/총목표80%, 정수주·현금·참여율 제한은 유지했다. 비용은 각 측 수수료1bp, half-spread5bp 및 기존 ADV 기반 충격이다. 고정 spread는 관측 브로커 호가를 검증한 값이 아니다. 비용 변화는 비용 차감 이후 다음 주문 자본도 바꾸므로 단순 달러 비용을 수익률에서 빼는 방식과 다르다.

| 기존 후보 | IC | 원래 V2 net 수익률 | 실제 평균 노출 | 연간 양방향 회전율 합계* | 비용 합계(USD) |
|---|---:|---:|---:|---:|---:|
| Quanta node0 | -0.01923 | -7.41% | 69.0% | 344.87 | 21,277 |
| Quanta node1~5 | -0.02754~-0.00280 | -16.35%~-31.01% | 77.6~79.5% | 387.97~397.47 | 20,081~23,356 |
| Vibe 생성 전략 | -0.03363 | -17.63% | 78.4% | 392.12 | 22,674 |
| RD GRU 기본 | 0.00891 | -11.48% | 79.3% | 396.29 | 22,784 |
| RD 팩터 결합 | 0.02477 | +1.23% | 79.2% | 396.14 | 24,802 |

*일별 turnover 수치를 합한 배수이며, 퍼센트가 아니다. 원본 체결 기준 비용·손익에서 NAV를 독립 재구성해 일치 여부를 검사했다. 분기별·종목별 손익도 전체 결과에 있다. 시점별 업종 분류가 없어 업종 효과는 추정하지 않았다.

사전등록된 **동일 신호·top4 비용 민감도**(새 전략 선정 자료 아님):

| 후보 | 비용0배 | 0.5배 | 1배 | 2배 | top8·1배 |
|---|---:|---:|---:|---:|---:|
| Quanta node0 | +15.28% | +3.27% | -7.41% | -25.66% | -0.63% |
| Vibe | +5.74% | -6.67% | -17.63% | -35.71% | -13.38% |
| RD 기본 | +13.80% | +0.31% | -11.48% | -31.04% | -13.61% |
| RD 팩터 결합 | +30.21% | +14.80% | +1.23% | -20.96% | -7.23% |

확인된 사실과 유보할 해석:

- `EXECUTION_COST`: 이 계약에서 확인. 비용 약 79%가 고정 spread이며, 매일 진입·당일 청산 구조의 높은 회전율이 net 성과를 크게 낮췄다. 그렇다고 spread를 낮춰 운영 전략을 채택하지 않았다. 실제 호가·체결 데이터로 비용을 검증할 필요가 있다.
- `EVALUATION_MISMATCH`: V1의 예측 목표/overnight 보유 불일치는 확인, V2에서 정렬됐다. 원래 가설이 요구한 기간과 공통 1일 intraday 매핑이 같다는 보장은 없다. 이번 top4/8 진단만으로 최적 보유기간을 정하지 않았다. 기간 변경 실험은 미실행이다.
- `DATA_LIMITATION`: US38/KR20 현재 생존 종목, 시점별 상장·상폐 유니버스/업종/기업행사 인증 부족은 확인. 이번 재분해는 US38·2025에 한정한다. 종목 선택과 시장 노출을 분리한 일별 선택 잔차는 node0 +0.36bp, Vibe -2.77bp, RD 기본 +0.84bp, 결합 +6.51bp로, 절대 양의 수익이 독립 알파를 뜻하지 않는다.
- `SEARCH_BUDGET_LIMITATION`: Quanta 6 bounded trajectories, RD 5epochs 소형 GRU, Vibe 소수 가설이라는 제한은 확인했다. 충분한 탐색을 준 matched control이 없으므로 핵심 알고리즘이 실험 규모 때문에 얼마나 저평가됐는지는 `UNDETERMINED`다. Quanta 원본 controller의 의미 있는 단계 실행과 대규모 원본 연구의 효능 검증은 별개다.
- `FEEDBACK_ERROR`: 절대수익 평균을 excess alias로 전달한 Task6 단계가 있었고 V2.1 export는 교정됐다. 이미 영향받은 후속 가설을 소급해서 교정된 연구로 표현하지 않는다. 같은 연구를 올바른 feedback으로 재실행한 인과 비교는 하지 않았다. 새 기업 연구에서는 절대수익을 초과수익으로 전달하지 않는다.
- `ENGINE_LIMITATION`: 특정 후보의 약한 예측력은 확인하지만 엔진 계열 자체의 한계는 미입증이다. Quanta 6개 IC가 음수이고 Vibe IC의 월 block 95% 구간은 [-0.0643,-0.0012]였다. 같은 개발 자료의 사후 진단이므로 범용 열등성 검정이 아니다.

RD 9,462 예측에서 MSE는 기본0.00035823, 팩터결합0.00042825로 **영(0) 예측 MSE0.00030728보다 모두 나빴다.** 방향 정확도는 50.95%/51.44%. 결합의 IC 증분 +0.01586은 월 block 95% 구간 [-0.03419,+0.06235]로 0을 포함한다. 순위 선택 효과 개선과 수치 예측 오차 개선을 혼동하지 않는다.

향후 우선순위는 (1) 모든 엔진의 feedback 지표 의미/예측 기간 계약 고정, (2) 검증된 비용·시점별 유니버스, (3) 사전 예산을 고정한 더 충분한 원본 탐색, (4) 독립 Forward다. RD는 단순 zero/linear 기준선과 오차·순위 목적을 함께 검증하고, Quanta는 native 평가와 공통 전략 매핑을 분리하고, Vibe는 아래 데이터 grounding을 먼저 안정화한다. 2026의 이미 본 결과는 새 Holdout으로 쓰지 않았다.

## 3. 실제 자율 탐색과 원문 수집

[탐색 결과](../../runtime/task7/leads/discovery_final.json), [질의·식별 보강 기록](../../runtime/task7/leads/), [원본 screener 결과](../../runtime/task7/native/native_screen.json).

사용자가 기업을 지정하지 않은 상태에서 공개 RSS의 산업/수요/생산능력 변화와 Vibe 원본 `_screen_market('us',sort_by='amount',top_n=30)`를 실행했다. 초기 영어 AND 질의와 KR locale의 부족을 확인하고, 명시 OR 및 US locale를 심층 선정 전에 추가했다. 모델에게 이 변경과 동일 관측 풀을 제공했다. 모든 상장 종목의 시세를 수집하지 않았다.

최종 후보는 **NVDA(반도체), CRWV(AI 클라우드), NAVER(인터넷), KT(통신), Hanon Systems(자동차 부품), DL E&C(건설)**. 심층은 원본 Vibe CLI가 NVDA/CRWV를 선정했다. CRWV는 기존 US38 연구군 밖이며 한국의 Hanon/DL도 기존 좁은 관심군 밖이다. NVDA를 다시 고른 것과 미국 심층 2건의 AI 집중은 선택 편향으로 남는다. 한국 DART 법인 식별만으로 거래소/보통주 적격성을 확정할 수 없어 한국 심층은 기권했다. 한국 미지원 때문의 엔진 감점은 하지 않았다.

[동결 회사 packet](../../runtime/task7/company/packet.json)의 SHA256은 `c1b8ee944a03c82f9789c0dfc4336237953ca3c93d45d754199dd74c3a00ff56`. 실제 공식 IR HTML/본문과 관측 시각/hash, Toss 완료 일봉을 보존했다. SEC 직접 GET은 HTTP403으로 실패했고 우회하지 않았다. IR은 성공했다. 기업 발표는 공식 사실, RSS 제목은 탐색 단서, LLM 전망은 가정으로 구분한다.

- [NVIDIA FY2027 Q2 공식 IR](https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Second-Quarter-Fiscal-2027/): 원문 발표2026-08-26, 분기 종료2026-07-26.
- [CoreWeave Q3 2026 공식 IR](https://investors.coreweave.com/news/news-details/2026/CoreWeave-Reports-Strong-Third-Quarter-2026-Results/default.aspx): 원문 발표2026-11-10, 분기 종료2026-09-30.

가격은 수집 중인 세션을 제외한 **2026-11-12 수정 일봉 종가 NVDA166.19/CRWV56.60 USD**이며 당시 실시간 호가가 아니다. 수정주가 기업행사의 독립 인증 및 V87 canonical 승격을 주장하지 않는다. 이번 연구 packet에만 사용했고 거래 입력을 교체하지 않았다.

## 4. 미래 실적·시장 기대·가치 연구

[전체 분석·예측](../../runtime/task7/comparison/), [조건부 가치 계산](../../runtime/task7/native/native_valuation.json), [가치 계산 사전 계약](../../experiments/task7/valuation_contract.json).

| 회사 | 확인한 사실(USD million) | 투자 가설과 반대 조건 |
|---|---|---|
| NVDA | 분기 매출96,221, Data Center89,000, 영업이익63,734, CFO24,077, 회사제시 FCF21,341. 지분증권 이익7,771과 매출채권63,059 | AI 시스템 출하가 성장 동력. 경쟁·공급·수출 규제가 반대 근거. GAAP EPS2.46이 non-GAAP2.22보다 높은 것은 투자이익 영향과 함께 해석. 회사 Q3 매출 가이던스108,000±2%는 컨센서스가 아님 |
| CRWV | 분기 매출3,661, 영업이익207, 이자비용846, 순손실709, adjusted EBITDA2,256, CFO1,975, 설비구매9,441 | 가동 전력·인도 가능 용량이 계약을 매출로 전환할 수 있음. backlog132,500은 인도·가용 조건부. CFO-capex=-7,466이므로 EBITDA를 잉여현금으로 보면 안 됨. 부채·투자·고객집중·희석 위험 |

공통 기준선의 미래 분기 매출 Bull/Base/Bear는 NVDA **114,000/108,000/99,000**, CRWV **5,100/4,800/4,100**, 각각 확률25%/50%/25%다. 아래 전문 arm의 다른 예측도 모두 원본 그대로 봉인했다. 확률은 주관적이며 calibration이 입증되지 않았다. NVDA의 base는 회사 가이던스와 일치하므로 독립 컨센서스 대비 우위가 아니다. CRWV 연간 가이던스에서 9개월 실적을 빼면 Q4 4,686~4,986이지만 이는 계산값이지 회사의 별도 Q4 가이던스가 아니다.

NVDA 목표FY2027Q3 종료2026-10-25는 지났어도 결과 발표를 관측하지 않아 `PENDING`이다. CRWV 목표Q42026 종료2026-12-31도 `PENDING`. 다음 검토일11월19~20일/2027년2월1~2일은 분석별 **연구 일정 가정이며 확인된 실적 발표일이 아니다.** 원본 수치·기간을 바꾸지 않았다. 반증은 NVDA 매출99,000 미만/마진 약화, CRWV 매출하단 미달·용량 지연·현금소모 지속 등 분석별 조건으로 기록한다. 실제 label이 있어야 오차와 구간 포함 여부를 채점한다.

Vibe 원본 `run_dcf()`는 누락 FCFF 경로/자본비용/terminal 입력에 `NOT_RUNNABLE`을 반환했다. 없는 가정을 채워 목표가를 만들지 않았다. 별도 고정 가정에서 원본 equity-research-skill `reverse_dcf()`를 실행했다. 현금만 반영한 bridge, 가중평균 희석주식수 대용치, 최근 분기×4, 5년간 일정 interim FCF, terminal성장3%, 회사별 사전 WACC/정상 FCF마진 범위에서는 필요한 매출 CAGR이 NVDA14.64~39.21%, CRWV42.02~99.98%다. **이는 강한 가정에 따른 모형상 요구치이며 적정가·시장 컨센서스·저평가 증거가 아니다.** 유가증권/리스 등 누락과 CRWV 음의 interim FCF가 계산에 크게 작용한다. 완전한 DCF, comps, 독립 sell-side consensus는 미확보여서 기권했다.

## 5. 전문 분석의 실제 증분과 원본 실행 범위

[고정 원본 버전·clean 상태](../../runtime/task7/source_versions.json), [원본 모델 호출](../../runtime/task7/model_calls/), [제한 gold 감사](../../runtime/task7/comparison/evaluation.json), [전체 문맥 증분 교정](../../runtime/task7/comparison/information_audit_refinement.json).

| 방식 | 실제 호출 경로 | 두 기업 facts 배열 감사 | 전체 문맥 대비 추가 정량 항목 |
|---|---|---|---|
| Vibe baseline | 원본 ChatLLM + bundled earnings-forecast 지시, 2기업 batch | 각9개 확인 | 기준선 |
| TradingAgents | 9fa1196 원본 bull/bear factory를 독립 state로 실행 + 자체 JSON 합성 | 각10개 확인 | NVDA 없음; CRWV 전년 동기 매출·이자비용·가동 전력 하한 |
| FinRobot | 63e1884 원본 FinRobot('Expert_Investor')/AutoGen generate_reply | NVDA9확인+1미감사, CRWV10확인 | NVDA 없음; CRWV adjusted 영업이익·이자비용 |
| 투자 스킬 묶음 | 고정 investor-harness 촉매/반론, financial-services earnings-preview, equity-research-skill 기대 역산 지시 부분 적용 | 각10개 확인 | NVDA 당기 gross margin; CRWV 이자비용 |

NVDA CFO는 baseline의 **counterevidence에 이미 있었다.** facts 배열의 차이만으로 신규 발견으로 세지 않도록 append-only 교정했다. CRWV 이자 정량화도 기준선이 이미 지적한 차입 위험을 구체화한 것이다. 제공된 동일 문서에서 추출한 추가 사실이며, 시장에 알려지지 않은 독립 투자 촉매를 발견했다는 의미는 아니다.

명시 gold의 수치/단위/출처 오류는 0건. FinRobot의 `closing price` 표기는 제한 matcher 범위 밖 1건으로 남겼다. 이는 리포트 전체의 무오류·완전 recall을 뜻하지 않는다. gold는 제한된 수동 원문표 검사이며 blinded 복수 평가자가 아니다. 논거의 투자 중요도와 미래 효과는 미입증이다.

**원본 Vibe CLI의 문제를 별도 보존:** inline packet 단계는 facts/수치 전망을 기권했다. 실제 `read_file`을 먼저 수행한 보강에서도 최종 응답이 rejected draft 뒤 deterministic fallback으로 내려갔다. CLI exit0을 유효 수치 분석 성공으로 세지 않았다. 원본 earnings provider 구성요소를 별도로 실제 실행한 결과를 위 기준선으로 사용했고, CLI 실패를 가리는 대체 성공으로 보고하지 않는다. 회사 investment committee 전체 실행은 미실행이다.

TradingAgents는 전체 TradingGraph/ResearchManager 실행이 아니며, FinRobot은 code_execution=False·proxy=None·외부 toolkit 미등록 상태다. 모델 worker는 network=none, 가짜 relay key만 받고 호스트 구독 인증·브로커 권한·운영 원장을 받지 않았다. FinRobot 전체 구형 requirements 재현은 하지 않았고 native workflow import에 필요한 의존성을 별도 환경에 설치했다. 최초 대형 GPU 의존성 설치를 중단한 기록과 CPU torch2.8 제약으로 성공한 로그를 보존했다.

세 투자 스킬의 원본 commit/URL/hash는 [manifest](../../runtime/task7/skills/manifest.json)에 있다. 필요한 부분만 사용했으므로 각 스킬 개별 효과나 전체 원본 워크플로 검증을 주장하지 않는다. InvestSkill 전체 도입이나 새 상시 전문 에이전트 서비스는 추가하지 않았다.

## 6. 비용·예산·재현성

동일 packet/관측 시점/실제 `gpt-6.1-terra`, arm별 최대6calls·260,000tokens를 사전 지정했다. 호출 구조와 실제 사용량까지 같지는 않다. Vibe 2기업 batch, TradingAgents 기업별3calls, FinRobot/skills 기업별1call 차이로 방법만의 순수 인과 비교는 불가능하다. [실제 사용량](../../runtime/task7/model_usage.json):

| scope | 실제 호출 | 입력+출력 tokens | 실패 |
|---|---:|---:|---:|
| 탐색 | 5 | 246,569 | 1(차단된 tool 제안 포함 usage) |
| Vibe(초기·grounding 보강·component 모두) | 5 | 240,395 | relay 실패0, CLI 수치 기권/fallback 별도 |
| TradingAgents | 6 | 231,785 | 0 |
| FinRobot | 2 | 68,462 | 0 |
| 스킬 묶음 | 2 | 107,637 | 0 |
| 총계 | 20 | 894,848 | 1 |

실패·재시도의 사용량도 포함했다. 캐시 입력은 해당 입력 token의 부분집합이며 이중 합산하지 않았다. 구독 인증을 사용했고 별도 유료 API/데이터 결제를 하지 않았다. 화폐 비용은 `null`이다. 원본 라이브러리의 alias 기반 추정액/0달러 표시는 실제 비용으로 쓰지 않았다. FinRobot이 이번 구성에서는 적게 썼으나 미래 예측 품질이 같은지는 아직 모른다. 입력 전체 반복과 원본 도구 catalog overhead가 커서 이후에는 필요한 근거 요약+hash 참조로 줄일 가치가 있다.

연구 데이터는 새로 수집한 실제 관측 snapshot이다. 과거에 알고 있던 정보로 소급하지 않았다. 역사적 회사 사건 및 LLM 사전학습 지식 가능성은 남고, 현재 봉인 이후 실제 발표를 관측해야 Forward 예측 평가가 된다. 2관련 기업만으로 유효 연구 1건당 비용·오탐률의 일반적 우열을 정하지 않는다.

## 7. 증거·복기·후속 연구 연결

[연결 코드](../../experiments/task7/connect_review.py), [DB 결과](../../runtime/task7/review/result.json), [후속 교정 연결](../../runtime/task7/review/refinement_connection.json), [새 프로세스 복원](../../runtime/task7/review/restart_probe.json).

- 기존 PG 컨테이너에 **새 DB `quant_task3_task7_research`**, 새 연구전용 role을 구성했다. 기존 운영 DB/거래 원장 권한·테이블을 바꾸지 않았다.
- 기존 `investment.Store`/`review_jobs.Queue`를 재사용해 8개 예측 및 당시 원문에 근거한 과정 평가를 불변 저장했다. 모델/분석 hash, source packet hash, 가정·확률·반증 조건·목표 기간·최초 봉인 시각을 보존했다. 당시 과정 평가에는 사후 실현 수익을 제공하지 않았다.
- 과정 복기 8건은 `PENDING_LABELS`, 실제 발표 관측 작업 8건은 다음 확인일의 `READY` 예약 상태다. 날짜만 지났다고 mature 처리하지 않는다. 공식 출처·검증 표시·본문 hash·공개/관측 시간·종목/단위/기간이 맞아야 scorer가 실현값을 받는다. 합성 label은 테스트에만 있다.
- facts-array 증분 오류를 후속 증거로 `Queue.observe`에 전달하고 원본 복기를 유지한 교정 1건을 `NO_CHANGE`로 처리했다. 전체 문맥 비교를 다음 연구 요청으로 남겼다. 수익/손실이 없는데 예측 실패나 정상 손실로 단정하지 않았다. 현재 원인 분류는 UNDETERMINED다.
- 새 프로세스에서 **불변 기록17건 hash**, `PENDING_LABELS8/READY8/NO_CHANGE1` 및 지금 처리할 중복 작업0을 확인했다. 실제 서버 재부팅은 하지 않았다.
- 원본 Vibe HypothesisRegistry/GoalStore/ResearchArtifactStore에 2개 회사 가설/goal/artifact를 저장했다. 동일 저장의 revision 멱등성과 새 컨테이너 프로세스 복원을 확인했다. 숫자 전망을 backtest로 위장하지 않도록 backtest 전용 Autopilot scaffold는 재사용하지 않았다.

공식 Factory 제안은 기존 namespace와 정상 예산으로 등록 시도했으나 **`Factory daily proposal budget exhausted` → BLOCKED_REGISTRATION**이다. [변경 불변 제안](../../runtime/task7/review/factory_proposal.json), [상태](../../runtime/task7/review/factory_status.json). 최소12 독립기업·실험1·parameter search0·승격 제한을 유지한다. 현재 2기업은 이 기준에 부족하며 기존 Task5/6 대기 작업보다 앞서 실행하지 않았다. 더 넓은 기업 입력은 이 동결 packet에 덧붙이지 않고, 별도 사전등록 follow-up과 새 input hash가 필요하다. 예산 우회·다른 디렉터리 등록·과거 결과로 신규 실험 대체는 하지 않았다.

**아직 자동 운영 연결 완료가 아니다.** 회사 실적 공개 원문의 범용 자동 수집/검증 adapter와 기존 daily worker가 이 새 회사 관측 kind를 자동 처리하는 연결은 후속 작업이다. 이번에는 공식 저장·작업 계약을 통한 실제 최소 수동 실행 경로와 재개를 검증했다. Factory 정상 등록·예약·독립 실험·12기업 비교는 미완료다.

## 8. 실행·테스트·파일 정리

주요 재현 명령(완료된 외부 API/LLM 호출은 보존 snapshot/relay cache를 우선 확인):

```bash
.venv/bin/python experiments/task7/quant_diagnosis.py
.venv/bin/python experiments/task7/refine_quant_attribution.py
.venv/bin/python experiments/task7/evaluate_company.py
.venv/bin/python experiments/task7/refine_information_audit.py
PYTHONPATH=src .venv/bin/python experiments/task7/connect_review.py
PYTHONPATH=src .venv/bin/python experiments/task7/register_refinement.py
PYTHONPATH=src .venv/bin/python experiments/task7/probe_restart.py
PYTHONPATH=src:experiments/task7 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  .venv/bin/pytest -q experiments/task7/test_company_contract.py
```

원본 실행용 `run_vibe.sh`, `run_specialist.sh`, 설치·CPU 제약 script와 native_history/probe 코드는 [experiments/task7](../../experiments/task7/)에 있다. native 실행 로그·prompt·환경 lock은 [native](../../runtime/task7/native/), 최초 실패와 시험 로그는 [evidence](../../runtime/task7/evidence/)에 보존했다. 모델 relay는 종료했으므로 새 모델 호출은 명시적 실행 준비가 필요하다. 이번 결과를 읽는 데 relay는 필요 없다.

| 검사 | 실제 결과 |
|---|---|
| compileall src/scripts/tests + Task7 실험 코드 | PASS |
| AGENTS 최소 V104/V104.2/V84/V89 4파일 | 24 PASS, exit0 |
| 예측 경계·합성 label 검사 | 11 PASS, exit0 |
| 실제 source-only PostgreSQL 저장·후속 교정·새 프로세스 복원 | PASS |
| 원본 Vibe 새 컨테이너 hypothesis/goal/artifact 복원 | PASS |
| TradingAgents/FinRobot native import·pip check | PASS, 설치 로그와 lock 보존 |
| Vibe CLI 수치 분석 | 기권/fallback, 유효한 full-CLI 수치 예측으로 판정하지 않음 |
| SEC 공식 직접 조회 | FAIL403, IR 자료로 제한 |
| Factory 정식 실험 | NOT_RUN, 정상 예산 차단·독립 사례 부족 |
| 미래 실적 예측 정확도/투자 초과수익 | PENDING / 미입증 |
| 전체 투자위원회·TA 전체Graph·장기 무인 운영·실제 재부팅 | NOT_RUN |

추적 파일 시작/종료 diff SHA256이 동일(`cc3f8959…e9ff2`)하며 원본 checkout3개도 clean이다. 추가 변경은 Task7 실험 코드·보고서·격리 증거/연구 DB에 한정한다. 운영 경로를 바꾸지 않아 추가 운영 전체 회귀/과거 검증 전체 재실행은 하지 않았다. [정리 내역](../../runtime/task7/cleanup.json): 시험용 `/tmp/task7-safety`, 두 격리 작업의 pip cache, 비editable 설치 후 중복 build-source와 Task7 pycache만 삭제. 10,284,208,096 bytes 정리. 원본/환경/원문/실패 로그/원장은 유지, 기존 5분 timer는 active 그대로다.

## 9. 유지할 기능과 Task 8~10 우선 과제

1. **Vibe 기본 연구 + 필요시 독립 반론**을 유지한다. 발견 사실과 전망의 구조화·출처 봉인은 유용하다. 이번 결과만으로 TradingAgents/FinRobot 전체 런타임을 상시 중복 운영할 근거는 없다. FinRobot의 소규모 구성은 비용 비교 후속 후보이며, 우승 엔진은 선정하지 않는다.
2. Vibe CLI grounding과 실제 파일 도구 접근을 먼저 고친다. 원본 earnings 구성요소 실행과 full CLI의 성공 조건을 분리하는 회귀 검사를 마련한다. 기존 기능의 중복 재구현을 피한다.
3. 회사 예측 목표별 공식 발표 수집 adapter, 발표시각/hash/수치단위 검증, 이번 PENDING 큐를 기존 단일 scheduler에 연결한다. 새 scheduler는 추가하지 않는다. 미래 결과를 받은 후 오차/확률 품질을 채점한다.
4. Factory의 정상 UTC 예산과 기존 큐 순서 아래 최소12 독립기업·산업을 확보한 사전등록 비교를 진행한다. full-report 신규성, 정보 중요도, 사실 오류, 비용, 실제 수치 오차를 분리한다. 피드백 metric alias와 중복 사실 집계를 검증 경계로 둔다.
5. 퀀트는 실제 비용·시점별 유니버스·원래 예측 기간과 전략 매핑을 먼저 정리하고 제한된 추가 탐색 예산을 사전 선언한다. 이미 본 역사 자료에서 잘 나온 파라미터를 채택하지 않는다. 실현 Forward가 없으면 후보/기권으로 유지한다.

이 보고서는 기능 실행·진단·최소 연결의 근거다. 장기적인 초과수익·예측 우위·자동 전략 승격 또는 Live 준비 완료를 뜻하지 않는다.

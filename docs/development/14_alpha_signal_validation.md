# Task 14 — 팀3 알파 예측력·증분 정보 검증

2026-11-16 KST · 기존 5후보의 읽기 전용 역사 진단 · HYBRID_MINIMAL 유지

## 핵심 판정: **RETURN_TO_TASK13**

**현재 후보를 Task15 경제성 검증에 기계적으로 넘길 근거가 부족하다.** 예측력이 존재하지 않는다고 증명한 것은 아니지만, 이번 S 자료에서 양의 primary를 통과한 후보가 없고 Quanta/RD가 단순 기존 팩터·모델에 추가한 정보도 확인되지 않았다. 다음 최소 작업은 데이터 플랫폼 확대가 아니라 **1~2개의 다른 경제 메커니즘을 제한적으로 재연구하고, 모델/feedback의 구체적 문제를 먼저 진단하는 것**이다.

- 고정된 **V_ROC20·V_LOWVAR20·Q0·Q1(H20 nominal2026), RD_SMALL(H5 adjusted2025)**만 평가했다. Q2와 미실행 제안은 제외하고 실패 원장에는 유지했다.
- 기존 hash·mask·label·핵심 metric은 대사됐다. 예외는 모델 CSV의 float 정밀도와 **KR Tree 4개 상수 예측일의 Pearson 처리**로, 새 평가에 명시했다. 원본 Task13을 수정하지 않았다.
- factor RankIC의 95% block 구간은 모두0을 포함했다. primary 10개는 **보정 전에도 p<0.05가 없고**, 미실행8슬롯을 포함한 Holm18 보정 후 모두1이었다.
- Q1은 MOM20과 순위 상관 **US0.989/KR0.962**이고 잔차 증분이 뒷받침되지 않았다. Q0는 단순 반전 통제 후 US partial rank가 **-0.103**이었다. US RD는 Ridge와 거의 같고, KR RD는 다른 예측을 하지만 오차가 더 컸다.
- 한국 V_ROC20의 평균 spread **+2.766%p**는 일별 중앙값 **-0.203%p**, 상위 기여3종목 제외 진단 **-0.117%p**와 대비된다. 큰 평균을 넓은 순위 예측력으로 해석할 수 없다.
- LLM/외부 수집/모델 학습/신규 알파 **0**. 시험 **29 PASS**, compileall PASS. 기존 Factory·Paper·Forward·Champion·Live·팀2를 변경하지 않았고 후속 Task를 시작하지 않았다.

주 근거: [고정 평가 계약](../../experiments/task14/contract.json), [대사](../../runtime/task14/audit.json), [전체 통계](../../runtime/task14/validation.json), [후보별 판정](../../runtime/task14/verdict.json). 표의 spread는 미래 H세션 수익 차이 평균이며 **계좌 누적수익·비용 후 성과가 아니다.**

## 1. 원본 계약·데이터·계산의 독립 대사

[Task11](11_research_architecture_audit.md), [Task12](12_alpha_data_readiness.md), [Task13](13_native_alpha_research.md)의 역할·노출 이력을 유지했다. Task13 manifest **435파일**, 시장별 candidate fingerprint **10개**, 원본 코드·input·checkpoint·계약 hash를 대사했다. [input_seal_check.json](../../runtime/task14/input_seal_check.json).

| 항목 | 실제 검사 / 결과 |
|---|---|
| 후보·방향·horizon | V_ROC20은 사전 -ROC ratio, V_LOWVAR20은 -std20/close. Q0/Q1 원본 score 유지. RD 고정 checkpoint/입력 유지. 방향 뒤집기·horizon 선택 없음 |
| label | close t 판단 → open t+1에서 open t+H+1까지. 같은 시장 세션에서 원가격/조정 track별로 독립 재산출, 중간 open 결측·미성숙 분리, 동일 종목/날짜 정렬 일치 |
| window/missing | Quanta `TS_MEAN(min_periods=1)`·`FILTER(false)=0`를 그대로 두고 Task13의 **전체 요구 input window 유효 mask**를 재구성해 일치 확인. 원본 raw score를 완전 window 계산이라고 오인하지 않음 |
| metric | 일별 횡단면 Pearson IC·Spearman RankIC·동일 floor(N/5) 상하위 spread를 독립 대사하고 기존 `task12.evaluation.signal_statistics`와 원본 Qlib `calc_ic`로 교차 확인 |
| lookahead | Task13의 실제 prefix/미래교란 검사와 수식 대사를 재사용. native controller·모델을 다시 실행하지 않음. fit scaler·라벨 purge·내부/외부 validation 경계는 봉인 학습 기록 유지 |
| 제외/편향 | current-survivor US38/KR20, KR의 결측·양수/finite 요건으로 유효 횡단면 변동. target 없는 종목 제외에 따른 생존/자료 편향과 미래 사후 지식 가능성은 미해결 |

팩터의 유효 signal은 US198일/7,524행, KR191일/3,449~3,621행이다. H20 기준 약9개의 비중첩 block 상한이며 독립 사례 수천 개가 아니다. RD는 US224일/8,512행, KR218일/4,360행이고 H5 비중첩 block 상한은44/43이다. **모델 2025와 팩터 2026을 하나의 엔진 순위로 합치지 않았다.**

RD fit은 US538/KR558일, target 종료≤2024-06-28, 내부 validation은2024년8월 이후, 진단 signal은2025-02-03 이후다. 숫자가 적힌 수만 행을 수만 개 독립 시장 사례로 세지 않는다. 조정주가 공급자 주장·기업행사·PIT 한계는 여전히 남는다. 모든 역사 자료는 이미 연구에 노출됐다.

### 새 평가에서 구분한 수치 처리

RD float32의 in-memory IC와 CSV float64 재계산은 약2~3e-10 차이가 났으며 RankIC는 일치했다. KR Tree는 **상수/거의 상수4일을 Pearson에서 제외**하면 IC **0.0168409**, 기존 기록은0.0165319였다. RankIC0.0311547와 MSE는 일치한다. 상수 예측의 상관은 미정의이며 0에 가까운 수치 잔차를 정보로 세지 않는다. Task14는 명시적 상수 guard를 적용한 새 평가이고 기존 결과를 덮어쓰지 않았다. [supplement.json](../../runtime/task14/supplement.json)의 원본/재계산 값·제외 수 참조. 초기 과도한 정밀도 assert 실패도 [보존 로그](../../runtime/task14/supplement_initial_strict_tolerance.log)에 남겼다.

## 2. 순수 예측력과 통계적 신뢰성

위험 gate·현금·포트폴리오·거래비용을 적용하지 않았다. H20/H5의 **circular moving-block bootstrap 5,000회, seed1401**, block=H를 primary로 사용했다. 기존 V103의 resampling 패턴을 얇은 평가 함수로 재사용하되, 기존 “bootstrap 양수 빈도”를 p값이라고 부르지 않고 **중심화한 null의 단측 양의 효과 p**와 percentile95% 구간을 계산했다. MC p에는 +1 보정을 썼다. 결측 달력 슬롯은 보존했고, 겹친 label을 IID로 처리하지 않았다. block2H는 사전 민감도이며 유리한 길이를 고르지 않았다.

현재9제안×2시장 family에서 실제10 primary는 factor RankIC8개와 RD의 zero 대비 일평균 squared loss 개선2개다. 미실행8개는 p=1 슬롯으로 포함해 **Holm18/FWER5%**를 적용했다. 증분 partial rank4개와 RDvsRidge loss2개는 **별도의 탐색적 Holm6**이며 primary 실패를 구제하지 않는다. 앞선 Task6~13의 적응적 노출 전체를 이18개로 초기화할 수 없으므로 보정 자체가 독립 확증을 만들지 않는다.

### 팩터 H20 — 평균 RankIC와 block 불확실성

| 후보/시장 | 평균 / 중앙 RankIC | 양수 일 비율 | RankIC 95% CI | 평균 spread | spread 95% CI |
|---|---:|---:|---:|---:|---:|
| V_ROC20 US | -0.0067 / -0.0190 | 46.0% | [-0.0988, +0.0881] | +0.184%p | [-3.725, +4.423]%p |
| V_LOWVAR20 US | -0.0509 / -0.0557 | 43.9% | [-0.1772, +0.0919] | -1.309%p | [-7.382, +4.909]%p |
| Q0 US | -0.0315 / -0.0367 | 48.0% | [-0.1328, +0.0670] | -1.754%p | [-5.933, +2.254]%p |
| Q1 US | -0.0055 / -0.0174 | 47.5% | [-0.0973, +0.0879] | +0.057%p | [-4.100, +4.548]%p |
| V_ROC20 KR | +0.0080 / -0.0135 | 47.6% | [-0.1170, +0.1412] | +2.766%p | [-5.202, +12.378]%p |
| V_LOWVAR20 KR | +0.0934 / +0.0767 | 63.4% | [-0.0431, +0.2395] | +1.711%p | [-6.554, +8.725]%p |
| Q0 KR | -0.0161 / -0.0271 | 46.6% | [-0.1517, +0.1149] | -1.131%p | [-7.843, +5.141]%p |
| Q1 KR | -0.0156 / -0.0333 | 44.5% | [-0.1377, +0.1202] | +1.167%p | [-6.458, +10.213]%p |

전체 Pearson IC 분포·median/quantile return·월별 값은 [validation.json](../../runtime/task14/validation.json), [factor_daily.csv](../../runtime/task14/factor_daily.csv), [stability.csv](../../runtime/task14/stability.csv)에 있다. block2H에서도 모든 RankIC 구간이0을 포함했다. 가장 작은 factor primary raw p도 KR V_LOWVAR20의 **0.1072**였고, 보정 후 전체10개 p는1이었다. 이는 **증거 부족**이며 알파가 없다는 증명은 아니다. 짧고 비정상적인 시장 경로에 대한 bootstrap도 완전한 일반화 장치가 아니다.

### 시장지수 상대 정보

같은 날짜의 지수 수익을 모든 종목에서 빼면 RankIC/IC·상하위 spread는 변하지 않는다. 따라서 이 불변성을 새로운 독립 성공으로 세지 않았다. S&P500/KOSPI의 동 기간 open→open 가격수익을 기준으로 상위 집단의 평균 초과값을 별도 계산했다.

| 후보 | US 상위 집단–S&P500 | KR 상위 집단–KOSPI |
|---|---:|---:|
| V_ROC20 | +1.177%p | -0.770%p |
| V_LOWVAR20 | -0.443%p | +0.655%p |
| Q0 | +0.690%p | -2.018%p |
| Q1 | +1.158%p | -2.078%p |

이는 일별로 겹친 H20 label의 평균이지 운용 계좌 초과수익이 아니다. Task9.1 지수 snapshot을 우선하고, 완전한 label 구간을 덮지 못하면 Task10 tail을 **그 구간 전체에** 사용했다. 두 원본 open의 중첩39/40일은 정확히 일치했다. 합성 지수 경로를 만들지 않았고, 사용 source를 signal별로 기록했다. 배당 미포함 가격지수다. 한국 V_ROC20은 하위 집단이 더 나빴을 뿐, 상위 집단이 지수를 이겼다고 해석할 수 없다.

## 3. 한국 V_ROC20: 큰 spread와 작은 RankIC의 원인

| 통계 | 값 |
|---|---:|
| 일별 상위 평균 / 하위 평균의 시간평균 | +1.999% / -0.767% |
| 각 날짜 상위/하위 집단 내부 중앙값의 시간평균 | +0.694% / -1.352% |
| 일별 spread의 평균 / 중앙값 | +2.766%p / **-0.203%p** |
| spread 양수 비율 | **49.2%** |
| 가장 큰 절대 spread5일의 순합 기여 | 전체 signed spread 합의 **66.7%** |

전체5분위 평균은 대략 **-0.77, +2.74, +3.89, +3.03, +2.07%**로 단조 증가가 아니다. 중간 순위가 더 좋아 전체 RankIC는 약0.008에 그친다. 이 완전5bin 분할은 잔여 종목을 배분하므로 마지막 bin 크기가 원본 계약의 동일 floor(N/5) top-k와 다를 수 있다. 원본 spread 정의를 바꾸지 않았다.

기여는 각 날짜 top/bottom의 ±1/k 수익을 합한 뒤 날짜 수로 나눴다. 삼성전기 **009150(KR015) +1.436%p**, 카카오 **035720(KR002) +1.292%p**, SK텔레콤 **017670(KR010) +0.851%p**가 큰 signed 기여를 보였다. 합계가 net보다 큰 것은 다른 기여가 음수이기 때문이다.

사후 민감도는 다음과 같다. 제거 뒤 집단을 다시 구성한 진단이며 새 성공 전략으로 채택하지 않는다.

| 제외한 항목 | 남은 평균 spread |
|---|---:|
| 절대 net 기여 최대1종목 KR015 | +1.186%p |
| 최대3종목 KR015/KR002/KR010 | **-0.117%p** |
| 절대 spread 최대5일 | +0.946%p |

상위 극단 event는2026-04-28 signal의20세션 구간이다. 저장 원가격에서 **4/29→6/1 LG전자066570 open141,200→375,000(+165.58%)**, 삼성전기009150 **818,000→2,021,000(+147.07%)**로 계산된다. 다음날부터 실제 동일 시장 세션을 센 산술은 일치했다. 그러나 이번에는 외부 수집0이므로 이 급변을 공식 거래소/기업행사 자료로 새로 인증하지 않았다. Task12에서009150의 vendor firstTradeDate도 누락돼 있었다. **큰 값이 오류라고 단정하지도, 인증된 경제적 이익으로 확정하지도 않는다.** 경제성 이용 전 이 소수 endpoint·코드/단위·기업행사를 좁게 대사해야 한다. [기여·endpoint 근거](../../runtime/task14/supplement.json).

전 후보에 같은 top1/top3종목·top5일 진단을 적용했다. 다른 후보의 부진도 제거 선택으로 성공시키지 않았다. V_LOWVAR20 KR은 제거 후에도 일부 양의 지표가 남지만 반등 국면 손실과 넓은 CI 때문에 곧바로 유효 알파로 분류할 수 없다.

## 4. QuantaAlpha: 단순 모멘텀·반전 대비 추가 정보

동일 종목/날짜/H20에서 일별 rank를 사용했다. Q1은 양의 MOM20, Q0는 음의 MOM20을 baseline으로 했다. **현재 signal을 baseline+절편에 투영**해 잔차를 만들고, partial Spearman과 잔차 RankIC를 계산했다. 미래 label은 이 잔차 signal을 만드는 데 사용하지 않았다. partial 통계의 target residualization은 사후 평가일 뿐 매매 비중·새 후보가 아니다.

| 후보/시장 | baseline 순위 상관 | 잔차 분산 비중 | partial rank 평균 [95% CI] | 잔차 RankIC |
|---|---:|---:|---:|---:|
| Q0 US vs 단순 반전 | +0.927 | 13.9% | **-0.1027 [-0.1677,-0.0442]** | -0.0933 |
| Q0 KR vs 단순 반전 | +0.828 | 29.3% | -0.0434 [-0.1092,+0.0316] | -0.0383 |
| Q1 US vs MOM20 | +0.989 | 2.15% | +0.0084 [-0.0256,+0.0431] | -0.0007 |
| Q1 KR vs MOM20 | +0.962 | 7.30% | -0.0350 [-0.0873,+0.0132] | -0.0329 |

Q1의 거래량 요소는 현재 표본에서 순위를 거의 바꾸지 않았고, 잔차의 양의 방향도 안정적이지 않다. Q0의 유동성 가중은 단순 반전보다 좋은 정보를 보이지 않았으며 US 조건부 성분은 오히려 음수였다. 이 음의 방향을 사후에 뒤집어 성공 후보로 만들지 않는다.

Q0 US partial은 H1 **-0.0904**, H2 **-0.1229**였다. Q0 KR은 **-0.0848/+0.0265**, Q1 US **+0.0122/+0.0023**, KR **-0.0549/-0.0016**이다. 탐색적 증분 검정6개도 Holm 후 모두1이었다. **양의 추가 정보를 확인하지 못했으므로 같은 추세/반전 수식 변형에 반복적으로 LLM 예산을 쓸 근거가 부족하다.** 원본 엔진 전체의 탐색 능력이 나쁘다고 결론 내릴 근거는 아니다.

## 5. RD_SMALL: 별도 track의 단순 모델 대비

| 시장/모델 | MSE | MAE | 재계산 IC / RankIC |
|---|---:|---:|---:|
| US RD_SMALL | 0.00224284 | 0.033138 | +0.0317 / +0.0342 |
| US zero | 0.00227781 | 0.033453 | N/A |
| US Ridge | 0.00224323 | 0.033143 | +0.0322 / +0.0368 |
| US Tree | 0.00225983 | 0.033315 | +0.0040 / +0.0080 |
| KR RD_SMALL | 0.00319226 | 0.040396 | -0.0382 / -0.0256 |
| KR zero | 0.00274424 | 0.036703 | N/A |
| KR Ridge | 0.00276338 | 0.036710 | +0.0345 / +0.0330 |
| KR Tree | 0.00274973 | 0.036649 | +0.0168 / +0.0312 |

MSE 단위는 소수 수익률의 제곱, MAE는 소수 수익률이며 IC와 별개다.

- **US:** zero–RD MSE 개선 **+3.50e-5**, 95%CI **[-2.64e-5,+9.85e-5]**. Ridge–RD는 **+3.92e-7**, CI **[-6.54e-6,+6.51e-6]**이다. 일별 예측 Pearson 상관0.9935/순위0.9881, Ridge 제거 후 잔차 분산은1.30%, 잔차 RankIC **-0.0108 [-0.0541,+0.0326]**다. LLM 생성 코드라는 사실 외에 추가 가치는 확인되지 않았다.
- **KR:** zero–RD **-4.48e-4 [-6.59e-4,-2.44e-4]**, Ridge–RD **-4.29e-4 [-6.37e-4,-2.22e-4]**다. 예측 순위 상관0.179로 US처럼 같지는 않지만, 다르다는 사실이 유용함을 뜻하지 않는다. 잔차 RankIC는 **-0.0374 [-0.0971,+0.0198]**다.
- **편향/분포:** US 예측 평균+0.371%, 실제 평균+0.427%, 예측 std0.278%다. KR은+0.087% 대+0.907%, 예측 std2.267%(Ridge0.326%), 1~99% 예측 범위 **-5.48~+7.07%**다. 같은5특징·6파라미터 선형 모델이어도 KR의 최적화/계수가 불안정할 가능성이 있다. 원인 확정에는 저장 계수·scaler·내부 선택 진단이 필요하며 바로 큰 network를 권하지 않는다.

월별·국면별 결과와 예측 오차/순위 능력을 별도로 저장했다. 이번 US 개선 폭은 작고 KR은 약하다. 학습 손실 감소, MSE 개선, 종목 선정 개선을 같은 성과로 취급하지 않는다.

## 6. 국면·시기 의존성과 실제 episode 수

Task12의 봉인된 분류를 재생성하지 않고 사용했다. US는 장기 **SPY proxy** 분류이며 S&P500 자체 분류로 부르지 않는다. KR은 `LEGACY_KS11`로2026-10-02까지이며 이후8개 유효 signal일은 `NO_REGIME_DATA`다. EX_POST 마지막20일도 PENDING으로 유지하고 다른 snapshot을 이어 붙여 분류하지 않았다.

아래는 V_ROC20의 대표 coverage이며 다른 후보도 [stability.csv](../../runtime/task14/stability.csv)에 있다. input mask 때문에 KR 유효 종목 수는 날짜마다 달라진다.

| AS_OF 구분 | US 유효일 / label 확장 후 episode 묶음 | KR 유효일 / episode 묶음 |
|---|---:|---:|
| UP | 26 / 1 | 109 / 1 |
| DOWN | 0 / 0 | 23 / 1 |
| CRASH | 0 / 0 | 14 / 2 |
| REBOUND | 0 / 0 | 18 / 2 |
| SIDEWAYS | 133 / 2 | 3 / 1 |
| TRANSITION | 39 / 6 | 16 / 1 |
| HIGH_VOL 중첩 | 0 | 159 / 1 |
| 분류 자료 없음 | 0 | 8 |

각 run을 H세션 뒤까지 확장한 후 같은 분류에서 겹친 run을 합친 수다. **같은 분류 안의 기계적인 비중첩 묶음**이며 경제적으로 독립된 사건 수나 분류 사이의 비중첩 episode를 입증하지 않는다. 예를 들어 KR UP12run은 label 중첩을 합치면1묶음이다. 얇은 국면의 일반화는 모두 `INSUFFICIENT_EVIDENCE`다. US에 정의상 없는 급락/반등을 기억에 의존한 구간으로 채우지 않는다.

### 2026년3월 KR의 signal일을 고정한 진단

| 후보 | 2/27~3/31: 22일 RankIC / spread | 3/31~4/8: 7일 RankIC / spread |
|---|---:|---:|
| V_ROC20 | +0.1713 / +4.743%p | +0.1282 / +8.707%p |
| V_LOWVAR20 | +0.1836 / +6.003%p | +0.0008 / -1.115%p |
| Q0 | -0.2001 / -5.029%p | -0.0840 / -6.783%p |
| Q1 | +0.1004 / +3.438%p | +0.1366 / +7.220%p |

두 구간은3/31을 공유하고 H20 target도 경계를 넘으므로 독립적인 급락/반등 전략 성과가 아니다. EX_POST는 결과 분석에만 사용했으며 기존 signal이나 투자 판단에 되돌려 적용하지 않았다.

KR V_LOWVAR20은 H1/H2 RankIC가 **+0.0898/+0.0995**로 양수지만 AS_OF REBOUND18일에서는 **-0.1895, spread -18.40%p**였다. UP109일에서는+0.1286, SIDEWAYS는3일뿐이다. US에서는 H1 **-0.0966**, H2 **+0.0240**으로 부호도 바뀐다. 좋은 국면 하나를 선택해 통과시키지 않는다.

PBO/DSR/CPCV는 **N/A**다. 완전한 전체 탐색 strategy-return 행렬·독립적인 미노출 분할 이력이 없고, 이번에는 Sharpe나 매매 경제성을 평가하지 않았다. 도구 이름을 추가했다고 소표본/선택 편향이 해소되지 않는다.

## 7. 후보 판정과 다음 최소 작업

| 후보 | US 판정 | KR 판정 | Task15를 권하지 않는 이유 |
|---|---|---|---|
| V_ROC20 | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | 넓은 CI, KR 비단조성·극단 기여, 양시장 primary 불통과 |
| V_LOWVAR20 | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | KR은 연구 단서지만 CI/반등 취약/적은 episode, US 불안정 |
| Q0 | REJECTED | INSUFFICIENT_EVIDENCE | US의 단순 반전 제거 후 추가 성분이 불리. KR도 양의 증분 미확인 |
| Q1 | REJECTED | REJECTED | 현재 후보를 추가할 가치가 미확인이고 기존 MOM20과 강하게 중복 |
| RD_SMALL | REJECTED | REJECTED | US는 거의 Ridge, KR은 기준선보다 오차가 큼. 새 모델의 효용 미확인 |

여기서 REJECTED는 **현재 추가 후보를 Task15로 추천하는 판단을 기각**한다는 뜻이며 알파 부재의 증명이나 엔진 전체 폐기가 아니다. Task13 상태를 소급 변경하지 않았다. `PROMISING`/`VALIDATED_HISTORICAL`로 옮긴 후보는 없다.

우선순위는 다음과 같다. 이번에는 실행하지 않고 [verdict.json](../../runtime/task14/verdict.json)에 범위만 남겼다.

1. **Task13을 제한 재개하기 전에**, 후보ID/코드·데이터hash/H/metric 정의를 한 receipt로 묶어 Q1의 “미평가” 문구와 실제 metric 귀속의 모호함을 없앤다. 복수 출력·예산·실패를 명시하고 무제한 재시도하지 않는다.
2. 최대1~2개의 **다른 메커니즘**으로 제한한다. 예컨대 미실행 overnight 대 intraday 원본 mutation 가설은 별도 Task13 계약에서 계산할 수 있지만 이번 Q2 성과는 추정하지 않는다. mutation/crossover를 완주했다는 기록도 만들지 않는다. 반복 사용하는 역사는 개발 증거로 남는다.
3. RD는 새 network/재학습보다 저장된 KR 계수·정규화·내부 checkpoint 선택과 Ridge의 차이를 먼저 조사한다. 다른 예측을 냈다는 것만으로 성공 판정하지 않는다.
4. 경제성에 쓰기 전에 위2종목의 극단 endpoint·단위·기업행사를 **좁게** 확인한다. 전시장 DB나 대규모 신규 수집은 필요하지 않다. 적격 재무·거시·이벤트 특징을 추가한다면 정보 vintage 적격성을 먼저 확인한다.
5. 기존 Forward를 유지한다. 현재5후보를 공식 Paper/Champion에 등록·대체하지 않고, 독립 Forward가 없는데 실전 승격을 권하지 않는다.

확인한 주원인은 **약하거나 중복된 현재 후보, US 단순 모델 대비 증분 부족, KR 모델의 불안정한 예측**이다. 짧은 기간·생존 코호트·불완전한 기업행사는 중요한 한계지만 그것만이 부진 원인이라고 단정하지 않는다. H20/H5 시각 정의는 이번에 일치했다. 다른 horizon이면 성공한다는 근거도 없어 변경하지 않았다.

## 8. 실행·보존·재현

평가 코드는 [experiments/task14](../../experiments/task14/)에만 추가했다. 기존 Qlib/Task12 평가 함수, NumPy/SciPy/pandas와 V103 block resampling 구조를 활용했다. 새 통계 서비스·DB·백테스터를 만들지 않았다. 기존 score/label/checkpoint를 복제하지 않고 일별 지표·기여·집계와 참조 hash를 저장했다.

```bash
.venv/bin/python experiments/task14/run.py       # 기존 격리 RD/Qlib 환경, network=none
.venv/bin/python experiments/task14/supplement.py
.venv/bin/python experiments/task14/verdict.py  # 판정 JSON만 작성. 연구를 실행하지 않음
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q \
  experiments/task14/test_validation.py
```

AGENTS 최소4suite **24 PASS**, centered-null/의존성/결측/다중비교/투영·실제 자료 검사 **5 PASS**, compileall PASS다. [안전 XML](../../runtime/task14/safety_tests.xml), [평가 XML](../../runtime/task14/validation_tests.xml). 운영 코드를 바꾸지 않아 추가 운영 suite와 V104 운영 실행은 이번에 미실행했다. 초기 supplement의 과도하게 엄격한 수치 assert 실패는 위와 같이 보존하고 최종 성공과 구별했다.

LLM·외부API·신규 학습·신규 알파는0이다. 주 평가는 기존 Docker CPU2/4GB에서 실행했고 전체 누적 CPU는 미계측이다. Task13의 전체435파일을 재확인했으며 원본 성과·후보 방향·모델·운영 기록은 불변이다. [Forward timer 읽기 확인](../../runtime/task14/forward_timer_readonly.log)도 active였다. 최종 파일 hash와 시험 수는 [artifact_manifest.json](../../runtime/task14/artifact_manifest.json)에 있다.

**독립 알파와 단순 기준선을 넘어서는 전문 엔진의 정보 증분을 확인하지 못했다. Task15는 시작하지 않는다. 제한된 Task13 재연구와 작은 입력·귀속 점검을 다음 작업으로 권고한다.**

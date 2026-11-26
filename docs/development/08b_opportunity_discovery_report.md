# Task 8b — 투자 후보 확대·저평가 및 반등 기회 검증

기준: 2026-11-14 KST. HYBRID_MINIMAL 유지. **탐색·분석·별도 Shadow 연결은 실행했으며, 투자 성과 검증은 대기 중이다.**

- 미국 8·한국 6, 총 14개 기업·6개 업종을 분석했다. 12개는 공식 원문/API를 보존했고, HRMY·AMKR는 직접 HTTP 수집 실패로 공식 페이지의 부분 발췌만 확보했다. 14개 분석을 14개 투자 적격 판정으로 세지 않는다.
- 분류는 `RESEARCH_SHADOW` 5, `RESEARCH_INCOMPLETE` 9, `PAPER_ELIGIBLE` 0, `REJECTED` 0이다. FPS·산일전기·롯데쇼핑·기업은행에 각각 2.5% **탐색 목표**를 봉인했다. NVIDIA는 실적 발표 후 재검토하며 진입하지 않는다.
- 실제 체결은 **0건**, 탐색 계좌도 현재 현금 100%다. 주말 봉인 이후 다음 공식 세션은 한국 11월 16일 09:00, 미국 같은 날 23:30 KST다. 과거 가격으로 체결을 만들지 않았다.
- 관련 회귀 91개와 필수 안전·운영 53개, 합계 **144개 통과**. 실제 PostgreSQL 합성시장 시험에서는 진입→커밋 직후 중단→중복 없는 복구→관측→126세션 청산을 실행했다. 이는 실제 Forward 체결 증거와 다르다.
- 기존 공식 Paper 적격성·운용 알고리즘·Live 잠금을 유지했다. Factory는 정식 제안 등록까지 완료했으며, 실험은 기존 작업 우선순위와 정상 예산을 기다린다. 수익 우위·목표가 정확도·1/3/6개월 성과는 미검증이다.

## 1. 실제 탐색과 자료 범위

시장별 RSS 4질의에서 총 154개 미디어 단서를 수집하고, 고정 Vibe 원본 screener의 미국 40개 출력을 실제 실행했다. 현재 종목 메타데이터 매칭은 미국 171개, 한국 55개였지만, 한국 결과에는 중복·구형 법인이 있어 이를 적격 유니버스 규모로 주장하지 않는다. 전체 시장의 시세·재무를 일괄 수집하지 않고 Terra가 14개를 선정한 뒤 자료 적격성을 점검했다.

업종은 전력·산업재·헬스케어·소비재·금융·기술이다. 종목 선정 입력·원본 Vibe 출력·누락 이유는 [discovery](../../runtime/task8b/discovery/)와 [native_artifacts](../../runtime/task8b/native_artifacts/)에 있다. 한국의 셀트리온제약·RFHIC는 DART `company.json`의 시장 구분으로 `.KQ`를 확인했다. 현재 상장 확인이며 역사 시점별 생존 편향을 해결한 자료는 아니다.

한국 6개 기업의 회사·반기 재무·주식수 자료를 확보했다. 셀트리온제약은 연결 미제공 응답을 보존하고 별도 재무를 사용했다. 추가 3분기 API는 금호건설·롯데쇼핑에서만 성공했고, 다른 4개의 `013`은 그대로 남겼다. 최신 수치를 임의 보충하지 않았다. [원문·수집 기록](../../runtime/task8b/fundamentals/), [최초 봉인 입력](../../runtime/task8b/research_packet.json), [추가 관측 입력](../../runtime/task8b/research_packet_v2.json).

가격 수집은 기존 수집기·공식 세션·불변 관측을 재사용했다. 초기 14회, 봉인용 일봉 4회, 봉인 후 신규 가격 관측 1회로 **19/22회**의 bootstrap 가격 요청을 사용했다. 미국 약 195~200행·한국 200행의 선택적 일봉은 새로 다운로드한 역사 자료이며 신규 Forward가 아니다. V87 수치/schema gate와 격리 revision 점검을 거쳤고 운영 canonical은 교체하지 않았다. 공식자료·탐색의 논리 요청 약 48건과 별도 웹 조회 약 20건을 기록했지만, redirect·인증 transport까지 포함한 정확한 wire 요청 총계는 계측하지 못했다.

## 2. 후보별 판단과 조건부 가치 범위

아래는 **1년 뒤 Bear/Base/Bull의 조건부 가격**이다. 달러 또는 원 단위이며 확률·검증된 목표가·컨센서스가 아니다. 현재 가격은 최초 분석 참조값이다. 이후 별도 관측을 원래 판단에 소급 반영하지 않았다.

| 기업 | 참조 가격 | 조건부 가격 Bear / Base / Bull | 상태·판단 | 추가 확인할 핵심 |
|---|---:|---:|---|---|
| NVIDIA NVDA | $159.88 | 87.86 / 169.29 / 288.28 | SHADOW·발표 대기 | 경영 승계, 지속 FCFF, 희석·청구권 |
| CoreWeave CRWV | $51.01 | 양의 FCFF 방식 부적합 | INCOMPLETE·대기 | 부채·설비투자·리스·고객 선불·희석 |
| Forgent Power FPS | $21.29 | 13.15 / 27.13 / 41.10 | SHADOW·2.5% 탐색 목표 | Up-C/NCI·세금수취약정·완전희석 주식수 |
| Harmony HRMY | $33.28 | 20.74 / 40.82 / 62.21 | INCOMPLETE | 원문 전체, 독점권·로열티·제품 집중 |
| Citizens CFG | $64.97 | 36.10 / 65.14 / 88.44 | INCOMPLETE | CET1·신용손실·정상 이익·배당능력 |
| Amkor AMKR | $35.45 | 20.16 / 41.86 / 61.88 | INCOMPLETE | 원문 전체·가동률·증설·현금흐름 |
| Bloom BE | $187.45 | 산정 유보 | INCOMPLETE | 프로젝트별 현금 전환·투자·자금조달 |
| Keurig Dr Pepper KDP | $36.315 | 산정 유보 | INCOMPLETE | 분할·거래 후 부채 및 우선주 배분 |
| 산일전기 062040.KS | ₩128,400 | 72,374 / 142,164 / 210,015 | SHADOW·2.5% 탐색 목표 | 수주 품질·납기·연간 이익·현금흐름 |
| 금호건설 002990.KS | ₩11,210 | 3,728 / 10,438 / 16,403 | INCOMPLETE | PF 보증·충당금·자본·차환 |
| 셀트리온제약 068760.KQ | ₩41,600 | 12,216 / 29,268 / 46,319 | INCOMPLETE | 별도 재무 범위·관계사·제품 수익성 |
| 롯데쇼핑 023530.KS | ₩77,700 | 45,691 / 107,509 / 193,785 | SHADOW·2.5% 탐색 목표 | 자산 회수성·리스·부채·지속 ROE |
| 기업은행 024110.KS | ₩19,030 | 10,694 / 24,096 / 32,484 | SHADOW·2.5% 탐색 목표 | 대손·규제자본·정책금융·배당 |
| RFHIC 218410.KQ | ₩55,400 | 14,208 / 29,955 / 49,728 | INCOMPLETE | 수주·일회성 이익·전환증권·현재 성장 기대 |

`SHADOW`는 연구 허용 상태이며 공식 Paper 승인이 아니다. 자료 부족만으로 기업을 부적격 확정하지 않았다. HRMY·AMKR는 원문 복구, CFG는 은행 자본·신용 분석으로 해결 가능한 연구 공백이다. 반대로 RFHIC는 선언한 반기 EPS 경로로 현재 가격을 설명하기 어려워 추가 성장 증거가 필요하다.

우선 연구 매력은 **미국 FPS, 한국 롯데쇼핑·기업은행의 조건부 가격 여유**에 있다. FPS Base의 14% 할인 현재값은 $23.79, 롯데쇼핑은 ₩94,306, 기업은행은 ₩21,905다. 그러나 정상 이익·자산 가치·주주 청구권 가정이 틀리면 이 여유도 사라진다. 산일전기는 구조적 전력 수요 가설을 관측할 후보지만 Base 할인값 ₩126,932가 참조가보다 낮아 1년 안전마진이 확인된 저평가주로 부르지 않는다. 소액 탐색은 해당 가설의 반증을 위한 관측이며 매수 권고·최적 전략 선정이 아니다.

계산은 [opportunity.py](../../src/quant_harness/investment/opportunity.py)에 있다. [사전 선언 가정](../../runtime/task8b/declared_valuation_hypotheses.json)과 [valuation 계약](../../experiments/task8b/valuation_contract.json)을 먼저 보존한 뒤 12기업×9경로=108개를 계산했다. 양의 FCFF 배수법을 적용할 수 없는 4개는 `NOT_VALUABLE`로 남겼다. 나머지 104개 계산 성공은 경제적 타당성 검증이 아니다.

EPS×PE는 이미 주주가치이므로 부채를 다시 빼지 않는다. 장부가×PBR는 지배주주 보통주 가치·주식수 proxy와 회수성에 의존한다. FCFF는 미래 EV에서 **미래 부채·기타 청구권을 차감하고 현금을 더한 뒤 희석 주식수로 나눴다.** 일부 EPS는 분기/반기의 단순 연율화 proxy이며 정상 이익이나 회계연도 예측이 아니다. 배수·성장률·할인율·기타 청구권 0은 선언한 민감도 가정이다. 중간 배당·현금분배가 빠진 exit-multiple 계산으로 완전한 DCF를 대체했다고 주장하지 않는다.

## 3. NVIDIA·CoreWeave의 하락과 독립 반론

두 종목의 독립 반론 작업에는 다른 분석자의 결론을 주지 않고 동일 사실·선언 가정만 제공했다. 실제 응답은 모두 `WAIT_EVENT`를 선호했다. [독립 결과·프롬프트](../../runtime/task8b/native_artifacts/independent_counter_resume.json).

### NVIDIA

공식 [CEO transition 발표](https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-CEO-Transition/default.aspx)는 11월 12일이다. Jensen Huang 사임, Colette Kress의 임시 CEO·CFO 역할, Harvey Jones의 이사회 의장 역할을 확인했다. 공개되지 않은 사임 이유를 추정하지 않았다. 다음 [공식 실적 일정](https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Sets-Conference-Call-for-Third-Quarter-Financial-Results/default.aspx)은 **11월 17일 약 13:20 PT(18일 약 06:20 KST)**다. 기존 연구의 19/20일 검토일과 구분하고 과거 예측을 수정하지 않았다.

성장 가설은 데이터센터 수요·제품 전환·현금 전환이 승계 후에도 유지된다는 것이다. 반론은 경영진 전환·고객 투자 집중·운전자본·밸류에이션 압축이다. [Q2 FY27 공식 자료](https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Second-Quarter-Fiscal-2027/default.aspx)의 매출 $96.221bn, 데이터센터 $89bn, FCF $21.341bn은 확인 사실이다. GAAP EPS $2.46에는 증권 관련 이익이 포함돼 단순 연율화로 정상 EPS를 확정할 수 없다.

고정 일봉에서 11/6→11/12 NVDA −11.02%, SPY +2.97%였고, 11/11→12는 각각 −4.41%, −0.35%였다. 공통 시장 하락만으로 설명하기 어렵지만 CEO 변화의 인과 효과를 분리한 실험은 아니다. 금리·AI 수요·다른 뉴스가 교란한다. [계산 및 한계](../../runtime/task8b/price_attribution.json).

1년 Base 미래값 $169.29의 12% 할인값 $151.15는 최초 $159.88보다 낮다. 3년 Bear/Base/Bull은 $81.81/$241.92/$479.00으로 가정 민감도가 크다. 새 관측가 $161.04에서 연 12%를 충족하려면 FCFF 마진 36%, exit 배수 24, 연 1% 희석, 미래 순현금 $5bn 가정 아래 1년 매출 약 **$511.45bn**, 3년 약 **$654.62bn**이 필요하다. 이는 가격의 조건부 역산이며 실제 시장 컨센서스를 관측한 결과가 아니다. Q2 연율화 매출 proxy와도 구분한다. [역산 원본](../../runtime/task8b/reverse_conditions.json).

따라서 즉시·분할 진입보다 **발표·가이던스·승계 근거를 확인한 조건부 대기**를 봉인했다. Q3 매출·마진 반증 기준도 기록했으나 이를 자동 청산 권한으로 바꾸지 않았다.

### CoreWeave

[Q3 공식 발표](https://investors.coreweave.com/news/news-details/2026/CoreWeave-Reports-Strong-Third-Quarter-2026-Results/default.aspx)의 매출 $3.661bn·백로그 $132.5bn은 성장 근거다. 그러나 영업이익 $207m 대비 이자비용 $846m, CFO $1.975bn 대비 현금 PPE 구매 $9.441bn으로 현금·조달 제약이 크다. 고객 선불/이연매출과 백로그의 실제 인도·매출 전환도 구분했다. 발표의 capex 정의와 현금 PPE 구매를 같은 지표로 취급하지 않았다.

11/6→11/12 CRWV는 오히려 +21.98%, SPY +2.97%였고 마지막 하루는 −6.86%였다. 특정 고점 이후 하락만으로 동일한 '저점' 상태를 전제할 수 없다. 관측 약 200봉의 고점은 52주 고점도 아니다.

현재 음의 FCFF에 양의 정상 FCFF 배수를 억지 적용하지 않았다. 선언한 3년 Base에서는 미래 순부채 $95bn·연 10% 희석이 주주 잔여가치를 소진한다. 계산의 0은 **그 가정 아래 유한책임 잔여가치 하한**이며 현재 적정가 0·파산 예측이 아니다. Bull의 $259.17 역시 충분한 자금조달과 현금 전환을 전제한다. $51.759 관측가에서 연 18%를 충족하려면 Base의 10% FCFF 마진·20배·동일 자본 경로 아래 3년 매출 약 **$79.14bn**이 필요하다. 선언 Base $45bn보다 높지만 부채·capex 경로가 달라지면 역산도 바뀐다.

결론은 **조달·리스·부채 만기·희석·계약별 현금 전환을 먼저 확인**하는 것이다. 상승 여력이 큰 시나리오와 조달 실패/주주 몫 축소 시나리오를 모두 남겼고 탐색 진입도 보류했다.

## 4. 현금 100% 원인과 Vibe 대비 차이

첫 원본 VibeChatLLM 분석 4배치는 14개 전부 수치 예측이 비어 있었고 대기/정보 부족을 반환했다. 따라서 기존 현금 판단에는 **검증된 투자 우위 부족과 분석의 수치 연결 부족이 함께 있었다.** 모든 주가가 비싸다는 실증 결과는 아니다.

후속 작업에서 원본 `valuation-model/SKILL.md`의 EV→주주가치·민감도·가치 함정 점검을 적용하고, 선언한 what-if를 제공했다. 원본 Vibe `equity_bridge`도 실제 실행해 14개 유효 FCFF 행의 계산 일치를 확인했다. 음수 잔여가치의 유한책임 하한 표시는 별도 연구 계산에 명시했다. 중국시장 예시 배수·세율은 가져오지 않았다.

동일 최종 입력에서 Vibe 후속 연구가 제안한 탐색 4개를 HYBRID도 유지했다. 추가 기능의 확인된 효용은 **별도 권한, 출처·시점, EV/주주가치 검산, 위험 한도, 봉인, 원장 복구**다. 더 나은 종목 선정·수익률은 아직 증명하지 못했다. 최초/후속 사이에는 자료·프롬프트·연구 허용 범위가 달라졌으므로 순수 모델/스킬 인과 A/B로 해석할 수 없다.

원본 HRP도 동일 가격에서 미국 8개·한국 6개를 각각 계산했다. 이는 공분산 기반 100% 배분 계산의 실행 확인이며 Vibe 전체 투자판단은 아니다. 적격성 gate가 없는 HRP를 현금 판단의 대안 우승자로 채택하지 않았다. [원본 실행 결과](../../runtime/task8b/native_artifacts/native_allocation_diagnostic.json).

## 5. 분리 Shadow·원장·자동 관측

| 계좌 | DB | 봉인 목표 | 실제 상태 |
|---|---|---|---|
| 연구 | `quant_task3_task8b_research` | 가설·자료·후속 요청 | 불변 기록·예약 보존 |
| 미국 탐색 | `quant_task3_task8b_explore_us` | FPS 2.5%, 현금 97.5% | 현금 $100,000, 체결 0 |
| 한국 탐색 | `quant_task3_task8b_explore_kr` | 산일·롯데·기업은행 각 2.5%, 현금 92.5% | 현금 ₩10,000,000, 체결 0 |

총노출 30%·종목 5%·업종 10%, 최초 probe 2.5%·최대 6개로 제한했다. ETF는 비교 데이터에만 사용하며 투자 대상은 개별주식이다. 통화·계좌를 합산하지 않는다. 첫 적격 regular quote가 봉인 이후이고 60초 이내이며 benchmark도 관측돼야 한다. 정수 수량·유동성·비용 검사는 기존 Paper 코드가 수행한다. 일일 provider 12회, 시장별 진입 시도 2회를 예약하며 실패도 예산에 포함한다. 스프레드는 실측 bid/ask가 아니라 기존 비용 가정이다.

사전 연구 계약의 결정 유효기간 상한은 96시간이지만 실제 실행은 기존 Paper의 **더 엄격한 72시간**을 사용한다. 현재 봉인은 11/14 02:47 UTC, 미체결 만료는 11/17 02:47 UTC다. 만료 시 재봉인을 강제하지 않는다. 현재 공식 세션대로라면 다음 월요일 두 시장의 관측 기회가 포함된다.

처음 봉인 후 post-cost 한도 검사가 필요함을 발견했다. 별도 재현 시험·최소 guard 수정 후, 기존 미체결 계획을 보존·무효화하고 **동일 자료·가설·비중**을 새 worker hash에 명시적으로 재봉인했다. 숨겨진 주문·사후 성과 조정은 없다. [재봉인 근거](../../runtime/task8b/guard_reseal.json).

기존 단일 `quant-operations.timer`의 CLI에 관측과 읽기 평가 hook만 연결했다. 11/14 정상 systemd 실행에서 `WAIT_NEXT_REGULAR_PRICE`와 `PENDING`을 확인했다. 추가 Gateway·타이머는 배포하지 않았다. [실제 서비스 로그](../../runtime/task8b/evidence/scheduled_hook_final.log), [새 프로세스 복구·한도 증거](../../runtime/task8b/restart_probe.json).

21/63/126개의 **확인된 거래 세션**과 해당 정확한 checkpoint 가격이 있어야 채점한다. 세션 날짜 경과만으로 성숙 처리하지 않는다. 126세션 뒤 다음 적격 quote에서 청산하는 경로는 합성시장 DB에서 시험했다. 실제 1/3/6개월 표본은 아직 없다.

평가는 현금이 많은 계좌와 100% 지수의 차이를 그대로 종목 선정 실패로 부르지 않도록, 전액 지수와 **최초 투자금 비율을 맞춘 gross 대조군**을 함께 보존한다. gross/net·실제 기록 비용·노출 효과를 분리하고, 검증되지 않은 ETF 매매비용을 넣어 net benchmark를 만들지 않는다. 배당·분할 확인이 없는 mark는 잠정 가격 관측이며 정식 checkpoint는 PENDING이다.

**남은 실행 제약:** 공식 기업행위/수정주가 대사 adapter, 배당 반영, 서술형 반증의 검증된 조기청산 adapter는 Task 9 과제다. 현재 반증은 후속 연구 요청이며 자동 이벤트 청산을 완료했다고 주장하지 않는다. 따라서 자동 관측 연결은 완료했지만 무인 장기 보유·총수익 평가의 완결은 아니다.

## 6. Factory·복기·Task 9 연결

UTC 예산이 정상 갱신된 뒤 기존 Task 5 공통 A/B가 11/14 00:02 UTC에 실제 실행돼 `FORWARD_REQUIRED`를 남겼다. 원래 대기하던 Task 6·7 제안을 순서대로 등록한 다음 Task 8b를 등록했다. 과거 BLOCKED 파일을 성공으로 덮어쓰지 않았다.

Task 8b 제안 `REVIEW-072e33a9a41f4c3d0a7fc5e5`는 `READY_FOR_DIAGNOSTIC`, 승격 `NOT_ELIGIBLE`이다. 당일 실험 1회 예산은 Task 5가 이미 사용해 Task 8b 실행은 `BLOCKED_NORMAL_BUDGET_OR_OLDER_PRIORITY`다. [공식 등록 영수증·후속 요청](../../runtime/task8b/factory_status.json). 12개 원문 기업 조건은 충족하지만 12개의 독립 Forward 결과·투자 우위를 충족한 것은 아니다.

Factory 연결은 **정식 제안·예약 대상 및 연구 요청 생성까지** 검증했다. Task 8b의 공식 격리 평가 자체는 아직 미실행이다. 등록된 worker는 handoff 용도이며 장기 예산·우선순위 dispatcher와 evaluator 완성은 Task 9에서 확인해야 한다. 현재 원장을 변경하거나 예산을 우회하지 않았다.

별도로 정상 일일 재시도가 성공한 공통 실험 영수증을 다른 kind로 저장하면서 불변 ID 충돌을 일으키던 기존 버그를 발견했다. 실제 SQL 재현 실패→retry 참조에 종류·날짜 metadata만 추가→같은 재현 시험 통과→정상 운영 CLI 성공을 확인했다. 원래 공식 실험 영수증·결과·전략은 변경하지 않았다. [버그 diff](../../runtime/task8b/operations_retry_fix/fix.diff), [수정 전 실패](../../runtime/task8b/evidence/retry_collision_before.log), [수정 후 운영](../../runtime/task8b/evidence/full_tick_after_fix.log).

NVDA 실적 관측의 잘못된 index URL도 별도 최소 source 수리로 공식 newsroom을 사용하도록 했다. issuer별 허용 host와 교차 issuer 차단을 시험했고 GET 200·111개 링크를 실제 확인했다. 아직 대상 Q3 발표는 없어 예측 결과는 PENDING이며 기존 24시간 관측 예약은 우회하지 않았다. [수리 증거](../../runtime/task8b/source_repair/).

Task 9 요청에는 기업별 부족 자료, 실적/반증 관측, 가격 변경 이후 재평가, CA 대사, 비용·희석·자금조달 및 정상 Factory 후속 평가가 포함된다. 당시 원문·최초 관측·모델·프롬프트·가정·후속 관측을 분리한다. 이전 Task 7 예측과 Task 8 판단은 소급 수정하지 않았다.

## 7. 모델·시험·복구·재현

Vibe 고정 커밋은 `0025531f005d4a7aac3fb884cda2fba9318e7158`, 원본 checkout은 clean이다. 기존 격리 venv와 네트워크 없는 VibeChatLLM worker, Codex 구독 relay를 사용했다. 모델은 Terra이며 브로커·DB 인증과 주문 도구를 연구 worker에 주지 않았다.

실제 모델 호출은 **11회 시도·8회 성공·3회 구독 한도 실패**다. 확인 가능한 토큰은 discovery 65,187 + analysis 334,309 + counter 57,476 = **456,972**다. 실패 3회 사용량은 불명이라 0으로 세지 않았다. 정상 quota 회복 후 재시도했고 별도 유료 API 결제는 하지 않았다. 금액 비용은 미확인이다. [사용량](../../runtime/task8b/model_usage.json), [실패 포함 trace](../../runtime/task8b/model_calls/). 현재 timer의 대기 tick은 LLM 0회다.

| 검증 | 결과·근거 |
|---|---|
| Task 3~8 및 신규 탐색·retry 회귀 | **91 PASS**, [configured log](../../runtime/task8b/evidence/regression_configured.log) |
| AGENTS 필수 4개 + 운영 5개 파일 | **53 PASS**, [final log](../../runtime/task8b/evidence/mandatory_final.log) |
| compileall src/scripts/tests | exit 0, [log](../../runtime/task8b/evidence/compile_complete.log) |
| V104 Forward 명령 | `NO_ENABLED_CANDIDATES`, append 0, Live false |
| 새 프로세스 불변 hash·원장 대사 | PASS, 2개 활성 계획·0 fills·기존 운영 fingerprint 일치 |
| 세 DB dump·새 격리 DB 복원 | 원문 hash와 양 계좌 대사 확인; [manifest](../../runtime/task8b/backup_latest.json) |
| 실제 서버 재부팅 | **미실행**; 새 프로세스 복구와 구분 |
| 실제 신규 체결·성숙 성과 | **자연 대기**; 주말·정확한 세션·가격·CA 근거 필요 |
| Task 8b 공식 Factory 실험 | **미실행**; 정상 예산·선행 작업 대기 |

V104의 반환값은 AGENTS의 조건부 예시 `NO_NEW_SESSION_AFTER_V104_FREEZE`와 다르다. 현재 코드가 빈 후보에서 먼저 반환하는 경로이며 append 0·Live false를 확인했다. 이를 바꾸려고 후보를 활성화하지 않았다.

최종 회귀 첫 시도에서는 시험 DB 환경변수 누락으로 오류·스킵이 있었다. [실패 로그](../../runtime/task8b/evidence/regression_complete.log)를 보존했고, 환경 지정 후 동일 91개가 스킵 없이 통과했다. 이전 한도 실패·삽입 중 syntax 오류도 보존했으며 통과로 세지 않았다.

재현 명령(기존 격리 PostgreSQL 실행 필요):

```bash
.venv/bin/python -m compileall -q src scripts tests
TASK3_STOCK_TEST_DATABASE_URL=postgresql://quant_task3@127.0.0.1:55432/quant_task3_stocktest \
TASK4_TEST_DATABASE_URL=postgresql://quant_task3@127.0.0.1:55432/quant_task3_review_test \
TASK4_SOURCE_KR_URL=postgresql://quant_paper_kr@127.0.0.1:55432/quant_task3_kr \
TASK5_TEST_DATABASE_URL=postgresql://quant_task3@127.0.0.1:55432/quant_task3_ops_test \
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -rA \
 tests/test_equity_pipeline.py tests/test_investment_pipeline.py \
 tests/test_review_self_improvement.py tests/test_autonomous_operations.py \
 tests/test_operations_verification.py tests/test_portfolio_integration.py \
 tests/test_opportunity_exploration.py tests/test_task8b_operations_retry.py
PYTHONPATH=src .venv/bin/python experiments/task8b/probe_state.py
```

필수 9개 시험 명령은 [AGENTS](../../AGENTS.md)에 있다. 시험은 지정 test DB를 초기화한다. 연구 계산·공식 hook·원본 실행 명령은 [experiments/task8b](../../experiments/task8b/), 당시 로그는 [evidence](../../runtime/task8b/evidence/)에 있다. `probe_state.py`는 현재 주말·미체결 상태의 재현 probe이며 실제 체결 이후에는 그 불변 가정을 갱신해야 한다. Factory 등록·봉인 스크립트는 단순 관측 명령이 아니므로 무의미하게 재실행하지 않는다.

새 탐색 DB는 수동 dump/복원을 확인했지만 기존 Task 5 정기 백업에 자동 편입되었다고 주장하지 않는다. Task 9에서 보존 정책에 포함해야 한다. DB별 snapshot이며 계좌 간 원자적 snapshot은 아니다. 실제 재부팅·장기 실적·총수익·독립 투자 우위는 이번 결과에 포함하지 않는다.

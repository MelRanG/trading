# Task 9.3 — 6개월 역사적 투자 계좌 재현

**HYBRID_MINIMAL 유지. 아래는 2026년 5월 15일 장 마감 이후의 제한된 역사적 진단이며 독립 Forward·투자 우위 검증이 아니다.** 5월18일 첫 가능 세션부터11월13일 종가까지 연속 계좌를 계산했다. 원문·수치·판단·거래·NAV·실패를 보존했으며 운영 Paper·Live에 주문하지 않았다.

## 1. 핵심 성과와 독립 판정

| 시장/초기 자본 | AI 정책 최종금액 | AI 정책 net | 지수100% 가격수익 | 초과수익(%p) | 선정 품질90% 대조군 |
| --- | --- | --- | --- | --- | --- |
| US / $100,000 | 100,576.66 | +0.58% | +1.98% | -1.40 | -26.76% |
| KR / 1,000만원 | 10,000,000.00 | +0.00% | -28.92% | 28.92 | -21.07% |

- **연속 계좌·매매 산술:** 실제 역사 가격, 기존 shared Paper replay로 수행. 정책의 조건부 진입·현금·보유를 그대로 실행했다. 강제 매수·강제 마지막 매도는 없다.
- **데이터 신뢰도: PARTIAL.** 재다운로드한 가격과 당시 발행된 문서다. 완전한 PIT 거래소 원장·상폐 유니버스·뉴스·컨센서스·Total Return을 확보한 실험은 아니다.
- **연구·투자 능력:** 위 지수 대비 결과와 작은 표본으로 판단한다. 기능 테스트가 투자 검증 성공을 뜻하지 않는다. 연간 실적 예측은11월13일까지 정합한 실제 연간 발표가 없어 미성숙이며 예측 정확도를 산출하지 않았다.
- **가치평가 완결성: PARTIAL.** SFM의 명시 가정으로 모델 주당가치를 재현하지 못했다. 후속 검증은 현금흐름 날짜·가정·native 산술 gate부터 보완해야 한다.
- **자율성 제한:** 미국 연구에는 직전 목표와 가격은 제공했으나 실제 체결 후 계좌 readback은 제공하지 못했다. 미국 봉인 결과를 소급 수정하지 않았다. 이후 한국 후속 연구에는 해당 시점까지 재생한 계좌 상태를 전달했다. 월별 신규 전시장 탐색을 반복한 시스템이나 완전 무인 운용을 검증했다고 주장하지 않는다.

**독립 판정:** 기술적 연속 계좌 재현은 진단 범위에서 PASS, 데이터/PIT와 완전한 자율 운영은 PARTIAL이다. 미국 종목 선정은 부진했고 한국의 현금 방어는 관측됐지만, 연구·예측 능력이나 일반적인 투자 우위는 입증되지 않았다.

## 2. 초기 시장 탐색과 선정·제외

미국 33개, 한국 35개를 사전 고정해 가격·유동성·당시 재무/주식수 조건을 검사했다. 미국은 [공식 2026-03-06 지수 변경 발표](https://www.spglobal.com/spdji/en/documents/indexnews/announcements/20260306-1482263/1482263_march2026rebalance1546.pdf)의 편입·편출8기업과 기존2025년의 광범위 업종 표본을 결합했다. 편출 기업을 임의로 제거하지 않았다. 공식PDF 서버403으로 브라우저의 공식 추출을 부분 근거로 보존했다. 한국은5월1~14일 당시 유가증권시장 분기보고서 검색6페이지에서 얻은96기업 중 ticker hash 순으로35개를 정했다. 제출 순서 상위35가 아니며 전시장/모든 업종을 대표하지 않는다. 주식수×당시 가격5000억원 proxy·dated numeric gate 후8개가 적격이었다. 성장·가치·회복을 모두 탐색하려 했으나 제한된 공시 window와 기존 미국 cohort 편향이 남는다.

| 시장 | 탐색 | 적격 | 실제 심층5기업 | 최초 선정 품질 top3 |
| --- | --- | --- | --- | --- |
| US | 33 | 32 | VRT, MOH, SFM, BAM, FLUT | SFM, FLUT, VRT |
| KR | 35 | 8 | 100840.KS, 377740.KS, 036530.KS, 011930.KS, 281820.KS | 100840.KS, 377740.KS, 036530.KS |

미국 심층은 산업재·헬스케어·필수소비·자산운용·소비/게임 등으로 분산했다. 한국은 에너지 설비·진단·지주·클린룸/태양광·반도체 장비 후보이며 최초 산업 분류는 일부 이름에서의 추론으로 표시했고 검증된 GICS라고 취급하지 않았다. 상세 선정 이유·추가 연구 질문·탈락 사유는 [미국 발견 기록](../../runtime/task9_3/discovery/US_model.json), [한국 발견 기록](../../runtime/task9_3/discovery/KR_model.json), [전체 screening](../../runtime/task9_3/screens)에 있다. 조사하지 않은 기업을 투자 매력 없다고 판정하지 않았다.

## 3. 연구와 실행을 담당한 실제 모듈

| 영역 | 실제 재사용과 한계 |
| --- | --- |
| 발견 | Vibe 원본 screener는 현재 Eastmoney 시세만 지원, 역사 asof 미지원. 과거 스크리너 원본 실행 성공으로 표시하지 않음. dated source/가격 adapter와 원본 ChatLLM의 우선순위 판단 사용 |
| 기업·시장 | 원본 `earnings-forecast`, `valuation-model`, `macro-analysis`, `sector-rotation` 스킬과 `src.providers.chat.ChatLLM` 사용. 전체 Autopilot/자율 웹 에이전트 실행과 구분 |
| 재무 숫자 | Task9.2 `financial_packet.verify_fact/model_numeric_view`; exact token·unit·CFS/SFS·기간·출처 hash 유지. narrative는 축약, typed numeric facts는 모델 view에서 보존 |
| 최신 정보 | 당시 Q1→Q2/H1→Q3 원문·공식 Fed/BOK 정책 문서. 최초 미국 입력에는 macro 문서가 없었고 unknown으로 처리; 이후 입력에 추가 |
| 퀀트 | 인과적 MOM63 별도 기준선. QuantaAlpha/RD의 해당2026-05-15 봉인·시점 적격 native alpha가 없어 원본 엔진 투자 성과 N/A. 폐기하거나 단순모멘텀을 해당 알파로 바꾸지 않음 |
| 실행 | 기존 `investment.research.replay_targets` 및 V77 수수료·spread·impact·현금·참여율 함수. 연구용 선택 항목 `rebalance_dates`, `allow_unpriced_hold`만 추가, default 동작 유지 |
| 복기·공식 승인 | 기존 `review.process_review`, Store/Queue, Factory 등록/예약 계약. 실거래·자동승격 권한 없음 |

실제 Terra **16회 / 969,375 tokens**. 사전 상한16회/1,000,000tokens, 매 호출90k 여유 예약을 적용했다. Codex 구독 인증과 기존 격리 환경을 사용했다. 별도 유료 API·패키지·서비스를 추가하지 않았다. 실제 현금 비용은 미계측이고 토큰 수를 달러 비용으로 환산하지 않았다. Codex CLI의 trusted hard token cap은 없어 호출 후 실측과 불확실 사용량 중단 정책을 사용했다. [호출 trace](../../runtime/task9_3/model_calls), [실제 요청](../../runtime/task9_3/requests), [원출력](../../runtime/task9_3/model_outputs)을 보존했다.

## 4. 기업가치·실적·시장 재평가 연구

아래는 **최초5월15일 모델 산출값**이다. 조건부 모델 가정이며 독립적으로 검증된 목표주가가 아니다. 사실/가정·원문의 guidance·독립 전망을 원출력에서 구분했다. 기간·세금·리스·희석·terminal value 가정의 완전한 검증은 남아 있다.

| 시장 | 기업 | 투자 논리(요약) | Bear/Base/Bull | 단위 | 투자 상태 | 비중 |
| --- | --- | --- | --- | --- | --- | --- |
| US | SFM | Specialty fresh, natural and organic food retailer; new stores can grow sales, but negative comparable sales and margin pressure challenge the case. | 26/53/91 | USD | WATCH | 0 |
| US | FLUT | Online sports betting and iGaming revenue grew, but investment, acquisition integration, leverage and variable sports outcomes constrain normalized shareholder cash flow. | 42/91/150 | USD | WATCH | 0 |
| US | VRT | Critical digital infrastructure benefits from data-center demand and capacity expansion; execution, working capital and the price paid for sustained growth matter. | 44/99/205 | USD | WATCH | 0 |
| US | BAM | Alternative asset management earns fees on capital; fundraising, deployment, realization timing and the economics of affiliates drive distributable earnings. | 16/29/48 | USD | RESEARCH_INCOMPLETE | 0 |
| US | MOH | Business lines and economics cannot be established from the supplied primary material; momentum does not establish an investment case. | None/None/None | USD | RESEARCH_INCOMPLETE | 0 |
| KR | 100840.KS | Industrial equipment maker exposed to oil and gas plant and power-project spending. Air coolers dominate revenue; project timing and working capital determine whether the | 15400/27500/58600 | KRW | RESEARCH_INCOMPLETE | 0 |
| KR | 377740.KS | Veterinary diagnostics and biological materials are sold through distributors and related parties. The large equity-accounted investment may dominate value, but its compo | None/None/None | KRW | RESEARCH_INCOMPLETE | 0 |
| KR | 036530.KS | A pure holding company owns interests in vehicle components, industrial equipment and other manufacturing. Consolidated cash and earnings are not wholly attributable to t | None/None/None | KRW | RESEARCH_INCOMPLETE | 0 |
| KR | 011930.KS | Cleanroom, air-handling and dry-room equipment and installation dominate sales; management also describes data-center cooling expansion. A turnaround depends on project e | None/None/None | KRW | RESEARCH_INCOMPLETE | 0 |
| KR | 281820.KS | Semiconductor CMP and cleaning equipment and materials drive the business; results depend on customer capital spending and delivery timing. Negative operating cash flow w | 22700/34300/51200 | KRW | RESEARCH_INCOMPLETE | 0 |

각 [봉인 판단](../../runtime/task9_3/decisions)에는 미래 실적, 가치평가·주가 기대, 반증 조건, 촉매, 추가 자료 및 비중 이유가 있다. MOH 공식 원문403, BAM Q2/Q3의 HTTP200 오류 페이지는 실제 금융 근거로 사용하지 않았다. 신성이엔지는5월15일 병합과 Q1 주식수/가격의 정합성을 경고했다. 키워드 발견만으로 재무 분석 완료라고 판정하지 않았다. 추가 계산 감사에서 최초 SFM의 명시적 Base FCFE 가정을 연말 할인으로 재구성하면 주당64.54달러인 반면 모델은53달러를 제시했다. Bear26→27.75, Bull91→91.65다. 현금흐름 날짜/stub가 완전히 명시되지 않아 이를 확정 수정 목표가로 쓰지 않으며, 누락 가정과 산술 오류를 분리 확정할 수 없다. **주당가치 계산이 완결됐다고 판정하지 않는다.** 원래 판단·매매·수익률은 그대로 보존했다([가치평가 계산 감사](../../runtime/task9_3/valuation_arithmetic_audit.json)). 단, numeric locator 검증이 완전한 회계 의미·시점별 자본구조 인증을 뜻하지는 않는다. 초기 SFM 금융부채 balance 사실에 period_start가 분기 시작일로 기록된 의미상 메타데이터 오류도 발견했다. 금액·balance 종료일은 같으며 봉인 입력을 수정하지 않고 별도 정정 제안으로 보존했다([의미 감사](../../runtime/task9_3/financial_semantic_warnings.json)).

## 5. 순차 운영·매수·매도·교체

사전에 지정한 월별 연구일과 미국 주요 실적 후4개 추가 연구일을 적용했다. 한국8월17일 휴장은 관측 거래 세션에 맞춰8월18일 연구→8월19일 첫 가능 체결로 이동했다. 미·한 현지 일자와 미국 DST는 분리했다. 완전한 공식 거래소 달력 인증은 미완료이며 실제 관측 지수 세션을 사용했다.

매 거래일 close와 기존25% entry drawdown 규칙을 검사하고 발동하면 다음 적격 open에 처리한다. 같은 날 종가를 보고 같은 종가에 체결하지 않는다. 자료가 없는 mark는 NaN으로 남기고 D-1 평가가 불가하면 `HOLD_ONLY`로 신규 리밸런싱을 차단한다. 운영 Shadow의2.5% 제한을 가져오지 않았다. 정책 cap은 종목25%·총90%·업종50%; 별도 사전 고정 선정 대조군은3종목×30%=90%이며 정책과 같은 종목 cap을 갖는 계좌는 아니다.

| 시장 | 연구일 | 목표 투자 | 현금 | 연구 top3 | 종류 |
| --- | --- | --- | --- | --- | --- |
| US | 2026-05-15 | 현금 | +100.00% | SFM/FLUT/VRT | 실제 Terra 연구 |
| US | 2026-06-15 | 현금 | +100.00% | SFM/FLUT/VRT | 실제 Terra 연구 |
| US | 2026-07-15 | 현금 | +100.00% | SFM/FLUT/VRT | 실제 Terra 연구 |
| US | 2026-07-30 | 현금 | +100.00% | SFM/FLUT/VRT | 실제 Terra 연구 |
| US | 2026-08-06 | 현금 | +100.00% | SFM/FLUT/VRT | 실제 Terra 연구 |
| US | 2026-08-17 | 현금 | +100.00% | SFM/FLUT/VRT | 실제 Terra 연구 |
| US | 2026-09-15 | 현금 | +100.00% | SFM/FLUT/VRT | 실제 Terra 연구 |
| US | 2026-10-15 | 현금 | +100.00% | SFM/FLUT/VRT | 실제 Terra 연구 |
| US | 2026-10-29 | SFM:10.0% | +90.00% | SFM/FLUT/VRT | 실제 Terra 연구 |
| US | 2026-11-02 | 현금 | +100.00% | SFM/FLUT/VRT | 실제 Terra 연구 |
| US | 2026-11-09 | SFM:10.0% | +90.00% | SFM/FLUT/VRT | 실제 Terra 연구 |
| KR | 2026-05-15 | 현금 | +100.00% | 100840.KS/377740.KS/036530.KS | 실제 Terra 연구 |
| KR | 2026-06-15 | 현금 | +100.00% | 100840.KS/377740.KS/036530.KS | DETERMINISTIC_NO_NEW_MODEL_JUDGMENT |
| KR | 2026-07-15 | 현금 | +100.00% | 100840.KS/377740.KS/036530.KS | DETERMINISTIC_NO_NEW_MODEL_JUDGMENT |
| KR | 2026-08-18 | 현금 | +100.00% | 100840.KS/377740.KS/036530.KS | 실제 Terra 연구 |
| KR | 2026-09-15 | 현금 | +100.00% | 100840.KS/377740.KS/036530.KS | DETERMINISTIC_NO_NEW_MODEL_JUDGMENT |
| KR | 2026-10-15 | 현금 | +100.00% | 100840.KS/377740.KS/036530.KS | DETERMINISTIC_NO_NEW_MODEL_JUDGMENT |
| KR | 2026-11-02 | 현금 | +100.00% | 100840.KS/377740.KS/036530.KS | 실제 Terra 연구 |

**정책의 실제 가상 체결 전부:**

| 시장 | 날짜 | 종목 | 방향 | 수량 | 시가 | 비용반영 체결가 | 별도 수수료 | 멱등 ID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US | 2026-11-10 | SFM | BUY | 201 | 49.17 | 49.20 | 0.99 | TASK93-02797d7619f172f1e7a82507 |

조건부 주문의 가격 미충족·보류도 [미국 날짜별 판단](../../runtime/task9_3/evaluation/US/POLICY_daily_actions.json), [한국 날짜별 판단](../../runtime/task9_3/evaluation/KR/POLICY_daily_actions.json)에 기록했다. [미국 일별 현금·수량·NAV](../../runtime/task9_3/evaluation/US/POLICY_nav.csv), [한국 일별 현금·수량·NAV](../../runtime/task9_3/evaluation/KR/POLICY_nav.csv)가 전체 기간을 포함한다. CSV의 기존 `_krw` 필드명은 공용 실행기의 레거시 명칭이며 미국 수치는 USD다.

## 6. 월별 평가금액

| 시장 | 월말/최종일 | 정책 평가액 | 정책 누적 | 지수 누적 | 선정 대조군 누적 |
| --- | --- | --- | --- | --- | --- |
| US | 2026-05-29 | 100,000.00 | +0.00% | +2.23% | -3.67% |
| US | 2026-06-30 | 100,000.00 | +0.00% | +1.14% | +0.98% |
| US | 2026-07-31 | 100,000.00 | +0.00% | +1.01% | -5.95% |
| US | 2026-08-31 | 100,000.00 | +0.00% | +3.66% | -5.93% |
| US | 2026-09-30 | 100,000.00 | +0.00% | +3.19% | -20.08% |
| US | 2026-10-30 | 100,000.00 | +0.00% | +2.23% | -24.59% |
| US | 2026-11-13 | 100,576.66 | +0.58% | +1.98% | -26.76% |
| KR | 2026-05-29 | 10,000,000.00 | +0.00% | +13.88% | -7.21% |
| KR | 2026-06-30 | 10,000,000.00 | +0.00% | +13.88% | -17.09% |
| KR | 2026-07-31 | 10,000,000.00 | +0.00% | -11.39% | -19.46% |
| KR | 2026-08-31 | 10,000,000.00 | +0.00% | -8.37% | -15.15% |
| KR | 2026-09-30 | 10,000,000.00 | +0.00% | -8.13% | -8.58% |
| KR | 2026-10-30 | 10,000,000.00 | +0.00% | -23.01% | -21.49% |
| KR | 2026-11-13 | 10,000,000.00 | +0.00% | -28.92% | -21.07% |

시작일5월18일과 종료일11월13일을 모든 arm에 동일 적용했다. 종료 보유분은 종가 평가이며 가상의 추가 매도 비용을 차감하지 않았다. 정확히6개월 후 미래 세션을 가져온 값이 아니다. 중간3개월 및 종료 checkpoint는 [checkpoint 결과](../../runtime/task9_3/checkpoints.json)에 있다.

## 7. 선정·배분·거래비용·위험 분해

| 시장 | arm | net | gross | 지수100% | MDD | 연환산Sharpe | 체결 | 회전율(단방향) | 평균 주식노출 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US | POLICY | +0.58% | +0.58% | +1.98% | -0.07% | 2.01 | 1 | 0.10 | +0.32% |
| US | SELECTION_EQUAL90 | -26.76% | -26.69% | +1.98% | -31.03% | -2.09 | 33 | 1.65 | +89.50% |
| US | INITIAL_SELECTION_HOLD90 | -28.59% | -28.53% | +1.98% | -31.88% | -2.41 | 3 | 0.89 | +87.81% |
| US | MOM63_POSITIVE90 | -4.43% | -4.03% | +1.98% | -13.46% | -0.24 | 32 | 6.12 | +64.86% |
| KR | POLICY | +0.00% | +0.00% | -28.92% | +0.00% | 미산출 | 0 | 0.00 | +0.00% |
| KR | SELECTION_EQUAL90 | -21.07% | -20.88% | -28.92% | 미산출 | 미산출 | 19 | 1.33 | +89.59% |
| KR | INITIAL_SELECTION_HOLD90 | -23.24% | -23.16% | -28.92% | 미산출 | 미산출 | 3 | 0.90 | +88.13% |
| KR | MOM63_POSITIVE90 | -22.40% | -22.19% | -28.92% | -36.97% | -0.66 | 13 | 2.40 | +36.31% |

`SELECTION_EQUAL90`은 AI가 선택한 top3를 고정된 동일 노출/비용 정책으로 연구일마다 균등 리밸런싱한 **연구 대조군**이다. `INITIAL_SELECTION_HOLD90`은 최초 선정만 유지한다. 두 값의 차이는 선정/리밸런싱 변화의 결합 효과이며 사후 최적 매매와의 비교가 아니다. `MOM63_POSITIVE90`은 각 연구일 적격5종목 중 양수 모멘텀 top3에 각30%이며 부족한 수만큼 현금을 보유한다. native Quanta/RD 성과가 아니다.

| 시장 | arm | 수수료/세금 | spread 가정 비용 | impact 가정 비용 | 동일노출 지수 근사 | 미확정 보유NAV일 | 배당 경제적 권리 민감도 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| US | POLICY | 0.99 | 4.94 | 0.31 | +0.05% | 0 | 0.00 |
| US | SELECTION_EQUAL90 | 16.54 | 82.68 | 5.02 | +1.84% | 0 | 11.21 |
| KR | POLICY | 0.00 | 0.00 | 0.00 | +0.00% | 0 | 0.00 |
| KR | SELECTION_EQUAL90 | 5,934.03 | 6,651.11 | 2,581.76 | 미산출 | 1 | 93,500.00 |

미국 매수/매도 수수료1bp씩+halfspread5bp, 한국 매수1.5bp/매도21.5bp+halfspread5bp, ADV 참여율 기반 impact5~30bp를 사전 고정했다. 실제 호가나 거래소별 세금 원장을 완전 재현한 비용이 아니다. 지수 추가 대사에서 KOSPI의 실제 진입 시가·최종 종가와124개 종가는 Toss/Yahoo가 일치했다. 일부 다른 날짜 시가는0.72% 차이가 있어 별도 기록했다. 미국 S&P500은 Yahoo 단일 공급자 계산이며 Toss SP500 지표가 지원되지 않아 독립 교차 검증은 미완료다([지수 대사](../../runtime/task9_3/benchmark_return_audit.json)). 기존 지수 값·기간은 바꾸지 않았다. 지수는 가격지수 gross이며 주식도 주된 비교는 배당 제외 가격 수익이다. 배당은 지급일이 확인되지 않아 기본 현금·재투자에 섞지 않고 별도 ex-date 경제적 권리 민감도로 보존했다. Total Return 우위를 주장하지 않는다.

동일 노출 지수는 전일 실현 주식노출을 다음 close-close 지수 수익률에 적용한 **근사적 기여도 계산**이며 실제 체결 시각까지 일치하는 정밀 인덱스 계좌는 아니다. 대조군90%는 목표 비중으로, D-1 sizing·미체결·가격 변동 때문에 종가 실현노출과 다르다. 한국 선정 대조군의 최대 종가 노출은92.35%였다([노출 감사](../../runtime/task9_3/risk_exposure_audit.json)); 일정 노출/하드 한도를 매일 충족한 실험으로 표시하지 않는다. 소수 거래/대부분 현금 계좌의 연환산 Sharpe를 통계적으로 안정적인 우위로 해석하지 않는다.

종목별 비용 포함 손익 기여는 [미국 결과](../../runtime/task9_3/evaluation/US/results.json), [한국 결과](../../runtime/task9_3/evaluation/KR/results.json)에 있다. 정책과 대조군의 매매·종목 변경은 각 `_fills.csv`, `_targets.csv`, `_daily_actions.json`으로 전부 재생 가능하다.

## 8. 정보 사건·예측·가치평가의 한계

[주별 관측](../../runtime/task9_3/weekly_observations.json)은 해당 시점에 이미 발표된 수집 범위 내 문서만 열거한다. 모든 역사 뉴스·수주·공시·수급·컨센서스를 포괄하지 않는다. 한국 일부 월은 새 LLM 판단을 만들지 않고 기존 thesis/weights를 유지한 결정론적 관측이다. 중요한 사건에 항상 즉시 반응하는 완전한 운영 dispatcher를 검증한 것은 아니다.

원문 수치와 가정/전망은 입력·출력에서 분리했다. 연간 FY 전망을 임의의 H1/Q3 실제값과 비교하지 않았다. 실현값과 단위·기준·회계기간을 맞출 수 없어 미래 실적 예측은 [PENDING 원장](../../runtime/task9_3/forecast_status.json)으로 남겼다. 단순 guidance 반복은 독립 예측 성공이 아니다. 주가 하락만으로 실적 예측 실패를 확정하지 않았다.

한국은 Yahoo/Toss/Naver 일별 시가·종가 각각의2공급자 합의 값을 사용한다. 공급자 다수결은 거래소 원본 인증이 아니다. SNT홀딩스10월12일 종가 미합의는 보간하지 않았다. 그 날 실제 보유한 대조군의 MDD/Sharpe는 미산출이다. 신성이엔지1:10 병합은 첫 가능 체결 이전이어서 보유 수량을 소급 바꾸거나10배 수익을 만들지 않았다. 당시 주식수·희석·리스의 불완전성은 연구 신뢰도를 제한한다.

## 9. 실패 원인과 독립 복기

- **US:** 정책 +0.58%, 선정 -26.76%, 지수 +1.98%. Selected basket underperforms index at fixed90%exposure. 리밸런싱/선정 갱신−최초 유지 차이 +1.83%, 선정 gross→net 차이 +0.07%.
- **KR:** 정책 +0.00%, 선정 -21.07%, 지수 -28.92%. Selected basket outperforms90%index in this diagnostic only. 리밸런싱/선정 갱신−최초 유지 차이 +2.17%, 선정 gross→net 차이 +0.19%.

확인된 것은 종목 선택/현금/비용의 **회계적 기여**, 원문/자본구조/표본의 결손 및 명시 가치평가 가정으로 모델 주당가치를 재현하지 못한 사례다. Task9.2의 날짜가 명시된 native 계산 gate가 이번 모든 모델 출력에 일관되게 강제되지는 못했다. 추후 모든 후보의 수치 가치평가를 계산 코드로 재현한 뒤 판단하도록 보완해야 하며, 이번 결과를 정상화 완료로 표시하지 않는다. 이를 해당 현금 판단이 사전적으로 비합리적이었다는 원인 확정으로 바꾸지 않는다. 연구 엔진 자체 한계·예측 실패·최적 타이밍은 `UNDETERMINED` 또는 정합 실제 실적 대기다. 제한된 탐색과 반복된 미국 후보가 기회 발굴을 좁혔을 가능성은 있지만 사후 최고 상승 종목을 정답으로 넣어 재실험하지 않았다.

기존 `process_review`로 사후 수익 접근 없이 과정 복기를 먼저 봉인했다. 이후 결과를 별도 Queue 작업이 읽어 원인 분해→후속 연구 요청으로 연결했다. 버그/자료 품질, 예측, 선택, 비중, 실행을 구분하며 과거 성과에 맞춰 임계값을 변경하지 않았다.

Factory 실제 상태: **BLOCKED**, `Factory daily experiment budget exhausted before execution`. 공식 등록·예약 계약을 호출했으며 예산을 우회하지 않았다. [공식 결과](../../runtime/task9_3/feedback.json)와 [제안](../../runtime/task9_3/factory_proposal_v2.json)을 보존했다. 입력 사실 검산용 실험과 투자 성능 검증은 별개다. 독립 심층 회사10개는 기존 최소12개를 충족하지 못한다. 공식 등록은 별도 [등록 확인](../../runtime/task9_3/factory_registration_observation.json)으로 확인했다. 후속 연구 Queue 요청을 만들었으나 새 Task93 kind의 자동 운영 dispatcher는 지원하지 않아 자동 재실행 완료로 표시하지 않는다.

## 10. 검증·재현·보존

| 실제 실행 | tests | failures | errors | skips |
| --- | --- | --- | --- | --- |
| unit_tests_final.xml | 8 | 0 | 0 | 0 |
| safety_tests_final.xml | 53 | 0 | 0 | 0 |
| ops_tests.xml | 32 | 0 | 0 | 0 |

```bash
.venv/bin/python experiments/task9_3/run_sequence.py
.venv/bin/python experiments/task9_3/process_reviews.py
.venv/bin/python experiments/task9_3/evaluate.py US KR
.venv/bin/python experiments/task9_3/observe_history.py
.venv/bin/python experiments/task9_3/audit_inputs.py
.venv/bin/python experiments/task9_3/prepare_followup.py
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q experiments/task9_3/test_replay.py
```

모델 재현에는 archived output/request/hash를 먼저 사용한다. 완료된 결정을 재호출하거나 전체 실험을 새 독립 결과로 세지 않는다. 초기 누락 timestamp, KR screening 초대형 요청 거절(실제모델호출 전), HTTP403, HTTP200 오류 페이지, 휴장일 검출 실패를 로그로 보존했다. 성공한 수정본과 구분한다.

[진행 기록](09_3_progress.md), [증거 manifest](../../runtime/task9_3/artifact_manifest.json), [입력 시점 감사](../../runtime/task9_3/input_audit.json), [검증 요약](../../runtime/task9_3/verification.json), [이전 원장 보존](../../runtime/task9_3/prior_preservation.json), [DB 보존](../../runtime/task9_3/persistence.json), [추가 가치평가 복기·백업](../../runtime/task9_3/persistence_supplement.json)을 참조한다. 실제 재부팅·실브로커 주문·신규 전략 승격은 실행하지 않았다.

원문·요청·응답·로그 해시를 확인한 뒤 이번 작업의 임시 relay/socket/worker 폴더와 시험 복제본만 정리했다. 완료된 `run_sequence.py`는 이미 봉인된 단계에서 모델 없이 종료한다. 기존 환경·오픈소스 checkout·과거 연구·운영 데이터는 보존했다([정리 기록](../../runtime/task9_3/cleanup.json)).

## 11. 남은 우선순위

1. 미국의 제한된 탐색/반복 후보를 개선하되 당시 산업·사업 변화를 검증할 수 있는 새 표본과 독립 Forward로 평가한다. 현재 소수 선정의 실패를 native Quanta/RD 알고리즘의 실패로 확정하지 않는다.
2. 자료 부족 기권과 검증된 가격 매력 부족을 계속 구분한다. 현금흐름 end_date/stub와 native 가치평가 계산 gate를 우선 복구하고, 자본구조·미래 재투자·실적 가정의 source별 의미를 검산하고 조건부 가치평가를 투자 확신으로 부풀리지 않는다.
3. 모든 시장의 실제 체결 후 계좌 상태를 연구 입력에 일관되게 반영하고, 계좌 인지·진입/청산·새 기업 대안의 증분 효용을 별도 사전등록한다.
4. 완전한 가격/기업행사·배당 지급일·시점별 업종/수급/컨센서스 자료와 정합 실적 actual을 확보한 범위에서 평가를 확대한다. 미확정 가격을 보간하거나 전체5년 데이터베이스를 먼저 만들지 않는다.
5. 공식 Factory 예약과 후속 worker를 정상 예산에서 이어가고, 역사 진단의 개선 후보를 새 Forward와 사람 승인 전에는 운용 전략에 적용하지 않는다.

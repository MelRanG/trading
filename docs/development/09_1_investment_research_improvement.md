# Task 9.1 — 투자 후보·비중 판단 개선 및 복기 실증

## 핵심 결론

**기술 연결은 작동했지만 일반적인 투자 판단 개선·초과수익은 입증하지 못했다(PARTIAL).** 신규 역사 시점 두 개에서 미국30/25·한국20/20 후보를 탐색하고, 미국5/5·한국4/4를 심층 입력으로 사용했다. 실제 Terra5회, 원본 Vibe ChatLLM 컴포넌트를 격리 실행했다. 전체 Autopilot·자율 웹 탐색·QuantaAlpha/RD-Agent 역사 신호의 성공으로 해석하지 않는다.

종목 선정과 비중 결정을 분리했다. 2025년 선정 종목의 12개월 동일노출 수익률은 미국 **-43.16%**(S&P500 **+20.88%**), 한국 **+197.93%**(KOSPI **+178.07%**). 추가로 같은 선정 종목의 비중을 물은 AI 연구 정책은 미국35%·한국30% 주식 노출, 각각 **-14.47% / +58.05%**였다. **현금을 줄이는 것이 언제나 개선이라는 결론은 성립하지 않는다.** 미국은 선정 실패가 큰 문제였고, 한국은 현금 기회비용이 컸으나 동일노출 지수+현금 대비로는 양의 기여가 있었다.

한국 수치는 **확인된 진입·청산 가격의 제한적 buy-and-hold 산술**이다. 일부 일별 원문 가격 불일치 때문에 완전한 일별 NAV·MDD·Sharpe는 차단 상태를 유지한다. 이 수치를 완전한 역사 Paper 재현이나 독립 Forward 우위로 표시하지 않는다. 실제 기업 수치 예측은 이번 호출에서 생성되지 않아 신규 예측 정확도는 평가하지 못했다.

기존 Review18개 과정평가를 결과 접근 전에 봉인했다. 실제 연구 Queue에서 원인 판정→후속 요청→고정60% 후보의2025년 별도 평가를 실행하고 재실행 시 중복 처리가 없음을 확인했다. 공식 Factory는 오늘 제안3/3·실험1/1 예산 소진으로 **BLOCKED_REGISTRATION**이다. 우회하거나 공식 실험 성공으로 표시하지 않았다. Task8b Forward 계획2개·타이머를 확인했으며 기존 계좌는 현금·체결0 상태였다. 운영 전략·원장·Live 설정은 변경하지 않았다.

## 1. 기존 부진의 원인과 이번 변경

| 원인 | 실제 근거 | 판정·수정 범위 |
| --- | --- | --- |
| 미국 후보·선정 | 과거 고정 Dow 후보 및 소수 반복 심층 기업; INTC/DOW 실적 예측 오차 | 후보 편향 가능성, 엔진 자체 한계 확정 불가. 당시 FTSE 신규 편입·기업 변화 후보로 신규 시점 실험 |
| 한국 현금 | 기존 선정+50.68%와 정책+1.74%의 차이; 본 연구의 동일 basket 배분 대조 | 기회비용은 관측 가능, 사전 판단 오류 여부는 별도. 고정노출을 운용에 강제하지 않음 |
| 입력 누락 | 로컬 원문에 있었지만 요약에 빠진 자본·현금흐름 등 키워드 사례 | 원문→입력 전달 문제를 확인. 정확한 원문 구간을 복원한 V2 후보 생성; 재LLM 효능 검증은 대기 |
| 현금 답변의 해석 | 첫4회는 screen-first3 조건부 배분; 최종 선정 top3와 다른 집합 | 이 계약 차이를 발견해 보존. 2025 최종 선정 집합만 따로 비중 질의1회 추가; 기존 현금 결과를 덮어쓰지 않음 |
| 가격·시점 | CVNA Yahoo 과거 명목가격이 Toss와5배 차이; 한국 평가 시점 원문 가격 불일치 | 모델에는 당시 Toss 명목가격 사용. 가격 단위·전체 일별·endpoint 진단을 구분; 불확실한 가격을 보간하지 않음 |
| 수치 예측·가치평가 | 기존 연간 EPS 예측 오차·회사 가이던스 반복 사례; 이번 신규 forecast0건 | 정량적 투자 매력 연결 미완성. 가이던스를 독립 예측으로 계산하지 않음 |

기존 +8.72% / +50.68%는2021~23년 세 구간의 연쇄 결과다. 아래 신규 구간과 기간·후보가 달라 직접적인 개선률로 비교하지 않는다. 과거 결과·threshold·비용·원장은 수정하지 않았다.

## 2. 신규 후보와 동일 조건

연구일은2024-11-29·2025-06-30 23:00UTC. 다음 실제 가격 세션 시가로 진입하고3/6/12개월 후 첫 관측 세션 시가로 청산했다. 이 날짜·비용·비중 정책은 결과 수집 전에 계약에 남겼다. 2025 FTSE 문서는6월13일 발행이므로5월 연구 입력으로 사용하지 않았다.

- 미국: [2024 FTSE 원문](https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/2024-russell-recon-recap-preliminary.pdf), [2025 FTSE 원문](https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/2025-russell-recon-recap-final.pdf)의 명시 기업. 신규 편입 예시+상위기업+style 변화의 한정 집합, 전체 역사 유니버스가 아니다.
- 한국: [DART 공시검색](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001)의 당시 분기보고서. 최초 혼합시장 탐색은 소형주 편향·현재 상장 구분 문제가 있어 가격·수익 확인 전에 유가증권시장 소스로 수정한 기록을 보존했다. 실제 과거 거래가격 및 당시 공개 주식수×가격의5000억원 이상 proxy를 요구했다. 수정 API가 미래 accession이면 배제하고 원문으로 복원했다. 일부2025 주식수는 당시 공개된 전년도 연간 보고서 proxy다.
- 가격63세션 momentum/volatility, 원문·receipt·V87 revision gate 보존. 전종목5년 DB·새 DB·상시 서비스를 만들지 않았다.
- 분야가 확인된 미국 후보는 source-order에서 업종을 분산해5개, 한국은 size 적격4개만 심층 처리했다. 한국 업종은 screen 당시 UNVERIFIED로 두었으며 검증된 GICS 위험 한도라고 주장하지 않는다.
- 공통 심층 집합에서 value / market-relative / MOM63 순위 / 통합 순위를 비교한다. 실제 Vibe 현재형 screener는 역사 as-of를 지원하지 않아 과거 시장 탐색 성공으로 사용하지 않았다.
- QuantaAlpha·RD-Agent의 봉인된2024/25 적격 신호가 없으므로 해당 원본 엔진의 역사 투자 성과는 **N/A**. 아래 quant는 기존 MOM63 방식의 인과적 가격 재구성이다.
- 미국 buy/sell6bp, 한국6.5/29.5bp 고정 가정. 한국의 실제 연도별 세금·호가 비용을 완전히 재현한 값은 아니다. 가격지수와 주식 가격 수익률을 비교하며 배당·세후 Total Return 우위가 아니다. ETF는 투자 대상에 넣지 않았다.

| 시점 | 시장 | 탐색 | 심층 | 실제 심층 입력 기업 | market-relative 선정 top3 |
| --- | --- | --- | --- | --- | --- |
| 2024-11-29 | US | 30 | 5 | Super Micro(SMCI), Carvana(CVNA), Permian Resources(PR), Comfort Systems(FIX), CRH(CRH) | CRH, PR, FIX |
| 2024-11-29 | KR | 20 | 4 | LS에코에너지(229640.KS), 화승엔터프라이즈(241590.KS), 카카오(035720.KS), 코스모신소재(005070.KS) | 241590.KS, 229640.KS, 035720.KS |
| 2025-06-30 | US | 25 | 5 | Summit Therapeutics(SMMT), Sprouts Farmers Market(SFM), Aurora Innovation(AUR), Brookfield Asset Management(BAM), Flutter(FLUT) | SFM, BAM, FLUT |
| 2025-06-30 | KR | 20 | 4 | NICE평가정보(030190.KS), 서울보증보험(031210.KS), LS에코에너지(229640.KS), LG이노텍(011070.KS) | 030190.KS, 011070.KS, 229640.KS |

심층 총18기업-시점이며 LS에코에너지가 두 번 포함된다. 원문 접근 실패가 있었던 FIX는 공식 PDF의 제한적 browser 추출 수치만 제공했고, SMMT 원문 다운로드 실패는 그대로 남겼다. 심층 입력18건을18건의 완전한 기업가치 검증 성공으로 세지 않는다. 공통 foundation hash와 실제 요청 hash·모델 사용량을 각각 보존했다.

## 3. 종목 선택의 비교

모두 연구용 동일100% 주식 노출·균등 비중·같은 보유기간과 비용이다. `SELECT_QUANT_RANK100`은 과거63세션 순위 top3, 양수 여부와 별개인 선택 능력 대조군이다. 원래 양수 gate는 `QUANT_RULE_POSITIVE`에 별도로 보존하며 두 arm 모두 실제 운용 수익률이 아니다. 통합은 사전 고정한 LLM 순위+quant 순위의 동등 Borda 결합이다.

| 시점 | 시장 | Value | Market-relative | MOM63 순위 | 통합 | 심층 전부 균등 | 지수 | 검증 수준 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-11-29 | US | +35.28% | +35.28% | +52.58% | +35.28% | +27.87% | +13.09% | 일별 NAV 제한검증 |
| 2024-11-29 | KR | -4.29% | +17.69% | +17.69% | +17.69% | +8.40% | +58.90% | endpoint 산술만 |
| 2025-06-30 | US | -43.16% | -43.16% | -43.16% | -43.16% | -25.88% | +20.88% | 일별 NAV 제한검증 |
| 2025-06-30 | KR | +197.93% | +197.93% | +10.91% | +197.93% | +147.63% | +178.07% | endpoint 산술만 |

시장 정보가 선정 **집합**을 바꾼 것은2024년 한국의 코스모신소재→카카오 교체다. 해당 한 번의12개월 계산에서 **-4.29%→+17.69%, +21.98%p**였다. 미국2024는 순서만 달라 균등 비중 결과는 같았고2025년 두 시장도 선정 집합은 같았다. 통합 순위는 이번4개 시장-시점에서 market-relative와 같은 집합이어서 증분 수익0이었다. 반복 호출·동일 난수 통제가 없어 이 차이를 매크로 정보만의 인과적 효과로 확정하지 않는다.

| 연구일 | 시장 | 개월 | Market-relative | MOM63 순위 | 지수 |
| --- | --- | --- | --- | --- | --- |
| 2024-11-29 | US | 3 | -11.58% | -11.85% | -1.19% |
| 2024-11-29 | US | 6 | -10.96% | +2.90% | -2.37% |
| 2024-11-29 | US | 12 | +35.28% | +52.58% | +13.09% |
| 2024-11-29 | KR | 3 | +24.65% | +24.65% | +1.74% |
| 2024-11-29 | KR | 6 | +12.22% | +12.22% | +8.63% |
| 2024-11-29 | KR | 12 | +17.69% | +17.69% | +58.90% |
| 2025-06-30 | US | 3 | -13.64% | -13.64% | +7.72% |
| 2025-06-30 | US | 6 | -26.62% | -26.62% | +11.17% |
| 2025-06-30 | US | 12 | -43.16% | -43.16% | +20.88% |
| 2025-06-30 | KR | 3 | +6.19% | +6.59% | +11.47% |
| 2025-06-30 | KR | 6 | +27.65% | +5.54% | +36.73% |
| 2025-06-30 | KR | 12 | +197.93% | +10.91% | +178.07% |

미국 market-relative의 일별 관측 MDD는2024 구간 **-32.84%**,2025 구간 **-50.23%**였다. 같은12개월 gross→net 비용 차이는 약0.16%p /0.07%p여서 이 표본의 수십%p 선택 차이를 거래비용 하나로 설명할 수 없다. 한국은 일부 일별 mark 불일치로 MDD·Sharpe를 채점하지 않았다. 업종 중립·정밀 가치/성장 스크리너에 필요한 역사 적격 자료는 부족하여 해당 기준선은 미검증이다.

## 4. 고정 종목의 비중·현금 판단

첫4회 호출은 심층 screen의 첫3개만 배분하도록 질문했다. 이는 최종 AI 선정 집합과 다를 수 있으므로 결과를 `ALLOC_*` 조건부 연구로 보존했다. 이 결과의 현금100%를 자유로운 최종 투자 정책으로 해석한 것은 잘못이다. 이를 바로잡아2025년의 실제 market-relative 선정 top3를 고정하고 비중만 다시 질문했다. 추가 호출은 결과를 보지 못했지만 담당자는 이미 역사 readout을 본 뒤이므로 **새 독립 holdout 검증이 아닌 설계 교정 진단**이다. 이 한 호출에서도 다른 연구일의 자료를 섞지 않았다.

- US: SFM 15.0%, BAM 12.0%, FLUT 8.0%; 현금 65.0%.
- KR: 030190.KS 12.0%, 011070.KS 10.0%, 229640.KS 8.0%; 현금 70.0%.
| 시장 | 고정 선정 종목 정책 | 초기 주식노출 | 12개월 net | 지수100% | 동일노출 지수+현금 gross | 대조군 대비 net |
| --- | --- | --- | --- | --- | --- | --- |
| US | SELECTED_EQUAL100 | +100.00% | -43.16% | +20.88% | +20.88% | -64.04% |
| US | SELECTED_FIXED60 | +60.00% | -25.90% | +20.88% | +12.53% | -38.43% |
| US | SELECTED_VIBE_IVP60 | +57.22% | -24.15% | +20.88% | +11.95% | -36.10% |
| US | SELECTED_AI | +35.00% | -14.47% | +20.88% | +7.31% | -21.77% |
| KR | SELECTED_EQUAL100 | +100.00% | +197.93% | +178.07% | +178.07% | +19.85% |
| KR | SELECTED_FIXED60 | +60.00% | +118.79% | +178.07% | +106.84% | +11.94% |
| KR | SELECTED_VIBE_IVP60 | +48.98% | +82.96% | +178.07% | +87.23% | -4.27% |
| KR | SELECTED_AI | +30.00% | +58.04% | +178.07% | +53.42% | +4.62% |

원본 Vibe `agent/src/quantlib/portfolio.py:inverse_variance_weights`를 실제 호출해 과거63세션 공분산으로 계산했다. 목표60% 후 단일종목20%를 넘는 부분은 재분배하지 않고 현금으로 두어 실제 노출은60% 미만일 수 있다. Quant `investment/portfolio.py:aggregate`는 기존 위험 preview/차단기로 재사용했으며 새 최적화기라고 표현하지 않는다. 100% 동등노출 대조군은 현 운용 위험 한도를 충족하는 Paper 전략이 아니다.

한국 AI정책은 전체 지수100%에는 크게 뒤졌지만 노출을 맞춘 지수+현금 대조군보다 높았다. 미국 AI정책은 노출을 맞춰도 부진했다. 따라서 한국의 현금을 무조건 줄이거나 미국에도 같은 비중 규칙을 강제하지 않는다. 이 가상 배분은 공식 Paper 적격성·가치평가 검증을 통과한 전략이 아니다. 실제 브로커/Paper 주문은 생성하지 않았다.

## 5. 가격·PIT 신뢰도와 남은 검증

- 과거 자료는2026년에 재조회한 것이며 과거 최초 수집 원본으로 표시하지 않았다. 상장폐지 포함 전체 PIT 유니버스, 당시 컨센서스·기관 순매수·기업행사 완전성은 확보하지 못했다. 현대 LLM의 역사 지식도 배제할 수 없다.
- 원본 수집의 Toss pagination 경계가 inclusive여서 같은 날짜가 반복됐다. 처음 실패한 `receipt.json`을 보존하고, OHLCV가 동일한 중복만 병합한 `receipt_v2.json`을 별도로 생성했다. 충돌한 중복은 차단하는 재현 시험을 추가했다. 새 API 재호출로 실패를 감추지 않았다.
- 한국의 일부 Toss/Yahoo 가격 불일치는 Naver 공개 원문으로 대조했다. Naver 실제 한 bar를 그대로 쓰고 각 필드가 Yahoo/Toss 중 적어도 한 출처와0.5% 내 일치해야 하는 V3 진단을 별도 보존했다. Yahoo2025-09-19 일부 종목은 OHLC가 모두 결측이었고 나머지 출처의 일부 필드도 불일치해 **전체 일별 NAV는 계속 차단**했다. 정규장/확장장·거래소 범위 차이 가능성은 있지만 제공자 의미를 완전히 확정하지 못했다.
- 대신 모든 선정 종목의 실제 진입·청산 **시가**에 Naver/Yahoo 일치를 요구하고, 해당 구간 선언 split이 없는 경우에만 endpoint 수익률을 계산했다. 하나라도 빠지면 전체 선택 바스켓을 차단하고 생존 종목으로 재정규화하지 않는다. 중간 가격을 보간하거나 endpoint를 연결한 Sharpe/MDD를 보고하지 않는다.
- 미국 역시 완전한 기업행사·세후 TR·공식 거래소 달력 감사가 아닌 공개가격 재구성(PARTIAL)이다. 배당 누락이 지수/종목에 동일한 경제적 영향을 준다고 가정하지 않는다.
- 시점은 새 두 개지만 구간이 일부 겹친다.4개 시장-시점이나 반복 horizon은12개 독립 기업/실험 성공 표본이 아니다.5년 연속 자율 운용·새 Forward 우위로 승격하지 않는다.

## 6. 실제 복기→후속 연구→별도 평가

1. 원본 Review `process_review`로18개 과정평가를 미래 수익 접근 전에 봉인. source 실패/trace·위험 계약만 검증하며 경제적 정답을 아는 oracle로 취급하지 않음.
2. 2024년 평가를 읽은 규칙형 adapter가 선택 부진, 현금 기회비용, 데이터 차단을 분리. 손실=오판으로 단정하지 않고 원인 확신을 `MECHANICAL_ACCOUNTING_ONLY / UNDETERMINED`로 남김.
3. 고정60% vs AI 조건부 현금의 **동일 screen-first3 바스켓** 후속 후보를2025년 readout 전에 봉인하고 기존 PostgreSQL Queue에 등록.
4. `run_followup.py`가 lease를 claim하고 두 시장3/6/12개월의 후보를 실제 재계산·저장·DONE 처리. 같은 job 재실행은 `NO_RECLAIM_COMPLETED_OR_WAITING_JOB`. 해당 후속 후보는 최종 선정 top3 배분 실험과 다른 집합임을 보존.
5. 공식 Factory 등록은 정상 예산 검사에서 차단. 분리된 pytest 임시 registry에서만 같은 등록→예약→결과·중복/일일 budget 차단 계약을 검증. 이를 운영 등록·예약·실험으로 세지 않음.

| 후속 시장 | 원래 고정 screen 바스켓 | AI 조건부 | 고정60% 후보 | 판정 |
| --- | --- | --- | --- | --- |
| US | SMMT, SFM, AUR | +0.00% | -9.63% | HISTORICAL_DIAGNOSTIC_ONLY_NOT_ADOPTED |
| KR | 030190.KS, 031210.KS, 229640.KS | +0.00% | +6.55% | HISTORICAL_DIAGNOSTIC_ONLY_NOT_ADOPTED |

후속 결과는 한쪽 시장에서는 개선, 다른 시장에서는 악화했다. 예산·표본 계약을 유지해 결과는 `INSUFFICIENT_EVIDENCE`, 승격 없음이다. 공식 등록 재시도 job은 다음 UTC일 이후로 저장했지만 기존 Operations가 새 Task91 job kind를 자동 실행하는 dispatcher는 아직 없다. 예약 시각을 저장한 것과 실제 자동 집행을 구분한다.

입력 누락 후속 후보도 구현했다. 18개 입력 중9개에서 키워드 기반 전달 누락이 발견됐고, 로컬 원문을 확보한16개에 대해 주식수·부채·현금흐름·이익의 실제 원문 구간을 문자 offset/hash와 함께 복원해 기존 요약과 대조했다. 이는 키워드/원문 구간 검증이며 정량 가치평가 충분성 판정은 아니다. 이는 자료 전달 수정을 검증한 것이며 해당 강화 입력으로 예측·수익이 개선되는지는 이번5회 budget 안에서 재검증하지 않았다. 새로운 수치 예측이0건이므로 예측 오차·valuation calibration은 N/A이며 다음 우선 과제다.

## 7. Forward·지속성·안전

기존 계획 2개, 타이머 `active`, 계좌 [{"market": "us", "initial": "100000", "cash": "100000", "fills": 0}, {"market": "kr", "initial": "10000000", "cash": "10000000", "fills": 0}]. 모두 읽기 전용으로 확인했다.

새 관측 계획은 과거 선정 기업을 모니터링 대상으로 봉인하되 `PENDING_FRESH_ASOF_COMPANY_RESEARCH`다. 과거2025년 가설을 현재 투자 신호로 재활용하지 않는다. 새 실적·가격·부채/희석·가치평가 자료와 새 판단을 확보하기 전 진입을 비활성화했다. 이후 적격 진입이 생겨야1/3/6개월 Forward 시계가 시작된다. 기존 Task8b 계획·계좌·주문 경로는 유지했다. 실제 서버 재부팅은 수행하지 않았다.

전용 기존 역사 연구 PostgreSQL에 결과19개를 append하고 읽기 검증했다. 원인·후속·Forward 작업은 기존 Queue에 보존했으며 DB dump/hash를 남겼다. 운영 DB·Paper 원장·Live hardlock에 쓰기를 하지 않았다.

## 8. 사용량·테스트·재현

실제 모델 `gpt-6.1-terra`, 5회 모두SUCCEEDED; 입력+출력 합계 **269884 tokens**, 8832 cached input tokens 포함. 총360000 token 한도 이내. 최초4회 정책에 최종 선정 비중 범위 교정을 위한1회를 별도 amendment로 추가했으며 총 token cap은 늘리지 않았다. 구독 호출이라 현금 단가/금액은 `null`이고0원으로 단정하지 않는다. CLI의 신뢰 가능한 hard token cap은 없어 호출 전 최악90k 여유를 예약하고 측정 후 guard한다. 비용이 다른 stage의 quota로 숨겨지지 않도록 추가 scope도 총합으로 검사했다.

- 신규 연구/격리 Factory/가격 복구 시험 **12 PASS**; 기존 필수 안전 회귀 **24 PASS**. 최초 pagination 실패18건·FIX/SMMT 원문 실패·전체 일별 가격 차단은 통과로 바꾸지 않음.
- `compileall src scripts tests experiments/task9_1` 통과. 운영 경로를 바꾸지 않아 전체 운영 시험을 불필요하게 재실행하지 않았음.
- Vibe 원본 ChatLLM·valuation/earnings/sector/macro skill 방법 일부와 원본 IVP를 재사용. QH Store/Queue/Review/Factory/metrics/portfolio 및 Task9 notional evaluator를 재사용. 새 백테스터/서비스 없음.

재현(저장 자료만 평가; 모델/외부 수집 재실행은 trace와 budget을 먼저 점검):

```bash
.venv/bin/python experiments/task9_1/evaluate.py 2024-11-29
.venv/bin/python experiments/task9_1/evaluate.py 2025-06-30
.venv/bin/python experiments/task9_1/evaluate_v3.py 2024-11-29
.venv/bin/python experiments/task9_1/evaluate_v3.py 2025-06-30
.venv/bin/python experiments/task9_1/evaluate_endpoint.py
.venv/bin/python experiments/task9_1/evaluate_selected_allocation.py
.venv/bin/python experiments/task9_1/run_followup.py
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q experiments/task9_1/test_protocol.py
```

보존된 요청/응답 기준 수집량: Yahoo117, Toss54, DART74, Naver8 GET; 미국 원문11·정책문서4·FTSE2 시도. 실패 원문과 최초 차단 결과도 보존했다. 외부 제공자 결제 telemetry가 아닌 파일 기반 호출 집계다.

핵심 근거:

- [experiments/task9_1/contract.json](../../experiments/task9_1/contract.json)
- [experiments/task9_1/allocation_amendment.json](../../experiments/task9_1/allocation_amendment.json)
- [runtime/task9_1/decision_seals.json](../../runtime/task9_1/decision_seals.json)
- [runtime/task9_1/selected_allocation_seal.json](../../runtime/task9_1/selected_allocation_seal.json)
- [runtime/task9_1/blinded_process_reviews.json](../../runtime/task9_1/blinded_process_reviews.json)
- [runtime/task9_1/evaluation_endpoint/portfolios.json](../../runtime/task9_1/evaluation_endpoint/portfolios.json)
- [runtime/task9_1/selected_allocation/portfolios.json](../../runtime/task9_1/selected_allocation/portfolios.json)
- [runtime/task9_1/followup_result.json](../../runtime/task9_1/followup_result.json)
- [runtime/task9_1/factory_handoff.json](../../runtime/task9_1/factory_handoff.json)
- [runtime/task9_1/factory_retry.json](../../runtime/task9_1/factory_retry.json)
- [runtime/task9_1/persistence.json](../../runtime/task9_1/persistence.json)
- [runtime/task9_1/forward_check.json](../../runtime/task9_1/forward_check.json)
- [runtime/task9_1/protocol_tests_final.log](../../runtime/task9_1/protocol_tests_final.log)
- [runtime/task9_1/safety_tests.log](../../runtime/task9_1/safety_tests.log)
- [runtime/task9_1/source_versions.json](../../runtime/task9_1/source_versions.json)
- [runtime/task9_1/api_usage.json](../../runtime/task9_1/api_usage.json)
- [runtime/task9_1/credentials_scan.json](../../runtime/task9_1/credentials_scan.json)

## 9. Task9 후속·Task10 우선순위

1. **완전한 기업가치 입력**: 원문 전달 coverage 수정부터 적용하고, net debt·희석·per-share 청구권·현금흐름과 현재 가격을 잇는 최소 필드를 확보한 후 제한적 재연구. Null 예측을 억지 숫자로 채우지 말 것.
2. **미국 선택 실패**: 성장률만으로 expensive growth를 선호하지 않도록 가격 내재 기대·하방 시나리오를 실제 근거로 검증. 후보 확대/새 자료/프롬프트 변경을 각각 분리한 후속 실험. 이번2025 하락 종목의 사후 대체 우승주를 찾는 최적화 금지.
3. **비중·현금**: 선택 품질, 투자 적격성, 실제 배분 질문의 계약을 먼저 정리. 같은 선정 집합에서 노출/가중 효과를 분리하고 기권 사유를 추가 자료 부족/부정적 기대수익으로 구별. 현재 검증만으로 노출을 올리지 말 것.
4. **한국 가격 의미**: 제공자별 거래소·정규/확장장·기업행사 의미 및 일별 결측을 확인. 완전한 MDD/Sharpe·매매 타이밍 검증이 끝나기 전 endpoint 수익률을 완전 재현으로 승격하지 말 것.
5. **실제 Forward**: 신선한 기업 연구를 새로 봉인하고 성숙한 실적 예측·가격 결과를 독립 수집. 새로운 후보 Queue의 운영 dispatcher 및 공식 Factory 정상 재시도는 대기 과제. 반복 horizon을 독립 표본으로 세지 말 것.

최종 판정: **신규 역사 선택/비중 진단·연구 Queue 최소 복기 경로 PASS, 공식 Factory 신규 실행 BLOCKED, 기업 예측/일반적 투자 개선/새 Forward 우위 미입증(PARTIAL)**.

# Task9 투자 유용성 검증 진행

2026-11-14. 사용자 방향수정:자료/엔진기능을투자실력성공으로판정안함. 전종목DB불필요,시총제한유지,두시장20~50후보/다양산업→소수심층→실제정책/동일노출선정품질분리→다중시점3/6/12개월.

- AGENTS/기존09보고서·진행·코드확인. 기존Vibe screener는현재Eastmoney만지원,역사asof불가. 과거snapshot으로오인안함.
- backtesting-frameworks 스킬검토:사전범위·비용·누출/생존편향검증에적용. 운영경로수정없음.
- 새계약 `experiments/task9_value/contract.json` 확정. 2021/2022/2023-11-30,US30/KR24산업분산datedseed,시장별가격20이상gate전LLM0. 각시점독립순위/시장별3심층,최대7호출350k known tokens. 연구용포트폴리오100%동일노출과AI현금포함정책<=60%구분. 성공목표가비현금강제가아님.
- 출처확보:현대차증권2021-11-01 원본PDF/본문(산업별약40기업+당시금리/지수/수급참조);2021-03-16 Robinhood Dow30 명단과2020S&P공식교체발표. Seed전체시점별새기업탐색이아닌기존datedseed내독립발굴임을한계로표시예정. 이후시점은당시공시/뉴스추가해연구근거갱신.
- 다음:유한54기업가격/당시DART요약·메타→breadthgate→3shortlist→심층원문→3투자판단봉인→독립성과평가. 평가불능선정기업은제외재정규화하지않음.

## 판단 봉인 및 호출 한계

- 세 시점전체판단봉인완료. 2021KR삼성전자/오리온각10%,2022US AXP15%/KR현대차15%,2023양시장현금. 연구용선정top2는별도. 사후성과아직미계산.
- 실제호출6회:screen3정상,deep2023정상,deep2021/22는완전한JSON생성후90000/호출 guard초과로transportFAILED(91355/92027). 상태수정안함. 정확한원본trace에서JSON/tool-free/inputhash/정책계약검증후**연구진단용**으로만회수,성공transport로재표시안함.
- 마지막compact딥65958토큰으로총355741,자체사전350000상한보다5741(1.64%)초과. legacyrelay는누적사용을호출전에만체크하고hard생성상한이없음. 예산준수PASS로표현안함. 추가LLM호출중단(7번째피드백실행안함),결정론적진단으로대체. 원본예약/trace/실패기록보존.
- 수집실패v1은신규adapter에value_approx누락, v2는Yahoo실제OHLC기하위반발견. 원시자료재수집없이v3격리/유효행numericgate통과;원본/실패보존. 결측·OHLC를보간하지않음.

## 최종 결과/재개 체크포인트

- 보고서 `docs/development/09_investment_utility_report.md` 작성. 3기준일×2시장,시장별초기30/24·가격29/24·매번심층3개,총18기업시점/14독립기업. 전체시장새코호트탐색이나5년연속운용으로과장하지않음.
- 실제LLM연구정책:2021KR삼성전자/오리온각10%·현금80%,2022US AXP15%·KR현대차15%각현금85%,나머지현금100%. 공식Paper매수/승격아님. 연구품질top2각50%별도.
- evaluate.py72개모드/기간CALCULATED_PARTIAL(독립72표본아님),54기업시점×기간가격pair의양끝open 모두두provider원화1원/달러1센트내일치. 2021/2022/2023각12개월US품질-6.02/+4.52/+10.68 vs지수-11.20/+11.56/+32.47,KR품질+4.01/+28.54/+12.71 vs지수-12.54/+0.76/-1.65.
- 이미정한12개월구간3개전부설명적연결:US품질+8.717/정책+1.213/지수+31.226%,KR품질+50.683/정책+1.739/지수-13.325%. 배당제외·가정비용후,분수notional계산,실제주문원장아님. 월별/사건별재연구아님.
- 코호트단순대조군은단일provider UNVERIFIED진단. 2023US6/12개월은3M/Solventum분배미정산으로전체성과차단,3M제외재정규화안함. 공식issuer8K원본/evaluator_only/material_actions/보존.
- 예측18개실현채점완료(v2). US단순분기×4대비6/9개오차작음,KR동일accession9개월×4/3대비3/6개작음. 주가·실적정확도별개. CSCO예측3.00이당시회사guide2.97~3.08내이므로독립증분예측력미입증별도audit.
- AXP사후공식PDF는image-only라초기텍스트실패보존,기존PyMuPDF로page0렌더직접검토해2023dilutedEPS11.21확인. actual_2023_receipt_v2.json/PNG/hash/forecast_scores_v2.json.
- 원인분해:미국선정품질부족+현금선택,한국선정품질양호/정책노출작음,순환정상화EPS추론오류. KB금융원문에은행자회사자본비율자료가있으나패킷미전달확인(그룹수치와혼동금지),자료수집/패킷구성/모델판단분리. 원래판단사후수정안함.
- 원본범위토큰위반유지:6calls355741,planned350000대비5741초과. relay전송2FAILED,trace회수는진단용,업스트림전과정성공으로표현안함. 새로운LLM호출금지/7번째피드백미실행. 위반상태정상화안함. 호출사용량model_usage.json. Yahoo59estimatedGET vs56plan도명시.
- Tosscount1000 400실패14보존후수정계약을성과계산전작성,같은14종목200봉×4page=56콜로정상수집. 원래18reference+14fail+1probe+56page=89calls,수정상한110이내. DART36calls. 추가인프라/패키지설치없음.
- 새연구단위10testsPASS/필수안전24PASS/compileallPASS. 기능통과와투자/예산판정별개. 기존Forward봉인2계획workerhash동일/현금US100000 KR10000000·체결0/timeractive. 운영src/config/scripts수정안함.
- 기존역사DB append7기록/readback7검증,연구용Queue후속1건ID4d86fdcf32b8ada483ba7e748f2ac1e851d450762fb9b8cab411ce6e667aa246(4개요청),신규공식Factory실험0. own dump value_research.dump. 실제재부팅/이번dump새DBrestore미실행.
- 재현은seal.py→evaluate.py→score_forecasts.py→chain.py→diagnose.py→write_report.py,기존원문/봉인사용해LLM0. 모델의부모입력마스킹/도구금지/실패상태검사유지. 각자료hash는최종artifact_manifest.json.
- 후속:새날짜/다른기업코호트,누락기관수급/consensus/자본구조/선행기업정보,순환정상화이익예측,Forward. 이번과거결과반복노출에따른최적화/위험한도변경/자동승격금지.

- 최종정리:임시relay PID2675599/socket종료,약8.6GB /tmp/task9-value-safety와실험bytecode캐시만삭제. 원문/실패로그/이미지/판단/연구DB/dump/기존가상환경보존. cleanup.json. 실제새패키지설치/운영프로세스변경없음.
- 최종검증:10+24 PASS,compileall/git diff --check 통과,54 endpoint roundtrip pricepairs 전부통화반올림범위,원문source223개inventory·API사용량·privatecredentialhit0. 단위시험은관측성과우위인증이아님. 보고서/최종hash manifest를먼저읽고재개.

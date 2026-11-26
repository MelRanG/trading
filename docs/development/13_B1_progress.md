# Task13-B1 진행

- 기업 US6/KR6, macro3(공식FOMC목표금리/DGS10/HYspread), 후보최대2(동일회계연도guidance revision/계약순증)와60HTTP/150MB cap 사전봉인.
- SEC는복구된설정으로submissions/companyfacts정상GET만확인. 재진단/키노출/운영변경금지. 구조화처리LLM0, 엔진/학습/백테스트0.
- B0 원문과잠정/정정계보재사용. candidate연구입력과사후감사·PIT_PARTIAL macro를분리. 필요필수회귀는현재코드/데이터의검증용복제에서진행해.venv/runtime전체복사문제를피할계획(원본테스트변경없음).

## 완료

- 실제39HTTP/39성공, 48.64MBdownload/검증gzip보존. B0원문참조재사용. US6API/5기업10분기정규화/51facts(25inline대사), JPM지정과거metadata부분누락. KR6기업8분기32facts+계약/잠정/정정계보.
- macro3: 공식FOMC2release의14:00EDT와0/-50bp행동→PEP/2024KR정정에asofjoin. DGS10/HYOASlatestbackfill은PIT_PARTIAL, 역사worker배제. stale120일초과macroNone.
- 가이던스하향H20: RESEARCH_READY(원문/특징량파일럿범위, 적격하향1기업1건이라통계검정준비완료아님). July약4→Oct낮은한자릿수, EPS최소8유지. 계약정정H60: DATA_PARTIAL, 명목증액262557900000/114569400000원, 신규경제적범위미확인.
- workerpacket3+sourceallowlistseal, Factory기존계약shape초안2. 등록/예약/dispatch/원장쓰기0. 실제worker/엔진/학습/백테스트/내부LLM0. 후속Task자동시작없음.
- 신규6tests/필수24regression/compileallPASS. 필수시험은.venv/runtime/.env제외한현재코드/실제data/reports SHA대사snapshot에서원본그대로실행, 임시복제제거. 초기4코드검증오류로그유지.
- 기존4616파일SHA불일치0, 운영timeractive, SEC식별설정SHA불변. collect재실행HTTP39→39/receipt동일 신규0 실제검증.
- 보고서 docs/development/13_B1_information_research_bridge.md. 다음은동일guidance변경유형의제한된원문확장·원시예측력파일럿만추천(30독립사건/12기업, Nasdaq종목세션대사, 개발/Forward독립성구분). 새macro카테고리/Quanta/RD/Task15/운영연결자동실행금지.

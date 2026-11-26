# Task9.4 진행

- AGENTS/Task9.3보고서/실제Vibe web_search·ChatLLM 및static평가함수 확인. 기존tracked5수정 보존. 운영src/config/Factory/Paper/Live변경금지.
- Task9.3의기존수익을이미알고있음,모델에는제공하지않음. 이번새후보/비교자산선정전futureprices조회금지. Task9.3원장불변·엄밀AB아님.
- contract.json 사전등록: Terra6회계획/8회절대상한/550000tokens,한번90k여유예약. 모델은검색계획→실제검색결과발굴/심층질의→최종가설/관계별comparators만담당,매매판단·비중없음.
- 시장별top3고정슬롯1/3·미적격슬롯cash,가격수익률동일기준1/3/최종구간,peer/ETF선정은성과조회전에모두봉인.
- 기존원본websearch는현재검색결과를반환하므로엄격publicationgate필요;공식datedsource만researchpacket으로공급. 시점불명은insufficient.

## 발굴·심층 자료 보완 체크포인트
- 실제Terra5호출 성공(초기KR계획의 미국질의범위오류1회포함),210,583tokens. 최종US/KR2회로총7회예정,8회/550ktokens상한유지.
- Vibe원본WebSearchTool broad6+target8쿼리/시장 실제실행. 미래기사/무관한2FA검색결과/빈응답은격리하고날짜확인된원문만입력. hostfallback은기존queryguide초과하며별도기록;엄밀한자율CLI성공아님.
- 미국18개/한국28개초기발굴,10개/8개심층후보. LS별칭오류수정;DART미래정정제외;삼성바이오는Apr23대체자료;AIR은Mar24최신FYQ3확보. 재무검증은Task92verify_fact재사용,발굴을주식수누락으로차단하지않음.
- ETF공식PDF직접검사에서KR_ETF_POWER가제목추정과달리연금상품안내였음을확인해관련성근거로제외. Apr13/20ETF보고서와Jan2026iShares원본으로존재/관련성만확인,보유종목중복은미확인표시.
- 현재검색은미래snippet을반환하기도하여코디네이터의간접노출가능성존재. raw검색로그격리,모델은사전필터문서만받음. 완전맹검·독립알파증거라고주장하지않음.
- 아직Task94미래가격조회없음. 최종US호출진행중,KR입력길이전송한도맞춤중. 기존운영코드/원장변경없음.

## 최종 연구 호출 복구
- 미국최종성공: AIR/ETN/GEV3개,사업가설과분기수치예측,peer/theme/ETF목록생성. 강제선발인원없음.
- 한국최종첫시도는실제추론100,955tokens로회당90kguard초과→FAILED. 원본trace/usage보존,성공으로표현하지않음. SDKtransport재시도는기존request차단으로추가LLM호출없음.
- 마지막8번째호출은동일한재무값/단위/기간/출처를그대로유지하고반복metric/label을사전으로압축한final_KR_compact. 입력business중복서술은제거. 예산550k이내여유확인,가격/종목사후결과는미제공.
- AGENTS최소4안전suite24개+신규연구계약5개=29테스트통과. 기존Task93manifest1564개해시모두일치. 최종산출물후추가seal/결과검사예정.

## 양 시장 봉인 완료·평가 전환
- research_seal.json: 미국AIR/ETN/GEV,한국LS일렉트릭/삼양식품/케이씨텍각3개. 비교목록포함15개자산동결. 무기호비교기업은이름만보존하고사후ticker확장금지.
- Terra실제8회(성공7,초과guard실패1),465,579tokens(입력436,802/출력28,777;cache75,648). 별도유료API없음,구독추가금액단가불명. 더이상LLM호출하지않음,전용relay종료.
- 원본native검색/원본ChatLLM/모든요청·실패trace·최종연구·ETF자료보존. 이제봉인검사후evaluator_only에서만미래가격수집시작. 이후판단/peer목록/비용변경없음.

## 완료 체크포인트
- 최초May18open→Jun18/Aug18/Nov13close정적평가완료. 미국top3gross -10.56%/net -10.67%,S&P500+1.98%. 한국gross -17.05%/net -17.32%,KOSPI-28.92%. 100%동일초기노출,매매판단·중간교체없음.
- ITA11/5분할3:1로최초소스충돌→BLOCKED보존. OCC60055거래소통지확인후Yahoo소급조정역산·Toss명목가격·수량3배대사V2생성. AIR-ITA+5.02pp. 동원F&B비교가격조회실패/빈자료미산출유지.
- 실적예측6개대조: AIR13%/ETN19%/GEV122GW/LS1.877789조/삼양7918억/KC1141.8669억. 범위내3,상방과소추정3. 가설수치반증조건은미충족이나가격인과는UNDETERMINED. 일부공식웹발췌·KC당일발표시각은PARTIAL.
- Task93최초top3정적고정대조군만별도진단: US-32.09%,KR-26.28%. 원래동적운용결과불변,동일조건AB개선주장금지.
- 최소안전24개+신규계약9개=고유33개통과. compileall통과. 봉인자료재계산일치. Task93manifest1564개모두동일,알려진실제환경인증값출력파일스캔0건.
- 원본trace/실패/소스/가격/결과보존후전용worker임시55파일843462bytes·소켓·실험pycache만정리. 기존checkout/venv/운영자료유지. relay및자체컨테이너종료.
- 최종보고09_4_vibe_discovery_benchmark.md작성. Discovery제한적PASS,Research PARTIAL,RelativeSelection PARTIAL(미국시장우위미확인). 신규Forward/실거래성과아님.
- 남은미검증: 완전PIT유니버스/현재검색간접미래노출,주당가치6개모두미완성,직접peer코드일부미확인,ETFdated편입/중복효과,배당포함수익,위험일치알파,원본전체Autopilot무인운영. 운영/팀3/Factory/Paper/Live변경없음.

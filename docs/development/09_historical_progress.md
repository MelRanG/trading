# Task 9.0 진행 기록

2026-11-14 KST 시작. Task8b 직후 새 역사 연구. 운영 전략/원장/Forward/timer 변경 금지.

- AGENTS 및 Task1~8b 보고서 핵심·원본 실행 코드 확인. 기존 Vibe commit0025531f, Quanta b7ceb27b, RD484776c 재사용. 새 설치/업데이트 없음.
- 기존 Task6 US38/KR20은 current survivor cohort와 이미 본 평가 결과. Task7~8b는 현재자료. 과거기업발굴/독립예측으로 재표시하지 않는다.
- 중요한 코드 사실: Toss get_market_calendar(start_date,end_date)는 인자를 받지만 실제 현재 previous/today/next snapshot만 요청한다. 역사 세션 조회로 쓰지 않는다. Vibe screener도 현재 Eastmoney snapshot이며 as-of 인자 없다.
- 실행 전 범위/자료/LLM/실행 gate는 experiments/task9_historical/contract.json. 대표 완전재현 gate 통과 전 5년롤링 대량 LLM 실행 금지. 현재 생존기업/사후상승주에서 시작하지 않는다.
- 원문 Master Prompt V3 전체는 현재 요청/저장소에서 아직 확인되지 않음. 사용자 제공 핵심원칙을 적용하며 원문을 읽은 것처럼 표시하지 않는다.
- 다음: 공식 역사 소스 실제 접근·DART 당시공시 목록과 수정 이력·가격/기업행사·역사세션 조사→대표시점 적격성→실제 연구/독립평가. 소스 실패/원문과 hash 보존, 자료불충분이면 수익률을 만들지 않는다.

## 중간 체크포인트 — 2026-11-14 04:25 UTC 전후

- 실제소스:SEC2021q3.zip/2021Q4master.idx/data.sec.gov정상식별GET3개모두403;KRX역사조회403. 우회안함. Yahoo S&P500/KOSPI 5년 가격지수 성공, V87수치/격리revision NO_REFERENCE통과. 현재다운로드이며 TR/당시보유원본아님.
- DART다섯달 각100개 periodic 공시=500개 row,총공시2955/3316/3203/3259/3302중첫페이지. 전체시장/전체달아님. 날짜순첫4개 원본보고서/서로다른법인 선택후 document.xml20회실제수집. 생존/현재시장분류/주가성과로필터안함. SPAC/비상장도남음.
- 소스오류:일부2021 XML선언UTF8실제CP949, raw보존후 strictdecode로수리. 표기용&cr;와잘못escape된원문때문XMLrecovery warning발생(계수보존);숫자/단위자동보정없음. 잘못디코딩v0도보존. 현재목록이름 와이앤넥스트 vs202605원문 연이비앤티 실제확인→현재명칭은연구입력제외.
- 모델원본VibeChatLLM+기존network-noneworker재사용. 첫2 oversized 요청 relay preflight502 (LLM예약/호출전 거부),원래request보존후BOUNDED_EXCERPTS_V2 새hash로재개. A2_202111/202311/202411/202511완료,202605진행. 대표2021은금융목차를본단락으로수리+당시가격PARTIAL별도추가한A3를새입력으로실행중. 기존A2수정안함.
- 대표원문기업:이미지스,JTC,DB금융8호SPAC,솔루엠. A2는이미지스/JTC연구우선,SPAC제외;영업이익/CFO/자산화위험발견. 원문에없는시장컨센서스/거래가능조건은기권.
- 기존Toss로대표4코드200일당시일봉GET실제실행,3개가격성공(2140/3800/23050),SPAC실패. 과거법인/코드연결·기업행사확인안돼PARTIAL,실제매매허용근거아님. 공식역사KR달력미확보.
- 최초A2이미지스2022매출/영업이익숫자시나리오응답hash를evaluator_only/contract.json에기록후후속원본2022사업보고서(20230320000533)및재무API수집. API접수번호가원본과일치,숫자를원문으로대조. 별도evaluator_only는worker에mount안함. score_forecasts.py실제채점,단순9개월연율화대조군도함께계산. 주가/포트폴리오성과아님,LLM과거지식교란미통제.
- experiments/task9_historical/replay_contract.py:원문공개시각/정정/회사·단위·기간계약,거래적격성6gate,누락때수익률None. 신규12tests통과. 필수안전4파일 /tmp/task9-historical-safety 진행(대규모복사I/O시간,완료확인필요). 운영src/scripts/config수정없음.
- 다음:대표A3→동일기초B(공식BOK/Fed당시발표+당시지수부분자료)→C(동일기업대안) 실제호출,다섯A결과출처감사/봉인,공식Factory/Review후속요청(정상예산유지),보고/아티팩트index/시험결과/정리. 전체PIT/대표완전재현gate미통과이므로9.0D연속운용/수익률생성은차단한다.

## 최종 체크포인트 — 2026-11-14 KST

### 완료

- `09_historical_investment_replay.md` 작성. 9.0-A 자료/기능 실사 실행, 9.0-B 대표 완전재현은PARTIAL(원문연구→실적채점만),9.0-C한국제한표본5시점 실행/미국미실행,9.0-D전체rolling BLOCKED,9.0-E 제한원인분해/후속연결 실행으로 구분.
- 20원문은 **20개서로다른corp_code**. 각시점4개/공시첫100행이라는선택편향,SPAC/비상장포함,전체시장/적격20투자아님. 후보별접수번호·원문이름·제외·예측·프롬프트·버전보존.
- 모델실제8성공:A2다섯시점+A3/B3/C3대표. Terra591801tokens(대표303592,기타288209),모두budget이내. 초기2logical요청oversize는모델호출전preflight거부,LLM0회이며별도로그보존. 금액미확인. B/C의공식Fed/BOK본문추출끝을직접확인해현재navigation/미래이벤트가들어가지않았음을확인.
- A3/B/C대표2021공통foundation/sessionhash동일. A3재무목차수리+부분가격이후원본판단은이미지스→솔루엠연구,JTC대기,SPAC제외. B시장/C대안추가해도판단·비중불변. 숫자가치평가/적격비중없음. A2와A3입력이다르므로순수효능A/B아님.
- 8출력102개인용102개모두원문문자매칭. 이는semantic/숫자기간/인과100%인증아님. `evaluation/provenance_audit.json`, `seals/manifest.json`, `research_outputs/`.
- 원문후속실적3기업6metric채점. 이미지스2022매출4.18%/OP35.54%오차(단순연율화4.29%/18.06%). 동남2025매출7.34%/OP3.90%,TSI2025매출5.54%/OP51.61%. 과거지식교란/소표본/넓은가정범위로인해독립예측우위아님. 2024A2숫자후보전부2개를추가평가하기전phase2계약고정,모델/예측재작성없음.
- evaluator코드처음IS만필터해실제CIS미채점→IS/CIS및원본접수번호·연도·단위일치최소수리. 초기blocked결과보존. 동남CFS013은성공으로표시안하고이미보유한원문별도요약의단위천원/2025첫열을직접감사해사용;추가API예산우회안함. TSI/API원본접수번호일치·숫자원문대조.
- 실측S&P/KOSPI가격지수경로확보(V87numeric/revision NO_REFERENCE). 2021-11-30→2026-11-13가격변화65.57%/86.35%. TR/ETF/AI운용성과아님. 전체가격기간시작Nov15이므로Nov1부터완전5년자료아님. 독립6개월미성숙을표시.
- 기존QH `research.replay_targets` 실제함수를합성3bar/매수매도로시험. thin `run_existing_replay`는인증된무기업행사구간만허용,기업행사processor없으면차단. 과거실제매매/원장/포트폴리오수익률은생성하지않음. 10시장×시점mandatorygate모두미통과,성과null. 현금0%수익률로위장안함.
- PostgreSQL `quant_task3_task9_history`,제한role,기존Store/Queue재사용. source snapshot+개선3건+사후실적review,1job실제claim→PENDING_EVIDENCE→Forward평가후속job 생성. 현재READY3/PENDING_EVIDENCE1. 새프로세스6payload/hash확인과DBdump보존. 실제재부팅/새DB정기백업편입미검증.
- 공식Factory정상등록시도BLOCKED(UTC당일3/3기존Task6/7/8b). 예산예약/실험/승격없음. `factory_budget_observation.json`. 이미대기제안의workerSHA원본을정확히복원해code_versions에보존,새adapter버전으로몰래대체하지않음.
- 운영src/scripts/config수정없음. 기존Task8b2봉인workerhash일치/US현금100000/KR10000000/체결0,기존timer active읽기전용확인. 역사결과를Forward로append안함.
- 시험:신규13PASS(`contract_tests_final.log`),필수안전4파일24PASS(`mandatory_tests.log`,134.91sec),총37PASS. compileall src/scripts/tests+실험코드exit0. 초기missingdate정규화/인코딩실패/oversize/CFS013/IS미채점로그보존.

### 재개 시 남은 의존성 (완료로 바꾸지 말 것)

1. 원본시점별시장전체종목/코드·상폐·거래정지/공식세션/기업행사·배당·청구권,consensus등적격자료복구. SEC/KRX403현재상태보존. 현재목록을과거유니버스로치환금지.
2. 적격대표1시점 실제기업발굴→A/B/C숫자가치/비중→가상체결/행사회계→성과검산. 현재NONE. 이를통과한뒤5시점완전·20분기rolling을사전예산으로진행.
3. Factory정상예산/선행우선순위이후원문12독립process진단및신규Forward실적예측평가. 현재source proposal만등록대기,실험없음.
4. Task8b자연Forward관측은기존timer에서유지,새tradepolicy/실주문/승격없음.

마지막 정리:끝난 /tmp/task9-historical-safety 시험복사본과실험bytecode,작업relay/socket만제거. 원문/실패/환경/DB/백업/연구출력유지. 정확한내역cleanup.json,최종source/evidence SHA manifest.json. 자동operating파일변동은manifest의mutable목록과구분.

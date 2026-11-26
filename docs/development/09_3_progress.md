# Task9.3 진행 기록

- AGENTS/기존diff/Task9.1·9.2보고서·실제Vibe스크리너·sharedreplay·모델격리경로 확인. 기존변경/원장보존.
- 계약 experiments/task9_3/contract.json: 20260515close→1113close, 시장별분리7연구일, 최대16Terra/1m토큰, 후보35/심층5, gross90/name25/sector50%, nextopen/고정비용/일별stop. 결과확인후변경금지.
- 원본Vibe스크리너는currentEastmoney만지원(과거asof없음), 역사스크리너원본성공으로표현금지. 원본financial/valuation/macro/sector스킬+ChatLLM 재사용, datedsource bounded 탐색adapter 필요.
- 다음: datedcandidate발굴/가격·재무적격성→첫시장연속연구·기존replay→양시장전체/검산/복기.

- 가격초기수집timestamp누락실패를보존후수정: US32/33,KR8/35적격. 한국5000억원proxy·datednumeric gate로축소,공시window표본편향명시.
- 기존sharedreplay의일별target drift거래를피하려고optional rebalance_dates만추가(defaultNone기존동작유지); 별도백테스터구축안함. 재현시험추가.

## 모델·가격 단계 체크포인트
- 실제최초US/KR연구봉인완료: 모두cash100%,rank와매수분리. US VRT/MOH/SFM/BAM/FLUT; KR SNT에너지/바이오노트/SNT홀딩스/신성이엔지/케이씨텍.
- 모델transport KR discovery최초request>180000거절(모델호출아님);screen요약만축소후V2실제성공. 전체numericdeepfacts는유지.
- US5주식2공급자daily대사PASS,KR다수daily차이. price_resolution.json V2에서open/close각각2공급자합의값만사용,미합의NaN/HOLD_ONLY,수익확인전규칙고정. 신성이엔지May15reverse1:10첫가능May18체결이전;초기Q1주식수·가격불일치경고.
- 036530.KS Oct12close미합의1개,원문모두보존·보간안함. 실제보유시일별NAV/MDD제한.
- 초기US프롬프트macro증거미포함(unknown),이후monthly에공식Fed/BOK본문공급. 원본문구변화로macro추출실패후raw에서복구(v2),BAMQ2/Q3 HTTP200404page는invalid표시,모델제외.
- 일반달별일정+공식실적후US4개eventreview,KR4개달별은결정론적관측/기존판단유지,총실제모델16상한동일. event_policy.json.
- Aug17한국휴장,benchmark관측세션에따라Aug18review→Aug19가능fill; calendar_mapping.json. US정상Aug17별도. 공식calendar전체독립인증은별도미확인.
- run_sequence.py 백그라운드진행중. US전체후KR진행. 재개시sequence.log/model_calls/*.reserved.json확인,RESERVED/TIMEOUT중복호출금지. 모델출력존재시run_model.sh캐시재사용,결정보존후진행.
- 진행중프로세스는초기코드로컴파일되어KR Aug17에서가격세션assert로멈출수있음. 이후수정된run_sequence.py재실행하면US완료분skip·KR Aug18부터이어짐. 새로운모델중복호출없음.
- 다음:US먼저evaluate.py US→KR수정일정계속→전체성과/일별ledger·월말NAV·Review/Factory증거/시험/최종보고. 아직최종수익률계산전,어떤높은결과도선정에반영하지않음.

## 계좌 피드백 한계와 보완
- US Oct29모델 SFM10%/48달러entryceiling→Nov02cash100% 봉인. 임의매수강제가아닌실제비현금모델판단생성. 아직최종실행계산전.
- 미국의이미봉인된연구에는직전목표/가격은있지만실제체결후원장readback이없음. 이를소급수정/재호출하지않음. 연속목표실행성과는평가가능하나완전한계좌인지형자율운용성공으로표시금지.
- prepare_next에신규packet만공유replay를asof까지실행한account_state_asof전달추가. 남은한국후속모델은이를사용. 미국이미sealed입력은불변. 시장간서로다른방법한계명시.

## 최종 완료 체크포인트
- 실제 Terra16/16 SUCCEEDED,969375/1000000tokens. 추가호출금지. 최초탐색2+US연구11+KR연구3; 총봉인판단18(한국4개달별은결정론적carry). 입력18packet/1349factversions 감사PASS,반복사실을독립표본으로세지않음.
- 기존sharedreplay8연속계좌/104가상체결의현금·수량·NAV·고유client_order_id 대사. USD정책100576.6571(+.576657%),SP500+1.977056%;KR정책10000000(0%),KOSPI-28.922160%. 선정90대조군US-26.759062%,KR-21.073919%.
- US Oct29의SFM48달러조건은Oct30시가조건불충족. Nov09 10%/50달러조건봉인→Nov10시가49.17,201주가상매수(비용후49.19614),Nov13종가보유평가. 정책매도0. KR전기간자료부족중심기권,하락예측성공으로해석금지.
- 한국SNT홀딩스Oct12미확정close1건;실제보유대조군NAV1일결측/MDDSharpe차단. ADV20까지결측인경우연구전용옵션에서추정없이미체결기록·보유유지(초기중단로그보존). default기존fail-closed변경없음. 대조군목표90/종가최대92.35노출차이명시,하드cap준수성공으로표시금지.
- 최초US실제체결계좌미제공한계보존,후속KRasof계좌readback추가. 초기SFM금융부채balance period_start분기시작메타데이터오류1건 별도정정제안,금액/enddate는그대로,봉인입력/모델결과소급수정없음.
- 복기→기존역사연구DBQueue처리DONE→공식Factory제안등록 REVIEW-270e801982914df5e0fa2121 확인. 실험일일예산소진으로reserveBLOCKED/실행0. 후속Queue새kind자동dispatcher미지원,미완성명시. 최초Factoryhashcanonical오류는원실패로그·구worker기록보존후V2에서정상계약연결. 동일worker재호출readback/중복0.
- 기존역사DB45개새증거append/readback+pg_dump/hash/별도프로세스재확인. 기존Task9.1/9.2/value총3241artifact SHA일치. 운영US/KR현금/체결0·timeractive 보존. Live/전략config/브로커주문경로수정없음.
- 최종신규8PASS,안전53PASS,Paper/운영/DB32PASS(0skip),compilePASS. V104실제NO_ENABLED_CANDIDATES/append0/Livefalse,예시freeze branch미실행. ops32는default불변경로,추가연구전용결측처리는8시험에서검증.
- 보고서 docs/development/09_3_six_month_historical_trading.md. 원문/모델/판단/월말NAV/일별거래/복기/DB근거 runtime/task9_3. 재개시verification/manifest/sourceversions확인후공식Factory예약·미지원followup·PIT/자본/계좌피드백개선만진행,이미실행한역사연구/모델재호출금지.

- 최종모델산출물49개archive SHA대조후임시work/relay/socket·약22GB시험복제본정리. 기존checkout/venv/원문/기록보존. US수익·NAV·체결은결측ADV처리수정전후완전동일SHA확인. 인증값scan1093파일0건. cleanup.json.

- 지수추가대사:KOSPI진입시가/최종종가 및124closes Toss/Yahoo일치,기타시가0.72%충돌은별도보존. US SP500 Tossindex미지원으로Yahoo단일계산신뢰도PARTIAL유지. 지수수치·기간·전략변경없음. 최초KR문자열숫자파싱오류→캐시에서numeric변환V2,추가원문조작없음. benchmark_return_audit.json.

- 마지막가치평가산술감사:최초SFM명시FCFE300/400-440-480/500경로와r/g로연말계산시Bear27.75/Base64.54/Bull91.65,모델26/53/91과불일치. nativeper-sharebridge재사용. stub/enddate누락도있어정정승인목표가아님;결정/거래/수익률교체없음. Task92의명시날짜계산gate가모든Task93출력에강제되지는못한한계명시. valuation_arithmetic_audit.json. 모델추가호출0.

- 추가가치평가복기1record+기존Queue에연구요청append,finalDBdump/readback보존(persistence_supplement.json). 기존45records/dump불변. 후속자동실행·추가LLM없음.
- 임시worker제거후archive결정봉인/모델없이전체sequence재개/DBreadback/8계좌104fills재검산모두PASS. 별도서비스/DB/Live변경없음. 최종보고서·검증·manifest작성완료.

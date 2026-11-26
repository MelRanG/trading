# Task9.0 후속 진행

2026-11-14 KST. AGENTS/기존09보고/진행/실제실험소스확인. 기존성과/운영불변.

- KRX OpenAPI catalog/usage/detail공식페이지HTTP200. 기존data.krx조회403과별개. 실제와샘플 sto/stk_bydd_trd basDd20211130은401 Unauthorized Key. 현재.env KRX key변수없음(값출력안함).
- 공식절차:Marketplace가입(개인본인인증/소셜),인증키신청관리자승인,API별활용신청관리자승인. 사용자에게승인키보유여부text질문,독립작업계속.
- 사용자DARTkey제안:기존.env키이미작동,키를다른기관KRX에전달하지않는다. DART당시주식수/명칭/기업행사추가조사로연결근거보강예정.
- KRX공식6상세명세수집중. SEC이전403본문은Undeclared Automated Tool. proxy환경없음. SEC공식API는읽기용공개데이터와filer제출용인증을구분해야함. 정상UserAgent/gzip정규경로최소재확인예정,우회없음.
- 새실행전계약experiments/task9_completion/contract.json. 데이터gate전LLM0. 원래2021원문선정기업유지;사후수익으로기간/종목변경없음. 최대63세션보유의한대표실험우선,필수근거없으면허위체결금지.

## 사용자 범위 명확화

- 전체종목일괄수집불필요,대상판별후검색으로가격/종목정보획득허용. 따라서KRX전체snapshot을대표소규모연구의필수조건으로강제하지않는다. 기존당시DART원문선정코호트만사용,선정후식별/가격/행사검색으로보강한다. 투자성과를높이려는종목/기간변경아님. 필수개별종목근거·시점·행사처리는유지.
- DART키추가조사9calls성공. 이미지스2021-10-25무상증자/11-10권리락과JTC2022-02-24배당락발견. stockTotqy2021Q3요청응답접수번호가다른이전보고서이므로기간·증자이후분모로자동채택금지. 대표3종목/Toss+Yahoo가격crosscheck와원문행사보강진행.

## 소규모 실증 입력 확정 전 체크포인트

- 사용자시총제한요청→한국5천억원/미국20억USD,성과평가전계약고정. KR기존원문3개중솔루엠만시총하한통과(1.153조원). JTC0.133조원/이미지스약0.033조원탈락;이미지스두소스가격기준도불일치. 미국은Nov1공식실적발표검색으로ON/ANET/VNO/SPG4개만발굴,가격5개(지수포함)선택수집. 현재관심종목/사후상승주에서출발안함.
- 공식KRX사이트가공개UI에제공하는샘플용인증을공식sample경로에서만사용→HTTP200/각10행/요청일자일치확인. 정규API에사용하지않음(정규401그대로). full-market자료로간주안함. 이10개실제지수행의활성일자+휴장0행으로2021-12-01진입→63세션→2022-03-07다음open KR달력검증. source sessions/에모두보존. KOSPI100을KOSPI로치환안함,가격지수는별도^KS11사용.
- ON도Toss/Yahoo가격일치,당시발표본문(NASDAQ:ON)·EPS·FCF실제검색확인. 서버직접IR HTML/PDF403(그대로보존),공식웹reader부분발췌별도quality저장. issuer2021 10K mirror원문gzip정상해독해과거무배당정책확인(평가전용). Nasdaq일정은NYSE공식2021/22휴장표+실제두providerbar로검증. US12/1→63세션→2022/3/3다음open.
- Yahoo솔루엠Jan3누락및Feb8/23/28 flatOHLC+0volume placeholder발견. primaryToss는모든공식세션실제bar/volume완비;secondary부적격4일은명시제외(보간없음). 나머지OHLC완전일치. US ON OHLC차이는공급자소수점반올림범위($0.005이하),close일치. 통화정밀도KR1원/US1센트비교로명시,기존과도한정밀도실패로그보존. 데이터상태PARTIAL_SECONDARY_COVERAGE,완벽PIT인증아님.
- ANET4배가격기준미대사로제외,VNO/SPG는배당/원문확보미완료로첫실증별도보류. 대상별제외/이유유지. 파생되는실증선택가능대상KR솔루엠/US ON,상대선택범위좁음명시.
- 솔루엠2021/2022Q1원문(20220321000896/20220502000016)에서최근5년무배당명시,발행주식변경표/행사audit확보. '-'를0으로보간하지않음. 이사후원문전체의실적은연구worker에제공안함.
- bounded계약v2는글로벌cutoffNov30 23UTC로수리:US Nov30종가가공개된뒤,KR Dec1 00UTC진입전. 이전15UTCcutoff에US종가를노출하지않음. 63세션/종목/정책/비용은성과이전에고정. KR실험매도총24.5bps(가정수수료1.5+당시세금23),운영config기존21.5bps변경안함.
- 다음:회사원문/가격<=cutoff만묶은Vibe A/B/C최대3호출→판단봉인→원래기간실제QH리플레이/대사/지수비교. probe강제안함;모두기권이면동결대조군매수만실행하고AI매수로표현안함.

## 실제 첫 재현 결과 및 오류 복구

- Terra A/B/C3호출성공,합149105known tokens. 같은sessionhash. 두시장모두WAIT:솔루엠Base18000<23050,ONBase65.16대비61.43약6%상승/큰하방. 확인된새가치없는데매수강제안함.
- 모든판단DB봉인뒤63세션리플레이실행. AI A/B/C현금0%수익,매수0. 사전등록대조군은솔루엠10주Dec1→Mar7,ON40주Dec1→Mar3실제역사가격으로매수·고정보유·매도,계좌손익각-5342.49KRW/-33.5538USD. 원시가격·수수료·추정spread/impact·매도세금·client_order_id·NAV보존. 이매매는AI매수가아님.
- KOSPI Yahoo Jan3누락으로초기평가fail-closed→당일KBS/Yonhap원문둘다2988.77관측close만sidecar보강. 원본CSV미수정,open/high/low임의생성안함. Sourcepatch는evaluator전용. 기준같은entry/exit open시장가격지수수익은KR-6.2917%,US-4.3780%. 현금회피기여와종목발굴알파구분.
- DB출력오류:cash대조기준의-0.0를PostgreSQLJSONB가+0.0로정규화해원래Storehash6건불일치. 금액/원장수치변경없음. 전역Store/운영코드수정안함. 읽기전용SQL재현test후local canonical_zero V28결과append,원본6건은정확한rawartifact/hash로복원가능하게보존·serialization-only superseded state. export는원본SHA검증재수화. ledger_recovery.json/원본결과/전후오류로그보존. 원본payload/hash UPDATE/DELETE없음.
- 동일스크립트재실행이미봉인모델/동일4fill재사용,새주문0·원장중복없음. 기존generic Store.export는V1음수0receipt에서호환한계가남으므로이DB은canonical V2/검증된복구export를읽어야함. 이한계를숨기지않음.
- 대조군target2.5%의US실제초기노출은D1→open gap으로2.522%(대조군별도초기상한20%이내). 이를2.5로위장안함. 향후ABC PROBE가있을때는postcost/open실제노출2.5초과면fill저장전차단하는guard추가. 현재ABC0/대조군결과변경없음,원본자료/모델불변.
- 신규6tests(실제QH매수매도/고정보유/벤치마크시점/결측·행사차단/현금/JSONB음수0)PASS,필수안전24PASS. 실제모델매수는여전히0이므로'자율비현금투자선택검증'은미달성,거래기능/실제가격대조군/기권성과만검증.

## 최종 체크포인트

- 완료보고서 `docs/development/09_historical_replay_completion.md` 작성. AI비현금매수미달성/시장별제한코호트/PARTIAL데이터/5년미완료를명시. 거래대조군과AI성과구분.
- fresh process+별도DB `quant_task3_completion_restore_091038` 복원성공:canonical8결과/고유4체결/AI0. recovered export29행원본hash검증. 실제재부팅미실행.
- 기존Task8bForward읽기전용검사:동결계획2개workerhash일치,USD100000/KRW10000000현금·체결0,단일timeractive. 운영DBwrite0.
- 자체연구Queue후속job ed11c3e771a46d1f6e7e4936ff7f1fa34f0b4982c860f1f6a614c99ee8464766등록. 공식Factory예약/평가를이번후속에서실행한것은아님;정상예산/우선순위유지. dump는이새후속job등록전시점,job은원DB/followup.json보존.
- 모델3호출/149105known tokens/SUCCEEDED3,금액비용추정안함. 저장된입력/출력재사용하면모델재호출필요없음. 신규산출물에.envAPI키/비밀값문자열검사hit0.
- 신규6PASS+기존필수24PASS. pandas시험FutureWarning1개. 운영경로불변으로운영전체시험반복안함.
- 재현: `.venv/bin/python experiments/task9_completion/run_pilot.py` (새체결0), `verify_preservation.py` (읽기전용), `PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q experiments/task9_completion/test_replay.py`. V1signed-zero genericStore독자는사용금지,canonicalV2/recoveredexport사용.
- 다음연구:시총하한유지+여러산업소수코호트확대,당시가격/배당대사,실적시나리오독립채점,깨끗한Forward. 원본signed-zero호환은별도최소bugfix;이번운영코드수정없음.

- 정리완료:이번relay PID2664194정확한명령확인후종료/socket제거,9.3GB `/tmp/task9-completion-safety`와실험__pycache__/0바이트tmp삭제. 원문/실패로그/결과/DB/backup/격리env는보존. `cleanup.json`. 마지막compileall통과,새원장/모델재실행없음.
- 보고서추가한계:수집시각2026와과거공개시각분리;동결계약benchmark설명은한국문구잔존(미국평가기실제S&P500),사후봉인계약수정안함.

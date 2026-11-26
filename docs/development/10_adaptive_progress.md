# Task10 진행·재개 기록

## 최초 실사 / 사전등록
- AGENTS, Task6완료보고 및 native Quanta controller/RD CoSTEER/Qlib·Factory·Review·replay_targets 실제 소스 확인. 기존 tracked5파일 변경 보존, 이번 작업은 experiments/task10와 runtime/task10 및보고서에격리.
- Quanta의 원본진화component+external평가, RD생성GRU+Qlib학습까지실증됐으나 주간경제성과→native재연구→후속운용 연결은없음. Review현재propose는주로trace결함진단이며 알파성과자동수정엔진아님.
- Factory공식결과는자동승인불가. 같은공식계약/격리PGQueue/모의replayclock으로실행하며, 연구계좌REPLAY_ADOPTED와공식Champion승격을구분. 운영directory·일일예산·Paper·Live·팀2불변.
- experiments/task10/contract.json을연구/수익계산전작성. 기존Task6 US38/KR20고정다업종cohort,생존/PIT제약명시. adjusted가격을명목원가격으로오인하지않고기존수집기adjusted=false로한정200세션train+평가구간확인. 전종목DB구축없음.
- 모델상한Quanta12/650k,RD4/180k,Review2/100k,CPU2/4GB/5epoch/seed42. 추가후보1개·시장별재학습1회상한. 이후성과보며기준변경금지.
- 5거래세션주기복기/거래, close t→open t+1→open t+6의라벨·보유기간정렬. 초기고정50/50 native연구후보는경제성검증미완료표시;적응형교체는동일prefix 비용/위험/IC/기간gate통과시만격리계좌다음세션에적용. 단일손실로연구강제하지않음.
- 다음: 원가격/기업행사데이터적격성→US초기native생성/학습→한시장첫자연trigger Factory최소완주→양시장전체→최종비교.

## 初期native실행·데이터체크포인트
- 가격수집200요청완료(Toss120/Yahoo60/Naver20),V87연결및2공급자OHLC .5%대사. 한국결측은NaN유지. 고정US38/KR20/ETF각1 외자산추가없음. S&P500/KOSPI평가기준은기존동결자료재사용.
- Quanta원본planner/hypothesis/expression/DSL코드생성3LLM호출완료. Volume-weighted20일return/63일volume평균의cross-sectionalrank공식. Futureprefix불변검사US/KR통과. fullAlphaAgentLoop아님.
- RD원본model hypothesis→experiment→CoSTEER3호출로GRU16생성. US/KR별Qlib5epoch실제학습. KR첫240fit<batch256으로drop_last학습0/NaN발견,실패checkpoint/pred보존후batch128로기계적복구(목적수익튜닝아님). 동일수치/seed/split/모델,finiteepochloss확인.
- outer유효label없는날은validationpred가없지만feature예측은가능함: 이를prefix누출로오인한검사수정. 별도prefix-only추론과full-tape동일시점추론일치통과. 미래라벨없음을예측기권으로사용하지않음.
- initial_strategy_seal.json완료. 초기개발검증80세션US+25.94%/IC.07298,KR+38.20%/IC-.02824. 시장/노출/과적합제약이있고경제성검증미완료인고정native후보로격리운용;초기알파우위로주장하지않음.
- Quanta초기feedback는metrics생성전호출FileNotFound실패(LLM호출없음)보존,데이터준비후재실행중. 다음: 주간Review/공식Factory격리PG/자연trigger처리·정적대조운용.

## 실제자연trigger→Factory→개선→계속운용완료
- US첫자연RESEARCH:2026-07-15,연속2회약화·20세션matchedETF초과-6.55pp·성숙5세션IC-.00835. 공식Factory격리예약후원본MutationOperator/제어기+가설/DSL/피드백으로갭평균회귀팩터생성,동일RDGRU코드를prefix로재학습.
- US검증80세션:parent+26.06%/MDD-15.43%/IC.04286,candidate+41.87%/MDD-5.00%/IC.01587. 비용·노출·12비중복블록·leave-one-out등사전gate모두통과. 공식상태FORWARD_REQUIRED,격리계좌만REPLAY_ADOPTED. 7/16첫세션적용,과거NAV/fill차이0검사통과.
- KR첫RESEARCH:7/7(USmutation7/15보다이름상/UTC상과거),미래Quanta버전미사용. 초기Quanta+KRprefixRD재학습1후보검증:parent+42.35%,candidate+28.18%,net개선gate탈락→공식REJECTED·기존전략유지. 후보기각은실제경제적검증결과,합성주입아님.
- 미국STATIC-9.0398%,ADAPTIVE+1.6218%,MOM63+0.4960%,S&P500+1.9771%. 한국STATIC=ADAPTIVE+1.4545%,MOM63-2.9459%,KOSPI-28.9222%. 양시장전체5/18~11/13주간Review·거래원장·NAV저장,US26/KR25회Review.
- US7/16이후구간STATIC-11.38%,ADAPTIVE-.99%. 평균노출차이+.0486pp,interval-matchedindex기여차이-.0596pp; 전체증분+10.6616pp가단순노출증가만으로설명되지않음. 통계/Forward알파주장금지.
- 사후별도attribution(채택/선택에미사용):Qmutation만+8.3155%,RDretrain만-15.0619%. 사후좋은Qonly로실제ADAPTIVE결과교체금지. nativeRD재학습이MSE를줄여도실제포트폴리오이익을늘린다고주장할수없음.
- 첫재개에서CSV기본parser의ULP차이로candidate재검증freeze충돌발견,실패로그보존. 후보CSV round_trip parser로이미봉인한실수값복원해원래검증동일성확인,경제기준/신호/과거결과수정없음.
- current지수/ETF/PIT제약:weeklytrigger는실제matchedSPY/KODEX200proxy(사전문서index표현보다구체적실행차이),최종S&P500/KOSPI별도대사. 원본전체거래소휴장인증미완료,관측source세션기준. 가격은nominal·배당제외. 무인운영/전체nativefin_quant/완전PIT유니버스미검증.
- 모델진행:Quanta8calls+RD4calls실행,추가LLM불필요. 추가scopeReview2콜은미사용. 이제테스트/DB재개·중복/입력무결성/보고서/백업·정리만남음.
- 모델품질진단V1의prefix말미6세션라벨범위는V2로별도교정(과거판단/성과영향없음). V2의pre_initial_validation이름은전체prefix(학습포함)진단이며진짜outer검증은각models/training.json참조.

## 최종검증중발견·정정(계좌성과/선정변경없음)
- 미국채택후주간Review의일반NAV-horizon이원래계좌시작5/18을유지하는버전범위오류발견. Native5-sessionIC/trigger/Factorygate/실제체결성과에는영향없음. V1원문/DB보존하고version_outcomes_v2.py에서신규버전7/16부터만채점,첫7/22는5개marks/5interval미성숙으로PENDING정정. 사후성과개선아닌Review정합성보정.
- 원본달력은Task6API3개근접세션만확인돼전체기간휴장원본인증미완료. 기존Reviewcalendar_verified는관측가격세션테이프정합범위이며공식거래소역사캘린더완전검증아님. 상세scope기록.
- 운영Factory V1관측은파일부재를0으로표현한잘못된가정. 실제기본runtime/alpha_research_factory/task4/없음,Task4/5backups에과거원장만있음. systemd서비스의WorkingDirectory는현재저장소. 운영budget=0사용이라고주장하지않고UNAVAILABLE_MISSING_STATE로V2정정. 임의복원/운영등록/예산초기화없음. 다음운영연결전원장권위·백업복원확인필요.
- 최종연구계약테스트12개통과(실제PGlease재개,동일소스/후보해시,version범위,PIT라벨,사전NAV불변등),AGENTS안전24개통과. 합성budget/lease테스트는경제성과에합산하지않음.

## 최종 체크포인트 — 완료 범위와 재개 조건
- 보고서: `docs/development/10_adaptive_quant_walk_forward.md`. 미국 STATIC -9.04%, ADAPTIVE +1.62%, S&P500 +1.98%; 한국 STATIC=ADAPTIVE +1.45%, KOSPI -28.92%. 경제적 일반화는 미입증이며 추가 연구를 위해 같은 결과에 재최적화하지 않는다.
- 실제 Terra 12회/318,106토큰, 성공 훈련 4건과 실패 1건, 실제 경제적 Factory 실험 2건을 보존했다. 추가 모델 호출·훈련은 하지 않았다.
- 연구 PostgreSQL dump를 별도 임시 DB에 복원하여 113개 기록과 작업 상태가 일치함을 확인했고, 임시 복원 DB만 제거했다. 실제 재부팅 및 운영 Factory 복구는 수행하지 않았다.
- 이전 Task9.3 1,564개와 Task9.4 765개 파일의 manifest 대사에서 변경 0건. 새 텍스트 산출물의 인증정보 검사 검출 0건. 작업 전부터 존재한 tracked 5개 파일 diff는 그대로 보존했다.
- 이 작업의 임시 모델 relay와 UNIX 소켓만 종료·제거했다. 원본 checkout, 격리 환경, 모델, 실패 로그, 원가격, 연구 pool, DB dump는 재현·재개에 필요하여 유지했다.
- `runtime/task10/artifact_manifest.json`에 코드·보고서·진행기록·증거 해시를 기록한다. 기존 계좌 검산에는 보고서의 analyze/ledger 명령을 사용하며 LLM 재호출은 필요 없다.
- 운영 연결 후속 작업은 누락된 Factory 원장의 권위와 백업을 먼저 대사해야 한다. 이번 격리 실행 성공을 운영 승인·운영 예산 사용·독립 Forward 성공으로 취급하지 않는다.

# SEC API 접근 복구

**RESTORED.** 기존 Git 설정에 이미 등록된 실제 Gmail 연락처와 `QuantHarness/1.0` 앱 식별자를 사용하자 공식 SEC API 접근이 정상화됐다. 임의 연락처·테스트용 한글문구를 운영에 넣지 않았다. 이전의 서버/IP전반 차단 추정은 잘못된 일반화였다. 재현상 User-Agent 값에 따라403/200이 달랐고 새 실제식별값으로기존수집경로까지정상완료했다. 특정메일제공자가항상차단된다는규칙까지주장하지않는다.

변경은 프로젝트 `.env`의 `SEC_USER_AGENT`, `EDGAR_IDENTITY` 두 항목뿐이다. 나머지 환경값 동일성을 검사했다. 기존 service.env와충돌없음확인, 전략/Factory예산/Paper/Forward/Champion/Live 변경없음. 기존식별값은 runtime/sec_access_recovery/identity_before.private.json(mode600)에 보존했고 보고서에개인연락처를복사하지않았다.

실제 검증:

- curl: Microsoft submissions200, 공식문서예시 companyconcept200.
- 기존 quant_harness.investment.equities.fetch: Microsoft submissions JSON186640bytes, companyfacts JSON4938072bytes 정상수집·CIK789019/재무facts검사통과.
- 기존 sec_observations([MSFT]): 실제 catalog+submissions 경로에서10-Q/8-K기록5건, SAVED. 새수집프레임워크없음.
- 총6개공식요청. 운영설정의실제연락처로Python수집성공을확인했으며curl전용해결이아님.
- compileall PASS. 필수안전회귀는23개완료후마지막V89시험의프로젝트전체복사중자원사용때문에직접중단했다(KeyboardInterrupt/exit2). 전체24개PASS로집계하지않음. API실수집검증과구분. 이전B0원문·403·봉인·평가를덮어쓰지않음. 새수집자료는현재관측공식JSON이며과거최초공개시각/정정PIT검증성공이나알파성공으로승격하지않음.

코드/결과: experiments/sec_access_recovery/{verify_contact,apply_identity,verify_python}.py, runtime/sec_access_recovery/{configuration_change,result_summary,native_collection_result}.json. 모델/후속연구/Task15자동실행없음.

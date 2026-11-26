"""Final data-readiness/accounting only. No future prices/returns/alpha statistics."""
from common import *
from collections import Counter,defaultdict
import pandas as pd,math,re

def main():
 P=json.loads((B/'plan.json').read_text());D=json.loads((B/'panel_diagnostics.json').read_text());events=json.loads((B/'financial_panel.json').read_text())['rows'];labels=json.loads((B/'label_availability.json').read_text())['rows'];C={p.stem:json.loads(p.read_text())for p in (B/'companies').glob('*.json')};req=[json.loads(p.read_text())for p in sorted((B/'requests').glob('*.json'))];assert len(req)<=300
 sources_meta=[json.loads(p.read_text())for p in(B/'sources').glob('*/receipt.json')]
 groups={}
 for name,group in [('cached',P['cache_reuse']),('pilot',P['pilot']),('extension',P['conditional_extension'][:37])]:
  cs=[C[a['symbol']]for a in group];groups[name]={'companies':len(cs),'companyfacts':sum('companyfacts'in c for c in cs),'structural_issuers':sum(c.get('structural_events',0)>0 for c in cs),'source_verified_issuers':sum(bool(c['events'])for c in cs),'source_verified_periods':sum(len(c['events'])for c in cs)}
 raw=sum(r.get('bytes',0)for r in req);failed=sum(r['status']=='FAILED'for r in req)
 costs={'wire_GETs':len(req),'success':sum(r['status']=='SAVED'for r in req),'failed':failed,'failure_types':dict(Counter(r.get('error_type')for r in req if r['status']=='FAILED')),'successful_response_bytes':raw,'failed_body_bytes':'Not measured by original fetch exception; NOT0. All18ValueErrorfailures are consistent with boundedresponse/readsize guards, but originalmessage was notretained, so exact reason/bytes cannot all be certified.','response_body_upper_bound_with_failures':raw+failed*(P['per_response_max_bytes']+1),'HTTP401_403_429_in_request_logs':sum(r.get('http_status')in[401,403,429]for r in req),'new_company_count':57,'cached_company_cohort':12,'cached_saved_source_receipts':sum(m.get('status')=='SAVED' and m.get('reused',False)for m in sources_meta),'source_receipts_total':len(sources_meta),'source_grade_counts':D['source_verified_periods'],'groups':groups,'external_paid_data':0,'internal_LLM_calls':0,'internal_LLM_tokens':0,'return_evaluations':0,'model_training':0,'new_installs':0}
 cpu=0.;components={}
 for name in ['pilot','decide','expand']:
  p=B/('stage_'+name+'_resource.json');x=json.loads(p.read_text());components[name]=x['CPU_seconds'];cpu+=x['CPU_seconds']
 for name in ['panel_resume','assemble','final_tests','safety']:
  p=B/(name+'_time.txt')
  if p.exists():
   t=p.read_text();u=float(re.search(r'USER_CPU=([\d.]+)',t)[1]);s=float(re.search(r'SYSTEM_CPU=([\d.]+)',t)[1]);components[name]=u+s;cpu+=u+s
 costs['measured_CPU_lower_bound_seconds']=cpu;costs['CPU_components']=components;costs['CPU_limitations']='Initial interrupted panelprocess didnot finalize its CPU record; earlyinteractive inspection/preflight alsounmetered. No exact whole-sessionCPU orzeroCodexcost claim. No multihour training/jobs.'
 costs['Codex_session_usage']='Not metered; separate from0internal researchLLM.'
 dump('collection_audit.json',costs)
 # Calendar-only overlap diagnosis. Pairwise financial durations never duplicate a fiscal event.
 period_overlaps=[];calendar_end_repeats=[];by=defaultdict(list)
 for e in events:by[e['CIK']].append(e)
 for cik,es in by.items():
  es.sort(key=lambda e:e['period_start'])
  for a,b in zip(es,es[1:]):
   if a['period_end']>=b['period_start']:period_overlaps.append([a['event_id'],b['event_id']])
  years=Counter(e['period_end'][:4]for e in es)
  for y,n in years.items():
   if n>1:calendar_end_repeats.append({'CIK':cik,'symbol':es[0]['symbol'],'calendar_end_year':y,'periods':[(e['period_start'],e['period_end'])for e in es if e['period_end'].startswith(y)],'note':'Calendarendyear is not always fiscalyear label. EXEL52week FY2020 ends2021-01-01; next nonoverlapping annualperiod ends2021-12-31. Count distinct periods, not naive calendar duplicates.'})
 assert not period_overlaps
 intervals=sorted([(e['entry_session'],e['exit_H252_session'])for e in labels if e['mask_potentially_usable']]);merged=[]
 for a,b in intervals:
  if merged and a<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],b)
  else:merged.append([a,b])
 dump('dependence_audit.json',{'financial_period_overlaps':period_overlaps,'calendar_end_year_repeats':calendar_end_repeats,'H252_global_connected_calendar_interval_unions':merged,'interpretation':'163issuer-periods/151potential labels are not independentmarketepisodes. Interval unions are mechanical overlap diagnostics, not independent episode count. Annualsource cluster sizes differ.','future_outcomes_computed':False})
 # Explicit source revision/ingestion contract, no forced price-schema admission.
 dump('revision_and_source_gate.json',{'original_plan_sha256':sha(B/'plan.json'),'all_saved_originals_SHA_checked':True,'original_numeric_proofs':4*len(events),'gate':'B1 SHA body+Task9.2 financial_packet.verify_fact+originalCIK/context/USD/signscale/same-accession-date/currentreportDate','V87':'Existing V87 price/canonical contract unchanged; financialraw/scores isolated, not falsely submitted as OHLCV. Originalcache/reference hashes protected; no operating data revision accepted.','publictime':'SEC officialsubmissions filingdate matchedAPIfiled; conservative NYlocalendofday. Raw acceptance preserved, timezone notcertified; no intraday use orfirst-news claim.','versions':'10-K/A is noteligible primary; original currentannualperiod mustmatchsubmissionsreportDate; delayed comparative years rejected, distinctsameissuer intervals preserved. Rawcompanyfacts/submissions retain laterrecords but no laterfinancial version used tooverwriteold decisions. Fullamendment restatement/economic scope lineage audit is not complete.'})
 draft={'id':'TASK13_C3_ACCRUAL_H252_FOLLOWUP_DRAFT','status':'DRAFT_ONLY_NOT_EXECUTED','input_panel':{'path':'runtime/task13_c3/financial_panel.json','sha256':sha(B/'financial_panel.json'),'original_verified_issuers':52,'periods':163,'mask_potential':151},'feature':P['feature'],'direction':1,'H':252,'primary_market':'US_R0_CURRENT_SURVIVOR_NONFINANCIAL_NONREIT','event_unit':'One first-current-original10K perCIK/annualperiod. Actualpaired sample<=151 after all baseline/price checks; no daily-forwardfilled count as independentobs.','signal_clock':'OriginalfilingNYdate endofday; nextactualUSsessionopen entry, exit252sessionslateropen; exactcalendar/native masks cannot be skipped.','controls':'Fixed REV5,MOM20,MOM63,LOWVOL20 and120sessionmarketbeta. Priorclose strictly beforefilingdate for preeventcontrols; nofilled missingprices; actualfinite/variance/pricebasis gate before outcomes.','primary':'Single positive partial event-level rank association between frozenaccrualscore andH252market-relative return controlling forfixedpricefactors+filedyearFE. Do not force sparse dailycrosssectionIC. No sign/horizon/sector/posthocoptimizing.','benchmark_gate':'Use consistentadjustedreturn basis forstocksandmarket. R0 ^GSPCpriceindex is nottotalreturn; stockadjustedvspriceindex mismatchmust notbe labelled marketalpha. Ifmatchedbasis cannot be established, formalrelativealpha evaluation remainsblocked or declared diagnosticunderseparateexplicitcontract, notsilentlyswitched.','statistics':'One primary; preregisterconservative40reservedtrialslots(C1family39+this1), unknownfullhistoricalattempts remainlimitation. HolmFWER.05; bothissuerandcalendarH252overlap sensitivity, >=5000fixedseedresamples whereeffectiveblocks support it. Only4sourcepublicationyearcohorts => intervals/pvalues fragile; no statisticalpower orindependence certification. ExistingTask14stats/B3eventresidualfunctions preferred; no newplatform.','exposure':'2019..2022filings andcorrespondingprices have exposedhistory. Development/historicaldiagnostic, notnewOOS. No candidate/parameter selectionfromoutcomes.','independent_confirmation':'Separate sealed new/as-yet-unobserved filingandmarketcohort needed. Notcreated orregistered inC3. ExistingoperatingShadow isnotreplaced andhistoricalrows are notappended asForwardresults.','execution_cost':'Researchgrossinformation only atfirst; no economics/portfolio claim withoutseparatecost/turnover/tradability andcorrectpricebasis evaluation.','stop':'Ifpairedsample, targetbasis, masks, identity, leakage orincrementaltests fail, stop withcurrent hypothesis; no missingaszero ornewtags, no alternatemodel/horizon.','automatic_next_task':False}
 dump('followup_contract_draft.json',draft)
 # Critical final assessment separates actual data gates from independent evidence.
 critique=[{'issue':'Success==numberofdownloads?','assessment':'REJECT','reason':'Only52issuers163originalmatchedperiods and151calendar/maskpotential arecounted. 57newcompanydownloads/280successfulrequests are notsignals/alpha.'},{'issue':'50/150guaranteesstatisticalpower?','assessment':'REJECT','reason':'CountsmeetconservativeC2screen, but2019/2022publicationcohorts32/29namesvs2020/2021cohorts50/52 andoverlappingH252 endpoints; fewmarketepisodes. No powerclaim.'},{'issue':'Accrualproxy measuresmanipulation?','assessment':'REJECT','reason':'154positive9negativevalues; normaldepreciation,capitalintensity,workingcapital,M&A andNCI/accountingscope canexplaincrosssection. KnownVibefactorfamily; incrementalforecastinformation untested.'},{'issue':'FullPIT/independentalpha ready?','assessment':'LIMIT','reason':'Originalnumbers anddateupperbound reconstructed; current-sourcesurvivors,price/actionbasis andsectorhistory remainpartial. Newfinancialraw does notmake oldpriceoutcomes unseen. Onlylimitedhistoricalexperimentdesign ready; independentconfirmation stillrequiresfreshseal/cohort.'},{'issue':'Local1.2GBstopandresumeconcealed?','assessment':'DISCLOSE','reason':'Initialcollectorstop at264GETpreserved, originalplan/sealsunchanged. Anexecution-onlybytebudgetoverlayusedremaining36withinuserhard300GETandnew80caps. Resumed34GET, final298; nohypothesis/tag/period/direction/samplecriteria changed. Thiswas aninitialcostestimate weakness, notSEC403orproofdataunavailable.'},{'issue':'Unlimitedcollectionneeded?','assessment':'REJECT','reason':'Stopnow:57newcompanies<80,298GET<300; no extra category/source/model. Minimumdata acquired, label/mask/benchmark limitationsexplicit. No alpha/backtest/Factory/Forwardlaunch.'}]
 dump('critical_review.json',critique)
 before=json.loads((B/'protected_before.json').read_text());integrity={};external=[]
 for root,old in before.items():
  files=[p for p in sorted((R/root).rglob('*'))if p.is_file() and '__pycache__'not in p.parts];rows=[(str(p.relative_to(R)),sha(p))for p in files];h=hashlib.sha256(json.dumps(rows).encode()).hexdigest()
  if h!=old['path_content_hash']:
   newer=[p for p in files if p.stat().st_mtime>(B/'protected_before.json').stat().st_mtime];kept=[(str(p.relative_to(R)),sha(p))for p in files if p not in newer]
   if len(kept)==old['files'] and hashlib.sha256(json.dumps(kept).encode()).hexdigest()==old['path_content_hash'] and root=='runtime/task10_1/forward':external.extend(str(p.relative_to(R))for p in newer)
   elif root=='runtime/task10_1/forward':
    ledger=R/root/'wire_reservations.jsonl';rawledger=ledger.read_bytes();matched=None
    # Reconstruct oldrootdigest using each historical line-boundary prefix.
    # Only permit pure append; every other oldfile must match the before digest.
    for n in range(len(rawledger.splitlines(keepends=True))+1):
     prefix=b''.join(rawledger.splitlines(keepends=True)[:n]);restored=sorted(kept+[(str(ledger.relative_to(R)),hashlib.sha256(prefix).hexdigest())],key=lambda item:Path(item[0]))
     if len(restored)==old['files'] and hashlib.sha256(json.dumps(restored).encode()).hexdigest()==old['path_content_hash']:
      matched={'path':str(ledger.relative_to(R)),'old_prefix_bytes':len(prefix),'new_bytes':len(rawledger),'appended_lines':len(rawledger.splitlines())-n,'old_prefix_sha256':hashlib.sha256(prefix).hexdigest()};break
    if matched is None:raise RuntimeError('PROTECTED_STATE_CHANGED_NOT_APPEND '+root)
    dump('external_Forward_append_proof.json',matched)
    external.extend(str(p.relative_to(R))for p in newer)
   else:raise RuntimeError('PROTECTED_STATE_CHANGED '+root)
  integrity[root]=True
 assert sha(B/'plan.json')==(B/'plan.sha256').read_text().strip()
 safe=json.loads((B/'safety_validation.json').read_text());assert safe['compileall_exit']==0 and safe['pytest_exit']==0
 dump('integrity.json',{'original_plan_unchanged':True,'protected_existing_files':sum(x['files']for x in before.values()),'preexisting_C3_changes':0,'external_append_only_ledger_proof':(json.loads((B/'external_Forward_append_proof.json').read_text())if(B/'external_Forward_append_proof.json').exists()else None),'external_running_Forward_appends':external,'operating_DB_writes_by_C3':0,'operating_config_or_strategy_changes':False,'note':'Filehashes establishpreexistingfilepreservation; noSQLoperatingmutation/restore. Normalexternalscheduler mayappendobservations;notcountedasC3performance.'})
 completion={'decision':'RESEARCH_DATA_READY','scope':'LIMITED_HISTORICAL_RESEARCH_FINANCIAL_DATA_NOT_INDEPENDENT_ALPHA','technical':'PASS_SOURCE_NUMERIC_PROVENANCE_AND_FEATURE','financial_panel':'PASS_RECONSTRUCTED_DATE_BOUND_PIT_WITH_SURVIVOR_LIMITS','downstream_experiment':'DESIGN_READY_WITH_EXPLICIT_PRICE_BASELINE_GATES','independent_evidence':'NOT_AVAILABLE_REQUIRES_NEW_UNOBSERVED_COHORT','issuers':52,'original_verified_periods':163,'mask_potential_issuers':52,'mask_potential_periods':151,'return_evaluations':0,'LLM_calls':0,'HTTP_GETs':298,'newcompanies':57,'tests':{'financial_transport_panel':16,'mandatorysafety':24,'compileall':'PASS'},'no_automatic_follow_on':True}
 dump('completion.json',completion)
 report=f'''# Task13-C3 — 발생액 품질 재무 데이터 제한 확장

## 1. 결론

**최종 판정: `RESEARCH_DATA_READY` — 제한적 역사 연구용 재무 자료 준비. 투자 알파 판정이 아니다.**

| 구분 | 실제 확인 범위 |
|---|---|
| SEC 수집·기술 검증 | **PASS**: 같은 원본10-K·CIK·기간·USD·차원 없는 연결기업 context의4개 수치 대사 |
| 시점 적격 재무 패널 | **52기업·163개 서로 다른 기업×연간 회계기간**, 보수적 공시일 경계로 재구성. 전체시장 PIT/생존편향 해소는 아님 |
| 후속 검증 가능성 | **제한 역사 실험 설계 가능**. 기존 날짜/마스크상 **52기업·151기간**이 H252 조건을 가짐. 실제 label/가격 기준선은 미계산이며 최종 평가 표본은 줄 수 있음 |
| 독립적인 알파 증거 | **없음**. 기존 역사 가격은 노출됐으며, 별도 사전 봉인한 새 관측 cohort가 필요 |

C2의50기업·150기간 참고 기준은 원문 패널과 마스크상 잠재 표본 모두 충족했다. 검정력·시장 우위의 증명은 아니다. 추가 데이터 확장을 중단했고, **후속 알파 평가·학습·Task14/15·Factory·Forward를 실행하지 않았다.**

## 2. 수집 실적과 중단·재개

R0 US CORE176과 공식 SEC 티커/CIK 캐시를 사용해 새 요청 전에 [명단·순서·가설·예산](../../runtime/task13_c3/plan.json)을 봉인했다. 현재 업종×현재 규모군 순환, 같은 CIK 주식클래스 중복 제거, 금융업/REIT 사전 별도 부적격, 보수적인 R0 native 이력 시작일 기준을 적용했다. 수익률/기존 투자 의견은 선정에 쓰지 않았다. 현재 업종/규모를 과거의 적격성으로 소급한 시장 패널이 아니다.

C2의16캐시/15기업·80구조기간 기록은 원본 그대로다. C3의 R0·CIK·업종·이력 조건에 들어온 기존 캐시 기업은12개이며 companyfacts 재다운로드0이다.

| 단계 | 조사 기업 | 구조상 가능 기업 | 원문 대사 기업 | 최종 원문 대사 기간 |
|---|---:|---:|---:|---:|
| 기존 캐시 | 12 | 11 | 10 | 35 |
| 신규 파일럿 | 20 | 17 | 15 | 52 |
| 조건부 신규 확장 | 37 | 31 | 27 | 76 |
| 합계 | 69 | 59 | **52** | **163** |

파일럿 종료 시에는 대표 원문1건씩만 확인해15/20기업 적격이었다. 캐시 원문10기업과75% 파일럿 적격률, 남은236요청, 잔여 요청 추정211회를 근거로 **2026-11-17T06:51:12Z `EXPAND`**를 기록한 후 사전 명단의 다음37개만 조사했다. [판정](../../runtime/task13_c3/expansion_decision.json). 표의 기간 수는 이후 같은 기업의 추가 연간 원문 대사까지 포함한 최종치다.

신규 companyfacts는57기업·57회, 전체 Python GET은 **298회(성공280·실패18)**다. submissions49회, 원본HTML146회, 원본 제출패키지46회까지 모두 포함한다. 신규 기업 상한80·요청 상한300을 넘지 않았다. 이전 저장본을 참조한 source receipt32개와 재시작 캐시를 재사용했다. 성공 응답 원시 바이트 합계는 **1,392,786,519 bytes**, 실제 추가 파일은 gzip 중심 약 **108MiB**다. 실패18개는기존수집기의ValueError이며 세부 메시지/전송 바이트가 보존되지 않아 이를0 또는 모두 확정된 동일 원인이라고 쓰지 않는다. 응답 읽기 상한을 적용한 실패 포함 body 총량 상한은 약1.825GB이며 TLS/헤더는 미계측이다.401/403/429는 기록되지 않았다.

초기 로컬1.2GB 전송량 가드가264회에서 중단한 기록을 [initial_budget_stop](../../runtime/task13_c3/initial_budget_stop/)에 보존했다. SEC 장애가 아니며, 사용자가 허용한300회 안의 잔여36회를 계산해 **실행 byte 가드만** 수정했다. 원 plan/SHA·기업·기간·가설·태그·방향·H252·최소 표본은 변경하지 않았다. [비용 수정](../../runtime/task13_c3/execution_byte_budget.json). 재개 후34회로 완결했으며 남은2회를 채우려 추가 요청하지 않았다. 원본 수집량을 처음에 과소 추정한 설계 한계다.

## 3. 원문·시점·회계 품질

기존 **B1 Sources → equities.fetch**, 같은 SEC 설정·User-Agent·연락처·유한 재시도, B1 `body` SHA 검사와 inline 숫자 파서를 재사용했다. 새 downloader·서비스·DB·설치는 없다. 설정/연락처는 보고서에 복사하지 않았다. 네트워크 상한·캐시·중단 재개·3회 권한 실패 circuit을 검증했다.

- companyfacts에서 form10-K, filed2017~2022,300~430일의 같은 연간 NI/CFO·USD·accession·filed를 찾고 기초/기말 Assets를 같은 제출본에서 연결했다. source 값은 [financial_packet.verify_fact](../../src/quant_harness/investment/financial_packet.py)로 대사했다.
- SEC submissions의 CIK/현재 ticker·원 form·공시일·reportDate를 대사해 현재 연간 기간만 선택했다. 늦게 다시 실린 비교연도·10-K/A를 새로운 독립 기간으로 세지 않았다. 원 source에 있는 뒤의 값으로 과거 값을 대체하지 않았다.
- 원본 HTML의 inline 값 또는 공식 제출패키지의 legacy XBRL에서 **CIK·차원 없는 기업 context·기간·USD 단위·sign/scale·동일 숫자**를 확인했다. 총 **652개 회계값**의 원문 연결을 보존했다. 상충 값은 임의 선택하지 않았다.
- 오래된 HTML에는 inline XBRL이 없어 SEC metadata로 legacy를 식별하고 원본 패키지를 직접 선택했다. SGML `<XBRL>` wrapper만 해제하는 작은 adapter를 추가했다. 원본/수식/숫자를 수정하지 않았다.
- 정확한 공개 분/초를 인증하지 않은 행은 **공식 제출일 뉴욕 현지23:59:59 이후** 이용 가능으로 처리한다. acceptance 문자열은 보존하지만 timezone을 추정하지 않았다. 이전 실적 보도자료보다 최초 뉴스라는 주장도 없다.

자료가 구조상 가능한 기업59개 중 원문 조건을 만족한 기업은52개다. 고정 태그 부재10기업, 원문 unavailable15시도·값/범위/기간 충돌6시도·CIK 미확인1시도를 별도로 보존했다. 한 기업의 실패와 한 기간의 실패를 혼동하지 않는다. 태그 누락을0으로 채우거나 다른 이익 지표로 교체하지 않았다.

원문 수치와 공시일을 재구성한 **제한 PIT**다. contemporaneous 수집 원본, 전체 수정계보·산업/기업행사·상장폐지 이력의 인증이 아니다. M&A·중단사업·비지배지분·정상 감가상각/운전자본 투자에 따른 경제적 비교 가능성은 미완성이다. R0/B3의 가격·마스크를 수정하거나 B3 전용 overlay를 일반 적용하지 않았다. V87의 운영 OHLCV 계약도 변경/강제 적용하지 않았으며 재무 source는 연구용 격리 revision gate를 사용했다.

## 4. Feature-only 진단

`-(NetIncomeLoss-OperatingCashFlow)/((Assets_start+Assets_end)/2)`를 Decimal로 재현했다. 이익조작/분식을 직접 측정하지 않는다. Vibe `fundamental/accruals.py`와 같은 알려진 cash-accrual 계열이며 새로운 독자 알파가 아니다. [재무 패널](../../runtime/task13_c3/financial_panel.csv), [원문/시점 연결](../../runtime/task13_c3/financial_panel.json).

| 제출연도 | 원문 대사 기업/기간 |
|---|---:|
| 2019 | 32 /32 |
| 2020 | 50 /50 |
| 2021 | 52 /52 |
| 2022 | 29 /29 |

공통 횡단면이 모든 연도에50개인 것은 아니다.2017~2018공시 원문은 최종 패널에 없으며 실제 범위를2019~2022로 보고한다. distinct 회계기간은 겹치지 않았다. EXEL의52주 회계연도 두 개가 모두2021년에 종료되므로, 단순 종료 달력연도를 진짜 fiscal-year 번호로 취급하지 않았다.

Feature 평균 **0.06017**, 표준편차 **0.06844**, 최소/중앙/최대 **−0.26411 /0.05210 /0.35979**다. 유한 값163개, 양수154·음수9·0값0, abs>1은0이었다. 제거/보간/winsorization은 하지 않았다. 현재 업종별 기간 수는필수소비33·경기소비29·IT23·헬스케어23·통신20·산업재11·에너지10·유틸리티8·소재6으로 불균형하다. 현재 분류를 과거 투자 통제로 인증하지 않는다.

기존 자료의 **날짜열과 품질/native mask만** 읽어 next-session→252세션 후의 구간 존재를 확인했다. 수익률 값은 모두null이다.163개 중 **151개·52기업**이 잠재 사용 가능하며,12개는 기존 stock mask4·index mask7·기준선 warmup1에서 제외됐다. [H252 가용성](../../runtime/task13_c3/label_availability.json). 실제 price basis·finite baseline·variance를 확인하면 표본은 더 줄 수 있다. 라벨이 계산됐거나 실제 체결 가격이 인증됐다는 뜻이 아니다.

151개가 독립 시장 사례는 아니다. 같은 회사의 반복 연간 정보와H252 구간, 여러 기업의 공통 시장 충격이 겹친다.4개 제출연도·서로 겹치는 시장 구간만으로 검정력을 확정할 수 없다.

## 5. 다음 연구 판단과 자체 비판

**한 번의 제한적 역사 알파 파일럿을 설계할 재무 자료는 확보했다.** [계약 초안](../../runtime/task13_c3/followup_contract_draft.json)은 기존 방향·H252, 공시일 이후 진입, 원래의 같은 source·마스크, REV5/MOM20/MOM63/LOWVOL20/beta 통제, 기업·시간 의존성과 다중검정을 고정하도록 했다. 날짜가 다른 사건에 일별 RankIC를 억지로 적용하지 않는다. 현재 단계는 설계이며 실행하지 않았다.

원자료/가격은 이미 노출됐으므로 새 독립 Holdout으로 부를 수 없다. 진정한 독립 확증은 이후 별도 봉인한 미관측 공시/시장 cohort에서 필요하다. 특히 R0 조정주가와 S&P500 가격지수의 배당/수익률 기준 차이, 기업행사, 실제 finite 기준선은 평가 전에 대사해야 하며, 기준이 맞지 않으면 정식 시장대비 알파 판정은 차단한다. 단순 gross 차이를 비용 후 투자 성과로 승격하지 않는다.

가장 유력한 경제적 실패 원인은 이 proxy가 기존 가격 신호 밖의 정보를 주지 못하거나 **정상 감가상각·자본집약도·운전자본/M&A 차이**를 잡는 것이다.154/163의 양수 분포도 이익조작의 빈도나 좋은 주식 비율이 아니다.50/150통과를 충분한 검정력으로 해석하는 것, 현재 업종/생존기업을 전체시장으로 일반화하는 것, 신규 원문을 미노출 가격으로 취급하는 것을 모두 기각했다. [비판 검토](../../runtime/task13_c3/critical_review.json).

추가 데이터 카테고리·엔진 경쟁·플랫폼 구축은 필요성이 입증되지 않았다. 지금은 수집을 더 넓히지 않으며, 후속 작업은 별도 승인된 단일 가설 평가 범위를 넘어 자동 진행하지 않는다.

## 6. 무결성·테스트·비용

재무/transport/실제 패널 시험 **16개**, AGENTS 필수 안전 회귀 **24개**, compileall 통과. 실제 검사 범위는계정 단위·부호/scale·연결 context/CIK·연간기간·제출일·원접수번호·지연 비교/수정본 배제·원문 SHA·누락/상충·캐시·재시작·요청한도/circuit·H252날짜경계다. 모든 산업/기업행사·intraday 공개시각·모든 정정의 경제적 영향·독립 알파는 검증하지 않았다. 초기 XPath namespace 오류 시험4실패와 준비 중단 로그를 남기고 최소 수정 후 재시험했다. 실패를 성공으로 집계하지 않았다.

계측 CPU 하한 **{cpu:.1f}초**다. 최초 중단된 panel 과정과 초기 대화형 진단의 CPU가 모두 기록되지 않아 전체 정확한 합계로 쓰지 않았다. 내부 연구 LLM **0회/0토큰**, 엔진·학습·백테스트·신규 알파 평가0, 유료 서비스0이다. Codex 본 세션 토큰/비용은 미계측이다.

기존 코드/설정/Factory·Paper·R0~R2/B/C1/C2 고정 파일은 hash로 보존했다. 정상 운영 스케줄러가 Forward calendar/tick 파일을 추가하고 wire 예약 원장에 append했다. 기존 원장의 모든 줄이 동일한 prefix임을 이전 root hash로 증명했다. 이 운영 추가분은 C3 성과로 사용하지 않았으며 원장 전체 hash가 불변이라고 주장하지 않는다. 운영 DB에 직접 쓰거나 전략·권한·Live hardlock을 변경하지 않았다. 새 raw·receipt·계약·패널·실패·코드 SHA는 [manifest](../../runtime/task13_c3/artifact_manifest.json)에 보존한다.

재현 코드: [plan](../../experiments/task13_c3/plan.py), [기존 transport adapter](../../experiments/task13_c3/common.py), [원문 회계 검증](../../experiments/task13_c3/accounting.py), [수집](../../experiments/task13_c3/collect.py), [feature/가용성](../../experiments/task13_c3/assemble.py). 이미 수집한 source는 SHA검증 후 재사용한다. 본 작업에서 후속 평가 명령은 실행하지 않았다.
'''
 path=R/'docs/development/13_C3_accrual_data_expansion.md';path.write_text(report)
 files=[p for p in B.rglob('*')if p.is_file()and p.name!='artifact_manifest.json'and '__pycache__'not in p.parts]+list((R/'experiments/task13_c3').glob('*.py'))+[path]
 dump('artifact_manifest.json',{'files':{str(p.relative_to(R)):sha(p)for p in sorted(files)},'scope':'Source/financialfeature readiness, notalpha performance','wire_GETs':298,'old_research_not_overwritten':True})
 print(completion['decision'],'files',len(files),'storage_MiB',sum(p.stat().st_size for p in files)/1048576,'externalForwardAppends',len(external))
if __name__=='__main__':main()

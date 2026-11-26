from protocol import *
research_seal()
def table(h,rows):return '| '+' | '.join(h)+' |\n| '+' | '.join(['---']*len(h))+' |\n'+'\n'.join('| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in r)+' |' for r in rows)+'\n'
def pct(v):return '미산출' if v is None else f'{v*100:+.2f}%'
def pp(v):return '미산출' if v is None else f'{v*100:+.2f}pp'
def load(p):return json.loads((B/p).read_text())
research={m:load('research/'+m+'.json') for m in ['US','KR']};port=load('evaluation_v2/portfolios.json');stocks=load('evaluation_v2/asset_returns.json');rel=load('evaluation_v2/relative.json');scores=load('evaluation_v2/hypothesis_scores.json');aud=load('discovery_audit.json');usage=load('usage.json');old=load('evaluation_v2/task93_descriptive_comparison.json');version=load('original_version.json')
name={a['symbol']:a['name'] for a in asset_list()};selected=[x for m in ['US','KR'] for x in research[m]['selected']]
def asset(s,h):return next(x for x in stocks if x['symbol']==s and x['horizon']==h)
text='''# Task 9.4 — 팀2(Vibe) 독립 발굴·상대 성과 진단

## 핵심 판정

**기존 제한 후보에서 벗어난 발굴은 확인했지만, 우수한 투자 연구 능력은 입증하지 못했다.** 미국 AIR·ETN·GEV, 한국 LS일렉트릭·삼양식품·케이씨텍을 최종 선정했다. 2026-05-18 시가부터 11-13 종가까지 고정 동일 비중 연구 포트폴리오는 미국 비용 후 **-10.67%**(S&P500 **+1.98%**), 한국 **-17.32%**(KOSPI **-28.92%**)였다. 한국은 지수보다 덜 하락했으나 손실·큰 낙폭이 발생했다. 이는 팀2의 비중 추천이나 실제 거래 결과가 아니다.

- **Discovery: PASS(제한적 기능 실증).** 날짜 검증 자료를 검색해 미국18·한국28기업을 발견하고10·8기업을 심층 대상으로 삼았다. 기존 Task93 전체 스크린 밖에서 미국3개·한국1개 최종 기업이 나왔다. 넓은 시장을 완전히 조사했다는 의미는 아니다.
- **Research: PARTIAL.** 6개 기업의 분기 수치 예측·촉매·반증 조건을 봉인하고 실제 발표값과 대조했다. 범위 내3/6, 상방 과소예측3/6이었다. 6개 모두 주당가치 시나리오는 미완성이다. 가격에 반영된 기대와 기대수익의 근거는 부족하다. 일부 원문·발표 시각 검증도 부분적이다.
- **Relative Selection: PARTIAL / 미국 우위 미확인.** 미국 전체 포트폴리오는 지수를 하회했다. AIR은 항공우주ETF를 이겼지만 조건부 비교 대상 TDG에는 뒤졌다. 한국 LS·케이씨텍은 각 ETF를 이겼으나, 직접 경쟁사 식별 및 삼양식품 대조군 가격에 공백이 있어 전체 상대 선정 능력을 확정할 수 없다.

원본 Vibe **WebSearchTool·ChatLLM·스킬을 실제 사용**했고 PIT 필터·자료 연결은 호스트 어댑터가 수행했다. 원본 전체 Research Autopilot의 자율 실행 성공이라고 주장하지 않는다. 신규 전용 가격 API 조회는 양 시장 봉인 이후 수행했다. 현재 검색이 반환한 미래 스니펫에 코디네이터가 간접 노출됐고 Task93 결과도 이미 알려져 있었다. 해당 내용을 연구 모델 입력에서 제외했지만 **완전한 맹검·독립 알파 실험이 아니다.**

## 1. 실행 구조·버전·예산

'''
text+=f"원본 Vibe checkout은 `{version['commit']}`다. 원본 검색 코드의 설치본/checkout SHA256을 대조했다. 기존 `HYBRID_MINIMAL`을 유지했으며 팀3·운영·Factory·Paper·Live 경로에는 변경을 하지 않았다. 모델은 기존 Codex 구독의 `gpt-6.1-terra`다.\n\n"
text+='''흐름은 검색계획 → 실제 원본 검색/공개 자료 회수 → 미래 기사 제외 → 기업 발굴 → 추가 자료/재무 검증 → 최종 연구·비교 목록 봉인 → 결정론적 가격·실적 평가다. QuantaAlpha/RD-Agent의 적격한 과거 알파를 새로 생성하거나 사용하지 않았다. 기술적 이상 징후를 통한 별도 정량 발굴도 이번 실행에는 포함하지 않았다.

'''
text+=table(['항목','실측'],[['모델 계획/상한','6회 계획 → KR 범위 교정·전송 실패 재시도로8회, 추가 호출 종료'],['실제 호출',f"성공 전송{usage['successful_transport']} / 실패{usage['failed']}"],['총 사용량',f"{usage['measured_total_tokens']:,}tokens = 입력{usage['input_tokens']:,} + 출력{usage['output_tokens']:,}; cache입력{usage['cached_input_tokens']:,}(입력에 포함)"],['비용','구독 이용, 별도 유료 API/데이터 구매 없음. 증분 달러 비용은 단가가 없어 미산출'],['오류','초기 KR 계획에 US 질의 포함 → 별도 교정. KR 최종1회100,955tokens로회당90kguard초과→FAILED 보존; 동일 수치를 사전 압축해 마지막1회로 재시도'],['검색','원본 broad6+target8질의/시장. 호스트 보완 검색 별도; 원래queryguide초과를 숨기지 않음'],['기업 가설당 호출량','선정6개 기준 전체약77,597tokens/가설; 실패·계획 포함, 투자 유효성의 비용 지표는 아님']])
text+='''[사전 계약](../../experiments/task9_4/contract.json), [호출 사용량](../../runtime/task9_4/usage.json), [실패·재시도](../../runtime/task9_4/KR_retry_provenance.json), [원본 버전](../../runtime/task9_4/original_version.json), [원본 검색 산출물](../../runtime/task9_4/native_search_evidence/).

## 2. 당시 시장·산업 방향과 실제 발견

미국은 전력기기 주문/백로그, 항공정비·부품, 공조, 주택·타이틀보험, 식품유통, 의료기기를 탐색했다. 전력 투자의 수주 전환과 항공 aftermarket의 유기 성장에 더 강한 근거가 있다고 최종 판단했다. 주택 부문의 활동 회복은 마진·금리 위험과 구분했고, 물 인프라 자금 부족 자체를 특정 회사 실적 개선으로 보지 않았다.

한국은 전력기기·반도체 장비·식품 수출·건설·바이오를 독립 탐색했다. 전력 수주 전환, 실제 반도체 장비 인식, 수출 식품 성장에 주목했다. 반도체 CAPEX 추정은 집행 실적과 구분했고, 건설의 충당금·수익 인식 및 바이오의 조건부 마일스톤을 반복 이익으로 취급하지 않았다. 조선의 날짜 적격 근거는 확보하지 못했다. 거시는 당시 공식 정책 발표를 제한적으로 재사용했으며 수급·컨센서스·내러티브 전체를 충분히 확보한 것은 아니다.

'''
text+=table(['시장','초기 발견','심층','최종','Task93전체스크린','그 밖의 최종 종목'],[[r['market'],r['initial_discovered_count'],r['deeper_selected_count'],r['final_promising_count'],r['old_Task93_screen_count'],', '.join(r['selected_outside_old_screen'])] for r in aud])
for r in aud:
 text+=f"\n**{r['market']} 초기 발견 명단:** "+' · '.join(x['name'] for x in r['all_broad_candidates'])+'。\n'
text+='''
미국18개는20개 가이드보다 적다. 숫자를 채우기 위해 무근거 회사를 추가하지 않았다. 산업 레이블은 모델의 서술 분류이며 표준 GICS 업종 수로 집계하지 않았다. 초기 발견은 심층 분석·투자 적격성 검증과 구분한다.

심층 대상은 미국 AIR/ETN/GEV/MAIR/OTIS/GEHC/PHM/STC/TILE/USFD, 한국 삼성바이오로직스/알테오젠/대우건설/현대건설/삼양식품/동원F&B/케이씨텍/LS일렉트릭이다. 최종 제외에서 MAIR은 유기 성장과 인수 기여·IPO 자본구조, PHM은 마진 압박, 알테오젠은 조건부 마일스톤·희석, 대우건설은 손실·충당금 불확실성, 현대건설은 매출·수주 감소를 기록했다. 동원F&B는 가격 누락 자체가 아니라 이익 감소와 원가 부담을 이유로 우선순위를 낮췄다. 자료가 부족한 다른 기업은 `INSUFFICIENT_DATA`로 남겼다.

[전체 발견·제외 사유](../../runtime/task9_4/discovery_audit.json), [미국 원본 최종 연구](../../runtime/task9_4/research/US.json), [한국 원본 최종 연구](../../runtime/task9_4/research/KR.json).

## 3. 최종 기업별 가설·근거·한계

'''
text+=table(['기업','공개된 변화와 독립 가설','주요 반대 근거'],[
['AIR','3/24 원본 FYQ3: 유기 조정매출+14%, 부품·정비 성장. 기존 고객 계약·확장 시설이 매출·이익으로 전환될 가설.','인수·인력·재고·정비 실행. 역사적 평균 희석주식으로 계산한 EV는 현재 가치가 아님.'],
['ETN','5/5 공식 일부 발췌: 유기매출+10%, Electrical Americas주문+42%, 전력 백로그 증가. 납품 전환 가설.','인수효과·생산능력·자본구조 부족. 주문 증가와 적정 주가의 관계 미완성.'],
['GEV','4/22 공식 일부 발췌: 유기 주문+71%, 가스터빈 백로그+예약100GW. 예약의 확정 주문 전환 가설.','인수 포함 백로그·비경상 이익·선수금. 예약을 확정 매출로 오인하면 안 됨.'],
['LS일렉트릭','4/26~29 기사: Q1매출/영업이익+33%/+45%, 전력 수주 확대. 납품·마진 유지 가설.','원가·납기·고객 집중. 확정 순희석주식·정상화 FCF 부족.'],
['삼양식품','5/14 기사: Q1매출7,144억원·영업이익1,771억원. 수출 수요가 원가 상승에도 매출을 지지할 가설.','환율·포장/원재료·공장 현금 소요. 시장 기대 대비 추가 성장 평가 부족.'],
['케이씨텍','5/13 기사: 반도체부문 매출이 전분기687.3→1,472.3억원. 실제 장비 공급·소재 매출 지속 가설.','장비 인식 시점·국내 고객 집중·CAPEX 지연. 대형 고객 투자 전망과 개별 주문을 구분.']])
text+='''
한국 연간 재무395개와 AIR 수치5개는 Task92 `verify_fact`로 값·단위·기간·기준·원문 위치·해시를 확인했다. 이는 의미적 회계 감사의 완결을 뜻하지 않는다. LS 별칭 `엘에스일렉트릭`을 복구했고 삼성바이오의 API 최신5/15정정 자료는 제외한 뒤4/23자료를 대체 확보했다. 주식수 누락을 발굴 탈락 규칙으로 사용하지 않았다.

6개 모두 Bear/Base/Bull 주당가치는 null이다. AIR의 5/15가격104.55×평균희석주식39.5m, 순부채816.5m을 쓰면 proxy EV약4,946.225m/TTM조정EBITDA376.2m≈13.15배다. 이는 현재 희석·리스가 검증된 내재가치나 목표가가 아니다. 나머지도 자본구조·지속 가능한 현금흐름·시장 기대를 충분히 연결하지 못했다. 계산은 [산술 대사](../../runtime/task9_4/evaluation_v2/valuation_arithmetic.json)에 보존했다. 새 DCF를 강제로 만들거나 원본 valuation 도구 실행 성공으로 표시하지 않았다.

주요 당시 출처: [AAR3/24](https://www.aarcorp.com/globalassets/investors/earnings/fy-2026-q3-results/aar-reports-third-quarter-fiscal-year-2026-results.pdf), [Eaton5/5](https://www.sec.gov/Archives/edgar/data/1551182/000155118226000010/etn03312026exhibit99.htm), [GEV4/22](https://www.sec.gov/Archives/edgar/data/1996810/000199681026000063/gevpressrelease1q26.htm), [전력기기4/28](https://www.hankyung.com/article/2026042833721), [식품5/14](https://news.nate.com/view/20260514n31174), [케이씨텍5/13](https://www.thelec.kr/news/articleView.html?idxno=56550). 수집은 현재이며 과거 최초 관측 원본을 보유했던 것으로 표시하지 않았다.

## 4. 봉인·가격·비용 계약

양 시장의 최종 모델 입력·출력·비교 목록을 [research_seal.json](../../runtime/task9_4/research_seal.json)에 해시로 봉인한 뒤 평가 전용 자료를 조회했다. 이후 LLM 판단은0회다. 팀2가 비중·매매 시점을 결정하지 않았다.

평가 시작은 양 시장5/18시가, 1개월6/18종가, 3개월8/18종가, 약6개월11/13종가다. 정확한6개월인11/18까지 외삽하지 않았다. 재선정·중간 거래·리밸런싱 없이 top3각1/3 고정 슬롯, 미선정/가격불가 슬롯 현금·재분배 금지다. 이번 최종6개는 모두 가격이 있어 연구 노출100%였다.

주 비교는 모든 주식·ETF·지수의 **배당/분배금 제외 가격 수익**이다. Total Return 알파나 실제 세후 성과가 아니다. 미국 매수/매도6bp씩, 한국 주식6.5/26.5bp를 자금 조달까지 포함해 기존 static `mix` 함수로 계산했다. 호가·시장충격 실측이 아닌 사전 고정 가정이다. gross와net을 모두 제시하고, net대지수gross 비교를 명시한다. ETF는 대조군으로만 사용했다.

Yahoo/Toss(한국Naver 추가)의 시가·종가 두 출처0.5%합의를 재사용하고 누락·충돌은 보간하지 않았다. V87 형식·revision gate는 주식/ETF에 적용했고 지수는 해당 계약 적용 대상이 아니다. 미국 S&P500은 단일 공급자, 한국 지수는 기존 두 출처 자료를 대사했다. 이는 거래소 원본 PIT 인증이나 완전한 상폐/기업행사 감사가 아니다.

ITA는11/5 **3:1분할**로 Yahoo의 소급 조정 가격과 Toss명목 가격이 달라 최초 평가에서 차단됐다. [OCC60055/MIAX공식 통지](https://www.miaxglobal.com/sites/default/files/alert-files/ITA_Split_60055.pdf)를 확보해 분할 전 Yahoo값×3을 명목 가격과 대사하고 분할 후 수량×3을 반영했다. [최초 차단 V1](../../runtime/task9_4/evaluation/asset_returns.json)을 남기고 [V2근거](../../runtime/task9_4/evaluator_only/ITA/resolution_v2.json)를 별도 생성했다. 종목·기간·비용을 변경하지 않았다. 동원F&B는 Yahoo/Toss실패·Naver빈자료로 비교 불가이며 다른 종목으로 대체하지 않았다.

## 5. 실제 가격 성과

'''
text+=table(['시장/종목','1개월','3개월','약6개월','6개월 지수초과 gross','MDD'],[[('US' if not x['symbol'].endswith('.KS') else 'KR')+' '+x['name']]+[pct(asset(x['symbol'],h)['price_return']) for h in ['1m','3m','6m']]+[pp(next(r for r in rel if r['symbol']==x['symbol'] and r['horizon']=='6m')['excess_market']),pct(asset(x['symbol'],'6m').get('mdd'))] for x in selected])
text+='\n'+table(['시장/기간','top3gross','top3net','지수100%gross','net초과','현금'],[[x['market']+' '+x['horizon'],pct(x['gross_price_return']),pct(x['net_price_return']),pct(x['benchmark_price_return']),pp(x['excess_vs_full_index']),pct(x['cash_target'])] for x in port])
text+='\n'+table(['6개월 계좌','MDD','Sharpe rf0진단','비용 효과','종목별 gross기여'],[[x['market'],pct(x.get('mdd_observed_marks')),round(x['sharpe_rf0_diagnostic'],3) if x.get('sharpe_rf0_diagnostic') is not None else '미산출',pp(-x['cost_effect']),'; '.join(s+':'+pp(v) for s,v in x['contribution_gross'].items())] for x in port if x['horizon']=='6m'])
text+='''
동일 초기 주식 노출100%이므로 지수+현금 대조군은 지수100%와 같다. 한국 성과를 현금 회피 성과로 해석할 수 없다. 종목 선택 gross잔차는 미국-12.54pp, 한국+11.88pp다. 변동성·MDD는 종가 및 최초 시가 기준이며 장중 손실은 측정하지 않는다. 한국 케이씨텍 자체 MDD가 매우 커서 ETF를 이겼다는 사실을 위험조정 알파로 해석할 수 없다.

[모든 자산1/3/6개월·변동성·원가격](../../runtime/task9_4/evaluation_v2/asset_returns.json), [계좌지표](../../runtime/task9_4/evaluation_v2/portfolios.json), [NAV CSV](../../runtime/task9_4/evaluation_v2/).

## 6. 기업·ETF·테마 대안 비교

모두 미래 가격 조회 전 모델이 선정한 비교자다. AIR/TDG는 정비업과 부품 OEM의 사업 차이가 있어 완전한 직접 경쟁 관계가 아니다. GEV/ETN도 전력기기 일부 범위만 겹친다. 한국 LS/케이씨텍의 설비투자 연결, 삼양/삼성바이오의 수출 연결은 넓은 간접 테마여서 좋은 대안 비교로 확정하지 않았다. 미확인 비교명을 사후 ticker로 확장하지 않았다.

'''
rr=[]
for x in rel:
 if x['horizon']!='6m':continue
 for a in x['comparators']:
  gap=a.get('gap_percentage_points');rr.append([name[x['symbol']],a['symbol'] or a.get('relation')+'(코드미확인)',a['relation'],pct(a['price_return']),f'{gap:+.2f}pp' if gap is not None else '미산출',a.get('verification') or '미확인'])
text+=table(['선정 기업','대조군','관계','대조군6개월','선정-대조','검증 한계'],rr)
text+='''
AIR은 ITA대비+5.02pp, TDG대비-2.91pp다(조건부 peer가격순위2/2). ETN은 GEV보다+12.08pp로조건부1/2, GEV는2/2다. 이 순위는 관계가 확인된 전체 경쟁사 모집단의 순위가 아니다. LS는 전력ETF대비+4.94pp지만 KOSPI를 크게 하회했고, 케이씨텍은 반도체ETF대비+44.44pp였다. 삼양의 직접 식품 대조군은 가격이 없어 순위를 계산하지 않았다.

ETF존재는 iShares Jan2026자료/2025말기준 목록과 한국4/13·4/20 ETF보고서로 확인했다. **ETF가 선정 회사를 실제 포함하는지와5/15가중치는 모두 미확인**이다. 이 중복을 제거한 초과성과는 계산하지 않았다. ETN/GEV·삼양의 적절한 ETF와 한국 직접 peer의 코드 확인은 미완료다. 잘못 연결된 한국 연금상품 PDF는 관련 산업 근거에서 제외했다.

[모든 기간의 상대 비교·조건부 순위](../../runtime/task9_4/evaluation_v2/relative.json), [선정 당시 ETF자료](../../runtime/task9_4/ETF_identity_preseal.json), [iShares원문](https://www.ishares.com/us/literature/presentation/ishares-sector-and-industry-etfs.pdf), [한국4/20보고서](https://bbn.kiwoom.com/rfTP743).

## 7. 사업 가설·예측과 실제 실적의 분리

'''
text+=table(['기업','봉인 지표/기간','Low/Base/High','실제','발표일','결과'],[[name[x['symbol']],x['sealed_prediction']['metric']+' / '+x['sealed_prediction']['period_end'],f"{x['sealed_prediction']['low']} / {x['sealed_prediction']['base']} / {x['sealed_prediction']['high']} {x['sealed_prediction']['unit']}",round(x['actual']['value'],4),x['actual']['published'],x['range_diagnostic']] for x in scores])
text+='''
AIR은 FYQ4 유기 **조정** 매출13%를 사용했다. 연결 명목 매출23%, 연간14%, 부품 부문19%와 혼동하지 않았다. ETN은 연결 유기19%로인수/환율 및 부문 수치를 구분했다. GEV는확정 백로그64+예약58=122GW로연말130GW가이던스와 구분했다. 한국은 연결3개월 매출이며 케이씨텍의누계3,829억원을분기1,141.87억원으로오인하지 않았다.

AIR의조정영업이익률10.6%는반증기준9%이상이다(GAAP8.6%와다름). LS실제영업이익률약12.44%는6%이상,삼양약24.78%는18%이상이며6개모두사전수치반증조건은충족되지않았다. 그러나 가설 전체의 확정 적중이나 주가 상승 원인 검증을 의미하지 않는다. GEV의 예약 취소·마진·현금 전환 등 정성 위험의 완전 감사는 남아 있다.

범위 적중3/6은 넓이가 다른 임의 시나리오의 진단이며 확률 calibration·가이던스/컨센서스 대비 우위가 아니다. LS·ETN·GEV는 성장 강도를 과소추정했다. 좋은 사업 변화가 있었는데도 ETN·GEV·LS의가격수익은 음수였다. **시장 기대·현재 가치 대비 가격을 충분히 산정하지 못한 것은 확인된 연구 공백**이나 실제 주가 부진의 원인을 고평가 하나로 단정할 근거는 없다(`UNDETERMINED`). 과거 LLM 지식의 영향도 제거하지 못했다.

실현 자료 신뢰도: AIR원본, LS/삼양DART원문잠정실적, 케이씨텍DART수치원문을 확보했다. 케이씨텍11/13당일공개시각은미러의장중시각과API날짜를교차참고했으나공식시각원문은미확인이다. ETN·GEV는호스트다운로드실패를남기고공식사이트/SEC의웹발췌로대조했다. 모두부분적시점/원문제약을보존했다.

실현 출처: [AIR7/21](https://www.aarcorp.com/en/newsroom/press-releases/2026/aar-reports-fourth-quarter-and-fiscal-year-2026-results/), [ETN11/3](https://www.eaton.com/us/en-us/company/news-insights/news-releases/2026/eaton-reports-record-third-quarter-2026-results.html), [GEV10/28SEC](https://www.sec.gov/Archives/edgar/data/1996810/000199681026000162/gevpressrelease3q26.htm), [LS10/21DART](https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261021800151), [삼양11/6DART](https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261106800605), [케이씨텍11/13DART](https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261113000561).

[원문수치/오차](../../runtime/task9_4/evaluation_v2/hypothesis_scores.json), [반증조건대사](../../runtime/task9_4/evaluation_v2/invalidation.json), [실현수치검증](../../runtime/task9_4/evaluation_v2/verified_actual_facts.json).

## 8. Task93 대비 변화·남은 실패 원인

Task93의 제출순서·해시 표본·고정5개 분석을 이번 선정 규칙으로 쓰지 않았다. 검색 기반 산업 변화에서 출발했고, 깊이·선정 수를강제하지 않았다. 원본검색은날짜연산자를무시하거나무관한2FA페이지를반환하기도했다. 이를격리한호스트필터의기여가커서원본Vibe단독의무인발굴능력으로확대해석할수없다.

Task93의 **최초 top3를 고정 보유했다고 가정한 대조군**만 같은 시가/종가·고정비용으로 재계산했다. 기존 Task93의 동적 운용·월별교체·공식 판단 결과를 수정하거나 다음 숫자로 대체하지 않았다.

'''
text+=table(['시장','Task93최초top3','그정적net','Task94정적net','관측차이(인과아님)'],[[r['market'],', '.join(r['old_initial_top3']),pct(r['old_static_initial_top3_result']['net_price_return']),pct(r['Task94_new_static_net']),pp(r['observed_net_difference'])] for r in old])
text+='''
이 차이는 서로 다른 후보·자료·호출량에 관한 서술 비교다. Task93결과를이미알고수행했으며동일조건AB·독립개선성공이아니다. 이번에미국은시장보다부진해, 이전대조군보다손실이작다는사실만으로선정능력이검증되지않는다. 한국도기존동적계좌또는기존역사실험과섞지않는다. [재계산근거](../../runtime/task9_4/evaluation_v2/task93_descriptive_comparison.json).

원인별판정:

| 영역 | 확인된 것 | 아직 확정할 수 없는 것 |
| --- | --- | --- |
| 발굴 | 새기업·산업근거확보,그러나검색오류·미래기사·산업범위누락 | 시장내최선기업발굴,놓친기회의전체규모 |
| 미래사업 | 분기수치봉인·실현대조,상방과소추정3건 | 독립Forward예측우위,장기가치전망적중 |
| 가격/기대 | 6기업주당가치미완성·컨센서스희소 | 부진이이미반영된기대/할인율/외부충격중어느원인인가 |
| 상대선정 | 미국지수하회,한국지수상회·일부ETF상회 | 완전한직접경쟁사/위험일치기준의알파 |
| 비용/실행 | 사전비용미국약0.11pp·한국약0.27pp효과,매매판단없음 | 실제호가/체결·세금원장의성과 |
| 데이터 | 현재재수집·부분기업행사대사·지수단일소스제약 | 완전한PIT유니버스·상폐/분배금포함성과 |

우선개선은선정후반복매매가아니라,①최종후보의자본구조·정상화현금흐름·당시기대를보강해가격매력을계산②직접peer코드·사업범위·datedETF편입목록을봉인전에완결③검색의미래/무관결과비율을줄이는것이다. 새상시서비스·새전략·Factory작업을추가하지않았다. 사후미발굴상승주를최초성과에합산하지않았고별도의사후우승주탐색도실행하지않았다.

## 9. 테스트·보존·재현

AGENTS최소안전4suite **24개통과**. 신규프로토콜은최종 **9개통과**(초기5개와중복이므로총고유33개). compileall통과. 실패·skip·timeout을PASS로바꾸지않았다. 운영코드를변경하지않아DB·실주문·운영스케줄통합시험은이번에실행하지않았다. 모델실패1회·원본다운로드실패·동원가격미확보는별도기록했다.

- [안전/초기프로토콜29개로그](../../runtime/task9_4/tests.log), [최종프로토콜9개](../../runtime/task9_4/protocol_tests.xml).
- Task93 manifest **1,564개해시일치**. Task93판단·성과·연구원장·운영전략·승격정책불변.
- 전용relay종료,임시작업디렉터리는검증후중복만정리. 원본checkout/venv·동결원문·모델trace·원가격·실패기록·재현코드유지.

봉인자료에서재계산(추가LLM/운영쓰기없음):

```bash
PYTHONPATH=src .venv/bin/python experiments/task9_4/evaluate_outcomes.py
PYTHONPATH=src .venv/bin/python experiments/task9_4/score_hypotheses.py
PYTHONPATH=src .venv/bin/python experiments/task9_4/check_invalidation.py
PYTHONPATH=src .venv/bin/python experiments/task9_4/compare_task93.py
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q experiments/task9_4/test_protocol.py
PYTHONPATH=src .venv/bin/python experiments/task9_4/write_report.py
```

미래결과가공개된현재위명령은동결자료검산용이다. 새연구·최초예측·신규Forward증거를생성하는명령이아니다. [진행기록](09_4_progress.md), [실험코드](../../experiments/task9_4/), [전체증거manifest](../../runtime/task9_4/artifact_manifest.json).
'''
p=R/'docs/development/09_4_vibe_discovery_benchmark.md';p.write_text(text);print(p,len(text))

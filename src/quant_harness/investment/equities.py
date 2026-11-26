"""US-first and KR individual-stock collection and fair screening.

Raw responses remain quarantined; no legacy V87/canonical is replaced.
"""
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import quote
import csv
import io
import json
import hashlib
import os
import time
import numpy as np
import pandas as pd
from .discovery import now, instant, company_discover, collect
from .research import digest,replay_targets,metrics
from .store import Store


def load_environment(root):
    """Aliases only inside this process. Never rewrites or prints .env values."""
    from dotenv import load_dotenv
    load_dotenv(Path(root)/'.env',override=False)
    for target,alias in {'OPENDART_API_KEY':'DART_API','TOSS_CLIENT_ID':'TOSS_API_KEY','TOSS_CLIENT_SECRET':'TOSS_API_SECREAT'}.items():
        if not os.getenv(target) and os.getenv(alias):os.environ[target]=os.environ[alias]


def settings(root):
    return json.loads((Path(root)/'config/task3_equity_contract.json').read_text())


def fetch(url,directory,identity='QuantHarness research/1.0',limit=20_000_000):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    with urlopen(Request(url,headers={'User-Agent':identity}),timeout=25) as response:
        raw=response.read(limit+1)
    if len(raw)>limit:raise ValueError('response too large')
    observed=now();checksum=hashlib.sha256(raw).hexdigest()
    target=directory/(checksum+'.raw')
    if not target.exists():target.write_bytes(raw)
    elif target.read_bytes()!=raw:raise ValueError('archive corrupted')
    receipt={'url':url,'source_hash':checksum,'available_at':observed,'elapsed_seconds':time.monotonic()-start,'cost_money':None}
    (directory/(digest(receipt)+'.receipt.json')).write_text(json.dumps(receipt))
    return raw,receipt


def us_catalog(directory):
    raw,receipt=fetch('https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt',directory)
    rows=[]
    for row in csv.DictReader(io.StringIO(raw.decode()),delimiter='|'):
        if row.get('Test Issue')=='N' and row.get('ETF')=='N' and row.get('Symbol'):
            rows.append({'symbol':row['Symbol'],'name':row['Security Name'],'exchange':row['Listing Exchange'],
                         'asset_type':'STOCK_LISTING_NON_ETF','observed_at':receipt['available_at'], 'common_stock_verified': ('Common Stock' in row['Security Name'] or 'Ordinary Shares' in row['Security Name'])})
    if not rows:raise ValueError('empty official US catalog')
    return {'market':'US','rows':rows,'receipt':receipt,'historical_membership_verified':False}


def kr_catalog(directory):
    from quant_harness.v72_integration_ready.opendart import OpenDartClient
    client=OpenDartClient()
    if not client.api_key:return {'market':'KR','rows':[],'status':'MISSING_CREDENTIAL'}
    rows=client.download_corp_codes()
    observed=now()
    payload={'market':'KR','rows':[r for r in rows if r.get('stock_code','').strip()], 'observed_at':observed,'historical_membership_verified':False}
    path=Path(directory)/'dart_catalog';path.mkdir(parents=True,exist_ok=True)
    (path/(digest(payload)+'.json')).write_text(json.dumps(payload,ensure_ascii=False))
    return payload


def normalize_chart(payload,symbol):
    result=payload['chart']['result'][0]
    if result['meta']['symbol'].upper()!=symbol.upper():raise ValueError('symbol mismatch')
    quote_rows=result['indicators']['quote'][0]
    adjusted=result['indicators'].get('adjclose',[{}])[0].get('adjclose')
    if adjusted is None:raise ValueError('adjustment factors missing')
    records=[]
    for i,stamp in enumerate(result['timestamp']):
        raw=[quote_rows[k][i] for k in ('open','high','low','close','volume')]
        # Incomplete bars are not silently filled. A trailing incomplete bar is
        # excluded only by the caller's explicit completion cutoff.
        if any(v is None for v in raw) or adjusted[i] is None:raise ValueError('missing chart bar')
        o,h,l,c,v=map(float,raw)
        if not all(np.isfinite(x) for x in (o,h,l,c,v,adjusted[i])) or min(o,h,l,c)<=0 or v<0 or h<max(o,c,l) or l>min(o,c,h):
            raise ValueError('invalid equity OHLCV')
        factor=float(adjusted[i])/c
        if factor<=0:raise ValueError('invalid adjustment factor')
        records.append({'timestamp':datetime.fromtimestamp(stamp,timezone.utc).isoformat(),'symbol':symbol,
            'open':o*factor,'high':h*factor,'low':l*factor,'close':float(adjusted[i]),'raw_open':o,'raw_high':h,'raw_low':l,'raw_close':c,'volume':v,
            'value_approx':c*v,'adjustment_factor':factor})
    frame=pd.DataFrame(records)
    if frame.empty or frame.timestamp.duplicated().any():raise ValueError('empty/duplicate equity bars')
    return frame,result['meta']


def equity_revision_gate(frame,symbol,directory,receipt):
    """Reuse V87 shape/revision checks under an explicit NEW raw-price contract."""
    from quant_harness.v87_actual_data_ingestion.engine import ProviderBatch,_validate_batch,_revision_audit
    cfg=json.loads((Path(__file__).resolve().parents[3]/'config/task3_equity_price_contract.json').read_text())
    rows=[]
    for row in frame.to_dict('records'):
        # Only completed old bars take part in revision comparison; a live bar
        # is not a historical revision and remains solely in the raw archive.
        if instant(row['timestamp']).timestamp()+86400>instant(receipt['available_at']).timestamp():continue
        rows.append({'date':row['timestamp'][:10],'ticker':symbol,'open':row['raw_open'],'high':row['raw_high'],'low':row['raw_low'],
                     'close':row['raw_close'],'volume':row['volume'],'value_approx':row['value_approx']})
    batch=ProviderBatch('YAHOO_CHART',symbol.zfill(6),tuple(rows),False,'YAHOO_CHART_RAW_OBSERVED',receipt['available_at'],{'raw_hash':receipt['source_hash']})
    canonical=_validate_batch(batch,cfg)
    canonical['ticker']=symbol  # restore original US/KR identity after legacy V87 padding
    folder=Path(directory)/'equity_revision';folder.mkdir(parents=True,exist_ok=True)
    key=digest(symbol);reference=folder/(key+'.reference.csv')
    audit=_revision_audit(canonical,reference,cfg)
    (folder/(key+'.'+receipt['source_hash']+'.audit.json')).write_text(json.dumps(audit,default=str))
    if not audit['passed']:raise ValueError('equity revision requires review')
    # The first accepted observation remains immutable, later versions archived.
    canonical.to_csv(folder/(key+'.'+receipt['source_hash']+'.csv'),index=False)
    if not reference.exists():canonical.to_csv(reference,index=False)
    return audit


def collect_prices(symbols,directory,history_range='5y'):
    result={};receipts=[]
    for symbol in symbols:
        try:
            url='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(symbol,safe='')+'?interval=1d&range='+history_range+'&events=div%2Csplits'
            raw,receipt=fetch(url,Path(directory)/'prices')
            frame,meta=normalize_chart(json.loads(raw),symbol)
            revision=equity_revision_gate(frame,symbol,directory,receipt)
            receipt['revision_gate']=revision
            result[symbol]={'frame':frame,'meta':meta,'receipt':receipt}
            receipts.append({'symbol':symbol,'status':'SAVED',**receipt})
        except Exception as exc:
            receipts.append({'symbol':symbol,'status':'FAILED','reason':type(exc).__name__})
        time.sleep(0.25)
    return result,receipts


def market_news(directory,market):
    from urllib.parse import urlencode
    from .discovery import recent_media
    query='(Apple OR Microsoft OR Nvidia) (earnings OR contract) when:7d' if market=='US' else '반도체 수주 실적 when:7d'
    params={'q':query,'hl':'en-US' if market=='US' else 'ko','gl':market,'ceid':'US:en' if market=='US' else 'KR:ko'}
    try:
        raw,receipt=fetch('https://news.google.com/rss/search?'+urlencode(params),Path(directory)/'market_news')
        records=recent_media(raw,instant(receipt['available_at']),query)
        return records,[{'provider':'GOOGLE_RSS_'+market,'status':'SAVED','research_items':len(records),**receipt}]
    except Exception as exc:return [],[{'provider':'GOOGLE_RSS_'+market,'status':'FAILED','reason':type(exc).__name__}]


def sec_observations(symbols,directory):
    """SEC raw API is the authority; optional EdgarTools parses individual filings.

    Submission acceptance strings are retained but unverified until compared to
    the raw filing header. First receipt is the only trusted availability here.
    """
    identity=os.getenv('EDGAR_IDENTITY')
    if not identity or '@' not in identity:
        return [],[{'provider':'SEC','status':'MISSING_EDGAR_IDENTITY'}]
    records=[];receipts=[]
    try:
        raw,catalog_receipt=fetch('https://www.sec.gov/files/company_tickers.json',Path(directory)/'sec',identity)
        catalog=json.loads(raw)
        mapping={r['ticker']:str(r['cik_str']).zfill(10) for r in catalog.values()}
    except Exception as exc:
        return [],[{'provider':'SEC','status':'FAILED_CATALOG','reason':type(exc).__name__}]
    for symbol in symbols[:4]:
        try:
            time.sleep(0.3)
            cik=mapping[symbol]
            raw,receipt=fetch(f'https://data.sec.gov/submissions/CIK{cik}.json',Path(directory)/'sec',identity)
            payload=json.loads(raw);recent=payload['filings']['recent']
            for i,form in enumerate(recent['form'][:20]):
                if form not in ('10-K','10-Q','8-K','10-K/A','10-Q/A','8-K/A'):continue
                accession=recent['accessionNumber'][i]
                body={'symbol':symbol,'cik':cik,'form':form,'accession':accession,'document':recent['primaryDocument'][i],
                      'acceptance_raw':recent['acceptanceDateTime'][i],'filing_date':recent['filingDate'][i]}
                records.append({'evidence_id':digest(body),'source_class':'OFFICIAL_FACT','available_at':receipt['available_at'],
                    'published_at':None,'acceptance_time_verified':False,'amendment':form.endswith('/A'),
                    'correction_chain_verified':False,'symbol':symbol,'entity_mapping':'SEC_CIK',
                    'source_hash':receipt['source_hash'],'title':json.dumps(body),
                    'url':f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-','')}/{body['document']}",
                    'capital_authority':'NONE'})
            receipts.append({'provider':'SEC','symbol':symbol,'status':'SAVED',**receipt})
        except Exception as exc:receipts.append({'provider':'SEC','symbol':symbol,'status':'FAILED','reason':type(exc).__name__})
    return records,receipts


def edgartools_parse(symbol):
    """Explicit optional enrichment, no automatic 'latest financials' in replay."""
    if not os.getenv('EDGAR_IDENTITY'):return {'status':'MISSING_EDGAR_IDENTITY'}
    try:
        from edgar import Company,set_identity
        set_identity(os.environ['EDGAR_IDENTITY'])
        filing=Company(symbol).get_filings(form=['10-K','10-Q']).latest()
        return {'status':'PARSED_METADATA_ONLY','symbol':symbol,'accession':filing.accession_no,
                'filing_date':str(filing.filing_date),'acceptance_time_verified':False,'forward_efficacy_verified':False}
    except ImportError:return {'status':'OPTIONAL_EDGARTOOLS_NOT_INSTALLED'}
    except Exception as exc:return {'status':'EDGARTOOLS_FAILED','reason':type(exc).__name__}


def stock_targets(close,cfg,kind):
    symbols=sorted(close.columns)
    score=close.pct_change(cfg['momentum_sessions'],fill_method=None).shift(1)
    trend=(close>close.rolling(cfg['trend_sessions'],min_periods=cfg['trend_sessions']).mean()).shift(1,fill_value=False)
    out=[]
    for day in close.index:
        valid=score.loc[day].where(score.loc[day]>0).dropna()
        if kind=='DEFENSIVE_STOCKS':valid=valid[trend.loc[day,valid.index]]
        if kind=='EQUAL_WEIGHT_STOCKS':valid=score.loc[day].dropna()*0+1
        chosen=list(valid.sort_values(ascending=False,kind='stable').index[:cfg['maximum_names']])
        weights={s:cfg['single_name_cap'] for s in chosen}
        out.append({'date':day,'target_weights_json':json.dumps(weights,sort_keys=True)})
    return pd.DataFrame(out)


def compare_stocks(root,market,collected,directory):
    from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec
    cfg=settings(root);directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    plan={'contract':cfg,'market':market,'input_hash':digest({s:x['receipt']['source_hash'] for s,x in collected.items()}),
          'purpose':'CURRENT_SURVIVOR_SEED_HISTORICAL_SCREEN_NOT_FORWARD','split_rule':'first 60% development, next20% validation, final20% reused historical diagnostic; no fitting/optimization'}
    registration=directory/'preregistration.json'
    if registration.exists() and json.loads(registration.read_text())!=plan:raise ValueError('immutable stock experiment conflict')
    registration.write_text(json.dumps(plan,indent=2))
    symbols=cfg[market]['seed_symbols']
    if any(s not in collected for s in symbols+[cfg[market]['index'],cfg[market]['benchmark']]):
        report={'status':'BLOCKED_INCOMPLETE_COMMON_INPUTS','input_hash':plan['input_hash']}
        (directory/'comparison.json').write_text(json.dumps(report));return report
    for symbol in symbols:
        if collected[symbol]['meta'].get('instrumentType')!='EQUITY':raise ValueError('non-equity in stock universe')
    frames={s:x['frame'].assign(date=lambda f:pd.to_datetime(f.timestamp,utc=True).dt.tz_convert('America/New_York' if market=='US' else 'Asia/Seoul').dt.tz_localize(None).dt.normalize()).set_index('date') for s,x in collected.items()}
    close=pd.DataFrame({s:frames[s].close for s in symbols}).sort_index()
    common_dates=close.dropna().index
    close=close.reindex(common_dates)
    if len(close)<cfg['trend_sessions']+60:raise ValueError('insufficient stock common history')
    # Today's possibly forming daily bar is excluded without pretending to know
    # whether a holiday session occurred. This is historical screening only.
    local_today=pd.Timestamp.now(tz='America/New_York' if market=='US' else 'Asia/Seoul').date()
    close=close[close.index.date<local_today]
    panel={'close':close,'open':pd.DataFrame({s:frames[s].open for s in symbols}).reindex(close.index),
           'adv20_d1':pd.DataFrame({s:frames[s].value_approx.rolling(20,min_periods=20).mean().shift(1) for s in symbols}).reindex(close.index)}
    dates=close.index[cfg['trend_sessions']:]
    assumptions=cfg['US_execution_assumptions'] if market=='US' else cfg['execution_assumptions']
    spec=ExecutionSpec(**{k:v for k,v in assumptions.items() if k!='minimum_order_nav_fraction'},minimum_order_notional_krw=cfg[market]['initial_capital']*assumptions['minimum_order_nav_fraction'])
    results={}
    for kind in cfg['strategies']:
        ledger=stock_targets(close,cfg,kind).set_index('date').reindex(dates).reset_index()
        account,orders,_=replay_targets(panel,dates,ledger,cfg[market]['initial_capital'],spec)
        row=metrics(account,orders,cfg[market]['initial_capital'])
        row['currency']=cfg[market]['currency'];row['cost_in_account_currency']=row.pop('cost_krw')
        row['splits']={}
        for split,a,b in [('development',0,0.6),('validation',0.6,0.8),('historical_tail',0.8,1)]:
            start,end=int(len(account)*a),int(len(account)*b)
            section=account.iloc[start:end]
            opening=cfg[market]['initial_capital'] if start==0 else account.nav_krw.iloc[start-1]
            row['splits'][split]={'return_pct':float((section.nav_krw.iloc[-1]/opening-1)*100),'independent_oos':False}
        account.rename(columns={'nav_krw':'nav','cash_krw':'cash'}).to_csv(directory/(kind+'_nav.csv'),index=False)
        orders.to_csv(directory/(kind+'_fills.csv'),index=False);ledger.to_csv(directory/(kind+'_targets.csv'),index=False)
        results[kind]=row
    benchmarks={}
    for symbol in (cfg[market]['index'],cfg[market]['benchmark']):
        series=frames[symbol].close
        if not dates.isin(series.index).all():raise ValueError('benchmark session coverage incomplete')
        before=series[series.index<dates[0]]
        if before.empty:raise ValueError('benchmark opening mark absent')
        benchmarks[symbol]={'gross_price_return_pct':float((series.loc[dates[-1]]/before.iloc[-1]-1)*100),'trading_allowed':False,
                           'dividend_status':'Yahoo adjusted ETF convention; index is price-only; not an investable net-return replica'}
    report={'status':'HISTORICAL_SCREEN_ONLY','market':market,'asset_type':'STOCKS_ONLY','input_hash':plan['input_hash'],
            'start':str(dates[0].date()),'end':str(dates[-1].date()),'sessions':len(dates),'results':results,'benchmarks':benchmarks,
            'limitations':[cfg['sample_status'],cfg['cost_status'],'No current catalog may be used as historical PIT membership. No strategy is approved by this screen.'],
            'selection':'SHADOW_ONLY_NO_AUTOMATIC_PROMOTION'}
    (directory/'comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    return report


def analyze_stocks(prices,cfg,market,kind='MOM63_STOCKS'):
    """Independent quant selection; no company-analysis argument."""
    from zoneinfo import ZoneInfo
    zone=ZoneInfo('America/New_York' if market=='US' else 'Asia/Seoul')
    current=datetime.now(timezone.utc);rows=[];marks={};adv={};missing=[]
    for symbol in cfg[market]['seed_symbols']:
        item=prices.get(symbol)
        if not item or item['meta'].get('instrumentType')!='EQUITY':missing.append(symbol);continue
        regular=item['meta'].get('currentTradingPeriod',{}).get('regular',{})
        if not regular.get('end'):missing.append(symbol);continue
        end=datetime.fromtimestamp(regular['end'],timezone.utc)
        completion_day=end.astimezone(zone).date()
        frame=item['frame'].copy()
        dates=pd.to_datetime(frame.timestamp,utc=True).dt.tz_convert(zone).dt.date
        if current<end+pd.Timedelta(minutes=5):frame=frame[dates<completion_day]
        else:frame=frame[dates<=completion_day]
        if len(frame)<cfg['trend_sessions']:missing.append(symbol);continue
        last=instant(frame.timestamp.iloc[-1]).astimezone(zone).date()
        # Receipt-time freshness bound; it is not a reconstructed PIT calendar.
        if (current.astimezone(zone).date()-last).days>4:missing.append(symbol);continue
        if any(not np.isfinite(v) for v in frame.close.iloc[-cfg['trend_sessions']:]):missing.append(symbol);continue
        score=float(frame.close.iloc[-1]/frame.close.iloc[-cfg['momentum_sessions']-1]-1)
        trend=bool(frame.close.iloc[-1]>frame.close.iloc[-cfg['trend_sessions']:].mean())
        marks[symbol]=float(frame.raw_close.iloc[-1]);adv[symbol]=float(frame.value_approx.iloc[-20:].mean())
        if score>0 and (kind!='DEFENSIVE_STOCKS' or trend):
            rows.append({'symbol':symbol,'momentum':score,'above_trend':trend,'reason':'FIXED_STOCK_RULE','horizon':'DAILY_REVIEW','invalidation':'positive momentum or registered trend eligibility fails'})
    selected=sorted(rows,key=lambda x:(-x['momentum'],x['symbol']))[:cfg['maximum_names']]
    return {'origin':'QUANT','market':market,'strategy_id':kind,'status':'ABSTAIN' if missing else 'CANDIDATES' if selected else 'CASH',
        'reason':'MISSING_OR_STALE_STOCK_INPUTS' if missing else 'PREREGISTERED_RULE_EVALUATED', 'missing':missing,
        'candidates':selected,'weights':{x['symbol']:cfg['single_name_cap'] for x in selected} if not missing else {},
        'prior_marks':marks,'adv20_d1':adv,'input_hash':digest({s:x['receipt']['source_hash'] for s,x in prices.items()}),
        'as_of':now(),'execution_eligible':not missing,'independent_company_input':True}


def observed_events(prices,market):
    """Fresh quotes only; never substitutes an earlier daily open or close."""
    events=[]
    for symbol,item in prices.items():
        meta=item['meta'];period=meta.get('currentTradingPeriod',{}).get('regular',{})
        if meta.get('instrumentType')!='EQUITY' or not period.get('start') or not period.get('end'):continue
        events.append({'symbol':symbol,'asset_type':'EQUITY','currency':meta.get('currency'),
            'price':meta.get('regularMarketPrice'),'event_at':datetime.fromtimestamp(meta['regularMarketTime'],timezone.utc).isoformat(),
            'available_at':item['receipt']['available_at'],'session_open':datetime.fromtimestamp(period['start'],timezone.utc).isoformat(),
            'session_close':datetime.fromtimestamp(period['end'],timezone.utc).isoformat(),'source':'YAHOO_CHART_OBSERVED','source_hash':item['receipt']['source_hash']})
    return events


def run_equity_cycle(root,url,market,directory,*,use_llm=True,compare=False,resume=None):
    from . import stockpaper
    root,directory=Path(root),Path(directory);directory.mkdir(parents=True,exist_ok=True)
    load_environment(root);cfg=settings(root)
    store=Store(url,market+'_STOCKS')
    if resume:
        decision=store.get(resume)
        import psycopg
        with psycopg.connect(store.url) as conn:
            complete=conn.execute('SELECT 1 FROM stock_nav WHERE decision_id=%s',(resume,)).fetchone()
        if complete or decision.get('algorithm_hash')!=stockpaper.algorithm_fingerprint():
            outcome=stockpaper.execute(store,root,resume,[])
            store.export(directory/'task4_records.jsonl')
            return outcome
        symbols=sorted(set(decision['opening_positions'])|{i['symbol'] for i in decision['intents']})
        prices,receipts=collect_prices(symbols,directory,'5d')
        events=toss_quote_events(symbols,directory,market) if market=='KR' and os.getenv('TOSS_CLIENT_ID') else observed_events(prices,market)
        store.put('stock_quote_collection',{'decision_id':resume,'receipts':receipts,'events':events})
        fresh=[e for e in events if instant(e['event_at'])>instant(decision['sealed_at']) and (instant(now())-instant(e['event_at'])).total_seconds()<=60]
        if decision['intents'] and len(fresh)!=len(symbols):
            return {'status':'WAITING_NEXT_PRICE_EVENT','decision_id':resume,'reason':'NO_COMPLETE_FRESH_POST_DECISION_EVENT_SET','broker_mutation_calls':0}
        outcome=stockpaper.execute(store,root,resume,events)
        store.export(directory/'task4_records.jsonl');return outcome
    catalog_receipt={}
    try:catalog=us_catalog(directory) if market=='US' else kr_catalog(directory)
    except Exception as exc:catalog={'market':market,'rows':[],'status':'FAILED','reason':type(exc).__name__}
    catalog_id=store.put('stock_universe_observation',catalog)
    symbols=cfg[market]['seed_symbols']+[cfg[market]['index'],cfg[market]['benchmark']]
    prices,receipts=collect_prices(symbols,directory,cfg['price_history_range'])
    if market=='KR' and os.getenv('TOSS_CLIENT_ID') and os.getenv('TOSS_CLIENT_SECRET'):
        try:
            fallback,fallback_receipts=collect_toss_stocks(cfg[market]['seed_symbols']+[cfg[market]['benchmark']],directory)
            prices.update(fallback);receipts+=fallback_receipts
            index,index_receipt=collect_toss_index(directory)
            prices['^KS11']=index;receipts.append(index_receipt)
        except Exception as exc:receipts.append({'source':'TOSS','status':'FAILED','reason':type(exc).__name__})
    store.put('stock_price_collection',{'receipts':receipts,'catalog_id':catalog_id,'retrieved_at':now(),'historical_membership_verified':False})
    # Full non-ETF catalog is collected; price coverage is an explicit bounded seed.
    if market=='US':
        listed={x['symbol'] for x in catalog['rows'] if x['common_stock_verified']}
    else:
        listed={x['stock_code']+'.KS' for x in catalog['rows']}
    quant=analyze_stocks(prices,cfg,market)
    if any(s not in listed for s in cfg[market]['seed_symbols']):
        quant.update(status='ABSTAIN',reason='CURRENT_STOCK_LISTING_NOT_VERIFIED',execution_eligible=False,weights={})
    quant_id=store.put('stock_quant_analysis',quant)
    if market=='US':
        evidence,sec_receipts=sec_observations(cfg[market]['seed_symbols'],directory)
        # A bounded RSS fallback remains clearly media, never official fact.
        news,news_receipts=market_news(directory,market)
        evidence+=news;sec_receipts+=news_receipts
    else:
        companies=[{'corp_code':r['corp_code'],'symbol':r['stock_code']} for r in catalog['rows'][:3]]
        media=collect(root,directory,'반도체 수주 실적',companies)
        evidence,sec_receipts=media['records'],media['receipts']
    evidence_id=store.put('stock_evidence_collection',{'records':evidence,'receipts':sec_receipts,'observed_at':now()})
    company=company_discover(evidence[:12],now(),skills='catalyst') if use_llm else {'status':'ABSTAIN','reason':'MODEL_DISABLED','candidates':[]}
    company_id=store.put('stock_company_analysis',company)
    comparison=compare_stocks(root,market,prices,directory/'comparison') if compare else {'status':'NOT_REQUESTED'}
    with store.lock():identity,decision=stockpaper.seal(store,root,market,quant,prices,catalog_id)
    store.put('stock_decision_lineage',{'decision_id':identity,'quant_id':quant_id,'company_id':company_id,'evidence_id':evidence_id,
        'catalog_id':catalog_id,'forecast_label_status':'PENDING','review_status':'PENDING_TASK4','factory_status':'NOT_CREATED',
        'company_execution':'SHADOW_UNTIL_VERIFIED_RULE_AND_PIT_INPUTS','etf_trading_allowed':False},identity+':lineage')
    if decision['intents']:
        # Quotes in the original price response predate sealing. Do not execute
        # against them: a later invocation must observe the next eligible event.
        outcome={'status':'WAITING_NEXT_PRICE_EVENT','decision_id':identity,'currency':cfg[market]['currency']}
    else:outcome=stockpaper.execute(store,root,identity,[])
    store.export(directory/'task4_records.jsonl')
    result={**outcome,'decision_id':identity,'market':market,'stock_catalog_count':len(catalog['rows']),
        'quant_status':quant['status'],'company_status':company['status'],'price_receipts':receipts,'comparison':comparison,
        'sec_status':[x.get('status') for x in sec_receipts],'etf_trading_allowed':False}
    (directory/'cycle_result.json').write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2))
    return result


def collect_toss_stocks(symbols,directory):
    """Strict paginated individual-stock candles; no OHLC fallback or ETF calls."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
    from quant_harness.active_market_data_update import _latest_completed_toss_trading_day
    from quant_harness.v87_actual_data_ingestion.engine import ProviderBatch,_validate_batch,_load_config,_revision_audit
    client=TossOpenApiClient();root=Path(__file__).resolve().parents[3]
    cfg=_load_config(root)
    latest=_latest_completed_toss_trading_day(client)
    calendar=client.get_market_calendar(market='KR',start_date=latest,end_date=latest)
    session=next(r for r in calendar if str(r['date'])[:10]==latest and r.get('is_open') is True)
    def session_time(value):
        text=str(value)
        return instant(text) if 'T' in text else datetime.fromisoformat(latest+'T'+text).replace(tzinfo=ZoneInfo('Asia/Seoul'))
    opening=session_time(session['raw']['integrated']['regularMarket']['startTime']);closing=session_time(session['regular_market_end'])
    items={};receipts=[];folder=Path(directory)/'toss_stocks';folder.mkdir(parents=True,exist_ok=True)
    for symbol in symbols:
        native=symbol.split('.')[0];archive=[]
        try:
            end=latest;rows={};oldest=None
            for page in range(8):
                payload=client._request('GET',client.endpoint_map.candles_path,query={'symbol':native,'interval':'1d','count':200,'before':end+'T23:59:59+09:00','adjusted':'true'})
                archive.append(payload)
                data=payload.get('data',payload);data=data.get('result',data) if isinstance(data,dict) else data
                candles=data.get('candles',[]) if isinstance(data,dict) else data
                if not candles:break
                for row in candles:
                    for key in ('timestamp','openPrice','highPrice','lowPrice','closePrice','volume','currency'):
                        if key not in row or row[key] is None:raise ValueError('strict candle field missing')
                    if row['currency']!='KRW':raise ValueError('KR currency mismatch')
                    day=str(row['timestamp'])[:10]
                    if day>latest:continue
                    body={'date':day,'ticker':native,'open':float(row['openPrice']),'high':float(row['highPrice']),'low':float(row['lowPrice']),
                          'close':float(row['closePrice']),'volume':float(row['volume']),'value_approx':float(row['closePrice'])*float(row['volume'])}
                    if day in rows and rows[day]!=body:raise ValueError('page revision conflict')
                    rows[day]=body
                first=min(str(r['timestamp'])[:10] for r in candles)
                if oldest and first>=oldest:raise ValueError('pagination did not progress')
                oldest=first;end=(datetime.fromisoformat(first).date()-timedelta(days=1)).isoformat()
                time.sleep(0.25)
                if len(candles)<200 or len(rows)>=1300:break
            observed=now();source_hash=digest(archive)
            (folder/(source_hash+'.json')).write_text(json.dumps(archive))
            batch=ProviderBatch('TOSS_EQUITY',native,tuple(rows.values()),True,'toss_openapi_1d_adjusted',observed,{'source_hash':source_hash})
            checked=_validate_batch(batch,cfg)
            if not np.isfinite(checked[['open','high','low','close','volume','value_approx']].to_numpy(dtype=float)).all():raise ValueError('nonfinite candles')
            reference=folder/(native+'.reference.csv')
            audit=_revision_audit(checked,reference,cfg)
            if not audit['passed']:raise ValueError('Toss equity revision gate')
            if not reference.exists():checked.to_csv(reference,index=False)
            frame=checked.rename(columns={'ticker':'symbol'}).copy();frame['symbol']=symbol
            frame['timestamp']=frame.date+'T00:00:00+09:00'
            for name in ('open','high','low','close'):frame['raw_'+name]=frame[name]
            frame['adjustment_factor']=1.0
            receipt={'symbol':symbol,'status':'SAVED','source':'TOSS_ADJUSTED_EQUITY','source_hash':source_hash,'available_at':observed,
                     'revision_gate':audit,'pages':len(archive),'history_is_new_forward':False,'cost_money':None}
            meta={'symbol':symbol,'instrumentType':'ETF' if symbol=='069500.KS' else 'EQUITY','currency':'KRW','source':'TOSS_ADJUSTED_EQUITY',
                  'regularMarketPrice':float(frame.close.iloc[-1]),'regularMarketTime':int(closing.timestamp()),
                  'currentTradingPeriod':{'regular':{'start':int(opening.timestamp()),'end':int(closing.timestamp())}}}
            items[symbol]={'frame':frame,'meta':meta,'receipt':receipt};receipts.append(receipt)
        except Exception as exc:receipts.append({'symbol':symbol,'status':'FAILED','source':'TOSS_ADJUSTED_EQUITY','reason':type(exc).__name__})
    return items,receipts


def collect_toss_index(directory):
    """Non-tradable KOSPI price benchmark, with raw page provenance."""
    from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
    from quant_harness.active_market_data_update import _latest_completed_toss_trading_day
    client=TossOpenApiClient();latest=_latest_completed_toss_trading_day(client)
    catalog=client.get_market_indicator_prices(['KOSPI','KOSDAQ'])
    if not any(r.get('symbol')=='KOSPI' for r in catalog):raise ValueError('official KOSPI identity absent')
    before=latest+'T23:59:59+09:00';all_rows=[];seen=set()
    for _ in range(8):
        rows,next_before=client.get_market_indicator_candles_page('KOSPI',count=200,before=before)
        all_rows.extend(rows)
        if not next_before:break
        if next_before in seen:raise ValueError('index pagination stalled')
        seen.add(next_before);before=next_before;time.sleep(0.25)
    observed=now();hash=digest(all_rows);folder=Path(directory)/'toss_index';folder.mkdir(parents=True,exist_ok=True)
    (folder/(hash+'.json')).write_text(json.dumps(all_rows))
    frame=pd.DataFrame(all_rows).drop_duplicates('timestamp').sort_values('timestamp')
    for field in ('open','high','low','close'):
        frame[field]=pd.to_numeric(frame[field],errors='raise')
        if not np.isfinite(frame[field]).all() or frame[field].le(0).any():raise ValueError('invalid index price')
        frame['raw_'+field]=frame[field]
    if (frame.high<frame[['open','close','low']].max(axis=1)).any() or (frame.low>frame[['open','close','high']].min(axis=1)).any():raise ValueError('index geometry')
    frame['value_approx']=None  # Not an executable instrument; no invented liquidity.
    receipt={'symbol':'^KS11','status':'SAVED','source':'TOSS_KOSPI_INDEX','source_hash':hash,'available_at':observed,'capital_authority':'BENCHMARK_ONLY'}
    return {'frame':frame,'meta':{'symbol':'^KS11','instrumentType':'INDEX','currency':'KRW'},'receipt':receipt},receipt


def toss_quote_events(symbols,directory,market='KR'):
    from zoneinfo import ZoneInfo
    from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
    client=TossOpenApiClient();current=datetime.now(ZoneInfo('Asia/Seoul'))
    today=current.date().isoformat()
    calendar=client.get_market_calendar(market=market,start_date=today,end_date=today)
    day=next((r for r in calendar if str(r['date'])[:10]==today and r.get('is_open') is True),None)
    if day is None:return []
    regular=day['raw']['integrated']['regularMarket']
    def at(value):
        text=str(value)
        return instant(text) if 'T' in text else datetime.fromisoformat(today+'T'+text).replace(tzinfo=ZoneInfo('Asia/Seoul'))
    opening,closing=at(regular['startTime']),at(regular['endTime'])
    if not opening<=current<=closing:return []
    names={s.split('.')[0]:s for s in symbols}
    payload=client._request('GET',client.endpoint_map.quote_path,query={'symbols':','.join(names)})
    observed=now();source_hash=digest(payload)
    folder=Path(directory)/'toss_quotes';folder.mkdir(parents=True,exist_ok=True)
    (folder/(source_hash+'.json')).write_text(json.dumps(payload))
    rows=payload.get('result')
    if not isinstance(rows,list):raise ValueError('stock quote response contract')
    events=[]
    for row in rows:
        native=row['symbol']
        if native not in names or row['currency']!='KRW':raise ValueError('stock quote identity/currency')
        timestamp=instant(row['timestamp'])
        events.append({'symbol':names[native],'asset_type':'EQUITY','currency':row['currency'],'price':row['lastPrice'],
            'event_at':timestamp.isoformat(),'available_at':observed,'session_open':opening.isoformat(),'session_close':closing.isoformat(),
            'source':'TOSS_STOCK_QUOTE_OBSERVED','source_hash':source_hash})
    return events

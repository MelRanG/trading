"""Source and feature-availability audit. No returns, targets or account runs."""
from collections import Counter
from hashlib import file_digest, sha256
from pathlib import Path
import re
import tarfile

from lxml import html
import pandas as pd

from experiments.research_references import source
from experiments.task13_f1_r4.replay import ROOT, load, save, sha
from experiments.task13_f1_r6.plan import OUT, R5, STARTS, screen
from quant_harness.v87_actual_data_ingestion.engine import ProviderBatch, _validate_batch, _revision_audit


def canonical(text):
    return re.sub(r'[^\w가-힣]+','',text).casefold()


def kind_rows(path):
    rows=[]
    doc=html.parse(str(path),html.HTMLParser(encoding="utf-8"))
    for tr in doc.xpath('//table//tbody/tr'):
        cells=tr.xpath('./td')
        if len(cells)<4:
            continue
        anchors=cells[1].xpath('.//a[contains(@onclick,"companysummary_open")]')
        if not anchors:
            continue
        token=re.search("companysummary_open\\('([0-9A-Z]+)'\\)",anchors[0].get('onclick'))
        date=cells[2].text_content().strip()
        if not token or not re.fullmatch(r'20\d\d-\d\d-\d\d',date):
            continue
        boards=cells[1].xpath('.//img/@alt')
        rows.append(dict(prefix=token[1],name=anchors[0].text_content().strip(),date=date,
                         board={'유가증권':'KOSPI','코스닥':'KOSDAQ','코넥스':'KONEX'}.get(boards[0]),
                         reason=cells[3].text_content().strip(), source=path.name))
    return rows


def join_event(record, events, begin, end):
    matches = [r for r in events if r['prefix'] == record['code'][:5]
               and r['board']==record['board'] and begin<=r['date']<=end]
    exact=[r for r in matches if canonical(r['name'])==canonical(record['name'])]
    if len(exact)==1:
        return {'status':'KIND_MATCHED','effective_date':exact[0]['date'],'reason':exact[0]['reason'],
                'evidence':exact[0]['source'],'kind_name':exact[0]['name']}
    return {'status':'NAME_OR_DATE_UNRESOLVED' if matches else 'NO_MATCH_IN_PUBLIC_LIST',
            'effective_date':None,'reason':None,
            'evidence':','.join(sorted({r['source'] for r in matches})),
            'kind_name':','.join(sorted({r['name'] for r in matches}))}


def check_archive():
    index=load(ROOT/'runtime/research_reference/index.json')
    inventory=Path(index['archive_inventory'])
    archive=Path(index['archive'])
    assert sha(inventory)==index['archive_inventory_sha256']
    with archive.open('rb') as f:
        assert file_digest(f,'sha256').hexdigest()==index['archive_sha256']
    entries=load(inventory)
    names=['runtime/task13_r0/contract.json','runtime/task13_f1_r4/price_gate.json']
    items={}
    with tarfile.open(archive,mode='r|gz') as tar:
        for member in tar:
            if member.name in names:
                data=tar.extractfile(member).read()
                assert sha256(data).hexdigest()==entries[member.name]['sha256']
                items[member.name]=__import__('json').loads(data)
                if len(items)==len(names):
                    break
    assert len(items)==len(names)
    return entries,items


def read_raw(path):
    rec=load(path.with_suffix('.receipt.json'))
    assert sha(path)==rec['sha256']
    return load(path)


def official_frames():
    refs={}
    r5_gate=load(R5/'preflight.json')
    paths=list((R5/'reference').glob('krx_*_????????.json'))
    paths += [source(ROOT,f'runtime/task13_f1_r4/krx_20251230_{b}.json') for b in ('KOSPI','KOSDAQ')]
    paths+=list((OUT/'raw').glob('krx_*_????????.json'))
    for p in paths:
        if p.parent==(OUT/'raw'):
            frame=read_raw(p)
        elif p.parent==(R5/'reference'):
            assert sha(p)==r5_gate['hashes'][p.relative_to(ROOT).as_posix()]
            frame=load(p)
        else:
            assert sha(p)==r5_gate['hashes']['runtime/task13_f1_r4/'+p.name]
            frame=load(p)
        for r in frame['OutBlock_1']:
            refs[(r['BAS_DD'],r['ISU_CD'])]=(p.name,r)
    return refs


def price_checks(references):
    conf=load(ROOT/'config/task3_equity_price_contract.json')
    conf['provider_contract'].update(required_source_tag='KIWOOM_REGULAR_NOMINAL',canonical_price_scale='NOMINAL_KRW')
    sessions=pd.to_datetime(pd.read_csv(R5/'benchmarks.csv',usecols=[0]).iloc[:,0])
    original=pd.read_csv(source(ROOT,"runtime/task13_r0/accepted/KR/^KS11/quote.csv"),usecols=['date']).date
    windows={arm:pd.DatetimeIndex(pd.concat([pd.to_datetime(original),sessions]).drop_duplicates().sort_values()).sort_values()
             for arm in STARTS}
    fields={'open':'open_pric','high':'high_pric','low':'low_pric','close':'cur_prc','volume':'trde_qty'}
    official=['TDD_OPNPRC','TDD_HGPRC','TDD_LWPRC','TDD_CLSPRC','ACC_TRDVOL']
    result=[]
    for p in sorted((OUT/'raw').glob('?_*.status.json')):
        stat=load(p)
        code,arm=stat['code'],stat['query_arm']
        data=[r for page in stat['pages'] for r in read_raw(OUT/'raw'/page['file'])['result_list']]
        actual=[r for r in data if re.fullmatch(r'20\d{6}',r.get('dt',''))]
        row={'arm':arm,'code':code,'name':stat['name'],'kind':stat['kind'],'dated_rows':len(actual),
             'blank_placeholder_rows':len(data)-len(actual),'v87':None,'matched_official':[]}
        check=[{'date':str(pd.Timestamp(r['dt']).date()),'ticker':code,'value_approx':int(r['trde_prica'])*1_000_000,
                **{k:int(r[v]) for k,v in fields.items()}} for r in actual]
        if check:
            data=_validate_batch(ProviderBatch('KIWOOM',code,tuple(check),False,'KIWOOM_REGULAR_NOMINAL',
                                                load((OUT/'raw'/stat['pages'][0]['file']).with_suffix('.receipt.json'))['at'],{}),conf)
            paired=[]
            for r in actual:
                date=r['dt']
                if (date,code) not in references:
                    continue
                ref_file, ref=references[(date,code)]
                matches=[int(r[k])==int(ref[j]) for k,j in zip(fields.values(),official)]
                row['matched_official'].append({'date':date,'OHLC_match':all(matches[:4]),'volume_match':matches[4],
                                                'source':ref_file})
                paired.append({'date':str(pd.Timestamp(date).date()),'ticker':code,'close':int(ref['TDD_CLSPRC'])})
            if paired:
                ref_path=OUT/f'v87_{arm}_{code}.csv'
                pd.DataFrame(paired).to_csv(ref_path,index=False)
                row['v87']=_revision_audit(data,ref_path,conf)
            cal=windows[arm]
            begin,end=map(pd.Timestamp,STARTS[arm][1:])
            expected=cal[(cal>=begin)&(cal<=end)]
            available_index=pd.DatetimeIndex(pd.to_datetime(data.date))
            row.update(eval_sessions=len(expected),missed_sessions=len(expected.difference(available_index)),
                       warmup_closes_available=len(cal[cal<begin][-64:].intersection(available_index)),
                       zero_volume_rows_in_eval=int((data.volume.eq(0)&data.date.between(str(begin.date()),str(end.date()))).sum()),
                       nominal_event_flags=dict(Counter(k for r in actual if str(begin.date()).replace('-','')<=r['dt']<=str(end.date()).replace('-','')
                                                        for k in r['upd_stkpc_tp'].split(',') if k)))
        result.append(row)
    assert len(result)==10
    sentinel={}
    for p in sorted((OUT/'raw').glob('A_048260_????????.json')):
        rows=read_raw(p)['result_list']
        sentinel[p.stem[-8:]]=sum(bool(x['dt']) for x in rows)
    return result,sentinel


def main():
    seal=load(OUT/'contract.json')
    for p,d in seal['sha256'].items():
        assert sha(ROOT/p)==d,p
    archive,historical=check_archive()
    source_ref=official_frames()
    r5=load(R5/'result.json')
    r4=load(source(ROOT,'runtime/task13_f1_r4/result.json'))
    roster=pd.read_csv(R5/'roster_snapshots.csv',dtype={'date':str,'code':str})
    staged=roster.groupby('date')
    cohort=pd.read_csv(OUT/'entry_cohorts.csv',dtype={'date':str,'code':str})
    event_files = [p for p in sorted((OUT/'raw').glob('kind_exits_20[0-9][0-9].html'))]
    events=[]
    for p in event_files:
        assert sha(p)==load(p.with_suffix('.receipt.json'))['sha256']
        events.extend(kind_rows(p))
    dedup={(r['prefix'],r['board'],r['name'],r['date'],r['reason']):r for r in events}
    events=list(dedup.values())
    current=pd.DataFrame(load(source(ROOT,'runtime/task13_r0/native_manifest/assets.json')))
    current=current[current.market.eq('KR')].assign(code=lambda p:p.symbol.str[:6]).set_index('code')
    t0 = {s[:6] for s in load(source(ROOT,'runtime/task13_f1_r2/collection_plan.json'))['symbols']}
    arms,changes,exits={},[],[]
    for arm,(stamp,begin,end) in STARTS.items():
        start=staged.get_group(stamp)
        finish=staged.get_group(end.replace('-',''))
        pool=screen(start)
        listed=cohort[cohort.arm.eq(arm)]
        assert set(listed.code)==set(pool.code)
        liquid=listed[listed.cap_sample]
        churn=start.loc[~start.code.isin(finish.code)]
        for row in churn.to_dict('records'):
            exits.append({'arm':arm,'eligible_at_cutoff':row['code'] in set(pool.code),
                         'locked_sample':row['code'] in set(liquid.code),**row,**join_event(row,events,begin,end)})
        matched=pool.merge(finish,on='code',suffixes=('_start','_end'))
        adj=[code for code in liquid.code if code in current.index and
             (source(ROOT,str(current.loc[code,'adjusted_path'])).exists() or current.loc[code,'adjusted_path'] in archive)]
        for row in matched[(matched.board_start!=matched.board_end)|(matched.name_start!=matched.name_end)].to_dict('records'):
            changes.append({'arm':arm,**row})
        arms[arm]={'cutoff':stamp,'pool_count':len(pool),'pool_by_board':pool.board.value_counts().to_dict(),
                   'old_sample_inside_cutoff_pool':len(set(pool.code)&t0),
                   'outside_previous_60':int((~pool.code.isin(t0)).sum()),'sample_count':len(liquid),
                   'sample_old_overlap':int(liquid.reference_60.sum()),
                   'sample_any_archived_R0_adjusted_asset':len(adj),'sample_old_flow_validity_possible':len(set(liquid.code)&t0),
                   'pool_to_endpoint_missing':sorted(set(pool.code)-set(finish.code)),
                   'sample_to_endpoint_missing':sorted(set(liquid.code)-set(finish.code)),
                   'pool_same_code_switch_board':int((matched.board_start!=matched.board_end).sum()),
                   'pool_same_code_name_diff':int((matched.name_start!=matched.name_end).sum()),
                   'cap_quantile_krw':{str(k):pool.cap.quantile(k) for k in [.25,.5,.75]},
                   'sample_cap_quantile_krw':{str(k):liquid.cap.quantile(k) for k in [.25,.5,.75]},
                   'official_market_section_is_not_industry':sorted({source_ref[(stamp,c)][1]['SECT_TP_NM']
                                                                    for c in pool.code}),
                   'status':'PIT_ENTRY_COHORT_ONLY','number_of_valid_evaluations':0}
    pd.DataFrame(changes).to_csv(OUT/'same_code_board_name_changes.csv',index=False)
    pd.DataFrame(exits).to_csv(OUT/'departures.csv',index=False)
    exits_df=pd.DataFrame(exits)
    for arm,row in arms.items():
        group=exits_df[exits_df.arm.eq(arm)]
        row['snapshot_departures_classification']=group.status.value_counts().to_dict()
        row['eligible_departures_classification']=group[group.eligible_at_cutoff].status.value_counts().to_dict()
    probes,sentinel=price_checks(source_ref)
    exit_quotes=[]
    for code,date in [('091990','20231215'),('003410','20240620'),('012510','20260625'),
                      ('057050','20260625'),('082640','20260806'),('048260','20230811')]:
        if (date,code) not in source_ref:
            continue
        path,row=source_ref[(date,code)]
        exit_quotes.append(dict(code=code,date=date,volume=int(row['ACC_TRDVOL']),nominal_close=int(row['TDD_CLSPRC']),
                                source=path,proceeds_verified=False))
    requests=[__import__('json').loads(line) for line in (OUT/'requests.jsonl').read_text().splitlines()]
    archive_stats=historical['runtime/task13_f1_r4/price_gate.json']
    save(OUT/'result.json',{'universe':'PIT_ENTRY_COHORT_ONLY','data_gate':'DATA_INSUFFICIENT',
         'economics':'HISTORICAL_PERFORMANCE_INCONCLUSIVE','portfolio_runs':0,
         'arms':arms,'pilot_prices':probes,'locked_048260_retry_dated_rows':sentinel,
         'KRX_exit_checkpoints':exit_quotes,'kind_rows':len(events),
         'historical_source_reuse':{'r0_identity':historical['runtime/task13_r0/contract.json']['identity'],
                                   'r4_calendar_days':archive_stats['evaluation_days'],
                                   'r4_cross':archive_stats['KRX_cross'],
                                   'archive_original_r0_type':'SURVIVOR_RESEARCH'},
         'legacy_comparator_only':{'A_R4':r4['arms']['T1_A']['total_pct'],
                                   'A_R4_mdd':r4['arms']['T1_A']['mdd_pct'],
                                   'A_original_exposure_mix':r4['arms']['T1_A']['prior_equity_matched_mix_pct'],
                                   'B_R5':r5['metrics']['MOM63']['total_pct'],
                                   'B_R5_mdd':r5['metrics']['MOM63']['mdd_pct'],
                                   'B_original_exposure_mix':r5['metrics']['MIX_LAGGED_EXPOSURE']['total_pct'],
                                   'B_original_stress':r5['stress']['windows']},
         'requests':dict(total=len(requests),by_http=dict(Counter(str(r.get('http')) for r in requests))),
         'failure_ledger':[
             {'type':'UNIVERSE','effect':'PIT common share/industry identity not available for whole locked samples; base API 401'},
             {'type':'DATA_ACTION','effect':'Kiwoom nominal data missing for sampled exit; no certified day-by-day holdings/cash settlement'},
             {'type':'INPUT_CONTRACT','effect':'Original flow-availability input mask mostly missing on historical cohorts; no deletion of future exits or survivor-only replay'},
             {'type':'TIMING','effect':'R4/R5 risk-off delay and missed summer bounce remain exposed survivor diagnostics only'},
             {'type':'COST_AND_FILL','effect':'No admissible R6 portfolio fills or NAV; outperformance and execution cost not estimable'},
         ]})


if __name__=='__main__':
    main()

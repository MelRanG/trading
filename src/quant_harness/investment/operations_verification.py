"""Read-only Task5 follow-up evidence. No API/model/trade/Factory mutations.

Invoked after the existing operating tick; future evidence stays pending until
actually observed. Only the explicitly marked report subsection is refreshed.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import fcntl,json,os,subprocess
import psycopg
from .research import digest
START='<!-- TASK5_FOLLOWUP_START -->'
END='<!-- TASK5_FOLLOWUP_END -->'


def update_section(path,body):
    path=Path(path)
    with path.with_suffix('.verification.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        original=path.read_text()
        section=START+'\n'+body.rstrip()+'\n'+END
        if START in original:
            before,tail=original.split(START,1)
            _,after=tail.split(END,1)
            updated=before+section+after
        else:updated=original.rstrip()+'\n\n'+section+'\n'
        temp=path.with_suffix('.verification.tmp');temp.write_text(updated);temp.replace(path)


def differences(before,after):
    result={}
    for key in ('logical_calls','wire_calls','input_tokens','output_tokens','journal_bytes','raw_bytes'):
        delta=after[key]-before[key]
        result[key]=delta if delta>=0 else None
    result['database_bytes']={k:after['databases'][k]['bytes']-v['bytes'] for k,v in before['databases'].items()}
    result['record_counts']={k:after['databases'][k]['records']-v['records'] for k,v in before['databases'].items()}
    return result


def collect(root,ops_url,sources,review_url):
    root=Path(root);folder=root/'runtime/task5/verification';folder.mkdir(parents=True,exist_ok=True)
    at=datetime.now(timezone.utc);state_path=folder/'baseline.json'
    baseline=json.loads(state_path.read_text()) if state_path.exists() else {'at':at.isoformat()}
    sample={'at':at.isoformat(),'databases':{},'markets':{},'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    urls={'ops':ops_url,'review':review_url,**sources}
    for name,url in urls.items():
        with psycopg.connect(url,options='-c default_transaction_read_only=on') as conn:
            size=conn.execute('SELECT pg_database_size(current_database()),pg_postmaster_start_time()').fetchone()
            count,payload_bytes=conn.execute('SELECT count(*),coalesce(sum(pg_column_size(payload)),0) FROM investment_record').fetchone()
            sample['databases'][name]={'bytes':size[0],'records':count,'payload_bytes':payload_bytes,'postmaster_start':size[1].isoformat()}
            if name in sources:
                sample['markets'][name]={'fills':conn.execute('SELECT count(*) FROM stock_fill').fetchone()[0],
                    'new_decisions':conn.execute("SELECT count(*) FROM investment_record WHERE kind='stock_decision' AND created_at>=%s",(baseline['at'],)).fetchone()[0],
                    'new_company_analyses':conn.execute("SELECT count(*) FROM investment_record WHERE kind='stock_company_analysis' AND created_at>=%s",(baseline['at'],)).fetchone()[0],
                    'new_analysis_results':conn.execute("SELECT kind,payload->>'status',payload->>'reason',created_at FROM investment_record WHERE kind IN ('stock_company_analysis','stock_quant_analysis') AND created_at>=%s ORDER BY created_at DESC LIMIT 20",(baseline['at'],)).fetchall(),
                    'states':conn.execute('SELECT status,count(*) FROM investment_run GROUP BY status ORDER BY status').fetchall()}
            if name=='ops':
                budgets=conn.execute('SELECT provider,sum(calls) FROM ops_budget GROUP BY provider').fetchall()
                sample['logical_calls']=sum(n for p,n in budgets if p.startswith('TOSS_') or p.startswith('CATALOG_') or p.startswith('RSS_'))
                sample['wire_calls']=sum(n for p,n in budgets if p.startswith('WIRE_'))
                models=conn.execute("SELECT payload->'measured_usage' FROM investment_record WHERE kind='ops_company_analysis'").fetchall()
                for key in ('input_tokens','output_tokens'):sample[key]=sum((r[0] or {}).get(key,0) for r in models)
                sample['targets']=baseline.get('targets') or {m:{'day':str(r[0]),'opening':r[1].isoformat(),'closing':r[2].isoformat()} for m in sources for r in conn.execute('SELECT day,opening,closing FROM ops_session WHERE market=%s AND opening>%s ORDER BY opening LIMIT 1',(m,baseline['at'])).fetchall()}
                latest=conn.execute("SELECT payload FROM investment_record WHERE kind='ops_tick' ORDER BY created_at DESC LIMIT 1").fetchone()
                sample['latest_tick']={'at':latest[0]['at'],'markets':[{k:r.get(k) for k in ('market','phase','last_complete_session','decision_id','paper_status','status','reason')} for r in latest[0]['markets']]} if latest else None
                request=conn.execute("SELECT r.payload FROM ops_pointer p JOIN investment_record r ON r.record_id=p.record_id WHERE p.name='experiment:pending'").fetchone()
                sample['experiment_input_hash']=digest(request[0]['snapshot']) if request else None
            if name=='review':
                outcomes=conn.execute("SELECT payload->'evaluation' FROM investment_record WHERE kind='review_outcome' AND created_at>=%s",(baseline['at'],)).fetchall()
                sample['outcomes']={s:sum(r[0].get('status')==s for r in outcomes) for s in ('PENDING','MATURED','INSUFFICIENT_EVIDENCE')}
    log=subprocess.run(['journalctl','--user','-u','quant-operations.service','--since',baseline['at'],'--no-pager','-o','cat'],capture_output=True,timeout=15)
    sample['journal_bytes']=len(log.stdout) if log.returncode==0 else 0
    sample['journal_measurement_ok']=log.returncode==0
    sample['raw_bytes']=sum(p.stat().st_size for p in (root/'runtime/task5/raw').rglob('*.json'))
    reservations=root/'runtime/alpha_research_factory/task4/experiment_reservations.jsonl'
    rows=[json.loads(line) for line in reservations.read_text().splitlines() if line] if reservations.exists() else []
    today=at.date().isoformat();used=sum(r['timestamp_utc'][:10]==today for r in rows)
    sample['factory_daily_used']=used
    sample['factory_next_reset']=(datetime.combine(at.date()+timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc)).isoformat()
    registry=root/'runtime/alpha_research_factory/task4/diagnostic_registry.jsonl'
    results=[json.loads(line) for line in registry.read_text().splitlines() if line] if registry.exists() else []
    matched=[r for r in results if r['result'].get('input_hash')==sample['experiment_input_hash']]
    sample['experiment_status']=matched[-1]['result']['status'] if matched else 'NATURAL_WAIT_FACTORY_RESET' if used else 'ELIGIBLE_NOT_YET_EXECUTED'
    sample['factory_result']=matched[-1] if matched else None
    if not state_path.exists():
        baseline={**sample,'targets':sample['targets']};state_path.write_text(json.dumps(baseline,indent=2,default=str))
    sample['delta_from_baseline']=differences(baseline,sample)
    with (folder/'samples.jsonl').open('a') as handle:handle.write(json.dumps(sample,default=str)+'\n')
    (folder/'latest.json').write_text(json.dumps(sample,indent=2,default=str))
    report=['## 9. Task 5 마무리 실증 — 자동 관측',f"관측 시각(UTC): {sample['at']}. 기준 시각: {baseline['at']}.",
      f"- 공통 A/B: `{sample['experiment_status']}`. Factory 오늘 예약 {used}건. 다음 UTC 예산 갱신: {sample['factory_next_reset']}. 기존 원장과 동일 input hash만 확인한다.",
      f"- 반복 사용량 증분: `{json.dumps(sample['delta_from_baseline'],ensure_ascii=False)}`. DB 증가는 page 할당·VACUUM 영향을 포함한다.",
      f"- 신규 사후 평가: `{json.dumps(sample['outcomes'])}`. 미성숙/불충분 결과를 완료로 간주하지 않는다.",
      f"- 실제 서버 재부팅 관측: {'boot ID 변경 확인' if sample['boot_id']!=baseline['boot_id'] else '미검증(기준 이후 boot ID 변화 없음)'}. PG start: {sample['databases']['ops']['postmaster_start']}."]
    for market,target in sample['targets'].items():
        status='NATURAL_WAIT_SESSION' if at<datetime.fromisoformat(target['opening']) else 'SESSION_TIME_REACHED_REQUIRES_EVENT_EVIDENCE'
        report.append(f"- {market} 다음 세션 {target['day']} / open {target['opening']}: `{status}`; 새 판단/기업분석/체결·상태: `{json.dumps(sample['markets'][market],ensure_ascii=False,default=str)}`.")
    if matched:report.append('실제 공통 A/B 결과(재사용 역사 진단, 신규 Forward 아님): `'+json.dumps(matched[-1]['result'],ensure_ascii=False)+'`')
    report.append('최근 실제 tick: `'+json.dumps(sample.get('latest_tick'),ensure_ascii=False)+'`')
    report.append('근거: `runtime/task5/verification/{baseline.json,samples.jsonl,latest.json}`. 이 관측기는 조회·기록만 수행하며 주문·모델·외부 API·Factory 실행을 추가하지 않는다.')
    update_section(root/'docs/development/05_autonomous_operations_report.md','\n\n'.join(report))
    return sample

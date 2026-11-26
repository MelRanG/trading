"""Manually launched three-point observation, terminating after the next open cutoff."""
import json
import time
from datetime import datetime
from experiments.task13_f1_r2.collect import OUT, KST, Client, save, snapshot

DAY='20261119'
PHASES={
    'regular_close':'2026-11-19T16:50:00+09:00',
    'evening':'2026-11-19T20:20:00+09:00',
    'next_preopen':'2026-11-20T08:15:00+09:00',
}


def main():
    save(OUT/'live_observation_plan.json',{'date':DAY,'timezone':'Asia/Seoul','phases':PHASES,
        'cutoff':'2026-11-20T08:30:00+09:00','max_lateness_seconds':300,
        'capabilities':'Kiwoom token + ka10059 only; no operating writes, no scheduling registration',
        'finality':'No explicit final version flag in ka10059. Stable values only provide stability evidence.'})
    status={}
    for phase,iso in PHASES.items():
        due=datetime.fromisoformat(iso)
        while (remaining:=(due-datetime.now(KST)).total_seconds())>0:
            time.sleep(min(remaining,60))
        if (datetime.now(KST)-due).total_seconds()>300:
            status[phase]='MISSED_WINDOW'
            continue
        try:
            snapshot(Client(),DAY,phase)
        except Exception as error:
            status[phase]={'error_type':type(error).__name__}
        else:
            status[phase]='OBSERVED'
        print(phase,status[phase],flush=True)
    comparisons={}
    if all(status[x]=='OBSERVED' for x in PHASES):
        records=[json.loads((OUT/f'observation_{DAY}_{p}.json').read_bytes()) for p in PHASES]
        for symbol in records[0]:
            v=[r[symbol] for r in records]
            comparisons[symbol]={'first_nonempty_observation':next((r['retrieved_at'] for r in v if r['value'] is not None),None),
                'changed_regular_to_evening':v[0]['value']!=v[1]['value'],
                'stable_evening_to_preopen':v[1]['value'] is not None and v[1]['value']==v[2]['value'],
                'found_before_cutoff':v[2]['value'] is not None and v[2]['retrieved_at']<'2026-11-20T08:30:00+09:00',
                'revision_status':'UNVERIFIED'}
    save(OUT/'live_observation_result.json',{'phases':status,'comparison':comparisons})


if __name__=='__main__':
    main()

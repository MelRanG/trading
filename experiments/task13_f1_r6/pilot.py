"""Use existing authenticated read-only clients and retain raw provenance."""
from urllib.parse import urlencode
from urllib.request import Request
import json
import time

from experiments.task13_f1_r2 import collect as ed
from experiments.task13_f1_r4 import prices
from experiments.task13_f1_r4.replay import load, save, sha
from experiments.task13_f1_r6.plan import OUT, STARTS

RAW = OUT/'raw'
LEDGER = OUT/'requests.jsonl'


def protect():
    if LEDGER.exists() and len(LEDGER.read_text().splitlines()) >= 39:
        raise RuntimeError('R6 provider budget reached')


def official(client):
    for stamp,_,_ in STARTS.values():
        for service in ['stk_isu_base_info','ksq_isu_base_info']:
            tag = service+'_'+stamp
            path=RAW/f'{tag}.json'
            if path.exists():
                assert sha(path)==load(path.with_suffix('.receipt.json'))['sha256']
                continue
            protect()
            raw,rec,_=client.request('https://data-dbg.krx.co.kr',f'/svc/apis/sto/{service}?basDd={stamp}',
                                     tag,headers={'AUTH_KEY':client.cfg['KRX_API_KEY']})
            if raw and client.cfg['KRX_API_KEY'].encode() not in raw:
                path.write_bytes(raw)
                save(path.with_suffix('.receipt.json'),{**rec,'sha256':sha(path)})
            print(tag,rec.get('http'),len(json.loads(raw).get('OutBlock_1',[])) if raw else 0,flush=True)


def kind(client):
    endpoints = {
        'kind_list_form': ('/investwarn/delcompany.do',{'method':'searchDelCompanyMain'}),
        'kind_exits_2026':('/investwarn/delcompany.do',{'method':'searchDelCompanySub','currentPageSize':'100',
                                 'pageIndex':'1','fromDate':'2026-01-01','toDate':'2026-11-18'}),
        'kind_exits_2023_25':('/investwarn/delcompany.do',{'method':'searchDelCompanySub','currentPageSize':'100',
                                 'pageIndex':'1','fromDate':'2023-04-03','toDate':'2025-12-30'}),
        'kind_listing_2026':('/listinvstg/listingcompany.do',{'method':'searchListingTypeSub','currentPageSize':'100',
                                 'pageIndex':'1','fromDate':'2026-01-01','toDate':'2026-11-18'}),
    }
    for tag,(uri,query) in endpoints.items():
        path=RAW/f'{tag}.html'
        if path.exists():
            continue
        protect()
        url='https://kind.krx.co.kr'+uri+'?'+urlencode(query)
        rec={'tag':tag,'url':url,'requested_at':ed.now()}
        try:
            with client.opener.open(Request(url),timeout=12) as response:
                rec['http']=response.code
                raw=response.read(4_000_000)
            path.write_bytes(raw)
            save(path.with_suffix('.receipt.json'),{**rec,'sha256':sha(path)})
            print(tag,len(raw),flush=True)
        except OSError as err:
            rec.update(error=type(err).__name__,http=getattr(err,'code',None))
            print(tag,rec['error'],flush=True)
        finally:
            with LEDGER.open('a') as fp:
                fp.write(json.dumps({**rec,'received_at':ed.now()})+'\n')
        time.sleep(.4)


def collect_nominal():
    prices.OUT = OUT
    client = prices.Client()
    for probe in load(OUT/'pilot_plan.json'):
        code,end,arm = probe['code'],probe['cutoff'],probe['arm']
        outcome=RAW/f'{arm}_{code}.status.json'
        if outcome.exists():
            continue
        cursor=None
        dated=set()
        record={'query_arm':arm,'code':code,'pages':[],'failure':None,'name':probe['name'],'kind':probe['kind']}
        for i in range(1,3):
            path=RAW/f'{arm}_{code}_{i}.json'
            meta=path.with_suffix('.receipt.json')
            if meta.exists() and path.exists():
                rec=load(meta)
                assert sha(path)==rec['sha256']
                body=load(path)
            else:
                protect()
                try:
                    body,rec,raw=client.query('ka11081',{'stk_cd':code,'base_dt':end,'upd_stkpc_tp':'0'},cursor)
                except (ValueError,OSError) as err:
                    record['failure']=str(err)
                    break
                path.write_bytes(raw)
                save(meta,rec)
            rows=body.get('result_list',[])
            names=body.get('stk_cd')==code
            dates=[r['dt'] for r in rows]
            if not names or dated.intersection(dates) or len(set(dates))!=len(dates) or any(d>end for d in dates):
                record['failure']='bad identity or overlapping/out-of-period pagination'
                break
            dated.update(dates)
            record['pages'].append({'file':path.name,'sha256':rec['sha256'],'rows':len(rows)})
            cursor=rec['cursor']
            earliest='20221226' if arm=='A' else '20250922'
            if not dates or min(dates)<=earliest or rec['more']!='Y' or not cursor:
                break
        record.update(first=min(dated,default=None),last=max(dated,default=None),rows=len(dated))
        save(outcome,record)
        print(arm,code,len(dated),record['first'],record['last'],record['failure'],flush=True)


if __name__=='__main__':
    RAW.mkdir(exist_ok=True)
    ed.OUT,ed.RAW = OUT,RAW
    c=ed.Client()
    official(c)
    kind(c)
    collect_nominal()

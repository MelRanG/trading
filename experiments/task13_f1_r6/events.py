"""Small supplementary official checks for fixed exit integrity probes."""
from urllib.parse import urlencode
from urllib.request import Request
import json
import time

from experiments.task13_f1_r2 import collect as ed
from experiments.task13_f1_r4.replay import load, save, sha
from experiments.task13_f1_r6.pilot import LEDGER, RAW, protect
from experiments.task13_f1_r6.plan import OUT

# These are source references for the sealed exit sentinels, unrelated to candidate construction.
FILINGS = {
    '091990':'/external/2024/05/16/001279/20240516003025/11013.htm',
    '003410':'/external/2024/06/17/000505/20240617001261/10002.htm',
    '012510':'/external/2026/05/19/000570/20260519001358/11347.htm',
    '082640':'/external/2026/07/06/000594/20260706001341/10084.htm',
    '057050':'/external/2026/02/12/000133/20260212000353/10084.htm',
}


def get(client, tag, path):
    target=RAW/(tag+'.html')
    receipt=target.with_suffix('.receipt.json')
    if target.exists():
        assert sha(target)==load(receipt)['sha256']
        return
    protect()
    url='https://kind.krx.co.kr'+path
    row={'tag':tag,'url':url,'requested_at':ed.now()}
    try:
        with client.opener.open(Request(url),timeout=14) as response:
            raw=response.read(12_000_001)
            row['http']=response.code
        if len(raw)>12_000_000:
            raise OSError('source exceeds preservation size')
        target.write_bytes(raw)
        save(receipt,{**row,'sha256':sha(target),'received_at':ed.now()})
    except OSError as err:
        row.update(error=type(err).__name__,http=getattr(err,'code',row.get('http')))
    finally:
        with LEDGER.open('a') as f:
            f.write(json.dumps({**row,'received_at':ed.now()})+'\n')
    time.sleep(.4)


def main():
    ed.OUT,ed.RAW=OUT,RAW
    client=ed.Client()
    for year in [2023,2024,2025]:
        params={'method':'searchDelCompanySub','currentPageSize':'100','pageIndex':'1',
                'fromDate':f'{year}-01-01','toDate':f'{year}-12-31'}
        get(client,f'kind_exits_{year}','/investwarn/delcompany.do?'+urlencode(params))
    for code,ref in FILINGS.items():
        get(client,f'event_{code}',ref)
    # Pre-suspension reference sessions documented in the captured filings.
    # These official snapshots can show trading before a stop but never certify proceeds.
    for board,date in [('KOSDAQ','20231215'),('KOSPI','20240620'),
                       ('KOSPI','20260625'),('KOSPI','20260806')]:
        protect()
        client.krx(board,date)


if __name__=='__main__':
    main()

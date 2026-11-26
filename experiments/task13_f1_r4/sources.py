"""Limited independent KRX and Toss nominal checkpoints."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import hashlib
import json
import os
from dotenv import dotenv_values
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
from experiments.task13_f1_r4.prices import ROOT, OUT

CHECKS = ['20230403','20240122','20250919','20251230']


def save(name,raw):
    (OUT/name).write_bytes(raw)
    return {'file':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def main():
    cfg={**dotenv_values(ROOT/'.env'), **os.environ}
    rec=[]
    for date in CHECKS:
        for board,tr in [('KOSPI','stk_bydd_trd'),('KOSDAQ','ksq_bydd_trd')]:
            url=f'https://data-dbg.krx.co.kr/svc/apis/sto/{tr}?basDd={date}'
            row={'source':'KRX','date':date,'board':board,'at':datetime.now(timezone.utc).isoformat()}
            try:
                with urlopen(Request(url,headers={'AUTH_KEY':cfg['KRX_API_KEY']}),timeout=10) as r:
                    raw=r.read(2_000_000)
                    row.update(http=r.status,**save(f'krx_{date}_{board}.json',raw))
            except HTTPError as e:
                row.update(http=e.code)
            rec.append(row)
    load_environment(ROOT)
    pending={}
    def transport(req,timeout):
        assert req.full_url.startswith('https://openapi.tossinvest.com/')
        method=req.get_method()
        assert '/oauth2/token' in req.full_url if method=='POST' else '/api/v1/candles' in req.full_url
        code,headers,raw=TossOpenApiClient._default_transport(req,timeout)
        row={'source':'TOSS','method':method,'at':datetime.now(timezone.utc).isoformat(),'http':code}
        if method=='GET':
            row.update(pending)
            if code==200:
                row.update(**save('toss_'+pending['symbol']+'_'+pending['date']+'.json',raw))
        rec.append(row)
        return code,headers,raw
    client=TossOpenApiClient(transport=transport)
    for s,date in [('080220','20240122'),('257720','20240531'),('064350','20251230')]:
        pending={'symbol':s,'date':date}
        before=f'{date[:4]}-{date[4:6]}-{date[6:]}T23:59:59+09:00'
        client._request('GET','/api/v1/candles',query={'symbol':s,'interval':'1d','count':12,'before':before,'adjusted':'false'})
    (OUT/'nominal_source_receipts.json').write_text(json.dumps(rec,indent=2)+'\n')
    print([(r['source'],r['http'],r.get('date')) for r in rec])


if __name__=='__main__':
    main()

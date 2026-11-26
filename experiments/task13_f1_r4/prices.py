"""Collect bounded KRX-scope, unadjusted daily bars. No account operations."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'runtime/task13_f1_r4'
R2 = ROOT/'runtime/task13_f1_r2'
RAW = OUT/'raw'
HOST = 'https://api.kiwoom.com'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def digest(value):
    return hashlib.sha256(value).hexdigest()


class Client:
    def __init__(self):
        self.config = {**dotenv_values(ROOT/'.env'), **os.environ}
        self.token = None
        self.opener = build_opener(NoRedirect())
        self.last = 0
        self.count = 0

    def query(self, tr, payload, cursor=None):
        if tr not in {'oauth','ka11081','ka10081'} or self.count>=480:
            raise ValueError('price scope or request budget exceeded')
        if tr != 'oauth' and not self.token:
            self.token = self.query('oauth', {
                'appkey': self.config['KIWOOM_APP_KEY'],
                'secretkey': self.config['KIWOOM_SECRET_KEY'], 'grant_type':'client_credentials',
            })[0]['token']
        path = '/oauth2/token' if tr=='oauth' else '/api/dostk/chart'
        hs = {'Content-Type':'application/json;charset=UTF-8'}
        if tr!='oauth':
            hs.update({'api-id':tr,'authorization':'Bearer '+self.token})
        if cursor:
            hs.update({'cont-yn':'Y','next-key':cursor})
        time.sleep(max(0,.35-(time.monotonic()-self.last)))
        self.last=time.monotonic()
        self.count+=1
        receipt={'at':datetime.now(timezone.utc).isoformat(),'tr':tr,'path':path}
        if tr!='oauth':
            receipt['query']=payload
        req=Request(HOST+path,data=json.dumps(payload).encode(),headers=hs,method='POST')
        try:
            try:
                res=self.opener.open(req,timeout=18)
            except HTTPError as err:
                res=err
            with res:
                b=res.read(4_000_000)
                receipt.update(http=res.code, cursor=res.headers.get('next-key'), more=res.headers.get('cont-yn'))
            obj=json.loads(b)
            receipt['code']=obj.get('return_code')
            if receipt['http']!=200 or receipt['code']!=0:
                raise ValueError(f'provider returned HTTP {receipt["http"]}, application code {receipt["code"]}')
            if tr!='oauth':
                if any(v.encode() in b for v in (self.token,self.config['KIWOOM_APP_KEY'],self.config['KIWOOM_SECRET_KEY'])):
                    raise ValueError('sensitive fields in market-data response')
                receipt['sha256']=digest(b)
            return obj,receipt,b
        finally:
            with (OUT/'requests.jsonl').open('a') as f:
                f.write(json.dumps({k:v for k,v in receipt.items() if k!='cursor'})+'\n')


def pull(client, code, tr):
    RAW.mkdir(exist_ok=True)
    old=None
    seen=set()
    cursor=None
    dates=set()
    for i in range(1,9):
        p=RAW/f'{tr}_{code}_{i}.json'
        m=RAW/f'{tr}_{code}_{i}.receipt.json'
        if p.exists() and m.exists():
            raw=p.read_bytes()
            receipt=json.loads(m.read_bytes())
            assert digest(raw)==receipt['sha256']
            body=json.loads(raw)
        else:
            query={'stk_cd':code,'base_dt':'20251230','upd_stkpc_tp':'0'}
            for attempt in range(2):
                try:
                    body,receipt,raw=client.query(tr,query,cursor)
                    break
                except OSError:
                    if attempt:
                        raise
                    time.sleep(1)
            p.write_bytes(raw)
            m.write_text(json.dumps(receipt,indent=2))
        if body.get('stk_cd',code)!=code:
            raise ValueError(f'identity mismatch: {code}: {body.get("stk_cd")}')
        rows=body['result_list' if tr=='ka11081' else 'stk_dt_pole_chart_qry']
        d=[r['dt'] for r in rows]
        if len(set(d))!=len(d) or dates.intersection(d) or (old and d and max(d)>=old) or (d and max(d)>'20251230'):
            raise ValueError(f'invalid pagination: {code}')
        dates.update(d)
        if not d or min(d)<='20230302' or receipt['more']!='Y':
            return code,len(dates),min(dates,default=None),max(dates,default=None),i
        old=min(d)
        cursor=receipt['cursor']
        if not cursor or cursor in seen:
            raise ValueError(f'invalid continuation: {code}')
        seen.add(cursor)
    return code,len(dates),min(dates),max(dates),i


def main():
    client=Client()
    tr=sys.argv[1]
    codes=[x.split('.')[0] for x in json.loads((R2/'collection_plan.json').read_bytes())['symbols']]
    chosen=sys.argv[2:] or codes
    for code in chosen:
        if code not in codes:
            raise ValueError('symbol outside original seal')
        print(*pull(client,code,tr),flush=True)


if __name__=='__main__':
    main()

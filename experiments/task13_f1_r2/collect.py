"""Read-only Kiwoom F1 collection with an immutable response cache."""
from datetime import datetime
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'runtime/task13_f1_r2'
RAW = OUT / 'raw'
KST = ZoneInfo('Asia/Seoul')
PILOT = ['005930.KS', '005490.KS', '247540.KQ']
FIELDS = ['frgnr_invsr', 'orgn', 'acc_trde_prica']
ASSETS = ROOT / 'runtime/task13_r0/native_manifest/assets.json'


def now():
    return datetime.now(KST).isoformat()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, result):
    with path.open('x') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, allow_nan=False)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, url):
        return None


class Client:
    def __init__(self):
        RAW.mkdir(exist_ok=True)
        self.cfg = {**dotenv_values(ROOT / '.env'), **os.environ}
        self.opener = build_opener(NoRedirect())
        self.token = None
        self.last = 0
        self.ledger = OUT / 'requests.jsonl'
        self.count = len(self.ledger.read_text().splitlines()) if self.ledger.exists() else 0

    def request(self, host, path, tag, payload=None, headers=None):
        if self.count >= 1200:
            raise RuntimeError('request budget exhausted')
        self.count += 1
        time.sleep(max(0, .27-(time.monotonic()-self.last)))
        self.last = time.monotonic()
        receipt = {'host':host, 'path':path, 'tag':tag, 'requested_at':now()}
        try:
            req = Request(host+path, data=json.dumps(payload).encode() if payload is not None else None,
                          headers={'Content-Type':'application/json;charset=UTF-8', **(headers or {})})
            try:
                res = self.opener.open(req, timeout=12)
            except HTTPError as error:
                res = error
            with res:
                raw = res.read(2_000_000)
                receipt.update(http=res.code, more=res.headers.get('cont-yn'), received_at=now())
                cursor = res.headers.get('next-key')
            body = json.loads(raw)
            receipt['code'] = body.get('return_code')
            if receipt['http'] != 200 or (host=='https://api.kiwoom.com' and receipt['code'] != 0):
                if path != '/oauth2/token':
                    msg=str(body.get('return_msg',''))
                    for value in [self.token,self.cfg.get('KRX_API_KEY')]:
                        if value: msg=msg.replace(value,'[REDACTED]')
                    receipt['message']=msg[:180]
                return None, receipt, None
            return raw, receipt, cursor
        except (URLError, TimeoutError, ValueError) as error:
            receipt['error']=type(error).__name__
            return None, receipt, None
        finally:
            with self.ledger.open('a') as f:
                f.write(json.dumps(receipt,ensure_ascii=False)+'\n')

    def kiwoom(self, symbol, end, selector, tag, cursor=None):
        target=RAW/(tag+'.json')
        meta=RAW/(tag+'.receipt.json')
        if target.exists() and meta.exists():
            data=target.read_bytes()
            receipt=json.loads(meta.read_bytes())
            assert sha(data)==receipt['sha256'], tag
            return json.loads(data)['stk_invsr_orgn'], receipt
        if not self.token:
            raw,receipt,_=self.request('https://api.kiwoom.com','/oauth2/token','oauth',
                        {'appkey':self.cfg['KIWOOM_APP_KEY'],'secretkey':self.cfg['KIWOOM_SECRET_KEY'],'grant_type':'client_credentials'})
            if raw is None:
                raise RuntimeError(f'Kiwoom authentication failed: {receipt}')
            self.token=json.loads(raw)['token']
        body={'dt':end,'stk_cd':symbol.split('.')[0],'amt_qty_tp':'1','trde_tp':str(selector),'unit_tp':'1'}
        auth={'api-id':'ka10059','authorization':'Bearer '+self.token}
        if cursor:
            auth.update({'cont-yn':'Y','next-key':cursor})
        raw,receipt,nxt=self.request('https://api.kiwoom.com','/api/dostk/stkinfo',tag,body,auth)
        if raw is None and receipt.get('http') in (None,500,502,503,504):
            time.sleep(1)
            raw,receipt,nxt=self.request('https://api.kiwoom.com','/api/dostk/stkinfo',tag,body,auth)
        if raw is None:
            raise RuntimeError(f'Kiwoom query failed: {receipt}')
        rows=json.loads(raw)['stk_invsr_orgn']
        assert all(self.cfg[k].encode() not in raw for k in ('KIWOOM_APP_KEY','KIWOOM_SECRET_KEY'))
        assert self.token.encode() not in raw
        receipt.update(symbol=symbol, query=body, next_cursor=nxt, sha256=sha(raw), rows=len(rows),
                       market_scope='KRX', unit='million KRW', source='KIWOOM ka10059')
        tmp=target.with_suffix('.tmp')
        tmp.write_bytes(raw)
        tmp.replace(target)
        save(meta,receipt)
        return rows,receipt

    def krx(self, board, day):
        tag=f'krx_{board}_{day}'
        service={'KOSPI':'stk_bydd_trd','KOSDAQ':'ksq_bydd_trd'}[board]
        target=RAW/(tag+'.json')
        meta=RAW/(tag+'.receipt.json')
        if target.exists() and meta.exists():
            assert sha(target.read_bytes())==json.loads(meta.read_bytes())['sha256']
            return json.loads(target.read_bytes())['OutBlock_1']
        raw,receipt,_=self.request('https://data-dbg.krx.co.kr',f'/svc/apis/sto/{service}?basDd={day}',tag,
                                   headers={'AUTH_KEY':self.cfg['KRX_API_KEY']})
        if raw is None:
            raise RuntimeError(f'KRX cross-check failed: {receipt}')
        if self.cfg['KRX_API_KEY'].encode() not in raw:
            target.write_bytes(raw)
        save(meta,{**receipt,'sha256':sha(raw)})
        return json.loads(raw)['OutBlock_1']


def pilot(client):
    previous=ROOT/'runtime/task13_f1_r1/kiwoom_recheck_20261119T012300Z'
    proof=json.loads((previous/'result.json').read_bytes())
    target='20240430'
    cross={b:{x['ISU_CD']:x for x in client.krx(b,target)} for b in ['KOSPI','KOSDAQ']}
    audits={}
    for symbol in PILOT:
        code, suffix=symbol.split('.')
        ref=(previous/(code+'_net_page1.json')).read_bytes()
        assert sha(ref)==next(x['sha256'] for x in proof['requests'] if x['tag']==code+'_net_page1')
        net={r['dt']:r for r in json.loads(ref)['stk_invsr_orgn'] if r['dt'].startswith('202404')}
        buys,_=client.kiwoom(symbol,target,1,code+'_pilot_buy')
        sells,_=client.kiwoom(symbol,target,2,code+'_pilot_sell')
        b={r['dt']:r for r in buys}
        s={r['dt']:r for r in sells}
        assert all(int(b[d][f]) >= 0 and int(s[d][f]) <= 0 for d in net for f in FIELDS[:2])
        errors=[abs(int(b[d][f])+int(s[d][f])-int(n[f])) for d,n in net.items() for f in FIELDS[:2]]
        exact=cross['KOSPI' if suffix=='KS' else 'KOSDAQ'][code]
        amount=int(exact['ACC_TRDVAL'])
        delta=int(net[target]['acc_trde_prica'])*1_000_000-amount
        audits[symbol]={'matched_sessions':len(net),'buy_sell_net_max_abs_million_krw':max(errors),
                        'denominator_diff_krw':delta,'denominator_relative_diff':delta/amount,
                        'denominator_krx_exact_krw':amount,'denominator_kiwoom_million_krw':int(net[target]['acc_trde_prica']),
                        'raw_net_sha256':sha(ref)}
    save(OUT/'pilot.json',audits)
    print(audits,flush=True)
    if any(x['matched_sessions']!=21 or x['buy_sell_net_max_abs_million_krw']>2 or abs(x['denominator_diff_krw'])>1_000_000 for x in audits.values()):
        raise RuntimeError('pilot accounting/denominator gate failed')


def snapshot(client, day, phase):
    report={}
    for symbol in PILOT:
        rows,receipt=client.kiwoom(symbol,day,0,f'{symbol[:6]}_obs_{day}_{phase}')
        row=next((x for x in rows if x['dt']==day),None)
        report[symbol]={'trade_date':day,'retrieved_at':receipt['received_at'],'source':receipt['source'],
                        'market_scope':'KRX','revision_status':'UNVERIFIED',
                        'requested_date_returned':row is not None,
                        'newest_date':max((x['dt'] for x in rows),default=None),
                        'value':{f:int(row[f]) for f in FIELDS} if row else None,
                        'sha256':receipt['sha256']}
    save(OUT/(f'observation_{day}_{phase}.json'),report)
    print(report,flush=True)


def select():
    assets=[x for x in json.loads(ASSETS.read_bytes()) if x['market']=='KR' and x['cohort']=='CORE']
    result=PILOT.copy()
    for board,limit in [('KOSPI',35),('KOSDAQ',25)]:
        groups={}
        for x in sorted(assets,key=lambda a:a['symbol']):
            if x['board']==board and x['list_date_kind'][:4]<='2022':
                groups.setdefault(x['sector_current'],[]).append(x['symbol'])
        pool=[(i,k,v) for k,g in groups.items() for i,v in enumerate(g) if v not in PILOT]
        result.extend(v for _,_,v in sorted(pool)[:limit-sum(s.endswith('.KS' if board=='KOSPI' else '.KQ') for s in PILOT)])
    return result


def bulk(client):
    plan=OUT/'collection_plan.json'
    if not plan.exists():
        save(plan,{'symbols':select(),'assets_sha256':sha(ASSETS.read_bytes()),
                   'start':'20220101','end':'20251230','pilot_sha256':sha((OUT/'pilot.json').read_bytes()),
                   'selection':'35 KOSPI, 25 KOSDAQ if available, fixed pilot plus sector round-robin; listed by 2022',
                   'market_scope':'KRX','expected_pages':660,'request_limit_including_all_phases':1200})
    plan=json.loads(plan.read_bytes())
    result={}
    for symbol in plan['symbols']:
        cursor=None
        seen=set()
        all_dates=set()
        for page in range(1,16):
            rows,receipt=client.kiwoom(symbol,plan['end'],0,f'{symbol[:6]}_history_{page:02d}',cursor)
            dates=[r['dt'] for r in rows]
            if len(dates)!=len(set(dates)) or all_dates.intersection(dates) or any(d>plan['end'] for d in dates):
                raise RuntimeError(f'{symbol}: invalid historical pagination page {page}')
            all_dates.update(dates)
            nxt=receipt['next_cursor']
            if not dates or min(dates)<=plan['start'] or receipt['more']!='Y' or not nxt:
                break
            if nxt in seen:
                raise RuntimeError(f'{symbol}: repeated page cursor')
            seen.add(nxt)
            cursor=nxt
        result[symbol]={'pages':page,'source_rows':len(all_dates),'date_range':sorted(all_dates)[::max(1,len(all_dates)-1)] if all_dates else []}
        print(symbol,page,len(all_dates),flush=True)
    save(OUT/'collection.json',result)


if __name__=='__main__':
    client=Client()
    if sys.argv[1]=='pilot':
        pilot(client)
    elif sys.argv[1]=='snapshot':
        snapshot(client,*sys.argv[2:])
    elif sys.argv[1]=='bulk':
        bulk(client)

"""Bounded, restartable collection using the existing read-only Kiwoom and KRX clients."""
import json
import sys
import time

from experiments.research_references import source
from experiments.task13_f1_r2 import collect as flow
from experiments.task13_f1_r4 import prices
from experiments.task13_f1_r4.replay import ROOT, R2, load, save, sha

OUT = ROOT / 'runtime/task13_f1_r5'
END = '20261118'
DATES = ('20230331', '20260102', '20260304', '20260831', END)
SYMBOLS = sorted(load(source(ROOT,R2 / 'collection_plan.json'))['symbols'])


def nominal():
    prices.OUT = OUT
    client = prices.Client()
    raw = OUT / 'nominal'
    raw.mkdir(exist_ok=True)
    for code in ['069500', *(s[:6] for s in SYMBOLS)]:
        path = raw / f'{code}.json'
        meta = raw / f'{code}.receipt.json'
        if path.exists() and meta.exists():
            receipt = load(meta)
            assert sha(path) == receipt['sha256']
            body = load(path)
        else:
            query = {'stk_cd': code, 'base_dt': END, 'upd_stkpc_tp': '0'}
            for attempt in range(2):
                try:
                    body, receipt, data = client.query('ka11081', query)
                    break
                except OSError:
                    if attempt:
                        raise
                    time.sleep(1)
            path.write_bytes(data)
            save(meta, receipt)
        dates = [r['dt'] for r in body['result_list']]
        assert body['stk_cd'] == code and len(set(dates)) == len(dates)
        assert min(dates) <= '20251230' and max(dates) <= END
        print(code, sum('20260101' <= d <= END for d in dates), min(dates), max(dates), flush=True)


def references(client):
    for d in DATES:
        for board in ['KOSPI', 'KOSDAQ']:
            try:
                rows = client.krx(board, d)
                print(board, d, len(rows), flush=True)
            except RuntimeError as e:
                print(board, d, e, flush=True)
    for d in ('20260304', '20260623', '20260629', '20260729', '20261015', '20261106', '20261116', '20261117', END):
        for service, board in [('kospi_dd_trd', '코스피'), ('kosdaq_dd_trd', '코스닥')]:
            if service == 'kosdaq_dd_trd':
                continue  # prior permission failure, use the authenticated Kiwoom index series
            path = flow.RAW / f'{service}_{d}.json'
            if path.exists():
                assert sha(path) == load(path.with_suffix('.receipt.json'))['sha256']
                continue
            raw, receipt, _ = client.request(
                'https://data-dbg.krx.co.kr', f'/svc/apis/idx/{service}?basDd={d}',
                service + '_' + d, headers={'AUTH_KEY': client.cfg['KRX_API_KEY']})
            if raw and client.cfg['KRX_API_KEY'].encode() not in raw:
                matches = [r for r in json.loads(raw)['OutBlock_1'] if r['IDX_NM'] == board]
                assert len(matches) == 1 and matches[0]['BAS_DD'] == d
                path.write_bytes(raw)
                save(path.with_suffix('.receipt.json'), {**receipt, 'sha256': sha(path)})
                print(service, d, matches[0]['CLSPRC_IDX'], flush=True)
            else:
                print(service, d, receipt, flush=True)


def availability(client):
    # Preserve the shared A/B historical eligibility mask. Amounts never enter MOM63 ranking.
    for symbol in SYMBOLS:
        cursor = None
        seen = set()
        dates = set()
        for page in range(1, 6):
            rows, receipt = client.kiwoom(symbol, END, 0, f'{symbol[:6]}_coverage_{page}', cursor)
            batch = [r['dt'] for r in rows]
            assert len(set(batch)) == len(batch) and not dates.intersection(batch)
            assert not dates or not batch or max(batch) < min(dates)
            dates.update(batch)
            cursor = receipt['next_cursor']
            if not batch or min(batch) <= '20260101' or receipt['more'] != 'Y':
                break
            assert cursor and cursor not in seen
            seen.add(cursor)
        print(symbol, page, sum('20260101' <= d <= END for d in dates), flush=True)


def indices(client):
    for code in ("001", "101"):
        tag = f"kiwoom_index_{code}"
        path = flow.RAW / f"{tag}.json"
        if path.exists():
            assert sha(path) == load(path.with_suffix(".receipt.json"))["sha256"]
            continue
        if not client.token:
            raw, _, _ = client.request("https://api.kiwoom.com", "/oauth2/token", "index_oauth",
                {"appkey":client.cfg["KIWOOM_APP_KEY"], "secretkey":client.cfg["KIWOOM_SECRET_KEY"],
                 "grant_type":"client_credentials"})
            if not raw:
                raise RuntimeError("index authentication failed")
            client.token = json.loads(raw)["token"]
        raw, receipt, _ = client.request("https://api.kiwoom.com", "/api/dostk/chart", tag,
            {"inds_cd":code, "base_dt":END}, {"api-id":"ka20006","authorization":"Bearer "+client.token})
        if not raw or any(v.encode() in raw for v in (client.token, client.cfg["KIWOOM_APP_KEY"],
                                                       client.cfg["KIWOOM_SECRET_KEY"])):
            raise RuntimeError("index query failed")
        response = json.loads(raw)
        assert response["inds_cd"] == code
        path.write_bytes(raw)
        save(path.with_suffix(".receipt.json"), {**receipt, "sha256":sha(path)})
        print(code, len(response["inds_dt_pole_qry"]), flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'nominal':
        nominal()
    else:
        flow.OUT = OUT
        flow.RAW = OUT / 'reference' if sys.argv[1] in ('reference','indices') else OUT / 'coverage'
        client = flow.Client()
        {'reference': references, 'coverage': availability, 'indices': indices}[sys.argv[1]](client)

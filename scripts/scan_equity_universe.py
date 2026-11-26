"""Bounded, resumable individual-stock discovery beyond the seed portfolio.

New discoveries remain Shadow; this job cannot create orders or change policy.
"""
from pathlib import Path
import argparse,json,os,sys
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.equities import load_environment,settings,us_catalog,kr_catalog,collect_prices,analyze_stocks
from quant_harness.investment.store import Store
import psycopg


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--market',choices=['US','KR'],default='US');p.add_argument('--batch-size',type=int,default=8)
    a=p.parse_args()
    if not 1<=a.batch_size<=20:p.error('batch must be 1..20')
    load_environment(ROOT);store=Store(os.environ['TASK3_'+a.market+'_DATABASE_URL'],a.market+'_STOCKS')
    directory=ROOT/'runtime/task3'/a.market.lower()/'universe_scan'
    catalog=us_catalog(directory) if a.market=='US' else kr_catalog(directory)
    symbols=sorted({r['symbol'] for r in catalog['rows'] if r['common_stock_verified']}) if a.market=='US' else sorted({r['stock_code']+'.KS' for r in catalog['rows']})
    cfg=settings(ROOT);seed=set(cfg[a.market]['seed_symbols']);symbols=[s for s in symbols if s not in seed]
    if not symbols:raise ValueError('no independently discovered stocks')
    with store.lock():
        with psycopg.connect(store.url) as conn:
            prior=conn.execute("SELECT payload FROM investment_record WHERE kind='stock_catalog_scan' ORDER BY created_at DESC LIMIT 1").fetchone()
        start=prior[0]['next_cursor']%len(symbols) if prior else 0
        batch=symbols[start:start+a.batch_size]
        prices,receipts=collect_prices(batch,directory,'1y')
        scoped=deepcopy(cfg);scoped[a.market]['seed_symbols']=batch
        analysis=analyze_stocks(prices,scoped,a.market)
        analysis['execution_eligible']=False
        analysis['capital_authority']='NONE_SHADOW_DISCOVERY'
        identity=store.put('stock_catalog_scan',{'catalog':catalog,'symbols':batch,'cursor':start,'next_cursor':start+len(batch),
            'receipts':receipts,'analysis':analysis,'universe_is_current_not_historical':True})
    store.export(directory/'task4_records.jsonl')
    print(json.dumps({'record_id':identity,'market':a.market,'scanned':batch,'status':analysis['status'],'candidates':analysis['candidates'],'execution_authority':'NONE'},ensure_ascii=False))

if __name__=='__main__':main()

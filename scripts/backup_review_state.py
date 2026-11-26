"""Snapshot Task4 DB + official Factory + worker code, excluding credentials."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,subprocess,tarfile,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
CONTAINER='quant-task3-postgres'


def call(*args,**kwargs):return subprocess.run(args,check=True,**kwargs)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--restore-check',action='store_true');a=p.parse_args()
    label=call('docker','inspect','-f','{{index .Config.Labels "quant-harness.scope"}}',CONTAINER,stdout=subprocess.PIPE,text=True).stdout.strip()
    if label!='task3-isolated':raise ValueError('not a Task3/4 research container')
    a.output.mkdir(parents=True,exist_ok=False,mode=0o700)
    dump=a.output/'review.dump'
    with dump.open('wb') as out:call('docker','exec',CONTAINER,'pg_dump','-U','quant_task3','-Fc','quant_task3_review',stdout=out)
    archive=a.output/'factory_code.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for name in ('runtime/alpha_research_factory/task4','config/task4_review_contract.json','src/quant_harness/alpha_research_factory.py'):
            tar.add(ROOT/name,arcname=name)
        for path in (ROOT/'src/quant_harness/investment').glob('review*.py'):tar.add(path,arcname=str(path.relative_to(ROOT)))
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),'dump_hash':hashlib.sha256(dump.read_bytes()).hexdigest(),
              'archive_hash':hashlib.sha256(archive.read_bytes()).hexdigest(),'credentials_included':False,'source_task3_modified':False}
    if a.restore_check:
        target='quant_task3_review_restore_'+datetime.now(timezone.utc).strftime('%H%M%S')
        call('docker','exec',CONTAINER,'createdb','-U','quant_task3',target)
        call('docker','exec','-i',CONTAINER,'pg_restore','-U','quant_task3','-d',target,'--exit-on-error',input=dump.read_bytes())
        import psycopg
        from quant_harness.investment.research import digest
        with psycopg.connect('postgresql://quant_task3@127.0.0.1:55432/'+target,options='-c default_transaction_read_only=on') as conn:
            rows=conn.execute('SELECT payload,payload_hash FROM investment_record').fetchall()
            if not all(digest(payload)==expected for payload,expected in rows):raise ValueError('restored review record hash mismatch')
            manifest['restore']={'database':target,'records_verified':len(rows),'status':'RESTORED_HASHES_MATCH',
                'research_jobs':conn.execute('SELECT count(*) FROM review_job').fetchone()[0]}
        with tarfile.open(archive) as tar:tar.extractall(a.output/'restored_files',filter='data')
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()

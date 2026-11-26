"""Consistent per-DB research backup, evidence hashes, isolated restore checks.

Run while holding the common operating lock. No deletion/retention pruning:
referenced investment evidence is never eligible for automatic removal.
"""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import hashlib,json,subprocess,tarfile
import psycopg
from .research import digest
from .discovery import now,instant
CONTAINER='quant-task3-postgres'
DATABASES=('quant_task3_us','quant_task3_kr','quant_task3_review','quant_task3_ops')


def call(*args,**kwargs):return subprocess.run(args,check=True,**kwargs)


def backup(root,*,restore_check=False):
    root=Path(root)
    label=call('docker','inspect','-f','{{index .Config.Labels "quant-harness.scope"}}',CONTAINER,stdout=subprocess.PIPE,text=True).stdout.strip()
    if label!='task3-isolated':raise ValueError('backup scope mismatch')
    folder=root/'runtime/task5/backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f');folder.mkdir(parents=True,mode=0o700)
    manifest={'created_at':now(),'scope':'PER_DATABASE_CONSISTENT_NOT_CROSS_DATABASE_ATOMIC','databases':{},'credentials_included':False,'retention':'14-day minimum; no automatic deletion of referenced evidence'}
    for name in DATABASES:
        path=folder/(name+'.dump')
        with path.open('wb') as out:call('docker','exec',CONTAINER,'pg_dump','-U','quant_task3','-Fc',name,stdout=out)
        item={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
        if restore_check:
            target='quant_task3_recovery_'+name.removeprefix('quant_task3_')+'_'+datetime.now(timezone.utc).strftime('%H%M%S')
            call('docker','exec',CONTAINER,'createdb','-U','quant_task3',target)
            call('docker','exec','-i',CONTAINER,'pg_restore','-U','quant_task3','-d',target,'--exit-on-error',input=path.read_bytes())
            with psycopg.connect('postgresql://quant_task3@127.0.0.1:55432/'+target,options='-c default_transaction_read_only=on') as conn:
                rows=conn.execute('SELECT payload,payload_hash FROM investment_record').fetchall()
                if not all(digest(p)==h for p,h in rows):raise ValueError('restored record integrity')
                item['restore']={'database':target,'records_verified':len(rows)}
                if name in ('quant_task3_us','quant_task3_kr'):
                    from .stockpaper import reconcile
                    # reconcile locks rows; a disposable restored DB is writable.
            if name in ('quant_task3_us','quant_task3_kr'):
                with psycopg.connect('postgresql://quant_task3@127.0.0.1:55432/'+target) as conn:
                    if not reconcile(conn):raise ValueError('restored ledger mismatch')
                    item['restore']['ledger_reconciled']=True
        manifest['databases'][name]=item
    paths=['runtime/task3/us','runtime/task3/kr','runtime/task4/daily','runtime/alpha_research_factory/task4','runtime/task5/raw',
           'runtime/task5/experiments','src/quant_harness/investment','src/quant_harness/alpha_research_factory.py']
    archive=folder/'evidence_code.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for name in paths:
            if (root/name).exists():tar.add(root/name,arcname=name,filter=lambda i:None if '__pycache__' in i.name else i)
        for pattern in ('config/task*.json','scripts/*operations*.py','scripts/run_common_experiment.py','deploy/systemd/quant-*'):
            for path in root.glob(pattern):tar.add(path,arcname=str(path.relative_to(root)))
    manifest['archive']={'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size}
    if restore_check:
        with tarfile.open(archive) as tar:tar.extractall(folder/'restored_files',filter='data')
        manifest['archive_restore']='EXTRACTED_NEW_DIRECTORY'
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2));return {'folder':str(folder.relative_to(root)),**manifest}


def due_backup(warehouse,interval=24,restore_check=False):
    prior=warehouse.lookup('backup:last')
    if prior and instant(now())-instant(prior['created_at'])<timedelta(hours=interval):return prior
    receipt=backup(warehouse.root,restore_check=restore_check)
    warehouse.point('backup:last','ops_backup',receipt);return receipt

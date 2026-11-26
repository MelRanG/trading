"""Initialize/backup/restore-check only the dedicated Task3 PostgreSQL container."""
from pathlib import Path
import argparse,hashlib,json,subprocess,tarfile
from datetime import datetime,timezone

CONTAINER='quant-task3-postgres'
DATABASES=('quant_task3_test','quant_task3_stocktest','quant_task3_us','quant_task3_kr')
ROOT=Path(__file__).resolve().parents[1]


def call(*args,**kwargs):
    return subprocess.run(args,check=True,**kwargs)


def verify():
    label=call('docker','inspect','-f','{{index .Config.Labels "quant-harness.scope"}}',CONTAINER,stdout=subprocess.PIPE,text=True).stdout.strip()
    if label!='task3-isolated':raise ValueError('refuse non-Task3 container')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['init','backup','restore-check']);p.add_argument('--backup',type=Path)
    a=p.parse_args();verify()
    if a.action=='init':
        for name in DATABASES:
            exists=call('docker','exec',CONTAINER,'psql','-U','quant_task3','-d','postgres','-Atc',"SELECT datname FROM pg_database WHERE datname='"+name+"'",stdout=subprocess.PIPE,text=True).stdout.strip()
            if not exists:call('docker','exec',CONTAINER,'createdb','-U','quant_task3',name)
        print('Isolated Task3 databases ready');return
    folder=a.backup or ROOT/'runtime/task3/backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    if a.action=='backup':
        folder.mkdir(parents=True,exist_ok=False)
        manifest={'created_at':datetime.now(timezone.utc).isoformat(),'scope':'PER_DATABASE_CONSISTENT_NO_CROSS_DATABASE_ATOMICITY','databases':{}}
        for name in ('quant_task3_us','quant_task3_kr'):
            dest=folder/(name+'.dump')
            with dest.open('wb') as out:call('docker','exec',CONTAINER,'pg_dump','-U','quant_task3','-Fc',name,stdout=out)
            manifest['databases'][name]={'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
        archive=folder/'equity_sources.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            for name in ('runtime/task3/us','runtime/task3/kr','src/quant_harness/investment'):
                path=ROOT/name
                if path.exists():tar.add(path,arcname=name,filter=lambda info: None if '__pycache__' in info.name else info)
            for path in (ROOT/'config').glob('task3*.json'):tar.add(path,arcname=str(path.relative_to(ROOT)))
        manifest['source_archive']={'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'path':archive.name,'credentials_included':False}
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
        print(str(folder));return
    manifest=json.loads((folder/'manifest.json').read_text())
    if 'source_archive' in manifest:
        archive=folder/manifest['source_archive']['path']
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=manifest['source_archive']['sha256']:raise ValueError('source archive hash')
        with tarfile.open(archive) as tar:tar.extractall(folder/'restored_files',filter='data')
    for name,meta in manifest['databases'].items():
        if name not in ('quant_task3_us','quant_task3_kr'):raise ValueError('backup DB identity')
        raw=(folder/(name+'.dump')).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=meta['sha256']:raise ValueError('backup hash')
        target=name.replace('quant_task3_','quant_task3_restore_')+'_'+datetime.now(timezone.utc).strftime('%H%M%S')
        # A new DB only: never drop or overwrite an existing restore/operational DB.
        call('docker','exec',CONTAINER,'createdb','-U','quant_task3',target)
        call('docker','exec','-i',CONTAINER,'pg_restore','-U','quant_task3','-d',target,'--exit-on-error',input=raw)
        result=call('docker','exec',CONTAINER,'psql','-U','quant_task3','-d',target,'-Atc','SELECT count(*) FROM investment_record',stdout=subprocess.PIPE,text=True)
        print(target,'records',result.stdout.strip())
    (folder/'restore_check.json').write_text(json.dumps({'status':'RESTORED_TO_NEW_ISOLATED_DATABASES','checked_at':datetime.now(timezone.utc).isoformat()}))

if __name__=='__main__':main()

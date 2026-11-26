from common import *
from replay_factory import open_store,Queue,NAME,URL
import subprocess,psycopg
store=open_store();store.export(B/'research_records.jsonl');p=B/'research.dump'
if not p.exists():
 with p.open('wb') as f:subprocess.run(['docker','exec','quant-task3-postgres','pg_dump','-U','quant_task3','-Fc',NAME],stdout=f,check=True)
copy='quant_task3_task10_restore_test';exists=subprocess.check_output(['docker','exec','quant-task3-postgres','psql','-U','quant_task3','-d','postgres','-Atc',"SELECT datname FROM pg_database WHERE datname='"+copy+"'"],text=True).strip()
assert not exists,'do not overwriteexistingrestoreDB'
subprocess.run(['docker','exec','quant-task3-postgres','createdb','-U','quant_task3',copy],check=True)
try:
 with p.open('rb') as f:subprocess.run(['docker','exec','-i','quant-task3-postgres','pg_restore','-U','quant_task3','--no-owner','-d',copy],stdin=f,check=True)
 rows=[]
 for db in [NAME,copy]:
  with psycopg.connect('postgresql://quant_task3@127.0.0.1:55432/'+db) as conn:rows.append({'records':conn.execute('SELECT count(*) FROM investment_record').fetchone()[0],'jobs':conn.execute('SELECT kind,status,count(*) FROM review_job GROUP BY kind,status ORDER BY kind,status').fetchall()})
 assert rows[0]==rows[1];freeze(B/'restore_check.json',{'dump_sha256':sha(p),'source_database':NAME,'temporary_restore_database':copy,'counts':rows[0],'isolated_restore_match':True,'production_or_coin_DB_touched':False,'temporary_restored_DB_removed':True})
finally:subprocess.run(['docker','exec','quant-task3-postgres','dropdb','-U','quant_task3',copy],check=True)
print('RESEARCH_DB_RESTORE_PASS')

"""Idempotent setup on the existing loopback-only Task3 PG; never reset a DB."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1];CONTAINER='quant-task3-postgres'
PAIRS={'quant_task3_ops':'quant_ops','quant_task3_us':'quant_paper_us','quant_task3_kr':'quant_paper_kr','quant_task3_review':'quant_review'}


def sql(database,statement):
    return subprocess.run(['docker','exec',CONTAINER,'psql','-U','quant_task3','-d',database,'-v','ON_ERROR_STOP=1','-Atc',statement],check=True,capture_output=True,text=True).stdout.strip()


def main():
    label=subprocess.run(['docker','inspect','-f','{{index .Config.Labels "quant-harness.scope"}}',CONTAINER],check=True,capture_output=True,text=True).stdout.strip()
    if label!='task3-isolated':raise ValueError('existing Task3 container required')
    for database,role in PAIRS.items():
        if not sql('postgres',f"SELECT datname FROM pg_database WHERE datname='{database}'"):
            if database!='quant_task3_ops':raise ValueError('restore existing Task3/4 source DB first')
            subprocess.run(['docker','exec',CONTAINER,'createdb','-U','quant_task3',database],check=True)
        existing=sql('postgres',f"SELECT rolsuper OR rolcreatedb OR rolcreaterole FROM pg_roles WHERE rolname='{role}'")
        if existing=='t':raise ValueError('scoped role has excessive authority')
        if not existing:sql('postgres',f'CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
        sql(database,f'GRANT CONNECT ON DATABASE {database} TO {role}; GRANT USAGE,CREATE ON SCHEMA public TO {role}; GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {role}; GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}; ALTER DEFAULT PRIVILEGES FOR ROLE quant_task3 IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO {role};')
    folder=ROOT/'runtime/task5';folder.mkdir(parents=True,exist_ok=True)
    path=folder/'service.env'
    expected='\n'.join(key+'=postgresql://'+PAIRS[db]+'@127.0.0.1:55432/'+db for key,db in [('TASK5_DATABASE_URL','quant_task3_ops'),('TASK5_US_DATABASE_URL','quant_task3_us'),('TASK5_KR_DATABASE_URL','quant_task3_kr'),('TASK4_REVIEW_DATABASE_URL','quant_task3_review')])+'\n'
    if not path.exists():path.write_text(expected);path.chmod(0o600)
    elif path.read_text()!=expected:raise ValueError('preserve existing service.env; reconcile manually')
    print('Scoped database roles ready; no database reset; no credentials displayed.')

if __name__=='__main__':main()

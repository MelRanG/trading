"""Create new Task8 research/Shadow DBs on existing isolated PG, never reset."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def call(*args):return subprocess.run(args,check=True,text=True,capture_output=True).stdout.strip()
def main():
    assert call('docker','inspect','-f','{{index .Config.Labels "quant-harness.scope"}}','quant-task3-postgres')=='task3-isolated'
    for name,role in [('quant_task3_task8_research','quant_task8_research'),('quant_task3_task8_shadow_us','quant_task8_shadow_us'),('quant_task3_task8_shadow_kr','quant_task8_shadow_kr'),('quant_task3_task8_test','quant_task8_test')]:
        def sql(db,statement):return call('docker','exec','quant-task3-postgres','psql','-U','quant_task3','-d',db,'-v','ON_ERROR_STOP=1','-Atc',statement)
        if not sql('postgres',f"SELECT datname FROM pg_database WHERE datname='{name}'"):call('docker','exec','quant-task3-postgres','createdb','-U','quant_task3',name)
        if not sql('postgres',f"SELECT rolname FROM pg_roles WHERE rolname='{role}'"):sql('postgres',f'CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
        sql(name,f'GRANT CONNECT ON DATABASE {name} TO {role}; GRANT USAGE,CREATE ON SCHEMA public TO {role}')
    print('Task8 new isolated databases ready; no reset, no operating DB grants')
if __name__=='__main__':main()

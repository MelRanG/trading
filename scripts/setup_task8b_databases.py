"""New exploration-only DBs on existing isolated PostgreSQL. No resets/grants elsewhere."""
import subprocess

def main():
 def run(*args):return subprocess.run(args,check=True,capture_output=True,text=True).stdout.strip()
 assert run('docker','inspect','-f','{{index .Config.Labels "quant-harness.scope"}}','quant-task3-postgres')=='task3-isolated'
 for db,role in [('quant_task3_task8b_research','quant_task8b_research'),('quant_task3_task8b_explore_us','quant_task8b_explore_us'),('quant_task3_task8b_explore_kr','quant_task8b_explore_kr'),('quant_task3_task8b_test','quant_task8b_test')]:
  def sql(database,text):return run('docker','exec','quant-task3-postgres','psql','-U','quant_task3','-d',database,'-v','ON_ERROR_STOP=1','-Atc',text)
  if not sql('postgres',f"SELECT datname FROM pg_database WHERE datname='{db}'"):run('docker','exec','quant-task3-postgres','createdb','-U','quant_task3',db)
  if not sql('postgres',f"SELECT rolname FROM pg_roles WHERE rolname='{role}'"):sql('postgres',f'CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
  sql(db,f'GRANT CONNECT ON DATABASE {db} TO {role}; GRANT USAGE,CREATE ON SCHEMA public TO {role}')
 print('New exploration research/US/KR/test DBs ready; existing operational roles unchanged')
if __name__=='__main__':main()

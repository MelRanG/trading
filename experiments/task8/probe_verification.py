"""Read-only real DB reproduction; report output goes only to a temporary root."""
from pathlib import Path
import tempfile,shutil,sys,json
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.operations_verification import collect
with tempfile.TemporaryDirectory(prefix='task8-report-probe-') as tmp:
 root=Path(tmp);folder=root/'runtime/task5/verification';folder.mkdir(parents=True);shutil.copy2(R/'runtime/task5/verification/baseline.json',folder/'baseline.json');report=root/'docs/development/05_autonomous_operations_report.md';report.parent.mkdir(parents=True);report.write_text('READONLY_DB_TEMPORARY_REPORT_TEST\n')
 result=collect(root,'postgresql://quant_ops@127.0.0.1:55432/quant_task3_ops',{'US':'postgresql://quant_paper_us@127.0.0.1:55432/quant_task3_us','KR':'postgresql://quant_paper_kr@127.0.0.1:55432/quant_task3_kr'},'postgresql://quant_review@127.0.0.1:55432/quant_task3_review')
 assert 'READONLY_DB_TEMPORARY_REPORT_TEST' in report.read_text()
 print(json.dumps({'status':'READONLY_REAL_DB_REPORT_REFRESH_PASS','output':'TEMPORARY_ROOT_ONLY','markets':list(result['markets']),'created_at_rows':sum(len(v['new_analysis_results']) for v in result['markets'].values()),'operations_db_mutations':0}))

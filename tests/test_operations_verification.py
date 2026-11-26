from quant_harness.investment.operations_verification import update_section,differences,START,END


def test_report_refresh_preserves_original_and_user_appendix(tmp_path):
    p=tmp_path/'report.md';p.write_text('Original evidence\n')
    update_section(p,'pending evidence')
    p.write_text(p.read_text()+'\nUser appendix\n')
    update_section(p,'actual evidence')
    assert p.read_text().count(START)==1 and p.read_text().count(END)==1
    assert 'Original evidence' in p.read_text() and 'User appendix' in p.read_text()
    assert 'pending evidence' not in p.read_text() and 'actual evidence' in p.read_text()


def test_usage_delta_does_not_claim_negative_usage_on_log_rotation():
    before={k:10 for k in ('logical_calls','wire_calls','input_tokens','output_tokens','journal_bytes','raw_bytes')}
    before['databases']={'ops':{'bytes':1000,'records':10}}
    after={**before,'journal_bytes':5,'wire_calls':12,'databases':{'ops':{'bytes':2000,'records':13}}}
    d=differences(before,after)
    assert d['journal_bytes'] is None and d['wire_calls']==2 and d['record_counts']=={'ops':3}

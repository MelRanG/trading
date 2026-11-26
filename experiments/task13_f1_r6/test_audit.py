"""Point-in-time selection and Korean source join regressions."""
import pandas as pd

from experiments.task13_f1_r6.audit import join_event, kind_rows
from experiments.task13_f1_r6.plan import sample, screen


def test_cutoff_screen_and_sample_ignore_future_outcomes():
    frame=pd.DataFrame({'code':['000001','000002','000003','000004'],
                        'cap':[900e9,550e9,800e9,490e9],'volume':[1,1,0,1],
                        'later_absent':[True,False,False,False]})
    screened=screen(frame)
    assert screened.code.tolist()==['000001','000002']
    assert sample(screened,1).code.tolist()==['000002']
    frame['later_absent']=~frame.later_absent
    assert sample(screen(frame),2).code.tolist()==['000001','000002']


def test_kind_join_requires_utf8_board_and_name(tmp_path):
    p=tmp_path/'listing.html'
    p.write_text("""<table><tbody><tr><td>1</td>
       <td><img alt="유가증권"><a onclick="companysummary_open('01251')">더존비즈온</a></td>
       <td>2026-07-15</td><td>완전자회사 편입</td></tr></tbody></table>""",encoding='utf-8')
    parsed=kind_rows(p)
    row={'code':'012510','board':'KOSPI','name':'더존비즈온'}
    assert join_event(row,parsed,'2026-01-02','2026-11-18')['effective_date']=='2026-07-15'
    row['name']='다른 종목'
    assert join_event(row,parsed,'2026-01-02','2026-11-18')['status']=='NAME_OR_DATE_UNRESOLVED'
    row['board']='KOSDAQ'
    assert join_event(row,parsed,'2026-01-02','2026-11-18')['status']=='NO_MATCH_IN_PUBLIC_LIST'

from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import pytest
from quant_harness.investment import discovery, research
from quant_harness.investment.store import require_database
ROOT=Path(__file__).resolve().parents[1]
def test_invalid_company_citation_and_no_evidence_never_calls_model(monkeypatch):
    monkeypatch.setattr(discovery.subprocess,'run',lambda *a,**k:pytest.fail('must abstain without evidence'))
    assert discovery.company_discover([],discovery.now())['reason']=='NO_AVAILABLE_EVIDENCE'
    with pytest.raises(ValueError,match='citation'):
        discovery.validate_company({'status':'CANDIDATES','candidates':[{'evidence_ids':['future']}]},[])


def test_recent_media_receipt_not_publication():
    observed=datetime(2026,11,13,tzinfo=timezone.utc)
    raw=b'<rss><channel><item><title>chip contract</title><link>https://news.google.com/rss/articles/a</link><pubDate>Thu, 12 Nov 2026 08:31:48 GMT</pubDate></item></channel></rss>'
    row=discovery.recent_media(raw,observed,'chip')[0]
    assert row['available_at']==observed.isoformat() and row['published_at']<row['available_at']
    assert row['capital_authority']=='NONE' and row['entity_mapping']=='UNVERIFIED'


def test_disallow_operational_database():
    for url in ('postgresql://x@127.0.0.1:5433/bioanalyst','postgresql://x@remote:55432/quant_task3_paper','postgresql://x@127.0.0.1:55432/production'):
        with pytest.raises(ValueError):require_database(url)


def test_cash_capable_replay_no_future_sizing_or_negative_cash():
    from quant_harness.v77_corrected_price_allocation.engine import _load_config
    dates=pd.date_range('2025-01-01',periods=5)
    close=pd.DataFrame({'069500':[100,100,200,100,100]},index=dates)
    market={'close':close,'open':close.copy(),'adv20_d1':close*0+1e9}
    ledger=pd.DataFrame({'date':dates[1:],'target_weights_json':['{"069500":0.4}','{}','{}','{}']})
    account,fills,_=research.replay_targets(market,dates[1:],ledger,1e7,_load_config(ROOT).base_execution)
    assert account.cash_krw.ge(0).all()
    assert set(fills.side)=={'BUY','SELL'}
    modified={**market,'close':close.copy(),'open':close.copy()}
    modified['close'].iloc[3:]*=20;modified['open'].iloc[3:]*=20
    other,other_fills,_=research.replay_targets(modified,dates[1:],ledger,1e7,_load_config(ROOT).base_execution)
    pd.testing.assert_frame_equal(account.iloc[:2],other.iloc[:2])
    pd.testing.assert_frame_equal(fills[fills.date<dates[3]],other_fills[other_fills.date<dates[3]])


def test_cross_sleeve_duplicate_risk_and_unspent_capital():
    from quant_harness.investment.portfolio import aggregate
    sleeves=[{'capital_fraction':0.5,'weights':{'069500':0.8}},{'capital_fraction':0.5,'weights':{'069500':0.8}}]
    args={'gross_cap':0.8,'single_name_cap':0.4,'sector_caps':{'broad':0.8},'sectors':{'069500':'broad'}}
    assert aggregate(sleeves,**args)['status']=='HOLD_ONLY'
    sleeves[1]['weights']={}
    result=aggregate(sleeves,**args)
    assert result['weights']=={'069500':0.4} and result['status']=='PREVIEW_ONLY'


def test_reverse_dcf_math_and_scenario_contract():
    from quant_harness.investment.valuation import implied_growth,scenario_record
    result=implied_growth(price=100,shares=1,debt=0,cash=0,revenue=100,fcf_margin=0.1,discount_rate=0.1,terminal_growth=0.02)
    assert result['status']=='CALCULATED_MODEL_IMPLIED_NOT_CONSENSUS' and -0.95<result['growth']<2
    with pytest.raises(ValueError):implied_growth(price=100,shares=1,debt=0,cash=0,revenue=100,fcf_margin=0.1,discount_rate=0.01,terminal_growth=0.02)
    with pytest.raises(ValueError):scenario_record('revenue','2027-03-31','B','USD',[{'name':n,'value':1,'probability':0.5,'assumptions':'fixture'} for n in ['bear','base','bull']])


def test_analyst_rejects_future_cutoff():
    with pytest.raises(ValueError,match='future'):
        discovery.company_discover([], '2099-01-01T00:00:00+00:00')


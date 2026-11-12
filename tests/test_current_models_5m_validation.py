from pathlib import Path

from quant_harness.current_models_5m_validation import _load_contract, _valid_full_session


ROOT = Path(__file__).resolve().parents[1]


def test_current_model_contracts_are_candidate_bound_and_hashed():
    v69, h69 = _load_contract(ROOT, "V69_PARENT")
    v79, h79 = _load_contract(ROOT, "V79_NO63_VOL_GUARD")
    assert v69["candidate_id"] == "V69_PARENT"
    assert v79["candidate_id"] == "V79_NO63_VOL_GUARD"
    assert len(h69) == 64 and len(h79) == 64
    assert v69["execution_contract"]["no_daily_fallback"] is True
    assert v79["execution_contract"]["no_daily_fallback"] is True


def test_incomplete_minute_cache_fails_closed(tmp_path):
    path = tmp_path / "2023-01-30.csv"
    path.write_text("timestamp,open,high,low,close,volume\n2023-01-30T09:01:00+09:00,1,1,1,1,1\n", encoding="utf-8")
    valid, bars, reason = _valid_full_session(tmp_path, "069500", path, "2023-01-30")
    assert valid is False
    assert bars == 1
    assert reason == "DAILY_REFERENCE_MISSING"

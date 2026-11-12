from pathlib import Path

import pandas as pd
import pytest

from quant_harness.open_5m_long_horizon_validation import CONTRACT_HASH, REQUIRED_TIMES, _validate_six


def _frame(times):
    return pd.DataFrame(
        {
            "timestamp": [f"2024-01-02T{t}:00+09:00" for t in times],
            "symbol": ["069500"] * len(times),
            "open": [100] * len(times),
            "high": [101] * len(times),
            "low": [99] * len(times),
            "close": [100] * len(times),
            "volume": [1] * len(times),
        }
    )


def test_long_runner_keeps_frozen_contract_hash():
    assert CONTRACT_HASH == "440ed25fd7b7a1ae7da998585b5654645a120f4b78f4c62c9834e3389c74bcc3"
    assert REQUIRED_TIMES == ("09:01", "09:02", "09:03", "09:04", "09:05", "09:06")


def test_six_bar_contract_rejects_missing_or_duplicate_bars():
    with pytest.raises(ValueError):
        _validate_six(_frame(REQUIRED_TIMES[:-1]), "2024-01-02")
    duplicate = _frame(REQUIRED_TIMES + ("09:06",))
    with pytest.raises(ValueError):
        _validate_six(duplicate, "2024-01-02")


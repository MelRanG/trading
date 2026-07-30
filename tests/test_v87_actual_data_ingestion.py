from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from quant_harness.v87_actual_data_ingestion.engine import (
    IngestionError,
    ProviderBatch,
    _load_config,
    _revision_audit,
    _validate_batch,
)


def _batch(**overrides):
    rows = (
        {"date": "2026-07-01", "ticker": "069500", "open": 100.0, "high": 103.0, "low": 99.0, "close": 102.0, "volume": 1000.0, "value_approx": 102000.0},
        {"date": "2026-07-02", "ticker": "069500", "open": 102.0, "high": 104.0, "low": 101.0, "close": 103.0, "volume": 1100.0, "value_approx": 113300.0},
    )
    data = dict(provider="TEST", symbol="069500", rows=rows, adjusted_ohlc_verified=True, source_tag="toss_openapi_1d_adjusted", retrieved_at="2026-07-03T00:00:00+00:00", raw_metadata={})
    data.update(overrides)
    return ProviderBatch(**data)


def test_verified_adjusted_batch_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = _load_config(root)
    frame = _validate_batch(_batch(), cfg)
    assert set(frame["price_scale"]) == {"ADJUSTED_OHLC"}
    assert set(frame["source"]) == {"toss_openapi_1d_adjusted"}


def test_unverified_or_wrong_source_is_blocked() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = _load_config(root)
    with pytest.raises(IngestionError, match="not verified"):
        _validate_batch(_batch(adjusted_ohlc_verified=False), cfg)
    with pytest.raises(IngestionError, match="source tag mismatch"):
        _validate_batch(_batch(source_tag="TOSS_OPEN_API"), cfg)


def test_duplicate_and_ohlc_geometry_are_blocked() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = _load_config(root)
    row = dict(_batch().rows[0])
    with pytest.raises(IngestionError, match="duplicate"):
        _validate_batch(_batch(rows=(row, row)), cfg)
    bad = dict(row); bad["high"] = 98.0
    with pytest.raises(IngestionError, match="geometry"):
        _validate_batch(_batch(rows=(bad,)), cfg)


def test_revision_gate_detects_material_same_provider_change(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = _load_config(root)
    ref = tmp_path / "reference.csv"
    pd.DataFrame([
        {"date": "2026-07-01", "ticker": "069500", "close": 100.0},
        {"date": "2026-07-02", "ticker": "069500", "close": 100.0},
    ]).to_csv(ref, index=False)
    new = pd.DataFrame([
        {"date": "2026-07-01", "ticker": "069500", "close": 110.0},
        {"date": "2026-07-02", "ticker": "069500", "close": 110.0},
    ])
    audit = _revision_audit(new, ref, cfg)
    assert audit["passed"] is False
    assert audit["changed_row_ratio"] == 1.0

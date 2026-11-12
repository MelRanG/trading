from __future__ import annotations

from pathlib import Path

from quant_harness.operational_candidate_comparison import _schema_url, _target_input_coverage
from quant_harness.paper_decision_runtime import build_candidate_strategy_preview
from quant_harness.recent_candidate_extension import market_coverage
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import build_candidate_ledgers, load_candidate_specs
from quant_harness.v79_high252_operational_replay import _metrics
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def test_candidate_preview_uses_registered_candidate_namespace() -> None:
    preview = build_candidate_strategy_preview(ROOT, "V79_PARENT", as_of="2018-01-16")
    assert preview["candidate_id"] == "V79_PARENT"
    assert preview["strategy_id"] == "V79_PARENT"
    assert preview["session_id"].startswith("PAPER-V79_PARENT-")


def test_schema_url_keeps_test_database_and_adds_search_path() -> None:
    url = _schema_url("postgresql://user:pass@host/db", "op_replay_v69_parent")
    assert "host/db" in url
    assert "search_path%3Dop_replay_v69_parent" in url


def test_operational_warmup_requires_d1_adv_and_price() -> None:
    built = build_candidate_ledgers(ROOT, load_candidate_specs(ROOT)["V69_PARENT"], use_common_cutoff=True)
    coverage = _target_input_coverage(built)
    assert coverage["warmup_end"] == "2018-01-16"
    # The active ETF files and KS11 now share the verified incremental cutoff.
    assert coverage["available_end"] == market_coverage(ROOT)["common_cutoff"]


def test_high252_slippage_metric_uses_fill_notional() -> None:
    nav = pd.DataFrame(
        {"date": ["2026-01-01", "2026-01-02"], "nav_krw": [1000.0, 1001.0], "cash_krw": [500.0, 500.0]}
    )
    trades = pd.DataFrame(
        [
            {"paper_fill_id": "F1", "fill_quantity": 10, "fill_price": 100, "slippage": 1, "fee": 2,
             "paper_order_id": "O1", "status": "FILLED", "side": "BUY"},
            {"paper_fill_id": "F2", "fill_quantity": 2, "fill_price": 100, "slippage": 3, "fee": 1,
             "paper_order_id": "O2", "status": "FILLED", "side": "SELL"},
        ]
    )

    metrics = _metrics(nav, trades)

    # paper_fill.slippage is a per-share price delta, not a KRW total.
    assert metrics["total_slippage_krw"] == 16.0

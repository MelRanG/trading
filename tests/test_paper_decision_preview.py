from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
import os
from pathlib import Path
from urllib.request import Request
import uuid

import psycopg
import pytest

from quant_harness.paper_decision_runtime import (
    PaperPreviewError,
    build_intent_previews,
    build_candidate_strategy_preview,
    build_strategy_preview,
    run_paper_decision_preview,
)
from quant_harness.paper_runtime_store import (
    PAPER_ACCOUNT_ID,
    ensure_paper_account,
    initialize_paper_schema,
    latest_paper_summaries,
    load_paper_account,
    save_paper_preview,
)
from quant_harness.toss_snapshot_runtime import (
    MockTransport,
    SafeRecordingTransport,
    run_toss_snapshot,
)
from quant_harness.v72_integration_ready.toss_openapi import TossApiError
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import (
    build_candidate_ledgers,
    load_candidate_specs,
)


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_PREVIEW_AS_OF = "2026-07-31"
URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL is required for PostgreSQL acceptance")


@pytest.fixture(autouse=True)
def clean_paper_tables() -> None:
    initialize_paper_schema(URL)
    with psycopg.connect(URL) as conn:
        conn.execute(
            """
            TRUNCATE paper_audit_event, order_intent_preview, target_allocation,
                     strategy_decision, paper_session, paper_position, paper_cash,
                     paper_account CASCADE
            """
        )


def test_single_paper_account_initialization_and_restart_persistence() -> None:
    source = "config/v85_operations.yaml:initial_capital_krw"
    assert ensure_paper_account(URL, Decimal("10000000"), source) == "CREATED"
    assert ensure_paper_account(URL, Decimal("10000000"), source) == "NO_OP"
    account = load_paper_account(URL)
    assert account["paper_account_id"] == PAPER_ACCOUNT_ID
    assert account["cash_krw"] == Decimal("10000000")
    assert account["positions"] == {}
    with pytest.raises(PaperPreviewError, match="initialization conflict"):
        ensure_paper_account(URL, Decimal("10000001"), source)


def test_latest_strategy_adapter_has_exact_parent_parity() -> None:
    preview = build_strategy_preview(ROOT, as_of=HISTORICAL_PREVIEW_AS_OF)
    spec = load_candidate_specs(ROOT)["V69_PARENT"]
    existing = build_candidate_ledgers(ROOT, spec, use_common_cutoff=True)
    expected = existing["ledger"].loc[
        existing["ledger"]["date"].eq(preview["as_of"])
    ].iloc[0]

    assert preview["strategy_id"] == "v69_fixed80_daily_control"
    assert preview["candidate_id"] == "V69_PARENT"
    assert preview["target_weights"] == json.loads(expected["target_weights_json"])
    assert preview["target_hash"] == expected["target_hash"]
    assert preview["candidate_fingerprint"] == spec.fingerprint
    assert preview["decision_receipt"]["status"] == "PASSED"


def test_preview_persists_atomically_and_is_idempotent() -> None:
    ensure_paper_account(
        URL, Decimal("10000000"), "config/v85_operations.yaml:initial_capital_krw"
    )
    preview = build_strategy_preview(ROOT, as_of=HISTORICAL_PREVIEW_AS_OF)
    preview["session_id"] = f"paper-{uuid.uuid4()}"
    account = load_paper_account(URL)
    intents = build_intent_previews(preview, account)

    assert save_paper_preview(URL, preview, intents) == "SAVED"
    assert save_paper_preview(URL, preview, intents) == "NO_OP"
    changed = deepcopy(preview)
    changed["input_hash"] = "0" * 64
    with pytest.raises(PaperPreviewError, match="session input hash conflict"):
        save_paper_preview(URL, changed, intents)

    restarted = load_paper_account(URL)
    assert restarted["cash_krw"] == Decimal("10000000")
    assert restarted["positions"] == {}
    summaries = latest_paper_summaries(URL)
    assert summaries["account"]["status"] == "ACTIVE"
    assert summaries["decision"]["authority_status"] == "PREVIEW_ONLY"
    assert all(row["authority_status"] == "PREVIEW_ONLY" for row in summaries["intents"])


def test_preview_does_not_mutate_cash_or_positions_and_zero_delta_is_no_action() -> None:
    ensure_paper_account(
        URL, Decimal("10000000"), "config/v85_operations.yaml:initial_capital_krw"
    )
    preview = build_strategy_preview(ROOT, as_of=HISTORICAL_PREVIEW_AS_OF)
    account = load_paper_account(URL)
    first = build_intent_previews(preview, account)
    second = build_intent_previews(preview, account)
    assert [row["intent_id"] for row in first] == [row["intent_id"] for row in second]

    matched = deepcopy(account)
    matched["positions"] = {
        row["symbol"]: row["target_quantity"] for row in preview["targets"]
    }
    assert build_intent_previews(preview, matched) == []
    assert load_paper_account(URL) == account


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda p: p.update(decision_receipt=None), "strategy receipt"),
        (lambda p: p.update(strategy_build_hash="bad"), "build hash"),
        (lambda p: p.update(selected_candidates=[]), "candidate"),
        (lambda p: p["targets"][0].update(reference_price=None), "executable target payload"),
        (lambda p: p["targets"][0].update(symbol="UNKNOWN"), "executable target rows"),
        (lambda p: p["targets"][0].update(target_weight=Decimal("0.95")), "target weight"),
    ],
)
def test_central_gate_fails_closed(mutation, message: str) -> None:
    preview = build_strategy_preview(ROOT, as_of=HISTORICAL_PREVIEW_AS_OF)
    mutation(preview)
    account = {
        "paper_account_id": PAPER_ACCOUNT_ID,
        "cash_krw": Decimal("10000000"),
        "positions": {},
        "status": "ACTIVE",
    }
    with pytest.raises(PaperPreviewError, match=message):
        build_intent_previews(preview, account)


def test_cash_shortage_is_left_to_v101_capacity_and_stale_data_holds() -> None:
    preview = build_strategy_preview(ROOT, as_of=HISTORICAL_PREVIEW_AS_OF)
    account = {
        "paper_account_id": PAPER_ACCOUNT_ID,
        "cash_krw": Decimal("1"),
        "positions": {},
        "status": "ACTIVE",
    }
    rows = build_intent_previews(preview, account)
    assert rows
    assert all(row["authority_status"] == "PREVIEW_ONLY" for row in rows)

    stale = deepcopy(preview)
    stale["market_data_status"] = "STALE"
    rows = build_intent_previews(
        stale,
        {
            "paper_account_id": PAPER_ACCOUNT_ID,
            "cash_krw": Decimal("10000000"),
            "positions": {},
            "status": "ACTIVE",
        },
    )
    assert all(row["authority_status"] == "HOLD_ONLY" for row in rows)


def test_transaction_rolls_back_on_invalid_target() -> None:
    ensure_paper_account(
        URL, Decimal("10000000"), "config/v85_operations.yaml:initial_capital_krw"
    )
    preview = build_strategy_preview(ROOT, as_of=HISTORICAL_PREVIEW_AS_OF)
    preview["session_id"] = f"rollback-{uuid.uuid4()}"
    intents = build_intent_previews(preview, load_paper_account(URL))
    preview["targets"][0]["reference_price"] = None
    with pytest.raises(Exception):
        save_paper_preview(URL, preview, intents)
    with psycopg.connect(URL) as conn:
        count = conn.execute(
            "SELECT count(*) FROM paper_session WHERE session_id=%s",
            (preview["session_id"],),
        ).fetchone()[0]
    assert count == 0


def test_integrated_mock_runner_and_real_mode_skip_are_safe(monkeypatch) -> None:
    import quant_harness.paper_decision_runtime as paper_runtime

    original_build_strategy_preview = paper_runtime.build_strategy_preview
    monkeypatch.setattr(
        paper_runtime,
        "build_strategy_preview",
        lambda root: original_build_strategy_preview(root, as_of=HISTORICAL_PREVIEW_AS_OF),
    )
    result = run_paper_decision_preview(ROOT, database_url=URL, mode="mock")
    assert result["status"] in {"SAVED", "NO_OP"}
    assert result["read_only_snapshot"]["mutation_calls"] == 0
    assert result["read_only_snapshot"]["cash_currencies"] == ["KRW", "USD"]
    assert result["paper_account"]["cash_krw"] == Decimal("10000000")
    assert result["authority_status"] == "PREVIEW_ONLY"
    assert result["decision"]["hold_reason"] is None
    sized_preview = original_build_strategy_preview(ROOT, as_of=HISTORICAL_PREVIEW_AS_OF)
    prior_prices = sized_preview["_preopen_sizing"]["prices"]
    for target in result["targets"]:
        symbol = str(target["symbol"]).zfill(6)
        expected_notional = Decimal("10000000") * Decimal(str(target["target_weight"]))
        expected_quantity = int(expected_notional / Decimal(str(prior_prices[symbol])))
        assert Decimal(str(target["reference_price"])) == Decimal(str(prior_prices[symbol]))
        assert Decimal(str(target["target_notional"])) == expected_notional
        assert Decimal(str(target["target_quantity"])) == expected_quantity
    for intent in result["intent_previews"]:
        assert result["execution_references"][str(intent["intent_id"])] > 0
    encoded = json.dumps(result, default=str)
    assert "access_token" not in encoded
    assert "client_secret" not in encoded
    assert "accountNo" not in encoded

    for key in (
        "TOSS_CLIENT_ID",
        "TOSS_CLIENT_SECRET",
        "TOSS_ACCOUNT_ALLOWLIST",
        "TOSS_API_BASE_URL",
        "TOSS_READ_ONLY_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)
    skipped = run_paper_decision_preview(ROOT, database_url=URL, mode="real-read-only")
    assert skipped["read_only_snapshot"]["status"] == "SKIPPED_NOT_CONFIGURED"
    assert skipped["read_only_snapshot"]["mutation_calls"] == 0
    assert skipped["paper_account"]["cash_krw"] == Decimal("10000000")


def test_historical_core_only_target_is_explicit_hold_only_against_90pct_cap() -> None:
    preview = build_strategy_preview(ROOT, as_of="2026-10-02")
    assert preview["as_of"].date().isoformat() == "2026-10-02"
    assert preview["selected_candidates"] == []
    assert preview["target_weights"] == {"069500": 1.0}
    account = {
        "paper_account_id": PAPER_ACCOUNT_ID,
        "cash_krw": Decimal("10000000"),
        "positions": {},
        "status": "ACTIVE",
    }
    assert build_intent_previews(preview, account) == []
    assert preview["authority_status"] == "HOLD_ONLY"
    assert preview["hold_reason"] == "NO_LEADER_CORE_FALLBACK_EXCEEDS_90_PERCENT_SINGLE_SYMBOL_CAP"


def test_v79_base_only_allocation_executes_when_generic_sleeve_is_empty() -> None:
    preview = build_candidate_strategy_preview(
        ROOT, "V79_NO63_VOL_GUARD", as_of="2019-03-04"
    )
    assert preview["selected_candidates"] == []
    assert preview["target_weights"] == pytest.approx({"069500": 0.44, "091180": 0.56})
    assert all(row["reason"] != "NO_LEADER_CORE_FALLBACK" for row in preview["targets"])
    account = {
        "paper_account_id": PAPER_ACCOUNT_ID,
        "cash_krw": Decimal("10000000"),
        "positions": {},
        "status": "ACTIVE",
    }
    intents = build_intent_previews(preview, account)
    assert intents
    assert preview["authority_status"] == "PREVIEW_ONLY"


def test_v79_unselected_100_percent_core_fallback_is_hold_only() -> None:
    preview = build_candidate_strategy_preview(
        ROOT, "V79_NO63_VOL_GUARD", as_of="2018-01-02"
    )
    assert preview["selected_candidates"] == []
    assert preview["target_weights"] == {"069500": 1.0}
    account = {
        "paper_account_id": PAPER_ACCOUNT_ID,
        "cash_krw": Decimal("10000000"),
        "positions": {},
        "status": "ACTIVE",
    }
    assert build_intent_previews(preview, account) == []
    assert preview["authority_status"] == "HOLD_ONLY"
    assert preview["hold_reason"] == "NO_SELECTED_TARGET_EXCEEDS_90_PERCENT_SINGLE_SYMBOL_CAP"


def test_first_panel_session_is_allowed_as_hold_only_warmup_without_prior_mark() -> None:
    preview = build_strategy_preview(ROOT, as_of="2018-01-02")
    assert preview["_preopen_sizing"]["prior_session"] is None
    assert preview["_preopen_sizing"]["prices"] == {}


def test_configured_real_read_only_contract_uses_only_oauth_post_and_business_get() -> None:
    env = {
        "TOSS_CLIENT_ID": "fixture-client",
        "TOSS_CLIENT_SECRET": "fixture-secret",
        "TOSS_ACCOUNT_ALLOWLIST": "MOCK-0000-1234",
        "TOSS_API_BASE_URL": "https://mock.invalid",
        "TOSS_READ_ONLY_TIMEOUT_SECONDS": "1",
    }
    delegate = MockTransport()
    result = run_toss_snapshot(
        database_url=URL,
        mode="real-read-only",
        env=env,
        transport=delegate,
    )
    assert result["status"] == "SAVED"
    assert result["oauth_posts"] == 1
    assert result["business_methods"] == ["GET"]
    assert result["mutation_calls"] == 0
    encoded = json.dumps(result, default=str)
    assert "fixture-secret" not in encoded
    assert "MOCK-0000-1234" not in encoded


def test_real_read_only_uses_official_defaults_and_single_account_when_allowlist_is_absent() -> None:
    result = run_toss_snapshot(
        database_url=URL,
        mode="real-read-only",
        env={
            "TOSS_CLIENT_ID": "fixture-client",
            "TOSS_CLIENT_SECRET": "fixture-secret",
        },
        transport=MockTransport(),
    )
    assert result["status"] == "SAVED"
    assert result["business_methods"] == ["GET"]
    assert result["mutation_calls"] == 0


def test_real_read_only_accepts_verified_nested_market_value_contract() -> None:
    class ActualHoldingTransport(MockTransport):
        def __call__(self, request, timeout):
            if request.get_method().upper() == "GET" and request.full_url.split("?", 1)[0].endswith("/holdings"):
                self.calls.append(("GET", "/api/v1/holdings"))
                return 200, {}, json.dumps({"result": {"items": [{
                    "symbol": "AAPL", "quantity": "2", "currency": "USD",
                    "averagePurchasePrice": "100", "lastPrice": "101",
                    "marketValue": {"amount": "202", "amountAfterCost": "200", "purchaseAmount": "200"},
                }]}}).encode("utf-8")
            return super().__call__(request, timeout)

    result = run_toss_snapshot(
        database_url=URL,
        mode="real-read-only",
        env={"TOSS_CLIENT_ID": "fixture-client", "TOSS_CLIENT_SECRET": "fixture-secret"},
        transport=ActualHoldingTransport(),
    )
    assert result["status"] == "SAVED"
    assert result["holding_count"] == 1


def test_real_read_only_failure_is_sanitized_and_mutation_is_blocked_before_delegate() -> None:
    malicious = "token-secret accountNo=MOCK-0000-1234"

    def failing_transport(request, timeout):
        raise TossApiError(malicious)

    env = {
        "TOSS_CLIENT_ID": "fixture-client",
        "TOSS_CLIENT_SECRET": "token-secret",
        "TOSS_ACCOUNT_ALLOWLIST": "MOCK-0000-1234",
        "TOSS_API_BASE_URL": "https://mock.invalid",
        "TOSS_READ_ONLY_TIMEOUT_SECONDS": "1",
    }
    result = run_toss_snapshot(
        database_url=URL,
        mode="real-read-only",
        env=env,
        transport=failing_transport,
    )
    encoded = json.dumps(result, default=str)
    assert result["status"] == "FAILED"
    assert result["mutation_calls"] == 0
    assert "token-secret" not in encoded
    assert "MOCK-0000-1234" not in encoded
    assert "accountNo" not in encoded

    called = False

    def must_not_run(request, timeout):
        nonlocal called
        called = True
        raise AssertionError("delegate must not receive broker mutations")

    recorder = SafeRecordingTransport(must_not_run)
    request = Request("https://mock.invalid/api/v1/orders", data=b"{}", method="POST")
    with pytest.raises(TossApiError, match="blocked before network"):
        recorder(request, 1)
    assert called is False
    assert recorder.mutation_calls == 1

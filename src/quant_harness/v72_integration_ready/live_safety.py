from __future__ import annotations

from dataclasses import dataclass
from typing import Final


LIVE_BUILD_CAPABILITY: Final[bool] = False
CURRENT_RELEASE_LIVE_AUTHORITY: Final[bool] = False


@dataclass(frozen=True)
class LiveOrderSafetyContext:
    broker_contract_verified: bool
    account_allowlisted: bool
    order_notional_within_limit: bool
    order_count_within_limit: bool
    reconciliation_normal: bool
    kill_switch_clear: bool
    explicit_approval: bool
    idempotency_key_present: bool
    paper_live_environment_separated: bool


@dataclass(frozen=True)
class LiveOrderSafetyDecision:
    allowed: bool
    blockers: tuple[str, ...]


def evaluate_live_order_safety(context: LiveOrderSafetyContext) -> LiveOrderSafetyDecision:
    """Evaluate every required gate; this release has no live build authority."""
    checks = (
        ("LIVE_BUILD_CAPABILITY_DISABLED", LIVE_BUILD_CAPABILITY),
        ("BROKER_CONTRACT_UNVERIFIED", context.broker_contract_verified),
        ("ACCOUNT_NOT_ALLOWLISTED", context.account_allowlisted),
        ("ORDER_NOTIONAL_LIMIT_UNVERIFIED", context.order_notional_within_limit),
        ("ORDER_COUNT_LIMIT_UNVERIFIED", context.order_count_within_limit),
        ("RECONCILIATION_NOT_NORMAL", context.reconciliation_normal),
        ("KILL_SWITCH_NOT_CLEAR", context.kill_switch_clear),
        ("EXPLICIT_APPROVAL_MISSING", context.explicit_approval),
        ("IDEMPOTENCY_KEY_MISSING", context.idempotency_key_present),
        ("PAPER_LIVE_ENVIRONMENT_NOT_SEPARATED", context.paper_live_environment_separated),
        ("CURRENT_RELEASE_LIVE_AUTHORITY_DISABLED", CURRENT_RELEASE_LIVE_AUTHORITY),
    )
    blockers = tuple(name for name, passed in checks if not passed)
    return LiveOrderSafetyDecision(allowed=not blockers, blockers=blockers)


def current_release_live_order_decision(
    *,
    account_id: str | None,
    idempotency_key: str | None,
) -> LiveOrderSafetyDecision:
    """Return the fail-closed decision for the currently shipped integration."""
    return evaluate_live_order_safety(
        LiveOrderSafetyContext(
            broker_contract_verified=False,
            account_allowlisted=False,
            order_notional_within_limit=False,
            order_count_within_limit=False,
            reconciliation_normal=False,
            kill_switch_clear=False,
            explicit_approval=False,
            idempotency_key_present=bool(idempotency_key),
            paper_live_environment_separated=False,
        )
    )

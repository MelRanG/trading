from __future__ import annotations

import json
import mimetypes
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import yaml

REPORT = "v86_control_plane_dashboard"


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    return value or "unnamed_strategy"


def _json_read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML object required: {path}")
    return payload


def _max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    arr = np.asarray(values, dtype=float)
    peaks = np.maximum.accumulate(arr)
    dd = arr / peaks - 1.0
    return float(np.nanmin(dd))


def _role_from_status(status: str) -> str:
    text = status.upper()
    if "CHAMPION" in text or "CONTROL" in text:
        return "CHAMPION"
    if "CHALLENGER" in text:
        return "CHALLENGER"
    if "ARCHIVED" in text:
        return "ARCHIVED"
    return "SHADOW"


@dataclass(frozen=True)
class StrategyRecord:
    strategy_id: str
    label: str
    role: str
    status: str
    parent_strategy_id: str | None
    created_by: str
    source: str
    account_id: str | None
    runtime_compatible: bool
    parameters: dict[str, Any]
    scenario: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "label": self.label,
            "role": self.role,
            "status": self.status,
            "parent_strategy_id": self.parent_strategy_id,
            "created_by": self.created_by,
            "source": self.source,
            "account_id": self.account_id,
            "runtime_compatible": self.runtime_compatible,
            "parameters": self.parameters,
            "scenario": self.scenario,
        }


class ControlPlane:
    """One strategy-agnostic UI backed by isolated per-strategy accounts."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.config = _yaml(self.root / "config/v86_control_plane.yaml")
        self.operations = _yaml(self.root / self.config["operations_config"])
        self.initial_capital = float(self.operations.get("initial_capital_krw", 10_000_000))

    @property
    def db_path(self) -> Path:
        return self.root / self.operations["operations"]["dual_paper_db"]

    def _base_registry(self) -> list[StrategyRecord]:
        reg = _yaml(self.root / self.config["registry_file"])
        records: list[StrategyRecord] = []
        for item in reg.get("strategies", []):
            sid = str(item["strategy_id"])
            status = str(item.get("status", "SHADOW"))
            records.append(
                StrategyRecord(
                    strategy_id=sid,
                    label=str(item.get("label", sid)),
                    role=_role_from_status(status),
                    status=status,
                    parent_strategy_id=None,
                    created_by="ResearchHarness",
                    source=self.config["registry_file"],
                    account_id=item.get("paper_account_id"),
                    runtime_compatible=bool(item.get("runtime_compatible", False)),
                    parameters=dict(item.get("parameters") or {}),
                )
            )
        return records

    def _generated_feedback_candidates(self) -> list[dict[str, Any]]:
        proposals_path = self.root / self.config["feedback_proposals_file"]
        metrics_path = self.root / self.config["strategy_metrics_file"]
        metrics: dict[str, dict[str, Any]] = {}
        if metrics_path.exists():
            frame = pd.read_csv(metrics_path)
            for row in frame.to_dict("records"):
                metrics[str(row.get("scenario"))] = row
        rows: list[dict[str, Any]] = []
        if proposals_path.exists():
            proposals = pd.read_csv(proposals_path)
            scenario_col = "proposed_candidate" if "proposed_candidate" in proposals.columns else "candidate"
            reason_col = "proposal_reason" if "proposal_reason" in proposals.columns else "issue"
            promoted_col = "promoted_for_next_fold" if "promoted_for_next_fold" in proposals.columns else "passed_backtest"
            if "proposal_created" in proposals.columns:
                proposals = proposals[proposals["proposal_created"].fillna(False).astype(bool)]
            for scenario in sorted(set(proposals.get(scenario_col, pd.Series(dtype=str)).dropna().astype(str))):
                if scenario.endswith("_PARENT"):
                    continue
                family = "V69" if scenario.startswith("V69") else "V79" if scenario.startswith("V79") else "UNKNOWN"
                parent = "v69_fixed80_daily_control" if family == "V69" else "v79_core70_generic_trend30" if family == "V79" else None
                selected = proposals[proposals[scenario_col].astype(str) == scenario]
                reasons = sorted(set(selected.get(reason_col, pd.Series(dtype=str)).dropna().astype(str)))
                promoted = bool(selected.get(promoted_col, pd.Series(dtype=bool)).fillna(False).astype(bool).any())
                rows.append(
                    {
                        "strategy_id": f"feedback_{_slug(scenario)}",
                        "scenario": scenario,
                        "label": scenario.replace("_", " ").title(),
                        "role": "SHADOW",
                        "status": "PROMOTED_SHADOW" if promoted else "RESEARCH_CANDIDATE",
                        "parent_strategy_id": parent,
                        "created_by": "FeedbackAgent",
                        "source": self.config["feedback_proposals_file"],
                        "account_id": None,
                        "runtime_compatible": False,
                        "parameters": {"proposal_reasons": reasons},
                        "backtest_metrics": metrics.get(scenario, {}),
                    }
                )
        return rows

    def ensure_feedback_candidate_registry(self) -> Path:
        path = self.root / self.config["feedback_candidate_registry"]
        path.parent.mkdir(parents=True, exist_ok=True)
        source_rel = self.config.get("feedback_candidate_registry_source")
        source_path = self.root / source_rel if source_rel else None
        if source_path is not None and source_path.exists():
            generated = _json_read(source_path, {"candidates": []}).get("candidates", [])
        else:
            generated = self._generated_feedback_candidates()
        existing = _json_read(path, {"schema_version": 1, "candidates": []})
        manual = {
            str(item.get("strategy_id")): item
            for item in existing.get("candidates", [])
            if isinstance(item, dict) and item.get("managed_by") == "external"
        }
        combined = {str(item["strategy_id"]): item for item in generated}
        combined.update(manual)
        payload = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "policy": {
                "one_ui_for_all_strategies": True,
                "one_isolated_account_per_paper_strategy": True,
                "feedback_candidates_default_to_shadow": True,
                "automatic_live_promotion": False,
            },
            "candidates": [combined[k] for k in sorted(combined)],
        }
        # Reading the catalog must not rewrite a historical report solely because
        # the volatile generation timestamp changed.
        if path.exists() and existing.get("policy") == payload["policy"] and existing.get("candidates") == payload["candidates"]:
            return path
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return path

    def catalog(self) -> list[dict[str, Any]]:
        base = {x.strategy_id: x.as_dict() for x in self._base_registry()}
        path = self.ensure_feedback_candidate_registry()
        dynamic = _json_read(path, {"candidates": []}).get("candidates", [])
        for item in dynamic:
            sid = str(item["strategy_id"])
            base[sid] = {
                "strategy_id": sid,
                "label": str(item.get("label", sid)),
                "role": str(item.get("role", "SHADOW")),
                "status": str(item.get("status", "RESEARCH_CANDIDATE")),
                "parent_strategy_id": item.get("parent_strategy_id"),
                "created_by": str(item.get("created_by", "FeedbackAgent")),
                "source": str(item.get("source", path.relative_to(self.root))),
                "account_id": item.get("account_id"),
                "runtime_compatible": bool(item.get("runtime_compatible", False)),
                "parameters": dict(item.get("parameters") or {}),
                "scenario": item.get("scenario"),
                "backtest_metrics": dict(item.get("backtest_metrics") or {}),
            }
        summaries = self._account_summaries()
        for sid, record in base.items():
            account = summaries.get(sid)
            record["account_available"] = account is not None
            record["account_summary"] = account
        priority = {"CHAMPION": 0, "CHALLENGER": 1, "SHADOW": 2, "ARCHIVED": 3}
        return sorted(base.values(), key=lambda x: (priority.get(x["role"], 9), x["strategy_id"]))

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise FileNotFoundError(f"dual paper DB not found: {self.db_path}")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _account_summaries(self) -> dict[str, dict[str, Any]]:
        if not self.db_path.exists():
            return {}
        output: dict[str, dict[str, Any]] = {}
        with self._connect() as conn:
            strategy_ids = [str(r[0]) for r in conn.execute("SELECT strategy_id FROM accounts ORDER BY strategy_id")]
            for sid in strategy_ids:
                sessions = conn.execute(
                    "SELECT session,nav,cash,holdings_json FROM sessions WHERE strategy_id=? ORDER BY session",
                    (sid,),
                ).fetchall()
                if not sessions:
                    continue
                navs = [float(r[1]) for r in sessions]
                latest = sessions[-1]
                output[sid] = {
                    "latest_session": str(latest[0]),
                    "latest_nav_krw": float(latest[1]),
                    "cash_krw": float(latest[2]),
                    "return_pct": (float(latest[1]) / self.initial_capital - 1.0) * 100.0,
                    "max_drawdown_pct": (_max_drawdown(navs) or 0.0) * 100.0,
                    "session_count": len(sessions),
                    "holding_count": len([v for v in json.loads(str(latest[3])).values() if float(v) != 0]),
                }
        return output

    def strategy_detail(self, strategy_id: str) -> dict[str, Any]:
        catalog = {x["strategy_id"]: x for x in self.catalog()}
        if strategy_id not in catalog:
            raise KeyError(strategy_id)
        record = catalog[strategy_id]
        detail: dict[str, Any] = {"strategy": record, "account": None, "equity_curve": [], "fills": [], "holdings": []}
        if not self.db_path.exists() or not record.get("account_available"):
            detail["research_only"] = True
            return detail
        market_path = self.root / self.operations["operations"]["canonical_market"]
        market = pd.read_csv(market_path, dtype={"ticker": str}) if market_path.exists() else pd.DataFrame()
        with self._connect() as conn:
            account = conn.execute(
                "SELECT cash,quantities_json,pending,prior_signature FROM accounts WHERE strategy_id=?",
                (strategy_id,),
            ).fetchone()
            sessions = conn.execute(
                "SELECT session,nav,cash,holdings_json FROM sessions WHERE strategy_id=? ORDER BY session",
                (strategy_id,),
            ).fetchall()
            fills = conn.execute(
                "SELECT session,ticker,side,quantity,reference_open,execution_price,fee,impact_bps,participation "
                "FROM fills WHERE strategy_id=? ORDER BY session DESC,ticker LIMIT 100",
                (strategy_id,),
            ).fetchall()
        quantities = json.loads(str(account[1])) if account else {}
        latest_session = str(sessions[-1][0]) if sessions else None
        close_map: dict[str, float] = {}
        if latest_session and not market.empty:
            rows = market[market["date"].astype(str) == latest_session]
            close_map = {str(r.ticker).zfill(6): float(r.close) for r in rows.itertuples(index=False)}
        holdings = []
        for ticker, quantity in sorted(quantities.items()):
            if not quantity:
                continue
            close = close_map.get(str(ticker).zfill(6))
            holdings.append(
                {
                    "ticker": str(ticker).zfill(6),
                    "quantity": int(quantity),
                    "close_krw": close,
                    "market_value_krw": float(quantity) * close if close is not None else None,
                }
            )
        navs = [float(x[1]) for x in sessions]
        detail["account"] = {
            "cash_krw": float(account[0]),
            "pending": bool(account[2]),
            "latest_session": latest_session,
            "latest_nav_krw": navs[-1] if navs else None,
            "return_pct": (navs[-1] / self.initial_capital - 1.0) * 100.0 if navs else None,
            "max_drawdown_pct": (_max_drawdown(navs) or 0.0) * 100.0,
        }
        detail["equity_curve"] = [{"session": str(x[0]), "nav_krw": float(x[1])} for x in sessions]
        detail["holdings"] = holdings
        detail["fills"] = [dict(x) for x in fills]
        detail["research_only"] = False
        return detail

    def _latest_manifest(self) -> dict[str, Any]:
        directory = self.root / self.operations["operations"]["run_manifest_dir"]
        files = sorted(directory.glob("V85-*.json")) if directory.exists() else []
        return _json_read(files[-1], {}) if files else {}

    def _alerts(self, limit: int = 20) -> list[dict[str, Any]]:
        path = self.root / self.operations["operations"]["alert_log"]
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"severity": "WARN", "code": "MALFORMED_ALERT", "message": line})
        return list(reversed(rows))

    def _data_health(self) -> dict[str, Any]:
        path = self.root / self.operations["operations"]["canonical_market"]
        if not path.exists():
            return {"available": False, "path": str(path.relative_to(self.root))}
        frame = pd.read_csv(path, dtype={"ticker": str})
        latest = str(frame["date"].max()) if len(frame) else None
        return {
            "available": True,
            "path": str(path.relative_to(self.root)),
            "rows": int(len(frame)),
            "ticker_count": int(frame["ticker"].nunique()),
            "start": str(frame["date"].min()) if len(frame) else None,
            "end": latest,
            "duplicates": int(frame.duplicated(["date", "ticker"]).sum()),
            "price_scales": sorted(set(frame.get("price_scale", pd.Series(dtype=str)).dropna().astype(str))),
            "sources": sorted(set(frame.get("source", pd.Series(dtype=str)).dropna().astype(str))),
        }

    def _readiness(self) -> dict[str, Any]:
        paths = {
            "actual_data": self.root / "reports/v87_actual_data_ingestion/summary.json",
            "order_reconciliation": self.root / "reports/v88_order_reconciliation/summary.json",
            "forward_governance": self.root / "reports/v89_forward_governance/summary.json",
        }
        output: dict[str, Any] = {}
        for key, path in paths.items():
            payload = _json_read(path, {})
            output[key] = {
                "available": bool(payload),
                "status": payload.get("status", "NOT_RUN"),
                "gates_passed": bool(payload.get("gates")) and all(bool(v) for v in payload.get("gates", {}).values()),
            }
        evaluation = _json_read(self.root / "reports/v89_forward_governance/evaluation.json", {})
        output["forward_governance"].update({
            "canary_eligible": bool(evaluation.get("canary_eligible", False)),
            "next_stage": evaluation.get("next_stage", "READ_ONLY"),
            "strategy_progress": evaluation.get("strategies", []),
        })
        return output

    def payload(self, strategy_id: str | None = None) -> dict[str, Any]:
        catalog = self.catalog()
        default = str(self.config.get("default_strategy_id"))
        selected = strategy_id if strategy_id and any(x["strategy_id"] == strategy_id for x in catalog) else default
        if not any(x["strategy_id"] == selected for x in catalog) and catalog:
            selected = catalog[0]["strategy_id"]
        manifest = self._latest_manifest()
        return {
            "version": "V86",
            "mode": "PAPER",
            "live_execution_allowed": False,
            "architecture": {
                "ui_instances": 1,
                "ui_model": "STRATEGY_AGNOSTIC_CONTROL_PLANE",
                "paper_account_model": "ONE_ISOLATED_ACCOUNT_PER_RUNTIME_STRATEGY",
                "feedback_candidate_model": "DYNAMIC_REGISTRY_SHADOW_FIRST",
                "final_convergence": "DEFAULT_VIEW_FOLLOWS_CHAMPION_WITH_HISTORY_RETAINED",
            },
            "default_strategy_id": default,
            "selected_strategy_id": selected,
            "strategies": catalog,
            "selected": self.strategy_detail(selected) if selected else None,
            "operations": {
                "latest_manifest": manifest,
                "stages": manifest.get("stages", {}),
                "status": manifest.get("status", "NOT_RUN"),
            },
            "data_health": self._data_health(),
            "alerts": self._alerts(),
            "readiness": self._readiness(),
            "governance": {
                "automatic_live_promotion": False,
                "manual_live_orders": False,
                "feedback_may_register_shadow_candidate": True,
                "feedback_may_mutate_champion_in_place": False,
            },
        }


@dataclass
class ControlPlaneApplication:
    plane: ControlPlane
    static_dir: Path

    def create_handler(self):
        app = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "QuantHarnessControlPlane/86.0"

            def _security_headers(self) -> None:
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                    "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
                )

            def _json(self, payload: Any, status: int = 200) -> None:
                raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self._security_headers()
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path == "/api/control-plane":
                    strategy_id = parse_qs(parsed.query).get("strategy_id", [None])[0]
                    try:
                        self._json(app.plane.payload(strategy_id))
                    except KeyError:
                        self._json({"error": "strategy not found"}, 404)
                    return
                if parsed.path == "/api/health":
                    payload = app.plane.payload()
                    self._json(
                        {
                            "ok": payload["data_health"].get("available", False),
                            "mode": payload["mode"],
                            "live_execution_allowed": False,
                            "strategy_count": len(payload["strategies"]),
                        }
                    )
                    return
                if parsed.path.startswith("/api/"):
                    self._json({"error": "read-only control plane"}, 404)
                    return
                path = "/index.html" if parsed.path == "/" else parsed.path
                target = (app.static_dir / path.lstrip("/")).resolve()
                try:
                    target.relative_to(app.static_dir.resolve())
                except ValueError:
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                if not target.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                raw = target.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(raw)))
                self._security_headers()
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self) -> None:  # noqa: N802
                self._json({"error": "control plane is read-only and live orders are blocked"}, 403)

            def log_message(self, fmt: str, *args: Any) -> None:
                print(f"[v86-control-plane] {self.client_address[0]} - {fmt % args}")

        return Handler


def run_server(root: Path | str, *, host: str = "127.0.0.1", port: int = 8788) -> None:
    root = Path(root)
    plane = ControlPlane(root)
    static_dir = root / plane.config["static_dir"]
    if host not in {"127.0.0.1", "localhost", "::1"} and os.getenv("V86_ALLOW_REMOTE_CONTROL_PLANE", "false").lower() != "true":
        raise ValueError("remote binding is blocked unless V86_ALLOW_REMOTE_CONTROL_PLANE=true")
    server = ThreadingHTTPServer((host, port), ControlPlaneApplication(plane, static_dir).create_handler())
    print(f"V86 control plane: http://{host}:{port}")
    print("Mode: PAPER / READ-ONLY / LIVE BLOCKED")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    plane = ControlPlane(root)
    payload = plane.payload()
    out = root / "reports" / REPORT
    out.mkdir(parents=True, exist_ok=True)
    gates = {
        "single_ui_for_all_strategies": payload["architecture"]["ui_instances"] == 1,
        "isolated_account_model": payload["architecture"]["paper_account_model"].startswith("ONE_ISOLATED"),
        "operational_strategies_visible": sum(bool(x.get("account_available")) for x in payload["strategies"]) >= 2,
        "feedback_candidates_discovered": any(x.get("created_by") == "FeedbackAgent" for x in payload["strategies"]),
        "champion_default_view": payload["default_strategy_id"] == "v69_fixed80_daily_control",
        "live_blocked": not payload["live_execution_allowed"],
        "read_only_governance": not payload["governance"]["manual_live_orders"],
    }
    (out / "control_plane_snapshot.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    pd.DataFrame([{"gate": k, "passed": v} for k, v in gates.items()]).to_csv(out / "quality_gates.csv", index=False)
    summary = {"status": "v86_strategy_agnostic_control_plane_complete_live_blocked", "gates": gates, "strategy_count": len(payload["strategies"])}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

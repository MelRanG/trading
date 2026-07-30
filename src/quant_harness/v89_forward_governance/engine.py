from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

REPORT = "v89_forward_governance"


class FrozenContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class FrozenHashes:
    strategy_registry_sha256: str
    execution_config_sha256: str
    data_contract_sha256: str


@dataclass(frozen=True)
class ForwardObservation:
    session: str
    strategy_id: str
    plan_hash: str
    strategy_hash: str
    target_match_ratio: float
    execution_nav_drift_pct: float
    data_gate_passed: bool
    reconciliation_passed: bool
    critical_alerts_unresolved: int


class ForwardGovernance:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.cfg = yaml.safe_load((self.root / "config/v89_forward_governance.yaml").read_text(encoding="utf-8"))
        self.report_dir = self.root / self.cfg["paths"]["report_dir"]
        self.report_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sha(path: Path) -> str:
        return sha256(path.read_bytes()).hexdigest()

    def current_hashes(self) -> FrozenHashes:
        p = self.cfg["paths"]
        return FrozenHashes(
            strategy_registry_sha256=self._sha(self.root / p["strategy_registry"]),
            execution_config_sha256=self._sha(self.root / p["execution_config"]),
            data_contract_sha256=self._sha(self.root / p["data_contract"]),
        )

    @property
    def registry_path(self) -> Path:
        return self.root / self.cfg["paths"]["registry"]

    @property
    def observations_path(self) -> Path:
        return self.root / self.cfg["paths"]["observations"]

    def freeze(self, *, start_session: str | None = None, overwrite: bool = False) -> dict[str, Any]:
        if self.registry_path.exists() and not overwrite:
            return json.loads(self.registry_path.read_text(encoding="utf-8"))
        hashes = self.current_hashes()
        registry = yaml.safe_load((self.root / self.cfg["paths"]["strategy_registry"]).read_text(encoding="utf-8"))
        strategies = [
            {
                "strategy_id": x["strategy_id"],
                "status": x.get("status"),
                "paper_account_id": x.get("paper_account_id"),
                "parameters": x.get("parameters", {}),
            }
            for x in registry.get("strategies", [])
            if x.get("runtime_compatible")
        ]
        payload = {
            "schema_version": 1,
            "trial_id": f"FROZEN-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "start_session": start_session,
            "status": "READY_NOT_STARTED" if not start_session else "RUNNING",
            "hashes": asdict(hashes),
            "strategies": strategies,
            "minimum_sessions": int(self.cfg["trial"]["minimum_sessions"]),
            "recommended_sessions": int(self.cfg["trial"]["recommended_sessions"]),
            "mutation_allowed": False,
            "live_execution_allowed": False,
        }
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return payload

    def verify_frozen_contract(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            raise FrozenContractError("trial is not frozen")
        registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        expected = registry["hashes"]
        actual = asdict(self.current_hashes())
        mismatches = {k: {"expected": expected[k], "actual": actual[k]} for k in expected if expected[k] != actual[k]}
        if mismatches:
            raise FrozenContractError(f"frozen contract mutation detected: {mismatches}")
        return {"passed": True, "hashes": actual}

    def append_observation(self, observation: ForwardObservation) -> None:
        self.verify_frozen_contract()
        row = asdict(observation)
        frame = pd.DataFrame([row])
        if self.observations_path.exists():
            existing = pd.read_csv(self.observations_path, dtype={"strategy_id": str})
            duplicate = (existing["session"].astype(str) == observation.session) & (existing["strategy_id"].astype(str) == observation.strategy_id)
            if duplicate.any():
                old = existing.loc[duplicate].iloc[0].to_dict()
                comparable = {k: old[k] for k in row}
                for key in ("target_match_ratio", "execution_nav_drift_pct"):
                    comparable[key] = float(comparable[key])
                for key in ("data_gate_passed", "reconciliation_passed"):
                    comparable[key] = str(comparable[key]).lower() in {"true", "1"}
                comparable["critical_alerts_unresolved"] = int(comparable["critical_alerts_unresolved"])
                if comparable != row:
                    raise FrozenContractError("observation idempotency conflict")
                return
            frame = pd.concat([existing, frame], ignore_index=True)
        self.observations_path.parent.mkdir(parents=True, exist_ok=True)
        frame.sort_values(["session", "strategy_id"]).to_csv(self.observations_path, index=False)

    def evaluate(self) -> dict[str, Any]:
        registry = self.freeze()
        contract = self.verify_frozen_contract()
        if self.observations_path.exists():
            obs = pd.read_csv(self.observations_path, dtype={"strategy_id": str})
        else:
            obs = pd.DataFrame(columns=[f.name for f in ForwardObservation.__dataclass_fields__.values()])
        strategy_ids = {x["strategy_id"] for x in registry["strategies"]}
        trial = self.cfg["trial"]
        per_strategy = []
        for sid in sorted(strategy_ids):
            rows = obs[obs["strategy_id"].astype(str) == sid].copy() if len(obs) else obs.copy()
            sessions = rows["session"].nunique() if len(rows) else 0
            target_failures = int((pd.to_numeric(rows.get("target_match_ratio", pd.Series(dtype=float)), errors="coerce") < 1.0 - float(trial["maximum_target_mismatch_ratio"])).sum()) if len(rows) else 0
            drift_failures = int((pd.to_numeric(rows.get("execution_nav_drift_pct", pd.Series(dtype=float)), errors="coerce").abs() > float(trial["maximum_execution_nav_drift_pct"])).sum()) if len(rows) else 0
            data_failures = int((~rows.get("data_gate_passed", pd.Series(dtype=bool)).astype(bool)).sum()) if len(rows) else 0
            reconcile_failures = int((~rows.get("reconciliation_passed", pd.Series(dtype=bool)).astype(bool)).sum()) if len(rows) else 0
            critical = int(pd.to_numeric(rows.get("critical_alerts_unresolved", pd.Series(dtype=int)), errors="coerce").fillna(0).sum()) if len(rows) else 0
            minimum_met = sessions >= int(trial["minimum_sessions"])
            recommended_met = sessions >= int(trial["recommended_sessions"])
            passed = minimum_met and target_failures == 0 and drift_failures == 0 and data_failures <= int(trial["maximum_data_failure_sessions"]) and reconcile_failures == 0 and critical == 0
            per_strategy.append(
                {
                    "strategy_id": sid,
                    "sessions": int(sessions),
                    "minimum_met": minimum_met,
                    "recommended_met": recommended_met,
                    "target_failures": target_failures,
                    "drift_failures": drift_failures,
                    "data_failures": data_failures,
                    "reconciliation_failures": reconcile_failures,
                    "critical_alerts_unresolved": critical,
                    "paper_gate_passed": passed,
                }
            )
        all_minimum = bool(per_strategy) and all(x["minimum_met"] for x in per_strategy)
        all_pass = bool(per_strategy) and all(x["paper_gate_passed"] for x in per_strategy)
        eligible = all_minimum and all_pass
        result = {
            "status": "READY_NOT_STARTED" if not len(obs) else "PAPER_GATE_PASSED" if eligible else "PAPER_RUNNING_OR_BLOCKED",
            "contract": contract,
            "strategies": per_strategy,
            "canary_eligible": eligible,
            "next_stage": self.cfg["promotion"]["first_live_stage"] if eligible else "READ_ONLY",
            "human_approval_required": True,
            "automatic_live_promotion_allowed": False,
            "live_execution_allowed": False,
        }
        (self.report_dir / "evaluation.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        pd.DataFrame(per_strategy).to_csv(self.report_dir / "strategy_forward_gates.csv", index=False)
        return result


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    gov = ForwardGovernance(root)
    registry = gov.freeze(overwrite=False)
    result = gov.evaluate()
    v88_path = root / gov.cfg["paths"]["v88_summary"]
    v85_path = root / gov.cfg["paths"]["v85_summary"]
    v88 = json.loads(v88_path.read_text(encoding="utf-8")) if v88_path.exists() else {}
    v85 = json.loads(v85_path.read_text(encoding="utf-8")) if v85_path.exists() else {}
    gates = {
        "frozen_hashes_written": all(registry["hashes"].values()),
        "two_runtime_strategies_frozen": len(registry["strategies"]) == 2,
        "strategy_mutation_blocked": registry["mutation_allowed"] is False,
        "forward_trial_not_faked": result["canary_eligible"] is False and result["status"] == "READY_NOT_STARTED",
        "v88_reconciliation_ready": bool(v88.get("gates")) and all(v88["gates"].values()),
        "v85_operational_ready": bool(v85.get("gates")) and all(v85["gates"].values()),
        "automatic_live_promotion_blocked": result["automatic_live_promotion_allowed"] is False,
        "live_blocked": result["live_execution_allowed"] is False,
    }
    pd.DataFrame([{"gate": k, "passed": v} for k, v in gates.items()]).to_csv(gov.report_dir / "quality_gates.csv", index=False)
    summary = {"status": "v89_frozen_forward_governance_ready_not_started_live_blocked", "gates": gates, "registry": registry, "evaluation": result}
    (gov.report_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary

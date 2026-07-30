from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd
import yaml

REPORT = "v87_actual_data_ingestion"


class IngestionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderBatch:
    provider: str
    symbol: str
    rows: tuple[dict[str, Any], ...]
    adjusted_ohlc_verified: bool
    source_tag: str
    retrieved_at: str
    raw_metadata: dict[str, Any]


class CandleProvider(Protocol):
    provider_name: str

    def get_daily_batch(self, symbol: str, *, start_date: str, end_date: str) -> ProviderBatch: ...


class CsvFixtureProvider:
    provider_name = "CSV_FIXTURE_TOSS_V19C"

    def __init__(self, directory: Path | str):
        self.directory = Path(directory)

    def get_daily_batch(self, symbol: str, *, start_date: str, end_date: str) -> ProviderBatch:
        ticker = str(symbol).zfill(6)
        path = self.directory / f"{ticker}_1d.csv"
        if not path.exists():
            raise IngestionError(f"fixture missing for {ticker}")
        frame = pd.read_csv(path)
        dates = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.normalize()
        frame = frame.assign(date=dates.dt.strftime("%Y-%m-%d"))
        frame = frame[(frame["date"] >= start_date) & (frame["date"] <= end_date)]
        source_values = set(frame.get("source", pd.Series(dtype=str)).dropna().astype(str))
        if source_values and source_values != {"toss_openapi_1d_adjusted"}:
            raise IngestionError(f"unexpected fixture source for {ticker}: {sorted(source_values)}")
        rows = []
        for r in frame.itertuples(index=False):
            rows.append(
                {
                    "date": str(r.date),
                    "ticker": ticker,
                    "open": float(r.open),
                    "high": float(r.high),
                    "low": float(r.low),
                    "close": float(r.close),
                    "volume": float(r.volume),
                    "value_approx": float(r.close) * float(r.volume),
                }
            )
        return ProviderBatch(
            provider=self.provider_name,
            symbol=ticker,
            rows=tuple(rows),
            adjusted_ohlc_verified=True,
            source_tag="toss_openapi_1d_adjusted",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            raw_metadata={"fixture_path": str(path), "row_count": len(rows)},
        )


class TossGatewayProvider:
    """Adapter around a configured gateway. It refuses ambiguous raw/adjusted price scales."""

    provider_name = "TOSS_CONFIGURABLE_GATEWAY"

    def __init__(self, gateway: Any, *, adjusted_ohlc_verified: bool):
        self.gateway = gateway
        self.adjusted_ohlc_verified = bool(adjusted_ohlc_verified)

    def get_daily_batch(self, symbol: str, *, start_date: str, end_date: str) -> ProviderBatch:
        rows = self.gateway.get_daily_candles(symbol, start_date=start_date, end_date=end_date)
        normalised = []
        for row in rows:
            close = row.get("close", row.get("adj_close"))
            normalised.append(
                {
                    "date": str(row["date"])[:10],
                    "ticker": str(row.get("ticker", symbol)).zfill(6),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(close),
                    "volume": float(row.get("volume", 0)),
                    "value_approx": float(row.get("value_approx", float(close) * float(row.get("volume", 0)))),
                }
            )
        return ProviderBatch(
            provider=self.provider_name,
            symbol=str(symbol).zfill(6),
            rows=tuple(normalised),
            adjusted_ohlc_verified=self.adjusted_ohlc_verified,
            source_tag="toss_openapi_1d_adjusted" if self.adjusted_ohlc_verified else "UNVERIFIED_PRICE_SCALE",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            raw_metadata={"gateway_health": self.gateway.health_check(), "row_count": len(normalised)},
        )


def _load_config(root: Path) -> dict[str, Any]:
    payload = yaml.safe_load((root / "config/v87_actual_data_ingestion.yaml").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IngestionError("V87 config must be a mapping")
    return payload


def _archive_batch(root: Path, cfg: dict[str, Any], run_id: str, batch: ProviderBatch) -> Path:
    directory = root / cfg["paths"]["raw_archive_dir"] / run_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{batch.symbol}.json"
    payload = {
        "provider": batch.provider,
        "symbol": batch.symbol,
        "adjusted_ohlc_verified": batch.adjusted_ohlc_verified,
        "source_tag": batch.source_tag,
        "retrieved_at": batch.retrieved_at,
        "raw_metadata": batch.raw_metadata,
        "rows": list(batch.rows),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=str), encoding="utf-8")
    return path


def _validate_batch(batch: ProviderBatch, cfg: dict[str, Any]) -> pd.DataFrame:
    contract = cfg["provider_contract"]
    quality = cfg["quality"]
    if contract["require_adjusted_ohlc_verified"] and not batch.adjusted_ohlc_verified:
        raise IngestionError(f"{batch.symbol}: adjusted OHLC is not verified")
    if batch.source_tag != contract["required_source_tag"]:
        raise IngestionError(f"{batch.symbol}: source tag mismatch {batch.source_tag!r}")
    frame = pd.DataFrame(batch.rows)
    required = {"date", "ticker", "open", "high", "low", "close", "volume", "value_approx"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise IngestionError(f"{batch.symbol}: missing columns {missing}")
    if frame.empty:
        raise IngestionError(f"{batch.symbol}: empty batch")
    frame["ticker"] = frame["ticker"].astype(str).str.zfill(6)
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.strftime("%Y-%m-%d")
    for col in ("open", "high", "low", "close", "volume", "value_approx"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    if frame[["open", "high", "low", "close"]].isna().any().any():
        raise IngestionError(f"{batch.symbol}: non-numeric price")
    if not quality["allow_nonpositive_prices"] and (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise IngestionError(f"{batch.symbol}: non-positive price")
    if not quality["allow_negative_volume"] and (frame["volume"] < 0).any():
        raise IngestionError(f"{batch.symbol}: negative volume")
    duplicates = int(frame.duplicated(["date", "ticker"]).sum())
    if duplicates and not quality["allow_duplicate_date_ticker"]:
        raise IngestionError(f"{batch.symbol}: duplicate date/ticker rows={duplicates}")
    geometry_bad = (
        (frame["high"] < frame[["open", "close", "low"]].max(axis=1) - 1e-9)
        | (frame["low"] > frame[["open", "close", "high"]].min(axis=1) + 1e-9)
    )
    if geometry_bad.any() and not quality["allow_ohlc_geometry_violation"]:
        sample = frame.loc[geometry_bad, ["date", "open", "high", "low", "close"]].head(3).to_dict("records")
        raise IngestionError(f"{batch.symbol}: OHLC geometry violation {sample}")
    if frame["ticker"].nunique() != 1 or frame["ticker"].iloc[0] != batch.symbol:
        raise IngestionError(f"{batch.symbol}: ticker identity mismatch")
    frame = frame.sort_values("date").reset_index(drop=True)
    if not frame["date"].is_monotonic_increasing:
        raise IngestionError(f"{batch.symbol}: dates are not monotonic")
    frame["source"] = batch.source_tag
    frame["price_scale"] = contract["canonical_price_scale"]
    frame["provider"] = batch.provider
    frame["retrieved_at"] = batch.retrieved_at
    return frame


def _revision_audit(new: pd.DataFrame, reference_path: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    gate = cfg["revision_gate"]
    if not reference_path.exists():
        return {"reference_available": False, "passed": True, "reason": "NO_REFERENCE"}
    reference = pd.read_csv(reference_path, dtype={"ticker": str})
    reference["ticker"] = reference["ticker"].astype(str).str.zfill(6)
    new = new.copy(); new["ticker"] = new["ticker"].astype(str).str.zfill(6)
    merged = reference[["date", "ticker", "close"]].merge(
        new[["date", "ticker", "close"]], on=["date", "ticker"], how="inner", suffixes=("_reference", "_new")
    )
    expected = len(reference[["date", "ticker"]].drop_duplicates())
    coverage = len(merged) / expected if expected else 0.0
    if merged.empty:
        return {"reference_available": True, "passed": False, "overlap_coverage": coverage, "reason": "NO_OVERLAP"}
    bps = (merged["close_new"] / merged["close_reference"] - 1.0).abs() * 10000.0
    median = float(bps.median())
    p99 = float(bps.quantile(0.99))
    changed_ratio = float((bps > float(gate["changed_row_threshold_bps"])).mean())
    checks = {
        "overlap_coverage": coverage >= float(gate["overlap_coverage_min"]),
        "median_abs_close_diff_bps": median <= float(gate["same_provider_median_abs_close_diff_bps_max"]),
        "p99_abs_close_diff_bps": p99 <= float(gate["same_provider_p99_abs_close_diff_bps_max"]),
        "changed_row_ratio": changed_ratio <= float(gate["changed_row_ratio_max"]),
    }
    return {
        "reference_available": True,
        "passed": all(checks.values()),
        "checks": checks,
        "overlap_rows": int(len(merged)),
        "reference_rows": int(expected),
        "overlap_coverage": coverage,
        "median_abs_close_diff_bps": median,
        "p99_abs_close_diff_bps": p99,
        "changed_row_ratio": changed_ratio,
    }


def ingest_market_data(
    root: Path | str,
    provider: CandleProvider,
    *,
    symbols: list[str],
    start_date: str,
    end_date: str,
    run_id: str | None = None,
    write_output: bool = True,
) -> dict[str, Any]:
    root = Path(root)
    cfg = _load_config(root)
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    frames: list[pd.DataFrame] = []
    archives: list[str] = []
    audits: list[dict[str, Any]] = []
    for symbol in sorted({str(x).zfill(6) for x in symbols}):
        batch = provider.get_daily_batch(symbol, start_date=start_date, end_date=end_date)
        archive = _archive_batch(root, cfg, run_id, batch)
        frame = _validate_batch(batch, cfg)
        frames.append(frame)
        archives.append(str(archive.relative_to(root)))
        audits.append(
            {
                "ticker": symbol,
                "rows": len(frame),
                "start": frame["date"].min(),
                "end": frame["date"].max(),
                "source": batch.source_tag,
                "adjusted_ohlc_verified": batch.adjusted_ohlc_verified,
                "raw_sha256": sha256(archive.read_bytes()).hexdigest(),
            }
        )
    canonical = pd.concat(frames, ignore_index=True).sort_values(["date", "ticker"]).reset_index(drop=True)
    duplicates = int(canonical.duplicated(["date", "ticker"]).sum())
    if duplicates:
        raise IngestionError(f"canonical duplicate date/ticker rows={duplicates}")
    reference_path = root / cfg["paths"]["reference_canonical"]
    revision = _revision_audit(canonical, reference_path, cfg)
    if not revision["passed"]:
        raise IngestionError(f"revision gate failed: {revision}")
    output = root / cfg["paths"]["output_canonical"]
    if write_output:
        output.parent.mkdir(parents=True, exist_ok=True)
        canonical.to_csv(output, index=False)
    fingerprint_columns = ["date", "ticker", "open", "high", "low", "close", "volume", "source", "price_scale"]
    fingerprint = sha256(canonical[fingerprint_columns].to_csv(index=False).encode()).hexdigest()
    report_dir = root / cfg["paths"]["report_dir"]
    report_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(audits).to_csv(report_dir / "source_audit.csv", index=False)
    result = {
        "status": "v87_actual_data_ingestion_passed",
        "run_id": run_id,
        "provider": provider.provider_name,
        "symbols": len(audits),
        "rows": len(canonical),
        "start": canonical["date"].min(),
        "end": canonical["date"].max(),
        "canonical_path": str(output.relative_to(root)),
        "canonical_sha256": fingerprint,
        "raw_archives": archives,
        "revision_audit": revision,
        "live_execution_allowed": False,
    }
    (report_dir / "ingestion_result.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    cfg = _load_config(root)
    universe = pd.read_csv(root / cfg["paths"]["universe"], dtype={"ticker": str})
    symbols = sorted(universe["ticker"].astype(str).str.zfill(6).unique())
    reference = pd.read_csv(root / cfg["paths"]["reference_canonical"], dtype={"ticker": str})
    result = ingest_market_data(
        root,
        CsvFixtureProvider(root / cfg["paths"]["fixture_dir"]),
        symbols=symbols,
        start_date=str(reference["date"].min()),
        end_date=str(reference["date"].max()),
        run_id="V87-FIXTURE-CONTRACT",
    )
    gates = {
        "raw_response_archived": len(result["raw_archives"]) == len(symbols),
        "adjusted_source_only": True,
        "revision_gate_passed": result["revision_audit"]["passed"],
        "canonical_written": (root / result["canonical_path"]).exists(),
        "live_blocked": not result["live_execution_allowed"],
    }
    report = root / "reports" / REPORT
    pd.DataFrame([{"gate": k, "passed": v} for k, v in gates.items()]).to_csv(report / "quality_gates.csv", index=False)
    summary = {"status": "v87_actual_data_contract_ready_live_blocked", "gates": gates, "ingestion": result}
    (report / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary

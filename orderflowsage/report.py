"""Report recomputation and aggregate-only presentation."""

from __future__ import annotations

from typing import Any

from .core import OrderFlowError, canonical_bytes, digest
from .engine import run_pipeline


def verify(config: Any, events: Any, report: Any) -> dict[str, Any]:
    if canonical_bytes(run_pipeline(config, events)) != canonical_bytes(report):
        raise OrderFlowError("report does not match deterministic recomputation")
    return report


def aggregate_facts(report: dict[str, Any]) -> dict[str, Any]:
    rows = report["features"]
    return {"events": len(rows), "windows": len(report["windows"]),
            "sequence": {"first": rows[0]["sequence"], "last": rows[-1]["sequence"]},
            "spread_bps": {"minimum": min(row["spread_bps"] for row in rows),
                           "maximum": max(row["spread_bps"] for row in rows),
                           "mean": sum(row["spread_bps"] for row in rows) / len(rows)},
            "mean_top_imbalance": sum(row["top_imbalance"] for row in rows) / len(rows),
            "mean_depth_imbalance": sum(row["depth_imbalance"] for row in rows) / len(rows),
            "total_order_flow_imbalance": sum(row["order_flow_imbalance"] or 0.0 for row in rows),
            "total_signed_trade_flow": sum(row["signed_trade_flow"] for row in rows),
            "integrity": report["integrity"], "claims": report["claims"]}


def summary(report: Any) -> str:
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise OrderFlowError("report schema_version must be 1")
    facts = aggregate_facts(report)
    return ("OrderFlowSage deterministic replay report\n"
            f"events={facts['events']} sequence={facts['sequence']['first']}..{facts['sequence']['last']} windows={facts['windows']}\n"
            f"spread_bps min={facts['spread_bps']['minimum']:.6f} mean={facts['spread_bps']['mean']:.6f} max={facts['spread_bps']['maximum']:.6f}\n"
            f"imbalance top_mean={facts['mean_top_imbalance']:.6f} depth_mean={facts['mean_depth_imbalance']:.6f}\n"
            f"flow ofi={facts['total_order_flow_imbalance']:.6f} trades={facts['total_signed_trade_flow']:.6f}\n"
            "integrity=complete_sequence,increasing_time,uncrossed_books\n"
            "mode=offline_replay_only not_a_prediction_or_signal\n")


def prompt(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise OrderFlowError("report schema_version must be 1")
    facts = aggregate_facts(report)
    return {"facts_sha256": digest(facts), "messages": [
        {"role": "system", "content": "Explain only these replay diagnostics. Do not predict price direction, recommend or rank trades, infer manipulation, or label a participant. OFI and imbalance are measurements, not signals."},
        {"role": "user", "content": canonical_bytes(facts).decode().rstrip("\n")}]}

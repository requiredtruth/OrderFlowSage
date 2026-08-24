"""Snapshot validation and transparent microstructure features."""

from __future__ import annotations

from typing import Any, Sequence

from . import __version__
from .core import OrderFlowError, digest, finite, utc


def validate_config(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "depth_levels", "window_events", "expected_start_sequence"} or raw.get("schema_version") != 1:
        raise OrderFlowError("config fields do not match schema version 1")
    for field, minimum, maximum in (("depth_levels", 1, 50), ("window_events", 2, 100_000),
                                    ("expected_start_sequence", 0, 2**63 - 1)):
        value = raw[field]
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise OrderFlowError(f"{field} must be an integer in {minimum}..{maximum}")
    return dict(raw)


def _levels(raw: Any, field: str, descending: bool, required: int) -> list[list[float]]:
    if not isinstance(raw, list) or len(raw) < required or len(raw) > 1000:
        raise OrderFlowError(f"{field} must contain {required}..1000 levels")
    result = []
    for index, level in enumerate(raw):
        if not isinstance(level, list) or len(level) != 2:
            raise OrderFlowError(f"{field}[{index}] must be [price,size]")
        result.append([finite(level[0], f"{field}[{index}].price", True),
                       finite(level[1], f"{field}[{index}].size", True)])
    prices = [level[0] for level in result]
    expected = sorted(prices, reverse=descending)
    if prices != expected or len(set(prices)) != len(prices):
        order = "descending" if descending else "ascending"
        raise OrderFlowError(f"{field} prices must be unique and strictly {order}")
    return result


def validate_events(raw_events: Any, config: dict[str, int]) -> list[dict[str, Any]]:
    if not isinstance(raw_events, list) or len(raw_events) < 2:
        raise OrderFlowError("dataset must contain at least two snapshots")
    events, previous_time = [], None
    expected = config["expected_start_sequence"]
    for index, raw in enumerate(raw_events):
        if not isinstance(raw, dict) or set(raw) != {"sequence", "timestamp", "bids", "asks", "trades"}:
            raise OrderFlowError(f"event {index} fields do not match schema")
        if raw["sequence"] != expected + index:
            raise OrderFlowError(f"sequence gap at event {index}: expected {expected + index}")
        current = utc(raw["timestamp"], f"event {index}.timestamp")
        if previous_time is not None and current <= previous_time:
            raise OrderFlowError("timestamps must be strictly increasing")
        previous_time = current
        bids = _levels(raw["bids"], f"event {index}.bids", True, config["depth_levels"])
        asks = _levels(raw["asks"], f"event {index}.asks", False, config["depth_levels"])
        if bids[0][0] >= asks[0][0]:
            raise OrderFlowError(f"event {index} has a locked or crossed book")
        trades = raw["trades"]
        if not isinstance(trades, list) or len(trades) > 100_000:
            raise OrderFlowError(f"event {index}.trades must be a bounded list")
        normalized_trades = []
        for trade_index, trade in enumerate(trades):
            if not isinstance(trade, dict) or set(trade) != {"side", "size"} or trade["side"] not in {"buy", "sell"}:
                raise OrderFlowError(f"event {index}.trades[{trade_index}] is invalid")
            normalized_trades.append({"side": trade["side"],
                                      "size": finite(trade["size"], f"trade {trade_index}.size", True)})
        events.append({"sequence": raw["sequence"], "timestamp": raw["timestamp"],
                       "bids": bids, "asks": asks, "trades": normalized_trades})
    return events


def order_flow_imbalance(previous: dict[str, Any], current: dict[str, Any]) -> float:
    """Top-of-book OFI using price/queue changes on both sides."""
    previous_bid, previous_ask = previous["bids"][0], previous["asks"][0]
    bid, ask = current["bids"][0], current["asks"][0]
    return (int(bid[0] >= previous_bid[0]) * bid[1] - int(bid[0] <= previous_bid[0]) * previous_bid[1]
            - int(ask[0] <= previous_ask[0]) * ask[1] + int(ask[0] >= previous_ask[0]) * previous_ask[1])


def feature_row(event: dict[str, Any], depth: int, previous: dict[str, Any] | None) -> dict[str, Any]:
    bid, ask = event["bids"][0], event["asks"][0]
    mid = (bid[0] + ask[0]) / 2.0
    top_total = bid[1] + ask[1]
    bid_depth = sum(level[1] for level in event["bids"][:depth])
    ask_depth = sum(level[1] for level in event["asks"][:depth])
    depth_total = bid_depth + ask_depth
    signed_flow = sum(trade["size"] * (1.0 if trade["side"] == "buy" else -1.0)
                      for trade in event["trades"])
    return {"sequence": event["sequence"], "timestamp": event["timestamp"],
            "best_bid": bid[0], "best_ask": ask[0], "mid": mid,
            "spread": ask[0] - bid[0], "spread_bps": (ask[0] - bid[0]) / mid * 10_000.0,
            "microprice": (ask[0] * bid[1] + bid[0] * ask[1]) / top_total,
            "top_imbalance": (bid[1] - ask[1]) / top_total,
            "depth_imbalance": (bid_depth - ask_depth) / depth_total,
            "order_flow_imbalance": None if previous is None else order_flow_imbalance(previous, event),
            "signed_trade_flow": signed_flow, "trade_count": len(event["trades"]),
            "book_sha256": digest({"bids": event["bids"], "asks": event["asks"]})}


def _aggregate(rows: Sequence[dict[str, Any]], window: int) -> list[dict[str, Any]]:
    result = []
    for start in range(0, len(rows), window):
        group = rows[start:start + window]
        if len(group) != window:
            break
        result.append({"first_sequence": group[0]["sequence"], "last_sequence": group[-1]["sequence"],
                       "events": len(group),
                       "mean_spread_bps": sum(row["spread_bps"] for row in group) / len(group),
                       "mean_top_imbalance": sum(row["top_imbalance"] for row in group) / len(group),
                       "mean_depth_imbalance": sum(row["depth_imbalance"] for row in group) / len(group),
                       "order_flow_imbalance": sum(row["order_flow_imbalance"] or 0.0 for row in group),
                       "signed_trade_flow": sum(row["signed_trade_flow"] for row in group),
                       "trades": sum(row["trade_count"] for row in group)})
    return result


def run_pipeline(raw_config: Any, raw_events: Any) -> dict[str, Any]:
    config = validate_config(raw_config)
    events = validate_events(raw_events, config)
    rows = [feature_row(event, config["depth_levels"], events[index - 1] if index else None)
            for index, event in enumerate(events)]
    return {"schema_version": 1, "tool_version": __version__, "config": config,
            "evidence": {"events_sha256": digest(events)}, "features": rows,
            "windows": _aggregate(rows, config["window_events"]),
            "integrity": {"sequence_complete": True, "timestamps_increasing": True,
                          "books_uncrossed": True},
            "claims": {"mode": "offline_replay_only", "prediction": False,
                       "trade_signal": False, "order_submission": False}}

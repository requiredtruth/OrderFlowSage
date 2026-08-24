"""Bounded JSONL input and canonical output."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


class OrderFlowError(ValueError):
    """A deterministic schema or replay-integrity failure."""


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + "\n").encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def atomic_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def load_json(path: str | Path, max_bytes: int = 1_000_000) -> Any:
    source = Path(path)
    try:
        if source.stat().st_size > max_bytes:
            raise OrderFlowError(f"{source} exceeds the size limit")
        return json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OrderFlowError(f"cannot read JSON from {source}: {exc}") from exc


def load_jsonl(path: str | Path, max_bytes: int = 50_000_000,
               max_rows: int = 1_000_000) -> list[Any]:
    source = Path(path)
    try:
        if source.stat().st_size > max_bytes:
            raise OrderFlowError(f"{source} exceeds the size limit")
        rows = []
        for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                raise OrderFlowError(f"blank JSONL line {number}")
            if len(rows) >= max_rows:
                raise OrderFlowError(f"dataset exceeds {max_rows} rows")
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise OrderFlowError(f"invalid JSON on line {number}: {exc.msg}") from exc
        return rows
    except (OSError, UnicodeError) as exc:
        raise OrderFlowError(f"cannot read JSONL from {source}: {exc}") from exc


def finite(value: Any, field: str, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise OrderFlowError(f"{field} must be a finite number")
    result = float(value)
    if positive and result <= 0:
        raise OrderFlowError(f"{field} must be positive")
    return result


def utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise OrderFlowError(f"{field} must be canonical ISO-8601 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise OrderFlowError(f"{field} is invalid") from exc
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise OrderFlowError(f"{field} must use canonical seconds")
    return parsed

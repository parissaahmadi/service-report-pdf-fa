"""Deterministic fingerprint of the input data (shown in the footer and PDF metadata)."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal


class DataError(ValueError):
    """The input JSON is missing a field or has an invalid value."""


def load_json(text: str):
    """Parse JSON keeping decimals exact (``0.10`` stays ``Decimal('0.10')``)."""
    return json.loads(text, parse_float=Decimal)


def canonical_json(data) -> str:
    """Key-order and whitespace independent text form of ``data``."""

    def default(o):
        if isinstance(o, Decimal):
            return format(o, "f")
        raise TypeError(f"not serialisable: {type(o).__name__}")

    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=default)


def sha256_hex(data) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def short(hex_digest: str, n: int = 16) -> str:
    """``abcd 1234 ef56 7890`` -- the first ``n`` hex characters in groups of four."""
    head = hex_digest[:n]
    return " ".join(head[i : i + 4] for i in range(0, len(head), 4))

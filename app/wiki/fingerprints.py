"""Deterministic fingerprints for primitive wiki state."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Return a stable JSON representation for primitive state."""

    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def stable_digest(value: Any) -> str:
    """Hash primitive state after canonical JSON encoding."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

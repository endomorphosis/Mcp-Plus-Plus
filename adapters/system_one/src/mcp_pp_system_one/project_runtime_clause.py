"""Project an accelerate-shaped clause. Unknown keys and ISO timestamps return None."""

import math
from datetime import datetime, timezone
from typing import Any

from mcp_pp_system_one.exact_policy import RESIDUAL_KEYS, STRUCTURAL_KEYS, Policy, Temporal

_METADATA = STRUCTURAL_KEYS | RESIDUAL_KEYS


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _iso(value: Any) -> str | None:
    if not _number(value) or not math.isfinite(float(value)):
        return None
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def project_runtime_clause(raw: dict[str, Any]) -> Policy | None:
    metadata = raw.get("metadata") or {}
    if not isinstance(metadata, dict):
        return None
    if any(key not in _METADATA for key in metadata):
        return None
    temporal_bits = {}
    for source, dest in (("valid_from", "not_before"), ("valid_until", "not_after")):
        if source not in raw:
            continue
        stamped = _iso(raw[source])
        if stamped is None:
            return None
        temporal_bits[dest] = stamped
    if raw.get("clause_type") == "obligation" and "obligation_deadline" in raw:
        stamped = _iso(raw["obligation_deadline"])
        if stamped is None:
            return None
        temporal_bits["not_after"] = stamped
    action = raw.get("action")
    if not isinstance(action, str) or not action:
        return None
    temporal = Temporal(**temporal_bits) if temporal_bits else None
    return Policy(
        policy_type=str(raw.get("clause_type") or ""),
        action=action,
        subject=raw.get("actor"),
        resource=raw.get("resource"),
        temporal=temporal,
        conditions=dict(metadata) or None,
    )

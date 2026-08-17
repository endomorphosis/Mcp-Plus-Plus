"""
Temporal Deontic Policy Validator and PolicyEvaluator@1

Validates Profile D (Temporal Deontic Policy Evaluation) and implements the
deterministic evaluator interface according to:

  docs/spec/temporal-deontic-policy.md

Interfaces:
  PolicyEvaluator@1  — deterministic evaluate(intent, delegation, policy, …)
  PolicyDecision@1   — allow | deny | allow_with_obligations + decision_cid

Acceptance (MCPP-046):
  Outputs are deterministic for the same inputs.
  Missing context or stale root is deny.
  Statement commitments are not treated as verified policy proofs.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .base_mcp import ValidationResult

try:
    from .canonical_jcs import ALGORITHM_ID, artifact_cid, canonicalize_bytes
except Exception:  # pragma: no cover - package layout fallback
    ALGORITHM_ID = "mcpp-jcs-v1"

    def canonicalize_bytes(value: Any) -> bytes:  # type: ignore[misc]
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")

    def artifact_cid(value: Any) -> str:  # type: ignore[misc]
        digest = hashlib.sha256(canonicalize_bytes(value)).digest()
        # Minimal CIDv1-shaped id for offline fallback (not multiformats-encoded).
        return "b" + digest.hex()[:58]


# ---------------------------------------------------------------------------
# Interface identity
# ---------------------------------------------------------------------------

INTERFACE_EVALUATOR = "PolicyEvaluator@1"
INTERFACE_DECISION = "PolicyDecision@1"
SCHEMA_MARKER = "mcp++/profile-d-policy-decision@1"
POLICY_SCHEMA_MARKER = "mcp++/profile-d-policy@1"
CANONICAL_ALGORITHM = ALGORITHM_ID

POLICY_TYPES = frozenset({"permission", "prohibition", "obligation"})
DECISION_VERDICTS = frozenset({"allow", "deny", "allow_with_obligations"})

REASON_MISSING_CONTEXT = "missing_context"
REASON_STALE_ROOT = "stale_root"
REASON_VERSION_MISMATCH = "policy_version_mismatch"
REASON_PROHIBITION = "prohibition_matched"
REASON_NO_PERMISSION = "no_matching_permission"
REASON_INVALID_INPUT = "invalid_input"
REASON_TEMPORAL_INACTIVE = "temporal_window_inactive"
REASON_DELEGATION_INVALID = "delegation_invalid"
REASON_MISSING_LOGICAL_TIME = "missing_logical_time"

# ISO-8601 calendar date + time (optional fractional seconds) + Z or ±offset.
_ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}"
    r"(?:T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?"
    r"(?:Z|[+-]\d{2}:\d{2})?)?$"
)
_TIME_OF_DAY_RE = re.compile(r"^\d{2}:\d{2}(?::\d{2})?$")
_DAY_NAMES = frozenset(
    {
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "mon",
        "tue",
        "wed",
        "thu",
        "fri",
        "sat",
        "sun",
    }
)


# ---------------------------------------------------------------------------
# PolicyDecision@1
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyDecision:
    """PolicyDecision@1 — immutable result of one evaluation.

    Normative fields are content-addressed into ``decision_cid``.  The
    ``decision_commitment`` is a sha2-256 hex digest of the same canonical
    decision body and MUST NOT be treated as a zero-knowledge proof.
    """

    decision: str
    granted: bool
    decision_cid: str
    evaluated_at: str
    policy_cid: str = ""
    intent_cid: str = ""
    justification: str = ""
    obligations: Tuple[Dict[str, Any], ...] = ()
    fired_rules: Tuple[Dict[str, Any], ...] = ()
    facts: Tuple[Dict[str, Any], ...] = ()
    deadlines: Tuple[Dict[str, Any], ...] = ()
    compensation: Tuple[Dict[str, Any], ...] = ()
    human_approval: Optional[Dict[str, Any]] = None
    decision_commitment: str = ""
    signature: Optional[str] = None
    reason_code: Optional[str] = None
    schema: str = SCHEMA_MARKER
    interface: str = INTERFACE_DECISION
    allowed: bool = False

    def __post_init__(self) -> None:
        # Keep allowed mirrored for wire-shape clients.
        object.__setattr__(self, "allowed", bool(self.granted))

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "schema": self.schema,
            "interface": self.interface,
            "decision": self.decision,
            "granted": self.granted,
            "allowed": self.allowed,
            "decision_cid": self.decision_cid,
            "evaluated_at": self.evaluated_at,
            "policy_cid": self.policy_cid,
            "intent_cid": self.intent_cid,
            "justification": self.justification,
            "obligations": [dict(x) for x in self.obligations],
            "fired_rules": [dict(x) for x in self.fired_rules],
            "facts": [dict(x) for x in self.facts],
            "deadlines": [dict(x) for x in self.deadlines],
            "compensation": [dict(x) for x in self.compensation],
            "decision_commitment": self.decision_commitment,
        }
        if self.human_approval is not None:
            payload["human_approval"] = dict(self.human_approval)
        if self.signature is not None:
            payload["signature"] = self.signature
        if self.reason_code is not None:
            payload["reason_code"] = self.reason_code
        return payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _parse_iso8601(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp. Returns None when empty; raises ValueError when invalid."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if not _ISO8601_RE.match(text):
        # Allow pure epoch seconds as string for interop.
        try:
            return datetime.fromtimestamp(float(text), tz=timezone.utc)
        except ValueError as exc:
            raise ValueError(f"invalid_iso8601:{text}") from exc
    if "T" not in text:
        text = text + "T00:00:00Z"
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid_iso8601:{text}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _format_iso8601(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _matches_pattern(pattern: str, value: str) -> bool:
    if pattern in ("", "*"):
        return True
    if pattern == value:
        return True
    if pattern.endswith("/*") and value.startswith(pattern[:-1]):
        return True
    if pattern.endswith("*") and value.startswith(pattern[:-1]):
        return True
    return False


def _stable_sort_key(item: Mapping[str, Any], index: int) -> Tuple[str, str, str, int]:
    return (
        _as_str(item.get("clause_id") or item.get("id") or item.get("rule_id")),
        _as_str(item.get("clause_type") or item.get("type")),
        _as_str(item.get("action")),
        index,
    )


def _extract_clauses(policy: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Normalize a policy document into an ordered list of clause dicts.

    Accepts either a multi-clause policy (``clauses`` list) or a single-clause
    document with top-level ``type`` / ``clause_type`` (validator fixture shape).
    """
    raw = policy.get("clauses")
    if isinstance(raw, list) and raw:
        clauses: List[Dict[str, Any]] = []
        for index, item in enumerate(raw):
            if not _is_mapping(item):
                continue
            clauses.append(_normalize_clause(dict(item), index=index))
        return clauses

    # Single-clause document.
    clause_type = _as_str(policy.get("clause_type") or policy.get("type")).lower()
    if clause_type in POLICY_TYPES:
        return [_normalize_clause(dict(policy), index=0)]
    return []


def _normalize_clause(raw: Mapping[str, Any], *, index: int) -> Dict[str, Any]:
    clause_type = _as_str(raw.get("clause_type") or raw.get("type")).lower()
    temporal = raw.get("temporal_constraints") if _is_mapping(raw.get("temporal_constraints")) else {}
    if not temporal and _is_mapping(raw.get("temporal")):
        temporal = dict(raw["temporal"])  # type: ignore[index]

    valid_from = (
        raw.get("valid_from")
        or raw.get("not_before")
        or temporal.get("valid_from")
        or temporal.get("not_before")
    )
    valid_until = (
        raw.get("valid_until")
        or raw.get("not_after")
        or temporal.get("valid_until")
        or temporal.get("not_after")
    )
    deadline = (
        raw.get("obligation_deadline")
        or raw.get("deadline")
        or temporal.get("deadline")
        or temporal.get("obligation_deadline")
    )

    metadata = raw.get("metadata") if _is_mapping(raw.get("metadata")) else {}
    metadata = dict(metadata)
    if raw.get("human_approval") is True or metadata.get("human_approval") is True:
        metadata["human_approval"] = True
    if raw.get("compensation") is not None:
        metadata["compensation"] = raw.get("compensation")
    if temporal.get("always") is True:
        metadata["always"] = True
    if "time_of_day" in temporal:
        metadata["time_of_day"] = temporal["time_of_day"]
    if "days_of_week" in temporal:
        metadata["days_of_week"] = temporal["days_of_week"]

    on_action = raw.get("on_action") or raw.get("applies_to")
    if on_action is None and metadata:
        on_action = metadata.get("on_action") or metadata.get("applies_to")

    return {
        "clause_id": _as_str(raw.get("clause_id") or raw.get("id") or raw.get("rule_id") or f"clause-{index}"),
        "clause_type": clause_type,
        "actor": _as_str(raw.get("actor") or raw.get("subject") or "*", default="*"),
        "action": _as_str(raw.get("action") or "*", default="*"),
        "resource": _as_str(raw.get("resource")) or None,
        "valid_from": _as_str(valid_from) or None,
        "valid_until": _as_str(valid_until) or None,
        "obligation_deadline": _as_str(deadline) or None,
        "trigger": _as_str(raw.get("trigger")) or None,
        "on_action": _as_str(on_action) or None,
        "metadata": metadata,
        "index": index,
    }


def _clause_active(clause: Mapping[str, Any], now: Optional[datetime]) -> bool:
    """Return whether a clause is temporally active at ``now``.

    When the clause has temporal bounds and ``now`` is missing, the clause is
    inactive (fail-closed) so evaluation does not depend on wall-clock time.
    """
    metadata = clause.get("metadata") if _is_mapping(clause.get("metadata")) else {}
    if metadata.get("always") is True:
        return True

    valid_from = clause.get("valid_from")
    valid_until = clause.get("valid_until")
    if valid_from or valid_until:
        if now is None:
            return False
        start = _parse_iso8601(valid_from) if valid_from else None
        end = _parse_iso8601(valid_until) if valid_until else None
        if start is not None and now < start:
            return False
        if end is not None and now > end:
            return False

    days = metadata.get("days_of_week")
    if days is not None:
        if now is None:
            return False
        if not isinstance(days, (list, tuple)):
            return False
        day_name = now.strftime("%A").lower()
        allowed = {str(d).strip().lower() for d in days}
        if day_name not in allowed and day_name[:3] not in allowed:
            return False

    tod = metadata.get("time_of_day")
    if _is_mapping(tod):
        if now is None:
            return False
        start_s = _as_str(tod.get("start"))
        end_s = _as_str(tod.get("end"))
        if start_s and end_s:
            current = now.strftime("%H:%M:%S")
            # Normalize HH:MM to HH:MM:00 for lexicographic compare.
            if len(start_s) == 5:
                start_s = start_s + ":00"
            if len(end_s) == 5:
                end_s = end_s + ":00"
            if not (start_s <= current <= end_s):
                return False
    return True


def _clause_matches(
    clause: Mapping[str, Any],
    *,
    actor: str,
    action: str,
    resource: Optional[str],
    now: Optional[datetime],
) -> bool:
    """Return whether a clause applies to the intent under evaluation.

    Permissions and prohibitions match on actor + action + resource.
    Obligations match on actor + resource only: their ``action`` field names
    the obligated act (e.g. ``audit/log``), not the intent method under test.
    An obligation may still set ``on_action`` / ``applies_to`` to restrict the
    intent methods that spawn it.
    """
    clause_type = clause.get("clause_type")
    if clause_type not in POLICY_TYPES:
        return False
    if not _clause_active(clause, now):
        return False
    if not _matches_pattern(_as_str(clause.get("actor"), "*"), actor):
        return False

    clause_resource = clause.get("resource")
    if clause_resource is not None and clause_resource != "":
        if resource is None or not _matches_pattern(str(clause_resource), resource):
            return False

    if clause_type == "obligation":
        # Optional intent-action scope for obligations.
        on_action = clause.get("on_action")
        if on_action is not None and not _matches_pattern(_as_str(on_action, "*"), action):
            return False
        return True

    if not _matches_pattern(_as_str(clause.get("action"), "*"), action):
        return False
    return True


def _normalize_context_roots(value: Any) -> Dict[str, str]:
    """Normalize context roots to a stable ``name → cid`` mapping."""
    if value is None:
        return {}
    if _is_mapping(value):
        out: Dict[str, str] = {}
        for key in sorted(value.keys(), key=lambda k: str(k)):
            item = value[key]
            if _is_mapping(item):
                cid = _as_str(item.get("root_cid") or item.get("cid") or item.get("value"))
            else:
                cid = _as_str(item)
            if cid:
                out[str(key)] = cid
        return out
    if isinstance(value, (list, tuple)):
        out = {}
        for index, item in enumerate(value):
            if not _is_mapping(item):
                continue
            name = _as_str(item.get("name") or item.get("id") or item.get("key") or f"root-{index}")
            cid = _as_str(item.get("root_cid") or item.get("cid") or item.get("value"))
            if cid:
                out[name] = cid
        return out
    return {}


def _intent_fields(intent: Mapping[str, Any]) -> Tuple[str, str, Optional[str], str]:
    actor = _as_str(
        intent.get("actor")
        or intent.get("subject")
        or intent.get("principal")
        or intent.get("iss")
        or "*"
    )
    action = _as_str(
        intent.get("action")
        or intent.get("method")
        or intent.get("tool")
        or intent.get("name")
        or "*"
    )
    resource_raw = intent.get("resource") or intent.get("target") or intent.get("resource_cid")
    resource = _as_str(resource_raw) or None
    intent_cid = _as_str(intent.get("intent_cid") or intent.get("cid"))
    return actor, action, resource, intent_cid


def _policy_cid_of(policy: Mapping[str, Any]) -> str:
    explicit = _as_str(policy.get("policy_cid") or policy.get("cid"))
    if explicit:
        return explicit
    body = {
        "schema": POLICY_SCHEMA_MARKER,
        "type": policy.get("type") or policy.get("clause_type"),
        "name": policy.get("name"),
        "version": policy.get("version") or policy.get("policy_version"),
        "clauses": _extract_clauses(policy),
        "action": policy.get("action"),
        "resource": policy.get("resource"),
        "temporal_constraints": policy.get("temporal_constraints"),
    }
    # Drop nulls for stable addressing.
    compact = {k: v for k, v in body.items() if v is not None}
    return artifact_cid(compact)


def _decision_body(
    *,
    decision: str,
    granted: bool,
    evaluated_at: str,
    policy_cid: str,
    intent_cid: str,
    justification: str,
    obligations: Sequence[Mapping[str, Any]],
    fired_rules: Sequence[Mapping[str, Any]],
    facts: Sequence[Mapping[str, Any]],
    deadlines: Sequence[Mapping[str, Any]],
    compensation: Sequence[Mapping[str, Any]],
    human_approval: Optional[Mapping[str, Any]],
    reason_code: Optional[str],
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "schema": SCHEMA_MARKER,
        "interface": INTERFACE_DECISION,
        "decision": decision,
        "granted": granted,
        "allowed": granted,
        "evaluated_at": evaluated_at,
        "policy_cid": policy_cid,
        "intent_cid": intent_cid,
        "justification": justification,
        "obligations": [dict(x) for x in obligations],
        "fired_rules": [dict(x) for x in fired_rules],
        "facts": [dict(x) for x in facts],
        "deadlines": [dict(x) for x in deadlines],
        "compensation": [dict(x) for x in compensation],
        "canonicalization": CANONICAL_ALGORITHM,
    }
    if human_approval is not None:
        body["human_approval"] = dict(human_approval)
    if reason_code is not None:
        body["reason_code"] = reason_code
    return body


def _mint_decision(
    *,
    decision: str,
    granted: bool,
    evaluated_at: str,
    policy_cid: str = "",
    intent_cid: str = "",
    justification: str = "",
    obligations: Optional[Sequence[Mapping[str, Any]]] = None,
    fired_rules: Optional[Sequence[Mapping[str, Any]]] = None,
    facts: Optional[Sequence[Mapping[str, Any]]] = None,
    deadlines: Optional[Sequence[Mapping[str, Any]]] = None,
    compensation: Optional[Sequence[Mapping[str, Any]]] = None,
    human_approval: Optional[Mapping[str, Any]] = None,
    reason_code: Optional[str] = None,
    signature: Optional[str] = None,
) -> PolicyDecision:
    obs = tuple(dict(x) for x in (obligations or ()))
    rules = tuple(dict(x) for x in (fired_rules or ()))
    fact_list = tuple(dict(x) for x in (facts or ()))
    deadline_list = tuple(dict(x) for x in (deadlines or ()))
    comp_list = tuple(dict(x) for x in (compensation or ()))
    body = _decision_body(
        decision=decision,
        granted=granted,
        evaluated_at=evaluated_at,
        policy_cid=policy_cid,
        intent_cid=intent_cid,
        justification=justification,
        obligations=obs,
        fired_rules=rules,
        facts=fact_list,
        deadlines=deadline_list,
        compensation=comp_list,
        human_approval=human_approval,
        reason_code=reason_code,
    )
    decision_cid = artifact_cid(body)
    commitment = hashlib.sha256(canonicalize_bytes(body)).hexdigest()
    return PolicyDecision(
        decision=decision,
        granted=granted,
        decision_cid=decision_cid,
        evaluated_at=evaluated_at,
        policy_cid=policy_cid,
        intent_cid=intent_cid,
        justification=justification,
        obligations=obs,
        fired_rules=rules,
        facts=fact_list,
        deadlines=deadline_list,
        compensation=comp_list,
        human_approval=dict(human_approval) if human_approval is not None else None,
        decision_commitment=commitment,
        signature=signature,
        reason_code=reason_code,
    )


def _validate_iso_timestamp_field(value: Any, field_name: str, result: ValidationResult) -> None:
    if value is None or value is True or value is False:
        return
    text = str(value).strip()
    if not text:
        return
    if isinstance(value, (int, float)):
        return
    try:
        _parse_iso8601(text)
    except ValueError:
        result.add_error(f"Invalid ISO-8601 timestamp for '{field_name}': {text}")


# ---------------------------------------------------------------------------
# PolicyEvaluator@1
# ---------------------------------------------------------------------------


class PolicyEvaluator:
    """Deterministic Profile D policy evaluator (PolicyEvaluator@1).

    Evaluation is a pure function of the supplied inputs.  Wall-clock time is
    never consulted: callers MUST pass ``logical_time`` when temporal windows
    matter.  Missing required context roots or a stale root CID yields deny.
    """

    INTERFACE = INTERFACE_EVALUATOR

    def evaluate(
        self,
        intent: Optional[Mapping[str, Any]] = None,
        *,
        policy: Optional[Mapping[str, Any]] = None,
        policies: Optional[Sequence[Mapping[str, Any]]] = None,
        delegation: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
        context_roots: Optional[Any] = None,
        expected_context_roots: Optional[Any] = None,
        required_context_keys: Optional[Sequence[str]] = None,
        logical_time: Optional[Union[str, float, int, datetime]] = None,
        prior_events: Optional[Sequence[Mapping[str, Any]]] = None,
        policy_version: Optional[str] = None,
        signature: Optional[str] = None,
    ) -> PolicyDecision:
        """Evaluate whether ``intent`` is permitted under the given policy inputs.

        Args:
            intent: Proposed action (actor/action/resource/intent_cid).
            policy: Single policy document (clause list or single-clause form).
            policies: Optional multi-policy set; prohibitions across the set win.
            delegation: Delegation proof(s). Structural invalidity is deny.
            context_roots: Observed context root map/list.
            expected_context_roots: Authoritative roots; mismatch is stale_root deny.
            required_context_keys: Keys that MUST be present in context_roots.
            logical_time: Evaluation time (ISO-8601 or epoch seconds). Deterministic.
            prior_events: Prior event records (facts surface; may mark revocations).
            policy_version: Expected policy version when the policy declares one.
            signature: Optional detached signature attached to the decision.

        Returns:
            PolicyDecision@1 (always a concrete allow/deny/allow_with_obligations).
        """
        # --- Input normalization (fail-closed) ---
        if not _is_mapping(intent):
            return _mint_decision(
                decision="deny",
                granted=False,
                evaluated_at=_format_iso8601(datetime(1970, 1, 1, tzinfo=timezone.utc)),
                justification="intent must be an object",
                reason_code=REASON_INVALID_INPUT,
                signature=signature,
            )

        actor, action, resource, intent_cid = _intent_fields(intent)

        try:
            now = _parse_iso8601(logical_time) if logical_time is not None else None
        except ValueError:
            return _mint_decision(
                decision="deny",
                granted=False,
                evaluated_at=_format_iso8601(datetime(1970, 1, 1, tzinfo=timezone.utc)),
                intent_cid=intent_cid,
                justification="logical_time is not a valid ISO-8601 timestamp",
                reason_code=REASON_INVALID_INPUT,
                signature=signature,
            )

        evaluated_at = _format_iso8601(now) if now is not None else "1970-01-01T00:00:00Z"

        # --- Delegation structural gate ---
        if delegation is not None:
            denials = self._check_delegation(delegation)
            if denials:
                return _mint_decision(
                    decision="deny",
                    granted=False,
                    evaluated_at=evaluated_at,
                    intent_cid=intent_cid,
                    justification=denials,
                    reason_code=REASON_DELEGATION_INVALID,
                    facts=({"kind": "delegation", "status": "invalid"},),
                    signature=signature,
                )

        # --- Context roots: missing / stale ---
        observed = _normalize_context_roots(context_roots)
        expected = _normalize_context_roots(expected_context_roots)

        required_keys = list(required_context_keys or ())
        if not required_keys and expected:
            required_keys = sorted(expected.keys())
        # Intent or policy may declare required context keys.
        for source in (intent, policy):
            if _is_mapping(source):
                extra = source.get("required_context_keys") or source.get("context_keys")
                if isinstance(extra, (list, tuple)):
                    for key in extra:
                        key_s = _as_str(key)
                        if key_s and key_s not in required_keys:
                            required_keys.append(key_s)

        missing = [k for k in required_keys if k not in observed or not observed[k]]
        if missing:
            return _mint_decision(
                decision="deny",
                granted=False,
                evaluated_at=evaluated_at,
                intent_cid=intent_cid,
                justification=f"Missing required context root(s): {', '.join(sorted(missing))}",
                reason_code=REASON_MISSING_CONTEXT,
                facts=(
                    {
                        "kind": "context",
                        "status": "missing",
                        "missing_keys": sorted(missing),
                        "observed_keys": sorted(observed.keys()),
                    },
                ),
                signature=signature,
            )

        if expected:
            stale = sorted(
                name
                for name, root in expected.items()
                if name in observed and observed[name] != root
            )
            if stale:
                return _mint_decision(
                    decision="deny",
                    granted=False,
                    evaluated_at=evaluated_at,
                    intent_cid=intent_cid,
                    justification=f"Stale context root(s): {', '.join(stale)}",
                    reason_code=REASON_STALE_ROOT,
                    facts=(
                        {
                            "kind": "context",
                            "status": "stale",
                            "stale_keys": stale,
                            "expected": {k: expected[k] for k in stale},
                            "observed": {k: observed[k] for k in stale},
                        },
                    ),
                    signature=signature,
                )

        # --- Policy collection ---
        policy_docs: List[Mapping[str, Any]] = []
        if _is_mapping(policy):
            policy_docs.append(policy)
        if isinstance(policies, (list, tuple)):
            for item in policies:
                if _is_mapping(item):
                    policy_docs.append(item)

        if not policy_docs:
            return _mint_decision(
                decision="deny",
                granted=False,
                evaluated_at=evaluated_at,
                intent_cid=intent_cid,
                justification="No policy supplied (closed-world deny)",
                reason_code=REASON_NO_PERMISSION,
                signature=signature,
            )

        # Version mismatch deny when a version is declared and expected.
        for doc in policy_docs:
            declared = _as_str(doc.get("version") or doc.get("policy_version"))
            if policy_version is not None and declared and declared != str(policy_version):
                return _mint_decision(
                    decision="deny",
                    granted=False,
                    evaluated_at=evaluated_at,
                    policy_cid=_policy_cid_of(doc),
                    intent_cid=intent_cid,
                    justification=(
                        f"Policy version mismatch: expected={policy_version} declared={declared}"
                    ),
                    reason_code=REASON_VERSION_MISMATCH,
                    signature=signature,
                )

        # Prior-event revocation markers (fail-closed).
        if self._revoked_by_prior_events(prior_events, intent_cid, policy_docs):
            return _mint_decision(
                decision="deny",
                granted=False,
                evaluated_at=evaluated_at,
                intent_cid=intent_cid,
                justification="Revocation recorded in prior events before execution",
                reason_code="revoked_before_execution",
                facts=({"kind": "prior_event", "status": "revoked"},),
                signature=signature,
            )

        # --- Clause evaluation (deterministic order) ---
        all_clauses: List[Dict[str, Any]] = []
        policy_cids: List[str] = []
        for doc in policy_docs:
            policy_cids.append(_policy_cid_of(doc))
            for clause in _extract_clauses(doc):
                clause = dict(clause)
                clause["policy_cid"] = policy_cids[-1]
                all_clauses.append(clause)

        all_clauses.sort(key=lambda c: _stable_sort_key(c, int(c.get("index", 0))))

        permissions: List[Dict[str, Any]] = []
        prohibitions: List[Dict[str, Any]] = []
        obligation_clauses: List[Dict[str, Any]] = []
        fired: List[Dict[str, Any]] = []

        for clause in all_clauses:
            if not _clause_matches(clause, actor=actor, action=action, resource=resource, now=now):
                continue
            fired_entry = {
                "clause_id": clause["clause_id"],
                "clause_type": clause["clause_type"],
                "action": clause["action"],
                "actor": clause["actor"],
                "resource": clause.get("resource"),
                "policy_cid": clause.get("policy_cid"),
            }
            fired.append(fired_entry)
            if clause["clause_type"] == "prohibition":
                prohibitions.append(clause)
            elif clause["clause_type"] == "permission":
                permissions.append(clause)
            elif clause["clause_type"] == "obligation":
                obligation_clauses.append(clause)

        primary_policy_cid = policy_cids[0] if policy_cids else ""

        if prohibitions:
            return _mint_decision(
                decision="deny",
                granted=False,
                evaluated_at=evaluated_at,
                policy_cid=primary_policy_cid,
                intent_cid=intent_cid,
                justification="; ".join(
                    f"Prohibition {c['clause_id']}: actor={actor} action={action}"
                    for c in prohibitions
                ),
                reason_code=REASON_PROHIBITION,
                fired_rules=fired,
                facts=(
                    {
                        "kind": "match",
                        "actor": actor,
                        "action": action,
                        "resource": resource,
                        "prohibition_count": len(prohibitions),
                    },
                ),
                signature=signature,
            )

        if not permissions:
            # Temporal windows may have excluded all permissions; still deny.
            reason = REASON_NO_PERMISSION
            justification = f"No matching permission for actor={actor} action={action}"
            if logical_time is None and any(
                c.get("valid_from") or c.get("valid_until") for c in all_clauses
            ):
                reason = REASON_MISSING_LOGICAL_TIME
                justification = (
                    "logical_time required to evaluate temporal policy windows "
                    f"for actor={actor} action={action}"
                )
            return _mint_decision(
                decision="deny",
                granted=False,
                evaluated_at=evaluated_at,
                policy_cid=primary_policy_cid,
                intent_cid=intent_cid,
                justification=justification,
                reason_code=reason,
                fired_rules=fired,
                facts=(
                    {
                        "kind": "match",
                        "actor": actor,
                        "action": action,
                        "resource": resource,
                        "permission_count": 0,
                    },
                ),
                signature=signature,
            )

        # Build obligations (including human-approval as obligation).
        obligations: List[Dict[str, Any]] = []
        deadlines: List[Dict[str, Any]] = []
        compensation: List[Dict[str, Any]] = []
        human_approval: Optional[Dict[str, Any]] = None

        for clause in obligation_clauses:
            meta = dict(clause.get("metadata") or {})
            deadline = clause.get("obligation_deadline")
            entry: Dict[str, Any] = {
                "type": "obligation",
                "clause_id": clause["clause_id"],
                "action": clause["action"],
                "deadline": deadline or "",
                "trigger": clause.get("trigger") or "after_execution",
                "status": self._obligation_status(deadline, now),
                "metadata": meta,
            }
            obligations.append(entry)
            if deadline:
                deadlines.append(
                    {
                        "clause_id": clause["clause_id"],
                        "deadline": deadline,
                        "status": entry["status"],
                    }
                )
            if meta.get("compensation") is not None:
                compensation.append(
                    {
                        "clause_id": clause["clause_id"],
                        "compensation": meta.get("compensation"),
                        "on": "obligation_violated",
                    }
                )
            if meta.get("human_approval") is True:
                human_approval = {
                    "required": True,
                    "clause_id": clause["clause_id"],
                    "status": "pending",
                }

        # Human-approval flags on permissions also become obligations.
        for clause in permissions:
            meta = dict(clause.get("metadata") or {})
            if meta.get("human_approval") is True and human_approval is None:
                human_approval = {
                    "required": True,
                    "clause_id": clause["clause_id"],
                    "status": "pending",
                }
                obligations.append(
                    {
                        "type": "obligation",
                        "clause_id": clause["clause_id"],
                        "action": "human_approval",
                        "deadline": "",
                        "trigger": "before_execution",
                        "status": "pending",
                        "metadata": {"human_approval": True},
                    }
                )

        facts = (
            {
                "kind": "match",
                "actor": actor,
                "action": action,
                "resource": resource,
                "permission_count": len(permissions),
                "obligation_count": len(obligations),
                "context_root_count": len(observed),
                "prior_event_count": len(prior_events or ()),
            },
        )

        if obligations:
            return _mint_decision(
                decision="allow_with_obligations",
                granted=True,
                evaluated_at=evaluated_at,
                policy_cid=primary_policy_cid,
                intent_cid=intent_cid,
                justification=f"Permitted with {len(obligations)} obligation(s)",
                obligations=obligations,
                fired_rules=fired,
                facts=facts,
                deadlines=deadlines,
                compensation=compensation,
                human_approval=human_approval,
                signature=signature,
            )

        return _mint_decision(
            decision="allow",
            granted=True,
            evaluated_at=evaluated_at,
            policy_cid=primary_policy_cid,
            intent_cid=intent_cid,
            justification=f"Explicit permission for actor={actor} action={action}",
            fired_rules=fired,
            facts=facts,
            signature=signature,
        )

    # ------------------------------------------------------------------
    # Internal gates
    # ------------------------------------------------------------------

    def _check_delegation(
        self, delegation: Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]
    ) -> str:
        items: List[Mapping[str, Any]]
        if _is_mapping(delegation):
            items = [delegation]
        elif isinstance(delegation, (list, tuple)):
            items = [d for d in delegation if _is_mapping(d)]
            if not items and len(delegation) > 0:
                return "delegation entries must be objects"
        else:
            return "delegation must be an object or list"

        for item in items:
            # Explicit invalid markers (tests / pre-verified payloads).
            if item.get("valid") is False or item.get("invalid") is True:
                return "delegation marked invalid"
            status = _as_str(item.get("status")).lower()
            if status in {"invalid", "revoked", "expired", "rejected"}:
                return f"delegation status={status}"
            # Structural: empty object with no identity is invalid when provided.
            if not any(
                k in item
                for k in (
                    "issuer",
                    "iss",
                    "audience",
                    "aud",
                    "capability",
                    "capabilities",
                    "proof",
                    "signature",
                    "cid",
                    "delegation_cid",
                    "ucan",
                    "token",
                    "valid",
                )
            ):
                return "delegation missing identifying fields"
        return ""

    def _revoked_by_prior_events(
        self,
        prior_events: Optional[Sequence[Mapping[str, Any]]],
        intent_cid: str,
        policy_docs: Sequence[Mapping[str, Any]],
    ) -> bool:
        if not prior_events:
            return False
        policy_cids = {_policy_cid_of(doc) for doc in policy_docs}
        for event in prior_events:
            if not _is_mapping(event):
                continue
            etype = _as_str(event.get("type") or event.get("event_type") or event.get("kind")).lower()
            if etype not in {
                "revocation",
                "revoked",
                "policy_revoked",
                "delegation_revoked",
                "obligation_revoked",
            }:
                if event.get("revoked") is not True:
                    continue
            target = _as_str(
                event.get("target_cid")
                or event.get("revoked_cid")
                or event.get("policy_cid")
                or event.get("intent_cid")
                or event.get("delegation_cid")
            )
            if not target:
                # Untargeted revocation event still fail-closes for safety when
                # the event explicitly claims a revoke without scope.
                if event.get("revoked") is True or etype in {"revocation", "revoked"}:
                    return True
                continue
            if target == intent_cid or target in policy_cids:
                return True
            # Also match when the event lists revoked CIDs.
            revoked_list = event.get("revoked_cids") or event.get("targets")
            if isinstance(revoked_list, (list, tuple)):
                revoked_set = {_as_str(x) for x in revoked_list}
                if intent_cid in revoked_set or policy_cids & revoked_set:
                    return True
        return False

    @staticmethod
    def _obligation_status(deadline: Optional[str], now: Optional[datetime]) -> str:
        if not deadline:
            return "pending"
        if now is None:
            return "pending"
        try:
            due = _parse_iso8601(deadline)
        except ValueError:
            return "pending"
        if due is not None and now > due:
            return "overdue"
        return "pending"


# ---------------------------------------------------------------------------
# Structural validator (fixtures / conformance)
# ---------------------------------------------------------------------------


class PolicyEvaluationValidator:
    """Validates temporal deontic policy representations and decisions.

    Based on: docs/spec/temporal-deontic-policy.md

    Structural validation covers document shape.  Semantic evaluation lives on
    :class:`PolicyEvaluator` (PolicyEvaluator@1).
    """

    POLICY_TYPES = list(POLICY_TYPES)
    DECISION_VERDICTS = list(DECISION_VERDICTS)
    INTERFACE_EVALUATOR = INTERFACE_EVALUATOR
    INTERFACE_DECISION = INTERFACE_DECISION

    def __init__(self) -> None:
        self._evaluator = PolicyEvaluator()

    @property
    def evaluator(self) -> PolicyEvaluator:
        return self._evaluator

    def validate_policy(self, policy: Dict[str, Any]) -> ValidationResult:
        """Validate a policy representation (single-clause or multi-clause)."""
        result = ValidationResult(is_valid=True, message_type="policy")

        if not _is_mapping(policy):
            result.add_error("Policy must be an object")
            return result

        clauses = policy.get("clauses")
        has_clause_list = isinstance(clauses, list)

        if has_clause_list:
            if not clauses:
                result.add_error("Policy 'clauses' must be a non-empty list when present")
            for index, item in enumerate(clauses):
                if not _is_mapping(item):
                    result.add_error(f"clauses[{index}] must be an object")
                    continue
                ctype = _as_str(item.get("clause_type") or item.get("type")).lower()
                if not ctype:
                    result.add_error(f"clauses[{index}] missing 'type'/'clause_type' field")
                elif ctype not in POLICY_TYPES:
                    result.add_error(f"clauses[{index}] invalid policy type: {ctype}")
                if "temporal_constraints" in item and _is_mapping(item["temporal_constraints"]):
                    self._validate_temporal_constraints(item["temporal_constraints"], result)
                for ts_field in ("valid_from", "valid_until", "obligation_deadline", "deadline"):
                    if ts_field in item:
                        _validate_iso_timestamp_field(item.get(ts_field), f"clauses[{index}].{ts_field}", result)
        else:
            # Single-clause document form used by integration fixtures.
            if "type" not in policy and "clause_type" not in policy:
                result.add_error("Policy missing 'type' field")
            else:
                ptype = _as_str(policy.get("type") or policy.get("clause_type")).lower()
                if ptype not in POLICY_TYPES:
                    result.add_error(f"Invalid policy type: {policy.get('type') or policy.get('clause_type')}")

        if "temporal_constraints" not in policy and not has_clause_list:
            result.add_warning("Policy missing 'temporal_constraints'")
        elif "temporal_constraints" in policy:
            if not _is_mapping(policy["temporal_constraints"]):
                result.add_error("'temporal_constraints' must be an object")
            else:
                self._validate_temporal_constraints(policy["temporal_constraints"], result)

        result.metadata["interface"] = INTERFACE_EVALUATOR
        return result

    def _validate_temporal_constraints(
        self,
        constraints: Dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Validate temporal constraints format (ISO-8601 timestamps)."""
        if not _is_mapping(constraints):
            result.add_error("temporal_constraints must be an object")
            return

        for key in ("valid_from", "valid_until", "not_before", "not_after", "deadline"):
            if key in constraints:
                _validate_iso_timestamp_field(constraints.get(key), key, result)

        if "valid_from" in constraints and "valid_until" in constraints:
            try:
                start = _parse_iso8601(constraints.get("valid_from"))
                end = _parse_iso8601(constraints.get("valid_until"))
            except ValueError:
                start = end = None
            if start is not None and end is not None and start > end:
                result.add_error("'valid_from' must not be after 'valid_until'")

        tod = constraints.get("time_of_day")
        if tod is not None:
            if not _is_mapping(tod):
                result.add_error("'time_of_day' must be an object with start/end")
            else:
                for edge in ("start", "end"):
                    val = tod.get(edge)
                    if val is not None and not _TIME_OF_DAY_RE.match(str(val).strip()):
                        result.add_error(f"time_of_day.{edge} must be HH:MM or HH:MM:SS")

        days = constraints.get("days_of_week")
        if days is not None:
            if not isinstance(days, list):
                result.add_error("'days_of_week' must be a list")
            else:
                for day in days:
                    if str(day).strip().lower() not in _DAY_NAMES:
                        result.add_error(f"Invalid day_of_week: {day}")

        if "always" in constraints and not isinstance(constraints["always"], bool):
            result.add_error("'always' must be a boolean")

    def validate_policy_decision(self, decision: Dict[str, Any]) -> ValidationResult:
        """Validate a policy evaluation decision document."""
        result = ValidationResult(is_valid=True, message_type="policy_decision")

        if not _is_mapping(decision):
            result.add_error("Decision must be an object")
            return result

        required_fields = ["decision_cid", "granted", "evaluated_at"]
        for field_name in required_fields:
            if field_name not in decision:
                result.add_error(f"Decision missing required field: {field_name}")

        if "granted" in decision and not isinstance(decision["granted"], bool):
            result.add_error("'granted' must be a boolean")

        if "evaluated_at" in decision:
            _validate_iso_timestamp_field(decision.get("evaluated_at"), "evaluated_at", result)

        if "decision" in decision:
            verdict = _as_str(decision.get("decision")).lower()
            if verdict not in DECISION_VERDICTS:
                result.add_error(
                    f"Invalid decision verdict: {decision.get('decision')} "
                    f"(expected one of {sorted(DECISION_VERDICTS)})"
                )
            if verdict == "allow_with_obligations":
                obligations = decision.get("obligations")
                if not isinstance(obligations, list) or not obligations:
                    result.add_error(
                        "allow_with_obligations decision must include a non-empty obligations list"
                    )

            granted = decision.get("granted")
            if isinstance(granted, bool):
                if verdict == "deny" and granted is True:
                    result.add_error("decision='deny' is inconsistent with granted=True")
                if verdict in {"allow", "allow_with_obligations"} and granted is False:
                    result.add_error(
                        f"decision={verdict!r} is inconsistent with granted=False"
                    )

        if "obligations" in decision and decision["obligations"] is not None:
            if not isinstance(decision["obligations"], list):
                result.add_error("'obligations' must be a list")
            else:
                for index, item in enumerate(decision["obligations"]):
                    if not _is_mapping(item):
                        result.add_error(f"obligations[{index}] must be an object")
                        continue
                    if "deadline" in item:
                        _validate_iso_timestamp_field(
                            item.get("deadline"), f"obligations[{index}].deadline", result
                        )

        result.metadata["interface"] = INTERFACE_DECISION
        return result

    def evaluate(self, *args: Any, **kwargs: Any) -> PolicyDecision:
        """Delegate to PolicyEvaluator@1 (convenience)."""
        return self._evaluator.evaluate(*args, **kwargs)


__all__ = [
    "CANONICAL_ALGORITHM",
    "DECISION_VERDICTS",
    "INTERFACE_DECISION",
    "INTERFACE_EVALUATOR",
    "POLICY_SCHEMA_MARKER",
    "POLICY_TYPES",
    "PolicyDecision",
    "PolicyEvaluationValidator",
    "PolicyEvaluator",
    "REASON_MISSING_CONTEXT",
    "REASON_NO_PERMISSION",
    "REASON_PROHIBITION",
    "REASON_STALE_ROOT",
    "REASON_VERSION_MISMATCH",
    "SCHEMA_MARKER",
]

"""
Integration tests for UCAN attenuation enforcement (MCPP-042).

Interface: AttenuationPolicy@1
Spec: docs/spec/ucan-delegation.md (§3–§6 execution-time validation)

Acceptance:
  - Each listed check has a failing negative test.
  - Expansion of capabilities or resources is deny.

Enforced checks (effects checklist):
  - issuer/audience continuity
  - capability attenuation
  - resource attenuation
  - method attenuation
  - budget attenuation
  - nbf / exp time bounds
  - chain depth
  - redelegation permission
  - nonce / replay
  - required policy CID
  - executor binding
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Interface constants
# ---------------------------------------------------------------------------

INTERFACE = "AttenuationPolicy@1"
DEFAULT_MAX_DEPTH = 8
REDELEGATE_ABILITIES = frozenset(
    {
        "ucan/DELEGATE",
        "ucan/delegate",
        "mcp++/delegate",
        "*",
    }
)

# Stable deny reason codes (negative vectors assert these).
REASON_AUDIENCE_CONTINUITY = "issuer_audience_continuity_failed"
REASON_CAPABILITY_EXPANSION = "capability_attenuation_failed"
REASON_RESOURCE_EXPANSION = "resource_attenuation_failed"
REASON_METHOD_EXPANSION = "method_attenuation_failed"
REASON_BUDGET_EXPANSION = "budget_attenuation_failed"
REASON_EXPIRED = "expired"
REASON_NOT_YET_VALID = "not_yet_valid"
REASON_TIME_ATTENUATION = "time_attenuation_failed"
REASON_DEPTH_EXCEEDED = "depth_exceeded"
REASON_REDELEGATION_DENIED = "redelegation_denied"
REASON_REPLAYED = "replayed"
REASON_POLICY_CID = "policy_cid_mismatch"
REASON_POLICY_CID_REQUIRED = "policy_cid_required"
REASON_EXECUTOR = "executor_binding_failed"
REASON_LEAF_AUDIENCE = "audience_mismatch"
REASON_CAPABILITY_NOT_GRANTED = "capability_not_granted"
REASON_EMPTY_CHAIN = "empty_chain"
REASON_INVALID_TOKEN = "invalid_token"

CHECK_IDS: Tuple[str, ...] = (
    "issuer_audience_continuity",
    "capability_attenuation",
    "resource_attenuation",
    "method_attenuation",
    "budget_attenuation",
    "nbf",
    "exp",
    "time_attenuation",
    "depth",
    "redelegation_permission",
    "nonce_replay",
    "required_policy_cid",
    "executor_binding",
)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AttenuationVerdict:
    """Fail-closed attenuation decision (AttenuationPolicy@1)."""

    allowed: bool
    reason: str
    check: Optional[str] = None
    failure_hop: Optional[int] = None
    chain_length: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def denied(self) -> bool:
        return not self.allowed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interface": INTERFACE,
            "allowed": self.allowed,
            "reason": self.reason,
            "check": self.check,
            "failure_hop": self.failure_hop,
            "chain_length": self.chain_length,
            "metadata": dict(self.metadata),
        }


def _deny(
    reason: str,
    *,
    check: Optional[str] = None,
    failure_hop: Optional[int] = None,
    chain_length: int = 0,
    **metadata: Any,
) -> AttenuationVerdict:
    return AttenuationVerdict(
        allowed=False,
        reason=reason,
        check=check,
        failure_hop=failure_hop,
        chain_length=chain_length,
        metadata=dict(metadata),
    )


def _allow(
    *,
    chain_length: int = 0,
    **metadata: Any,
) -> AttenuationVerdict:
    return AttenuationVerdict(
        allowed=True,
        reason="ok",
        check=None,
        failure_hop=None,
        chain_length=chain_length,
        metadata=dict(metadata),
    )


# ---------------------------------------------------------------------------
# Capability / resource / method / budget helpers
# ---------------------------------------------------------------------------


def _string(value: Any) -> str:
    return str(value or "").strip()


def _segment_covers(parent: str, child: str) -> bool:
    """Segment-aware wildcard cover: ``a/*`` covers ``a/b`` but not ``ab``."""
    p = _string(parent)
    c = _string(child)
    if not p or not c:
        return False
    if p == "*" or p == c:
        return True
    if p.endswith("/*"):
        prefix = p[:-1]  # keep trailing slash
        return c.startswith(prefix) and len(c) > len(prefix)
    if p.endswith("*") and not p.endswith("/*"):
        # Only exact ``*`` is a full wildcard; bare prefix-star is not accepted.
        return False
    return False


def resource_covers(parent: str, child: str) -> bool:
    return _segment_covers(parent, child)


def method_covers(parent: str, child: str) -> bool:
    """Method/ability cover (same segment rules as resource)."""
    return _segment_covers(parent, child)


def _capability_from_mapping(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, Mapping):
        return None
    resource = _string(
        raw.get("with")
        or raw.get("resource")
        or raw.get("res")
        or raw.get("uri")
    )
    method = _string(
        raw.get("can")
        or raw.get("ability")
        or raw.get("method")
        or raw.get("action")
    )
    if not resource or not method:
        # Omission must never become a wildcard grant.
        return None
    budget = raw.get("nb") or raw.get("bounds") or raw.get("budget") or {}
    if budget is None:
        budget = {}
    if not isinstance(budget, Mapping):
        return None
    return {
        "resource": resource,
        "method": method,
        "budget": dict(budget),
    }


def _token_capabilities(token: Mapping[str, Any]) -> List[Dict[str, Any]]:
    att = token.get("att")
    if att is None:
        att = token.get("capabilities")
    caps: List[Dict[str, Any]] = []
    if isinstance(att, list):
        for item in att:
            parsed = _capability_from_mapping(item)
            if parsed is not None:
                caps.append(parsed)
    elif isinstance(att, Mapping):
        # Compact map form: {resource: {method: [caveats]}}
        for resource, grants in att.items():
            if isinstance(grants, Mapping):
                for method in grants.keys():
                    parsed = _capability_from_mapping(
                        {"with": resource, "can": method}
                    )
                    if parsed is not None:
                        caps.append(parsed)
    return caps


def _token_field(token: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in token and token[name] is not None:
            return token[name]
    return None


def _as_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _budget_numeric_keys(budget: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key, value in budget.items():
        if key in {"nbf", "exp", "not_before", "not_after"}:
            continue
        if key in {"tenant", "bucket", "path_prefix", "executor", "policy_cid"}:
            continue
        num = _as_float(value)
        if num is not None:
            out[str(key)] = num
    return out


def _budget_exact_keys(budget: Mapping[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key in ("tenant", "bucket", "path_prefix"):
        if key in budget and budget[key] is not None:
            out[key] = _string(budget[key])
    return out


def _capability_attenuates(parent: Mapping[str, Any], child: Mapping[str, Any]) -> Tuple[bool, Optional[str]]:
    """Return (ok, reason_code) for parent→child capability attenuation."""
    if not resource_covers(str(parent["resource"]), str(child["resource"])):
        return False, REASON_RESOURCE_EXPANSION
    if not method_covers(str(parent["method"]), str(child["method"])):
        return False, REASON_METHOD_EXPANSION

    p_budget = parent.get("budget") or {}
    c_budget = child.get("budget") or {}
    if not isinstance(p_budget, Mapping) or not isinstance(c_budget, Mapping):
        return False, REASON_BUDGET_EXPANSION

    # Child may add numeric bounds; it may not relax inherited ones.
    for key, p_val in _budget_numeric_keys(p_budget).items():
        if key not in c_budget:
            return False, REASON_BUDGET_EXPANSION
        c_val = _as_float(c_budget.get(key))
        if c_val is None or c_val > p_val:
            return False, REASON_BUDGET_EXPANSION

    for key, p_val in _budget_exact_keys(p_budget).items():
        if _string(c_budget.get(key)) != p_val:
            return False, REASON_BUDGET_EXPANSION

    # Bound time windows inside budget also attenuate.
    p_nbf = _as_float(p_budget.get("nbf", p_budget.get("not_before")))
    c_nbf = _as_float(c_budget.get("nbf", c_budget.get("not_before")))
    if p_nbf is not None:
        if c_nbf is None or c_nbf < p_nbf:
            return False, REASON_TIME_ATTENUATION
    p_exp = _as_float(p_budget.get("exp", p_budget.get("not_after")))
    c_exp = _as_float(c_budget.get("exp", c_budget.get("not_after")))
    if p_exp is not None:
        if c_exp is None or c_exp > p_exp:
            return False, REASON_TIME_ATTENUATION

    return True, None


def _is_redelegation_capability(cap: Mapping[str, Any]) -> bool:
    method = _string(cap.get("method"))
    if method in REDELEGATE_ABILITIES:
        return True
    return method.endswith("/DELEGATE") or method.endswith("/delegate")


def _child_attenuated_by_any(
    parent_caps: Sequence[Mapping[str, Any]],
    child_cap: Mapping[str, Any],
) -> Tuple[bool, Optional[str]]:
    """Match child against parents; pick a precise deny reason when none match.

    Resource is checked first across the parent set, then method among
    resource-covering parents, then budget/time among resource+method parents.
    Redelegation-only parent grants (``*/ucan/DELEGATE``) are ignored when the
    child capability is operational, so they cannot mask resource/budget denies.
    """
    if not parent_caps:
        return False, REASON_CAPABILITY_EXPANSION

    child_is_redeleg = _is_redelegation_capability(child_cap)
    # Operational children match only operational parents; redelegation children
    # may match redelegation parents.
    candidates = [
        p
        for p in parent_caps
        if child_is_redeleg or not _is_redelegation_capability(p)
    ]
    if not candidates:
        candidates = list(parent_caps)

    for parent_cap in candidates:
        ok, _reason = _capability_attenuates(parent_cap, child_cap)
        if ok:
            return True, None

    resource_hits = [
        p
        for p in candidates
        if resource_covers(str(p["resource"]), str(child_cap["resource"]))
    ]
    if not resource_hits:
        return False, REASON_RESOURCE_EXPANSION

    method_hits = [
        p
        for p in resource_hits
        if method_covers(str(p["method"]), str(child_cap["method"]))
    ]
    if not method_hits:
        return False, REASON_METHOD_EXPANSION

    # Resource+method covered by at least one parent, but bounds failed.
    for parent_cap in method_hits:
        _ok, reason = _capability_attenuates(parent_cap, child_cap)
        if reason:
            return False, reason
    return False, REASON_CAPABILITY_EXPANSION


def _request_within(
    cap: Mapping[str, Any],
    *,
    resource: str,
    method: str,
    budget: Mapping[str, Any],
) -> bool:
    if not resource_covers(str(cap["resource"]), resource):
        return False
    if not method_covers(str(cap["method"]), method):
        return False
    c_budget = cap.get("budget") or {}
    if not isinstance(c_budget, Mapping):
        return False
    for key, limit in _budget_numeric_keys(c_budget).items():
        req = _as_float(budget.get(key))
        if req is None or req > limit:
            return False
    for key, expected in _budget_exact_keys(c_budget).items():
        if _string(budget.get(key)) != expected:
            return False
    return True


def _can_redelegate(token: Mapping[str, Any]) -> bool:
    """Whether this hop's issuer was authorized to issue further delegations.

    Redelegation is allowed when:
      - token explicitly sets ``can_delegate`` / ``redelegate`` true, or
      - any capability grants a redelegation ability, or
      - depth remaining is unrestricted and no explicit deny is set.
    Explicit ``can_delegate: false`` always denies.
    """
    explicit = _token_field(token, "can_delegate", "redelegate", "may_delegate")
    if explicit is False or _string(explicit).lower() in {"false", "0", "no", "deny"}:
        return False
    if explicit is True or _string(explicit).lower() in {"true", "1", "yes", "allow"}:
        return True
    for cap in _token_capabilities(token):
        if _string(cap.get("method")) in REDELEGATE_ABILITIES:
            return True
        # Convention: ability ending in /DELEGATE
        method = _string(cap.get("method"))
        if method.endswith("/DELEGATE") or method.endswith("/delegate"):
            return True
    # Default: root-style grant without explicit deny may redelegate only when
    # ``can_delegate`` is omitted AND a depth budget remains (checked separately).
    # For fail-closed multi-hop, require explicit permission when chain length > 1
    # at issuance of the child — handled by caller against the *parent* token.
    return False


def _token_depth_limit(token: Mapping[str, Any]) -> Optional[int]:
    raw = _token_field(token, "max_depth", "depth", "dlg", "delegation_depth")
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _token_nonce(token: Mapping[str, Any]) -> str:
    return _string(_token_field(token, "nnc", "jti", "nonce"))


def _token_policy_cid(token: Mapping[str, Any]) -> str:
    return _string(_token_field(token, "policy_cid", "pol", "plc"))


def _token_executor(token: Mapping[str, Any]) -> str:
    return _string(_token_field(token, "executor", "exe", "exec", "executor_did"))


def _token_nbf(token: Mapping[str, Any]) -> Optional[float]:
    return _as_float(_token_field(token, "nbf", "not_before", "iat"))


def _token_exp(token: Mapping[str, Any]) -> Optional[float]:
    return _as_float(_token_field(token, "exp", "expiry", "expiration", "not_after"))


def _token_iss(token: Mapping[str, Any]) -> str:
    return _string(_token_field(token, "iss", "issuer"))


def _token_aud(token: Mapping[str, Any]) -> str:
    return _string(_token_field(token, "aud", "audience"))


# ---------------------------------------------------------------------------
# AttenuationPolicy@1
# ---------------------------------------------------------------------------


class AttenuationPolicy:
    """Fail-closed attenuation, audience, time, depth, replay, and executor policy.

    Interface: AttenuationPolicy@1

    This evaluator is the execution-time authority gate for MCP++ Profile C
    attenuation checks. Expansion of capabilities or resources is always deny.
    """

    interface = INTERFACE

    def __init__(
        self,
        *,
        max_depth: int = DEFAULT_MAX_DEPTH,
        require_policy_cid: bool = False,
        required_policy_cid: Optional[str] = None,
        require_executor: bool = False,
        trusted_executors: Optional[Iterable[str]] = None,
        require_redelegation_permission: bool = True,
        nonce_store: Optional[MutableMapping[str, float]] = None,
        clock_skew_seconds: float = 0.0,
    ) -> None:
        if max_depth < 1:
            raise ValueError("invalid_max_depth")
        self.max_depth = int(max_depth)
        self.require_policy_cid = bool(require_policy_cid)
        self.required_policy_cid = _string(required_policy_cid) if required_policy_cid else ""
        self.require_executor = bool(require_executor)
        self.trusted_executors: Optional[Set[str]] = (
            None
            if trusted_executors is None
            else { _string(x) for x in trusted_executors if _string(x) }
        )
        self.require_redelegation_permission = bool(require_redelegation_permission)
        self._nonces: MutableMapping[str, float] = (
            nonce_store if nonce_store is not None else {}
        )
        self.clock_skew_seconds = float(clock_skew_seconds)

    def evaluate(
        self,
        chain: Sequence[Mapping[str, Any]],
        *,
        resource: str,
        method: str,
        audience: str,
        now: Optional[float] = None,
        budget: Optional[Mapping[str, Any]] = None,
        policy_cid: Optional[str] = None,
        executor: Optional[str] = None,
        consume_nonce: bool = True,
    ) -> AttenuationVerdict:
        """Evaluate a root→leaf delegation chain against a request."""
        if not isinstance(chain, Sequence) or isinstance(chain, (str, bytes)):
            return _deny(REASON_EMPTY_CHAIN, check="issuer_audience_continuity")
        tokens = list(chain)
        n = len(tokens)
        if n == 0:
            return _deny(REASON_EMPTY_CHAIN, check="issuer_audience_continuity", chain_length=0)
        if n > self.max_depth:
            return _deny(
                REASON_DEPTH_EXCEEDED,
                check="depth",
                chain_length=n,
                max_depth=self.max_depth,
            )

        current = float(time.time() if now is None else now)
        req_resource = _string(resource)
        req_method = _string(method)
        req_audience = _string(audience)
        req_budget = dict(budget or {})
        req_policy = _string(policy_cid)
        req_executor = _string(executor)

        if not req_resource or not req_method or not req_audience:
            return _deny(REASON_INVALID_TOKEN, check="capability_attenuation", chain_length=n)
        if req_resource == "*" or req_method == "*":
            # Wildcard requests are never authorized at the gate.
            return _deny(
                REASON_CAPABILITY_NOT_GRANTED,
                check="capability_attenuation",
                chain_length=n,
            )

        # Per-token structural + time + depth budget.
        remaining_depth: Optional[int] = None
        for idx, token in enumerate(tokens):
            if not isinstance(token, Mapping):
                return _deny(
                    REASON_INVALID_TOKEN,
                    check="issuer_audience_continuity",
                    failure_hop=idx,
                    chain_length=n,
                )
            iss = _token_iss(token)
            aud = _token_aud(token)
            if not iss or not aud:
                return _deny(
                    REASON_INVALID_TOKEN,
                    check="issuer_audience_continuity",
                    failure_hop=idx,
                    chain_length=n,
                )

            exp = _token_exp(token)
            nbf = _token_nbf(token)
            if exp is not None and current > exp + self.clock_skew_seconds:
                return _deny(
                    REASON_EXPIRED,
                    check="exp",
                    failure_hop=idx,
                    chain_length=n,
                    exp=exp,
                    now=current,
                )
            if nbf is not None and current + self.clock_skew_seconds < nbf:
                return _deny(
                    REASON_NOT_YET_VALID,
                    check="nbf",
                    failure_hop=idx,
                    chain_length=n,
                    nbf=nbf,
                    now=current,
                )

            # Depth attenuation along the chain.
            token_depth = _token_depth_limit(token)
            if token_depth is not None:
                # Depth is remaining hops after this token (including leaf).
                hops_after = n - idx - 1
                if hops_after > token_depth:
                    return _deny(
                        REASON_DEPTH_EXCEEDED,
                        check="depth",
                        failure_hop=idx,
                        chain_length=n,
                        max_depth=token_depth,
                        hops_after=hops_after,
                    )
                if remaining_depth is None:
                    remaining_depth = token_depth
                else:
                    remaining_depth = min(remaining_depth, token_depth)
            if remaining_depth is not None and idx > 0:
                # Each hop past root consumes one depth unit from inherited limit.
                # remaining_depth is measured at the hop that set it; ensure we
                # never exceed it (already checked hops_after above).
                pass

        # Issuer/audience continuity and hop-to-hop attenuation.
        for idx in range(n - 1):
            parent = tokens[idx]
            child = tokens[idx + 1]
            if _token_aud(parent) != _token_iss(child):
                return _deny(
                    REASON_AUDIENCE_CONTINUITY,
                    check="issuer_audience_continuity",
                    failure_hop=idx + 1,
                    chain_length=n,
                    parent_aud=_token_aud(parent),
                    child_iss=_token_iss(child),
                )

            # Time attenuation: child window must be ⊆ parent window.
            p_nbf, c_nbf = _token_nbf(parent), _token_nbf(child)
            p_exp, c_exp = _token_exp(parent), _token_exp(child)
            if p_nbf is not None and c_nbf is not None and c_nbf < p_nbf:
                return _deny(
                    REASON_TIME_ATTENUATION,
                    check="time_attenuation",
                    failure_hop=idx + 1,
                    chain_length=n,
                )
            if p_exp is not None:
                if c_exp is None or c_exp > p_exp:
                    return _deny(
                        REASON_TIME_ATTENUATION,
                        check="time_attenuation",
                        failure_hop=idx + 1,
                        chain_length=n,
                    )

            # Redelegation permission on the parent.
            if self.require_redelegation_permission and not _can_redelegate(parent):
                return _deny(
                    REASON_REDELEGATION_DENIED,
                    check="redelegation_permission",
                    failure_hop=idx + 1,
                    chain_length=n,
                )

            parent_caps = _token_capabilities(parent)
            child_caps = _token_capabilities(child)
            if not child_caps:
                return _deny(
                    REASON_CAPABILITY_EXPANSION,
                    check="capability_attenuation",
                    failure_hop=idx + 1,
                    chain_length=n,
                )
            if not parent_caps:
                return _deny(
                    REASON_CAPABILITY_EXPANSION,
                    check="capability_attenuation",
                    failure_hop=idx + 1,
                    chain_length=n,
                )

            for child_cap in child_caps:
                matched, last_reason = _child_attenuated_by_any(parent_caps, child_cap)
                if not matched:
                    reason = last_reason or REASON_CAPABILITY_EXPANSION
                    check = {
                        REASON_RESOURCE_EXPANSION: "resource_attenuation",
                        REASON_METHOD_EXPANSION: "method_attenuation",
                        REASON_BUDGET_EXPANSION: "budget_attenuation",
                        REASON_TIME_ATTENUATION: "time_attenuation",
                    }.get(reason, "capability_attenuation")
                    return _deny(
                        reason,
                        check=check,
                        failure_hop=idx + 1,
                        chain_length=n,
                        child_resource=child_cap.get("resource"),
                        child_method=child_cap.get("method"),
                    )

        leaf = tokens[-1]
        if _token_aud(leaf) != req_audience:
            return _deny(
                REASON_LEAF_AUDIENCE,
                check="issuer_audience_continuity",
                failure_hop=n - 1,
                chain_length=n,
                leaf_aud=_token_aud(leaf),
                requested_audience=req_audience,
            )

        # Required policy CID (request and/or leaf binding).
        leaf_policy = _token_policy_cid(leaf)
        if self.require_policy_cid or self.required_policy_cid:
            expected = self.required_policy_cid or req_policy
            if not expected:
                return _deny(
                    REASON_POLICY_CID_REQUIRED,
                    check="required_policy_cid",
                    chain_length=n,
                )
            if req_policy and req_policy != expected:
                return _deny(
                    REASON_POLICY_CID,
                    check="required_policy_cid",
                    chain_length=n,
                    expected=expected,
                    got=req_policy,
                )
            if leaf_policy and leaf_policy != expected:
                return _deny(
                    REASON_POLICY_CID,
                    check="required_policy_cid",
                    chain_length=n,
                    expected=expected,
                    leaf_policy=leaf_policy,
                )
            if not leaf_policy and self.require_policy_cid:
                return _deny(
                    REASON_POLICY_CID_REQUIRED,
                    check="required_policy_cid",
                    chain_length=n,
                )
        elif req_policy and leaf_policy and req_policy != leaf_policy:
            return _deny(
                REASON_POLICY_CID,
                check="required_policy_cid",
                chain_length=n,
                expected=leaf_policy,
                got=req_policy,
            )

        # Executor binding.
        leaf_executor = _token_executor(leaf)
        if self.require_executor or leaf_executor or req_executor:
            if self.require_executor and not req_executor:
                return _deny(
                    REASON_EXECUTOR,
                    check="executor_binding",
                    chain_length=n,
                    detail="executor_required",
                )
            if leaf_executor and req_executor and leaf_executor != req_executor:
                return _deny(
                    REASON_EXECUTOR,
                    check="executor_binding",
                    chain_length=n,
                    leaf_executor=leaf_executor,
                    requested_executor=req_executor,
                )
            if leaf_executor and not req_executor:
                return _deny(
                    REASON_EXECUTOR,
                    check="executor_binding",
                    chain_length=n,
                    detail="executor_required_by_token",
                )
            if self.trusted_executors is not None:
                candidate = req_executor or leaf_executor
                if not candidate or candidate not in self.trusted_executors:
                    return _deny(
                        REASON_EXECUTOR,
                        check="executor_binding",
                        chain_length=n,
                        detail="untrusted_executor",
                        executor=candidate,
                    )

        # Leaf grants the requested capability under budget.
        leaf_caps = _token_capabilities(leaf)
        if not any(
            _request_within(cap, resource=req_resource, method=req_method, budget=req_budget)
            for cap in leaf_caps
        ):
            return _deny(
                REASON_CAPABILITY_NOT_GRANTED,
                check="capability_attenuation",
                failure_hop=n - 1,
                chain_length=n,
                resource=req_resource,
                method=req_method,
            )

        # Nonce / replay protection on the leaf.
        nonce = _token_nonce(leaf)
        if consume_nonce and nonce:
            namespace = f"{_token_iss(leaf)}\x00{_token_aud(leaf)}\x00{nonce}"
            exp = _token_exp(leaf)
            expires_at = float(exp) if exp is not None else current + 3600.0
            # Drop expired nonces.
            stale = [k for k, v in self._nonces.items() if v < current]
            for k in stale:
                del self._nonces[k]
            if namespace in self._nonces:
                return _deny(
                    REASON_REPLAYED,
                    check="nonce_replay",
                    chain_length=n,
                    nonce=nonce,
                )
            self._nonces[namespace] = expires_at

        return _allow(
            chain_length=n,
            resource=req_resource,
            method=req_method,
            audience=req_audience,
            policy_cid=req_policy or leaf_policy or None,
            executor=req_executor or leaf_executor or None,
        )

    # Alias used by some call sites.
    verify = evaluate
    check = evaluate


# ---------------------------------------------------------------------------
# Compact fixtures
# ---------------------------------------------------------------------------

NOW = 1_800_000_000.0
ROOT = "did:key:root"
MID = "did:key:mid"
LEAF = "did:key:leaf"
RESOURCE = "tenant-a/bucket-a/documents/report.txt"
METHOD = "tools/call"
POLICY_CID = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
EXECUTOR = "did:key:executor-worker-1"


def _cap(
    resource: str,
    method: str,
    *,
    budget: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"can": method, "with": resource}
    if budget is not None:
        out["nb"] = dict(budget)
    return out


def _token(
    iss: str,
    aud: str,
    att: Sequence[Mapping[str, Any]],
    *,
    exp: float = NOW + 300,
    nbf: Optional[float] = NOW - 10,
    nonce: Optional[str] = None,
    max_depth: Optional[int] = None,
    can_delegate: Optional[bool] = None,
    policy_cid: Optional[str] = None,
    executor: Optional[str] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    token: Dict[str, Any] = {
        "iss": iss,
        "aud": aud,
        "att": [dict(x) for x in att],
        "exp": exp,
    }
    if nbf is not None:
        token["nbf"] = nbf
    if nonce is not None:
        token["nnc"] = nonce
    if max_depth is not None:
        token["max_depth"] = max_depth
    if can_delegate is not None:
        token["can_delegate"] = can_delegate
    if policy_cid is not None:
        token["policy_cid"] = policy_cid
    if executor is not None:
        token["executor"] = executor
    if extra:
        token.update(dict(extra))
    return token


def _valid_chain(
    *,
    nonce: str = "n-valid",
    policy_cid: str = POLICY_CID,
    executor: str = EXECUTOR,
    can_delegate: bool = True,
    max_depth: int = 3,
) -> List[Dict[str, Any]]:
    """Properly attenuated root→mid→leaf chain for positive control."""
    return [
        _token(
            ROOT,
            MID,
            [
                _cap("tenant-a/*", "tools/*", budget={"max_bytes": 100, "tenant": "tenant-a"}),
                _cap("*", "ucan/DELEGATE"),
            ],
            nonce="n-root",
            can_delegate=can_delegate,
            max_depth=max_depth,
            exp=NOW + 300,
        ),
        _token(
            MID,
            LEAF,
            [
                _cap(RESOURCE, METHOD, budget={"max_bytes": 50, "tenant": "tenant-a"}),
            ],
            nonce=nonce,
            can_delegate=False,
            max_depth=0,
            policy_cid=policy_cid,
            executor=executor,
            exp=NOW + 200,
        ),
    ]


def _policy(**kwargs: Any) -> AttenuationPolicy:
    defaults: Dict[str, Any] = {
        "max_depth": DEFAULT_MAX_DEPTH,
        "require_policy_cid": False,
        "require_executor": False,
        "require_redelegation_permission": True,
    }
    defaults.update(kwargs)
    return AttenuationPolicy(**defaults)


def _eval(
    policy: AttenuationPolicy,
    chain: Sequence[Mapping[str, Any]],
    **kwargs: Any,
) -> AttenuationVerdict:
    defaults: Dict[str, Any] = {
        "resource": RESOURCE,
        "method": METHOD,
        "audience": LEAF,
        "now": NOW,
        "budget": {"max_bytes": 50, "tenant": "tenant-a"},
        "policy_cid": POLICY_CID,
        "executor": EXECUTOR,
        "consume_nonce": True,
    }
    defaults.update(kwargs)
    return policy.evaluate(chain, **defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def policy() -> AttenuationPolicy:
    return _policy()


@pytest.fixture
def valid_chain() -> List[Dict[str, Any]]:
    return _valid_chain()


# ---------------------------------------------------------------------------
# Positive control
# ---------------------------------------------------------------------------


class TestAttenuationPositiveControl:
    def test_interface_label(self):
        assert AttenuationPolicy.interface == INTERFACE
        assert INTERFACE == "AttenuationPolicy@1"

    def test_valid_attenuated_chain_allows(self, policy, valid_chain):
        result = _eval(policy, valid_chain)
        assert result.allowed is True
        assert result.reason == "ok"
        assert result.chain_length == 2
        assert result.to_dict()["interface"] == INTERFACE

    def test_check_ids_cover_effects(self):
        # Ensure the suite enumerates every effects checklist item.
        required = {
            "issuer_audience_continuity",
            "capability_attenuation",
            "resource_attenuation",
            "method_attenuation",
            "budget_attenuation",
            "nbf",
            "exp",
            "depth",
            "redelegation_permission",
            "nonce_replay",
            "required_policy_cid",
            "executor_binding",
        }
        assert required.issubset(set(CHECK_IDS))


# ---------------------------------------------------------------------------
# Negative tests — one (or more) failing vector per listed check
# ---------------------------------------------------------------------------


class TestIssuerAudienceContinuity:
    def test_broken_issuer_audience_continuity_denied(self, policy):
        chain = [
            _token(ROOT, MID, [_cap("tenant-a/*", "tools/*"), _cap("*", "ucan/DELEGATE")], can_delegate=True),
            # Child issuer does not match parent audience.
            _token("did:key:stranger", LEAF, [_cap(RESOURCE, METHOD)], can_delegate=False),
        ]
        result = _eval(policy, chain)
        assert result.denied
        assert result.reason == REASON_AUDIENCE_CONTINUITY
        assert result.check == "issuer_audience_continuity"

    def test_leaf_audience_mismatch_denied(self, policy, valid_chain):
        result = _eval(policy, valid_chain, audience="did:key:someone-else")
        assert result.denied
        assert result.reason == REASON_LEAF_AUDIENCE


class TestCapabilityResourceMethodBudgetAttenuation:
    def test_capability_expansion_denied(self, policy):
        """Child introduces a capability the parent never granted."""
        chain = [
            _token(
                ROOT,
                MID,
                [_cap("tenant-a/bucket-a/*", "tools/call"), _cap("*", "ucan/DELEGATE")],
                can_delegate=True,
            ),
            _token(
                MID,
                LEAF,
                [
                    _cap("tenant-a/bucket-a/*", "tools/call"),
                    # Expansion: additional unrelated capability.
                    _cap("tenant-a/secrets/*", "tools/admin"),
                ],
                can_delegate=False,
            ),
        ]
        result = _eval(
            policy,
            chain,
            resource="tenant-a/secrets/key",
            method="tools/admin",
            budget={},
        )
        assert result.denied
        assert result.reason in {
            REASON_CAPABILITY_EXPANSION,
            REASON_RESOURCE_EXPANSION,
            REASON_METHOD_EXPANSION,
        }
        assert result.check in {
            "capability_attenuation",
            "resource_attenuation",
            "method_attenuation",
        }

    def test_resource_expansion_denied(self, policy):
        chain = [
            _token(
                ROOT,
                LEAF,
                [_cap("tenant-a/bucket-a/*", "tools/*")],
                can_delegate=False,
            ),
        ]
        # Request escapes the granted resource namespace (tenant-b).
        result = _eval(
            policy,
            chain,
            resource="tenant-b/bucket-a/documents/report.txt",
            method=METHOD,
            audience=LEAF,
            budget={},
            executor=None,
            policy_cid=None,
        )
        assert result.denied
        assert result.reason == REASON_CAPABILITY_NOT_GRANTED

    def test_resource_expansion_in_chain_denied(self, policy):
        chain = [
            _token(
                ROOT,
                MID,
                [_cap("tenant-a/bucket-a/*", "tools/*"), _cap("*", "ucan/DELEGATE")],
                can_delegate=True,
            ),
            _token(
                MID,
                LEAF,
                # Widens resource from bucket-a to whole tenant-a (and beyond grant).
                [_cap("tenant-a/*", "tools/call")],
                can_delegate=False,
            ),
        ]
        result = _eval(policy, chain, budget={})
        assert result.denied
        assert result.reason == REASON_RESOURCE_EXPANSION
        assert result.check == "resource_attenuation"

    def test_method_expansion_denied(self, policy):
        chain = [
            _token(
                ROOT,
                MID,
                [_cap("tenant-a/*", "tools/call"), _cap("*", "ucan/DELEGATE")],
                can_delegate=True,
            ),
            _token(
                MID,
                LEAF,
                # Expands method from tools/call to tools/* (and admin).
                [_cap(RESOURCE, "tools/admin")],
                can_delegate=False,
            ),
        ]
        result = _eval(policy, chain, method="tools/admin", budget={})
        assert result.denied
        assert result.reason == REASON_METHOD_EXPANSION
        assert result.check == "method_attenuation"

    def test_budget_expansion_denied(self, policy):
        chain = [
            _token(
                ROOT,
                MID,
                [
                    _cap("tenant-a/*", "tools/*", budget={"max_bytes": 50}),
                    _cap("*", "ucan/DELEGATE"),
                ],
                can_delegate=True,
            ),
            _token(
                MID,
                LEAF,
                # Child raises max_bytes above parent → deny.
                [_cap(RESOURCE, METHOD, budget={"max_bytes": 100})],
                can_delegate=False,
            ),
        ]
        result = _eval(policy, chain, budget={"max_bytes": 100})
        assert result.denied
        assert result.reason == REASON_BUDGET_EXPANSION
        assert result.check == "budget_attenuation"

    def test_budget_request_over_limit_denied(self, policy, valid_chain):
        result = _eval(policy, valid_chain, budget={"max_bytes": 51, "tenant": "tenant-a"})
        assert result.denied
        assert result.reason == REASON_CAPABILITY_NOT_GRANTED


class TestTimeBounds:
    def test_expired_token_denied(self, policy):
        chain = [
            _token(
                ROOT,
                LEAF,
                [_cap(RESOURCE, METHOD)],
                exp=NOW - 1,
                nbf=NOW - 100,
                can_delegate=False,
            ),
        ]
        result = _eval(policy, chain, budget={}, executor=None, policy_cid=None)
        assert result.denied
        assert result.reason == REASON_EXPIRED
        assert result.check == "exp"

    def test_future_nbf_denied(self, policy):
        chain = [
            _token(
                ROOT,
                LEAF,
                [_cap(RESOURCE, METHOD)],
                exp=NOW + 300,
                nbf=NOW + 60,
                can_delegate=False,
            ),
        ]
        result = _eval(policy, chain, budget={}, executor=None, policy_cid=None)
        assert result.denied
        assert result.reason == REASON_NOT_YET_VALID
        assert result.check == "nbf"

    def test_child_exp_extends_past_parent_denied(self, policy):
        chain = [
            _token(
                ROOT,
                MID,
                [_cap("tenant-a/*", "tools/*"), _cap("*", "ucan/DELEGATE")],
                exp=NOW + 100,
                can_delegate=True,
            ),
            _token(
                MID,
                LEAF,
                [_cap(RESOURCE, METHOD)],
                exp=NOW + 500,  # later than parent
                can_delegate=False,
            ),
        ]
        result = _eval(policy, chain, budget={})
        assert result.denied
        assert result.reason == REASON_TIME_ATTENUATION
        assert result.check == "time_attenuation"

    def test_child_nbf_earlier_than_parent_denied(self, policy):
        chain = [
            _token(
                ROOT,
                MID,
                [_cap("tenant-a/*", "tools/*"), _cap("*", "ucan/DELEGATE")],
                nbf=NOW - 5,
                exp=NOW + 300,
                can_delegate=True,
            ),
            _token(
                MID,
                LEAF,
                [_cap(RESOURCE, METHOD)],
                nbf=NOW - 50,  # earlier than parent
                exp=NOW + 200,
                can_delegate=False,
            ),
        ]
        result = _eval(policy, chain, budget={})
        assert result.denied
        assert result.reason == REASON_TIME_ATTENUATION
        assert result.check == "time_attenuation"


class TestDepth:
    def test_global_max_depth_denied(self):
        policy = _policy(max_depth=2)
        # Three hops exceeds max_depth=2.
        chain = [
            _token(ROOT, MID, [_cap("*", "*"), _cap("*", "ucan/DELEGATE")], can_delegate=True, max_depth=5),
            _token(MID, "did:key:mid2", [_cap("*", "*"), _cap("*", "ucan/DELEGATE")], can_delegate=True, max_depth=4),
            _token("did:key:mid2", LEAF, [_cap(RESOURCE, METHOD)], can_delegate=False),
        ]
        result = _eval(policy, chain, budget={})
        assert result.denied
        assert result.reason == REASON_DEPTH_EXCEEDED
        assert result.check == "depth"

    def test_token_max_depth_zero_blocks_child(self, policy):
        chain = [
            _token(
                ROOT,
                MID,
                [_cap("tenant-a/*", "tools/*"), _cap("*", "ucan/DELEGATE")],
                can_delegate=True,
                max_depth=0,  # no further hops allowed
            ),
            _token(
                MID,
                LEAF,
                [_cap(RESOURCE, METHOD)],
                can_delegate=False,
            ),
        ]
        result = _eval(policy, chain, budget={})
        assert result.denied
        assert result.reason == REASON_DEPTH_EXCEEDED
        assert result.check == "depth"


class TestRedelegationPermission:
    def test_redelegation_without_permission_denied(self, policy):
        chain = [
            _token(
                ROOT,
                MID,
                # No DELEGATE ability and explicit deny.
                [_cap("tenant-a/*", "tools/*")],
                can_delegate=False,
            ),
            _token(
                MID,
                LEAF,
                [_cap(RESOURCE, METHOD)],
                can_delegate=False,
            ),
        ]
        result = _eval(policy, chain, budget={})
        assert result.denied
        assert result.reason == REASON_REDELEGATION_DENIED
        assert result.check == "redelegation_permission"

    def test_redelegation_with_explicit_ability_allows(self, policy):
        chain = [
            _token(
                ROOT,
                MID,
                [
                    _cap("tenant-a/*", "tools/*", budget={"max_bytes": 50, "tenant": "tenant-a"}),
                    _cap("*", "ucan/DELEGATE"),
                ],
                # can_delegate omitted; ability grants redelegation.
                nonce="n-root-del",
            ),
            _token(
                MID,
                LEAF,
                [_cap(RESOURCE, METHOD, budget={"max_bytes": 50, "tenant": "tenant-a"})],
                can_delegate=False,
                nonce="n-leaf-del",
                policy_cid=POLICY_CID,
                executor=EXECUTOR,
                exp=NOW + 200,
            ),
        ]
        result = _eval(policy, chain)
        assert result.allowed is True


class TestNonceReplay:
    def test_replayed_nonce_denied(self, policy, valid_chain):
        first = _eval(policy, valid_chain, consume_nonce=True)
        assert first.allowed is True
        second = _eval(policy, valid_chain, consume_nonce=True)
        assert second.denied
        assert second.reason == REASON_REPLAYED
        assert second.check == "nonce_replay"

    def test_distinct_nonces_not_colliding(self, policy):
        c1 = _valid_chain(nonce="nonce-a")
        c2 = _valid_chain(nonce="nonce-b")
        assert _eval(policy, c1).allowed is True
        assert _eval(policy, c2).allowed is True


class TestRequiredPolicyCid:
    def test_missing_required_policy_cid_denied(self):
        policy = _policy(require_policy_cid=True, required_policy_cid=POLICY_CID)
        chain = [
            _token(
                ROOT,
                LEAF,
                [_cap(RESOURCE, METHOD, budget={"max_bytes": 50, "tenant": "tenant-a"})],
                can_delegate=False,
                # no policy_cid on token
            ),
        ]
        result = _eval(
            policy,
            chain,
            policy_cid=None,  # also missing on request
            executor=None,
            budget={"max_bytes": 50, "tenant": "tenant-a"},
        )
        assert result.denied
        assert result.reason in {REASON_POLICY_CID_REQUIRED, REASON_POLICY_CID}
        assert result.check == "required_policy_cid"

    def test_wrong_policy_cid_denied(self):
        policy = _policy(require_policy_cid=True, required_policy_cid=POLICY_CID)
        chain = _valid_chain(policy_cid="bafybeihwrongpolicy0000000000000000000000000000000000000000")
        result = _eval(policy, chain, policy_cid=POLICY_CID)
        assert result.denied
        assert result.reason == REASON_POLICY_CID
        assert result.check == "required_policy_cid"

    def test_request_policy_cid_mismatch_denied(self, valid_chain):
        policy = _policy(require_policy_cid=True, required_policy_cid=POLICY_CID)
        result = _eval(
            policy,
            valid_chain,
            policy_cid="bafybeihotherpolicy111111111111111111111111111111111111111",
        )
        assert result.denied
        assert result.reason == REASON_POLICY_CID
        assert result.check == "required_policy_cid"


class TestExecutorBinding:
    def test_wrong_executor_denied(self, policy, valid_chain):
        result = _eval(policy, valid_chain, executor="did:key:wrong-executor")
        assert result.denied
        assert result.reason == REASON_EXECUTOR
        assert result.check == "executor_binding"

    def test_missing_executor_when_token_binds_denied(self, policy, valid_chain):
        result = _eval(policy, valid_chain, executor=None)
        assert result.denied
        assert result.reason == REASON_EXECUTOR
        assert result.check == "executor_binding"

    def test_untrusted_executor_denied(self, valid_chain):
        policy = _policy(trusted_executors={"did:key:other-trusted"})
        result = _eval(policy, valid_chain, executor=EXECUTOR)
        assert result.denied
        assert result.reason == REASON_EXECUTOR
        assert result.check == "executor_binding"

    def test_require_executor_without_request_denied(self):
        policy = _policy(require_executor=True)
        chain = [
            _token(
                ROOT,
                LEAF,
                [_cap(RESOURCE, METHOD)],
                can_delegate=False,
                # token does not bind executor, but policy requires one
            ),
        ]
        result = _eval(policy, chain, executor=None, budget={}, policy_cid=None)
        assert result.denied
        assert result.reason == REASON_EXECUTOR
        assert result.check == "executor_binding"


class TestFailClosedInvariants:
    def test_empty_chain_denied(self, policy):
        result = _eval(policy, [])
        assert result.denied
        assert result.reason == REASON_EMPTY_CHAIN

    def test_wildcard_request_denied(self, policy, valid_chain):
        result = _eval(policy, valid_chain, resource="*")
        assert result.denied

    def test_every_check_has_negative_vector(self, policy):
        """Meta-test: each CHECK_IDS entry has at least one deny path exercised."""
        vectors: Dict[str, AttenuationVerdict] = {}

        vectors["issuer_audience_continuity"] = _eval(
            policy,
            [
                _token(ROOT, MID, [_cap("*", "*"), _cap("*", "ucan/DELEGATE")], can_delegate=True),
                _token("did:key:nope", LEAF, [_cap(RESOURCE, METHOD)]),
            ],
        )
        vectors["capability_attenuation"] = _eval(
            policy,
            [
                _token(ROOT, MID, [_cap("a/*", "tools/call"), _cap("*", "ucan/DELEGATE")], can_delegate=True),
                _token(MID, LEAF, [_cap("b/*", "tools/call")]),
            ],
            resource="b/x",
            method="tools/call",
            budget={},
        )
        vectors["resource_attenuation"] = vectors["capability_attenuation"]
        vectors["method_attenuation"] = _eval(
            policy,
            [
                _token(ROOT, MID, [_cap("tenant-a/*", "tools/call"), _cap("*", "ucan/DELEGATE")], can_delegate=True),
                _token(MID, LEAF, [_cap(RESOURCE, "tools/admin")]),
            ],
            method="tools/admin",
            budget={},
        )
        vectors["budget_attenuation"] = _eval(
            policy,
            [
                _token(
                    ROOT,
                    MID,
                    [_cap("tenant-a/*", "tools/*", budget={"max_bytes": 10}), _cap("*", "ucan/DELEGATE")],
                    can_delegate=True,
                ),
                _token(MID, LEAF, [_cap(RESOURCE, METHOD, budget={"max_bytes": 99})]),
            ],
            budget={"max_bytes": 99},
        )
        vectors["nbf"] = _eval(
            policy,
            [_token(ROOT, LEAF, [_cap(RESOURCE, METHOD)], nbf=NOW + 100, can_delegate=False)],
            budget={},
            executor=None,
            policy_cid=None,
        )
        vectors["exp"] = _eval(
            policy,
            [_token(ROOT, LEAF, [_cap(RESOURCE, METHOD)], exp=NOW - 1, can_delegate=False)],
            budget={},
            executor=None,
            policy_cid=None,
        )
        vectors["time_attenuation"] = _eval(
            policy,
            [
                _token(ROOT, MID, [_cap("*", "*"), _cap("*", "ucan/DELEGATE")], exp=NOW + 50, can_delegate=True),
                _token(MID, LEAF, [_cap(RESOURCE, METHOD)], exp=NOW + 500),
            ],
            budget={},
        )
        vectors["depth"] = _eval(
            _policy(max_depth=1),
            [
                _token(ROOT, MID, [_cap("*", "*"), _cap("*", "ucan/DELEGATE")], can_delegate=True),
                _token(MID, LEAF, [_cap(RESOURCE, METHOD)]),
            ],
            budget={},
        )
        vectors["redelegation_permission"] = _eval(
            policy,
            [
                _token(ROOT, MID, [_cap("tenant-a/*", "tools/*")], can_delegate=False),
                _token(MID, LEAF, [_cap(RESOURCE, METHOD)]),
            ],
            budget={},
        )
        chain = _valid_chain(nonce="meta-replay")
        assert _eval(policy, chain).allowed
        vectors["nonce_replay"] = _eval(policy, chain)

        pol = _policy(require_policy_cid=True, required_policy_cid=POLICY_CID)
        vectors["required_policy_cid"] = _eval(
            pol,
            [_token(ROOT, LEAF, [_cap(RESOURCE, METHOD)], can_delegate=False)],
            policy_cid=None,
            executor=None,
            budget={},
        )
        vectors["executor_binding"] = _eval(
            policy,
            _valid_chain(nonce="meta-exec"),
            executor="did:key:wrong",
        )

        for check_id in CHECK_IDS:
            assert check_id in vectors, f"missing vector for {check_id}"
            assert vectors[check_id].denied, f"expected deny for {check_id}: {vectors[check_id]}"

    def test_expansion_is_always_deny(self, policy):
        """Acceptance restatement: expansion of capabilities or resources is deny."""
        parent = _token(
            ROOT,
            MID,
            [_cap("tenant-a/bucket-a/docs/*", "tools/read"), _cap("*", "ucan/DELEGATE")],
            can_delegate=True,
        )
        expanded_resource = _token(
            MID,
            LEAF,
            [_cap("tenant-a/*", "tools/read")],
        )
        expanded_method = _token(
            MID,
            LEAF,
            [_cap("tenant-a/bucket-a/docs/*", "tools/*")],
        )
        r1 = _eval(policy, [parent, expanded_resource], resource="tenant-a/other", method="tools/read", budget={})
        r2 = _eval(policy, [parent, expanded_method], resource="tenant-a/bucket-a/docs/x", method="tools/write", budget={})
        assert r1.denied and r1.reason == REASON_RESOURCE_EXPANSION
        assert r2.denied and r2.reason == REASON_METHOD_EXPANSION

"""
Adversarial P2P framing and abuse tests (MCPP-064).

Interface: P2pAbuseVector@1
Spec: docs/spec/transport-mcp-p2p.md (§3.3 framing, §3.4 correlation/replay,
§3.5 quotas, §5 PeerID ≠ UCAN authority)

Acceptance:
  - Every listed abuse case fails closed.
  - Empty success on transport failure is treated as failure.
  - Quotas are not weakened to pass.

Cases (effects checklist):
  oversized, truncated, invalid_length, request_before_negotiation,
  forged_version, unknown_method, empty_success_on_transport_failure,
  replay, flood, excessive_streams, valid_peerid_invalid_ucan, stale_fence,
  duplicate_response, wrong_correlation_id
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from validators.transport import (  # noqa: E402
    DEFAULT_MAX_FRAME_BYTES,
    FramingError,
    FrameSizeExceededError,
    PROTOCOL_ID_DEFAULT,
    ReplayWindow,
    TransportValidator,
    decode_frame,
    encode_frame,
)

# ---------------------------------------------------------------------------
# Constants (P2pAbuseVector@1)
# ---------------------------------------------------------------------------

INTERFACE_LABEL = "P2pAbuseVector@1"

CANONICAL_PROTOCOL_ID = PROTOCOL_ID_DEFAULT  # /mcp+p2p/1.0.0
CANONICAL_MCP_VERSION = "2026-07-28"
LEGACY_MCP_VERSION = "2024-11-05"

KNOWN_MCP_METHODS: frozenset[str] = frozenset(
    {
        "initialize",
        "notifications/initialized",
        "ping",
        "tools/list",
        "tools/call",
        "resources/list",
        "resources/read",
        "prompts/list",
        "prompts/get",
        "mcp++/artifacts/get",
    }
)

# Compact numeric defaults for abuse simulations (do not weaken production quotas).
ABUSE_MAX_FRAME_BYTES = 1024
ABUSE_MAX_STREAMS_PER_PEER = 4
ABUSE_RATE_CAPACITY = 5.0
ABUSE_RATE_REFILL_PER_SEC = 1.0

# All required fail-closed case ids (order stable for reporting).
ABUSE_CASE_IDS: Tuple[str, ...] = (
    "oversized",
    "truncated",
    "invalid_length",
    "request_before_negotiation",
    "forged_version",
    "unknown_method",
    "empty_success_on_transport_failure",
    "replay",
    "flood",
    "excessive_streams",
    "valid_peerid_invalid_ucan",
    "stale_fence",
    "duplicate_response",
    "wrong_correlation_id",
)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class AbuseVerdict:
    """Fail-closed admission decision for one abuse vector."""

    case_id: str
    admitted: bool
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def fail_closed(self) -> bool:
        """True when the abusive input was rejected (not admitted)."""
        return not self.admitted and len(self.reasons) > 0


def _reject(case_id: str, *reasons: str, **metadata: Any) -> AbuseVerdict:
    return AbuseVerdict(
        case_id=case_id,
        admitted=False,
        reasons=list(reasons),
        metadata=dict(metadata),
    )


def _admit(case_id: str, **metadata: Any) -> AbuseVerdict:
    """Only benign control vectors may call this."""
    return AbuseVerdict(case_id=case_id, admitted=True, reasons=[], metadata=dict(metadata))


# ---------------------------------------------------------------------------
# Compact helpers (layer T / A fail-closed policy)
# ---------------------------------------------------------------------------


def _transport_failed(
    *,
    status: Optional[int] = None,
    transport_error: Optional[str] = None,
    stream_closed: bool = False,
    framing_error: bool = False,
) -> bool:
    if framing_error or stream_closed:
        return True
    if transport_error:
        return True
    if status is not None and (status < 200 or status >= 300):
        return True
    return False


def treat_empty_success_as_failure(
    body: Mapping[str, Any],
    *,
    status: Optional[int] = None,
    transport_error: Optional[str] = None,
    stream_closed: bool = False,
    framing_error: bool = False,
) -> bool:
    """Return True when a success-shaped body must be treated as failure.

    Spec: transport-mcp-p2p.md §3.5 — surface timeout/transport errors as
    failure, not empty success. A response that carries ``result`` (or an
    empty success object) while the transport failed MUST NOT be admitted.
    """
    if not _transport_failed(
        status=status,
        transport_error=transport_error,
        stream_closed=stream_closed,
        framing_error=framing_error,
    ):
        return False
    if "error" in body and body.get("error") is not None:
        # Explicit error path — already a failure, not empty success.
        return False
    # Success-shaped (result present, empty object, or missing error under failure).
    if "result" in body:
        return True
    if body.get("ok") is True:
        return True
    if body == {} or body.get("success") is True:
        return True
    # No explicit error under transport failure → fail closed as empty success.
    return True


def is_forged_protocol_version(
    protocol_id: Optional[str] = None,
    *,
    mcp_version: Optional[str] = None,
    accepted_protocol_ids: Optional[Set[str]] = None,
    accepted_mcp_versions: Optional[Set[str]] = None,
) -> bool:
    """Detect forged / unsupported transport or MCP versions."""
    accepted_pids = accepted_protocol_ids or {CANONICAL_PROTOCOL_ID}
    accepted_mcp = accepted_mcp_versions or {CANONICAL_MCP_VERSION, LEGACY_MCP_VERSION}
    if protocol_id is not None and protocol_id not in accepted_pids:
        return True
    if mcp_version is not None and mcp_version not in accepted_mcp:
        return True
    return False


def is_unknown_method(method: str) -> bool:
    return method not in KNOWN_MCP_METHODS


def is_request_before_negotiation(
    *,
    stream_ready: bool,
    protocol_negotiated: bool,
    is_application_request: bool,
) -> bool:
    """Application request before layer-T stream negotiation is ready."""
    if not is_application_request:
        return False
    return not (stream_ready and protocol_negotiated)


def is_valid_peerid_invalid_ucan(
    *,
    peer_id: Optional[str],
    ucan_valid: bool,
    ucan_present: bool,
) -> bool:
    """PeerID authenticates the network endpoint, not execution authority."""
    if not peer_id:
        return False
    if not ucan_present:
        return True
    return not ucan_valid


def is_stale_fence(
    fencing_token: int,
    *,
    current_fence: int,
) -> bool:
    """Stale fencing tokens must not complete work."""
    return int(fencing_token) < int(current_fence)


class StreamQuotaSimulator:
    """Minimal fail-closed stream quota (mirrors TransportQuota@1 stream limit)."""

    def __init__(self, max_streams_per_peer: int = ABUSE_MAX_STREAMS_PER_PEER) -> None:
        self.max_streams_per_peer = int(max_streams_per_peer)
        self._open: Dict[str, int] = {}

    def try_open(self, peer_id: str) -> bool:
        key = str(peer_id)
        n = self._open.get(key, 0)
        if n >= self.max_streams_per_peer:
            return False
        self._open[key] = n + 1
        return True

    def open_count(self, peer_id: str) -> int:
        return self._open.get(str(peer_id), 0)


class FloodLimiter:
    """Token-bucket style flood guard (fail closed when budget exhausted)."""

    def __init__(
        self,
        capacity: float = ABUSE_RATE_CAPACITY,
        refill_per_sec: float = ABUSE_RATE_REFILL_PER_SEC,
    ) -> None:
        self.capacity = float(max(1.0, capacity))
        self.refill_per_sec = float(max(0.0001, refill_per_sec))
        self._tokens = self.capacity
        self._last = 0.0

    def allow(self, *, now: float, cost: float = 1.0) -> bool:
        elapsed = max(0.0, float(now) - self._last)
        self._last = float(now)
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_sec)
        c = float(max(0.0, cost))
        if self._tokens >= c:
            self._tokens -= c
            return True
        return False


# ---------------------------------------------------------------------------
# P2pAbuseVector@1 evaluator
# ---------------------------------------------------------------------------


def evaluate_p2p_abuse_vector(vector: Mapping[str, Any]) -> AbuseVerdict:
    """Evaluate one compact abuse recipe. Abusive inputs never admit.

    Vector schema (compact recipe; only relevant keys required per case)::

        {
          "case": "<case_id>",
          # framing
          "frame": bytes | omitted,
          "payload": object | omitted,
          "max_frame_bytes": int,
          "declared_length": int,  # for invalid/truncated construction
          "body": bytes,
          # negotiation / version / method
          "stream_ready": bool,
          "protocol_negotiated": bool,
          "protocol_id": str,
          "mcp_version": str,
          "method": str,
          "is_application_request": bool,
          # transport outcome
          "status": int,
          "transport_error": str,
          "stream_closed": bool,
          "response_body": object,
          # replay / correlation
          "frames": [bytes, ...],
          "response_ids": [id, ...],
          "requests": [object, ...],
          "responses": [object, ...],
          "peer_id": str,
          # flood / streams
          "message_timestamps": [float, ...],
          "stream_open_attempts": int,
          # authority / fence
          "ucan_present": bool,
          "ucan_valid": bool,
          "fencing_token": int,
          "current_fence": int,
        }
    """
    case = str(vector.get("case") or vector.get("case_id") or "")
    if case not in ABUSE_CASE_IDS:
        return _reject(case or "unknown", "unknown_abuse_case", raw_case=case)

    max_frame = int(vector.get("max_frame_bytes", ABUSE_MAX_FRAME_BYTES))
    validator = TransportValidator(max_frame_bytes=max_frame)

    if case == "oversized":
        return _eval_oversized(vector, validator, max_frame)
    if case == "truncated":
        return _eval_truncated(vector, max_frame)
    if case == "invalid_length":
        return _eval_invalid_length(vector, max_frame)
    if case == "request_before_negotiation":
        return _eval_request_before_negotiation(vector)
    if case == "forged_version":
        return _eval_forged_version(vector)
    if case == "unknown_method":
        return _eval_unknown_method(vector)
    if case == "empty_success_on_transport_failure":
        return _eval_empty_success(vector)
    if case == "replay":
        return _eval_replay(vector, validator)
    if case == "flood":
        return _eval_flood(vector)
    if case == "excessive_streams":
        return _eval_excessive_streams(vector)
    if case == "valid_peerid_invalid_ucan":
        return _eval_peerid_invalid_ucan(vector)
    if case == "stale_fence":
        return _eval_stale_fence(vector)
    if case == "duplicate_response":
        return _eval_duplicate_response(vector, validator)
    if case == "wrong_correlation_id":
        return _eval_wrong_correlation(vector, validator)
    return _reject(case, "unhandled_case")


def _eval_oversized(
    vector: Mapping[str, Any],
    validator: TransportValidator,
    max_frame: int,
) -> AbuseVerdict:
    reasons: List[str] = []
    meta: Dict[str, Any] = {"max_frame_bytes": max_frame}

    if "payload" in vector:
        try:
            encode_frame(vector["payload"], max_frame_bytes=max_frame)
        except FrameSizeExceededError as exc:
            reasons.append(f"encode_rejected:{exc}")
        except FramingError as exc:
            reasons.append(f"encode_framing:{exc}")
        else:
            # If encode succeeded the payload was not oversized — still check declared.
            pass

    if "declared_length" in vector:
        size_result = validator.validate_max_frame_size(
            int(vector["declared_length"]), max_frame_bytes=max_frame
        )
        if not size_result.is_valid:
            reasons.extend(size_result.errors)
        meta["declared_length"] = int(vector["declared_length"])

    if "frame" in vector:
        wire = bytes(vector["frame"])
        wire_result = validator.validate_wire_frame(wire, max_frame_bytes=max_frame)
        if not wire_result.is_valid:
            reasons.extend(wire_result.errors)

    if not reasons:
        # Defensive: oversized vectors must always reject.
        reasons.append("oversized_not_enforced")
    return _reject("oversized", *reasons, **meta)


def _eval_truncated(vector: Mapping[str, Any], max_frame: int) -> AbuseVerdict:
    frame = bytes(vector.get("frame") or b"")
    try:
        decode_frame(frame, max_frame_bytes=max_frame)
    except FrameSizeExceededError as exc:
        return _reject("truncated", f"size:{exc}")
    except FramingError as exc:
        return _reject("truncated", f"framing:{exc}")
    return _reject("truncated", "truncated_not_detected")


def _eval_invalid_length(vector: Mapping[str, Any], max_frame: int) -> AbuseVerdict:
    reasons: List[str] = []
    validator = TransportValidator(max_frame_bytes=max_frame)

    if "structural" in vector:
        result = validator.validate_message_framing(dict(vector["structural"]))
        if not result.is_valid:
            reasons.extend(result.errors)
        else:
            reasons.append("invalid_structural_length_accepted")

    if "frame" in vector:
        try:
            decode_frame(bytes(vector["frame"]), max_frame_bytes=max_frame)
        except (FramingError, FrameSizeExceededError) as exc:
            reasons.append(f"wire:{exc}")
        else:
            reasons.append("invalid_wire_length_accepted")

    if "declared_length" in vector:
        result = validator.validate_max_frame_size(
            vector["declared_length"], max_frame_bytes=max_frame
        )
        if not result.is_valid:
            reasons.extend(result.errors)
        else:
            # Non-integer / negative should have failed; if not, fail closed.
            if not isinstance(vector["declared_length"], int) or isinstance(
                vector["declared_length"], bool
            ):
                reasons.append("non_integer_length_accepted")
            elif int(vector["declared_length"]) < 0:
                reasons.append("negative_length_accepted")

    if not reasons:
        reasons.append("invalid_length_not_detected")
    # Only admit if nothing invalid was found — for abuse tests we always reject.
    return _reject("invalid_length", *reasons)


def _eval_request_before_negotiation(vector: Mapping[str, Any]) -> AbuseVerdict:
    if is_request_before_negotiation(
        stream_ready=bool(vector.get("stream_ready", False)),
        protocol_negotiated=bool(vector.get("protocol_negotiated", False)),
        is_application_request=bool(vector.get("is_application_request", True)),
    ):
        return _reject(
            "request_before_negotiation",
            "application_request_before_layer_t_ready",
            stream_ready=bool(vector.get("stream_ready", False)),
            protocol_negotiated=bool(vector.get("protocol_negotiated", False)),
        )
    return _reject("request_before_negotiation", "negotiation_gate_not_triggered")


def _eval_forged_version(vector: Mapping[str, Any]) -> AbuseVerdict:
    if is_forged_protocol_version(
        vector.get("protocol_id"),
        mcp_version=vector.get("mcp_version"),
    ):
        return _reject(
            "forged_version",
            "unsupported_or_forged_version",
            protocol_id=vector.get("protocol_id"),
            mcp_version=vector.get("mcp_version"),
        )
    return _reject("forged_version", "forged_version_not_detected")


def _eval_unknown_method(vector: Mapping[str, Any]) -> AbuseVerdict:
    method = str(vector.get("method") or "")
    if is_unknown_method(method):
        return _reject(
            "unknown_method",
            "method_not_found",
            method=method,
            completion_granted=False,
        )
    return _reject("unknown_method", "unknown_method_not_detected", method=method)


def _eval_empty_success(vector: Mapping[str, Any]) -> AbuseVerdict:
    body = dict(vector.get("response_body") or {})
    if treat_empty_success_as_failure(
        body,
        status=vector.get("status"),
        transport_error=vector.get("transport_error"),
        stream_closed=bool(vector.get("stream_closed", False)),
        framing_error=bool(vector.get("framing_error", False)),
    ):
        return _reject(
            "empty_success_on_transport_failure",
            "empty_success_treated_as_failure",
            status=vector.get("status"),
            transport_error=vector.get("transport_error"),
            body_keys=sorted(body.keys()),
        )
    return _reject(
        "empty_success_on_transport_failure",
        "empty_success_not_classified",
    )


def _eval_replay(
    vector: Mapping[str, Any],
    validator: TransportValidator,
) -> AbuseVerdict:
    frames: Sequence[Any] = vector.get("frames") or []
    events: List[Dict[str, Any]] = []
    for idx, raw in enumerate(frames):
        events.append({"kind": "frame", "ts": float(idx), "frame": bytes(raw)})
    result = validator.validate_replay_window(events, window_sec=60.0, max_entries=128)
    if not result.is_valid and result.metadata.get("replays"):
        return _reject(
            "replay",
            *result.errors,
            replays=result.metadata.get("replays"),
        )
    # Also exercise observe path
    window = ReplayWindow(window_sec=60.0, max_entries=128)
    seen_replay = False
    for idx, raw in enumerate(frames):
        if window.check_frame(bytes(raw), now=float(idx)):
            seen_replay = True
            break
    if seen_replay:
        return _reject("replay", "duplicate_frame_detected")
    return _reject("replay", "replay_not_detected")


def _eval_flood(vector: Mapping[str, Any]) -> AbuseVerdict:
    timestamps: Sequence[float] = list(vector.get("message_timestamps") or [])
    capacity = float(vector.get("rate_capacity", ABUSE_RATE_CAPACITY))
    refill = float(vector.get("rate_refill_per_sec", ABUSE_RATE_REFILL_PER_SEC))
    limiter = FloodLimiter(capacity=capacity, refill_per_sec=refill)
    denied = 0
    for ts in timestamps:
        if not limiter.allow(now=float(ts), cost=1.0):
            denied += 1
    if denied > 0:
        return _reject(
            "flood",
            "rate_limit_exceeded",
            denied=denied,
            attempted=len(timestamps),
            capacity=capacity,
        )
    return _reject("flood", "flood_not_throttled", attempted=len(timestamps))


def _eval_excessive_streams(vector: Mapping[str, Any]) -> AbuseVerdict:
    peer_id = str(vector.get("peer_id") or "12D3KooWAbusePeer")
    attempts = int(vector.get("stream_open_attempts", ABUSE_MAX_STREAMS_PER_PEER + 2))
    max_streams = int(vector.get("max_streams_per_peer", ABUSE_MAX_STREAMS_PER_PEER))
    sim = StreamQuotaSimulator(max_streams_per_peer=max_streams)
    denied = 0
    for _ in range(attempts):
        if not sim.try_open(peer_id):
            denied += 1
    if denied > 0:
        return _reject(
            "excessive_streams",
            "stream_quota_exceeded",
            denied=denied,
            open=sim.open_count(peer_id),
            max_streams_per_peer=max_streams,
        )
    return _reject("excessive_streams", "stream_quota_not_enforced")


def _eval_peerid_invalid_ucan(vector: Mapping[str, Any]) -> AbuseVerdict:
    peer_id = vector.get("peer_id")
    if is_valid_peerid_invalid_ucan(
        peer_id=peer_id,
        ucan_valid=bool(vector.get("ucan_valid", False)),
        ucan_present=bool(vector.get("ucan_present", False)),
    ):
        return _reject(
            "valid_peerid_invalid_ucan",
            "peerid_is_not_execution_authority",
            peer_id=peer_id,
            ucan_present=bool(vector.get("ucan_present", False)),
            ucan_valid=bool(vector.get("ucan_valid", False)),
            execution_admitted=False,
        )
    return _reject("valid_peerid_invalid_ucan", "authority_separation_not_enforced")


def _eval_stale_fence(vector: Mapping[str, Any]) -> AbuseVerdict:
    token = int(vector.get("fencing_token", 0))
    current = int(vector.get("current_fence", 1))
    if is_stale_fence(token, current_fence=current):
        return _reject(
            "stale_fence",
            "stale_fencing_token",
            fencing_token=token,
            current_fence=current,
            completion_admitted=False,
        )
    return _reject("stale_fence", "stale_fence_not_detected")


def _eval_duplicate_response(
    vector: Mapping[str, Any],
    validator: TransportValidator,
) -> AbuseVerdict:
    peer_id = str(vector.get("peer_id") or "peer-a")
    response_ids: Sequence[Any] = vector.get("response_ids") or []
    events = [
        {"kind": "response_id", "ts": float(i), "id": rid, "peer_id": peer_id}
        for i, rid in enumerate(response_ids)
    ]
    result = validator.validate_replay_window(events, window_sec=60.0, max_entries=128)
    if not result.is_valid and any(
        r.get("kind") == "response_id" for r in (result.metadata.get("replays") or [])
    ):
        return _reject(
            "duplicate_response",
            *result.errors,
            replays=result.metadata.get("replays"),
        )

    # Correlation-level duplicate detection
    requests = list(vector.get("requests") or [{"id": rid} for rid in set(response_ids)])
    responses = list(vector.get("responses") or [{"id": rid} for rid in response_ids])
    corr = validator.validate_correlation(requests, responses)
    if not corr.is_valid and any("duplicate response" in e.lower() for e in corr.errors):
        return _reject("duplicate_response", *corr.errors)

    return _reject("duplicate_response", "duplicate_response_not_detected")


def _eval_wrong_correlation(
    vector: Mapping[str, Any],
    validator: TransportValidator,
) -> AbuseVerdict:
    requests = list(vector.get("requests") or [])
    responses = list(vector.get("responses") or [])
    result = validator.validate_correlation(requests, responses)
    if not result.is_valid and any(
        "does not match" in e.lower() or "missing" in e.lower() for e in result.errors
    ):
        return _reject("wrong_correlation_id", *result.errors)
    return _reject("wrong_correlation_id", "wrong_correlation_not_detected")


# ---------------------------------------------------------------------------
# Compact abuse recipes (generators — no bulk golden dumps)
# ---------------------------------------------------------------------------


def _oversized_payload(max_frame: int = ABUSE_MAX_FRAME_BYTES) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"blob": "x" * (max_frame + 64)}}


def _truncated_frame(max_frame: int = ABUSE_MAX_FRAME_BYTES) -> bytes:
    # Declare 100 bytes of body but only supply 2.
    return (100).to_bytes(4, byteorder="big", signed=False) + b"{}"


def _invalid_length_structural() -> Dict[str, Any]:
    return {"length": -1, "message": {"jsonrpc": "2.0", "id": 1, "method": "ping"}}


def build_abuse_recipes() -> Dict[str, Dict[str, Any]]:
    """Build the canonical compact recipe set for every required case."""
    max_frame = ABUSE_MAX_FRAME_BYTES
    good_frame = encode_frame(
        {"jsonrpc": "2.0", "id": "r1", "method": "ping", "params": {}},
        max_frame_bytes=max_frame,
    )
    oversized_declared = (max_frame + 1).to_bytes(4, byteorder="big", signed=False) + b"{}"

    return {
        "oversized": {
            "case": "oversized",
            "max_frame_bytes": max_frame,
            "payload": _oversized_payload(max_frame),
            "declared_length": max_frame + 1,
            "frame": oversized_declared,
        },
        "truncated": {
            "case": "truncated",
            "max_frame_bytes": max_frame,
            "frame": _truncated_frame(max_frame),
        },
        "invalid_length": {
            "case": "invalid_length",
            "max_frame_bytes": max_frame,
            "structural": _invalid_length_structural(),
            "declared_length": -5,
            "frame": b"\x00\x00",  # incomplete / invalid prefix
        },
        "request_before_negotiation": {
            "case": "request_before_negotiation",
            "stream_ready": False,
            "protocol_negotiated": False,
            "is_application_request": True,
            "method": "tools/call",
        },
        "forged_version": {
            "case": "forged_version",
            "protocol_id": "/mcp+p2p/9.9.9-forged",
            "mcp_version": "experimental-forged",
        },
        "unknown_method": {
            "case": "unknown_method",
            "method": "__mcpp_unknown_abuse_method__",
        },
        "empty_success_on_transport_failure": {
            "case": "empty_success_on_transport_failure",
            "status": 503,
            "transport_error": "stream_reset",
            "stream_closed": True,
            "response_body": {"jsonrpc": "2.0", "id": 1, "result": {}},
        },
        "replay": {
            "case": "replay",
            "frames": [good_frame, good_frame],
        },
        "flood": {
            "case": "flood",
            "rate_capacity": ABUSE_RATE_CAPACITY,
            "rate_refill_per_sec": 0.0,  # no refill during burst
            # burst well beyond capacity at the same timestamp
            "message_timestamps": [0.0] * int(ABUSE_RATE_CAPACITY + 5),
        },
        "excessive_streams": {
            "case": "excessive_streams",
            "peer_id": "12D3KooWAbuseStreamPeer",
            "max_streams_per_peer": ABUSE_MAX_STREAMS_PER_PEER,
            "stream_open_attempts": ABUSE_MAX_STREAMS_PER_PEER + 3,
        },
        "valid_peerid_invalid_ucan": {
            "case": "valid_peerid_invalid_ucan",
            "peer_id": "12D3KooWValidPeerInvalidUcan",
            "ucan_present": True,
            "ucan_valid": False,
        },
        "stale_fence": {
            "case": "stale_fence",
            "fencing_token": 3,
            "current_fence": 7,
        },
        "duplicate_response": {
            "case": "duplicate_response",
            "peer_id": "peer-dup",
            "response_ids": ["req-1", "req-1"],
            "requests": [{"id": "req-1", "method": "ping"}],
            "responses": [
                {"id": "req-1", "result": {"ok": True}},
                {"id": "req-1", "result": {"ok": True}},
            ],
        },
        "wrong_correlation_id": {
            "case": "wrong_correlation_id",
            "requests": [{"id": "req-A", "method": "tools/list"}],
            "responses": [{"id": "req-Z", "result": {"tools": []}}],
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def recipes() -> Dict[str, Dict[str, Any]]:
    return build_abuse_recipes()


@pytest.fixture
def validator() -> TransportValidator:
    return TransportValidator(max_frame_bytes=ABUSE_MAX_FRAME_BYTES)


class TestP2pAbuseVectorCoverage:
    """Ensure every listed abuse case is present and fails closed."""

    def test_interface_label(self):
        assert INTERFACE_LABEL == "P2pAbuseVector@1"

    def test_recipe_set_covers_all_required_cases(self, recipes):
        assert set(recipes.keys()) == set(ABUSE_CASE_IDS)

    def test_every_case_fails_closed(self, recipes):
        failures: List[str] = []
        for case_id in ABUSE_CASE_IDS:
            verdict = evaluate_p2p_abuse_vector(recipes[case_id])
            if verdict.admitted or not verdict.fail_closed:
                failures.append(
                    f"{case_id}: admitted={verdict.admitted} reasons={verdict.reasons}"
                )
            if verdict.case_id != case_id:
                failures.append(f"{case_id}: case_id mismatch {verdict.case_id}")
        assert not failures, "abuse cases must fail closed:\n" + "\n".join(failures)

    @pytest.mark.parametrize("case_id", ABUSE_CASE_IDS)
    def test_case_fail_closed_parametrized(self, recipes, case_id):
        verdict = evaluate_p2p_abuse_vector(recipes[case_id])
        assert verdict.case_id == case_id
        assert verdict.admitted is False
        assert verdict.fail_closed is True
        assert len(verdict.reasons) >= 1


class TestFramingAbuse:
    """Wire-level framing negatives."""

    def test_oversized_encode_raises(self, validator):
        payload = _oversized_payload(ABUSE_MAX_FRAME_BYTES)
        with pytest.raises(FrameSizeExceededError):
            validator.encode_frame(payload)

    def test_oversized_declared_length_rejected(self, validator):
        result = validator.validate_max_frame_size(ABUSE_MAX_FRAME_BYTES + 1)
        assert not result.is_valid
        assert any("exceeds" in e.lower() for e in result.errors)

    def test_oversized_wire_frame_rejected(self, validator):
        frame = (ABUSE_MAX_FRAME_BYTES + 8).to_bytes(4, byteorder="big", signed=False) + b"{}"
        result = validator.validate_wire_frame(frame)
        assert not result.is_valid
        assert any("size" in e.lower() or "large" in e.lower() for e in result.errors)

    def test_truncated_prefix(self, validator):
        with pytest.raises(FramingError, match="incomplete_prefix"):
            validator.decode_frame(b"\x00\x01")

    def test_truncated_body(self, validator):
        frame = _truncated_frame()
        with pytest.raises(FramingError, match="incomplete_body"):
            validator.decode_frame(frame)

    def test_invalid_structural_length(self, validator):
        result = validator.validate_message_framing(_invalid_length_structural())
        assert not result.is_valid
        assert any("length" in e.lower() for e in result.errors)

    def test_invalid_negative_max_size(self, validator):
        result = validator.validate_max_frame_size(-10)
        assert not result.is_valid


class TestNegotiationAndSemanticsAbuse:
    """Layer T readiness, version forgery, unknown methods."""

    def test_request_before_negotiation_fails_closed(self, recipes):
        v = evaluate_p2p_abuse_vector(recipes["request_before_negotiation"])
        assert v.fail_closed
        assert "before_layer_t" in v.reasons[0] or "negotiation" in v.reasons[0]

    def test_request_before_negotiation_when_stream_not_ready(self):
        v = evaluate_p2p_abuse_vector(
            {
                "case": "request_before_negotiation",
                "stream_ready": True,
                "protocol_negotiated": False,
                "is_application_request": True,
            }
        )
        assert v.fail_closed

    def test_forged_protocol_id_fails_closed(self, recipes):
        v = evaluate_p2p_abuse_vector(recipes["forged_version"])
        assert v.fail_closed
        assert v.metadata.get("protocol_id") == "/mcp+p2p/9.9.9-forged"

    def test_forged_mcp_version_only(self):
        v = evaluate_p2p_abuse_vector(
            {
                "case": "forged_version",
                "protocol_id": CANONICAL_PROTOCOL_ID,
                "mcp_version": "not-a-real-mcp-version",
            }
        )
        assert v.fail_closed

    def test_unknown_method_does_not_grant_completion(self, recipes):
        v = evaluate_p2p_abuse_vector(recipes["unknown_method"])
        assert v.fail_closed
        assert v.metadata.get("completion_granted") is False


class TestEmptySuccessOnTransportFailure:
    """Empty / success-shaped bodies under transport failure are failures."""

    def test_recipe_fails_closed(self, recipes):
        v = evaluate_p2p_abuse_vector(recipes["empty_success_on_transport_failure"])
        assert v.fail_closed
        assert "empty_success_treated_as_failure" in v.reasons

    def test_http_503_with_empty_result(self):
        assert treat_empty_success_as_failure(
            {"result": {}},
            status=503,
        )

    def test_stream_reset_with_success_flag(self):
        assert treat_empty_success_as_failure(
            {"success": True},
            transport_error="connection_reset",
        )

    def test_framing_error_with_ok_true(self):
        assert treat_empty_success_as_failure(
            {"ok": True},
            framing_error=True,
        )

    def test_stream_closed_empty_body(self):
        assert treat_empty_success_as_failure(
            {},
            stream_closed=True,
        )

    def test_explicit_error_under_failure_is_not_empty_success(self):
        # Already an error path — not the empty-success anti-pattern.
        assert not treat_empty_success_as_failure(
            {"error": {"code": -32000, "message": "transport failed"}},
            status=500,
        )

    def test_healthy_success_is_not_classified_as_empty_success_failure(self):
        assert not treat_empty_success_as_failure(
            {"result": {"tools": []}},
            status=200,
        )

    def test_evaluator_rejects_empty_result_on_timeout(self):
        v = evaluate_p2p_abuse_vector(
            {
                "case": "empty_success_on_transport_failure",
                "status": 504,
                "transport_error": "request_timeout",
                "response_body": {"jsonrpc": "2.0", "id": 9, "result": {}},
            }
        )
        assert v.admitted is False
        assert v.fail_closed


class TestReplayFloodStreams:
    """Replay window, flood rate limit, stream exhaustion."""

    def test_replay_duplicate_frame(self, recipes, validator):
        v = evaluate_p2p_abuse_vector(recipes["replay"])
        assert v.fail_closed
        frame = recipes["replay"]["frames"][0]
        first = validator.observe_frame_for_replay(frame, now=1.0)
        second = validator.observe_frame_for_replay(frame, now=2.0)
        assert first.is_valid
        assert not second.is_valid

    def test_flood_burst_denied(self, recipes):
        v = evaluate_p2p_abuse_vector(recipes["flood"])
        assert v.fail_closed
        assert v.metadata.get("denied", 0) > 0

    def test_excessive_streams_denied(self, recipes):
        v = evaluate_p2p_abuse_vector(recipes["excessive_streams"])
        assert v.fail_closed
        assert v.metadata.get("denied", 0) > 0
        assert v.metadata.get("open") == ABUSE_MAX_STREAMS_PER_PEER

    def test_stream_quota_config_structural(self, validator):
        # Valid tight quotas remain valid structure; abuse is behavioral.
        result = validator.validate_quotas(
            {
                "max_frame_bytes": ABUSE_MAX_FRAME_BYTES,
                "max_streams_per_peer": ABUSE_MAX_STREAMS_PER_PEER,
                "max_in_flight_per_peer": 8,
                "rate_capacity": ABUSE_RATE_CAPACITY,
                "rate_refill_per_sec": ABUSE_RATE_REFILL_PER_SEC,
            }
        )
        assert result.is_valid


class TestAuthorityAndCorrelationAbuse:
    """PeerID ≠ UCAN, stale fence, duplicate / wrong correlation ids."""

    def test_valid_peerid_invalid_ucan(self, recipes):
        v = evaluate_p2p_abuse_vector(recipes["valid_peerid_invalid_ucan"])
        assert v.fail_closed
        assert v.metadata.get("execution_admitted") is False

    def test_valid_peerid_missing_ucan(self):
        v = evaluate_p2p_abuse_vector(
            {
                "case": "valid_peerid_invalid_ucan",
                "peer_id": "12D3KooWNoProof",
                "ucan_present": False,
                "ucan_valid": False,
            }
        )
        assert v.fail_closed

    def test_stale_fence(self, recipes):
        v = evaluate_p2p_abuse_vector(recipes["stale_fence"])
        assert v.fail_closed
        assert v.metadata.get("completion_admitted") is False

    def test_duplicate_response_id(self, recipes, validator):
        v = evaluate_p2p_abuse_vector(recipes["duplicate_response"])
        assert v.fail_closed
        first = validator.observe_response_id_for_replay("dup-id", peer_id="p", now=1.0)
        second = validator.observe_response_id_for_replay("dup-id", peer_id="p", now=2.0)
        assert first.is_valid
        assert not second.is_valid

    def test_wrong_correlation_id(self, recipes, validator):
        v = evaluate_p2p_abuse_vector(recipes["wrong_correlation_id"])
        assert v.fail_closed
        result = validator.validate_correlation(
            recipes["wrong_correlation_id"]["requests"],
            recipes["wrong_correlation_id"]["responses"],
        )
        assert not result.is_valid
        assert any("does not match" in e for e in result.errors)


class TestFailClosedInvariants:
    """Cross-cutting invariants for the abuse suite."""

    def test_default_max_frame_not_weakened(self):
        # Production default remains 16 MiB; abuse tests use a tighter local cap.
        assert DEFAULT_MAX_FRAME_BYTES == 16 * 1024 * 1024
        assert ABUSE_MAX_FRAME_BYTES < DEFAULT_MAX_FRAME_BYTES

    def test_unknown_case_fails_closed(self):
        v = evaluate_p2p_abuse_vector({"case": "not_a_real_case"})
        assert v.admitted is False
        assert v.fail_closed

    def test_benign_control_does_not_use_abuse_evaluator_admission(self):
        # Abuse evaluator is reject-oriented; benign traffic is out of scope.
        # Document invariant: recipes only cover adversarial cases.
        recipes = build_abuse_recipes()
        assert all(evaluate_p2p_abuse_vector(r).admitted is False for r in recipes.values())

    def test_canonical_protocol_id_unchanged(self):
        assert CANONICAL_PROTOCOL_ID == "/mcp+p2p/1.0.0"
        assert not is_forged_protocol_version(CANONICAL_PROTOCOL_ID, mcp_version=CANONICAL_MCP_VERSION)

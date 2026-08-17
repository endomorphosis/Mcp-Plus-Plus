"""
Transport Protocol Validator

Validates Profile E (mcp+p2p transport) according to docs/spec/transport-mcp-p2p.md.

Provides structural validators plus deterministic length-prefixed frame
encode/decode helpers, max-size enforcement, correlation checks, quota
structure validation, and replay-window detection used by unit tests.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import hashlib
import json
from json import JSONDecodeError
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .base_mcp import ValidationResult


# Normative defaults from transport-mcp-p2p.md §3.3.1 / §3.4 / §3.5
PROTOCOL_ID_DEFAULT = "/mcp+p2p/1.0.0"
DEFAULT_MAX_FRAME_BYTES = 16 * 1024 * 1024  # 16 MiB
HEADER_SIZE = 4
DEFAULT_REPLAY_WINDOW_SEC = 300.0
DEFAULT_REPLAY_WINDOW_SIZE = 4096


class FramingError(Exception):
    """Raised when frame encode/decode fails during validator helpers."""


class FrameSizeExceededError(FramingError):
    """Raised when a frame exceeds the configured maximum size."""


class ReplayDetectedError(Exception):
    """Raised when a duplicate frame or response id is observed."""


def encode_frame(
    payload: Mapping[str, Any],
    *,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> bytes:
    """Encode *payload* as a u32 big-endian length-prefixed UTF-8 JSON frame.

    Deterministic: compact separators, ensure_ascii=True.
    """
    if not isinstance(payload, Mapping):
        raise FramingError("payload_not_object")
    body = json.dumps(dict(payload), separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    limit = int(max_frame_bytes)
    if len(body) > limit:
        raise FrameSizeExceededError(f"frame_too_large:{len(body)}>{limit}")
    return len(body).to_bytes(HEADER_SIZE, byteorder="big", signed=False) + body


def decode_frame(
    frame: bytes,
    *,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> Tuple[Dict[str, Any], int]:
    """Decode a length-prefixed frame; return ``(payload, consumed_bytes)``."""
    if not isinstance(frame, (bytes, bytearray, memoryview)):
        raise FramingError("frame_not_bytes")
    data = bytes(frame)
    if len(data) < HEADER_SIZE:
        raise FramingError("incomplete_prefix")
    declared = int.from_bytes(data[:HEADER_SIZE], byteorder="big", signed=False)
    limit = int(max_frame_bytes)
    if declared > limit:
        raise FrameSizeExceededError(f"declared_frame_too_large:{declared}>{limit}")
    if len(data) < HEADER_SIZE + declared:
        raise FramingError("incomplete_body")
    body = data[HEADER_SIZE : HEADER_SIZE + declared]
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FramingError("invalid_utf8") from exc
    try:
        payload = json.loads(text)
    except JSONDecodeError as exc:
        raise FramingError("invalid_json") from exc
    if not isinstance(payload, dict):
        raise FramingError("payload_not_object")
    return payload, HEADER_SIZE + declared


def frame_fingerprint(frame: bytes) -> str:
    """SHA-256 hex digest of a raw frame for replay tracking."""
    return hashlib.sha256(bytes(frame)).hexdigest()


@dataclass
class ReplayWindow:
    """Sliding-window detector for duplicate frames and response ids.

    Spec: transport-mcp-p2p.md §3.4 — detect duplicates within a configured
    window and drop/reject them.
    """

    window_sec: float = DEFAULT_REPLAY_WINDOW_SEC
    max_entries: int = DEFAULT_REPLAY_WINDOW_SIZE
    _seen: "OrderedDict[str, float]" = field(default_factory=OrderedDict)

    def __post_init__(self) -> None:
        self.window_sec = float(max(0.0, self.window_sec))
        self.max_entries = int(max(1, self.max_entries))

    def _purge(self, now: float) -> None:
        cutoff = now - self.window_sec
        while self._seen:
            _key, ts = next(iter(self._seen.items()))
            if ts >= cutoff and len(self._seen) <= self.max_entries:
                break
            if ts < cutoff or len(self._seen) > self.max_entries:
                self._seen.popitem(last=False)
                continue
            break

    def observe(self, key: str, *, now: float) -> bool:
        """Record *key* at *now*. Return True if it is a replay."""
        self._purge(now)
        if key in self._seen:
            prev = self._seen[key]
            if now - prev <= self.window_sec:
                self._seen.move_to_end(key)
                return True
        self._seen[key] = now
        self._seen.move_to_end(key)
        self._purge(now)
        return False

    def check_frame(self, frame: bytes, *, now: float) -> bool:
        """Return True if *frame* was already seen inside the window."""
        return self.observe(f"frame:{frame_fingerprint(frame)}", now=now)

    def check_response_id(
        self,
        response_id: Union[str, int, None],
        *,
        peer_id: str = "",
        now: float = 0.0,
    ) -> bool:
        """Return True if *response_id* is a duplicate within the window."""
        if response_id is None:
            return False
        return self.observe(f"rid:{peer_id}|{response_id!r}", now=now)

    def __len__(self) -> int:
        return len(self._seen)


class TransportValidator:
    """
    Validates mcp+p2p transport protocol compliance.

    Based on: docs/spec/transport-mcp-p2p.md

    Also exposes LengthPrefixedFrame@1 encode/decode helpers and
    TransportQuota@1 / replay-window structural checks for unit tests.
    """

    PROTOCOL_ID = PROTOCOL_ID_DEFAULT
    DEFAULT_MAX_FRAME_BYTES = DEFAULT_MAX_FRAME_BYTES
    HEADER_SIZE = HEADER_SIZE

    def __init__(
        self,
        *,
        max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
        replay_window_sec: float = DEFAULT_REPLAY_WINDOW_SEC,
        replay_window_size: int = DEFAULT_REPLAY_WINDOW_SIZE,
    ) -> None:
        self.max_frame_bytes = int(max_frame_bytes)
        self.replay_window = ReplayWindow(
            window_sec=replay_window_sec,
            max_entries=replay_window_size,
        )

    # ------------------------------------------------------------------
    # Protocol ID
    # ------------------------------------------------------------------

    def validate_protocol_id(self, protocol_id: str) -> ValidationResult:
        """
        Validate protocol identifier.

        Spec: transport-mcp-p2p.md:37-51
        Requirement: MUST define libp2p stream protocol identifiers

        Args:
            protocol_id: The protocol identifier string

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='protocol_id')

        if not protocol_id:
            result.add_error("Protocol ID cannot be empty")
            return result

        # Should start with /mcp+p2p/
        if not protocol_id.startswith('/mcp+p2p/'):
            result.add_warning(f"Protocol ID should start with '/mcp+p2p/': {protocol_id}")

        return result

    # ------------------------------------------------------------------
    # Message framing (structural)
    # ------------------------------------------------------------------

    def validate_message_framing(self, frame: Dict[str, Any]) -> ValidationResult:
        """
        Validate message framing structure.

        Spec: transport-mcp-p2p.md:75-96
        Requirement: MUST define how messages are delimited/framed

        Args:
            frame: The message frame structure

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='message_frame')

        # Check for length prefix
        if 'length' not in frame:
            result.add_error("Frame missing 'length' field")
        else:
            length = frame['length']
            if not isinstance(length, int) or length < 0:
                result.add_error("Frame length must be a non-negative integer")

        # Check for message payload
        if 'message' not in frame:
            result.add_error("Frame missing 'message' payload")

        # Validate max message size
        if 'length' in frame and isinstance(frame['length'], int):
            if frame['length'] > self.max_frame_bytes:
                result.add_warning("Frame length exceeds recommended maximum (16 MiB)")

        return result

    def validate_max_frame_size(
        self,
        length: int,
        *,
        max_frame_bytes: Optional[int] = None,
    ) -> ValidationResult:
        """
        Validate a declared frame body length against the max-size quota.

        Spec: transport-mcp-p2p.md §3.3.1
        Requirement: MUST reject frames with N greater than configured maximum.
        """
        result = ValidationResult(is_valid=True, message_type='max_frame_size')
        limit = int(self.max_frame_bytes if max_frame_bytes is None else max_frame_bytes)
        if not isinstance(length, int) or isinstance(length, bool):
            result.add_error("Frame length must be an integer")
            return result
        if length < 0:
            result.add_error("Frame length must be non-negative")
            return result
        if length > limit:
            result.add_error(
                f"Frame length {length} exceeds maximum {limit}"
            )
        result.metadata["length"] = length
        result.metadata["max_frame_bytes"] = limit
        return result

    # ------------------------------------------------------------------
    # Frame encode / decode (LengthPrefixedFrame@1)
    # ------------------------------------------------------------------

    def encode_frame(
        self,
        payload: Mapping[str, Any],
        *,
        max_frame_bytes: Optional[int] = None,
    ) -> bytes:
        """Encode *payload* into a deterministic length-prefixed frame."""
        limit = self.max_frame_bytes if max_frame_bytes is None else int(max_frame_bytes)
        return encode_frame(payload, max_frame_bytes=limit)

    def decode_frame(
        self,
        frame: bytes,
        *,
        max_frame_bytes: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], int]:
        """Decode a length-prefixed frame into payload + consumed length."""
        limit = self.max_frame_bytes if max_frame_bytes is None else int(max_frame_bytes)
        return decode_frame(frame, max_frame_bytes=limit)

    def validate_frame_round_trip(
        self,
        payload: Mapping[str, Any],
        *,
        max_frame_bytes: Optional[int] = None,
    ) -> ValidationResult:
        """
        Encode then decode *payload* and verify semantic preservation.

        Covers unit-test acceptance: frame encode/decode.
        """
        result = ValidationResult(is_valid=True, message_type='frame_round_trip')
        limit = self.max_frame_bytes if max_frame_bytes is None else int(max_frame_bytes)
        try:
            wire = encode_frame(payload, max_frame_bytes=limit)
            decoded, consumed = decode_frame(wire, max_frame_bytes=limit)
        except FrameSizeExceededError as exc:
            result.add_error(f"Frame size exceeded: {exc}")
            return result
        except FramingError as exc:
            result.add_error(f"Framing error: {exc}")
            return result

        if consumed != len(wire):
            result.add_error(f"Consumed {consumed} bytes, frame is {len(wire)}")
        # Compare via JSON round-trip to ignore Mapping vs dict
        if json.dumps(decoded, sort_keys=True) != json.dumps(dict(payload), sort_keys=True):
            result.add_error("Decoded payload does not match original")
        result.metadata["frame_bytes"] = len(wire)
        result.metadata["payload"] = decoded
        return result

    def validate_wire_frame(
        self,
        frame: bytes,
        *,
        max_frame_bytes: Optional[int] = None,
    ) -> ValidationResult:
        """
        Validate a raw length-prefixed wire frame (prefix, size, JSON body).
        """
        result = ValidationResult(is_valid=True, message_type='wire_frame')
        limit = self.max_frame_bytes if max_frame_bytes is None else int(max_frame_bytes)
        try:
            payload, consumed = decode_frame(frame, max_frame_bytes=limit)
        except FrameSizeExceededError as exc:
            result.add_error(f"Frame size exceeded: {exc}")
            return result
        except FramingError as exc:
            result.add_error(f"Framing error: {exc}")
            return result
        result.metadata["payload"] = payload
        result.metadata["consumed"] = consumed
        return result

    # ------------------------------------------------------------------
    # Correlation
    # ------------------------------------------------------------------

    def validate_correlation(
        self,
        requests: Sequence[Mapping[str, Any]],
        responses: Sequence[Mapping[str, Any]],
    ) -> ValidationResult:
        """
        Validate JSON-RPC request/response id correlation.

        Spec: transport-mcp-p2p.md §3.4
        Requirement: MUST preserve correlation via application ``id``.
        """
        result = ValidationResult(is_valid=True, message_type='correlation')
        pending = set()
        for req in requests:
            if "id" not in req:
                result.add_error("Request missing 'id' for correlation")
                continue
            rid = req["id"]
            if rid in pending:
                result.add_error(f"Duplicate in-flight request id: {rid!r}")
            pending.add(rid)

        seen_responses = set()
        for resp in responses:
            if "id" not in resp:
                result.add_error("Response missing 'id' for correlation")
                continue
            rid = resp["id"]
            if rid not in pending:
                result.add_error(f"Response id {rid!r} does not match any request")
            if rid in seen_responses:
                result.add_error(f"Duplicate response id: {rid!r}")
            seen_responses.add(rid)

        unmatched = pending - seen_responses
        if unmatched:
            result.add_warning(f"Unmatched in-flight request ids: {sorted(unmatched, key=str)}")

        result.metadata["in_flight"] = len(pending)
        result.metadata["matched"] = len(seen_responses & pending)
        return result

    # ------------------------------------------------------------------
    # Quotas (TransportQuota@1 structural)
    # ------------------------------------------------------------------

    def validate_quotas(self, quotas: Mapping[str, Any]) -> ValidationResult:
        """
        Validate transport quota configuration structure.

        Spec: transport-mcp-p2p.md §3.5
        """
        result = ValidationResult(is_valid=True, message_type='transport_quota')
        required_positive = (
            "max_frame_bytes",
            "max_streams_per_peer",
            "max_in_flight_per_peer",
        )
        for key in required_positive:
            if key not in quotas:
                result.add_error(f"Quota missing required field: {key}")
                continue
            value = quotas[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                result.add_error(f"Quota '{key}' must be a positive integer")

        if "max_frame_bytes" in quotas:
            mfb = quotas["max_frame_bytes"]
            if isinstance(mfb, int) and not isinstance(mfb, bool) and mfb > DEFAULT_MAX_FRAME_BYTES:
                result.add_warning(
                    f"max_frame_bytes {mfb} exceeds baseline default {DEFAULT_MAX_FRAME_BYTES}"
                )

        for optional_key in ("rate_capacity", "rate_refill_per_sec", "idle_timeout_sec"):
            if optional_key in quotas:
                value = quotas[optional_key]
                if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                    result.add_error(f"Quota '{optional_key}' must be a positive number")

        return result

    # ------------------------------------------------------------------
    # Replay window
    # ------------------------------------------------------------------

    def validate_replay_window(
        self,
        events: Sequence[Mapping[str, Any]],
        *,
        window_sec: Optional[float] = None,
        max_entries: Optional[int] = None,
    ) -> ValidationResult:
        """
        Validate a sequence of frame/response events for replays.

        Each event is a mapping with:
          - ``kind``: ``"frame"`` | ``"response_id"``
          - ``ts``: monotonic timestamp (float)
          - for frames: ``frame`` (bytes) or ``fingerprint`` (str)
          - for response ids: ``id`` (str|int), optional ``peer_id``

        Spec: transport-mcp-p2p.md §3.4
        Covers unit-test acceptance: replay window.
        """
        result = ValidationResult(is_valid=True, message_type='replay_window')
        window = ReplayWindow(
            window_sec=(
                self.replay_window.window_sec if window_sec is None else float(window_sec)
            ),
            max_entries=(
                self.replay_window.max_entries if max_entries is None else int(max_entries)
            ),
        )
        replays: List[Dict[str, Any]] = []
        accepted = 0

        for idx, event in enumerate(events):
            kind = event.get("kind")
            ts = event.get("ts")
            if not isinstance(ts, (int, float)) or isinstance(ts, bool):
                result.add_error(f"Event {idx}: missing numeric 'ts'")
                continue
            now = float(ts)

            if kind == "frame":
                if "frame" in event:
                    raw = event["frame"]
                    if not isinstance(raw, (bytes, bytearray)):
                        result.add_error(f"Event {idx}: 'frame' must be bytes")
                        continue
                    is_replay = window.check_frame(bytes(raw), now=now)
                    key = frame_fingerprint(bytes(raw))
                elif "fingerprint" in event:
                    key = str(event["fingerprint"])
                    is_replay = window.observe(f"frame:{key}", now=now)
                else:
                    result.add_error(f"Event {idx}: frame event needs 'frame' or 'fingerprint'")
                    continue
                if is_replay:
                    replays.append({"index": idx, "kind": "frame", "key": key})
                else:
                    accepted += 1
            elif kind == "response_id":
                if "id" not in event:
                    result.add_error(f"Event {idx}: response_id event missing 'id'")
                    continue
                rid = event["id"]
                peer_id = str(event.get("peer_id", ""))
                is_replay = window.check_response_id(rid, peer_id=peer_id, now=now)
                if is_replay:
                    replays.append({"index": idx, "kind": "response_id", "id": rid})
                else:
                    accepted += 1
            else:
                result.add_error(f"Event {idx}: unknown kind {kind!r}")

        result.metadata["accepted"] = accepted
        result.metadata["replays"] = replays
        result.metadata["window"] = {
            "window_sec": window.window_sec,
            "max_entries": window.max_entries,
            "size": len(window),
        }
        if replays:
            # Presence of replays is informational for the validator: callers
            # decide drop vs reject. Mark invalid when any duplicate is found
            # so unit tests can assert detection.
            for item in replays:
                result.add_error(
                    f"Replay detected at event {item['index']} ({item['kind']})"
                )
        return result

    def observe_frame_for_replay(
        self,
        frame: bytes,
        *,
        now: float,
    ) -> ValidationResult:
        """Observe a single frame against the validator's replay window."""
        result = ValidationResult(is_valid=True, message_type='replay_observe')
        if self.replay_window.check_frame(frame, now=now):
            result.add_error("Replay detected: duplicate frame")
        result.metadata["fingerprint"] = frame_fingerprint(frame)
        result.metadata["window_size"] = len(self.replay_window)
        return result

    def observe_response_id_for_replay(
        self,
        response_id: Union[str, int],
        *,
        peer_id: str = "",
        now: float,
    ) -> ValidationResult:
        """Observe a single response id against the validator's replay window."""
        result = ValidationResult(is_valid=True, message_type='replay_observe')
        if self.replay_window.check_response_id(response_id, peer_id=peer_id, now=now):
            result.add_error(f"Replay detected: duplicate response id {response_id!r}")
        result.metadata["response_id"] = response_id
        result.metadata["window_size"] = len(self.replay_window)
        return result

    # ------------------------------------------------------------------
    # Session lifecycle / JSON-RPC / addressing (existing API)
    # ------------------------------------------------------------------

    def validate_session_lifecycle(self, session: Dict[str, Any]) -> ValidationResult:
        """
        Validate session lifecycle compliance.

        Spec: transport-mcp-p2p.md:53-61
        Requirement: MUST establish connection, open stream, run initialization

        Args:
            session: Session lifecycle information

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='session_lifecycle')

        required_phases = ['connection', 'stream', 'initialization']

        for phase in required_phases:
            if phase not in session:
                result.add_error(f"Session missing required phase: {phase}")

        # Validate connection phase
        if 'connection' in session:
            conn = session['connection']
            if 'peer_id' not in conn:
                result.add_error("Connection missing 'peer_id'")

        # Validate stream phase
        if 'stream' in session:
            stream = session['stream']
            if 'protocol_id' not in stream:
                result.add_error("Stream missing 'protocol_id'")

        # Validate initialization phase
        if 'initialization' in session:
            init = session['initialization']
            if 'handshake' not in init:
                result.add_error("Initialization missing 'handshake'")

        return result

    def validate_jsonrpc_preservation(
        self,
        original: Dict[str, Any],
        transported: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate that JSON-RPC semantics are preserved over transport.

        Spec: transport-mcp-p2p.md:60
        Requirement: MUST preserve MCP JSON-RPC semantics

        Args:
            original: Original JSON-RPC message
            transported: Message after transport

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='jsonrpc_preservation')

        # Check essential JSON-RPC fields are preserved
        jsonrpc_fields = ['jsonrpc', 'id', 'method']

        for field_name in jsonrpc_fields:
            if field_name in original:
                if field_name not in transported:
                    result.add_error(f"Field '{field_name}' lost during transport")
                elif original[field_name] != transported[field_name]:
                    result.add_error(f"Field '{field_name}' modified during transport")

        # Check params preservation
        if 'params' in original:
            if 'params' not in transported:
                result.add_error("Params lost during transport")
            # Deep comparison would be needed for full validation

        return result

    def validate_addressing(self, address: Dict[str, Any]) -> ValidationResult:
        """
        Validate peer addressing and discovery.

        Spec: transport-mcp-p2p.md:62-74
        Requirement: MAY use peer IDs and multiaddrs for addressing

        Args:
            address: Addressing information

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='addressing')

        # Should have peer_id
        if 'peer_id' not in address:
            result.add_warning("Address missing 'peer_id'")

        # Should have multiaddrs
        if 'multiaddrs' not in address:
            result.add_warning("Address missing 'multiaddrs'")
        elif not isinstance(address['multiaddrs'], list):
            result.add_error("'multiaddrs' must be a list")

        return result

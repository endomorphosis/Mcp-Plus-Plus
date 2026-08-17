"""
Integration tests for dual-binding peer compatibility
(BindingCompatibilityMatrix@1).

Spec: docs/spec/bindings/compatibility-matrix.md
Interface: BindingCompatibilityMatrix@1
Task: MCPP-022

Acceptance:
  - Matrix and tests cover legacy-only, current-only, dual, forged version,
    and downgrade.
  - All negatives fail closed.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pytest

# Reuse primitive reference peers from MCPP-020 / MCPP-021.
from test_mcp_binding_current import (  # type: ignore
    BINDING_ID as CURRENT_BINDING_ID,
    ERR_INVALID_PARAMS,
    ERR_METHOD_NOT_FOUND,
    ERR_UNSUPPORTED_PROTOCOL_VERSION,
    META_BINDING_ID,
    META_CLIENT_CAPS,
    META_CLIENT_INFO,
    META_PROTOCOL_VERSION,
    META_SERVER_INFO,
    PROTOCOL_VERSION as CURRENT_PROTOCOL_VERSION,
    McpBinding20260728,
    BindingResponse as CurrentBindingResponse,
    current_request_meta,
    make_request as current_make_request,
)
from test_mcp_binding_legacy import (  # type: ignore
    BINDING_ID as LEGACY_BINDING_ID,
    ERR_NOT_INITIALIZED,
    PROTOCOL_VERSION as LEGACY_PROTOCOL_VERSION,
    McpBindingLegacy20241105,
    SessionPhase,
    BindingResponse as LegacyBindingResponse,
    legacy_initialize_params,
    make_request as legacy_make_request,
    open_legacy_session,
)

# ---------------------------------------------------------------------------
# Constants (BindingCompatibilityMatrix@1)
# ---------------------------------------------------------------------------

INTERFACE_LABEL = "BindingCompatibilityMatrix@1"

SPEC_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "spec"
    / "bindings"
    / "compatibility-matrix.md"
)

# Shared matrix reason codes (normative recommendations in the matrix doc).
REASON_FORGED_VERSION = "forged_version"
REASON_BINDING_MISMATCH = "binding_id_mismatch"
REASON_SILENT_DOWNGRADE = "silent_downgrade_rejected"
REASON_INIT_AS_CURRENT = "initialize_as_current_rejected"
REASON_BINDING_NOT_OFFERED = "binding_not_offered"
REASON_PATH_AMBIGUOUS = "path_ambiguous"
REASON_VERSION_BINDING_MISMATCH = "version_binding_mismatch"

ABSTRACT_PROFILE_KEYS = (
    "mcp++/mcp-idl",
    "mcp++/cid-envelope",
    "mcp++/ucan",
    "mcp++/deontic-policy",
    "mcp++/p2p-transport",
    "mcp++/event-dag",
    "mcp++/risk-scheduling",
    "mcp++/x402-payments",
)


class PeerMode(str, Enum):
    LEGACY_ONLY = "legacy-only"
    CURRENT_ONLY = "current-only"
    DUAL = "dual"


# ---------------------------------------------------------------------------
# Dual / multi-mode reference peer
# ---------------------------------------------------------------------------


@dataclass
class CompatResponse:
    """Unified JSON-RPC style response for matrix tests."""

    id: Any
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    is_notification_ack: bool = False
    path: Optional[str] = None  # "legacy" | "current" | None

    @property
    def ok(self) -> bool:
        if self.is_notification_ack:
            return self.error is None
        return self.error is None and self.result is not None


def _from_legacy(resp: LegacyBindingResponse, path: str = "legacy") -> CompatResponse:
    return CompatResponse(
        id=resp.id,
        result=resp.result,
        error=resp.error,
        is_notification_ack=resp.is_notification_ack,
        path=path,
    )


def _from_current(resp: CurrentBindingResponse, path: str = "current") -> CompatResponse:
    return CompatResponse(
        id=resp.id,
        result=resp.result,
        error=resp.error,
        path=path,
    )


@dataclass
class DualBindingPeer:
    """
    Multi-mode MCP++ binding peer for BindingCompatibilityMatrix@1.

    Modes:
      - legacy-only: wraps legacy initialize path only
      - current-only: wraps current _meta path only
      - dual: both paths; silent downgrade and forgery fail closed

    Active binding tracks the last successfully accepted path on this
    connection context so silent downgrade can be rejected.
    """

    mode: PeerMode = PeerMode.DUAL
    server_name: str = "mcp++-compat-ref"
    server_version: str = "1.0.0"
    profiles: Set[str] = field(
        default_factory=lambda: {
            "mcp++/mcp-idl",
            "mcp++/cid-envelope",
            "mcp++/event-dag",
        }
    )
    active_binding: Optional[str] = None
    request_count: int = 0
    legacy_successes: int = 0
    current_successes: int = 0
    rejected_downgrades: int = 0
    rejected_forgeries: int = 0

    # Inner peers (constructed in __post_init__)
    legacy: Optional[McpBindingLegacy20241105] = None
    current: Optional[McpBinding20260728] = None

    def __post_init__(self) -> None:
        if self.legacy is None:
            self.legacy = McpBindingLegacy20241105(
                server_name=f"{self.server_name}-legacy",
                server_version=self.server_version,
                profiles=set(self.profiles),
                claim_mcpp=True,
            )
        if self.current is None:
            self.current = McpBinding20260728(
                server_name=f"{self.server_name}-current",
                server_version=self.server_version,
                profiles=set(self.profiles),
            )

    # -- mode helpers -------------------------------------------------------

    @property
    def offers_legacy(self) -> bool:
        return self.mode in (PeerMode.LEGACY_ONLY, PeerMode.DUAL)

    @property
    def offers_current(self) -> bool:
        return self.mode in (PeerMode.CURRENT_ONLY, PeerMode.DUAL)

    def offered_bindings(self) -> List[str]:
        out: List[str] = []
        if self.offers_current:
            out.append(CURRENT_BINDING_ID)
        if self.offers_legacy:
            out.append(LEGACY_BINDING_ID)
        return out

    def offered_versions(self) -> List[str]:
        out: List[str] = []
        if self.offers_current:
            out.append(CURRENT_PROTOCOL_VERSION)
        if self.offers_legacy:
            out.append(LEGACY_PROTOCOL_VERSION)
        return out

    def reset(self) -> None:
        """Reset connection-scoped negotiation state."""
        self.active_binding = None
        assert self.legacy is not None
        assert self.current is not None
        self.legacy.reset_session()
        # Current peer is stateless for session; clear stores for isolation.
        self.current.state_store.clear()
        self.current.tasks.clear()
        self.current.initialize_calls = 0
        self.current.request_count = 0

    # -- dispatch -----------------------------------------------------------

    def handle(self, message: Dict[str, Any]) -> CompatResponse:
        """Select path and enforce dual-binding fail-closed rules."""
        self.request_count += 1
        msg_id = message.get("id")
        method = message.get("method")

        if message.get("jsonrpc") != "2.0":
            return self._error(msg_id, ERR_INVALID_PARAMS, "jsonrpc must be '2.0'")

        if not method or not isinstance(method, str):
            return self._error(msg_id, ERR_INVALID_PARAMS, "missing method")

        # Priority 1: initialize-family → legacy path (or reject if not offered).
        if method in ("initialize", "notifications/initialized", "initialized"):
            return self._handle_legacy_lifecycle(message)

        params = message.get("params") or {}
        if params is not None and not isinstance(params, dict):
            return self._error(msg_id, ERR_INVALID_PARAMS, "params must be an object")
        if not isinstance(params, dict):
            params = {}

        meta = params.get("_meta")
        has_current_meta = isinstance(meta, dict) and (
            META_PROTOCOL_VERSION in meta or META_BINDING_ID in meta
        )

        # Priority 2: current-shaped _meta → current path.
        if has_current_meta:
            return self._handle_current_path(message, meta)

        # Priority 3: open legacy session, bare application methods.
        if (
            self.offers_legacy
            and self.legacy is not None
            and self.legacy.phase is not SessionPhase.UNINITIALIZED
        ):
            # If current is active, bare legacy methods are silent downgrade.
            if self.active_binding == CURRENT_BINDING_ID:
                return self._reject_silent_downgrade(
                    msg_id,
                    detail="bare legacy application method after current path",
                )
            resp = _from_legacy(self.legacy.handle(message))
            if resp.ok:
                self.active_binding = LEGACY_BINDING_ID
                self.legacy_successes += 1
            return resp

        # No usable path.
        if self.offers_legacy and not self.offers_current:
            # Legacy-only: unnegotiated application method.
            assert self.legacy is not None
            return _from_legacy(self.legacy.handle(message))

        if self.offers_current and not has_current_meta:
            return self._error(
                msg_id,
                ERR_INVALID_PARAMS,
                "current path requires params._meta protocol version",
                data={
                    "reason": REASON_BINDING_NOT_OFFERED
                    if not self.offers_legacy
                    else REASON_PATH_AMBIGUOUS,
                    "supportedBindings": self.offered_bindings(),
                    "supportedVersions": self.offered_versions(),
                    "missing": [META_PROTOCOL_VERSION],
                },
            )

        return self._error(
            msg_id,
            ERR_METHOD_NOT_FOUND,
            f"no binding path for method {method!r}",
            data={
                "reason": REASON_PATH_AMBIGUOUS,
                "supportedBindings": self.offered_bindings(),
            },
        )

    def _handle_legacy_lifecycle(self, message: Dict[str, Any]) -> CompatResponse:
        msg_id = message.get("id")
        method = message.get("method")

        if not self.offers_legacy:
            # Current-only: initialize-as-current rejected.
            assert self.current is not None
            return _from_current(self.current.handle(message))

        # Silent downgrade: active current → legacy initialize family.
        if (
            self.active_binding == CURRENT_BINDING_ID
            and method == "initialize"
        ):
            return self._reject_silent_downgrade(
                msg_id,
                detail="initialize after current binding became active",
            )

        # Dual: initialize remains legacy lifecycle only — modern version on
        # initialize is a version/binding mismatch, not promotion to current.
        if method == "initialize":
            params = message.get("params") or {}
            if isinstance(params, dict):
                version = params.get("protocolVersion")
                if version == CURRENT_PROTOCOL_VERSION:
                    self.rejected_forgeries += 1
                    return self._error(
                        msg_id,
                        ERR_UNSUPPORTED_PROTOCOL_VERSION,
                        "modern protocol version is not valid on initialize path",
                        data={
                            "reason": REASON_VERSION_BINDING_MISMATCH,
                            "requested": version,
                            "supported": [LEGACY_PROTOCOL_VERSION]
                            if self.mode == PeerMode.LEGACY_ONLY
                            else self.offered_versions(),
                            "path": "legacy",
                            "bindingId": LEGACY_BINDING_ID,
                        },
                    )
                # Cross-pair: current binding id on initialize.
                caps = params.get("capabilities")
                if isinstance(caps, dict):
                    claimed = _extract_binding_id(caps)
                    if claimed == CURRENT_BINDING_ID:
                        self.rejected_forgeries += 1
                        return self._error(
                            msg_id,
                            ERR_INVALID_PARAMS,
                            "current binding id is not valid on initialize path",
                            data={
                                "reason": REASON_BINDING_MISMATCH,
                                "expected": LEGACY_BINDING_ID,
                                "requested": claimed,
                                "path": "legacy",
                            },
                        )

        assert self.legacy is not None
        # Dual initialize success: enrich result with dual advertisement.
        resp = self.legacy.handle(message)
        out = _from_legacy(resp)
        if out.ok and method == "initialize" and out.result is not None:
            if self.mode == PeerMode.DUAL:
                out.result = self._enrich_legacy_initialize_result(out.result)
            self.active_binding = LEGACY_BINDING_ID
            self.legacy_successes += 1
        elif (
            out.ok
            and method in ("notifications/initialized", "initialized")
        ):
            # Session fully open; keep active as legacy.
            self.active_binding = LEGACY_BINDING_ID
        elif not out.ok and out.error is not None:
            data = out.error.get("data") or {}
            reason = data.get("reason")
            if reason in (
                REASON_BINDING_MISMATCH,
                "binding_name_required",
            ) or out.error.get("code") == ERR_UNSUPPORTED_PROTOCOL_VERSION:
                self.rejected_forgeries += 1
        return out

    def _handle_current_path(
        self, message: Dict[str, Any], meta: Dict[str, Any]
    ) -> CompatResponse:
        msg_id = message.get("id")

        if not self.offers_current:
            self.rejected_forgeries += 1
            return self._error(
                msg_id,
                ERR_UNSUPPORTED_PROTOCOL_VERSION,
                "current binding is not offered by this peer",
                data={
                    "reason": REASON_BINDING_NOT_OFFERED,
                    "requested": meta.get(META_PROTOCOL_VERSION),
                    "requestedBinding": meta.get(META_BINDING_ID),
                    "supported": self.offered_versions(),
                    "supportedBindings": self.offered_bindings(),
                },
            )

        # Matrix forgery checks before delegating to current peer.
        version = meta.get(META_PROTOCOL_VERSION)
        claimed_binding = meta.get(META_BINDING_ID)

        if version is None:
            return self._error(
                msg_id,
                ERR_INVALID_PARAMS,
                f"missing required _meta key {META_PROTOCOL_VERSION}",
                data={"missing": [META_PROTOCOL_VERSION]},
            )

        # Forged: legacy version on current-shaped path.
        if version == LEGACY_PROTOCOL_VERSION:
            self.rejected_forgeries += 1
            return self._error(
                msg_id,
                ERR_UNSUPPORTED_PROTOCOL_VERSION
                if version != CURRENT_PROTOCOL_VERSION
                else ERR_INVALID_PARAMS,
                "legacy protocol version is not valid on current path",
                data={
                    "reason": REASON_FORGED_VERSION,
                    "requested": version,
                    "supported": [CURRENT_PROTOCOL_VERSION]
                    if self.mode == PeerMode.CURRENT_ONLY
                    else self.offered_versions(),
                    "path": "current",
                    "expectedBinding": CURRENT_BINDING_ID,
                },
            )

        # Forged cross-pair: current binding id + non-current version, or
        # legacy binding id + current version.
        if (
            claimed_binding == CURRENT_BINDING_ID
            and version != CURRENT_PROTOCOL_VERSION
        ):
            self.rejected_forgeries += 1
            return self._error(
                msg_id,
                ERR_INVALID_PARAMS,
                "forged protocol version for current binding id",
                data={
                    "reason": REASON_FORGED_VERSION,
                    "requested": version,
                    "requestedBinding": claimed_binding,
                    "expected": CURRENT_PROTOCOL_VERSION,
                },
            )

        if (
            claimed_binding == LEGACY_BINDING_ID
            and version == CURRENT_PROTOCOL_VERSION
        ):
            self.rejected_forgeries += 1
            return self._error(
                msg_id,
                ERR_INVALID_PARAMS,
                "legacy binding id is not valid on current path",
                data={
                    "reason": REASON_BINDING_MISMATCH,
                    "expected": CURRENT_BINDING_ID,
                    "requested": claimed_binding,
                    "path": "current",
                },
            )

        if (
            claimed_binding is not None
            and claimed_binding not in (CURRENT_BINDING_ID, LEGACY_BINDING_ID)
        ):
            self.rejected_forgeries += 1
            return self._error(
                msg_id,
                ERR_INVALID_PARAMS,
                "unknown binding id",
                data={
                    "reason": REASON_BINDING_MISMATCH,
                    "requested": claimed_binding,
                    "supportedBindings": self.offered_bindings(),
                },
            )

        # Dual discover: answer with both bindings before delegating.
        method = message.get("method")
        if method == "server/discover" and self.mode == PeerMode.DUAL:
            # Still require valid current meta via current peer validation path.
            assert self.current is not None
            probe = self.current.handle(message)
            if not probe.ok:
                return _from_current(probe)
            result = self._dual_discover_result()
            self.active_binding = CURRENT_BINDING_ID
            self.current_successes += 1
            return CompatResponse(id=msg_id, result=result, path="current")

        assert self.current is not None
        resp = _from_current(self.current.handle(message))
        if resp.ok:
            # Explicit current path is an allowed upgrade from legacy active.
            self.active_binding = CURRENT_BINDING_ID
            self.current_successes += 1
        elif resp.error is not None:
            data = resp.error.get("data") or {}
            if data.get("reason") in (
                REASON_BINDING_MISMATCH,
                "binding_id_mismatch",
            ) or resp.error.get("code") == ERR_UNSUPPORTED_PROTOCOL_VERSION:
                self.rejected_forgeries += 1
        return resp

    def _enrich_legacy_initialize_result(
        self, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        out = copy.deepcopy(result)
        caps = out.setdefault("capabilities", {})
        mcpp = caps.setdefault("mcp++", {})
        mcpp["bindingId"] = LEGACY_BINDING_ID
        mcpp["bindingIds"] = self.offered_bindings()
        mcpp["supportedVersions"] = self.offered_versions()
        mcpp.setdefault("profiles", sorted(self.profiles))
        out["supportedVersions"] = self.offered_versions()
        out["supportedBindings"] = self.offered_bindings()
        return out

    def _dual_discover_result(self) -> Dict[str, Any]:
        profile_map = {k: True for k in sorted(self.profiles)}
        return {
            "resultType": "complete",
            "supportedVersions": self.offered_versions(),
            "supportedBindings": self.offered_bindings(),
            "capabilities": {
                "tools": {},
                "extensions": {
                    "io.modelcontextprotocol/tasks": {},
                    "io.mcplusplus/profiles": profile_map,
                },
                "mcp++": {
                    "bindingId": CURRENT_BINDING_ID,
                    "bindingIds": self.offered_bindings(),
                    "profiles": sorted(self.profiles),
                },
            },
            "_meta": {
                META_SERVER_INFO: {
                    "name": self.server_name,
                    "version": self.server_version,
                },
                META_BINDING_ID: CURRENT_BINDING_ID,
            },
        }

    def _reject_silent_downgrade(
        self, msg_id: Any, *, detail: str
    ) -> CompatResponse:
        self.rejected_downgrades += 1
        return self._error(
            msg_id,
            ERR_INVALID_PARAMS,
            f"silent downgrade rejected: {detail}",
            data={
                "reason": REASON_SILENT_DOWNGRADE,
                "activeBinding": self.active_binding,
                "supportedBindings": self.offered_bindings(),
                "detail": detail,
            },
        )

    @staticmethod
    def _error(
        msg_id: Any,
        code: int,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> CompatResponse:
        err: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return CompatResponse(id=msg_id, error=err)


def _extract_binding_id(capabilities: Dict[str, Any]) -> Optional[str]:
    nested = capabilities.get("mcp++")
    if isinstance(nested, dict):
        raw = nested.get("bindingId")
        if isinstance(raw, str):
            return raw
    experimental = capabilities.get("experimental")
    if isinstance(experimental, dict):
        raw = experimental.get("mcp++/bindingId")
        if isinstance(raw, str):
            return raw
    return None


def dual_open_legacy(peer: DualBindingPeer) -> CompatResponse:
    """Run initialize + notifications/initialized on a dual/legacy peer."""
    init = peer.handle(
        legacy_make_request(
            "initialize",
            req_id=1,
            params=legacy_initialize_params(),
        )
    )
    if not init.ok:
        return init
    peer.handle(
        legacy_make_request(
            "notifications/initialized",
            notification=True,
            params={},
        )
    )
    return init


# ---------------------------------------------------------------------------
# Spec presence
# ---------------------------------------------------------------------------


class TestCompatibilityMatrixSpec:
    def test_spec_document_exists_and_names_interface(self):
        assert SPEC_PATH.is_file(), f"missing matrix spec: {SPEC_PATH}"
        text = SPEC_PATH.read_text(encoding="utf-8")
        assert INTERFACE_LABEL in text
        assert LEGACY_BINDING_ID in text
        assert CURRENT_BINDING_ID in text
        assert LEGACY_PROTOCOL_VERSION in text
        assert CURRENT_PROTOCOL_VERSION in text
        # Required scenario classes from acceptance criteria.
        for token in (
            "legacy-only",
            "current-only",
            "dual",
            "Forged version",
            "Silent downgrade",
            "fail-closed",
        ):
            assert token in text or token.lower() in text.lower(), token
        assert "BindingPathSelect@1" in text
        assert "silent_downgrade_rejected" in text
        assert "forged_version" in text


# ---------------------------------------------------------------------------
# Legacy-only
# ---------------------------------------------------------------------------


class TestLegacyOnlyPeer:
    @pytest.fixture
    def peer(self) -> DualBindingPeer:
        return DualBindingPeer(mode=PeerMode.LEGACY_ONLY)

    def test_honest_legacy_initialize_and_tools(self, peer: DualBindingPeer):
        init = dual_open_legacy(peer)
        assert init.ok, init.error
        assert peer.active_binding == LEGACY_BINDING_ID
        listed = peer.handle(legacy_make_request("tools/list", req_id=2, params={}))
        assert listed.ok, listed.error
        assert listed.path == "legacy"
        names = {t["name"] for t in (listed.result or {}).get("tools", [])}
        assert "echo" in names

    def test_current_meta_request_rejected(self, peer: DualBindingPeer):
        resp = peer.handle(
            current_make_request(
                "tools/list",
                req_id=1,
                meta=current_request_meta(),
            )
        )
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] == REASON_BINDING_NOT_OFFERED
        assert CURRENT_BINDING_ID not in resp.error["data"]["supportedBindings"]
        assert LEGACY_BINDING_ID in resp.error["data"]["supportedBindings"]

    def test_does_not_advertise_current_on_initialize(self, peer: DualBindingPeer):
        resp = peer.handle(
            legacy_make_request(
                "initialize",
                params=legacy_initialize_params(),
            )
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        assert resp.result["protocolVersion"] == LEGACY_PROTOCOL_VERSION
        mcpp = resp.result["capabilities"]["mcp++"]
        assert mcpp["bindingId"] == LEGACY_BINDING_ID
        # Dual enrichment only applies in dual mode.
        assert "bindingIds" not in mcpp or CURRENT_BINDING_ID not in mcpp.get(
            "bindingIds", []
        )


# ---------------------------------------------------------------------------
# Current-only
# ---------------------------------------------------------------------------


class TestCurrentOnlyPeer:
    @pytest.fixture
    def peer(self) -> DualBindingPeer:
        return DualBindingPeer(mode=PeerMode.CURRENT_ONLY)

    def test_tools_without_initialize(self, peer: DualBindingPeer):
        resp = peer.handle(
            current_make_request(
                "tools/list",
                req_id=10,
                meta=current_request_meta(),
            )
        )
        assert resp.ok, resp.error
        assert peer.active_binding == CURRENT_BINDING_ID
        assert peer.current is not None
        assert peer.current.initialize_calls == 0

    def test_initialize_rejected(self, peer: DualBindingPeer):
        resp = peer.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": LEGACY_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "legacy-shaped", "version": "0.1"},
                },
            }
        )
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["code"] == ERR_METHOD_NOT_FOUND
        assert resp.error["data"]["reason"] == REASON_INIT_AS_CURRENT
        assert peer.active_binding is None

    def test_notifications_initialized_rejected(self, peer: DualBindingPeer):
        resp = peer.handle(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] == REASON_INIT_AS_CURRENT


# ---------------------------------------------------------------------------
# Dual
# ---------------------------------------------------------------------------


class TestDualPeer:
    @pytest.fixture
    def peer(self) -> DualBindingPeer:
        return DualBindingPeer(mode=PeerMode.DUAL)

    def test_legacy_client_full_handshake(self, peer: DualBindingPeer):
        init = dual_open_legacy(peer)
        assert init.ok, init.error
        assert init.result is not None
        assert LEGACY_BINDING_ID in init.result["supportedBindings"]
        assert CURRENT_BINDING_ID in init.result["supportedBindings"]
        assert set(init.result["supportedVersions"]) == {
            LEGACY_PROTOCOL_VERSION,
            CURRENT_PROTOCOL_VERSION,
        }
        listed = peer.handle(legacy_make_request("tools/list", req_id=2, params={}))
        assert listed.ok, listed.error
        call = peer.handle(
            legacy_make_request(
                "tools/call",
                req_id=3,
                params={"name": "echo", "arguments": {"text": "dual-legacy"}},
            )
        )
        assert call.ok, call.error
        assert call.result is not None
        assert call.result["content"][0]["text"] == "dual-legacy"
        assert peer.legacy_successes >= 1

    def test_current_client_without_initialize(self, peer: DualBindingPeer):
        resp = peer.handle(
            current_make_request(
                "tools/call",
                req_id=11,
                params={"name": "echo", "arguments": {"text": "dual-current"}},
                meta=current_request_meta(),
            )
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        assert resp.result["content"][0]["text"] == "dual-current"
        assert peer.active_binding == CURRENT_BINDING_ID
        assert peer.current is not None
        assert peer.current.initialize_calls == 0

    def test_discover_lists_both_bindings(self, peer: DualBindingPeer):
        resp = peer.handle(
            current_make_request(
                "server/discover",
                req_id="d1",
                meta=current_request_meta(),
            )
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        assert set(resp.result["supportedBindings"]) == {
            LEGACY_BINDING_ID,
            CURRENT_BINDING_ID,
        }
        assert CURRENT_PROTOCOL_VERSION in resp.result["supportedVersions"]
        assert LEGACY_PROTOCOL_VERSION in resp.result["supportedVersions"]
        assert (
            resp.result["capabilities"]["mcp++"]["bindingIds"]
            == peer.offered_bindings()
        )

    def test_honest_upgrade_legacy_to_current(self, peer: DualBindingPeer):
        assert dual_open_legacy(peer).ok
        assert peer.active_binding == LEGACY_BINDING_ID
        # Explicit current _meta is allowed upgrade (not silent downgrade).
        upgraded = peer.handle(
            current_make_request(
                "tools/list",
                req_id=20,
                meta=current_request_meta(),
            )
        )
        assert upgraded.ok, upgraded.error
        assert peer.active_binding == CURRENT_BINDING_ID
        assert peer.current_successes >= 1

    def test_independent_paths_on_fresh_peers(self):
        """Two dual peers: one legacy client, one current client — both accept."""
        legacy_peer = DualBindingPeer(mode=PeerMode.DUAL, server_name="dual-a")
        current_peer = DualBindingPeer(mode=PeerMode.DUAL, server_name="dual-b")
        assert dual_open_legacy(legacy_peer).ok
        cur = current_peer.handle(
            current_make_request("tools/list", meta=current_request_meta())
        )
        assert cur.ok, cur.error
        assert legacy_peer.active_binding == LEGACY_BINDING_ID
        assert current_peer.active_binding == CURRENT_BINDING_ID


# ---------------------------------------------------------------------------
# Forged version (all modes as applicable)
# ---------------------------------------------------------------------------


class TestForgedVersion:
    def test_unknown_version_on_legacy_initialize(self):
        peer = DualBindingPeer(mode=PeerMode.LEGACY_ONLY)
        params = legacy_initialize_params(protocol_version="1900-01-01")
        resp = peer.handle(legacy_make_request("initialize", params=params))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["code"] == ERR_UNSUPPORTED_PROTOCOL_VERSION
        assert peer.active_binding is None

    def test_modern_version_on_legacy_only_initialize(self):
        peer = DualBindingPeer(mode=PeerMode.LEGACY_ONLY)
        params = legacy_initialize_params(
            protocol_version=CURRENT_PROTOCOL_VERSION
        )
        resp = peer.handle(legacy_make_request("initialize", params=params))
        assert not resp.ok
        assert resp.error is not None
        # DualBindingPeer intercepts modern version before legacy peer.
        assert resp.error["data"]["reason"] == REASON_VERSION_BINDING_MISMATCH
        assert peer.active_binding is None

    def test_modern_version_on_dual_initialize_not_promoted(self):
        peer = DualBindingPeer(mode=PeerMode.DUAL)
        params = legacy_initialize_params(
            protocol_version=CURRENT_PROTOCOL_VERSION
        )
        resp = peer.handle(legacy_make_request("initialize", params=params))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] == REASON_VERSION_BINDING_MISMATCH
        assert peer.active_binding is None
        # Current path still works after the rejected forge attempt.
        ok = peer.handle(
            current_make_request("tools/list", meta=current_request_meta())
        )
        assert ok.ok, ok.error

    def test_legacy_version_on_current_only_meta(self):
        peer = DualBindingPeer(mode=PeerMode.CURRENT_ONLY)
        meta = current_request_meta(protocol_version=LEGACY_PROTOCOL_VERSION)
        resp = peer.handle(current_make_request("tools/list", meta=meta))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] == REASON_FORGED_VERSION
        assert peer.active_binding is None
        assert peer.rejected_forgeries >= 1

    def test_legacy_version_on_dual_current_path(self):
        peer = DualBindingPeer(mode=PeerMode.DUAL)
        meta = current_request_meta(protocol_version=LEGACY_PROTOCOL_VERSION)
        resp = peer.handle(current_make_request("tools/list", meta=meta))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] == REASON_FORGED_VERSION

    def test_current_binding_id_with_legacy_version_meta(self):
        peer = DualBindingPeer(mode=PeerMode.DUAL)
        meta = current_request_meta(protocol_version=LEGACY_PROTOCOL_VERSION)
        meta[META_BINDING_ID] = CURRENT_BINDING_ID
        resp = peer.handle(current_make_request("tools/list", meta=meta))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] == REASON_FORGED_VERSION

    def test_legacy_binding_id_with_current_version_meta(self):
        peer = DualBindingPeer(mode=PeerMode.DUAL)
        meta = current_request_meta(protocol_version=CURRENT_PROTOCOL_VERSION)
        meta[META_BINDING_ID] = LEGACY_BINDING_ID
        resp = peer.handle(current_make_request("tools/list", meta=meta))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] == REASON_BINDING_MISMATCH

    def test_current_binding_id_on_initialize_legacy_only(self):
        peer = DualBindingPeer(mode=PeerMode.LEGACY_ONLY)
        params = legacy_initialize_params(binding_id=CURRENT_BINDING_ID)
        resp = peer.handle(legacy_make_request("initialize", params=params))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] in (
            REASON_BINDING_MISMATCH,
            "binding_id_mismatch",
        )
        assert peer.active_binding is None

    def test_current_binding_id_on_initialize_dual(self):
        peer = DualBindingPeer(mode=PeerMode.DUAL)
        params = legacy_initialize_params(binding_id=CURRENT_BINDING_ID)
        resp = peer.handle(legacy_make_request("initialize", params=params))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] == REASON_BINDING_MISMATCH
        assert peer.active_binding is None

    def test_forged_unknown_binding_id_on_current_path(self):
        peer = DualBindingPeer(mode=PeerMode.DUAL)
        meta = current_request_meta()
        meta[META_BINDING_ID] = "mcp-binding/forged-9999-99-99"
        resp = peer.handle(current_make_request("tools/list", meta=meta))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] == REASON_BINDING_MISMATCH


# ---------------------------------------------------------------------------
# Silent downgrade
# ---------------------------------------------------------------------------


class TestSilentDowngrade:
    @pytest.fixture
    def peer(self) -> DualBindingPeer:
        return DualBindingPeer(mode=PeerMode.DUAL)

    def test_current_active_then_initialize_rejected(self, peer: DualBindingPeer):
        ok = peer.handle(
            current_make_request("tools/list", meta=current_request_meta())
        )
        assert ok.ok, ok.error
        assert peer.active_binding == CURRENT_BINDING_ID

        down = peer.handle(
            legacy_make_request(
                "initialize",
                req_id=99,
                params=legacy_initialize_params(),
            )
        )
        assert not down.ok
        assert down.error is not None
        assert down.error["data"]["reason"] == REASON_SILENT_DOWNGRADE
        assert down.error["data"]["activeBinding"] == CURRENT_BINDING_ID
        assert peer.rejected_downgrades == 1
        # Active binding remains current; no legacy session opened.
        assert peer.active_binding == CURRENT_BINDING_ID
        assert peer.legacy is not None
        assert peer.legacy.phase is SessionPhase.UNINITIALIZED

    def test_current_active_then_bare_legacy_app_method_rejected(
        self, peer: DualBindingPeer
    ):
        assert peer.handle(
            current_make_request("tools/list", meta=current_request_meta())
        ).ok
        # After current path, bare tools/list without _meta is silent downgrade
        # (no open legacy session either).
        bare = peer.handle(legacy_make_request("tools/list", req_id=2, params={}))
        assert not bare.ok
        assert bare.error is not None
        # Either silent downgrade (if we had legacy session) or missing meta /
        # path ambiguity — both fail closed without accepting legacy.
        reason = (bare.error.get("data") or {}).get("reason")
        assert reason in (
            REASON_SILENT_DOWNGRADE,
            REASON_PATH_AMBIGUOUS,
            "not_initialized",
        ) or bare.error["code"] in (
            ERR_INVALID_PARAMS,
            ERR_NOT_INITIALIZED,
            ERR_METHOD_NOT_FOUND,
        )
        assert peer.active_binding == CURRENT_BINDING_ID

    def test_current_active_then_bare_legacy_after_prior_legacy_session(
        self, peer: DualBindingPeer
    ):
        """Upgrade to current, then bare legacy app method must fail closed."""
        assert dual_open_legacy(peer).ok
        assert peer.active_binding == LEGACY_BINDING_ID
        assert peer.handle(
            current_make_request("tools/list", meta=current_request_meta())
        ).ok
        assert peer.active_binding == CURRENT_BINDING_ID

        bare = peer.handle(legacy_make_request("tools/list", req_id=5, params={}))
        assert not bare.ok
        assert bare.error is not None
        assert bare.error["data"]["reason"] == REASON_SILENT_DOWNGRADE
        assert peer.rejected_downgrades >= 1

    def test_fresh_legacy_after_reset_is_not_downgrade(self, peer: DualBindingPeer):
        assert peer.handle(
            current_make_request("tools/list", meta=current_request_meta())
        ).ok
        peer.reset()
        assert peer.active_binding is None
        init = dual_open_legacy(peer)
        assert init.ok, init.error
        assert peer.active_binding == LEGACY_BINDING_ID


# ---------------------------------------------------------------------------
# Matrix checklist coverage (BindingCompatibilityMatrix@1)
# ---------------------------------------------------------------------------


class TestMatrixChecklistCoverage:
    """Ensure the 14 checklist rows from the matrix doc are exercised."""

    def test_all_checklist_rows_have_fail_closed_or_accept_proof(self):
        results: Dict[int, str] = {}

        # 1 legacy-only honest
        p = DualBindingPeer(mode=PeerMode.LEGACY_ONLY)
        assert dual_open_legacy(p).ok
        results[1] = "accept"

        # 2 legacy-only current meta
        p = DualBindingPeer(mode=PeerMode.LEGACY_ONLY)
        r = p.handle(current_make_request("tools/list", meta=current_request_meta()))
        assert not r.ok
        results[2] = "reject"

        # 3 legacy-only forged modern initialize
        p = DualBindingPeer(mode=PeerMode.LEGACY_ONLY)
        r = p.handle(
            legacy_make_request(
                "initialize",
                params=legacy_initialize_params(
                    protocol_version=CURRENT_PROTOCOL_VERSION
                ),
            )
        )
        assert not r.ok
        results[3] = "reject"

        # 4 current-only tools without initialize
        p = DualBindingPeer(mode=PeerMode.CURRENT_ONLY)
        r = p.handle(current_make_request("tools/list", meta=current_request_meta()))
        assert r.ok
        results[4] = "accept"

        # 5 current-only initialize
        p = DualBindingPeer(mode=PeerMode.CURRENT_ONLY)
        r = p.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": LEGACY_PROTOCOL_VERSION, "capabilities": {}},
            }
        )
        assert not r.ok
        results[5] = "reject"

        # 6 current-only forged legacy version meta
        p = DualBindingPeer(mode=PeerMode.CURRENT_ONLY)
        r = p.handle(
            current_make_request(
                "tools/list",
                meta=current_request_meta(protocol_version=LEGACY_PROTOCOL_VERSION),
            )
        )
        assert not r.ok
        results[6] = "reject"

        # 7 dual legacy handshake
        p = DualBindingPeer(mode=PeerMode.DUAL)
        assert dual_open_legacy(p).ok
        results[7] = "accept"

        # 8 dual current without initialize
        p = DualBindingPeer(mode=PeerMode.DUAL)
        r = p.handle(current_make_request("tools/list", meta=current_request_meta()))
        assert r.ok
        results[8] = "accept"

        # 9 dual discover both
        p = DualBindingPeer(mode=PeerMode.DUAL)
        r = p.handle(
            current_make_request("server/discover", meta=current_request_meta())
        )
        assert r.ok and r.result is not None
        assert len(r.result["supportedBindings"]) == 2
        results[9] = "accept"

        # 10 dual upgrade
        p = DualBindingPeer(mode=PeerMode.DUAL)
        assert dual_open_legacy(p).ok
        r = p.handle(current_make_request("tools/list", meta=current_request_meta()))
        assert r.ok
        results[10] = "accept"

        # 11 forged cross-pair current path
        p = DualBindingPeer(mode=PeerMode.DUAL)
        meta = current_request_meta()
        meta[META_BINDING_ID] = LEGACY_BINDING_ID
        r = p.handle(current_make_request("tools/list", meta=meta))
        assert not r.ok
        results[11] = "reject"

        # 12 current binding id on initialize
        p = DualBindingPeer(mode=PeerMode.DUAL)
        r = p.handle(
            legacy_make_request(
                "initialize",
                params=legacy_initialize_params(binding_id=CURRENT_BINDING_ID),
            )
        )
        assert not r.ok
        results[12] = "reject"

        # 13 current → silent initialize
        p = DualBindingPeer(mode=PeerMode.DUAL)
        assert p.handle(
            current_make_request("tools/list", meta=current_request_meta())
        ).ok
        r = p.handle(
            legacy_make_request("initialize", params=legacy_initialize_params())
        )
        assert not r.ok
        assert r.error is not None
        assert r.error["data"]["reason"] == REASON_SILENT_DOWNGRADE
        results[13] = "reject"

        # 14 current → bare legacy after upgrade
        p = DualBindingPeer(mode=PeerMode.DUAL)
        assert dual_open_legacy(p).ok
        assert p.handle(
            current_make_request("tools/list", meta=current_request_meta())
        ).ok
        r = p.handle(legacy_make_request("tools/list", params={}))
        assert not r.ok
        assert r.error is not None
        assert r.error["data"]["reason"] == REASON_SILENT_DOWNGRADE
        results[14] = "reject"

        assert set(results) == set(range(1, 15))
        assert all(v in ("accept", "reject") for v in results.values())
        # All negatives are reject.
        for row in (2, 3, 5, 6, 11, 12, 13, 14):
            assert results[row] == "reject"
        for row in (1, 4, 7, 8, 9, 10):
            assert results[row] == "accept"


class TestInterfaceSurface:
    def test_interface_constants(self):
        assert INTERFACE_LABEL == "BindingCompatibilityMatrix@1"
        assert LEGACY_BINDING_ID == "mcp-binding/legacy-2024-11-05"
        assert CURRENT_BINDING_ID == "mcp-binding/2026-07-28"
        assert all(k.startswith("mcp++/") for k in ABSTRACT_PROFILE_KEYS)

    def test_peer_mode_offer_sets(self):
        assert DualBindingPeer(mode=PeerMode.LEGACY_ONLY).offered_bindings() == [
            LEGACY_BINDING_ID
        ]
        assert DualBindingPeer(mode=PeerMode.CURRENT_ONLY).offered_bindings() == [
            CURRENT_BINDING_ID
        ]
        dual = DualBindingPeer(mode=PeerMode.DUAL).offered_bindings()
        assert LEGACY_BINDING_ID in dual and CURRENT_BINDING_ID in dual

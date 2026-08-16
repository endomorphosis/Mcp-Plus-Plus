"""
Integration tests for the legacy MCP binding: mcp-binding/legacy-2024-11-05.

Spec: docs/spec/bindings/mcp-legacy-2024-11-05.md
Interface: McpBindingLegacy20241105@1
Task: MCPP-020

Acceptance:
  - Legacy tests pass including 2024-11-05 initialize.
  - The binding name is mandatory in capability advertisement.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pytest

# ---------------------------------------------------------------------------
# Constants (McpBindingLegacy20241105@1)
# ---------------------------------------------------------------------------

BINDING_ID = "mcp-binding/legacy-2024-11-05"
PROTOCOL_VERSION = "2024-11-05"
CURRENT_BINDING_ID = "mcp-binding/2026-07-28"
CURRENT_PROTOCOL_VERSION = "2026-07-28"

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

ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INVALID_REQUEST = -32600
ERR_UNSUPPORTED_PROTOCOL_VERSION = -32022
ERR_NOT_INITIALIZED = -32000

SPEC_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "spec"
    / "bindings"
    / "mcp-legacy-2024-11-05.md"
)

VECTOR_PATH = (
    Path(__file__).resolve().parents[2]
    / "conformance"
    / "vectors"
    / "initialize_result.json"
)


# ---------------------------------------------------------------------------
# Reference peer: legacy-only MCP 2024-11-05 binding
# ---------------------------------------------------------------------------


class SessionPhase(Enum):
    UNINITIALIZED = auto()
    INITIALIZED = auto()  # InitializeResult sent; awaiting notifications/initialized
    READY = auto()  # Full session open


@dataclass
class BindingResponse:
    """JSON-RPC style response for the reference peer."""

    id: Any
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    # Notifications may produce no wire response
    is_notification_ack: bool = False

    @property
    def ok(self) -> bool:
        if self.is_notification_ack:
            return self.error is None
        return self.error is None and self.result is not None

    def as_jsonrpc(self) -> Optional[Dict[str, Any]]:
        if self.is_notification_ack and self.error is None:
            return None
        body: Dict[str, Any] = {"jsonrpc": "2.0", "id": self.id}
        if self.error is not None:
            body["error"] = self.error
        else:
            body["result"] = self.result
        return body


@dataclass
class McpBindingLegacy20241105:
    """
    Legacy-only reference peer for mcp-binding/legacy-2024-11-05
    (McpBindingLegacy20241105@1).

    Implements:
      - initialize / InitializeResult / notifications/initialized
      - mandatory binding name in capability advertisement
      - protocolVersion 2024-11-05 pin
      - profile advertisement on initialize
      - post-handshake tools/list and tools/call
      - fail-closed rejection when binding name missing or forged
      - rejection of application methods before initialize
    """

    server_name: str = "mcp++-legacy-ref"
    server_version: str = "1.0.0"
    # When True, server claims MCP++ 1.0 and must advertise binding id.
    claim_mcpp: bool = True
    profiles: Set[str] = field(
        default_factory=lambda: {
            "mcp++/mcp-idl",
            "mcp++/cid-envelope",
        }
    )
    tools: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    phase: SessionPhase = SessionPhase.UNINITIALIZED
    negotiated_version: Optional[str] = None
    negotiated_client_binding: Optional[str] = None
    negotiated_profiles: Set[str] = field(default_factory=set)
    client_info: Optional[Dict[str, Any]] = None
    initialize_calls: int = 0
    initialized_notifications: int = 0
    request_count: int = 0
    # Test hook: if True, omit binding id from server InitializeResult (non-conformant)
    omit_server_binding_id: bool = False
    # Test hook: require client binding id only when client claims MCP++ profiles
    require_client_binding_when_mcpp: bool = True

    def __post_init__(self) -> None:
        if not self.tools:
            self.tools = {
                "echo": {
                    "name": "echo",
                    "description": "Echo arguments (legacy binding smoke tool)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                    },
                }
            }

    # -- public API ---------------------------------------------------------

    def handle(self, message: Dict[str, Any]) -> BindingResponse:
        """Dispatch one JSON-RPC message under the legacy session model."""
        self.request_count += 1
        msg_id = message.get("id")
        method = message.get("method")

        if message.get("jsonrpc") != "2.0":
            return self._error(msg_id, ERR_INVALID_PARAMS, "jsonrpc must be '2.0'")

        if not method or not isinstance(method, str):
            return self._error(msg_id, ERR_INVALID_PARAMS, "missing method")

        if method == "initialize":
            return self._handle_initialize(msg_id, message)

        if method == "notifications/initialized" or method == "initialized":
            return self._handle_initialized_notification(msg_id, message)

        # Application methods require a completed (or at least started) handshake.
        if self.phase is SessionPhase.UNINITIALIZED:
            return self._error(
                msg_id,
                ERR_NOT_INITIALIZED,
                "session not initialized; send initialize first",
                data={
                    "bindingId": BINDING_ID,
                    "reason": "not_initialized",
                    "supportedVersions": [PROTOCOL_VERSION],
                },
            )

        params = message.get("params") or {}
        if params is not None and not isinstance(params, dict):
            return self._error(msg_id, ERR_INVALID_PARAMS, "params must be an object")
        if not isinstance(params, dict):
            params = {}

        if method == "tools/list":
            return BindingResponse(id=msg_id, result=self._tools_list_result())
        if method == "tools/call":
            return self._tools_call(msg_id, params)
        if method == "ping":
            return BindingResponse(id=msg_id, result={})

        return self._error(msg_id, ERR_METHOD_NOT_FOUND, f"Method not found: {method}")

    def reset_session(self) -> None:
        self.phase = SessionPhase.UNINITIALIZED
        self.negotiated_version = None
        self.negotiated_client_binding = None
        self.negotiated_profiles = set()
        self.client_info = None

    # -- initialize path ----------------------------------------------------

    def _handle_initialize(
        self, msg_id: Any, message: Dict[str, Any]
    ) -> BindingResponse:
        self.initialize_calls += 1
        params = message.get("params") or {}
        if not isinstance(params, dict):
            return self._error(msg_id, ERR_INVALID_PARAMS, "params must be an object")

        version = params.get("protocolVersion")
        if version is None:
            return self._error(
                msg_id,
                ERR_INVALID_PARAMS,
                "missing required params.protocolVersion",
                data={"missing": ["protocolVersion"]},
            )
        if version != PROTOCOL_VERSION:
            return self._error(
                msg_id,
                ERR_UNSUPPORTED_PROTOCOL_VERSION,
                "Unsupported protocol version",
                data={
                    "supported": [PROTOCOL_VERSION],
                    "requested": version,
                    "bindingId": BINDING_ID,
                },
            )

        capabilities = params.get("capabilities")
        if capabilities is None:
            capabilities = {}
        if not isinstance(capabilities, dict):
            return self._error(
                msg_id, ERR_INVALID_PARAMS, "params.capabilities must be an object"
            )

        # Extract binding id from client capabilities (mandatory for MCP++ claims).
        client_binding, client_profiles, claim_mcpp = extract_binding_and_profiles(
            capabilities
        )

        if claim_mcpp or self.claim_mcpp:
            # MCP++ 1.0: binding name is mandatory in capability advertisement.
            if not client_binding:
                return self._error(
                    msg_id,
                    ERR_INVALID_PARAMS,
                    "binding name is mandatory in capability advertisement",
                    data={
                        "expected": BINDING_ID,
                        "reason": "binding_name_required",
                        "bindingId": BINDING_ID,
                    },
                )
            if client_binding != BINDING_ID:
                return self._error(
                    msg_id,
                    ERR_INVALID_PARAMS,
                    "binding id does not match legacy binding",
                    data={
                        "expected": BINDING_ID,
                        "requested": client_binding,
                        "reason": "binding_id_mismatch",
                    },
                )

        client_info = params.get("clientInfo")
        if client_info is not None and not isinstance(client_info, dict):
            return self._error(
                msg_id, ERR_INVALID_PARAMS, "params.clientInfo must be an object"
            )

        # Success: open session to INITIALIZED (awaiting notifications/initialized).
        self.phase = SessionPhase.INITIALIZED
        self.negotiated_version = version
        self.negotiated_client_binding = client_binding
        self.client_info = copy.deepcopy(client_info) if client_info else None
        if client_profiles:
            self.negotiated_profiles = set(client_profiles) & set(self.profiles)
        else:
            self.negotiated_profiles = set(self.profiles) if self.claim_mcpp else set()

        return BindingResponse(id=msg_id, result=self._initialize_result())

    def _handle_initialized_notification(
        self, msg_id: Any, message: Dict[str, Any]
    ) -> BindingResponse:
        self.initialized_notifications += 1
        if self.phase is SessionPhase.UNINITIALIZED:
            return self._error(
                msg_id if msg_id is not None else None,
                ERR_NOT_INITIALIZED,
                "notifications/initialized without prior initialize",
                data={"reason": "not_initialized", "bindingId": BINDING_ID},
            )
        self.phase = SessionPhase.READY
        # Notification: no result body when no id; still ack for the reference peer.
        return BindingResponse(id=msg_id, is_notification_ack=True)

    def _initialize_result(self) -> Dict[str, Any]:
        """Build InitializeResult; binding name mandatory when claim_mcpp."""
        capabilities: Dict[str, Any] = {
            "tools": {"listChanged": True},
            "experimental": {},
        }
        if self.claim_mcpp:
            mcpp: Dict[str, Any] = {
                "profiles": sorted(self.profiles),
            }
            if not self.omit_server_binding_id:
                mcpp["bindingId"] = BINDING_ID
            capabilities["mcp++"] = mcpp
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": capabilities,
            "serverInfo": {
                "name": self.server_name,
                "version": self.server_version,
            },
        }

    def _tools_list_result(self) -> Dict[str, Any]:
        return {
            "tools": list(self.tools.values()),
            "bindingId": BINDING_ID if self.claim_mcpp else None,
        }

    def _tools_call(self, msg_id: Any, params: Dict[str, Any]) -> BindingResponse:
        name = params.get("name")
        if not name or name not in self.tools:
            return self._error(
                msg_id,
                ERR_INVALID_PARAMS,
                f"unknown tool: {name!r}",
            )
        arguments = params.get("arguments") or {}
        text = arguments.get("text", "")
        return BindingResponse(
            id=msg_id,
            result={
                "content": [{"type": "text", "text": str(text)}],
                "bindingId": BINDING_ID if self.claim_mcpp else None,
            },
        )

    @staticmethod
    def _error(
        msg_id: Any,
        code: int,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> BindingResponse:
        err: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return BindingResponse(id=msg_id, error=err)


def extract_binding_and_profiles(
    capabilities: Dict[str, Any],
) -> tuple[Optional[str], List[str], bool]:
    """
    Extract binding id, profile keys, and whether the client claims MCP++.

    Supports preferred nested mcp++ object and experimental map forms.
    """
    binding: Optional[str] = None
    profiles: List[str] = []
    claim_mcpp = False

    nested = capabilities.get("mcp++")
    if isinstance(nested, dict):
        claim_mcpp = True
        raw_binding = nested.get("bindingId")
        if isinstance(raw_binding, str):
            binding = raw_binding
        raw_profiles = nested.get("profiles")
        if isinstance(raw_profiles, list):
            profiles.extend(str(p) for p in raw_profiles)
        elif isinstance(raw_profiles, dict):
            profiles.extend(str(k) for k, v in raw_profiles.items() if v)

    experimental = capabilities.get("experimental")
    if isinstance(experimental, dict):
        exp_binding = experimental.get("mcp++/bindingId")
        if isinstance(exp_binding, str):
            binding = binding or exp_binding
            claim_mcpp = True
        for key, value in experimental.items():
            if key.startswith("mcp++/") and key != "mcp++/bindingId" and value:
                claim_mcpp = True
                profiles.append(key)

    # De-dupe profiles preserving order
    seen: Set[str] = set()
    ordered: List[str] = []
    for p in profiles:
        if p not in seen:
            seen.add(p)
            ordered.append(p)

    return binding, ordered, claim_mcpp


def legacy_initialize_params(
    *,
    protocol_version: str = PROTOCOL_VERSION,
    client_name: str = "legacy-test-client",
    client_version: str = "1.0.0",
    profiles: Optional[List[str]] = None,
    include_binding_id: bool = True,
    binding_id: str = BINDING_ID,
    form: str = "nested",
    extra_capabilities: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build initialize params for a legacy MCP++ client."""
    capabilities: Dict[str, Any] = {"tools": {}, "experimental": {}}
    if extra_capabilities:
        capabilities.update(copy.deepcopy(extra_capabilities))

    profile_list = list(profiles) if profiles is not None else ["mcp++/cid-envelope"]

    if form == "nested":
        mcpp: Dict[str, Any] = {"profiles": profile_list}
        if include_binding_id:
            mcpp["bindingId"] = binding_id
        capabilities["mcp++"] = mcpp
    elif form == "experimental":
        experimental = dict(capabilities.get("experimental") or {})
        if include_binding_id:
            experimental["mcp++/bindingId"] = binding_id
        for p in profile_list:
            experimental[p] = True
        capabilities["experimental"] = experimental
    elif form == "baseline_only":
        # No MCP++ claim at all
        pass
    else:
        raise ValueError(f"unknown form: {form}")

    return {
        "protocolVersion": protocol_version,
        "capabilities": capabilities,
        "clientInfo": {"name": client_name, "version": client_version},
    }


def make_request(
    method: str,
    *,
    req_id: Any = 1,
    params: Optional[Dict[str, Any]] = None,
    notification: bool = False,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": method,
    }
    if not notification:
        body["id"] = req_id
    if params is not None:
        body["params"] = params
    elif method == "initialize":
        body["params"] = legacy_initialize_params()
    return body


def open_legacy_session(
    peer: McpBindingLegacy20241105,
    *,
    params: Optional[Dict[str, Any]] = None,
) -> BindingResponse:
    """Run initialize + notifications/initialized; return initialize response."""
    init_params = params if params is not None else legacy_initialize_params()
    init_resp = peer.handle(
        make_request("initialize", req_id=1, params=init_params)
    )
    if not init_resp.ok:
        return init_resp
    peer.handle(
        make_request(
            "notifications/initialized",
            notification=True,
            params={},
        )
    )
    return init_resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLegacyBindingSpecPresence:
    def test_spec_document_exists_and_names_binding(self):
        assert SPEC_PATH.is_file(), f"missing binding spec: {SPEC_PATH}"
        text = SPEC_PATH.read_text(encoding="utf-8")
        assert BINDING_ID in text
        assert PROTOCOL_VERSION in text
        assert "initialize" in text.lower()
        assert "McpBindingLegacy20241105@1" in text
        assert "mandatory" in text.lower()
        assert "notifications/initialized" in text
        assert "initialize_result.json" in text

    def test_historical_initialize_vector_readable(self):
        assert VECTOR_PATH.is_file(), f"missing vector: {VECTOR_PATH}"
        data = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
        assert data["model"] == "InitializeResult"
        payload = data["payload"]
        assert payload["protocolVersion"] == PROTOCOL_VERSION
        assert "capabilities" in payload
        assert payload["serverInfo"]["name"] == "mcp++"


class TestInitialize20241105:
    """Acceptance: legacy tests pass including 2024-11-05 initialize."""

    @pytest.fixture
    def peer(self) -> McpBindingLegacy20241105:
        return McpBindingLegacy20241105()

    def test_initialize_accepts_2024_11_05(self, peer: McpBindingLegacy20241105):
        resp = peer.handle(
            make_request(
                "initialize",
                req_id=1,
                params=legacy_initialize_params(),
            )
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        assert resp.result["protocolVersion"] == PROTOCOL_VERSION
        assert resp.result["serverInfo"]["name"] == peer.server_name
        assert resp.result["capabilities"]["tools"]["listChanged"] is True
        assert peer.phase is SessionPhase.INITIALIZED
        assert peer.initialize_calls == 1
        assert peer.negotiated_version == PROTOCOL_VERSION

    def test_full_handshake_then_tools_list(self, peer: McpBindingLegacy20241105):
        init = open_legacy_session(peer)
        assert init.ok, init.error
        assert peer.phase is SessionPhase.READY
        assert peer.initialized_notifications == 1

        listed = peer.handle(make_request("tools/list", req_id=2, params={}))
        assert listed.ok, listed.error
        assert listed.result is not None
        names = {t["name"] for t in listed.result["tools"]}
        assert "echo" in names

    def test_tools_call_after_handshake(self, peer: McpBindingLegacy20241105):
        assert open_legacy_session(peer).ok
        resp = peer.handle(
            make_request(
                "tools/call",
                req_id=3,
                params={"name": "echo", "arguments": {"text": "hello-legacy"}},
            )
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        assert resp.result["content"][0]["text"] == "hello-legacy"

    def test_ping_after_handshake(self, peer: McpBindingLegacy20241105):
        assert open_legacy_session(peer).ok
        resp = peer.handle(make_request("ping", req_id=4, params={}))
        assert resp.ok, resp.error
        assert resp.result == {}

    def test_initialize_result_includes_binding_and_profiles(
        self, peer: McpBindingLegacy20241105
    ):
        resp = peer.handle(
            make_request("initialize", params=legacy_initialize_params())
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        mcpp = resp.result["capabilities"]["mcp++"]
        assert mcpp["bindingId"] == BINDING_ID
        for key in peer.profiles:
            assert key in mcpp["profiles"]

    def test_vector_baseline_fields_present_on_result(
        self, peer: McpBindingLegacy20241105
    ):
        """Historical pin fields remain present (vector continuity)."""
        vector = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))["payload"]
        resp = peer.handle(
            make_request("initialize", params=legacy_initialize_params())
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        for field in ("protocolVersion", "capabilities", "serverInfo"):
            assert field in resp.result
            assert field in vector
        assert resp.result["protocolVersion"] == vector["protocolVersion"]
        assert "tools" in resp.result["capabilities"]
        assert "listChanged" in resp.result["capabilities"]["tools"]

    def test_application_method_before_initialize_rejected(
        self, peer: McpBindingLegacy20241105
    ):
        resp = peer.handle(make_request("tools/list", req_id=1, params={}))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["code"] == ERR_NOT_INITIALIZED
        assert resp.error["data"]["reason"] == "not_initialized"
        assert resp.error["data"]["bindingId"] == BINDING_ID


class TestBindingNameMandatory:
    """Acceptance: the binding name is mandatory in capability advertisement."""

    @pytest.fixture
    def peer(self) -> McpBindingLegacy20241105:
        return McpBindingLegacy20241105()

    def test_client_missing_binding_id_rejected(
        self, peer: McpBindingLegacy20241105
    ):
        params = legacy_initialize_params(include_binding_id=False)
        resp = peer.handle(make_request("initialize", params=params))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["code"] == ERR_INVALID_PARAMS
        assert resp.error["data"]["reason"] == "binding_name_required"
        assert resp.error["data"]["expected"] == BINDING_ID
        assert peer.phase is SessionPhase.UNINITIALIZED

    def test_client_nested_form_with_binding_accepted(
        self, peer: McpBindingLegacy20241105
    ):
        params = legacy_initialize_params(form="nested", include_binding_id=True)
        resp = peer.handle(make_request("initialize", params=params))
        assert resp.ok, resp.error
        assert peer.negotiated_client_binding == BINDING_ID

    def test_client_experimental_form_with_binding_accepted(
        self, peer: McpBindingLegacy20241105
    ):
        params = legacy_initialize_params(
            form="experimental",
            include_binding_id=True,
            profiles=["mcp++/mcp-idl"],
        )
        resp = peer.handle(make_request("initialize", params=params))
        assert resp.ok, resp.error
        assert peer.negotiated_client_binding == BINDING_ID
        assert "mcp++/mcp-idl" in peer.negotiated_profiles

    def test_server_initialize_result_must_advertise_binding(
        self, peer: McpBindingLegacy20241105
    ):
        resp = peer.handle(
            make_request("initialize", params=legacy_initialize_params())
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        assert (
            resp.result["capabilities"]["mcp++"]["bindingId"] == BINDING_ID
        ), "MCP++ 1.0 legacy servers must advertise binding id"

    def test_server_omitting_binding_id_is_detectably_nonconformant(self):
        """
        Spec: servers that claim MCP++ must not omit the binding name.
        Reference peer can be configured non-conformant for the assertion.
        """
        peer = McpBindingLegacy20241105(omit_server_binding_id=True)
        resp = peer.handle(
            make_request("initialize", params=legacy_initialize_params())
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        mcpp = resp.result["capabilities"]["mcp++"]
        assert "bindingId" not in mcpp
        # Conformance check used by MCP++ 1.0 claims:
        assert not server_advertises_required_binding(resp.result)

    def test_conformant_server_passes_binding_advertisement_check(
        self, peer: McpBindingLegacy20241105
    ):
        resp = peer.handle(
            make_request("initialize", params=legacy_initialize_params())
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        assert server_advertises_required_binding(resp.result)

    def test_current_binding_id_on_initialize_rejected(
        self, peer: McpBindingLegacy20241105
    ):
        params = legacy_initialize_params(binding_id=CURRENT_BINDING_ID)
        resp = peer.handle(make_request("initialize", params=params))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] == "binding_id_mismatch"
        assert resp.error["data"]["expected"] == BINDING_ID
        assert resp.error["data"]["requested"] == CURRENT_BINDING_ID


class TestVersionFailClosed:
    @pytest.fixture
    def peer(self) -> McpBindingLegacy20241105:
        return McpBindingLegacy20241105()

    def test_missing_protocol_version_rejected(
        self, peer: McpBindingLegacy20241105
    ):
        params = legacy_initialize_params()
        del params["protocolVersion"]
        resp = peer.handle(make_request("initialize", params=params))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["code"] == ERR_INVALID_PARAMS

    def test_modern_protocol_version_on_legacy_path_rejected(
        self, peer: McpBindingLegacy20241105
    ):
        params = legacy_initialize_params(
            protocol_version=CURRENT_PROTOCOL_VERSION
        )
        resp = peer.handle(make_request("initialize", params=params))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["code"] == ERR_UNSUPPORTED_PROTOCOL_VERSION
        assert resp.error["data"]["supported"] == [PROTOCOL_VERSION]
        assert resp.error["data"]["requested"] == CURRENT_PROTOCOL_VERSION
        assert resp.error["data"]["bindingId"] == BINDING_ID

    def test_unknown_protocol_version_rejected(
        self, peer: McpBindingLegacy20241105
    ):
        params = legacy_initialize_params(protocol_version="1900-01-01")
        resp = peer.handle(make_request("initialize", params=params))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["code"] == ERR_UNSUPPORTED_PROTOCOL_VERSION


class TestProfileNegotiation:
    @pytest.fixture
    def peer(self) -> McpBindingLegacy20241105:
        return McpBindingLegacy20241105(
            profiles={"mcp++/mcp-idl", "mcp++/cid-envelope", "mcp++/event-dag"}
        )

    def test_profile_intersection(self, peer: McpBindingLegacy20241105):
        params = legacy_initialize_params(
            profiles=["mcp++/cid-envelope", "mcp++/ucan"]
        )
        resp = peer.handle(make_request("initialize", params=params))
        assert resp.ok, resp.error
        # Intersection: only cid-envelope is offered by both
        assert peer.negotiated_profiles == {"mcp++/cid-envelope"}

    def test_server_lists_its_profiles_with_binding(
        self, peer: McpBindingLegacy20241105
    ):
        resp = peer.handle(
            make_request("initialize", params=legacy_initialize_params())
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        advertised = set(resp.result["capabilities"]["mcp++"]["profiles"])
        assert advertised == peer.profiles
        assert resp.result["capabilities"]["mcp++"]["bindingId"] == BINDING_ID


class TestLibp2pIsNotInitialize:
    def test_carriage_handshake_does_not_substitute_for_initialize(self):
        peer = McpBindingLegacy20241105()
        carriage = {"streamProtocolId": "/mcp+p2p/1.0.0", "negotiated": True}
        assert carriage["negotiated"] is True

        # Stream open alone is insufficient.
        listed = peer.handle(make_request("tools/list", req_id=1, params={}))
        assert not listed.ok
        assert listed.error is not None
        assert listed.error["data"]["reason"] == "not_initialized"

        # Full MCP initialize still required.
        assert open_legacy_session(peer).ok
        listed2 = peer.handle(make_request("tools/list", req_id=2, params={}))
        assert listed2.ok, listed2.error


class TestInterfaceSurface:
    def test_interface_constants(self):
        assert BINDING_ID == "mcp-binding/legacy-2024-11-05"
        assert PROTOCOL_VERSION == "2024-11-05"
        assert all(k.startswith("mcp++/") for k in ABSTRACT_PROFILE_KEYS)

    def test_legacy_only_peer_does_not_claim_current_version(self):
        peer = McpBindingLegacy20241105()
        resp = peer.handle(
            make_request("initialize", params=legacy_initialize_params())
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        assert resp.result["protocolVersion"] == PROTOCOL_VERSION
        assert resp.result["protocolVersion"] != CURRENT_PROTOCOL_VERSION
        assert (
            resp.result["capabilities"]["mcp++"]["bindingId"] != CURRENT_BINDING_ID
        )


# ---------------------------------------------------------------------------
# Conformance helpers (binding advertisement)
# ---------------------------------------------------------------------------


def server_advertises_required_binding(initialize_result: Dict[str, Any]) -> bool:
    """
    Return True if InitializeResult satisfies mandatory binding-name rule.

    Preferred form: capabilities.mcp++.bindingId == BINDING_ID
    Equivalent: capabilities.experimental['mcp++/bindingId'] == BINDING_ID
    """
    caps = initialize_result.get("capabilities")
    if not isinstance(caps, dict):
        return False
    nested = caps.get("mcp++")
    if isinstance(nested, dict) and nested.get("bindingId") == BINDING_ID:
        return True
    experimental = caps.get("experimental")
    if isinstance(experimental, dict):
        if experimental.get("mcp++/bindingId") == BINDING_ID:
            return True
    return False

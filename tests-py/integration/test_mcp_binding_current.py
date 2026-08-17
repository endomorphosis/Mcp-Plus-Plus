"""
Integration tests for the current MCP binding: mcp-binding/2026-07-28.

Spec: docs/spec/bindings/mcp-2026-07-28.md
Interface: McpBinding20260728@1
Task: MCPP-021

Acceptance:
  - A current client works without initialize.
  - initialize-as-current is rejected.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pytest

# ---------------------------------------------------------------------------
# Constants (McpBinding20260728@1)
# ---------------------------------------------------------------------------

BINDING_ID = "mcp-binding/2026-07-28"
PROTOCOL_VERSION = "2026-07-28"

META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CLIENT_CAPS = "io.modelcontextprotocol/clientCapabilities"
META_CLIENT_INFO = "io.modelcontextprotocol/clientInfo"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"
META_BINDING_ID = "io.mcplusplus/bindingId"

EXT_TASKS = "io.modelcontextprotocol/tasks"
EXT_PROFILES = "io.mcplusplus/profiles"

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
ERR_UNSUPPORTED_PROTOCOL_VERSION = -32022

SPEC_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "spec"
    / "bindings"
    / "mcp-2026-07-28.md"
)


# ---------------------------------------------------------------------------
# Reference peer: current-only MCP 2026-07-28 binding
# ---------------------------------------------------------------------------


@dataclass
class BindingResponse:
    """JSON-RPC style response for the reference peer."""

    id: Any
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.result is not None

    def as_jsonrpc(self) -> Dict[str, Any]:
        body: Dict[str, Any] = {"jsonrpc": "2.0", "id": self.id}
        if self.error is not None:
            body["error"] = self.error
        else:
            body["result"] = self.result
        return body


@dataclass
class McpBinding20260728:
    """
    Current-only reference peer for mcp-binding/2026-07-28 (McpBinding20260728@1).

    Implements:
      - per-request _meta validation
      - server/discover
      - tools/list and tools/call without any initialize
      - fail-closed rejection of initialize / notifications/initialized
      - profile advertisement via discover and per-request caps
      - StateRef mapping for multi-request handles
      - MCP Tasks → MCP++ artifact mapping sketch
    """

    server_name: str = "mcp++-current-ref"
    server_version: str = "1.0.0"
    profiles: Set[str] = field(
        default_factory=lambda: {
            "mcp++/mcp-idl",
            "mcp++/cid-envelope",
            "mcp++/event-dag",
        }
    )
    tools: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Explicit application state (never inferred from connection)
    state_store: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Task id → MCP++ artifact references
    tasks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Observability for tests
    initialize_calls: int = 0
    request_count: int = 0

    def __post_init__(self) -> None:
        if not self.tools:
            self.tools = {
                "echo": {
                    "name": "echo",
                    "description": "Echo arguments (current binding smoke tool)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                    },
                }
            }

    # -- public API ---------------------------------------------------------

    def handle(self, message: Dict[str, Any]) -> BindingResponse:
        """Dispatch one JSON-RPC message. Stateless: no prior initialize."""
        self.request_count += 1
        msg_id = message.get("id")

        if message.get("jsonrpc") != "2.0":
            return self._error(msg_id, ERR_INVALID_PARAMS, "jsonrpc must be '2.0'")

        method = message.get("method")
        if not method or not isinstance(method, str):
            return self._error(msg_id, ERR_INVALID_PARAMS, "missing method")

        # Forbidden on current binding (initialize-as-current rejected).
        if method == "initialize":
            self.initialize_calls += 1
            return self._reject_initialize(msg_id)
        if method == "notifications/initialized" or method == "initialized":
            self.initialize_calls += 1
            return self._reject_initialize(
                msg_id,
                message=(
                    "notifications/initialized is not supported under "
                    f"{BINDING_ID}"
                ),
            )

        params = message.get("params") or {}
        if not isinstance(params, dict):
            return self._error(msg_id, ERR_INVALID_PARAMS, "params must be an object")

        meta_err = self._validate_request_meta(params)
        if meta_err is not None:
            code, msg, data = meta_err
            return self._error(msg_id, code, msg, data=data)

        if method == "server/discover":
            return BindingResponse(id=msg_id, result=self._discover_result())
        if method == "tools/list":
            return BindingResponse(id=msg_id, result=self._tools_list_result())
        if method == "tools/call":
            return self._tools_call(msg_id, params)
        if method == "tasks/get":
            return self._tasks_get(msg_id, params)
        if method == "state/get":
            return self._state_get(msg_id, params)

        return self._error(msg_id, ERR_METHOD_NOT_FOUND, f"Method not found: {method}")

    # -- helpers ------------------------------------------------------------

    def _server_meta(self) -> Dict[str, Any]:
        return {
            META_SERVER_INFO: {
                "name": self.server_name,
                "version": self.server_version,
            },
            META_BINDING_ID: BINDING_ID,
        }

    def _discover_result(self) -> Dict[str, Any]:
        profile_map = {k: True for k in sorted(self.profiles)}
        return {
            "resultType": "complete",
            "supportedVersions": [PROTOCOL_VERSION],
            "capabilities": {
                "tools": {},
                "extensions": {
                    EXT_TASKS: {},
                    EXT_PROFILES: profile_map,
                },
                "mcp++": {
                    "bindingId": BINDING_ID,
                    "profiles": sorted(self.profiles),
                },
            },
            "_meta": self._server_meta(),
        }

    def _tools_list_result(self) -> Dict[str, Any]:
        return {
            "resultType": "complete",
            "tools": list(self.tools.values()),
            "_meta": self._server_meta(),
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
        # Optional state handle → StateRef discipline (§9)
        state_handle = params.get("stateHandle")
        state_ref = None
        if state_handle is not None:
            state_ref = self._resolve_or_create_state_ref(str(state_handle), text)

        # MCP Tasks → MCP++ artifacts when long-running path requested
        task_id = params.get("taskId")
        artifacts = None
        if task_id is not None:
            artifacts = self._bind_task_to_artifacts(str(task_id), name, text)

        result: Dict[str, Any] = {
            "resultType": "complete",
            "content": [{"type": "text", "text": str(text)}],
            "_meta": self._server_meta(),
        }
        if state_ref is not None:
            result["stateRef"] = state_ref
        if artifacts is not None:
            result["artifacts"] = artifacts
        return BindingResponse(id=msg_id, result=result)

    def _resolve_or_create_state_ref(
        self, handle: str, note: str
    ) -> Dict[str, Any]:
        """Map an explicit state handle to a StateRef@1-shaped object."""
        existing = self.state_store.get(handle)
        if existing is None:
            ref = {
                "mode": "single_authority",
                "ref": f"urn:mcpp:state:{handle}",
                "version": 1,
                "bindingId": BINDING_ID,
                "note": note,
            }
            self.state_store[handle] = ref
            return copy.deepcopy(ref)
        # CAS-style bump on revisit (still explicit handle, not connection state)
        existing = dict(existing)
        existing["version"] = int(existing.get("version", 0)) + 1
        existing["note"] = note
        self.state_store[handle] = existing
        return copy.deepcopy(existing)

    def _bind_task_to_artifacts(
        self, task_id: str, tool_name: str, text: str
    ) -> Dict[str, Any]:
        """Map MCP Tasks id to MCP++ Profile B-style artifact references."""
        # Deterministic fake CIDs for the reference peer (shape only).
        receipt_cid = f"bafyrei{task_id.replace('-', '')[:32].ljust(32, 'a')}"
        output_cid = f"bafyreiout{task_id.replace('-', '')[:29].ljust(29, 'b')}"
        record = {
            "taskId": task_id,
            "extension": EXT_TASKS,
            "tool": tool_name,
            "output_cid": output_cid,
            "receipt_cid": receipt_cid,
            "bindingId": BINDING_ID,
            "summary": text,
        }
        self.tasks[task_id] = record
        return copy.deepcopy(record)

    def _tasks_get(self, msg_id: Any, params: Dict[str, Any]) -> BindingResponse:
        task_id = params.get("taskId") or params.get("id")
        if not task_id or str(task_id) not in self.tasks:
            return self._error(msg_id, ERR_INVALID_PARAMS, "unknown taskId")
        record = copy.deepcopy(self.tasks[str(task_id)])
        return BindingResponse(
            id=msg_id,
            result={
                "resultType": "complete",
                "status": "completed",
                "artifacts": record,
                "_meta": self._server_meta(),
            },
        )

    def _state_get(self, msg_id: Any, params: Dict[str, Any]) -> BindingResponse:
        handle = params.get("stateHandle")
        if not handle or str(handle) not in self.state_store:
            return self._error(msg_id, ERR_INVALID_PARAMS, "unknown stateHandle")
        return BindingResponse(
            id=msg_id,
            result={
                "resultType": "complete",
                "stateRef": copy.deepcopy(self.state_store[str(handle)]),
                "_meta": self._server_meta(),
            },
        )

    def _validate_request_meta(
        self, params: Dict[str, Any]
    ) -> Optional[tuple]:
        meta = params.get("_meta")
        if not isinstance(meta, dict):
            return (
                ERR_INVALID_PARAMS,
                "missing required params._meta",
                {"missing": [META_PROTOCOL_VERSION, META_CLIENT_CAPS]},
            )

        version = meta.get(META_PROTOCOL_VERSION)
        if version is None:
            return (
                ERR_INVALID_PARAMS,
                f"missing required _meta key {META_PROTOCOL_VERSION}",
                {"missing": [META_PROTOCOL_VERSION]},
            )
        if version != PROTOCOL_VERSION:
            return (
                ERR_UNSUPPORTED_PROTOCOL_VERSION,
                "Unsupported protocol version",
                {
                    "supported": [PROTOCOL_VERSION],
                    "requested": version,
                },
            )

        caps = meta.get(META_CLIENT_CAPS)
        if caps is None or not isinstance(caps, dict):
            return (
                ERR_INVALID_PARAMS,
                f"missing required _meta key {META_CLIENT_CAPS}",
                {"missing": [META_CLIENT_CAPS]},
            )

        # Fail closed on binding id forgery when the client asserts one.
        claimed = meta.get(META_BINDING_ID)
        if claimed is not None and claimed != BINDING_ID:
            return (
                ERR_INVALID_PARAMS,
                "binding id does not match current binding",
                {
                    "expected": BINDING_ID,
                    "requested": claimed,
                    "reason": "binding_id_mismatch",
                },
            )

        return None

    def _reject_initialize(
        self,
        msg_id: Any,
        message: Optional[str] = None,
    ) -> BindingResponse:
        return self._error(
            msg_id,
            ERR_METHOD_NOT_FOUND,
            message
            or f"initialize is not supported under {BINDING_ID}",
            data={
                "bindingId": BINDING_ID,
                "supportedVersions": [PROTOCOL_VERSION],
                "reason": "initialize_as_current_rejected",
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


def current_request_meta(
    *,
    client_name: str = "current-test-client",
    client_version: str = "1.0.0",
    capabilities: Optional[Dict[str, Any]] = None,
    profiles: Optional[List[str]] = None,
    include_binding_id: bool = True,
    protocol_version: str = PROTOCOL_VERSION,
) -> Dict[str, Any]:
    """Build per-request _meta for a modern current client (no initialize)."""
    caps: Dict[str, Any] = dict(capabilities or {})
    if profiles:
        extensions = dict(caps.get("extensions") or {})
        extensions[EXT_PROFILES] = {p: True for p in profiles}
        caps["extensions"] = extensions
        caps.setdefault("mcp++", {})
        if isinstance(caps["mcp++"], dict):
            caps["mcp++"] = dict(caps["mcp++"])
            caps["mcp++"]["profiles"] = list(profiles)
    meta: Dict[str, Any] = {
        META_PROTOCOL_VERSION: protocol_version,
        META_CLIENT_CAPS: caps,
        META_CLIENT_INFO: {"name": client_name, "version": client_version},
    }
    if include_binding_id:
        meta[META_BINDING_ID] = BINDING_ID
    return meta


def make_request(
    method: str,
    *,
    req_id: Any = 1,
    params: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    body_params = dict(params or {})
    if meta is not None:
        body_params["_meta"] = meta
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": body_params,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCurrentBindingSpecPresence:
    def test_spec_document_exists_and_names_binding(self):
        assert SPEC_PATH.is_file(), f"missing binding spec: {SPEC_PATH}"
        text = SPEC_PATH.read_text(encoding="utf-8")
        assert BINDING_ID in text
        assert PROTOCOL_VERSION in text
        assert "initialize" in text.lower()
        assert "McpBinding20260728@1" in text
        assert "server/discover" in text
        assert "StateRef" in text
        assert "io.modelcontextprotocol/tasks" in text


class TestCurrentClientWithoutInitialize:
    """Acceptance: a current client works without initialize."""

    @pytest.fixture
    def peer(self) -> McpBinding20260728:
        return McpBinding20260728()

    def test_tools_list_without_initialize(self, peer: McpBinding20260728):
        meta = current_request_meta()
        req = make_request("tools/list", req_id=10, meta=meta)
        resp = peer.handle(req)

        assert resp.ok, resp.error
        assert peer.initialize_calls == 0
        assert peer.request_count == 1
        assert resp.result is not None
        assert resp.result["resultType"] == "complete"
        tool_names = {t["name"] for t in resp.result["tools"]}
        assert "echo" in tool_names
        assert resp.result["_meta"][META_BINDING_ID] == BINDING_ID
        assert resp.result["_meta"][META_SERVER_INFO]["name"] == peer.server_name

    def test_tools_call_without_initialize(self, peer: McpBinding20260728):
        meta = current_request_meta(profiles=["mcp++/cid-envelope"])
        req = make_request(
            "tools/call",
            req_id=11,
            params={"name": "echo", "arguments": {"text": "hello-current"}},
            meta=meta,
        )
        resp = peer.handle(req)

        assert resp.ok, resp.error
        assert peer.initialize_calls == 0
        assert resp.result is not None
        assert resp.result["content"][0]["text"] == "hello-current"

    def test_multiple_independent_requests_no_session(
        self, peer: McpBinding20260728
    ):
        """Statelessness: each request stands alone; no initialize between."""
        for i, text in enumerate(("a", "b", "c"), start=1):
            req = make_request(
                "tools/call",
                req_id=i,
                params={"name": "echo", "arguments": {"text": text}},
                meta=current_request_meta(),
            )
            resp = peer.handle(req)
            assert resp.ok, resp.error
            assert resp.result is not None
            assert resp.result["content"][0]["text"] == text
        assert peer.initialize_calls == 0
        assert peer.request_count == 3

    def test_server_discover_optional_before_work(self, peer: McpBinding20260728):
        discover = peer.handle(
            make_request(
                "server/discover",
                req_id="d1",
                meta=current_request_meta(),
            )
        )
        assert discover.ok, discover.error
        assert discover.result is not None
        assert PROTOCOL_VERSION in discover.result["supportedVersions"]
        assert discover.result["capabilities"]["mcp++"]["bindingId"] == BINDING_ID
        for key in peer.profiles:
            assert discover.result["capabilities"]["extensions"][EXT_PROFILES][key] is True

        # Work without ever calling initialize (discover is optional, not a handshake)
        work = peer.handle(
            make_request(
                "tools/list",
                req_id="w1",
                meta=current_request_meta(),
            )
        )
        assert work.ok, work.error
        assert peer.initialize_calls == 0

    def test_work_without_discover_or_initialize(self, peer: McpBinding20260728):
        """Official rule: discover is optional; inline RPC with _meta is enough."""
        resp = peer.handle(
            make_request(
                "tools/call",
                req_id=42,
                params={"name": "echo", "arguments": {"text": "inline"}},
                meta=current_request_meta(include_binding_id=False),
            )
        )
        assert resp.ok, resp.error
        assert peer.initialize_calls == 0


class TestInitializeAsCurrentRejected:
    """Acceptance: initialize-as-current is rejected."""

    @pytest.fixture
    def peer(self) -> McpBinding20260728:
        return McpBinding20260728()

    def test_initialize_rejected(self, peer: McpBinding20260728):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "legacy-shaped", "version": "0.1"},
            },
        }
        resp = peer.handle(req)

        assert not resp.ok
        assert resp.error is not None
        assert resp.error["code"] == ERR_METHOD_NOT_FOUND
        assert resp.error["data"]["reason"] == "initialize_as_current_rejected"
        assert resp.error["data"]["bindingId"] == BINDING_ID
        assert PROTOCOL_VERSION in resp.error["data"]["supportedVersions"]
        assert peer.initialize_calls == 1

    def test_initialize_claiming_modern_version_still_rejected(
        self, peer: McpBinding20260728
    ):
        """Forged initialize-as-current: modern version on initialize path."""
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "forged-current", "version": "1.0"},
                "_meta": current_request_meta(),
            },
        }
        resp = peer.handle(req)

        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] == "initialize_as_current_rejected"
        # Subsequent modern request still works (no partial session created)
        ok = peer.handle(
            make_request(
                "tools/list",
                req_id=3,
                meta=current_request_meta(),
            )
        )
        assert ok.ok, ok.error

    def test_notifications_initialized_rejected(self, peer: McpBinding20260728):
        req = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        resp = peer.handle(req)
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] == "initialize_as_current_rejected"


class TestMetaAndVersionFailClosed:
    @pytest.fixture
    def peer(self) -> McpBinding20260728:
        return McpBinding20260728()

    def test_missing_meta_rejected(self, peer: McpBinding20260728):
        req = make_request("tools/list", req_id=1, params={})
        # no _meta at all
        resp = peer.handle(req)
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["code"] == ERR_INVALID_PARAMS

    def test_missing_protocol_version_rejected(self, peer: McpBinding20260728):
        meta = current_request_meta()
        del meta[META_PROTOCOL_VERSION]
        resp = peer.handle(make_request("tools/list", meta=meta))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["code"] == ERR_INVALID_PARAMS

    def test_missing_client_capabilities_rejected(self, peer: McpBinding20260728):
        meta = current_request_meta()
        del meta[META_CLIENT_CAPS]
        resp = peer.handle(make_request("tools/list", meta=meta))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["code"] == ERR_INVALID_PARAMS

    def test_unsupported_protocol_version(self, peer: McpBinding20260728):
        meta = current_request_meta(protocol_version="1900-01-01")
        resp = peer.handle(make_request("tools/list", meta=meta))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["code"] == ERR_UNSUPPORTED_PROTOCOL_VERSION
        assert resp.error["data"]["supported"] == [PROTOCOL_VERSION]
        assert resp.error["data"]["requested"] == "1900-01-01"

    def test_legacy_protocol_version_on_current_path_rejected(
        self, peer: McpBinding20260728
    ):
        meta = current_request_meta(protocol_version="2024-11-05")
        resp = peer.handle(make_request("tools/list", meta=meta))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["code"] == ERR_UNSUPPORTED_PROTOCOL_VERSION

    def test_binding_id_mismatch_rejected(self, peer: McpBinding20260728):
        meta = current_request_meta()
        meta[META_BINDING_ID] = "mcp-binding/legacy-2024-11-05"
        resp = peer.handle(make_request("tools/list", meta=meta))
        assert not resp.ok
        assert resp.error is not None
        assert resp.error["data"]["reason"] == "binding_id_mismatch"


class TestStateRefAndTasksMapping:
    @pytest.fixture
    def peer(self) -> McpBinding20260728:
        return McpBinding20260728()

    def test_state_handle_maps_to_state_ref(self, peer: McpBinding20260728):
        meta = current_request_meta(profiles=["mcp++/cid-envelope"])
        resp = peer.handle(
            make_request(
                "tools/call",
                req_id=1,
                params={
                    "name": "echo",
                    "arguments": {"text": "v1"},
                    "stateHandle": "sh-alpha",
                },
                meta=meta,
            )
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        state_ref = resp.result["stateRef"]
        assert state_ref["mode"] == "single_authority"
        assert state_ref["ref"].startswith("urn:mcpp:state:")
        assert state_ref["version"] == 1
        assert state_ref["bindingId"] == BINDING_ID

        # Same handle on a later request is still explicit (not connection session)
        resp2 = peer.handle(
            make_request(
                "tools/call",
                req_id=2,
                params={
                    "name": "echo",
                    "arguments": {"text": "v2"},
                    "stateHandle": "sh-alpha",
                },
                meta=meta,
            )
        )
        assert resp2.ok, resp2.error
        assert resp2.result is not None
        assert resp2.result["stateRef"]["version"] == 2

        got = peer.handle(
            make_request(
                "state/get",
                req_id=3,
                params={"stateHandle": "sh-alpha"},
                meta=meta,
            )
        )
        assert got.ok, got.error
        assert got.result is not None
        assert got.result["stateRef"]["version"] == 2

    def test_mcp_task_maps_to_mcpp_artifacts(self, peer: McpBinding20260728):
        meta = current_request_meta(
            profiles=["mcp++/cid-envelope", "mcp++/event-dag"],
            capabilities={
                "extensions": {EXT_TASKS: {}},
            },
        )
        resp = peer.handle(
            make_request(
                "tools/call",
                req_id=1,
                params={
                    "name": "echo",
                    "arguments": {"text": "task-body"},
                    "taskId": "task-001",
                },
                meta=meta,
            )
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        artifacts = resp.result["artifacts"]
        assert artifacts["extension"] == EXT_TASKS
        assert artifacts["output_cid"].startswith("bafyrei")
        assert artifacts["receipt_cid"].startswith("bafyrei")
        assert artifacts["bindingId"] == BINDING_ID

        polled = peer.handle(
            make_request(
                "tasks/get",
                req_id=2,
                params={"taskId": "task-001"},
                meta=meta,
            )
        )
        assert polled.ok, polled.error
        assert polled.result is not None
        assert polled.result["status"] == "completed"
        assert polled.result["artifacts"]["receipt_cid"] == artifacts["receipt_cid"]


class TestLibp2pIsNotInitialize:
    def test_carriage_handshake_does_not_imply_mcp_initialize(self):
        """
        Profile E / libp2p stream open is carriage only.
        A current peer still requires modern _meta and still rejects initialize.
        """
        peer = McpBinding20260728()
        # Simulate: stream negotiated (/mcp+p2p/1.0.0) then first MCP message.
        carriage = {"streamProtocolId": "/mcp+p2p/1.0.0", "negotiated": True}
        assert carriage["negotiated"] is True

        # Opening the stream must not allow initialize-as-current.
        init_resp = peer.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                },
            }
        )
        assert not init_resp.ok
        assert init_resp.error is not None
        assert init_resp.error["data"]["reason"] == "initialize_as_current_rejected"

        # First application message with _meta succeeds without initialize.
        work = peer.handle(
            make_request(
                "tools/list",
                req_id=2,
                meta=current_request_meta(),
            )
        )
        assert work.ok, work.error
        assert peer.initialize_calls == 1  # only the rejected attempt


class TestInterfaceSurface:
    def test_interface_constants(self):
        assert BINDING_ID == "mcp-binding/2026-07-28"
        assert PROTOCOL_VERSION == "2026-07-28"
        assert all(k.startswith("mcp++/") for k in ABSTRACT_PROFILE_KEYS)

    def test_discover_advertises_only_current_version(self):
        peer = McpBinding20260728()
        resp = peer.handle(
            make_request("server/discover", meta=current_request_meta())
        )
        assert resp.ok, resp.error
        assert resp.result is not None
        assert resp.result["supportedVersions"] == [PROTOCOL_VERSION]
        # Current-only peer does not advertise initialize-era versions.
        assert "2024-11-05" not in resp.result["supportedVersions"]

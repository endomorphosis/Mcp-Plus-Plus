# Binding compatibility matrix (`BindingCompatibilityMatrix@1`)

**Status:** Normative (MCP++ 1.0 dual-binding peer proofs)  
**Task:** MCPP-022  
**Interface label:** `BindingCompatibilityMatrix@1`  
**Authority:** ADR-0006 (Accepted); plan KD-3; gates 2–5; MCPP-G030  
**Parent index:** [README.md](README.md)  
**Binding modules:** [mcp-legacy-2024-11-05.md](mcp-legacy-2024-11-05.md) · [mcp-2026-07-28.md](mcp-2026-07-28.md)

## 1. Purpose

This document is the **compatibility matrix** for MCP++ 1.0 MCP application
bindings. It proves, in one place, how peers behave under:

| Cell | Meaning |
| --- | --- |
| **Legacy-only** | Peer offers only `mcp-binding/legacy-2024-11-05` |
| **Current-only** | Peer offers only `mcp-binding/2026-07-28` |
| **Dual** | Peer advertises and implements both bindings |
| **Forged version** | Client asserts a version / binding id pair that is not honestly offered |
| **Downgrade** | Client silently switches from a negotiated stronger/current path to legacy without re-advertisement |

Abstract Profiles A–H stay MCP-version-independent (ADR-0006 §1). This matrix
owns **path selection**, **advertisement**, and **fail-closed** outcomes only.

Integration evidence: `tests-py/integration/test_mcp_binding_compat.py`.

## 2. Normative keywords

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY**
are to be interpreted as described in RFC 2119.

## 3. Binding identity pins

| Binding id | `protocolVersion` | Lifecycle | Role |
| --- | --- | --- | --- |
| `mcp-binding/legacy-2024-11-05` | `2024-11-05` | `initialize` / `notifications/initialized` | Legacy |
| `mcp-binding/2026-07-28` | `2026-07-28` | Stateless per-request `_meta`; **no** initialize | Current |

A pair is **honest** only when the advertised binding id matches the version
and lifecycle used on that request path. Cross-pairing is forgery (see §7).

## 4. Peer offer modes

A peer **MUST** operate in exactly one of the following offer modes for a given
listener / connection advertisement surface (a dual peer **MAY** still expose
both paths on one process).

| Mode id | Offered bindings | Advertisement requirement |
| --- | --- | --- |
| `legacy-only` | `{legacy}` | **MUST** name `mcp-binding/legacy-2024-11-05` on initialize when claiming MCP++ 1.0 |
| `current-only` | `{current}` | **MUST** name `mcp-binding/2026-07-28` on discover / result `_meta` when claiming MCP++ 1.0 |
| `dual` | `{legacy, current}` | **MUST** list **both** binding ids and both supported protocol versions |

Dual is the intended migration path (ADR-0006 §2: both allowed). Dual support
**MUST NOT** collapse the two lifecycles into one ambiguous path.

### 4.1 Dual advertisement shape (normative sketch)

Dual peers **MUST** be able to expose both of:

1. **Legacy path:** `initialize` with `protocolVersion` `2024-11-05` and
   `capabilities.mcp++.bindingId` = `mcp-binding/legacy-2024-11-05` (or
   equivalent experimental key form from the legacy binding).
2. **Current path:** requests with
   `params._meta["io.modelcontextprotocol/protocolVersion"]` = `2026-07-28`
   and optional `params._meta["io.mcplusplus/bindingId"]` =
   `mcp-binding/2026-07-28`.

On dual `server/discover` (current path) and dual initialize results (legacy
path), the peer **MUST** advertise both supported versions and both binding
ids so clients can select without guessing.

Recommended dual discover fields (normative intent; field nesting may follow
the current binding document):

```json
{
  "supportedVersions": ["2026-07-28", "2024-11-05"],
  "supportedBindings": [
    "mcp-binding/2026-07-28",
    "mcp-binding/legacy-2024-11-05"
  ],
  "capabilities": {
    "mcp++": {
      "bindingIds": [
        "mcp-binding/2026-07-28",
        "mcp-binding/legacy-2024-11-05"
      ],
      "profiles": ["mcp++/mcp-idl", "mcp++/cid-envelope"]
    }
  }
}
```

## 5. Path selection algorithm (`BindingPathSelect@1`)

When a dual peer receives a JSON-RPC message, selection **MUST** be
deterministic:

| Priority | Condition | Selected path |
| --- | --- | --- |
| 1 | `method` is `initialize` or `notifications/initialized` / `initialized` | **Legacy path** (if legacy is offered; otherwise reject) |
| 2 | `params._meta` contains `io.modelcontextprotocol/protocolVersion` | **Current path** (if current is offered; otherwise reject) |
| 3 | Legacy session already open (`READY` / post-initialize) and no current `_meta` | **Legacy path** application methods |
| 4 | Otherwise | **Reject** fail-closed (`path_ambiguous` or method not found) |

Rules:

1. Discovery (`server/discover`) on dual peers uses the **current path** rules
   (requires modern `_meta`).
2. Opening a libp2p / `mcp+p2p` stream is **not** path selection; it is carriage
   only (bindings README §5).
3. A dual peer **MUST NOT** treat successful legacy initialize as proof of the
   current binding, or successful modern `_meta` work as an open legacy session.

## 6. Outcome matrix (positive cells)

Legend: **Accept** = successful JSON-RPC result (subject to ordinary param
validation). **Reject** = JSON-RPC error; no session / binding side effect that
would imply the forged path.

### 6.1 Client path × peer mode

| Client behavior | Legacy-only peer | Current-only peer | Dual peer |
| --- | --- | --- | --- |
| Honest legacy initialize `2024-11-05` + binding id | **Accept** | **Reject** (`initialize_as_current_rejected` / method not found) | **Accept** on legacy path; advertise dual support |
| Honest current request `_meta` `2026-07-28` (no initialize) | **Reject** (not offered / unsupported version or missing session) | **Accept** | **Accept** on current path |
| `server/discover` with current `_meta` | **Reject** or not offered | **Accept** | **Accept**; lists both bindings |
| Application RPC before any negotiation | **Reject** (`not_initialized`) | **Accept** if `_meta` valid | Current `_meta` → accept; bare legacy → reject |

### 6.2 Dual peer happy paths (normative)

A dual peer **MUST** allow both of the following on the same process (not
necessarily the same concurrent session state):

1. **Legacy-only client:** full initialize handshake then `tools/list` /
   `tools/call` without modern `_meta`.
2. **Current-only client:** `tools/list` / `tools/call` with modern `_meta` and
   **zero** `initialize` calls.

A dual peer **MAY** allow a client to **upgrade** from a completed legacy
session to the current path by sending an explicit current-path request with
honest `2026-07-28` `_meta` (re-advertisement by use of the current path).
That upgrade **MUST** not invent legacy session state for the current path.

## 7. Negative matrix (fail-closed)

All cells in this section **MUST** reject. Implementations **MUST NOT**
silently coerce, promote, or demote version / binding pairs.

### 7.1 Forged version

| Attack / mistake | Peer mode | Required outcome | Reason code (recommended) |
| --- | --- | --- | --- |
| `protocolVersion` unknown string on initialize | legacy-only, dual | Reject `-32022` | unsupported version |
| `protocolVersion` `2026-07-28` on initialize | legacy-only | Reject `-32022` | modern version on legacy path |
| `protocolVersion` `2026-07-28` on initialize | dual | Reject on legacy path (initialize remains legacy-lifecycle only) | `version_binding_mismatch` or unsupported on legacy path |
| `_meta` version `2024-11-05` on current-shaped request | current-only, dual | Reject `-32022` or invalid params | `forged_version` / unsupported |
| `_meta` version `2026-07-28` with binding id `mcp-binding/legacy-2024-11-05` | current-only, dual | Reject | `binding_id_mismatch` / `forged_version` |
| `_meta` version `2024-11-05` with binding id `mcp-binding/2026-07-28` | any offering current path | Reject | `forged_version` |
| initialize with legacy version but binding id `mcp-binding/2026-07-28` | legacy-only | Reject | `binding_id_mismatch` |
| initialize with legacy version but binding id `mcp-binding/2026-07-28` | dual | Reject (current binding id is not valid on initialize path) | `binding_id_mismatch` |
| Missing required `_meta` keys on current path | current-only, dual | Reject `-32602` | invalid params |
| Missing `protocolVersion` on initialize | legacy-only, dual | Reject `-32602` | invalid params |

### 7.2 Silent downgrade

**Silent downgrade** means: after the peer has an **active current binding**
for the connection / client context (a successful current-path request that
set the active binding to `mcp-binding/2026-07-28`), the client attempts to
use the legacy initialize lifecycle **without** an explicit dual re-bind
procedure that re-advertises and re-selects legacy.

| Sequence | Required outcome | Reason code (recommended) |
| --- | --- | --- |
| Current-path success → later `initialize` (legacy) without re-advertisement flag | **Reject** | `silent_downgrade_rejected` |
| Current-path success → bare legacy application method (no current `_meta`, no open legacy session) | **Reject** | `silent_downgrade_rejected` or path not available |
| Dual peer: client claims only current in advertisement then sends initialize as if current | **Reject** | initialize never becomes current behavior |

**Not** silent downgrade (allowed):

| Sequence | Outcome |
| --- | --- |
| Dual peer: legacy handshake success → later honest current `_meta` request | **Accept** (explicit upgrade / path switch) |
| Dual peer: two independent clients, one legacy and one current | **Accept** each on its path (no shared active binding) |
| Dual peer: fresh connection, client chooses legacy first | **Accept** |

A peer that has negotiated or declared a binding **MUST** reject silent
downgrade to a weaker or different binding without re-advertisement
(ADR-0006 §2 Downgrade rejection).

### 7.3 Mode exclusivity negatives

| Attempt | Required outcome |
| --- | --- |
| Current-only peer receives `initialize` | Reject (`initialize_as_current_rejected`) |
| Current-only peer receives `notifications/initialized` | Reject |
| Legacy-only peer receives current `_meta` with `2026-07-28` | Reject (current not offered) |
| Legacy-only peer is asked for dual `supportedBindings` containing current as if offered | **MUST NOT** claim current; advertisement is legacy-only |

## 8. Error payload conventions

Fail-closed errors **SHOULD** include machine-readable `error.data` fields so
conformance tests and clients can distinguish forgery from ordinary unknown
methods:

| Field | When |
| --- | --- |
| `reason` | Always for matrix negatives (`forged_version`, `binding_id_mismatch`, `silent_downgrade_rejected`, `initialize_as_current_rejected`, `binding_not_offered`, …) |
| `supported` / `supportedVersions` | Unsupported or forged protocol version |
| `supportedBindings` | Dual or mode advertisement on rejection of wrong path |
| `requested` | Client-asserted version or binding id |
| `expected` | Peer-required binding id for the selected path |
| `activeBinding` | Present on silent-downgrade rejections |

Exact JSON-RPC numeric codes follow the binding documents (`-32601`, `-32602`,
`-32022`, …). The **rejection** and the **reason** are normative for MCP++ 1.0
matrix claims; code numbers alone are not sufficient proof.

## 9. Full matrix checklist (`BindingCompatibilityMatrix@1`)

An implementation may claim interface **`BindingCompatibilityMatrix@1`** when
automated tests prove every row below.

| # | Scenario class | Scenario | Expected | Evidence locus |
| --- | --- | --- | --- | --- |
| 1 | Legacy-only | Honest `2024-11-05` initialize + tools | Accept | compat tests § legacy-only |
| 2 | Legacy-only | Current `_meta` request | Reject | compat tests § legacy-only |
| 3 | Legacy-only | Forged modern version on initialize | Reject | compat tests § forged |
| 4 | Current-only | Tools without initialize | Accept | compat tests § current-only |
| 5 | Current-only | `initialize` | Reject | compat tests § current-only |
| 6 | Current-only | Forged legacy version in `_meta` | Reject | compat tests § forged |
| 7 | Dual | Legacy client full handshake | Accept | compat tests § dual |
| 8 | Dual | Current client without initialize | Accept | compat tests § dual |
| 9 | Dual | Discover lists both bindings | Accept | compat tests § dual |
| 10 | Dual | Honest upgrade legacy → current | Accept | compat tests § dual |
| 11 | Forged version | Version / binding id cross-pair on current path | Reject | compat tests § forged |
| 12 | Forged version | Current binding id on initialize | Reject | compat tests § forged |
| 13 | Downgrade | Current active → silent initialize | Reject | compat tests § downgrade |
| 14 | Downgrade | Current active → bare legacy app method | Reject | compat tests § downgrade |

All **Reject** rows **MUST** leave the peer without accepting the forged or
downgraded binding as active.

## 10. Relationship to other tasks

| Artifact | Role |
| --- | --- |
| MCPP-020 `mcp-legacy-2024-11-05.md` + `test_mcp_binding_legacy.py` | Legacy path positive/negative primitives |
| MCPP-021 `mcp-2026-07-28.md` + `test_mcp_binding_current.py` | Current path positive/negative primitives |
| **This matrix + `test_mcp_binding_compat.py`** | Cross-mode, dual, forgery, and downgrade composition |
| MCPP-023 runtime adapters | Wire the same rules into accelerate/datasets servers |
| ADR-0006 | Decision authority for dual support and fail-closed |

## 11. Non-goals

- Redefining Profiles A–H object models.
- A2A extension wire identifiers (ADR-0006 §3; MCPP-054…057).
- Carriage-level libp2p protocol ID negotiation as a substitute for either
  MCP application path.
- Bulk golden JSON dumps per matrix cell (tests use compact peer recipes).

## 12. Conformance evidence

| Artifact | Role |
| --- | --- |
| This document | Normative matrix `BindingCompatibilityMatrix@1` |
| `tests-py/integration/test_mcp_binding_compat.py` | Integration proof for all matrix cells |
| `tests-py/integration/test_mcp_binding_legacy.py` | Legacy-only primitive evidence |
| `tests-py/integration/test_mcp_binding_current.py` | Current-only primitive evidence |
| ADR-0006 | Dual-binding and fail-closed decision |
| [README.md](README.md) | Binding inventory index |

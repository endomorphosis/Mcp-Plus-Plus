# MCP binding: `mcp-binding/legacy-2024-11-05` (legacy)

**Status:** Normative (MCP++ 1.0 legacy MCP application binding)  
**Task:** MCPP-020  
**Authority:** ADR-0006 (Accepted); plan KD-2, KD-3; gates 2–5; MCPP-G030  
**MCP revision:** `2024-11-05` (initialize-era family as documented here)  
**Binding id:** `mcp-binding/legacy-2024-11-05`  
**Interface label:** `McpBindingLegacy20241105@1`  
**Primary sources:** Historical MCP initialize lifecycle; in-tree pin
`conformance/vectors/initialize_result.json`; ADR-0006 dual-binding rules;
parent index [README.md](README.md)  
**Sibling (current):** [mcp-2026-07-28.md](mcp-2026-07-28.md)  
**Parent index:** [README.md](README.md) · Abstract profiles: [../mcp++-profiles-draft.md](../mcp++-profiles-draft.md)

## 1. Purpose

This document is the **legacy** MCP application binding for MCP++ 1.0. It maps
abstract Profiles A–H onto the initialize-era MCP revision family whose
canonical pin is `protocolVersion` **`2024-11-05`**:

- Session lifecycle uses `initialize` then `notifications/initialized`.
- Client and server capabilities (including MCP++ profile keys) are negotiated
  on the initialize exchange.
- The binding id **`mcp-binding/legacy-2024-11-05` is mandatory** whenever a peer
  offers or accepts this initialize-era path under MCP++ 1.0 claims.
- Existing vectors such as `initialize_result.json` remain readable under this
  binding; they do **not** prove the current binding.

This binding does **not** redefine Profile A–H object models, CID rules, UCAN
validation, policy evaluation, Event DAG structure, or payment objects. Those
remain in the abstract profile registry and profile chapters.

## 2. Normative keywords

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY**
are to be interpreted as described in RFC 2119.

## 3. Identity

| Field | Value |
| --- | --- |
| Binding id | `mcp-binding/legacy-2024-11-05` |
| MCP `protocolVersion` | `2024-11-05` (pin); see §5 for family notes |
| Lifecycle | Session `initialize` / `notifications/initialized` |
| Role | **Legacy.** Required name when offering initialize-era behavior |
| Interface | `McpBindingLegacy20241105@1` |

A peer that claims this binding id **MUST** implement the rules in this
document. Dual-era peers that also offer the modern path **MUST** name that
path as `mcp-binding/2026-07-28` (see that binding document); they **MUST NOT**
treat initialize as current-binding behavior.

**Explicit naming (normative).** Supporting initialize without advertising
`mcp-binding/legacy-2024-11-05` is **non-conformant** for MCP++ 1.0 claims
(ADR-0006; bindings README §3 rule 2).

## 4. Lifecycle (normative)

### 4.1 Session handshake

Under this binding the application session is established as follows:

```
Client → Server: initialize          (request; params include protocolVersion,
                                      capabilities, clientInfo)
Server → Client: InitializeResult    (result; protocolVersion, capabilities,
                                      serverInfo; MCP++ binding id mandatory)
Client → Server: notifications/initialized  (notification; no response body
                                              required)
```

Order rules:

1. The client **MUST** send `initialize` before other application methods on
   this session path (except transport-level pings if the carriage allows them
   outside the MCP session — see §10).
2. The server **MUST** reply with a successful `InitializeResult` (or a
   JSON-RPC error) before treating the session as open for profile methods.
3. After a successful `InitializeResult`, the client **MUST** send
   `notifications/initialized` before relying on full session semantics for
   subsequent work. Servers **MAY** accept a single post-initialize application
   method before `notifications/initialized` only for diagnostic tolerance;
   MCP++ 1.0 legacy conformance tests require the notification.
4. Until initialize succeeds, application methods such as `tools/list` and
   `tools/call` **MUST** be rejected (or fail closed) as unnegotiated session
   use under this binding.

### 4.2 Initialize request

Clients send:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {},
      "experimental": {},
      "mcp++": {
        "bindingId": "mcp-binding/legacy-2024-11-05",
        "profiles": ["mcp++/mcp-idl", "mcp++/cid-envelope"]
      }
    },
    "clientInfo": {
      "name": "example-legacy-client",
      "version": "1.0.0"
    }
  }
}
```

| Field | Requirement |
| --- | --- |
| `params.protocolVersion` | **MUST** be present. For this binding pin, **MUST** be `2024-11-05` (or an accepted initialize-era synonym documented in §5). |
| `params.capabilities` | **MUST** be an object (may be empty for baseline MCP-only). |
| `params.clientInfo` | **SHOULD** be `{name, version}`. |
| MCP++ binding id in capabilities | **MUST** be present when the client claims MCP++ 1.0 under this binding (see §6). |

### 4.3 Initialize result

Servers return at least:

| Field | Requirement |
| --- | --- |
| `protocolVersion` | Negotiated version; for the pin, `2024-11-05` |
| `capabilities` | Server capability map |
| `serverInfo` | `{name, version}` |

Historical pin shape (`conformance/vectors/initialize_result.json`):

```json
{
  "protocolVersion": "2024-11-05",
  "capabilities": {
    "tools": {"listChanged": true},
    "experimental": {}
  },
  "serverInfo": {
    "name": "mcp++",
    "version": "1.0.0"
  }
}
```

That vector remains **readable**. MCP++ 1.0 servers that claim this binding
**MUST** additionally advertise the binding id in capabilities as specified in
§6 (the pin may omit it for historical readability; new implementations
**MUST NOT** omit the binding name).

### 4.4 `notifications/initialized`

After accepting `InitializeResult`, the client **MUST** send:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized",
  "params": {}
}
```

This is a JSON-RPC notification (no `id`). Servers **MUST NOT** require a
result body. After this notification, the session is fully open for negotiated
methods.

### 4.5 Session scope

1. The open session is tied to the negotiated binding id and protocol version
   from initialize—not to an implicit current-binding claim.
2. Application state that spans requests **MAY** use session context under this
   binding (unlike the current binding’s pure per-request `_meta` model).
3. Peers that later speak only `mcp-binding/2026-07-28` on the same connection
   **MUST** re-advertise and re-negotiate; silent reinterpretation of an
   initialize session as current-binding is forbidden (MCPP-022 matrices).

## 5. Protocol version acceptance

| Condition | Server behavior |
| --- | --- |
| `protocolVersion` is `2024-11-05` and this binding is offered | Accept (subject to other validation) |
| `protocolVersion` missing | Reject `-32602` (Invalid params) |
| `protocolVersion` is a modern revision (e.g. `2026-07-28`) on this legacy path | Reject fail-closed (version / binding mismatch); do not silently promote to current binding |
| `protocolVersion` is an unknown string | Reject with unsupported-version style error listing supported initialize-era versions |

**Family note (informative):** ADR-0006 allows the legacy binding document to
cover initialize-era family semantics through later initialize-era dates as
documented here. The **normative pin** for MCP++ 1.0 legacy vectors and tests
is `2024-11-05`. Additional initialize-era versions **MAY** be accepted only
when the server lists them under supported versions **and** still advertises
`mcp-binding/legacy-2024-11-05` (not the current binding id).

Unsupported version error shape (recommended):

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32022,
    "message": "Unsupported protocol version",
    "data": {
      "supported": ["2024-11-05"],
      "requested": "<client version>",
      "bindingId": "mcp-binding/legacy-2024-11-05"
    }
  }
}
```

## 6. Mandatory binding name in capability advertisement

### 6.1 Rule

When a peer offers or accepts the initialize-era path under MCP++ 1.0, it
**MUST** name the binding explicitly as:

```
mcp-binding/legacy-2024-11-05
```

| Locus | Requirement |
| --- | --- |
| Client `initialize` params | **MUST** include the binding id when claiming MCP++ 1.0 |
| Server `InitializeResult.capabilities` | **MUST** include the binding id when claiming MCP++ 1.0 |
| Subsequent capability dumps / list APIs on this session | **MUST** continue to carry the same binding id |

**Missing binding name is non-conformant.** A server that completes initialize
with MCP++ profile keys (or MCP++ branding) but without the binding id **MUST**
be treated as failing MCP++ 1.0 legacy-binding claims. A client that omits the
binding id while claiming MCP++ profiles **MUST** be rejected by a conforming
MCP++ 1.0 legacy server (fail closed).

### 6.2 Placement (normative forms)

Peers **MUST** use at least one of the following equivalent placements. Servers
that claim MCP++ 1.0 **MUST** emit form (1) on `InitializeResult`; they
**SHOULD** also accept form (2) on client initialize.

**(1) Nested `mcp++` object (preferred):**

```json
{
  "capabilities": {
    "tools": {"listChanged": true},
    "experimental": {},
    "mcp++": {
      "bindingId": "mcp-binding/legacy-2024-11-05",
      "profiles": ["mcp++/mcp-idl", "mcp++/cid-envelope"]
    }
  }
}
```

**(2) Experimental map with explicit binding key:**

```json
{
  "capabilities": {
    "experimental": {
      "mcp++/bindingId": "mcp-binding/legacy-2024-11-05",
      "mcp++/mcp-idl": true,
      "mcp++/cid-envelope": true
    }
  }
}
```

Documented aliases that expand to `mcp-binding/legacy-2024-11-05` **MAY** be
accepted only if the expansion is specified in this document. No alias is
defined for MCP++ 1.0 beyond the exact id string.

### 6.3 Forgery and mismatch

| Condition | Behavior |
| --- | --- |
| Client claims `mcp-binding/2026-07-28` on `initialize` | Reject fail-closed (`binding_id_mismatch` or equivalent) |
| Client claims unknown binding id | Reject fail-closed |
| Client claims legacy binding id with modern-only protocol version | Reject fail-closed |
| Server omits binding id while advertising MCP++ profiles | Non-conformant server |

## 7. Profile capability placement (normative)

Abstract profile keys are defined in the parent registry and are
**MCP-version-independent**:

| Key | Profile |
| --- | --- |
| `mcp++/mcp-idl` | A |
| `mcp++/cid-envelope` | B |
| `mcp++/ucan` | C |
| `mcp++/deontic-policy` | D |
| `mcp++/p2p-transport` | E (optional transport) |
| `mcp++/event-dag` | F |
| `mcp++/risk-scheduling` | G |
| `mcp++/x402-payments` | H |

### 7.1 Client advertisement (initialize)

Under this binding, profile support the client wishes to use **MUST** be present
on `initialize` when those profiles will be used on the session. Placement
**MUST** be one of:

1. **Preferred:** `params.capabilities["mcp++"].profiles` as a list (or map) of
   abstract keys, with `params.capabilities["mcp++"].bindingId` set; or
2. **Equivalent:** `params.capabilities.experimental["mcp++/<profile>"] = true`
   (and binding id via §6.2 form 2).

Empty client capabilities are legal for baseline MCP methods that do not
require MCP++ profiles, **except** that MCP++ 1.0 clients still **MUST** send
the binding id when they claim this binding.

### 7.2 Server advertisement (initialize result)

Servers that claim MCP++ profiles under this binding **MUST** advertise them on
`InitializeResult.capabilities` using the same abstract keys and **MUST**
include `bindingId` per §6.

Example MCP++-conformant initialize result:

```json
{
  "protocolVersion": "2024-11-05",
  "capabilities": {
    "tools": {"listChanged": true},
    "experimental": {},
    "mcp++": {
      "bindingId": "mcp-binding/legacy-2024-11-05",
      "profiles": ["mcp++/mcp-idl", "mcp++/cid-envelope"]
    }
  },
  "serverInfo": {
    "name": "mcp++-legacy",
    "version": "1.0.0"
  }
}
```

### 7.3 Intersection

The intersection of client-offered and server-offered MCP++ profile keys is the
set of profiles that may be used on subsequent session requests (parent registry
§3.4). Profile methods apply only after the corresponding key is mutually
available.

## 8. Post-initialize application methods

After a successful handshake, standard initialize-era methods apply, including
at least:

| Method | Notes |
| --- | --- |
| `tools/list` | List tools |
| `tools/call` | Invoke a tool |
| `ping` | Liveness (when offered) |
| Profile methods | Parent registry Appendix A, when profiles negotiated |

Requests after initialize **MAY** omit modern per-request `_meta` keys required
by `mcp-binding/2026-07-28`. If a client does send modern `_meta` on a legacy
session, servers **MAY** ignore unrecognized keys but **MUST NOT** treat the
session as having switched to the current binding without re-advertisement.

## 9. Historical vector continuity

| Artifact | Role under this binding |
| --- | --- |
| `conformance/vectors/initialize_result.json` | Readable pin of `protocolVersion` `2024-11-05` and baseline capability shape |
| Existing accelerate / dashboard initialize clients | Evidence that initialize-era fleets remain supported when named |

Rules:

1. Implementations **MUST** continue to accept result objects that match the
   historical pin fields (`protocolVersion`, `capabilities`, `serverInfo`).
2. MCP++ 1.0 **conformance claims** for this binding additionally require the
   binding id (§6); the bare historical pin alone is insufficient for new
   MCP++ 1.0 claims.
3. The vector **MUST NOT** be used as proof of `mcp-binding/2026-07-28`.

## 10. Transport vs MCP application binding

| Concern | Locus |
| --- | --- |
| This document (`mcp-binding/legacy-2024-11-05`) | MCP revision, initialize handshake, capability placement, binding name |
| Profile E / `transport-mcp-p2p.md` | libp2p stream protocol IDs, framing, peer discovery |
| HTTP / stdio | Historical MCP transport pages for the initialize-era revision |

**libp2p stream negotiation is a carriage handshake.** Opening a `/mcp+p2p/…`
stream **MUST NOT** substitute for MCP application `initialize` under this
binding, and it **MUST NOT** be required as the only way to activate Profiles
A–D or F–H when initialize has already negotiated those profiles.

## 11. Fail-closed rules (summary)

A peer claiming only `mcp-binding/legacy-2024-11-05` **MUST**:

1. Accept well-formed `initialize` with `protocolVersion` `2024-11-05` when the
   binding id is correctly advertised.
2. Require the binding name in capability advertisement for MCP++ 1.0 claims
   (§6).
3. Complete `notifications/initialized` as part of the session open sequence.
4. Reject missing `protocolVersion` on initialize (`-32602`).
5. Reject unsupported or forged protocol versions on this path.
6. Reject forged or mismatched binding id (including current binding id on the
   initialize path without dual-binding re-advertisement).
7. Reject post-handshake application methods when initialize has not succeeded
   (legacy-only peer).
8. Not treat successful initialize as proof of the current binding.

Dual-binding peers, silent downgrade, and cross-binding forgery matrices are
specified and tested in MCPP-022; they build on the positive and negative
proofs of this document and the current binding.

## 12. Interface checklist (`McpBindingLegacy20241105@1`)

An implementation may claim interface **`McpBindingLegacy20241105@1`** when it:

1. Uses binding id `mcp-binding/legacy-2024-11-05` and MCP revision pin
   `2024-11-05`.
2. Implements `initialize` → `InitializeResult` → `notifications/initialized`.
3. Accepts `protocolVersion` `2024-11-05` on that path.
4. **Mandates** the binding name in capability advertisement (§6).
5. Advertises abstract profile keys on initialize (§7).
6. Keeps `initialize_result.json` readable for baseline fields (§9).
7. Keeps libp2p/transport handshakes out of substituting for MCP initialize
   (§10).
8. Fails closed on version / binding forgery (§5, §6.3, §11).

## 13. Conformance evidence

| Artifact | Role |
| --- | --- |
| This document | Normative legacy binding |
| `tests-py/integration/test_mcp_binding_legacy.py` | Integration proof: 2024-11-05 initialize; binding name mandatory |
| `conformance/vectors/initialize_result.json` | Historical pin (readable) |
| ADR-0006 | Dual-binding and fail-closed decision |
| [README.md](README.md) | Binding inventory index |
| Current binding `mcp-2026-07-28.md` | Sibling stateless binding (MCPP-021) |

## 14. Non-goals

- Redefining Profiles A–H object models.
- Dual-binding peer matrices (MCPP-022).
- Current-binding discovery / Tasks / `_meta` rules (MCPP-021).
- A2A extension adapter and handoff tests (MCPP-054…057).
- Requiring a specific carriage transport.
- Treating this binding as the default for new normative MCP++ work (current
  is `mcp-binding/2026-07-28`).

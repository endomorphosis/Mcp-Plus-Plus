# Profile E: `mcp+p2p` Transport Binding (libp2p)

**Status:** Draft  
**Interface:** `McpP2pBinding@1`  
**Capability key:** `mcp++/p2p-transport`  
**Parent registry:** [mcp++-profiles-draft.md](mcp++-profiles-draft.md)

This document is the normative Profile E chapter for carrying MCP JSON-RPC
messages over a peer-to-peer substrate (libp2p). Profile E is **carriage-only**:
it defines how bytes move between peers. It does **not** redefine MCP methods,
tool semantics, UCAN validation, or policy rules.

---

## 0. Three-layer split (normative)

Readers and implementers **MUST** treat the following layers as distinct.
Success or failure at one layer **MUST NOT** be inferred from another.

| Layer | Name | What it decides | Not responsible for |
| --- | --- | --- | --- |
| **T** | Transport negotiation | libp2p connection, stream protocol ID, framing, quotas, encrypted channels | MCP methods, tool execution, UCAN proofs |
| **M** | MCP application messages | JSON-RPC payloads, binding-local lifecycle (sessionless *or* legacy session), correlation of RPC ids | Stream open success, PeerID trust, execution permission |
| **A** | Execution authority | UCAN proofs, capability match, policy / caveats at invocation time | Whether a stream is open or a frame was delivered |

### 0.1 Non-substitution rules (normative)

1. **Transport success is not application success.** Opening a `/mcp+p2p/…`
   stream and delivering a framed payload **MUST NOT** be treated as a successful
   MCP method call or as authorization to execute.
2. **Transport handshake is not MCP `initialize`.** libp2p multistream-select
   (or equivalent protocol-ID negotiation) is layer **T** only. It **MUST NOT**
   reintroduce session-level MCP `initialize` on the current binding path.
3. **PeerID is not execution authority.** Authenticated libp2p identity is layer
   **T** network identity. Execution permission is layer **A** (Profile C UCAN
   and related policy). A valid PeerID with an invalid or missing UCAN **MUST**
   deny execution (fail closed), not degrade to allow.
4. **UCAN is not a transport credential.** Presence of a proof **MUST NOT**
   substitute for stream protocol negotiation, framing validity, or abuse
   limits.

### 0.2 Current path is sessionless (normative)

The **current** MCP application path for new MCP++ 1.0 work is
`mcp-binding/2026-07-28` ([bindings/mcp-2026-07-28.md](bindings/mcp-2026-07-28.md)):

- **Sessionless:** each framed JSON-RPC request stands alone.
- Version, client capabilities, and profile keys ride **per-request** metadata
  (e.g. `_meta`), not a prior MCP session handshake.
- Profile E **MUST NOT** require MCP `initialize` /
  `notifications/initialized` for current-binding claims.

**Legacy sessions** (`mcp-binding/legacy-2024-11-05`, including MCP
`initialize` / `notifications/initialized`) exist **only** under that legacy
binding. They are layer **M** application semantics, not layer **T** stream
negotiation. See [bindings/mcp-legacy-2024-11-05.md](bindings/mcp-legacy-2024-11-05.md)
and [bindings/README.md](bindings/README.md).

```
┌──────────────────────────────────────────────────────────────────┐
│ Layer A — Execution authority (Profile C / policy)               │
│   UCAN proofs · capability match · caveats · deny on invalid     │
├──────────────────────────────────────────────────────────────────┤
│ Layer M — MCP application messages (binding-local)               │
│   Current: sessionless JSON-RPC + per-request _meta              │
│   Legacy:  initialize session only under legacy binding          │
├──────────────────────────────────────────────────────────────────┤
│ Layer T — Transport negotiation (this profile)                   │
│   libp2p conn · protocol ID · length-prefix frames · quotas      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 1. Scope

### 1.1 In scope (layer T)

- Carriage of MCP JSON-RPC messages over libp2p.
- Versioned stream protocol identifiers.
- Deterministic length-prefixed framing and maximum frame size.
- Multiplexing, backpressure, stream/peer quotas, rate limits, timeouts.
- Request/response correlation on the wire (preserving JSON-RPC `id`).
- Addressing, discovery, NAT/relay guidance, encrypted channels.
- Optional event dissemination channels (pubsub), independent of RPC correctness.

### 1.2 Out of scope

- MCP method semantics, tool contracts, or envelope schemas (Profiles A–B, F–H).
- UCAN proof formats and validation algorithms (Profile C:
  [ucan-delegation.md](ucan-delegation.md)).
- Temporal deontic policy evaluation (Profile D).
- Defining a global consensus mechanism.
- Replacing existing MCP client↔server transports (HTTP, stdio, SSE).
- Standardizing a single network-wide discovery scheme.

---

## 2. Goals

- Support multi-agent, cross-org deployments without a fixed client↔server topology.
- Use secure, multiplexed streams for concurrent tool calls.
- Support bidirectional patterns (events, receipts, descriptor dissemination).
- Support connectivity features common in P2P deployments (NAT traversal, relays,
  resilient routing) without mandating a single strategy.
- Keep layers **T**, **M**, and **A** separable for conformance and abuse testing.

### 2.1 Non-goals

- Defining a global consensus mechanism.
- Replacing existing MCP client↔server transports.
- Standardizing a single network-wide discovery scheme.
- Treating PeerID authentication as sufficient for tool execution.

---

## 3. Layer T — Transport negotiation

A conforming `mcp+p2p` implementation (layer **T**):

1. Establishes an authenticated/encrypted libp2p connection between peers.
2. Opens one or more multiplexed streams using a negotiated `mcp+p2p` protocol ID.
3. Frames application bytes with a deterministic length-prefix scheme.
4. Enforces max frame size, quotas, rate limits, and idle timeouts.
5. Delivers framed payloads to the MCP application layer **without** interpreting
   them as authorization decisions.

### 3.1 Stream protocol identifiers (normative)

The binding **MUST** define one or more libp2p stream protocol identifiers
(protocol IDs) used to negotiate MCP carriage.

Implementations **MAY** use separate protocol IDs for:

- a control/capability advertisement stream (transport-level only),
- JSON-RPC request/response traffic,
- optional event dissemination.

#### 3.1.1 Default protocol ID

Until a formal registry entry exists, implementations **SHOULD** support:

- `/mcp+p2p/1.0.0`

as the default libp2p protocol ID for MCP carriage streams.

Implementations **MAY** define sub-protocols (e.g. `/mcp+p2p/session/1.0.0`,
`/mcp+p2p/events/1.0.0`) but **SHOULD** prioritize one commonly supported ID
to maximize interoperability.

#### 3.1.2 Versioning convention

Protocol IDs **SHOULD** embed a semantic version:

- breaking wire or framing changes bump the major version (`/mcp+p2p/2.0.0`);
- additive, backwards-compatible changes bump minor/patch.

When standardizing, a registry entry **SHOULD** specify: protocol ID string(s),
framing, maximum frame size defaults, and transport open expectations.

Custom protocol IDs (not under `/mcp+p2p/`) are permitted for private
deployments but **SHOULD** be treated as non-baseline for interop claims.

### 3.2 Stream open lifecycle (normative)

For each MCP carriage stream over `mcp+p2p`, an implementation **MUST**:

1. **Connection** — Establish a libp2p connection to a remote peer (PeerID and
   address material such as multiaddrs), using authenticated/encrypted channels.
2. **Stream** — Open a stream using a negotiated `mcp+p2p` protocol ID
   (multistream-select or stack equivalent).
3. **Ready for application data** — After protocol ID negotiation succeeds,
   framed MCP application messages (layer **M**) may be exchanged.

This lifecycle is **transport stream readiness**, not MCP application
initialization. Layer **T** **MUST NOT** require an MCP `initialize` exchange
before accepting framed JSON-RPC on the current binding path.

#### 3.2.1 Optional transport capability advertisement

After stream open, implementations **MAY** exchange a **transport-level**
capability advertisement (supported protocol ID versions, max frame size,
quota hints). Such an exchange:

- is layer **T** only;
- **MUST NOT** be labeled or treated as MCP `initialize`;
- **MUST NOT** create MCP application session state on the current path.

### 3.3 Message framing (normative)

MCP JSON-RPC payloads **MUST** be transmitted without semantic modification
(field rewriting, method translation, or silent id remapping).

The binding **MUST** define:

- how messages are delimited/framed on the stream,
- how request/response correlation is preserved,
- backpressure and flow control expectations,
- maximum frame size and behavior on violation.

#### 3.3.1 Length-prefixed framing (normative default)

Implementations **MUST** implement a deterministic length-prefixed framing
scheme for baseline compliance. The recommended wire layout is:

| Field | Size | Encoding |
| --- | --- | --- |
| `length` | 4 bytes | unsigned big-endian integer `N` |
| `payload` | `N` bytes | UTF-8 JSON text (application message body) |

Receivers **MUST** reject frames with `N` greater than the configured maximum.
Default maximum frame size: **16 MiB** (16 × 1024 × 1024 bytes). Deployments
**MAY** configure a lower limit; they **MUST** document the effective limit.

On max-size violation implementations **MUST** fail closed for that stream
(close the stream and/or return a transport error). They **MUST NOT** allocate
unbounded buffers based on attacker-supplied lengths.

#### 3.3.2 Canonical application message body (`P2PMessage`)

The reference implementations (ipfs_accelerate_py, ipfs_datasets_py, SwissKnife)
carry an application-level envelope inside each frame, validated by `P2PMessage`
in the spec validators. The body is UTF-8 JSON with:

- `type` — `request` | `response` | `notification` | `event` (REQUIRED; strings tolerated)
- `method`, `params`, `id` — request fields (OPTIONAL)
- `result`, `error` — response fields (OPTIONAL; `error` is a string)
- `sender` — origin peer id (OPTIONAL; network identity, not UCAN)
- `timestamp` — epoch seconds or ISO-8601 (OPTIONAL)

Default frame cap is 16 MiB. Validators permit extra fields so payload-bundled
variants (e.g. `{type, id, payload}`) remain interoperable.

When the payload is a raw MCP JSON-RPC object (`jsonrpc`, `id`, `method`, …),
implementations **MUST** preserve those fields end-to-end (see §4.3).

### 3.4 Correlation, concurrency, cancel, and retry (normative)

- Implementations **MUST** preserve JSON-RPC request/response correlation via
  the application `id` field across the transport.
- Implementations **MUST** allow multiple in-flight requests per stream
  (multiplexed concurrent calls), subject to peer quotas.
- Implementations **SHOULD** support cancel of an in-flight request using
  binding-appropriate cancel/notification semantics; transport **MUST** deliver
  cancel signals without inventing success results.
- **Retry safety:** reopening a stream or retransmitting a request is safe only
  when the application method is idempotent or when application-layer
  deduplication (e.g. intent CID / nonce) is present. Layer **T** **MUST NOT**
  invent automatic retry that duplicates non-idempotent side effects without
  application guidance.
- **Replay:** implementations **SHOULD** detect duplicate frames or duplicate
  response `id` values within a configured window and drop or reject them.
  Replay detection does not replace UCAN freshness or receipt CID checks
  (layer **A** / Profile B artifacts).

### 3.5 Backpressure, quotas, rate limits, timeouts (normative)

Baseline-compliant implementations **MUST**:

| Control | Requirement |
| --- | --- |
| Backpressure | Honor stream-level flow control; stop reading/writing when peer or local buffers are full |
| Max frame | Enforce configured maximum (§3.3.1) |
| Stream quota | Limit concurrent streams per peer |
| Peer quota | Limit concurrent in-flight requests and bandwidth per PeerID |
| Rate limit | Rate-limit inbound stream creation and inbound message volume |
| Idle timeout | Close or recycle idle streams after a configured idle period |
| Request timeout | Bound wait time for a correlated response; surface timeout as failure, not empty success |

Exact numeric defaults for quotas and timeouts are deployment-configurable.
Implementations **MUST** publish effective defaults used in interop tests.

### 3.6 Addressing and discovery (non-normative guidance)

Implementations **MAY** use:

- peer IDs and multiaddrs for addressing;
- DHT-based discovery;
- rendezvous/relay services;
- LAN-local discovery (e.g. mDNS);
- pubsub topics for announcements.

Implementations **MAY** support NAT traversal / connectivity across hostile
networks using techniques available in their libp2p stack (relays, rendezvous,
hole punching). This binding does not mandate a particular NAT traversal strategy.

Implementations **MAY** implement routing behaviors that improve availability
in dynamic peer sets (“resilient routing”). Any such behavior **MUST** remain
transparent to MCP JSON-RPC semantics (layer **M**).

### 3.7 Encrypted channels (normative)

- Implementations **MUST** use authenticated/encrypted channels supported by
  libp2p for `mcp+p2p` carriage.
- Encryption authenticates network endpoints (PeerID). It does **not** grant
  execution authority (layer **A**).

---

## 4. Layer M — MCP application messages

Layer **M** is defined by the peers' selected **MCP application binding**, not
by Profile E alone. Profile E only carries framed JSON-RPC (or `P2PMessage`
envelopes that contain it).

### 4.1 Binding selection

| Binding id | Lifecycle on Profile E | Document |
| --- | --- | --- |
| `mcp-binding/2026-07-28` (**current**) | **Sessionless** — no MCP `initialize`; per-request `_meta` | [bindings/mcp-2026-07-28.md](bindings/mcp-2026-07-28.md) |
| `mcp-binding/legacy-2024-11-05` | **Session** — MCP `initialize` / `notifications/initialized` as first application messages on the stream | [bindings/mcp-legacy-2024-11-05.md](bindings/mcp-legacy-2024-11-05.md) |

Which binding rides over a `/mcp+p2p/…` stream is selected by declared MCP
bindings ([bindings/README.md](bindings/README.md)), not by the protocol ID alone.

### 4.2 Current path (sessionless) — normative default for new work

When peers claim `mcp-binding/2026-07-28` over Profile E:

1. After layer **T** stream readiness (§3.2), either peer **MAY** send framed
   JSON-RPC requests immediately.
2. Each request **MUST** carry modern per-request metadata as required by the
   current binding (including version / binding identity keys as specified there).
3. Implementations **MUST NOT** require a prior MCP `initialize` exchange.
4. Implementations **MUST** reject `initialize` / `notifications/initialized`
   when offered as current-path behavior (fail closed per current binding).
5. Implementations **MUST NOT** invent MCP application session state from
   connection identity (PeerID) alone.

### 4.3 Legacy path (sessions only under legacy binding)

When peers claim `mcp-binding/legacy-2024-11-05` over Profile E:

1. Layer **T** stream open still occurs as in §3.2 (carriage handshake only).
2. Layer **M** **MUST** then run the legacy MCP initialization handshake over
   the stream as the first application data, per the legacy binding document.
3. Post-handshake application methods follow legacy session rules.
4. Successful legacy initialize **MUST NOT** be treated as proof of the current
   binding.

Dual-binding peers **MAY** support both paths; downgrade and forgery rules are
normative in the binding documents and ADR-0006, not restated here.

### 4.4 JSON-RPC preservation (normative)

- MCP JSON-RPC payloads **MUST** be transmitted without semantic modification.
- Essential fields (`jsonrpc`, `id`, `method`, and `params` when present)
  **MUST** be preserved end-to-end.
- Profile E **MUST NOT** translate method names or rewrite result/error shapes.

### 4.5 Capability advertisement (MCP++ profiles)

Abstract MCP++ profile keys (`mcp++/mcp-idl`, `mcp++/ucan`, …) are defined in
the parent registry. Wire placement is **binding-local**:

- **Current:** per-request `_meta` and/or discovery RPCs.
- **Legacy:** session `initialize` capability maps (e.g. experimental keys).

Advertisement of `mcp++/p2p-transport` indicates Profile E carriage support. It
does **not** by itself advertise UCAN authority or policy permissions.

---

## 5. Layer A — Execution authority

Layer **A** is **not** part of the libp2p protocol ID or frame header. It is
evaluated at invocation time using Profile C (and optionally Profile D).

### 5.1 Separation from transport identity (normative)

| Concept | Layer | Role |
| --- | --- | --- |
| libp2p PeerID | **T** | Network endpoint identity under encrypted channels |
| MCP client/server roles / binding metadata | **M** | Application protocol identity and version |
| UCAN proofs / `proof_cid` / capability attenuation | **A** | Whether the invocation may execute |

Implementations **MUST**:

1. Validate UCAN (or equivalent) proofs at execution time
   ([ucan-delegation.md](ucan-delegation.md)).
2. Treat missing, expired, forged, or capability-mismatched proofs as **deny**.
3. Treat a valid PeerID with an invalid UCAN as **deny**, not a degraded allow.
4. Record proofs in CID-native artifacts when Profile B is in use
   ([cid-native-artifacts.md](cid-native-artifacts.md)).

### 5.2 Invocation shape (informative)

At execution time an invocation **SHOULD** include (per Profile C):

- `intent_cid`
- `ucan_proofs[]` and/or `proof_cid`
- `policy_cid` when deontic policy applies
- `context_cids[]` as needed

Profile E **MAY** carry these fields inside framed JSON-RPC `params` or
envelope metadata. Carriage of the bytes is layer **T**/**M**; acceptance of
the proof is layer **A**.

### 5.3 Fail-closed matrix (normative summary)

| Condition | Transport (T) | Application (M) | Authority (A) |
| --- | --- | --- | --- |
| Stream opens; no app data yet | success | n/a | n/a |
| Valid frame; unknown method | success | method error | n/a |
| Valid frame; valid method; no UCAN | success | request delivered | **deny** |
| Valid PeerID; invalid UCAN | success | request delivered | **deny** |
| Oversized / truncated frame | **fail** | not delivered | n/a |
| Empty success on transport failure | **non-conformant** | — | — |

Transport success **MUST NOT** be reported as application or authorization
success. Empty or fabricated success results on transport failure are
non-conformant.

---

## 6. Optional event dissemination

Implementations **MAY** publish/subscribe to topics for:

- `interface_cid` announcements (MCP-IDL)
- `receipt_cid` / `decision_cid` dissemination
- coordination signals for scheduling/ordering

If event dissemination is enabled, implementations **SHOULD** clearly separate:

- **point-to-point session/stream traffic** (tool calls, responses), from
- **fanout traffic** (announcements, receipts, coordination),

so that RPC correctness does not depend on pubsub delivery.

If pubsub is implemented, it **MUST NOT** be required for correctness of
point-to-point MCP request/response streams. Topic naming, message types, and
validation rules **SHOULD** be documented by the implementation.

---

## 7. Security considerations

- Use authenticated/encrypted channels supported by libp2p (layer **T**).
- Authorization is enforced at the application/authority layers (UCAN + policy).
- Peers **SHOULD** rate-limit and validate incoming messages to mitigate abuse.

Additional considerations:

- **Peer identity:** the remote libp2p PeerID is not, by itself, sufficient
  authorization. Bind execution authority to explicit proofs (e.g. UCAN) and
  policy decisions (layer **A**).
- **Resource exhaustion:** protect against unbounded stream creation, oversized
  frames, and high-rate notifications (layer **T** quotas).
- **Replay:** if receipts/decisions are disseminated, implementations **SHOULD**
  include enough context (CIDs, signatures, freshness bounds) to detect
  duplicates/replays. Transport-level duplicate frame detection complements but
  does not replace application-level replay controls.

---

## 8. Related documents

| Document | Concern |
| --- | --- |
| [mcp++-profiles-draft.md](mcp++-profiles-draft.md) | Abstract Profiles A–H registry |
| [bindings/README.md](bindings/README.md) | MCP application bindings index |
| [bindings/mcp-2026-07-28.md](bindings/mcp-2026-07-28.md) | Current sessionless binding |
| [bindings/mcp-legacy-2024-11-05.md](bindings/mcp-legacy-2024-11-05.md) | Legacy initialize binding |
| [ucan-delegation.md](ucan-delegation.md) | Profile C execution authority |
| [mcp-idl.md](mcp-idl.md) | Interface contracts |
| [cid-native-artifacts.md](cid-native-artifacts.md) | CID artifacts / receipts |
| [temporal-deontic-policy.md](temporal-deontic-policy.md) | Profile D policy |

---

## 9. Interop checklist (implementation guidance)

This section reduces “two implementations that both claim `mcp+p2p` but cannot
talk” failures. Items marked **MUST** are required for baseline interoperability;
items marked **SHOULD** are strong recommendations.

### 9.1 Wire compatibility (layer T)

- Implementations **MUST** agree on the libp2p stream protocol ID(s) used for
  `mcp+p2p`.
- Implementations **MUST** preserve MCP JSON-RPC payload semantics (no field
  rewriting, no method translation).
- Implementations **MUST** define message framing unambiguously.
- Implementations **MUST** use length-prefixed framing for baseline compliance.
- Implementations **MUST** define maximum frame size and behavior on violation
  (e.g. close stream).

### 9.2 Stream and application semantics

- Implementations **MUST** complete layer **T** stream open (connection +
  protocol ID) before treating the stream as ready for application data.
- On the **current** binding path, implementations **MUST** accept sessionless
  framed requests without MCP `initialize`.
- On the **legacy** binding path only, implementations **MUST** run MCP
  initialization (version + capability negotiation) as the first application
  data on the session stream.
- Implementations **MUST** preserve request/response correlation (`id`) across
  the transport.
- Implementations **MUST** define concurrency expectations (e.g. multiple
  outstanding requests per stream).
- Implementations **SHOULD** specify keepalive/idle-timeout behavior.
- Implementations **SHOULD** define retry/reconnect guidance (what is safe to
  retry; what requires idempotency at the application layer).

### 9.3 Abuse resistance (layer T)

- Implementations **MUST** rate-limit inbound stream creation and inbound
  message volume.
- Implementations **SHOULD** apply per-peer quotas (streams, bandwidth, frame
  rate, max concurrent in-flight requests).
- Implementations **MUST** validate framing before allocating large buffers.

### 9.4 Identity and authorization (layers T vs A)

- Implementations **MUST** use authenticated/encrypted libp2p channels.
- Implementations **MUST** treat network identity (PeerID) as distinct from
  execution authority.
- Implementations **SHOULD** bind “who is acting” to explicit proofs (e.g.
  UCAN) and record those proofs in CID-native artifacts.
- Implementations **MUST** deny execution when UCAN validation fails, even if
  the PeerID and transport are valid.

### 9.5 Optional event dissemination

- If pubsub dissemination is implemented, it **MUST NOT** be required for
  correctness of point-to-point MCP request/response streams.
- Implementations **SHOULD** document topic naming, message types, and
  validation rules for any published events.

### 9.6 Conformance test ideas (non-normative)

1. **Transport handshake vs MCP initialize**
   - Open a stream using the `mcp+p2p` protocol ID (layer **T**).
   - On current binding: send a sessionless JSON-RPC request without MCP
     `initialize`; verify acceptance when `_meta` is well-formed.
   - On legacy binding: verify MCP initialization completes and negotiated
     capabilities match expectations.
   - Negative: conflate multistream protocol ID negotiation with MCP initialize;
     verify peers do not treat protocol ID alone as application session state.

2. **Framing and correlation**
   - Send multiple concurrent JSON-RPC requests with distinct `id` values.
   - Verify responses correlate correctly under reordering/latency.
   - Negative: send an oversized frame; verify deterministic enforcement
     (close stream, error).

3. **Backpressure + abuse limits**
   - Flood with small frames and/or open many streams.
   - Verify rate limits/quotas trigger without crashing the process or unbounded
     memory growth.

4. **Authorization separation**
   - Establish a valid libp2p connection but omit UCAN/proof material in the
     higher-layer envelope.
   - Verify the transport succeeds while the application layer denies execution.
   - Negative: valid PeerID + invalid UCAN → deny (not degraded allow).

5. **Pubsub independence (if implemented)**
   - Disable pubsub connectivity and verify point-to-point MCP streams still work.
   - Enable pubsub and verify published announcements are validated
     (schema/signature/CID checks) before acceptance.

6. **Empty success on transport failure**
   - Induce stream reset mid-request; verify the caller receives a failure, not
     an empty success result.

---

## 10. Baseline compliance profile (draft)

This section defines a **minimal interoperability set**. If two implementations
both claim “Baseline `mcp+p2p` compliance”, they should be able to establish a
carriage stream and exchange MCP JSON-RPC messages reliably under a mutually
supported binding.

### 10.1 Baseline requirements

An implementation claiming Baseline compliance:

- **MUST** support at least one well-known `mcp+p2p` libp2p protocol ID
  (default: `/mcp+p2p/1.0.0`).
- **MUST** open a libp2p stream using that protocol ID (layer **T** readiness)
  before exchanging application frames.
- **MUST** implement length-prefixed framing and publish max frame size.
- **MUST** enforce maximum frame size and define violation behavior.
- **MUST** preserve JSON-RPC `id` correlation and allow multiple in-flight
  requests per stream.
- **MUST** use authenticated/encrypted libp2p channels.
- **MUST** implement basic abuse resistance: rate-limit stream creation and
  inbound message volume; apply stream/peer quotas.
- **MUST** document whether the current sessionless binding, the legacy session
  binding, or both are supported over the stream.
- **MUST** treat PeerID as distinct from UCAN execution authority.
- **MUST NOT** report transport success as application or authorization success.

### 10.2 Optional extensions (non-baseline)

The following features are explicitly **optional** and should be
negotiated/documented separately:

- Pubsub-based dissemination of receipts/decisions/interface descriptors
- DHT/rendezvous/mDNS discovery behaviors
- Separate control/data streams or multiple protocol IDs
- Additional ordering/coordination mechanisms (e.g. scheduling coordination signals)
- Transport-level capability advertisement frames (§3.2.1)

### 10.3 Protocol ID registry (placeholder)

This draft proposes `/mcp+p2p/1.0.0` as the interop default until a formal
registry entry is agreed.

#### Versioning convention (non-normative)

Protocol IDs **SHOULD** embed a semantic version:

- breaking changes bump the major version (`/mcp+p2p/2.0.0`)
- additive, backwards-compatible changes bump minor/patch

When standardizing, the registry entry **SHOULD** specify:

- protocol ID string(s)
- framing (length-prefix)
- maximum frame size defaults
- stream open expectations (layer **T**)
- which MCP application bindings are supported over the stream (layer **M**)

### 10.4 Interface checklist (`McpP2pBinding@1`)

An implementation may claim interface **`McpP2pBinding@1`** when it:

1. Implements layer **T** stream open with a versioned `/mcp+p2p/…` protocol ID.
2. Implements length-prefixed framing with an enforced max frame size.
3. Preserves JSON-RPC semantics and `id` correlation with multi-in-flight support.
4. Enforces backpressure-aware quotas, rate limits, and timeouts as in §3.5.
5. Documents current (sessionless) vs legacy (session) MCP paths and does not
   require initialize on the current path.
6. Separates PeerID (transport identity) from UCAN (execution authority) with
   fail-closed deny on invalid proofs.
7. Does not treat stream open as MCP initialize or as authorization success.

---

## 11. Mapping note for existing validators

Structural validators and integration tests historically describe a three-phase
“session lifecycle” of `connection` → `stream` → `initialization`. Under this
document:

| Historical phase key | Normative meaning |
| --- | --- |
| `connection` | Layer **T** libp2p connection (PeerID, multiaddrs) |
| `stream` | Layer **T** protocol ID negotiation |
| `initialization` / `handshake` | Layer **M** binding-local start: **legacy** MCP initialize **or**, on the current path, readiness to accept sessionless requests (not MCP initialize) |

Tests that still supply an MCP-shaped `handshake` object remain valid structural
fixtures for the legacy binding path. They **MUST NOT** be read as requiring
MCP initialize for baseline `mcp+p2p` carriage on the current sessionless path.

# MCP++: CID-Native, Contract-Driven Execution Profiles for MCP

**Status:** Draft (Non-Normative / Discussion) — Profiles A-H interoperability candidate

---

## 1. Introduction

This document defines **MCP++**, a set of *optional, backward-compatible execution profiles* for the Model Context Protocol (MCP). MCP++ is designed to support federated, multi-agent, and parallel execution environments while preserving MCP message semantics and incremental adoptability.

MCP++ addresses two practical pressures observed in production deployments:
1. **Extension fragmentation** and uncertain compatibility across clients and servers.
2. **Context and toolset constraints** that prevent reliable utilization of large or evolving tool ecosystems.

MCP++ introduces modernized solutions inspired by historical distributed systems (e.g., interface repositories and brokers), implemented in a content-addressed, capability-secure, and policy-aware manner suitable for AI-native systems.

**Profiles A–H are abstract.** They define execution semantics (contracts, envelopes, delegation, policy, provenance, risk/scheduling, payments) **without** requiring a specific MCP protocol revision or a specific carriage transport. How profiles are advertised, discovered, and activated on the wire is specified by **versioned MCP bindings** and optional **transport bindings**—not by inlining one historical MCP lifecycle into this registry. See [bindings/README.md](bindings/README.md) and ADR-0006.

## 1.1 Spec Chapters

This draft is the top-level profile registry. The component details live in these chapters:

- [Profile A: MCP-IDL (CID-Addressed Interface Contracts)](mcp-idl.md)
- [Profile B: CID-Native Execution Artifacts](cid-native-artifacts.md)
- [Profile C: Capability Delegation (UCAN)](ucan-delegation.md)
- [Profile D: Temporal Deontic Policy Evaluation](temporal-deontic-policy.md)
- [Profile E: `mcp+p2p` Transport Binding](transport-mcp-p2p.md)
- [Profile F: Event DAG Provenance, Archival, and Compaction](event-dag-ordering.md)
- [Profile G: Risk Scoring, Neighborhood Consensus, and Scheduling](risk-scheduling.md)
- [Profile H: x402 Payments and Paid Capability Access](x402-payments.md)

### 1.2 MCP version bindings (referenced, not inlined)

MCP application lifecycle and revision-specific capability carriage live under
[docs/spec/bindings/](bindings/README.md). This registry **MUST NOT** treat any
single handshake as the only normative negotiation path for Profiles A–H.

| Binding id | MCP revision | Lifecycle shape | Role |
| --- | --- | --- | --- |
| `mcp-binding/legacy-2024-11-05` | `2024-11-05` (initialize-era) | Session `initialize` / `notifications/initialized` | **Legacy.** Documented in [bindings/mcp-legacy-2024-11-05.md](bindings/mcp-legacy-2024-11-05.md) (MCPP-020). |
| `mcp-binding/2026-07-28` | `2026-07-28` | Stateless per-request `_meta`; **no** initialize | **Current.** Documented in [bindings/mcp-2026-07-28.md](bindings/mcp-2026-07-28.md) (MCPP-021). |

A peer **MAY** support both bindings. Dual support, downgrade rejection, and
version-forgery fail-closed rules are normative in ADR-0006 and the binding
documents—not restated as profile law here.

Transport negotiation (for example libp2p stream protocol IDs under Profile E)
is a **carriage handshake**. It is **not** a substitute for, and **MUST NOT**
be conflated with, an MCP application-level initialize exchange.

---

## 2. Terminology

- **CID**: Content Identifier (immutable, hash-addressed reference to canonicalized content).
- **Profile**: An optional, negotiable MCP++ capability that adds execution semantics without changing baseline MCP message formats for peers that do not advertise the profile.
- **Binding**: A versioned document/module that maps abstract profile keys and objects onto a specific MCP protocol revision (and, separately where needed, a carriage transport).
- **Interface Descriptor**: A canonical, content-addressed contract describing a tool/resource interface.
- **Execution Envelope**: A CID-native wrapper around an MCP invocation.
- **Event DAG**: A directed acyclic graph of execution events linked by causal references.
- **Policy CID**: A content-addressed representation of time-bounded permissions, prohibitions, and obligations.

Normative keywords **MUST**, **SHOULD**, and **MAY** are used as described in RFC 2119.

---

## 3. Compatibility Model

### 3.1 Baseline interoperability

Implementations that do not support MCP++ **MUST** continue to interoperate
using baseline MCP semantics for the MCP revision they speak. No MCP++ profile
modifies or invalidates existing MCP JSON-RPC message formats for peers that
have not negotiated the corresponding profile.

### 3.2 Profile independence (normative)

Profiles **A–H** describe *what* is offered (object models, methods, CIDs,
policy and proof requirements). They **MUST NOT** require:

1. A specific MCP `protocolVersion` value as the sole legal revision.
2. The legacy `initialize` / `notifications/initialized` exchange as the only
   capability negotiation path.
3. A specific carriage transport (HTTP, stdio, SSE, `mcp+p2p`, or otherwise)
   for their abstract semantics to be valid.

MCP revision mechanics, handshake vs per-request `_meta`, discovery RPCs, and
HTTP header bindings are **binding-local**. See [bindings/README.md](bindings/README.md).

### 3.3 Capability advertisement (abstract keys)

MCP++ profile support is advertised using stable capability keys (or equivalent
extension identifiers documented by the active binding). The wire placement of
those keys depends on the selected binding:

| Capability key | Profile |
| --- | --- |
| `mcp++/mcp-idl` | A — MCP-IDL |
| `mcp++/cid-envelope` | B — CID-native envelopes |
| `mcp++/ucan` | C — UCAN delegation |
| `mcp++/deontic-policy` | D — temporal deontic policy |
| `mcp++/p2p-transport` | E — `mcp+p2p` carriage (optional) |
| `mcp++/event-dag` | F — Event DAG provenance / archival / compaction |
| `mcp++/risk-scheduling` | G — risk scoring / neighborhood coordination / scheduling |
| `mcp++/x402-payments` | H — x402 payments |

**Legacy binding placement (informative, not exclusive):** under
`mcp-binding/legacy-2024-11-05`, clients and servers may exchange these keys
during the session `initialize` handshake (for example under
`capabilities.experimental` as `{"mcp++/<profile>": true}`, or under a nested
`capabilities["mcp++"].profiles` list). Exact shapes are normative only in the
legacy binding document and in historical vectors such as
`initialize_result.json`.

**Current binding placement (informative, not exclusive):** under
`mcp-binding/2026-07-28`, the same abstract keys ride per-request `_meta`
(and related discovery / extension mechanisms). There is **no** initialize
handshake on that path. Exact key tables are normative only in the current
binding document.

Implementations that claim MCP++ 1.0 dual-binding support **MUST** name the
binding id(s) they speak when advertising capabilities (see ADR-0006).
Supporting initialize alone without naming `mcp-binding/legacy-2024-11-05` is
non-conformant for MCP++ 1.0 claims.

### 3.4 Negotiation outcomes

Regardless of binding:

1. The intersection of client-offered and server-offered MCP++ profile keys is
   the set of profiles that may be used on subsequent requests.
2. A peer **MAY** support a subset of Profiles A–H.
3. Profile methods and object models in chapters A–H apply only after the
   corresponding profile key is mutually available under the active binding.
4. Forged binding ids, silent downgrade between bindings, or treating initialize
   as current MCP behavior when only `mcp-binding/2026-07-28` is claimed **MUST**
   fail closed (binding and dual-peer rules; not re-specified per profile).

---

## 4. Profile A: MCP-IDL (CID-Addressed Interface Contracts)

### 4.1 Overview

The MCP-IDL profile defines a runtime-discoverable, content-addressed interface contract system inspired by historical Interface Repository concepts, adapted for modern distributed AI systems.

See: [docs/spec/mcp-idl.md](mcp-idl.md)

### 4.2 Interface Descriptor Object (Normative)

An Interface Descriptor MUST be canonicalized and content-addressed to produce an `interface_cid`.

**Required Fields:**
- `name`
- `namespace`
- `version`
- `methods[]` (input/output schemas)
- `errors[]`
- `compatibility` (supersedes / compatible_with)
- `requires[]` (capabilities)

**Optional Fields:**
- semantic tags
- observability hooks
- streaming/event semantics (callbacks / event streams)
- resource cost hints

### 4.3 Interface Repository APIs (Normative)

Servers supporting MCP-IDL MUST expose the following endpoints:
- `interfaces/list`
- `interfaces/get(interface_cid)`
- `interfaces/compat(interface_cid)`

### 4.4 Toolset Slicing (Optional)

Servers MAY expose `interfaces/select(task_hint_cid, budget)` to recommend interface subsets compatible with client context constraints.

---

## 5. Profile B: CID-Native Execution Envelopes

### 5.1 Envelope Structure (Normative)

An execution envelope MAY wrap any MCP invocation and includes:
- `interface_cid`
- `input_cid`
- `intent_cid`
- `policy_cid` (optional)
- `proof_cid` (optional)
- `parents[]`

### 5.2 Output and Receipts

Executions produce:
- `output_cid`
- `receipt_cid`

Receipts MUST be content-addressed and MAY be signed.

See: [docs/spec/cid-native-artifacts.md](cid-native-artifacts.md)

---

## 6. Profile C: Capability Delegation (UCAN)

### 6.1 Delegation Chains

MCP++ uses capability tokens to represent delegable authority. Execution-time validation is REQUIRED.

See: [docs/spec/ucan-delegation.md](ucan-delegation.md)

### 6.2 Invocation and Receipts

Invocations MUST reference a valid delegation chain. Receipts attest execution outcomes and bind them to immutable execution artifacts.

---

## 7. Profile D: Temporal Deontic Policy Evaluation

### 7.1 Policy Representation

Policies MUST be content-addressed (`policy_cid`) and express:
- Permissions
- Prohibitions
- Obligations
- Temporal constraints

### 7.2 Runtime Evaluation

At execution-time, implementations MUST:
1. Validate delegation proofs
2. Evaluate policy constraints
3. Emit a `decision_cid`

Decisions MAY spawn obligations with deadlines.

See: [docs/spec/temporal-deontic-policy.md](temporal-deontic-policy.md)

---

## 8. Profile E: P2P Transport Binding (Optional)

### 8.1 Transport Semantics

The `mcp+p2p` transport profile defines **carriage** of MCP JSON-RPC messages
over a peer-to-peer substrate (specifically, a libp2p binding in this draft).
Message semantics for Profiles A–D, F–H remain unchanged.

Profile E is an **optional transport binding**, not an MCP application lifecycle.
libp2p stream protocol negotiation is a carriage handshake. It **MUST NOT** be
read as requiring the legacy MCP `initialize` exchange as the only path to
activate other MCP++ profiles. Which MCP revision binding rides over a
`mcp+p2p` stream is selected by the peers' declared MCP bindings
([bindings/README.md](bindings/README.md)), not by Profile E alone.

### 8.2 Eventing

Implementations MAY support bidirectional streams and event publication for receipts, interface descriptors, and coordination signals.

See: [docs/spec/transport-mcp-p2p.md](transport-mcp-p2p.md)

---

## 9. Profile F: Event DAG Provenance, Archival, and Compaction

### 9.1 Capability and Profile Name (Normative)

Profile F is advertised with the abstract capability key `mcp++/event-dag`
(see §3.3). The stable wire key remains intentionally short for compatibility;
implementations MUST expose the profile name **"Profile F: Event DAG
Provenance, Archival, and Compaction"** in profile metadata and documentation.
How the key is carried (session initialize vs per-request `_meta` vs discovery)
is binding-local.

Profile F defines a bounded-retention Event DAG. It preserves auditability
without requiring every peer to keep, load, or traverse the entire execution
history in memory.

### 9.2 Event Structure (Normative)

Each event CID MUST commit to:
- intent
- interface
- proofs
- decision
- outputs
- parents

### 9.3 Hot, Archived, and Compacted Tiers (Normative)

Implementations MAY retain recent events in a hot in-memory tier and MUST
write an archive before removing an event from that tier. An archive MUST be
content-addressed or otherwise integrity-addressed, contain the original event
records and Merkle layers sufficient for inclusion verification, and remain
retrievable through the implementation's declared archive backend.

An implementation MAY compact an old epoch into a certificate only after its
archive write is durable. Compaction MUST NOT silently discard the underlying
event records. Implementations SHOULD bound `history` and `provenance`
traversals and return archive boundaries rather than forcing a client to load
unbounded history.

### 9.4 Compaction Certificate (Normative)

A compaction certificate MUST include `certificate_cid`, `archive_cid`,
`merkle_root`, `epoch_id`, `event_count`, `root_cids[]`, `frontier_cids[]`,
`proof_system`, and `zero_knowledge`. It MUST include `proof` when the selected
proof system emits proof material, and `verification_key_cid` when a verifier
key is required.

`zero_knowledge` MUST be `true` only when the certificate contains an actual
zero-knowledge proof that the receiver can verify against the declared proof
system and verification key. A hash, Merkle root, signature, or simulated
Groth16-shaped digest is an integrity commitment and MUST set
`zero_knowledge` to `false`.

### 9.4.1 Verifier-Backed ZK Extension (Normative)

Implementations that offer real Profile F proof generation expose the following
operations in the Profile F namespace:

- `mcp++/dag/zk/status`
- `mcp++/dag/zk/prove`
- `mcp++/dag/zk/verify`

The REST equivalents are `GET /mcp/dag/zk/status` and `POST
/mcp/dag/zk/{prove,verify}`. `status` MUST report `available: false` when the
proving binary, proving key, or verifying key is unavailable. A prover MUST
fail closed in that state; it MUST NOT return simulated proof bytes with
`zero_knowledge: true`.

The initial bounded circuit profiles are `MCP++_EventDAG_Compaction_v1`
(`groth16-bn254-event-dag-v3`) and the SwissKnife-local
`event_dag_compaction_v1` (`groth16-bn254-poseidon-event-dag-v1`). Each
certificate MUST identify its exact circuit and leaf derivation. Both prove
knowledge of one through four private event commitments with a public root and
active-leaf count. An archive verifier MUST derive the declared commitments
from the archived CID batch, recompute the declared ZK root, verify the
Groth16 proof, and verify the normal archive Merkle root before accepting the
certificate. Implementations MUST NOT treat different circuit identifiers as
interchangeable. Larger archives MAY be split into bounded proof batches or
retain a hash-only certificate until an audited aggregation circuit is
available.

Certificates produced by this extension MUST include `proof_system`,
`zero_knowledge`, `circuit_version`, `ruleset_id`, `zk_merkle_root`, `proof`,
`verification_key_cid`, and `verification_key_sha256`. A verification-key CID
identifies the exact key blob; deployments are responsible for publishing that
blob through their declared archive backend before advertising the proof path.

### 9.5 Unrolling and Audit

Causal traversal of the Event DAG enables deterministic replay, rollback, and
attribution. When a traversal reaches compacted history, the response MUST
include the relevant `archive_cid` and `certificate_cid`; the caller MAY fetch
the archive or request a Merkle inclusion proof instead of traversing all prior
nodes.

See: [docs/spec/event-dag-ordering.md](event-dag-ordering.md)

---

## 10. Concurrency, Ordering, and Scheduling

### 10.1 Partial Ordering

Events reference parents to establish causal order without requiring global consensus.

### 10.2 Neighborhood Coordination

Implementations MAY cluster events or peers using similarity metrics and coordinate ordering locally.

### 10.3 Scheduling

Risk-adjusted prioritization MAY be implemented using priority queues. Scheduling behavior is non-normative.

See: [docs/spec/risk-scheduling.md](risk-scheduling.md)

---

## 11. Risk Scoring (Non-Normative)

Risk metrics MAY be computed from immutable history, including:
- policy violations
- missed obligations
- disputed receipts

---

## 12. Security Considerations

- All authority validation MUST occur at execution-time.
- Content-addressed artifacts MUST be canonicalized to avoid ambiguity.
- Implementations SHOULD isolate policy evaluation environments.

---

## 13. Incremental Adoption Strategy

Implementations MAY adopt MCP++ profiles independently:
1. MCP-IDL
2. CID-native envelopes
3. Delegation
4. Policy evaluation
5. P2P transport
6. Profile F Event DAG archival and compaction

---

## 14. Open Questions

- Canonicalization standards for interface descriptors
- Policy language interoperability
- Registry vs. gossip-based discovery tradeoffs

---

## 15. Conclusion

MCP++ extends MCP into federated, multi-agent domains by introducing contract
clarity, immutable provenance, explicit delegation, and policy-aware
execution—without deprecating or breaking existing MCP deployments. Profile
semantics stay stable across MCP revisions; version-specific lifecycle lives in
named bindings under [bindings/](bindings/README.md).

---

## Appendix A: HTTP/JSON-RPC Method Surface (Normative)

This appendix freezes **profile method names, REST paths, and result fields**
for third-party interoperability. It is **not** a complete MCP application
lifecycle specification.

**Lifecycle is binding-local.** Session initialize, per-request `_meta`,
`server/discover`, and HTTP version headers are specified only in the versioned
MCP binding documents under [bindings/](bindings/README.md). This appendix
**MUST NOT** be read as requiring `initialize` as the only negotiation path for
Profiles A–H.

To enable third-party interoperability, conformant servers expose the profiles
over a JSON-RPC 2.0 `POST /mcp` dispatcher and parallel REST paths. Method
names and the execution result shape are canonical and MUST match:

| Profile | JSON-RPC method | REST path | Result fields |
|---|---|---|---|
| capability / discovery (binding-local) | See active MCP binding — legacy: `initialize`; current: per-request `_meta` and `server/discover` (and related) | — | binding-local capability advertisement of abstract keys in §3.3 |
| A (IDL) | `tools/list` | `GET /mcp/interfaces` | `interfaces[]` |
| B (CID exec) | `tools/call`, `mcp++/execute` | `POST /mcp/execute` | `output`, `envelope_cid`, `event_cid`, `receipt` |
| C (UCAN) | `mcp++/ucan/validate` | `POST /mcp/ucan/{delegate,revoke,validate}` | `valid`, `chain[]` |
| D (policy) | `mcp++/policy/evaluate` | `POST /mcp/policy/evaluate` | `decision`, `obligations[]`, `allowed` |
| E (P2P) | `mcp++/p2p/peers` | `GET /mcp/p2p/peers` | `peers[]`, `protocol` |
| F (Event DAG) | `mcp++/dag/{frontier,history,provenance,append,compact,archive,archives,certificate/get,certificate/verify,inclusion,zk/status,zk/prove,zk/verify}` | `GET /mcp/dag/{frontier,history,provenance/{cid},archives,certificates/{cid},inclusion/{cid},zk/status}`; `POST /mcp/dag/{append,compact,archive,certificates/verify,zk/prove,zk/verify}` | bounded `frontier[]`/`events[]`/`chain[]`, archive boundaries, certificate CIDs, and optional verifier-backed ZK certificates |
| H (x402 payments) | `mcp++/payments/{profile,catalog,quote,verify,settle,receipt/get,entitlement/get,usage/get,refund/request,reconcile}` | HTTP 402 + `PAYMENT-REQUIRED` / `PAYMENT-SIGNATURE` / `PAYMENT-RESPONSE`; REST paid dispatch under `/mcp` | `PaymentQuote`, `PaymentAuthorization`, `SettlementReceipt`, `PaidEntitlement`, `AccessReceipt` (see [docs/spec/x402-payments.md](x402-payments.md)) |

The `mcp++/execute` `receipt` object MUST include `success` and SHOULD include
`receipt_cid`, `output_cid`, `error`, `duration_ms`; signed receipts add
`signature`. CID-native deployments require `receipt_cid` + `output_cid`. All
CIDs in these payloads MUST satisfy the CID format regex in
`cid-native-artifacts.md`.

Abstract capability keys (binding-independent identifiers) are listed in §3.3:
`mcp++/mcp-idl`, `mcp++/cid-envelope`, `mcp++/ucan`, `mcp++/deontic-policy`,
`mcp++/event-dag` (Profile F), `mcp++/p2p-transport`, `mcp++/risk-scheduling`,
`mcp++/x402-payments` (Profile H).

Profile H over Profile E carries the same decoded x402 objects as the HTTP
carriage. The libp2p representation is an MCP++ **transport** binding and
**MUST NOT be represented as upstream x402 HTTP conformance**. Claim both only
when the HTTP side passes upstream vectors and object translation passes
Profile H parity vectors.

### A.1 Canonical Error Codes (Normative)

JSON-RPC error responses MUST use these codes; meanings are normative:

| Code | Meaning |
|---|---|
| `-32700` | Parse error (malformed JSON) |
| `-32600` | Invalid request (e.g. bad id) |
| `-32601` | Method not found / tool not found |
| `-32602` | Invalid params |
| `-32603` | Internal error |
| `-32000` | Server/execution error (incl. tool timeout) |

Validators expose these as `ErrorCode` (py/ts) and `error_code::*` (rs).

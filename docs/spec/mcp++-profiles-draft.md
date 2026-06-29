# MCP++: CID-Native, Contract-Driven Execution Profiles for MCP

**Status:** Draft (Non-Normative / Discussion)

---

## 1. Introduction

This document defines **MCP++**, a set of *optional, backward-compatible execution profiles* for the Model Context Protocol (MCP). MCP++ is designed to support federated, multi-agent, and parallel execution environments while preserving MCP message semantics and incremental adoptability.

MCP++ addresses two practical pressures observed in production deployments:
1. **Extension fragmentation** and uncertain compatibility across clients and servers.
2. **Context and toolset constraints** that prevent reliable utilization of large or evolving tool ecosystems.

MCP++ introduces modernized solutions inspired by historical distributed systems (e.g., interface repositories and brokers), implemented in a content-addressed, capability-secure, and policy-aware manner suitable for AI-native systems.

## 1.1 Spec Chapters

This draft is the top-level profile registry. The component details live in these chapters:

- [Profile A: MCP-IDL (CID-Addressed Interface Contracts)](mcp-idl.md)
- [Profile B: CID-Native Execution Artifacts](cid-native-artifacts.md)
- [Profile C: Capability Delegation (UCAN)](ucan-delegation.md)
- [Profile D: Temporal Deontic Policy Evaluation](temporal-deontic-policy.md)
- [Event DAG, Concurrency, and Ordering](event-dag-ordering.md)
- [Risk Scoring, Neighborhood Consensus, and Scheduling](risk-scheduling.md)
- [Profile E: `mcp+p2p` Transport Binding](transport-mcp-p2p.md)

---

## 2. Terminology

- **CID**: Content Identifier (immutable, hash-addressed reference to canonicalized content).
- **Profile**: An optional, negotiable MCP capability that adds semantics without changing core MCP messages.
- **Interface Descriptor**: A canonical, content-addressed contract describing a tool/resource interface.
- **Execution Envelope**: A CID-native wrapper around an MCP invocation.
- **Event DAG**: A directed acyclic graph of execution events linked by causal references.
- **Policy CID**: A content-addressed representation of time-bounded permissions, prohibitions, and obligations.

Normative keywords **MUST**, **SHOULD**, and **MAY** are used as described in RFC 2119.

---

## 3. Compatibility Model

MCP++ profiles are negotiated during MCP initialization using existing capability negotiation mechanisms. Implementations that do not support MCP++ MUST continue to interoperate using baseline MCP semantics.

The `initialize` handshake is normative: clients send `InitializeParams`
(`protocolVersion` `2024-11-05`, `clientInfo`, `capabilities` with desired
profiles under `capabilities.experimental` as `{"mcp++/<profile>": true}`); the
server replies with `InitializeResult` (`protocolVersion`, `serverInfo`,
`capabilities.experimental` echoing the supported subset). Both shapes are
validated by the `InitializeParams`/`InitializeResult` spec models.

No MCP++ profile modifies or invalidates existing MCP JSON-RPC message formats.

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

The `mcp+p2p` transport profile defines carriage of MCP JSON-RPC messages over a peer-to-peer substrate (specifically, a libp2p binding in this draft). Message semantics remain unchanged.

### 8.2 Eventing

Implementations MAY support bidirectional streams and event publication for receipts, interface descriptors, and coordination signals.

See: [docs/spec/transport-mcp-p2p.md](transport-mcp-p2p.md)

---

## 9. Event DAG and Provenance

### 9.1 Event Structure (Normative)

Each event CID MUST commit to:
- intent
- interface
- proofs
- decision
- outputs
- parents

### 9.2 Unrolling and Audit

Causal traversal of the Event DAG enables deterministic replay, rollback, and attribution.

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

---

## 14. Open Questions

- Canonicalization standards for interface descriptors
- Policy language interoperability
- Registry vs. gossip-based discovery tradeoffs

---

## 15. Conclusion

MCP++ extends MCP into federated, multi-agent domains by introducing contract clarity, immutable provenance, explicit delegation, and policy-aware execution—without deprecating or breaking existing MCP deployments.

---

## Appendix A: HTTP/JSON-RPC Wire Binding (Normative)

To enable third-party interoperability, conformant servers expose the
profiles over a JSON-RPC 2.0 `POST /mcp` dispatcher and parallel REST paths.
Method names and the execution result shape are canonical and MUST match:

| Profile | JSON-RPC method | REST path | Result fields |
|---|---|---|---|
| handshake | `initialize` | — | `capabilities.experimental{mcp++/*}` |
| A (IDL) | `tools/list` | `GET /mcp/interfaces` | `interfaces[]` |
| B (CID exec) | `tools/call`, `mcp++/execute` | `POST /mcp/execute` | `output`, `envelope_cid`, `event_cid`, `receipt` |
| C (UCAN) | `mcp++/ucan/validate` | `POST /mcp/ucan/{delegate,revoke,validate}` | `valid`, `chain[]` |
| D (policy) | `mcp++/policy/evaluate` | `POST /mcp/policy/evaluate` | `decision`, `obligations[]`, `allowed` |
| E (P2P) | `mcp++/p2p/peers` | `GET /mcp/p2p/peers` | `peers[]`, `protocol` |
| DAG | — | `GET /mcp/dag/{frontier,history,provenance/{cid}}` | `frontier[]`/`events[]`/`chain[]` |

The `mcp++/execute` `receipt` object MUST include `receipt_cid`, `output_cid`,
`success`, `error`, `duration_ms`; signed receipts add `signature`. All CIDs in
these payloads MUST satisfy the CID format regex in `cid-native-artifacts.md`.
Capability negotiation keys are: `mcp++/mcp-idl`, `mcp++/cid-envelope`,
`mcp++/ucan`, `mcp++/deontic-policy`, `mcp++/event-dag`, `mcp++/p2p-transport`.

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



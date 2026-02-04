# Archive → Canonical Traceability

This page is an **audit checklist** to ensure the curated docs/specs capture the key ideas from the raw design artifact.

- **Archive artifact:** [docs/_archive/chatgpt.html](../_archive/chatgpt.html)
- **Canonical docs entrypoint:** [docs/index.md](../index.md)

## Why this exists

The canonical spec uses standard terms (e.g., “Merkle clock”, “Fibonacci heap”). The archive sometimes contains misspellings or mis-hearings (e.g., “meekly clock”, “fibinocci heap”). We preserve those as **explicit aliases** so future contributors/agents can still find the intent.

## Checklist (high-signal phrases)

Each row is: **archive phrase → canonical concept → canonical location(s)**.

| Archive phrase (literal) | Canonical concept | Canonical doc(s) |
|---|---|---|
| optional profile (no fork) | Backward-compatible profile mechanism | [docs/spec/mcp++-profiles-draft.md](../spec/mcp++-profiles-draft.md) |
| libp2p for the transport layer | Optional P2P transport binding (`mcp+p2p`) | [docs/spec/transport-mcp-p2p.md](../spec/transport-mcp-p2p.md) |
| capability/audit envelope | CID-addressed wrapper around MCP calls | [docs/spec/cid-native-artifacts.md](../spec/cid-native-artifacts.md) |
| ucan system / chains of permission | Capability delegation chains (UCAN-style) | [docs/spec/ucan-delegation.md](../spec/ucan-delegation.md) |
| temporal deontic first order logic | Temporal deontic policy evaluation | [docs/spec/temporal-deontic-policy.md](../spec/temporal-deontic-policy.md) |
| content addressing / immutability | CID-native artifacts and canonicalization | [docs/spec/cid-native-artifacts.md](../spec/cid-native-artifacts.md) |
| CID-based execution envelope / CID-Native Execution Envelope | Execution envelopes referencing inputs/outputs/policy/proofs by CID | [docs/spec/cid-native-artifacts.md](../spec/cid-native-artifacts.md) |
| Intent CID | CID-addressed proposed action | [docs/spec/cid-native-artifacts.md](../spec/cid-native-artifacts.md), [docs/architecture/glossary.md](glossary.md) |
| Policy CID | CID-addressed policy | [docs/spec/temporal-deontic-policy.md](../spec/temporal-deontic-policy.md), [docs/architecture/glossary.md](glossary.md) |
| Decision CID | CID-addressed policy evaluation result | [docs/spec/temporal-deontic-policy.md](../spec/temporal-deontic-policy.md), [docs/architecture/glossary.md](glossary.md) |
| Receipt CID | CID-addressed execution attestation | [docs/spec/cid-native-artifacts.md](../spec/cid-native-artifacts.md), [docs/architecture/glossary.md](glossary.md) |
| Proof CID | CID-addressed proof bundle (e.g., UCAN chain) | [docs/spec/ucan-delegation.md](../spec/ucan-delegation.md), [docs/architecture/glossary.md](glossary.md) |
| credit assignment | Receipts + provenance for attribution | [docs/spec/cid-native-artifacts.md](../spec/cid-native-artifacts.md), [docs/spec/event-dag-ordering.md](../spec/event-dag-ordering.md) |
| unroll transactions | Replay/rollback via Event DAG provenance | [docs/spec/event-dag-ordering.md](../spec/event-dag-ordering.md) |
| actions (often in parallel) | Concurrency model + partial ordering | [docs/spec/event-dag-ordering.md](../spec/event-dag-ordering.md) |
| hamming distance | Locality / neighborhood grouping signal | [docs/spec/risk-scheduling.md](../spec/risk-scheduling.md) |
| locality sensitive hash | LSH-based clustering / neighbor selection | [docs/spec/risk-scheduling.md](../spec/risk-scheduling.md) |
| k nearest neighbors | kNN neighborhood consensus boundary | [docs/spec/risk-scheduling.md](../spec/risk-scheduling.md) |
| meekly clock | Merkle clock (alias preserved) | [docs/spec/event-dag-ordering.md](../spec/event-dag-ordering.md), [docs/architecture/glossary.md](glossary.md) |
| fibinocci heap | Fibonacci heap (alias preserved) | [docs/spec/risk-scheduling.md](../spec/risk-scheduling.md), [docs/architecture/glossary.md](glossary.md) |
| consensus between the peer group | Neighborhood consensus / attestation | [docs/spec/risk-scheduling.md](../spec/risk-scheduling.md) |
| speculate about the future tasks | Speculative scheduling / frontier planning | [docs/spec/risk-scheduling.md](../spec/risk-scheduling.md) |
| extension fragmentation / CORBA/IDL vibe | Profiles + MCP-IDL + toolset slicing | [docs/spec/mcp++-profiles-draft.md](../spec/mcp++-profiles-draft.md), [docs/spec/mcp-idl.md](../spec/mcp-idl.md) |
| CORBA→MCP 2.0 | CORBA analogy for contracts + compatibility + runtime introspection | [docs/spec/mcp-idl.md](../spec/mcp-idl.md), [docs/architecture/glossary.md](glossary.md) |
| Agent Object Protocol | Event-driven, strongly-typed “agent object” interaction framing | [docs/spec/mcp-idl.md](../spec/mcp-idl.md), [docs/architecture/glossary.md](glossary.md) |
| mandatory tool versioning/compatibility metadata | Interface descriptors carry explicit version/compatibility fields | [docs/spec/mcp-idl.md](../spec/mcp-idl.md) |
| callbacks / event streams | Declared streaming/eventing interface patterns (avoid polling) | [docs/spec/mcp-idl.md](../spec/mcp-idl.md), [docs/spec/transport-mcp-p2p.md](../spec/transport-mcp-p2p.md) |
| mandatory observability hooks (trace IDs, provenance metadata) | Trace/provenance propagation as a first-class, declared capability | [docs/spec/mcp-idl.md](../spec/mcp-idl.md), [docs/spec/cid-native-artifacts.md](../spec/cid-native-artifacts.md) |
| deterministic canonicalization pipeline | Canonicalization requirements for CID computation | [docs/spec/cid-native-artifacts.md](../spec/cid-native-artifacts.md), [docs/spec/mcp-idl.md](../spec/mcp-idl.md) |

## How to extend

When you add a new canonical section based on something from the archive:

1. Add a row to this table with the *literal* archive phrase.
2. Add an alias note in the relevant spec chapter and/or [docs/architecture/glossary.md](glossary.md) if spelling/terminology differs.



# Profile F: Event DAG Provenance, Archival, and Compaction

**Status:** Draft

This document defines **Profile F: Event DAG Provenance, Archival, and
Compaction**. It uses the negotiated capability key `mcp++/event-dag` and a
content-addressed Event DAG to provide provenance, replay, rollback, partial
ordering, and bounded retention for parallel actions.

## 1. Event DAG Basics

- Each execution emits an **event node** (CID’d) that references inputs, proofs, decisions, outputs, and receipts.
- Events reference `parents[]` to establish causal dependencies.

This makes the execution history:
- append-only,
- content-addressed,
- traversable for audit and replay.

## 2. “Unrolling transactions”

If every event is content-addressed and linked to its parents, then:

- Rollback/dispute analysis becomes: “walk the DAG from a root and inspect exactly what inputs produced what outputs.”
- Credit assignment becomes: “attribute receipts and outputs to peer DIDs.”

## 3. Partial Order (No Global Sequencer)

Parallelism is expected (multiple agents, multiple tools). MCP++ therefore aims for a **strict partial order**:

- If event B depends on event A, then A ∈ parents(B).
- If two events are independent, they are concurrent (no total order required).

## 4. Merkle-Clock / Merkle-CRDT (Non-Normative)

A common approach in Merkle-DAG-based systems is to construct a “Merkle-clock-ish” ordering layer:

- events form a DAG frontier,
- frontiers can be compared to establish “happened-before” when possible,
- concurrent operations remain unordered until a reconciliation rule is applied.

MCP++ does not require CRDT semantics initially; it only requires that events and dependencies are recorded as CIDs.

Note: the archived design chat used the phrase “meekly clock”; this spec uses the standard term “Merkle clock”.

## 5. Conflict Detection and Resolution

Implementations SHOULD support:
- detecting conflicting intents that touch the same resources or violate invariants,
- escalating to stronger coordination only when conflicts or risk thresholds demand it.

Local coordination mechanisms are described in [docs/spec/risk-scheduling.md](risk-scheduling.md).

## 6. Suggested Event Fields

Event nodes on the wire MUST carry: `event_cid` (CID per `cid-native-artifacts.md`),
`event_type`, `parents[]`, `timestamp` (ISO 8601 string or epoch seconds), and a
generic `payload` object holding type-specific fields (e.g. `intent_cid`,
`decision_cid`, `output_cid`, `receipt_cid`). Canonical `event_type` values are:
`invocation`, `result`, `error`, `delegation`, `policy_decision`, `intent`,
`decision`, `receipt`, `envelope`. Implementations MAY add extra top-level keys.

See [docs/spec/cid-native-artifacts.md](cid-native-artifacts.md) for suggested `event_cid` shape.

## 7. Archival and Compaction

Implementations SHOULD keep a bounded hot tier for recent events and compact
older epochs only after creating a durable archive. An archive stores the
original event records, their ordered CID list, and enough Merkle layers to
produce inclusion proofs. This lets a verifier recover an individual historic
event or validate its membership without loading the entire DAG into memory.

The archive is summarized by a compaction certificate with `certificate_cid`,
`archive_cid`, `merkle_root`, `event_count`, `root_cids`, `frontier_cids`,
`proof_system`, and `zero_knowledge`. Provenance responses that reach compacted
history MUST return the archive and certificate references as a traversal
boundary. They MUST NOT require unbounded recursive traversal.

An integrity hash or simulated proof is not a zero-knowledge proof. Such a
certificate MUST identify its proof system and set `zero_knowledge: false`.
Only a certificate produced and verified by an actual ZK proof system, with a
verifiable statement and verification key, MAY set `zero_knowledge: true`.

## 8. Security Considerations

- Parent links MUST be immutable and verifiable by CID.
- Replayers/auditors must validate that referenced CIDs are available and canonicalized under agreed rules.

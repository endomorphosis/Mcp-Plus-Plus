# Event DAG, Concurrency, and Ordering

**Status:** Draft

This document explains how MCP++ uses a content-addressed Event DAG to provide provenance, replay, rollback, and partial ordering for parallel actions.

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

See [docs/spec/cid-native-artifacts.md](cid-native-artifacts.md) for suggested `event_cid` shape.

## 7. Security Considerations

- Parent links MUST be immutable and verifiable by CID.
- Replayers/auditors must validate that referenced CIDs are available and canonicalized under agreed rules.

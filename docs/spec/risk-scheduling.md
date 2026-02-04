# Risk Scoring, Neighborhood Consensus, and Scheduling

**Status:** Draft (Mostly Non-Normative)

This document expands MCP++’s “systems layer”: how immutable history can drive risk scoring and how parallel execution can be prioritized and coordinated without a single global chain.

## 1. Risk Scoring Inputs

Peers MAY accumulate reputation/risk based on immutable evidence such as:

- attempted capability/policy violations
- anomaly rates
- divergence from predicted outcomes
- frequency of rollbacks/disputes in their event subgraph
- missed obligations (deadline violations)
- frequency of disputed receipts

A key property: once artifacts are CID-native, risk can be computed *from the Event DAG itself* rather than ad-hoc logs.

## 2. Locality-Sensitive Grouping (Non-Normative)

To scale coordination, implementations MAY bucket related events/peers using:

- Hamming distance over feature sketches
- locality-sensitive hashing (LSH) for approximate nearest neighbors
- a k-nearest-neighbor overlay for faster convergence

“Feature sketches” may include behavior signatures, interface usage patterns, or event-graph summaries.

## 3. Prioritization Frontier

A scheduler can maintain a task/event frontier keyed by:

- expected value
- risk-adjusted cost
- dependency readiness
- distance to the local frontier (cluster proximity)

### 3.1 Fibonacci Heap Rationale (Non-Normative)

A Fibonacci heap is plausible when priorities change frequently (many `decrease-key` operations) as new receipts/decisions arrive.

## 4. Lightweight (Neighborhood) Consensus

Rather than “one chain to rule them all,” MCP++ can use neighborhood agreement:

- peers converge on ordering within local clusters
- commitments propagate outward
- escalate to stronger consensus only when conflicts or risk thresholds trigger it

## 5. Interface Contracts and Toolset Slicing Integration

This layer benefits from MCP-IDL:
- a node can prioritize intents by interface CID and known compatibility,
- toolset slicing can select the best subset under a context budget.

See [docs/spec/mcp-idl.md](mcp-idl.md).

## 6. Open Questions

- Standard sketches/feature vectors for interoperability
- How to represent and exchange “risk evidence” without leaking sensitive data
- When and how to escalate from neighborhood consensus to stronger coordination

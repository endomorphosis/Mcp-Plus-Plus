# Project Overview

## What is MCP++?

**MCP++** is a set of *optional, backward-compatible execution profiles* intended to extend MCP deployments into more distributed and policy-constrained environments.

MCP++’s core design stance:

- **Do not break MCP**: keep MCP JSON-RPC message semantics intact.
- Add functionality via **profile negotiation** and **wrapping/enveloping**.
- Make artifacts **content-addressed (CID-native)** so provenance is verifiable and immutable by construction.

## Core concepts

- **Profiles**: Negotiable capabilities that add semantics without changing baseline messages.
- **Interface descriptors (CID-addressed)**: Contracts for tools/resources; enable compatibility checks and toolset slicing.
- **Execution envelopes**: Wrappers around invocations that reference CID’d inputs/intent/policy/proofs.
- **Event DAG**: Append-only, content-addressed execution history with causal links.
- **Delegation and policy**: Capability chains (e.g., UCAN) and temporal deontic policies (permissions/prohibitions/obligations).
- **Transport binding (optional)**: e.g., `mcp+p2p` for carriage of MCP messages over a P2P substrate.

Transport is a primary **trust and failure boundary**: it shapes identity, connectivity, multiplexing, and abuse resistance. MCP++ keeps it optional to preserve incremental adoptability, but treats it as a first-class profile because federation and cross-org execution quickly run into transport limitations.

## Intended outcomes

- Reliable tool interoperability at scale (contracts + compatibility)
- Auditability and replay (event DAG)
- Least-privilege delegation across multi-hop workflows (capabilities)
- Explicit policy evaluation and decision receipts (deontic/temporal)
- Operational leverage: a **capability ledger + immutable audit trail** makes **incident response** and **blast-radius control** more feasible in complex agent graphs (archive framing).

## Non-goals (for now)

- Defining a single global consensus mechanism
- Replacing MCP’s baseline transports
- Locking into one policy language or one capability token format

## Documents

- Draft spec: [docs/spec/mcp++-profiles-draft.md](../spec/mcp++-profiles-draft.md)
- Spec chapters:
	- [docs/spec/mcp-idl.md](../spec/mcp-idl.md)
	- [docs/spec/cid-native-artifacts.md](../spec/cid-native-artifacts.md)
	- [docs/spec/ucan-delegation.md](../spec/ucan-delegation.md)
	- [docs/spec/temporal-deontic-policy.md](../spec/temporal-deontic-policy.md)
	- [docs/spec/event-dag-ordering.md](../spec/event-dag-ordering.md)
	- [docs/spec/risk-scheduling.md](../spec/risk-scheduling.md)
	- [docs/spec/transport-mcp-p2p.md](../spec/transport-mcp-p2p.md)
- Glossary: [docs/architecture/glossary.md](glossary.md)

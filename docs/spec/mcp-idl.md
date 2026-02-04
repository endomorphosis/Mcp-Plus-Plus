# Profile A: MCP-IDL (CID-Addressed Interface Contracts)

**Status:** Draft

This document expands the MCP++ “MCP-IDL” profile: a CID-addressed, runtime-queryable interface contract system intended to reduce extension/tool fragmentation and enable reliable compatibility checks.

## 1. Goals

- Provide a **machine-readable, hashable contract** for tools/resources/prompts.
- Make compatibility checks **deterministic** (set operations over immutable IDs).
- Support **runtime discovery** (not “read docs and guess”).
- Enable **toolset slicing** under context/token/compute budgets.
- Remain **non-breaking**: baseline MCP messages remain valid.

## 1.1 Historical Notes (Non-Normative)

The archived design research uses CORBA-era language (e.g., “IDL”, “Interface Repository”, “ORB”) and the phrase “Agent Object Protocol (AOP)” as an analogy for the missing pieces in fragmented agent ecosystems: strongly-typed contracts, runtime compatibility introspection, and event-driven workflows.

MCP-IDL adopts the *useful* conceptual pieces (contracts + runtime query + compatibility metadata) while remaining CID-first and optional; it is not a dependency on CORBA or legacy CORBA stacks.

Alias note: the archive also uses the phrase “interface contract object” to describe the universally comparable contract; in MCP-IDL this is the Interface Descriptor content-addressed as `interface_cid`.

## 2. Conceptual Model

- An **Interface Descriptor** is canonical content (schema + metadata).
- Its canonical bytes are content-addressed into an `interface_cid`.
- Clients negotiate support via MCP capability negotiation.
- A server exposes query APIs so clients can list/get/compare descriptors.

## 3. Canonicalization and `interface_cid`

Implementations MUST define a deterministic canonicalization pipeline for Interface Descriptors. Acceptable approaches include canonical JSON, DAG-JSON, or DAG-CBOR.

- The `interface_cid` MUST be computed from the canonical bytes.
- Two descriptors that are semantically identical SHOULD produce the same `interface_cid` (this is the point of canonicalization).

## 4. Interface Descriptor (Normative)

An Interface Descriptor MUST include enough information for clients to:
- validate input/output shapes,
- understand error surface,
- assess compatibility and required extensions/capabilities.

### 4.1 Required Fields

- `name`: stable human identifier
- `namespace`: grouping / ownership scope
- `version`: descriptor version (semantic versioning recommended)
- `methods[]`: method signatures and their input/output schemas
- `errors[]`: error types surfaced by the interface
- `requires[]`: required capabilities/extensions
- `compatibility`: compatibility metadata (e.g., `compatible_with[]`, `supersedes[]`)

### 4.2 Recommended Fields

- `semantic_tags[]`: stable tags for retrieval/tool selection
- `observability`: trace/provenance hooks supported/expected
- `interaction_patterns`: declared request/response vs callback/event-stream patterns
- `resource_cost_hints`: approximate runtime/token/network hints
- `schema_hash`: hash of the descriptor schema portion (redundant to CID, but useful for sub-selection)

### 4.3 Minimal JSON Shape (Example)

```json
{
  "name": "git",
  "namespace": "com.example.tools",
  "version": "1.2.0",
  "methods": [
    {
      "name": "repo.status",
      "input_schema_cid": "bafy...",
      "output_schema_cid": "bafy...",
      "error_schema_cids": ["bafy..."]
    }
  ],
  "errors": [{"name": "NotFound"}, {"name": "Unauthorized"}],
  "requires": ["mcp++/cid-envelope", "mcp++/ucan"],
  "compatibility": {
    "compatible_with": ["bafy..."],
    "supersedes": ["bafy..."]
  },
  "semantic_tags": ["vcs", "git"],
  "observability": {"trace": true, "provenance": true},
  "interaction_patterns": {
    "request_response": true,
    "event_streams": false
  }
}
```

### 4.4 Streaming and Callbacks (Non-Normative)

Some tools are best modeled as event streams (“callbacks / event streams”) rather than repeated polling. MCP-IDL allows descriptors to declare this in a purely descriptive way so clients can do graceful degradation:

- A method MAY be described as producing a stream of events (or a server MAY expose a separate event endpoint).
- If streaming/eventing is used, the descriptor SHOULD provide an `event_schema_cid` (or equivalent) so receivers can validate event payloads.

## 5. Interface Repository APIs (Normative)

A server that advertises MCP-IDL support MUST expose the following tool/resource methods (names are provisional; align with MCP naming conventions later):

- `interfaces/list` → returns a list of `interface_cid`s
- `interfaces/get(interface_cid)` → returns the canonical Interface Descriptor bytes (or a CID that retrieves them)
- `interfaces/compat(interface_cid)` → returns a compatibility verdict and reasons

### 5.1 Compatibility Verdict

`interfaces/compat` SHOULD return:
- `compatible: boolean`
- `reasons[]`: structured reasons for incompatibility
- `requires_missing[]`: missing capabilities
- `suggested_alternatives[]`: interface CIDs that may satisfy intent

## 6. Toolset Slicing (Optional but Important)

To handle context/toolset limits, servers MAY expose:

- `interfaces/select(task_hint_cid, budget)` → returns a recommended subset of interface CIDs

Notes:
- `budget` can be defined as token budget, bytes, or a composite.
- `task_hint_cid` may reference an embedding, a natural language task description, or a prior intent DAG node.

## 7. Distribution (P2P-Friendly)

MCP-IDL does not require P2P, but benefits from it:
- descriptors can be gossiped via DHT/pubsub patterns,
- clients can fetch descriptors by CID from multiple peers,
- registries become optional discovery accelerators rather than single sources of truth.

## 8. Security Considerations

- Descriptors are **not authority**. Authorization to fetch/execute interfaces MUST be enforced separately (e.g., UCAN).
- Clients SHOULD treat descriptors as untrusted input (validate schemas; guard against resource exhaustion).

## 9. Open Questions

- Canonicalization standard (pick one; publish test vectors).
- How to represent semantic compatibility beyond schema-level matching.
- How to standardize a budget model for toolset slicing.

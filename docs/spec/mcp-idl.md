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
- `methods[]`: method signatures, each with `name`, inline `input_schema`/`output_schema`, optional `errors[]` (string names), and `streaming`
- `errors[]`: interface-level error names (strings)
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
      "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
      "output_schema": {"type": "object"},
      "errors": ["NotFound", "Unauthorized"],
      "streaming": false
    }
  ],
  "errors": ["NotFound", "Unauthorized"],
  "requires": ["mcp++/cid-envelope", "mcp++/ucan"],
  "compatibility": {
    "compatible_with": ["bafkrei..."],
    "supersedes": ["bafkrei..."]
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

## 10. Agent Advertisement (`AgentAdvertisement@1`)

**Status:** Normative (MCP++ 1.0 discovery)  
**Interface label:** `AgentAdvertisement@1`  
**Schema marker:** `mcp++/discovery/agent-advertisement@1`  
**Schema path:** `ipfs_accelerate_py/mcplusplus/schemas/discovery/agent-advertisement-1.schema.json`  
**Related:** [a2a-extension.md](a2a-extension.md) (`AgentCardMapping@1`), goal `MCPP-G110`, tasks `MCPP-058`…`MCPP-061`

Profile A Interface Descriptors say **what** can be executed (`interface_cid`). An **agent advertisement** says **who** claims to execute those interfaces, **where** they are reachable, and **under what** non-authoritative selection constraints (health, load, TTL, locality, price).

Finding an advertisement is **not** permission to execute. A registry record is **never** execution authority (plan KD-14; MCPP-G110). UCAN / policy proofs authorize invocation; the advertisement only aids discovery and routing.

### 10.1 Required fields (fail-closed)

JSON Schema validation **MUST** reject advertisements that omit any of:

| Field | Meaning |
| --- | --- |
| `identity` | Principal identity object (`did` required; optional `name`, `description`, `version`, `url`, `key_id`, `peer_id`) |
| `ttl_ms` | Freshness TTL in milliseconds (1…604800000) |
| `interface_cids` | List of MCP-IDL Interface Descriptor CIDs (array required; may be empty only when advertising presence without executable interfaces) |

The closed schema marker `schema: "mcp++/discovery/agent-advertisement@1"` is also required.

Registries **MUST** additionally reject **stale** records (past `expires_at_ms`, or past `published_at_ms + ttl_ms` when absolute expiry is omitted) and, when the deployment requires signed ads, **unsigned** or **invalidly signed** records. Health and load are **selection inputs**, not trust.

### 10.2 Full field inventory

| Field | Required | Role |
| --- | --- | --- |
| `schema` | yes | Schema marker |
| `identity` | yes | Agent principal + display fields |
| `ttl_ms` | yes | Advertisement TTL |
| `interface_cids` | yes | Executable Interface Descriptor CIDs |
| `endpoints` | no | Service URLs / multiaddrs by role |
| `transports` | no | Accepted transport ids |
| `mcp_versions` | no | ADR-0006 MCP binding ids |
| `a2a_version` | no | A2A protocol version string |
| `profiles` | no | MCP++ profile letters A–H |
| `policy_languages` | no | Policy dialect ids |
| `proof_systems` | no | Delegation / signature systems |
| `runtimes` | no | Runtime family hints |
| `accelerators` | no | Resource-class / accelerator hints |
| `locality` | no | Region / zone / country / network |
| `price` | no | Non-authorizing price hints |
| `health` | no | Health snapshot (selection only) |
| `load` | no | Utilization / capacity (selection only) |
| `published_at_ms` / `expires_at_ms` | no | Publication and absolute expiry |
| `trust_domain` | no | Trust-domain id and/or CID |
| `residency` | no | Data residency / jurisdiction |
| `confidentiality` | no | Encrypted-artifact / TEE claims |
| `skills` | no | A2A skill projections |
| `a2a_extension` | no | Projection of the execution extension entry |
| `canonicalization` | no | `mcpp-jcs-v1` when content-addressed |
| `signature` | no | Integrity signature block |
| `metadata_cid` | no | Non-authoritative free-form metadata |

### 10.3 Minimal valid example

```json
{
  "schema": "mcp++/discovery/agent-advertisement@1",
  "identity": {
    "did": "did:web:agent.example",
    "name": "example-git-agent"
  },
  "ttl_ms": 300000,
  "interface_cids": [
    "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
  ]
}
```

Missing `identity`, missing `ttl_ms`, or missing `interface_cids` **MUST** fail schema validation.

### 10.4 Mapping to A2A Agent Card (`AgentCardMapping@1`)

MCP++ does **not** replace the A2A Agent Card. When an agent claims A2A interop with MCP++ execution evidence, the advertisement **projects onto** the card and the execution extension declared in [a2a-extension.md](a2a-extension.md) §4.1 and §6.1.

| AgentAdvertisement@1 | A2A Agent Card surface | Notes |
| --- | --- | --- |
| `identity.name` | `AgentCard.name` | Display name |
| `identity.description` | `AgentCard.description` | Human description |
| `identity.version` | `AgentCard.version` | Card / agent version string |
| `identity.url` or primary `endpoints[]` with `role: "a2a"` | `AgentCard.url` | Preferred public A2A endpoint |
| `identity.did` / `key_id` | Card security schemes / auth material | DID is principal identity; PeerID is transport-only |
| `skills[]` | `AgentCard.skills[]` | `id` / `name` / `tags` align with IDL methods and `semantic_tags[]` |
| `skills[].interface_cid` / `method` | Skill `metadata` under the execution extension prefix | See a2a-extension.md §6.1 example |
| `interface_cids` | `AgentExtension.params.interface_cids` | Primary executable contracts |
| `profiles` | `AgentExtension.params.profiles` | MCP++ profile letters |
| `mcp_versions` | `AgentExtension.params.mcp_bindings` | ADR-0006 binding ids only |
| `a2a_extension.uri` | `AgentExtension.uri` | **MUST** be `https://mcplusplus.io/extensions/execution/v1` |
| `a2a_extension.params.*` | `AgentExtension.params` | Envelope/receipt/state-ref markers, canonicalization, alias |
| `a2a_version` | Card / capability version metadata | Informational; wire extension id remains the HTTPS URI |
| `transports` / non-A2A `endpoints` | Deployment-specific; not core A2A card fields | MAY appear as additional card metadata |
| `ttl_ms` / `expires_at_ms` | Registry freshness (not an A2A card field) | Cards may be cached separately; ads expire independently |
| `health` / `load` / `locality` / `price` | Selection hints only | **MUST NOT** be treated as authorization |
| `trust_domain` / `residency` / `confidentiality` | Policy / compliance selection | Still not execution authority |
| `signature` | Card or registry integrity | Registry rules own verification |

**Normative projection rules:**

1. When publishing both an Agent Card and an `AgentAdvertisement@1`, `interface_cids` on the advertisement **SHOULD** be a superset of (or equal to) `a2a_extension.params.interface_cids` and skill-level `interface_cid` values.
2. Skill `id` **SHOULD** match the IDL `methods[].name` (or a stable alias documented on the descriptor) when the skill is MCP-IDL-backed.
3. Agents that claim MCP++ A2A interop **MUST** set `a2a_extension.uri` to `https://mcplusplus.io/extensions/execution/v1` (never the reverse-DNS alias alone). See a2a-extension.md §2.2.
4. Descriptors and advertisements remain **not authority** (§8). Clients **MUST** obtain and verify delegation proofs before execution even when the card and advertisement agree.
5. Reverse mapping (card → advertisement) **MAY** synthesize a minimal ad from card identity, skills, and extension params for registry bootstrap; synthesized ads **MUST** still carry a concrete `ttl_ms` and the required fields of §10.1.

### 10.5 Relationship to Interface Repository APIs

| Mechanism | Answers |
| --- | --- |
| `interfaces/list` / `get` / `compat` (§5) | What contracts exist and whether they are compatible |
| `AgentAdvertisement@1` + registry (MCPP-059+) | Which agents claim to run which `interface_cid`s, where, and for how long |
| A2A Agent Card + execution extension | Public multi-agent discovery and lifecycle for A2A peers |

Clients **SHOULD** resolve `interface_cid` contents via MCP-IDL (or CID fetch) rather than trusting free-form card text for input/output shapes.

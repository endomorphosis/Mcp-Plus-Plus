# MCP++ Architecture Overview

**Status:** Architecture guide (MCP++ 1.0 gap-closure)  
**Interfaces:** `ArchitectureGuide@1`  
**Task:** MCPP-078 · Goal `MCPP-G170` · Bundle `mcplusplus/1.0/docs-architecture`  
**Authority:** Sealed plan Key Decisions KD-1…KD-17; ADRs 0001–0006  
**Document class:** **reference** (orientation) with **normative** cross-links to ADRs and specs

| Section | Authority class |
| --- | --- |
| §1 Purpose and design stance | reference |
| §2 Layered architecture | reference |
| §3 Profile model (A–H) | reference (profiles normative in their chapters) |
| §4 Profile bundles (KD-17) | **normative** packaging vocabulary |
| §5 Conformance levels | **normative** (ADR-0003) |
| §6 Portable carriers and state | reference → linked normative specs |
| §7 Durable execution | reference → [durable-execution.md](durable-execution.md) |
| §8 Trust and threat posture | reference → [trust-boundaries.md](trust-boundaries.md), [threat-model.md](threat-model.md) |
| §9 MCP / A2A bindings | reference → ADR-0006 and binding chapters |
| §10 Migration and compatibility | **non-normative** operator guidance |
| §11 Explicit non-claims | **normative** honesty rules for this guide |
| §12 Document map | reference |

This guide orients readers. Schema acceptance alone is never “implemented”
(ADR-0003). Documentation here does **not** admit production deployment by
itself; production admission requires named evidence at the claimed
conformance level.

---

## 1. Purpose and design stance

**MCP++** is a set of *optional, backward-compatible execution profiles* that
extend MCP deployments into distributed, capability-constrained, and
policy-aware environments.

Design stance:

1. **Do not break MCP.** Baseline JSON-RPC message formats remain valid for
   peers that never negotiate MCP++ profiles.
2. **Add via profiles and envelopes.** New semantics arrive through negotiated
   profile keys, CID-native artifacts, and versioned bindings—not by forking
   MCP wire messages for every peer.
3. **Content-address first.** Contracts, inputs, policies, proofs, events, and
   receipts are content-addressed (CID-native) so provenance is immutable by
   construction under a declared canonicalization algorithm.
4. **Fail closed.** Authorization, policy, signature, proof, lease, fencing,
   payment, and trust-boundary failures reject rather than soft-allow.
5. **Honest packaging.** Profile *bundles* (KD-17) group capabilities for
   assignment packaging; they do not invent a seventh security level or
   replace ADR-0003’s conformance ladder.

### 1.1 Intended outcomes

| Outcome | Primary mechanisms |
| --- | --- |
| Interoperable tools at scale | Profile A interface descriptors + compatibility APIs |
| Portable execution requests | `ExecutionEnvelope@1` family (KD-7) |
| Least-privilege multi-hop work | Profile C UCAN delegation + Profile D deontic policy |
| Audit and replay | Profile F Event DAG + DurableExecutor journals |
| Federated coordination | Profile E transport + Profile G risk/neighborhood (not BFT) |
| Paid access without auth elevation | Profile H x402 (payment ≠ authorization) |

### 1.2 Non-goals (program level)

- A single global consensus chain for all MCP++ state
- Replacing MCP baseline transports for every deployment
- Locking the ecosystem to one policy language or one token format beyond the
  mandatory crypto suite (ADR-0002)
- Claiming cryptographic, durability, or proof conformance without tests at
  those levels

---

## 2. Layered architecture

```text
┌──────────────────────────────────────────────────────────────────┐
│ Application / agents (hosts, tools, A2A tasks, operator UX)      │
├──────────────────────────────────────────────────────────────────┤
│ Profile semantics A–H (contracts, envelopes, caps, policy, DAG,  │
│   risk/scheduling, payments) — abstract, revision-independent    │
├──────────────────────────────────────────────────────────────────┤
│ Portable carriers: ExecutionEnvelope@1 / Result / Receipt /      │
│   PortableError@1 · StateRef@1 · DurableExecutor@1               │
├──────────────────────────────────────────────────────────────────┤
│ Versioned MCP bindings · optional A2A extension · transport      │
│   bindings (stdio / HTTP / mcp+p2p / …)                          │
├──────────────────────────────────────────────────────────────────┤
│ Runtime adapters (accelerate, datasets, kit, SwissKnife, …)      │
│   — consume schemas; do not redefine portable contracts          │
├──────────────────────────────────────────────────────────────────┤
│ Persistence: CID block store · SQLite state/journal · Automerge  │
│   · optional consensus plugins                                   │
└──────────────────────────────────────────────────────────────────┘
```

**Ownership (KD-1 / ADR-0001):** the mcplusplus / Mcp-Plus-Plus tree owns
schemas, vectors, validators, and matrices. Runtimes own adapters only.

---

## 3. Profile model (A–H)

Profiles are abstract capability modules. They define object models and
methods without requiring a specific MCP `protocolVersion` or carriage
transport (KD-2). Wire placement of capability keys is **binding-local**.

| Profile | Capability key | Concern |
| --- | --- | --- |
| **A** MCP-IDL | `mcp++/mcp-idl` | CID-addressed interface contracts, repository APIs, toolset slicing |
| **B** CID-native artifacts | `mcp++/cid-envelope` | Envelopes, outputs, receipts (legacy modular content; carrier family is Envelope@1) |
| **C** UCAN delegation | `mcp++/ucan` | Capability chains, attenuation, revocation |
| **D** Temporal deontic policy | `mcp++/deontic-policy` | Permissions, prohibitions, obligations, deadlines |
| **E** `mcp+p2p` transport | `mcp++/p2p-transport` | Optional P2P carriage of MCP messages |
| **F** Event DAG | `mcp++/event-dag` | Causal provenance, archival, compaction |
| **G** Risk / neighborhood / scheduling | `mcp++/risk-scheduling` | Risk scoring, neighborhood coordination, scheduling |
| **H** x402 payments | `mcp++/x402-payments` | Paid capability access; settlement is not authorization |

Registry entry: [../spec/mcp++-profiles-draft.md](../spec/mcp++-profiles-draft.md).

---

## 4. Profile bundles (KD-17)

**Authority class: normative** for packaging vocabulary.

MCP++ 1.0 groups Profiles A–H into **five profile bundles** for assignment
packaging, evidence-bundle labeling, and operator composition. A bundle is a
**declared set of profile keys (and related higher-level evidence rules)**—not
an automatic promotion of conformance level.

| Bundle | Profiles / contents | Intent |
| --- | --- | --- |
| **Evidence Core** | **A, B, F** | Contracts, CID-native artifacts / envelope lineage, Event DAG provenance suitable for audit and replay of published history |
| **Secure Delegation** | **C, D** | Cryptographic capability delegation plus temporal deontic policy evaluation |
| **Federated Mesh** | **E, G** | Optional P2P carriage plus neighborhood risk/scheduling coordination across peers |
| **Commerce** | **H** | Payment and paid access artifacts; settlement evidence without elevating authorization |
| **Verified Execution** | **Signed receipts / attestations / verified proofs only** | Cross-trust attestation path: independently verifiable `ExecutionReceipt@1` signatures, attestation objects, and proof objects that a real verifier accepts—not simulated proof-shaped JSON |

### 4.1 Bundle composition rules

1. Peers **MAY** implement a subset of Profiles A–H and still claim individual
   profile support under ADR-0003 scoring.
2. A **bundle claim** means the peer advertises (and, for higher levels, has
   evidence for) every profile or evidence class in that bundle’s definition.
3. **Verified Execution** is **not** “any receipt field present.” It requires
   the highest applicable levels among `receipt-signed` and `proof-verified`
   for the objects claimed (ADR-0003).
4. **Commerce** never implies **Secure Delegation**. Payment success **MUST
   NOT** grant UCAN capabilities or override policy deny (KD-14).
5. **Federated Mesh** never implies BFT. Profile G is `coordination` and/or
   `majority_approval` only (KD-11 / ADR-0004).
6. Bundle names **MUST NOT** be used as free-text substitutes for the six
   conformance level identifiers.

### 4.2 Bundle → typical evidence

| Bundle | Typical positive evidence | Must not count as success alone |
| --- | --- | --- |
| Evidence Core | IDL descriptors resolve; envelope/CID round-trip; Event DAG parents reconstruct order | Schema green without canonical identity where claimed |
| Secure Delegation | UCAN verify + attenuation negatives; policy evaluate + obligation lifecycle | Signature *field presence*; policy JSON without evaluation |
| Federated Mesh | Framing/abuse tests; neighborhood coordination labels honest | PeerID as authority; G labeled `bft` |
| Commerce | x402 settlement paths with payment≠auth negatives | Paid invoice as capability grant |
| Verified Execution | Independent receipt signature verify; real proof verifier on current vectors | Simulated Groth16 / digest-as-proof; transport identity as receipt authority |

---

## 5. Conformance levels

**Authority class: normative** (ADR-0003 / KD-6).

```text
structural → canonical → cryptographic → policy-enforced → receipt-signed → proof-verified
```

| Level | Meaning (short) |
| --- | --- |
| `structural` | Shape, types, enums; no security semantics |
| `canonical` | Same logical object → same canonical bytes / digest / CID |
| `cryptographic` | Signatures verified under mandatory suite (Ed25519, kid, DID-compatible iss/aud) |
| `policy-enforced` | Deontic evaluation runs; not field presence |
| `receipt-signed` | Cross-trust receipts signed and independently verifiable |
| `proof-verified` | Real verifier accepts proof objects on current vectors |

Promotion requires tests **at that level** (positive and negative). Line-coverage
documents and structural suites do not promote higher claims.

---

## 6. Portable carriers and shared state

| Carrier | Role | Normative chapter |
| --- | --- | --- |
| `ExecutionEnvelope@1` | Portable authorized request | [../spec/execution-envelope.md](../spec/execution-envelope.md) |
| `ExecutionResult@1` | Attempt outcome | same |
| `ExecutionReceipt@1` | Content-addressed attestation | same |
| `PortableError@1` | Portable failure | same |
| `StateRef@1` | Shared-state handle with exactly one consistency mode | [../spec/state-ref.md](../spec/state-ref.md), [state-model.md](state-model.md) |
| `DurableExecutor@1` | Crash-survivable multi-step execution | [durable-execution.md](durable-execution.md) |

Historical Profile B/G artifacts adapt into the envelope family **without
silent CID breakage** (versioned canonicalization; KD-5 / KD-7).

---

## 7. Durable execution (summary)

Multi-step agent work survives process death through a **journaled**
`DurableExecutor@1`. The mandatory production-capable adapter path is the
**SQLite journaled executor** (ADR-0005 / KD-12). Restate and Dapr are optional
second adapters only under repeatable local compose without unpaid cloud.

Separations:

| Mechanism | Authority for |
| --- | --- |
| Durable journal | Step commit, recover, cancel/timer persistence, fencing |
| Event DAG (F) | Causal audit trail of published events |
| StateRef modes | Shared mutable/immutable state consistency |

In-process memory retry is **not** crash recovery.

Details: [durable-execution.md](durable-execution.md).

---

## 8. Trust and threat posture

| Rule | Statement |
| --- | --- |
| KD-14 | Transport identity (PeerID, TLS client cert) **≠** execution authority |
| KD-14 | Payment **≠** authorization |
| KD-15 | Encrypted artifact references must not leak plaintext through logs, Event DAG metadata, or local fallback caches |
| Fail closed | Missing proofs, stale fences, revoked caps, policy deny → reject |

Guides:

- [trust-boundaries.md](trust-boundaries.md)
- [threat-model.md](threat-model.md)

---

## 9. MCP and A2A bindings

Profiles A–H stay independent of MCP revision. MCP++ 1.0 ships dual bindings
(ADR-0006 / KD-3):

| Binding id | MCP revision | Lifecycle shape |
| --- | --- | --- |
| `mcp-binding/legacy-2024-11-05` | `2024-11-05` | Session `initialize` / `notifications/initialized` (**legacy**) |
| `mcp-binding/2026-07-28` | `2026-07-28` | Stateless per-request `_meta`; **no** initialize (**current**) |

Current MCP **MUST NOT** be described as initialize-based. Silent downgrade
and version forgery fail closed.

A2A interoperability uses the verified extension URI
`https://mcplusplus.io/extensions/execution/v1` and **MUST NOT** invent a
competing public task lifecycle (KD-13).

Binding docs: [../spec/bindings/README.md](../spec/bindings/README.md) ·  
A2A: [../spec/a2a-extension.md](../spec/a2a-extension.md).

---

## 10. Migration and compatibility

**Authority class: non-normative** (operator guidance). Normative byte and CID
preservation rules live in ADR-0002 and the envelope/state chapters.

### 10.1 Compatibility principles

1. Baseline MCP peers that never advertise MCP++ continue to interoperate.
2. Historical artifacts remain readable under their **recorded**
   canonicalization algorithm; new mints use `mcpp-jcs-v1` (RFC 8785 JCS)
   when claiming MCP++ 1.0 identity.
3. Do not silently change bytes or CIDs of existing artifacts.
4. Dual-binding servers **MAY** accept legacy initialize **or** current
   `_meta` paths; they **MUST** name binding ids when claiming dual support.
5. Runtime adapters map local types into Envelope@1 / StateRef@1 without
   inventing a second portable contract.

### 10.2 Suggested migration sequence

| Step | Action | Bundle impact |
| --- | --- | --- |
| 1 | Inventory advertised profile keys and binding ids | All |
| 2 | Adopt Envelope@1 adapters for B/G artifacts | Evidence Core |
| 3 | Turn on real signature verify for C; policy evaluate for D | Secure Delegation |
| 4 | Declare StateRef modes; stop silent multi-writer merges | Evidence Core / Federated Mesh |
| 5 | Journal durable steps (SQLite adapter) before claiming crash-safe resume | Evidence Core ops |
| 6 | Separate payment settlement from authz checks | Commerce |
| 7 | Require independent receipt verify / real proof verify only when claiming Verified Execution | Verified Execution |

### 10.3 Compatibility matrix and release evidence

| Concern | Location |
| --- | --- |
| Requirement-to-evidence matrix | [../roadmap/mcplusplus-1.0-gap-closure.md](../roadmap/mcplusplus-1.0-gap-closure.md) |
| Binding compatibility | [../spec/bindings/compatibility-matrix.md](../spec/bindings/compatibility-matrix.md) |
| Implementation report (when published) | `docs/reports/MCPPLUSPLUS_1_0_IMPLEMENTATION_REPORT.md` (repo root under mcplusplus) |
| Three-peer demo / verifier | program gates 25–26; CLI `mcpp` path |

---

## 11. Explicit non-claims

This architecture guide **does not** claim:

- That current trees are admitted for production deployment without gate
  evidence (plan §11).
- That line-coverage or historical “validation complete” docs prove security.
- That Profile G is Byzantine-fault-tolerant consensus.
- That simulated proof artifacts satisfy Verified Execution.
- That schema acceptance equals `implemented` at cryptographic or higher levels.
- That PeerID, TLS client cert, registry presence, or payment settlement is
  execution authority.

G170 documentation policy forbids over-claim language that asserts unproven
deployment fitness, empty residual risk, universal conformance, or unverified
proof strength (see objectives evidence source policy). Prefer conformance
level identifiers and named evidence commands.

---

## 12. Document map

### 12.1 Architecture set (this task)

| Document | Role |
| --- | --- |
| [overview.md](overview.md) | This guide; bundles; orientation |
| [threat-model.md](threat-model.md) | Threats, assets, mitigations |
| [trust-boundaries.md](trust-boundaries.md) | Boundaries and authority rules |
| [state-model.md](state-model.md) | State modes and backends |
| [durable-execution.md](durable-execution.md) | DurableExecutor@1 interface guide |
| [glossary.md](glossary.md) | Terms and archive aliases |
| [traceability.md](traceability.md) | Archive → canonical checklist |
| [decisions/](decisions/) | ADRs 0001–0006 |

### 12.2 Spec and binding entry points

| Topic | Path |
| --- | --- |
| Profile registry | [../spec/mcp++-profiles-draft.md](../spec/mcp++-profiles-draft.md) |
| Execution envelope | [../spec/execution-envelope.md](../spec/execution-envelope.md) |
| StateRef | [../spec/state-ref.md](../spec/state-ref.md) |
| UCAN | [../spec/ucan-delegation.md](../spec/ucan-delegation.md) |
| Policy | [../spec/temporal-deontic-policy.md](../spec/temporal-deontic-policy.md) |
| Event DAG | [../spec/event-dag-ordering.md](../spec/event-dag-ordering.md) |
| Risk / scheduling | [../spec/risk-scheduling.md](../spec/risk-scheduling.md) |
| Payments | [../spec/x402-payments.md](../spec/x402-payments.md) |
| Transport | [../spec/transport-mcp-p2p.md](../spec/transport-mcp-p2p.md) |
| Canonicalization | [../spec/canonicalization-mcpp-jcs-v1.md](../spec/canonicalization-mcpp-jcs-v1.md) |
| A2A extension | [../spec/a2a-extension.md](../spec/a2a-extension.md) |
| MCP bindings | [../spec/bindings/README.md](../spec/bindings/README.md) |

### 12.3 Checklist (ArchitectureGuide@1)

1. Profiles A–H summarized without treating initialize as current MCP.
2. Profile bundles **Evidence Core**, **Secure Delegation**, **Federated Mesh**,
   **Commerce**, and **Verified Execution** defined per KD-17.
3. Conformance ladder linked; schema ≠ implemented.
4. Trust rules KD-14/15 and durable/state separations stated.
5. Migration and compatibility paths linked, not claimed complete without
   evidence.
6. No forbidden over-claim phrases.

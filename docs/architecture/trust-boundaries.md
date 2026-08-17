# MCP++ Trust Boundaries

**Status:** Architecture security guide (MCP++ 1.0 gap-closure)  
**Interfaces:** `ArchitectureGuide@1` (trust-boundary chapter)  
**Task:** MCPP-078 · Goal `MCPP-G170` · Bundle `mcplusplus/1.0/docs-architecture`  
**Authority:** KD-1, KD-13, KD-14, KD-15; ADR-0001, ADR-0004, ADR-0005, ADR-0006  
**Document class:** **normative** for boundary rules; **not production-admitted** as deployment certification

| Section | Authority class |
| --- | --- |
| §1 Purpose | reference |
| §2 Boundary map | **normative** |
| §3 Authority lattice (what may authorize what) | **normative** |
| §4 Identity classes | **normative** |
| §5 Data-plane vs control-plane | **normative** |
| §6 Profile-bundle boundaries | **normative** (KD-17 packaging) |
| §7 Confidential artifact boundary (KD-15) | **normative** |
| §8 Cross-runtime ownership boundary | **normative** (KD-1) |
| §9 Fail-closed checklist | **normative** |
| §10 Migration notes | **non-normative** |
| §11 Related documents | reference |

Companion: [threat-model.md](threat-model.md) · [overview.md](overview.md).

---

## 1. Purpose

A **trust boundary** is a place where authority, identity, or data sensitivity
changes. MCP++ fails closed when a lower-authority signal is used as a
higher-authority grant.

This chapter answers:

1. Which identities exist?
2. What each identity is allowed to mean?
3. Which subsystems may never substitute for each other (journal vs DAG vs
   state vs payment vs transport)?

---

## 2. Boundary map

```text
                         ┌─────────────────────────────┐
                         │  Human operator / org policy │
                         └──────────────┬──────────────┘
                                        │ policy CIDs, keys, ops
                                        v
 ┌──────────────┐   MCP binding    ┌────────────────────────────┐
 │ MCP Host /   │ ───────────────► │ Runtime adapter            │
 │ A2A client   │   (untrusted     │ (accelerate / datasets /   │
 └──────────────┘    content)      │  kit / SwissKnife / …)     │
                                   └─────────────┬──────────────┘
          transport PeerID / TLS                 │
          (identity only — KD-14)                │
                 │                               │ must evaluate
                 │                               │ C + D before effects
                 v                               v
        ┌────────────────┐            ┌──────────────────────┐
        │ Profile E wire │            │ Secure Delegation    │
        │ framing (opt.) │            │ (UCAN + deontic)     │
        └───────┬────────┘            └──────────┬───────────┘
                │                                │
                │  never grants UCAN             │ allow / deny /
                │  capabilities                  │ obligations
                v                                v
        ┌────────────────────────────────────────────────────┐
        │ ExecutionEnvelope@1  →  DurableExecutor@1           │
        │                      →  StateProvider (StateRef@1)  │
        └────────────────────────────┬───────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              v                      v                      v
     ┌────────────────┐   ┌──────────────────┐   ┌─────────────────┐
     │ Journal        │   │ Event DAG (F)    │   │ CID artifact    │
     │ (step commit)  │   │ (causal audit)   │   │ store           │
     └────────────────┘   └──────────────────┘   └────────┬────────┘
                                                          │
                     ┌────────────────────────────────────┤
                     v                                    v
            ┌─────────────────┐                 ┌──────────────────┐
            │ Commerce (H)    │                 │ Confidential ref │
            │ payment settle  │                 │ (ciphertext only │
            │ ≠ authorization │                 │  on public paths)│
            └─────────────────┘                 └──────────────────┘
```

| Boundary edge | Low side | High side | Rule |
| --- | --- | --- | --- |
| B1 Host → runtime | Untrusted messages | Enforced C/D + schema | Malformed / unauthorized → reject |
| B2 Transport → execution | PeerID / TLS cert | UCAN / policy | Transport never grants capabilities (KD-14) |
| B3 Payment → execution | Settlement proof | Authorization decision | Payment never grants authorization (KD-14) |
| B4 Journal ↔ Event DAG | Provenance publication | Step-commit authority | DAG validators are not the journal |
| B5 Journal ↔ StateRef | Shared state modes | Durable step fences | CAS/CRDT ≠ crash journal |
| B6 Local runtime → federated peer | Same-trust optional shortcuts | Cross-trust receipts | Cross-trust requires `receipt-signed` |
| B7 Spec package → runtime adapter | Portable schemas | Local wiring | Runtimes do not redefine portable contracts (KD-1) |
| B8 Plaintext → public channels | Decrypted payload | Logs / DAG meta / caches | No plaintext leak (KD-15) |
| B9 A2A Task ↔ DurableExecutor | Public multi-agent task | Step recovery | No competing public task lifecycle (KD-13) |
| B10 Binding advertisement → session | Claimed binding id | Actual lifecycle | Forgery / silent downgrade fail closed |

---

## 3. Authority lattice (what may authorize what)

Authority is **not** transitive across these rows.

| Signal | May authorize | Must not authorize |
| --- | --- | --- |
| Valid UCAN chain (C) under policy (D) | Tool/resource invocation within attenuations | Bypass of revoke/expiry; unlimited ambient authority |
| Temporal deontic allow | Proceed when caps also valid | Create capabilities by itself without C where C is required |
| Signed `ExecutionReceipt@1` | Independent verification of outcome binding | Future invocations without fresh caps |
| Durable fencing token | Exclusive resume/recover for that execution epoch | Cross-execution or transport login |
| StateRef lease / CAS version | Writes in `single_authority` mode | Durable journal recover without journal records |
| Profile G neighborhood approval | Coordination / majority_approval **as labeled** | BFT safety; UCAN mint |
| x402 payment success | Settlement / paid-access bookkeeping | UCAN capabilities; policy override |
| PeerID / TLS client cert | Transport multiplexing, abuse budgets, dial identity | Execution authority |
| Registry presence / advertisement | Discovery hints | Authorization |
| Schema validation pass | Structural accept | “Implemented security” |

---

## 4. Identity classes

| Class | Examples | Trust meaning |
| --- | --- | --- |
| **Transport identity** | libp2p PeerID, TLS client cert, TCP source | Who is on the wire *right now*; ephemeral relative to caps |
| **Cryptographic principal** | DID-compatible iss/aud, Ed25519 `kid` | Who signed what over canonical bytes |
| **Delegated capability** | UCAN attenuation chain | What principal is allowed to do, for how long, with whose authority |
| **Executor / adapter identity** | `executor_did`, `adapter_id` | Who ran the journaled work |
| **Task / execution identity** | A2A Task id, `execution_id` | Which unit of work; not a capability |
| **Content identity** | CIDv1 of artifacts | Integrity of bytes; not who may read/decrypt |

**Normative rule:** elevating a lower class to a higher class without a defined
protocol step is a trust-boundary violation and **MUST** fail closed.

---

## 5. Data-plane vs control-plane

| Plane | Contents | Boundary notes |
| --- | --- | --- |
| **Control** | Profile negotiation, binding ids, discovery ads, policy CIDs, caps, fences, cancel | Authenticated and fail-closed; prefer explicit capability checks |
| **Data** | Tool inputs/outputs, large artifacts, streams | May be bulk; still referenced by CID from envelopes; confidentiality rules apply |
| **Evidence** | Receipts, journal CIDs, Event DAG nodes, verifier bundles | Readable by third parties only when signatures/proofs match claim level |

Control-plane acceptance **MUST NOT** be inferred from successful data-plane
delivery alone (message arrived ≠ authorized).

---

## 6. Profile-bundle boundaries

Bundles (KD-17) cross trust concerns; operators must not treat them as a single
security monoid.

| Bundle | Trust implication | Hard boundary |
| --- | --- | --- |
| **Evidence Core** (A, B, F) | Contracts + provenance for audit | Does not imply caps verified or policy evaluated |
| **Secure Delegation** (C, D) | Authorization and obligations | Does not imply payment settled or mesh BFT |
| **Federated Mesh** (E, G) | Carriage + coordination | Transport/mesh **≠** Secure Delegation |
| **Commerce** (H) | Economic settlement | **≠** authorization (B3) |
| **Verified Execution** | Independently checkable outcomes/proofs | Requires signed receipts / real verified proofs—not structural receipts |

Composing **Commerce + Evidence Core** without **Secure Delegation** may record
paid traffic that still **MUST** be denied at execution time if C/D fail.

---

## 7. Confidential artifact boundary (KD-15)

Encrypted artifact references **MUST** carry at least:

- ciphertext CID  
- algorithm  
- key-envelope  
- recipients / capability  
- plaintext schema CID  
- optional protected digest  
- disclosure and retention policy  

**Normative non-leak channels:**

| Channel | Plaintext allowed? |
| --- | --- |
| Public Event DAG metadata | **No** |
| Operator logs (default) | **No** |
| Local fallback caches used for public replay | **No** |
| Authorized decrypt path under capability | **Yes** (in-memory / protected store only as implemented) |

Content addressing of ciphertext is **not** publication of plaintext.

---

## 8. Cross-runtime ownership boundary

| Package role | Owns | Must not own |
| --- | --- | --- |
| mcplusplus / Mcp-Plus-Plus (spec tree) | Schemas, vectors, validators, matrices, portable prose | Divergent per-runtime “private protocol” for portable claims |
| Runtime adapters | Local wiring, storage paths, product UX | Second Envelope/StateRef/DurableExecutor wire contract for MCP++ 1.0 claims |

Crossing this boundary without adapters that preserve CIDs and fail-closed
rules produces non-interoperable islands and false matrix rows.

---

## 9. Fail-closed checklist

Implementations **MUST** reject (or equivalent hard-fail) when:

1. Execution is requested with transport identity alone as the capability proof.
2. Payment settlement is the only “authorization” signal.
3. Required UCAN/policy proofs are missing on portable/cross-trust envelopes.
4. Signature verify fails, `kid` missing, or algorithm outside mandatory suite.
5. Policy evaluates deny, obligation breach, or expired/revoked material.
6. StateRef mode is missing, unknown, multi-mode, or silent cross-mode merge is
   attempted for mutable `single_authority` values.
7. Durable resume/recover presents a stale fencing token.
8. Cross-trust finalize lacks a verifiable receipt signature when claiming
   `receipt-signed`.
9. Proof objects are simulated while claiming `proof-verified` / Verified
   Execution.
10. Binding id forgery or silent MCP revision downgrade is detected.
11. Confidential plaintext would be written to logs, Event DAG metadata, or
    public fallback caches.
12. A second public task lifecycle competes with A2A Task status/cancel/stream.

---

## 10. Migration notes

**Authority class: non-normative.**

| From | To | Boundary action |
| --- | --- | --- |
| PeerID-gated tools | Capability-gated tools | Keep PeerID for dial limits; add C proofs on invoke |
| “Paid users may call X” | Commerce + Secure Delegation | Check settlement then **still** check C/D |
| In-memory session auth | Durable executions | Issue fencing tokens; journal cancel |
| Single global mutable map | StateRef modes | Pick one mode per ref; stop silent merges |
| Initialize-only servers | Dual bindings | Name `mcp-binding/…` ids; do not call initialize “current MCP” |
| Structural receipt fields | Verified Execution claims | Add independent verify before advertising the bundle |

---

## 11. Related documents

| Topic | Path |
| --- | --- |
| Threat catalog | [threat-model.md](threat-model.md) |
| Overview + bundles | [overview.md](overview.md) |
| State modes | [state-model.md](state-model.md) |
| Durable executor | [durable-execution.md](durable-execution.md) |
| Execution envelope | [../spec/execution-envelope.md](../spec/execution-envelope.md) |
| UCAN | [../spec/ucan-delegation.md](../spec/ucan-delegation.md) |
| Payments | [../spec/x402-payments.md](../spec/x402-payments.md) |
| Transport | [../spec/transport-mcp-p2p.md](../spec/transport-mcp-p2p.md) |
| A2A | [../spec/a2a-extension.md](../spec/a2a-extension.md) |
| ADR ownership | [decisions/0001-spec-runtime-ownership.md](decisions/0001-spec-runtime-ownership.md) |
| ADR bindings | [decisions/0006-bindings-a2a.md](decisions/0006-bindings-a2a.md) |

### Checklist

1. Boundaries B1–B10 defined with fail-closed rules.  
2. Authority lattice forbids transport/payment → execution elevation.  
3. Journal, Event DAG, and StateRef authorities separated.  
4. Profile bundles do not collapse into one security claim.  
5. KD-15 confidential non-leak channels listed.  
6. No forbidden over-claim phrases; document is not production admission.

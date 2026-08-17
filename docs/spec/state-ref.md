# StateRef@1 — Shared-State Reference with Mandatory Consistency Modes

**Status:** Normative (MCP++ 1.0)  
**Interface:** `StateRef@1`  
**Schema marker:** `mcp++/state/state-ref@1`  
**Schema:** `ipfs_accelerate_py/mcplusplus/schemas/state/state-ref-1.schema.json`  
**Authority:** ADR-0004 (`docs/architecture/decisions/0004-state-modes.md`); sealed plan KD-8…KD-11  
**Related:** Profile F Event DAG (`event-dag-ordering.md`); Profile G risk/neighborhood (`risk-scheduling.md`); CID-native artifacts (`cid-native-artifacts.md`); canonicalization `mcpp-jcs-v1` (`canonicalization-mcpp-jcs-v1.md`)

This document is the normative specification of **`StateRef@1`**: the portable
handle used by MCP++ peers, envelopes, and providers to name shared state under
an **explicit, single consistency mode**.

---

## 1. Purpose and non-goals

### 1.1 Purpose

- Give every language runtime one wire shape for “this is the state I mean.”
- Force every reference to declare **exactly one** consistency mode from a
  closed set so concurrent Event DAG branches cannot silently invent merge
  semantics for mutable values (plan KD-8).
- Carry the fields providers need for CAS, leases, fences, causal clocks,
  capability checks, and policy linkage without growing informal ad-hoc maps.

### 1.2 Non-goals

- This document does **not** implement state providers (MCPP-036…039) or the
  Event DAG non-merge proof test (MCPP-040).
- This document does **not** define DurableExecutor journal recovery (ADR-0005).
- This document does **not** claim Profile G neighborhood agreement is BFT
  (ADR-0004 §4; plan §11).
- Schema acceptance alone is never “implemented” (ADR-0003).

---

## 2. Interface identity

| Field | Value |
| --- | --- |
| Interface label | `StateRef@1` |
| Schema marker (`schema`) | `mcp++/state/state-ref@1` |
| JSON Schema `$id` | `https://mcp-plus-plus.dev/schemas/state/state-ref-1.schema.json` |
| In-tree schema path | `ipfs_accelerate_py/mcplusplus/schemas/state/state-ref-1.schema.json` |
| Versioning rule | Breaking changes require `StateRef@2` / a new schema marker; do not overload `@1` |

Documents that claim `StateRef@1` MUST validate against the in-tree schema and
MUST satisfy the fail-closed rules in §4 and §5.

---

## 3. Conceptual model

A **StateRef** is a *handle*, not the full history of a value:

| Concept | Role |
| --- | --- |
| `id` | Stable logical identity of the handle (does not change when the live value advances). |
| `root_cid` | Current content-addressed root / head of the live value (advances under the mode’s rules). |
| `schema_cid` | CID of the value-schema the root payload must satisfy. |
| `mode` | Exactly one consistency mode (mandatory). |
| `version` / `epoch` / `fence` / `lease` | Concurrency control for exclusive and fenced writers. |
| `clocks` / `parents` | Causal evidence and partial-order linkage. |
| Policy CIDs | Merge, retention, confidentiality, consensus policy documents by CID. |
| Caps | Read/write capability references evaluated at access time. |

Peers MAY embed a StateRef inside execution envelopes, tasks, or Event DAG
payloads. Observing a StateRef on two concurrent Event DAG branches does **not**
authorize a silent merge of mutable live values; merge behavior is mode-gated
(§5).

---

## 4. Consistency modes (normative, closed enum)

### 4.1 Allowed modes

A `StateRef@1` MUST declare **exactly one** of the following `mode` tokens
(snake_case wire form; no aliases):

| Mode | Normative meaning | Merge / conflict rule |
| --- | --- | --- |
| `immutable` | Content-addressed, append-only values. Identity is CID (or equivalent digest). | Mutation of an existing identity is rejected. New values mint new CIDs. No multi-writer merge. |
| `single_authority` | One authoritative writer (or leased exclusive writer) owns the live value. | Concurrent writers without a valid lease/fence produce an **explicit conflict**, not a silent merge. CAS / version preconditions apply. |
| `causal` | Values are ordered only by recorded causal history (Event DAG parents / clocks). | Concurrent branches remain concurrent until an explicit reconciliation policy is applied. Observing two branches MUST NOT invent a total order or merge payloads. |
| `crdt` | Multi-writer commutative/associative merge under a real CRDT. | Concurrent offline updates MUST converge after exchange. Merge evidence is the CRDT document state, not informal last-write-wins. |
| `consensus` | Agreement is produced only by a declared consensus **plugin** with an honest guarantee label. | Values change only when plugin evidence for the declared guarantee is present and valid. |

### 4.2 Fail-closed mode rules

| Rule | Normative statement |
| --- | --- |
| Exhaustive set | Allowed modes for MCP++ 1.0 are **exactly** `immutable`, `single_authority`, `causal`, `crdt`, `consensus`. |
| Required field | `mode` is **required**. A document without `mode` is **invalid**. |
| No unknown strings | Any string outside the five-token enum is **invalid**. |
| No multi-mode | Arrays of modes, dual primary/fallback modes, or a second mode in `metadata` are **invalid**. |
| No free-text | Free-text or vendor-specific mode strings are **invalid** without a superseding ADR. |
| Mode immutability of a ref | A given StateRef `id` does not silently change `mode`. Mode change requires a new ref identity or an explicit, versioned migration recorded outside silent write paths. |

**Acceptance (MCPP-035):** Missing or unknown mode is invalid. Allowed modes are
exactly `immutable`, `single_authority`, `causal`, `crdt`, `consensus`.

### 4.3 Mode-to-backend defaults (ADR-0004)

| Mode | Mandatory backend / substrate (MCP++ 1.0) |
| --- | --- |
| `immutable` | Content-addressed block / artifact store (CID-native) |
| `single_authority` | **DuckDB / Quack / DuckLake** (SQLite fallback) |
| `causal` | Event DAG parents / clocks as the ordering substrate |
| `crdt` | **Automerge** (real CRDT; not informal LWW) |
| `consensus` | Declared consensus plugin with one of four guarantee labels |

SQLite remains an explicit fallback (`MCPPLUSPLUS_SQL_ENGINE=sqlite`). It MUST
NOT replace DuckDB/Quack/DuckLake as the default single-authority backend for
MCP++ 1.0 conformance claims.

---

## 5. Cross-mode and Event DAG rules (normative)

1. **Non-merge of mutable values:** Observing two concurrent Event DAG branches
   that reference the same logical `id` under `single_authority` MUST NOT
   silently merge payloads. Implementations MUST surface an explicit conflict,
   retain both branches, or apply only an **explicit** reconciliation policy
   outside silent write paths (proven later by MCPP-040).
2. **CRDT merge only in `crdt`:** Automatic multi-writer merge is allowed only
   when `mode` is `crdt` and the backend is a real CRDT (Automerge).
3. **Consensus acceptance only in `consensus`:** State transitions that depend
   on agreement evidence are valid only when `mode` is `consensus` and plugin
   evidence matches the declared guarantee.
4. **Causal observation ≠ merge:** `mode: causal` records partial order; it
   does **not** authorize CRDT-style merge or total-order invention.
5. **Immutable rejection of in-place mutation:** Under `immutable`, a write that
   would change bytes under an existing `root_cid` identity MUST fail closed.

---

## 6. Field inventory (normative)

Unless noted, field names are **snake_case** on the wire. The JSON Schema is
authoritative for types, bounds, and `additionalProperties: false` at the
top level.

### 6.1 Required fields

| Field | Type | Notes |
| --- | --- | --- |
| `schema` | string const | MUST be `mcp++/state/state-ref@1`. |
| `id` | string | Stable logical handle id (opaque at this layer). |
| `mode` | enum string | Exactly one of the five modes in §4. |

### 6.2 Core optional fields

| Field | Type | Notes |
| --- | --- | --- |
| `schema_cid` | CID | Value-schema CID for root payloads. |
| `root_cid` | CID \| null | Current head; `null` means explicitly empty / not yet minted. |
| `authority` | object | Writer / ownership descriptor (§7). |
| `version` | non-negative integer | CAS / observational version counter. |
| `epoch` | non-negative integer | Claim / fencing epoch. |
| `clocks` | object | Logical, hybrid, vector, and/or Merkle frontier clocks (§8). |
| `read_caps` | array | Read capability refs (§9). |
| `write_caps` | array | Write capability refs (§9). |
| `lease` | object \| null | Exclusive-write lease (§10). |
| `fence` | object \| null | Fencing token (§10). |
| `merge_policy_cid` | CID \| null | Merge / reconciliation policy document. |
| `retention_policy_cid` | CID \| null | Retention / archival policy. |
| `confidentiality_policy_cid` | CID \| null | Confidentiality / disclosure policy. |
| `consensus_policy_cid` | CID \| null | Consensus plugin policy document. |
| `parents` | CID[] | Causal parents (prior StateRef snapshots and/or Event DAG nodes). |
| `provider` | string | Optional backend label (informational; `mode` remains authoritative). |
| `metadata` | object | Non-authoritative annotations; MUST NOT redeclare `mode` or override concurrency fields. |

### 6.3 CID form

CID strings follow the same portable form as other MCP++ 1.0 schemas:

- CIDv1 base32 (`b…`) preferred for new mints.
- CIDv0 (`Qm…`) remains readable when historical.
- Pattern (schema): `^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58,})$`

Canonical bytes for newly minted normative StateRef snapshots SHOULD use
`mcpp-jcs-v1` (RFC 8785 JCS) per ADR-0002.

---

## 7. Authority object

```text
authority.kind ∈ { none, principal, lease_holder, quorum, plugin }
```

| `kind` | Typical use |
| --- | --- |
| `none` | Pure `immutable` refs with no live writer. |
| `principal` | Fixed single writer DID/principal. |
| `lease_holder` | Writer is the current lease holder (`lease.holder`). |
| `quorum` | Threshold set (`principals` + `threshold`). |
| `plugin` | Consensus plugin (`plugin_id`, optional `guarantee`). |

**Trust boundary (plan KD-14):** Transport identity (PeerID / TLS client cert)
is never execution authority by itself. Payment never grants authorization.
Authority for writes MUST be established via declared principals, leases, and
capability proofs evaluated at access time.

### 7.1 Consensus guarantee labels

When `authority.guarantee` or consensus-plugin evidence is present, the label
MUST be one of:

| Label | Meaning |
| --- | --- |
| `coordination` | Best-effort ordering/scheduling; no crash/Byzantine safety claim. |
| `majority_approval` | Threshold approval under an honest-majority assumption for a declared set only. |
| `crash_consensus` | CFT agreement (crash/recover processes). |
| `bft` | Byzantine fault tolerance under a declared fault bound — **only** with a real BFT engine. |

Profile G neighborhood agreement is **`coordination` and/or `majority_approval`
only**. Labeling a Profile G neighborhood result as `bft` is a fail-closed error
(ADR-0004 §4; MCPP-039).

---

## 8. Clocks and parents

### 8.1 `clocks`

| Subfield | Use |
| --- | --- |
| `logical` | Lamport-style counter. |
| `hybrid.wall_ms` + `hybrid.logical` | Hybrid logical clock. |
| `vector` | Sparse vector clock map principal → counter. |
| `merkle_frontier` | Event DAG / Merkle frontier CIDs. |
| `observed_at` | Informational wall time (ISO-8601); not total-order authority. |

For `mode: causal`, implementations SHOULD populate at least one of `logical`,
`hybrid`, `vector`, or `merkle_frontier`, and SHOULD link `parents` to the
causal history used for comparison.

### 8.2 `parents`

`parents` is an array of CIDs establishing happened-before edges. Independent
events remain concurrent (no global sequencer required; see
`event-dag-ordering.md`). Parents alone never authorize silent merge under
`single_authority`.

---

## 9. Read and write capabilities

`read_caps` and `write_caps` are arrays of:

1. **CID** — proof or capability bundle CID, or  
2. **Inline descriptor** — `{ "resource", "ability", "proof_cid"? }` aligned with
   UCAN-style ability records (`ucan-delegation.md`).

At access time, implementations MUST evaluate caps (and linked UCAN proofs)
before serving or mutating state. A valid StateRef shape with missing rights
still fails authorization closed.

---

## 10. Lease and fence

### 10.1 Lease

| Field | Required | Notes |
| --- | --- | --- |
| `holder` | yes | Principal with exclusive write. |
| `expires_at_ms` | yes | Unix ms expiry; post-expiry writers without renew fail closed. |
| `issued_at_ms` | no | Issue time. |
| `epoch` | no | SHOULD align with top-level `epoch` when both present. |
| `lease_cid` | no | Content-addressed lease record. |
| `renewable` | no | Whether same-epoch renew is allowed. |

### 10.2 Fence

| Field | Required | Notes |
| --- | --- | --- |
| `token` | yes | Monotonic fencing token; higher wins. |
| `epoch` | no | Optional epoch binding. |
| `issued_to` | no | Principal the fence was issued to. |
| `fence_cid` | no | Content-addressed fence record. |

**Stale fence rule:** A write or completion presenting a fence token lower than
the highest accepted token for this `id` MUST be rejected (Profile G
`G_STALE_FENCE` semantics align with this rule).

---

## 11. Policy CIDs

| Field | Role |
| --- | --- |
| `merge_policy_cid` | Explicit merge/reconciliation policy. MUST NOT substitute for Automerge under `crdt` by inventing LWW. MUST NOT authorize silent `single_authority` merge. |
| `retention_policy_cid` | How long history/snapshots are kept; compaction boundaries. |
| `confidentiality_policy_cid` | Disclosure, ciphertext vs plaintext, log redaction (plan KD-15 alignment). |
| `consensus_policy_cid` | Plugin membership, guarantee label, quorum, evidence format for `consensus` mode. |

Policy documents are content-addressed. Absent policy CIDs mean “no extra
policy document”; they do **not** mean “permissive open access.”

---

## 12. Validation checklist (structural)

A document is a valid `StateRef@1` only if all of the following hold:

1. Parses as a JSON object with `additionalProperties` disallowed at the top level.
2. `schema` equals `mcp++/state/state-ref@1`.
3. `id` is a non-empty string matching the schema pattern.
4. `mode` is present and is one of the five enum tokens — **missing or unknown is invalid**.
5. All present CIDs match the portable CID pattern.
6. Nested `authority`, `lease`, `fence`, `clocks`, and capability objects match their `$defs`.
7. `metadata` does not reintroduce reserved concurrency fields as an alternate control plane.

Higher conformance levels (canonical bytes, cryptographic proof, policy
enforcement) are layered above this structural acceptance (ADR-0003).

---

## 13. Examples

### 13.1 Immutable

```json
{
  "schema": "mcp++/state/state-ref@1",
  "id": "state:demo/immutable-config",
  "schema_cid": "bafkreigh2akiscaildcqabsyg3dfr6chu3fgpregiymsck7e7aqa4s52zy",
  "root_cid": "bafkreifzjut3te2nhyekklss27nh3k72ysco7y32koao5eei66wof36n5e",
  "mode": "immutable",
  "authority": { "kind": "none" },
  "version": 0,
  "parents": []
}
```

### 13.2 Single-authority with lease and fence

```json
{
  "schema": "mcp++/state/state-ref@1",
  "id": "state:demo/task-lease",
  "mode": "single_authority",
  "root_cid": "bafkreifzjut3te2nhyekklss27nh3k72ysco7y32koao5eei66wof36n5e",
  "authority": {
    "kind": "lease_holder",
    "principal": "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH"
  },
  "version": 7,
  "epoch": 2,
  "lease": {
    "holder": "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH",
    "expires_at_ms": 1783872061000,
    "epoch": 2,
    "renewable": true
  },
  "fence": {
    "token": 3,
    "epoch": 2
  },
  "parents": []
}
```

### 13.3 Invalid documents (MUST reject)

| Case | Why invalid |
| --- | --- |
| Missing `mode` | Required field absent. |
| `"mode": "lww"` | Unknown mode (not in closed enum). |
| `"mode": "CRDT"` | Case-sensitive enum; wrong token. |
| `"mode": ["crdt", "causal"]` | Multi-mode / wrong type. |
| Missing `schema` or `id` | Required fields absent. |
| `"mode": "single_authority"` plus silent branch merge without conflict | Runtime fail-closed (MCPP-040); not a schema-shape success. |

---

## 14. Downstream providers

| Mode | Follow-on task | Provider interface (planned) |
| --- | --- | --- |
| `immutable` | MCPP-036 | `ImmutableCidState@1` via `StateProvider@1` |
| `single_authority` | MCPP-037 | `SqliteAuthorityState@1` (WAL + CAS) |
| `crdt` | MCPP-038 | `AutomergeCrdtState@1` |
| `consensus` | MCPP-039 | `ConsensusPlugin@1` with honest labels |
| Non-merge proof | MCPP-040 | Event DAG branch tests for mutable modes |

---

## 15. References

- ADR-0004 state modes — `docs/architecture/decisions/0004-state-modes.md`
- Sealed plan KD-8…KD-11 — `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md`
- Traceability REQ-ST-01…04 — `docs/roadmap/mcplusplus-1.0-gap-closure.md`
- Event DAG partial order — `event-dag-ordering.md`
- UCAN delegation — `ucan-delegation.md`
- Canonicalization — `canonicalization-mcpp-jcs-v1.md`

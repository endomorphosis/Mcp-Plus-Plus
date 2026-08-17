# MCP++ Shared-State Model

**Status:** Architecture guide (MCP++ 1.0 gap-closure)  
**Interfaces:** `ArchitectureGuide@1` (state chapter); portable object `StateRef@1`  
**Task:** MCPP-078 · Goal `MCPP-G170` · Bundle `mcplusplus/1.0/docs-architecture`  
**Authority:** ADR-0004 (KD-8…KD-11); normative schema prose in [../spec/state-ref.md](../spec/state-ref.md)  
**Document class:** **reference** architecture with **normative** mode/backend rules mirrored from ADR-0004; **not production-admitted** without provider tests

| Section | Authority class |
| --- | --- |
| §1 Purpose and non-goals | reference |
| §2 Conceptual model | reference |
| §3 Consistency modes | **normative** (closed enum) |
| §4 Backends and substrates | **normative** defaults |
| §5 Consensus guarantee labels | **normative** |
| §6 Interaction with Event DAG and durable execution | **normative** separations |
| §7 Trust-boundary notes | **normative** (summary) |
| §8 Profile-bundle relevance | **normative** packaging |
| §9 Migration | **non-normative** |
| §10 Conformance and evidence | reference |
| §11 Checklist | reference |

Normative keywords **MUST**, **MUST NOT**, **SHOULD**, and **MAY** follow RFC 2119
when restating ADR-0004 / StateRef rules.

---

## 1. Purpose and non-goals

### 1.1 Purpose

MCP++ agents share intents, decisions, work-product, and coordination state
across peers and Event DAG branches. The shared-state model:

1. Forces every portable handle to declare **exactly one** consistency mode.
2. Names mandatory backends for single-authority and CRDT modes.
3. Labels consensus-class guarantees honestly (Profile G is not BFT).
4. Prevents silent merge of mutable values when two causal branches are observed.

### 1.2 Non-goals

- Replacing DurableExecutor journals (step commit / crash recovery).
- Defining a single global BFT chain for all MCP++ deployments.
- Treating this guide as gate-8…12 closure without provider tests.
- Claiming informal last-write-wins is a CRDT.

---

## 2. Conceptual model

A **`StateRef@1`** is a *handle*, not the full history of a value:

| Field family | Role |
| --- | --- |
| `id` | Stable logical identity of the handle |
| `root_cid` | Current content-addressed head of the live value |
| `schema_cid` | Schema the root payload must satisfy |
| `mode` | Exactly one consistency mode (mandatory) |
| `version` / `epoch` / `fence` / `lease` | Concurrency control |
| `clocks` / `parents` | Causal evidence |
| Policy / cap CIDs | Merge, retention, confidentiality, access |

Peers embed StateRefs in envelopes, tasks, or Event DAG payloads. Observing the
same `id` on two branches does **not** authorize silent merge unless the mode
explicitly defines merge (`crdt`) or plugin acceptance (`consensus`).

```text
  Envelope / Task / Event
           │
           ▼
      StateRef@1  ──mode──►  provider adapter
           │                      │
           │         ┌────────────┼────────────────┐
           │         v            v                v
           │   immutable store  DuckDB CAS    Automerge
           │   (CID blocks)     (single_auth) (crdt)
           │         │            │                │
           │         └────────────┼────────────────┘
           │                      v
           │              optional consensus plugin
           ▼
     Event DAG parents (causal evidence; not automatic merge)
```

Wire shape and field rules: [../spec/state-ref.md](../spec/state-ref.md).

---

## 3. Consistency modes

**Authority class: normative.** Allowed modes for MCP++ 1.0 are **exactly**:

| Mode | Meaning | Conflict / merge rule |
| --- | --- | --- |
| `immutable` | Content-addressed, append-only values | Mutation of an existing identity is rejected; new values mint new CIDs |
| `single_authority` | One authoritative (or leased exclusive) writer | Concurrent writers without valid lease/fence → **explicit conflict**, not silent merge; CAS/version preconditions apply |
| `causal` | Ordered only by recorded causal history | Concurrent branches remain concurrent until explicit reconciliation; no invented total order |
| `crdt` | Multi-writer merge under a real CRDT | Concurrent offline updates converge after exchange; evidence is CRDT document state |
| `consensus` | Values change only with valid plugin evidence | Plugin guarantee label must be honest and present |

### 3.1 Fail-closed mode rules

| Rule | Statement |
| --- | --- |
| Exhaustive set | No aliases, free-text modes, or sixth default mode without a superseding ADR |
| Exactly one | Missing mode, multi-mode arrays, or dual primary/fallback modes are **invalid** |
| Mode immutability | A given StateRef `id` does not silently change `mode`; mode change needs a new ref or versioned migration outside silent write paths |
| Cross-mode non-merge | Observing two Event DAG branches **MUST NOT** silently merge `single_authority` values; CRDT merge only in `crdt`; consensus only with plugin evidence |

---

## 4. Backends and substrates

| Mode | Mandatory backend / substrate | Notes |
| --- | --- | --- |
| `immutable` | CID-native block / artifact store | Append-only |
| `single_authority` | **DuckDB / Quack / DuckLake** with transactional **CAS** | SQLite is an explicit fallback (`MCPPLUSPLUS_SQL_ENGINE=sqlite`) |
| `causal` | Event DAG parents / clocks | Partial order only |
| `crdt` | **Automerge** | Real CRDT; informal LWW is forbidden |
| `consensus` | Declared **consensus plugin** | One of four guarantee labels (§5) |

DuckDB as **state** authority is related to but distinct from DuckDB as the
**durable execution journal** (ADR-0005). A runtime MAY colocate files; table
namespaces and authority must remain separate. SQLite remains an explicit
fallback for both stores.

---

## 5. Consensus guarantee labels

Consensus-class behavior is **not** a boolean. Plugins and Profile G
coordination **MUST** use one of:

| Label | Meaning | Typical use |
| --- | --- | --- |
| `coordination` | Best-effort alignment; no crash/Byzantine safety claim | Neighborhood clustering, local frontier sync |
| `majority_approval` | Threshold approval among a declared set under honest-majority assumption for **that set only** | Profile G neighborhood majority |
| `crash_consensus` | CFT agreement (crash/recover) | Raft/Paxos-class plugins when so declared |
| `bft` | Byzantine fault tolerance under declared bounds | Only with real BFT plugin evidence |

**Profile G neighborhood agreement is `coordination` and/or `majority_approval`
only.** Labeling a Profile G result as `bft` is a fail-closed error (KD-11).

Escalation from neighborhood coordination to a stronger `consensus` mode **MUST**
change the declared guarantee label and evidence format—not silently upgrade
claims.

---

## 6. Interaction with Event DAG and durable execution

| Subsystem | Authority for | Must not be used as |
| --- | --- | --- |
| **StateRef + providers** | Shared mutable/immutable values under a mode | Crash-recovery journal for multi-step effects |
| **Event DAG (Profile F)** | Causal provenance of published events | Silent merge engine for `single_authority` state |
| **DurableExecutor journal** | Step commit, recover, cancel/timer persistence, fencing | CRDT merge or multi-mode state store |

Rules:

1. Journaled side effects **MAY** reference StateRef transitions by CID.
2. A successful state CAS **MUST NOT** be reported as durable crash recovery.
3. Event DAG validators **MUST NOT** be treated as the durable journal store.
4. Exclusive tasks combine StateRef leases/fences **and/or** durable fencing
   tokens as declared by the execution path; transport identity still grants
   neither (KD-14).

---

## 7. Trust-boundary notes

| Risk | Control |
| --- | --- |
| Lost update after restart | DuckDB/Quack CAS restart tests (gate 10); SQLite WAL fallback |
| Fake CRDT | Automerge mandatory; reject LWW-as-crdt |
| False BFT marketing | Label tests; G ≠ bft (gate 12) |
| Branch observation → silent merge | Non-merge proof (MCPP-040 family) |
| Lease theft | Fence/lease checks fail closed on stale tokens |

See [trust-boundaries.md](trust-boundaries.md) B5 and [threat-model.md](threat-model.md)
T-TAMP-04, T-FED-01.

---

## 8. Profile-bundle relevance

| Bundle | State-model relationship |
| --- | --- |
| **Evidence Core** (A, B, F) | Causal mode aligns with Event DAG parents; immutable mode with CID artifacts |
| **Secure Delegation** (C, D) | Caps/policy CIDs on StateRef gate read/write; not a consistency mode |
| **Federated Mesh** (E, G) | Neighborhood coordination labels; partition-heal CRDT/consensus paths |
| **Commerce** (H) | Payment state must not be modeled as authorization capability |
| **Verified Execution** | State transitions in receipts bind CIDs; proofs/receipts still need verify |

---

## 9. Migration

**Authority class: non-normative.**

| Legacy pattern | Target mode | Migration action |
| --- | --- | --- |
| Process-local dict / cache | often `single_authority` | Introduce StateRef + DuckDB CAS; define lease owner |
| Append-only log of CIDs | `immutable` or `causal` | Prefer immutable for pure content; causal when parents matter |
| Timestamp LWW map called “CRDT” | `crdt` only if Automerge | Replace LWW; keep history if needed for audit |
| “Cluster agreed” boolean | `consensus` + label | Pick guarantee label; attach plugin evidence |
| Global merge-on-read | forbidden for `single_authority` | Surface conflicts; optional escalate to crdt/consensus |

Versioned migration of mode for an existing `id` **MUST** be explicit (new ref
or recorded migration), never a silent rewrite on a hot write path.

---

## 10. Conformance and evidence

| Level (ADR-0003) | State-related meaning |
| --- | --- |
| `structural` | StateRef validates; mode enum enforced |
| `canonical` | State document CIDs stable under `mcpp-jcs-v1` where claimed |
| `cryptographic` | Cap proofs on state access verified when required |
| `policy-enforced` | Retention/merge/confidentiality policies evaluated |
| `receipt-signed` / `proof-verified` | Outcomes that include state CIDs independently attested |

Suggested presence check for this architecture chapter:

```bash
test -s ipfs_accelerate_py/mcplusplus/docs/architecture/state-model.md
test -s ipfs_accelerate_py/mcplusplus/docs/spec/state-ref.md
```

Provider/gate evidence (when present in tree) is named in the traceability
matrix rows REQ-ST-01…04—not asserted complete by this document alone.

---

## 11. Checklist

1. Five modes only: `immutable`, `single_authority`, `causal`, `crdt`, `consensus`.  
2. DuckDB/Quack/DuckLake primary for single-authority (SQLite fallback); Automerge mandatory for CRDT.  
3. Four consensus labels; Profile G not BFT.  
4. Journal ≠ Event DAG ≠ StateRef authority.  
5. Profile bundles referenced without over-claim.  
6. No forbidden over-claim phrases; not production admission without tests.

## 12. References

- ADR-0004: [decisions/0004-state-modes.md](decisions/0004-state-modes.md)
- StateRef spec: [../spec/state-ref.md](../spec/state-ref.md)
- Event DAG: [../spec/event-dag-ordering.md](../spec/event-dag-ordering.md)
- Risk / scheduling (G): [../spec/risk-scheduling.md](../spec/risk-scheduling.md)
- Durable execution: [durable-execution.md](durable-execution.md)
- Consensus plugin (when present): [../spec/consensus-plugin.md](../spec/consensus-plugin.md)

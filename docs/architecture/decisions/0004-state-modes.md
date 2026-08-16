# ADR-0004: State consistency modes, DuckDB/Quack/DuckLake single-authority, and Automerge CRDT

- **Status:** Accepted
- **Date:** 2026-08-15
- **Last verified:** 2026-08-16
- **Deciders:** MCP++ 1.0 gap-closure program (MCPP-G020); sealed plan Key Decisions KD-8, KD-9, KD-10, and KD-11; 2026-08-16 operator correction of KD-9 runtime default
- **Scope:** The mandatory set of shared-state consistency modes for MCP++ 1.0; the rule that a `StateRef@1` declares exactly one mode; the primary single-authority backend (DuckDB with local Quack/DuckLake `LOAD`; SQLite fallback); the mandatory CRDT backend (Automerge); and honest labeling of consensus-class guarantees, including that Profile G neighborhood agreement is not BFT.
- **Non-goals:** Full `StateRef@1` schema and prose (MCPP-035); concrete provider implementations and restart/convergence tests (MCPP-036…040); DurableExecutor / journaled crash recovery (KD-12 / ADR-0005 / MCPP-017, MCPP-050…053); cryptographic suite (ADR-0002); envelope carrier shape (KD-7); which runtime package hosts adapters (ADR-0001 / MCPP-013); conformance-level ladder (ADR-0003 / MCPP-015); Profile F Event DAG normative event schemas beyond the non-merge rule for state modes.
- **Supersedes:** none
- **Superseded-by:** none
- **Related guides:**
  - Sealed plan: `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md` (§5 KD-8…KD-11; §10 gates 8, 10–12; §11 non-claim that Profile G is not BFT)
  - Traceability matrix: `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md` (REQ-ST-01…04, REQ-G-03)
  - Profile F draft: `ipfs_accelerate_py/mcplusplus/docs/spec/event-dag-ordering.md`
  - Profile G systems layer (mostly non-normative): `ipfs_accelerate_py/mcplusplus/docs/spec/risk-scheduling.md`
  - Future normative detail: `ipfs_accelerate_py/mcplusplus/docs/spec/state-ref.md` (MCPP-035); `ipfs_accelerate_py/mcplusplus/docs/spec/consensus-plugin.md` (MCPP-039)
- **Source anchors:**
  - `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md` — KD-8, KD-9, KD-10, KD-11; gate 8/10/11/12; §11 Profile G non-BFT
  - `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md` — REQ-ST-01…04
  - `ipfs_accelerate_py/mcplusplus/docs/spec/event-dag-ordering.md` — causal parents; partial order without global sequencer
  - `ipfs_accelerate_py/mcplusplus/docs/spec/risk-scheduling.md` — neighborhood agreement as coordination optimization, not consensus requirement
  - Kit coordination storage pattern (immutable blocks + local SQLite index): `ipfs_kit_py/ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py`
  - Downstream tasks MCPP-035…040 (StateRef schema and mode-specific providers)

## Status meanings (do not invent new values)

| Value | Use when |
| --- | --- |
| Proposed | Decision is under review; **not** yet evidenced current design |
| Accepted | Decision is normative for Scope (sealed defaults refined with tree evidence) |
| Deprecated | Still historical; prefer another practice for new work |
| Superseded | Replaced by the ADR in Superseded-by |
| Rejected | Considered and not adopted; retained to document the negative choice |

Only **Accepted** records are current design authority. **Proposed** records
must not be treated as implemented system law.

This ADR is **Accepted** as the binding state-mode and backend suite for MCP++
1.0 design and implementation tasks. It does **not** claim that `StateRef@1`,
SQLite restart tests, Automerge convergence tests, or consensus-plugin label
tests already exist in-tree; those land in MCPP-035…040. Documentation alone
does not close gates 8, 10, 11, or 12.

## Context

MCP++ agents share intents, decisions, receipts, and mutable work-product
across peers and Event DAG branches. Without an explicit consistency mode:

1. **Readers silently reconcile concurrent branches** and invent last-write-wins
   or “merge JSON objects” semantics that drop causal evidence.
2. **Backends are chosen ad hoc** (in-memory maps, informal LWW, remote
   databases) that cannot pass restart or partition-heal gates.
3. **Profile G neighborhood agreement is mislabeled as BFT**, overstating
   safety and blocking honest escalation to stronger consensus plugins.

Current-tree forces:

| Force | Evidence |
| --- | --- |
| Sealed plan requires exactly one consistency mode on `StateRef@1` | KD-8; gate 8; REQ-ST-01 status `missing` |
| Single-authority backend must be restart-testable and repository-native | KD-9; gate 10; REQ-ST-02 |
| CRDT must be a real library, not informal LWW | KD-10; gate 11; REQ-ST-03; MCPP-038 forbids inventing LWW |
| Consensus guarantees must be labeled honestly; Profile G is not BFT | KD-11; gate 12; plan §11; REQ-ST-04 / REQ-G-03; risk-scheduling §4 archive note |
| Event DAG already models causal parents without global total order | `event-dag-ordering.md` §§1–3 |
| Kit already uses SQLite as a local index beside immutable blocks | `coordination_storage.py` (authority model differs; SQLite presence is in-tree) |
| Downstream StateRef schema (MCPP-035) depends on this ADR’s mode enum | todo MCPP-035 acceptance: exactly those five modes |

If this decision is deferred, parallel lanes invent incompatible mode names,
claim “CRDT” for LWW maps, treat SQLite as optional, or advertise Profile G as
Byzantine-fault-tolerant. Gates 8 and 10–12 cannot close; MCPP-035…040 lack a
stable enum and backend mandate.

Who is affected: StateRef schema authors, state provider implementers,
Profile G neighborhood/coordination authors, DurableExecutor designers (who
must not conflate journal recovery with CRDT merge), operators reading
consistency claims on evidence bundles, and any peer that must fail closed on
missing or multi-mode state references.

## Decision

**MCP++ 1.0 uses exactly five mandatory state consistency modes, one mandatory
single-authority backend, one mandatory CRDT backend, and four distinct
consensus-class guarantee labels.** A `StateRef@1` MUST declare exactly one
mode. Implementations MUST fail closed on missing, unknown, multi-mode, or
silently cross-mode merge of mutable values. Profile G neighborhood agreement
MUST NOT be labeled BFT.

### 1. Mandatory consistency modes (exactly one)

A normative state reference declares **exactly one** of the following mode
identifiers (wire/string form is the snake_case token shown):

| Mode | Normative meaning | Merge / conflict rule |
| --- | --- | --- |
| `immutable` | Content-addressed, append-only values. Identity is CID (or equivalent content digest). | Mutation of an existing identity is rejected. New values mint new CIDs. No multi-writer merge. |
| `single_authority` | One authoritative writer (or leased exclusive writer) owns the live value. | Concurrent writers without a valid lease/fence produce an **explicit conflict**, not a silent merge. CAS / version preconditions apply. |
| `causal` | Values are ordered only by recorded causal history (Event DAG parents / clocks). | Concurrent branches remain concurrent until an explicit reconciliation policy is applied. Observing two branches MUST NOT invent a total order or merge payloads. |
| `crdt` | Multi-writer commutative/associative merge under a real CRDT. | Concurrent offline updates MUST converge after exchange. Merge evidence is the CRDT document state, not informal last-write-wins. |
| `consensus` | Agreement is produced only by a declared consensus **plugin** with an honest guarantee label. | Values change only when plugin evidence for the declared guarantee is present and valid for that mode. |

Rules:

| Rule | Normative statement |
| --- | --- |
| Exhaustive set | For MCP++ 1.0, allowed modes are **exactly** `immutable`, `single_authority`, `causal`, `crdt`, `consensus`. No aliases, no additional default modes, no free-text mode. |
| Exactly one | `StateRef@1` MUST carry a single mode field. Missing mode, multi-mode arrays, or dual “primary/fallback” modes on one ref are invalid. |
| Fail closed | Unknown mode strings, empty mode, or schema that accepts multi-mode without a superseding ADR MUST be rejected by validators and runtimes. |
| Non-merge across modes | Observing two concurrent Event DAG branches MUST NOT silently merge `single_authority` values. CRDT merge happens **only** in `crdt` mode. Consensus acceptance happens **only** in `consensus` mode with plugin evidence. |
| Mode immutability of a ref | A given `StateRef` identity does not silently change mode; mode change requires a new ref (or an explicit, versioned migration recorded outside silent write paths). |

Rationale alignment: KD-8; gate 8; MCPP-035 acceptance; MCPP-040 non-merge proof.

### 2. Single-authority backend: DuckDB / Quack / DuckLake (primary)

**Correction 2026-08-16:** MCP++ persistence is **DuckDB-primary**. The earlier
KD-9 SQLite-mandatory wording is superseded for runtime defaults. SQLite
remains an explicit fallback (`MCPPLUSPLUS_SQL_ENGINE=sqlite`).

| Rule | Normative statement |
| --- | --- |
| Primary backend | The **primary** production-capable backend for `single_authority` mode is **DuckDB**, with best-effort local **Quack** and **DuckLake** `LOAD` (never network `INSTALL`). |
| Durability features | The backend MUST support transactional commit and **compare-and-swap (CAS)** / version preconditions so concurrent writers and restart recovery are testable. |
| Restart obligation | Gate 10 requires restart tests that recover committed state and reject stale fences / CAS mismatches (implemented under MCPP-037 / MCPP-052 family). |
| Fallback adapter | **SQLite** MAY be used when DuckDB cannot be imported or when an operator sets `MCPPLUSPLUS_SQL_ENGINE=sqlite`. |
| Why DuckDB | MCP++ and the surrounding lift stack already treat DuckDB/Quack/DuckLake as the control-plane and payment ledger store; single-authority state must not silently default to a second engine. |

SQLite as single-authority **state** is distinct from SQLite used only as a
derived index beside immutable block stores (kit coordination storage). Index
rows remain rebuildable from immutable evidence; single-authority mode values
are the authority for that mode’s live keyspace and must pass CAS/restart
semantics on their own provider path.

### 3. CRDT backend: Automerge (mandatory)

| Rule | Normative statement |
| --- | --- |
| Mandatory backend | The **mandatory** CRDT backend for `crdt` mode is **Automerge**. |
| Real CRDT | Implementations MUST use Automerge (or a thin adapter over Automerge document semantics). They MUST NOT invent informal last-write-wins, timestamp maps, or “merge dicts” and call the result a CRDT. |
| License / bindings | Automerge is chosen for permissive licensing and real multi-language binding availability (Python/JS and related ecosystems), matching KD-10. |
| Convergence obligation | Gate 11 requires concurrent-update and partition-heal convergence tests (MCPP-038): two isolated replicas converge; duplicates are idempotent. |
| Evidence | CRDT merge evidence is the Automerge document / change history required to reproduce the converged state—not an ad-hoc winner timestamp alone. |

### 4. Consensus guarantees (four labels) and Profile G is not BFT

Consensus-class behavior is **not** a single boolean. Plugins and Profile G
coordination MUST use one of the following **honest guarantee labels**:

| Label | Meaning (normative intent) | Typical use |
| --- | --- | --- |
| `coordination` | Best-effort ordering or scheduling alignment; no safety claim under crash or Byzantine faults. | Neighborhood clustering, local frontier sync |
| `majority_approval` | Threshold approval among a declared peer set under an honest-majority **assumption for that set only**; not global BFT. | Profile G neighborhood majority / attestation-style approval |
| `crash_consensus` | Agreement among non-Byzantine processes that may crash/recover (classic CFT). | Raft/Paxos-class plugins when so declared |
| `bft` | Byzantine fault tolerance under a declared fault bound and membership. | Only when a plugin actually implements and tests BFT |

Rules:

| Rule | Normative statement |
| --- | --- |
| Four labels | The consensus plugin contract documents **exactly these four** guarantee classes: coordination, majority approval, crash consensus, BFT (wire names may use snake_case as above). |
| Profile G | Profile G neighborhood agreement is **`coordination` and/or `majority_approval` only**. It is **not** Byzantine-fault-tolerant consensus. Labeling a Profile G neighborhood result as `bft` is a **fail-closed error** (MCPP-039 acceptance; REQ-G-03; plan §11). |
| Escalation | Peers MAY escalate from neighborhood coordination to a stronger `consensus` mode plugin when conflicts or risk thresholds demand it; escalation MUST change the declared guarantee label and evidence format—not silently upgrade claims. |
| Evidence required | In `consensus` mode, state transitions require plugin evidence matching the declared guarantee. Absent evidence, the write fails closed. |
| No global chain requirement | MCP++ does not mandate one global BFT chain for all state. Neighborhood coordination remains an optimization path (risk-scheduling archive note). |

### 5. Mode-to-backend mapping (normative defaults)

| Mode | Mandatory backend / substrate | Notes |
| --- | --- | --- |
| `immutable` | Content-addressed block / artifact store (CID-native) | Append-only; MCPP-036 |
| `single_authority` | **DuckDB / Quack / DuckLake** (SQLite fallback) | MCPP-037 |
| `causal` | Event DAG parents / clocks as the ordering substrate | No silent total order; Profile F alignment |
| `crdt` | **Automerge** | Not informal LWW; MCPP-038 |
| `consensus` | Declared **consensus plugin** with one of the four labels | Profile G ≠ BFT; MCPP-039 |

### 6. Normative checklist (StateModeDecision@1)

An implementation claims this ADR only when all of the following hold for its
**new** normative state paths:

1. Allowed modes are exactly `immutable`, `single_authority`, `causal`, `crdt`, `consensus`.
2. Every `StateRef` declares exactly one mode; missing/unknown/multi-mode is invalid.
3. Single-authority production backend is DuckDB/Quack/DuckLake with transactional CAS; SQLite is an explicit fallback.
4. CRDT production backend is Automerge, not informal LWW.
5. Consensus paths use honest labels among coordination / majority_approval / crash_consensus / bft.
6. Profile G neighborhood results are never labeled BFT.
7. Cross-mode or silent Event DAG branch merges of mutable `single_authority` values are rejected (proven later by MCPP-040).

## Alternatives

### Alternative A: Free-form or open-ended consistency strings

- **Summary:** Allow `mode: string` with vendor-specific values.
- **Expected benefits:** Flexibility for experimental stores.
- **Why not chosen:** Breaks four-language schemas and interop; gates cannot test a closed enum; silent multi-mode invention returns. KD-8 requires a closed set.

### Alternative B: Treat Event DAG observation as automatic merge authority

- **Summary:** When two branches appear in the Event DAG, merge live state by LWW or recursive JSON merge.
- **Expected benefits:** “Always converges” demos.
- **Why not chosen:** Destroys single-authority leases, fences, and auditability. KD-8 explicitly forbids silent merge of mutable values across branches. Merge is allowed only under `crdt` (Automerge) or `consensus` (plugin evidence).

### Alternative C: DuckDB (or remote Postgres) as the mandatory single-authority backend

- **Summary:** Require DuckDB or a networked SQL service for all single-authority state.
- **Expected benefits:** Analytics features; multi-process sharing via a server.
- **Why not chosen (2026-08-15):** SQLite was already in-tree, local, and restart-testable without a new service (KD-9).
- **Correction 2026-08-16:** this alternative is now the **runtime default**. DuckDB/Quack/DuckLake is the primary single-authority store; SQLite remains the explicit fallback. The original rejection is retained as history.

### Alternative D: Informal last-write-wins labeled as “CRDT”

- **Summary:** Use timestamp or peer-rank winners and call the mode `crdt`.
- **Expected benefits:** Tiny dependency surface; easy to fake green tests.
- **Why not chosen:** Not a CRDT; diverges under reordering/duplication; assignment and KD-10 forbid informal LWW. Automerge is the mandatory real CRDT.

### Alternative E: Claim Profile G neighborhood agreement is BFT

- **Summary:** Market k-nearest-neighbor majority as Byzantine fault tolerance.
- **Expected benefits:** Stronger-sounding safety marketing.
- **Why not chosen:** False safety claim. Plan §11 and KD-11 state Profile G is coordination / majority approval, not BFT. MCPP-039 tests must fail closed on BFT mislabeling.

### Alternative F: Do nothing / status quo

- **Summary:** Defer mode enum and backend choice until providers land.
- **Why not chosen:** Wave 3 ADRs exist so Waves 4–6 (G060 state work) do not invent incompatible modes (MCPP-G020). Plan KD-8…KD-11 already decide; this ADR records them with evidence and consequences.

## Consequences

### Positive

- Closed mode enum unblocks `StateRef@1` schema (MCPP-035) and mode-specific providers (MCPP-036…039).
- DuckDB-primary mandate makes restart/CAS/lease tests (gate 10) a concrete obligation on the same engine family as Profile H ledgers and the lift control plane. SQLite remains a fallback.
- Automerge mandate prevents LWW-as-CRDT fakes and gives partition-heal tests a real merge engine (gate 11).
- Honest consensus labels stop Profile G from being oversold as BFT (gate 12; plan §11).
- Non-merge rule across Event DAG branches preserves auditability and exclusive-task fencing.

### Negative

- Five modes increase schema and test matrix surface versus a single “shared mutable map.”
- Automerge dependency must be maintained and version-pinned for multi-language adapters.
- SQLite single-writer / locking characteristics must be designed into leases and fencing (not a free multi-master SQL cluster).
- Authors must learn four consensus labels instead of a single “consensus: true” flag.
- Existing informal state helpers must be reclassified or rewritten to declare a mode and backend.

### Neutral / residual risks

- `StateRef@1` field set beyond mode (authority, lease, fence, clocks, merge policy CIDs) is specified in MCPP-035, not here.
- Automerge document size and compaction strategy remain implementation concerns for MCPP-038.
- DuckDB SQL dialect differs from SQLite (INTEGER width, upsert, RETURNING); the engine adapter must keep those translations honest. SQLite fallback remains restart-testable.
- Stronger BFT plugins may be added later only under the `bft` label with real evidence—not by rebranding Profile G.
- DurableExecutor crash recovery (KD-12) is related but separate: journaled effects ≠ state mode merge semantics.

## Evidence

| Claim in Decision | Evidence (path, test, or operational check) | Notes |
| --- | --- | --- |
| Exactly five modes on StateRef | Plan KD-8; gate 8; REQ-ST-01; MCPP-035 acceptance | Schema not yet landed (`missing`) |
| DuckDB is primary single-authority backend; SQLite is fallback | Plan KD-9 as corrected 2026-08-16; gate 10; REQ-ST-02; MCPP-037 | Restart tests run against the live engine |
| Automerge is mandatory CRDT | Plan KD-10; gate 11; REQ-ST-03; MCPP-038 | Forbids informal LWW |
| Four consensus guarantee labels; G ≠ BFT | Plan KD-11; plan §11; gate 12; REQ-ST-04; REQ-G-03; risk-scheduling §4 | MCPP-039 must fail if neighborhood labeled BFT |
| Causal mode aligns with Event DAG parents | `event-dag-ordering.md` §§1–3 | Causal mode ≠ automatic CRDT merge |
| Non-merge of single_authority across branches | KD-8 rationale; MCPP-040 | Proof test after providers exist |
| SQLite present in-tree | kit `coordination_storage.py`; future accelerate state package | Index use ≠ single-authority mode, but shows SQLite readiness |

Evidence classes used: sealed plan key decisions (design authority for this
wave), draft Profile F/G specs (tree intent), traceability matrix (gap status).
Provider implementations and gate evidence artifacts are **not** claimed
complete by this ADR.

## Verification

How a future reader confirms this ADR still holds:

1. **Document presence (this task):**
   ```text
   test -s ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/0004-state-modes.md
   ```
2. **Mode enum still closed:** inspect Decision §1 and, once landed,
   `ipfs_accelerate_py/mcplusplus/docs/spec/state-ref.md` plus
   `ipfs_accelerate_py/mcplusplus/schemas/state/state-ref-1.schema.json`
   for exactly the five modes.
3. **DuckDB-primary single-authority (later):**  
   `python -m pytest -q test/api/test_mcplusplus_duckdb_primary.py test/api/test_mcplusplus_state_sqlite_restart.py`
4. **Automerge CRDT (later):**  
   `python -m pytest -q test/api/test_mcplusplus_state_automerge.py`
5. **Consensus labels / non-BFT Profile G (later):**  
   `python -m pytest -q test/api/test_mcplusplus_state_consensus_labels.py`
6. **Non-merge (later):**  
   `python -m pytest -q test/api/test_mcplusplus_state_event_dag_nonmerge.py`
7. **Staleness signals:** a sixth default mode without a superseding ADR;
   SQLite claimed as the default/only single-authority backend; LWW
   labeled `crdt`; Profile G results labeled `bft`; silent merge of concurrent
   `single_authority` branches.

## Review triggers

- [ ] Source anchors no longer match the Decision statement
- [ ] A recorded negative consequence becomes unacceptable
- [ ] A rejected alternative (open mode strings, LWW-as-CRDT, G-as-BFT) becomes viable without those costs
- [ ] Security or trust-boundary changes touch leases, fences, or consensus evidence
- [ ] Automerge license, maintenance, or binding availability forces a superseding CRDT choice
- [ ] Superseding design is Accepted under a new ADR number

When superseding: create a new ADR number; set this file to **Superseded** with
`Superseded-by`; set the successor’s `Supersedes`; do not delete this file.

## Notes (optional)

### Downstream task map

| Concern | Follow-on |
| --- | --- |
| `StateRef@1` schema + `state-ref.md` | MCPP-035 |
| Immutable CID state provider | MCPP-036 |
| DuckDB/SQLite single-authority CAS/lease/restart | MCPP-037 |
| Automerge CRDT adapter + convergence tests | MCPP-038 |
| Consensus plugin contract + honest labels | MCPP-039 |
| Event DAG branch non-merge proof | MCPP-040 |
| DurableExecutor / journal (related, separate ADR) | MCPP-017, MCPP-050…053 |

### Interface label

Task interface id: **`StateModeDecision@1`** — the normative checklist in
Decision §6.

### Sealed defaults preserved

This ADR records plan KD-8, KD-10, and KD-11 without reopening them. KD-9’s
original SQLite-mandatory wording is retained as history; the 2026-08-16
correction makes DuckDB/Quack/DuckLake the runtime default and SQLite the
explicit fallback. Profile G non-BFT restatement is unchanged.

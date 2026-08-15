# ADR-0005: DurableExecutor, SQLite journaled adapter, and Restate/Dapr evaluation

- **Status:** Accepted
- **Date:** 2026-08-15
- **Last verified:** 2026-08-15
- **Deciders:** MCP++ 1.0 gap-closure program (MCPP-G020); sealed plan Key Decision KD-12
- **Scope:** The durable-execution contract for MCP++ 1.0 (`DurableExecutor`); the mandatory production-capable adapter (SQLite journaled executor, locally crash-recovery testable); the evaluation of Restate and Dapr as optional second adapters; the admission rule that a second adapter is adopted only when a repeatable local compose environment works without unpaid cloud; and the separation of journaled crash recovery from Event DAG validation and state-mode merge semantics.
- **Non-goals:** Full `DurableExecutor@1` method schemas and prose (MCPP-050); concrete SQLite journal package and unit tests (MCPP-051); crash-recovery integration test (MCPP-052); accelerate runtime binding (MCPP-053); reimplementing a full commercial workflow engine; state consistency modes and single-authority SQLite for `StateRef` (ADR-0004 / KD-8…KD-11); crypto suite (ADR-0002); envelope carrier shape (KD-7); A2A task lifecycle ownership (KD-13 / ADR-0006); which package owns schemas vs adapters beyond restating that DurableExecutor is defined in the spec repo (ADR-0001 / MCPP-013).
- **Supersedes:** none
- **Superseded-by:** none
- **Related guides:**
  - Sealed plan: `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md` (§5 KD-12; §10 gate 17; §15 open question resolved here)
  - Traceability matrix: `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md` (REQ-DUR-01)
  - Goal tree: MCPP-G090 Durable execution adapter
  - State modes (related, not the same problem): `ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/0004-state-modes.md`
  - Future normative detail: `ipfs_accelerate_py/mcplusplus/docs/architecture/durable-execution.md` (MCPP-050); schemas under `ipfs_accelerate_py/mcplusplus/schemas/durable/`
  - Future runtime package: `ipfs_accelerate_py/mcp_server/mcplusplus/durable/` (MCPP-051)
- **Source anchors:**
  - `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md` — KD-12; gate 17; PR-11; §15 Restate/Dapr vs SQLite decision deferred to MCPP-017
  - `docs/architecture/mcplusplus_1_0_gap_closure.objectives.md` — MCPP-G090 evidence policy (SQLite mandatory; Restate/Dapr second only with local environment)
  - `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md` — REQ-DUR-01 status `missing`
  - Kit SQLite pattern (local durability presence, different authority model): `ipfs_kit_py/ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py`
  - Downstream tasks MCPP-050…053

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

This ADR is **Accepted** as the binding durable-executor choice for MCP++ 1.0
design and implementation tasks. It does **not** claim that `DurableExecutor@1`,
the SQLite journal adapter, crash-recovery tests, or accelerate bindings already
exist in-tree; those land in MCPP-050…053. Documentation alone does not close
gate 17.

## Context

MCP++ multi-step agent work must survive process death without repeating
committed side effects or losing cancellation and deontic obligations. Without
an explicit durable-execution contract:

1. **In-memory “retry” is mistaken for crash recovery**, so kill-restart demos
   pass while production restarts re-dispatch external effects.
2. **Workflow engines are chosen ad hoc** (Restate, Dapr workflows, Temporal,
   custom Redis queues) that CI cannot run without unpaid cloud accounts or
   non-repeatable cluster setup.
3. **Journaling is folded into Event DAG validators or state providers**,
   conflating causal history, consistency modes, and step-commit fences.

Current-tree forces:

| Force | Evidence |
| --- | --- |
| Sealed plan requires a DurableExecutor defined in the spec repo | KD-12; MCPP-G090; REQ-DUR-01 status `missing` |
| First production-capable adapter must satisfy crash recovery **locally** | KD-12; gate 17; G090 refinement: in-memory retry is not crash recovery |
| Restate and Dapr must be **evaluated** in this ADR; adoption as second adapter is conditional | KD-12; plan §15; G090 evidence source policy; MCPP-051 conflict policy |
| Fail closed if an external engine cannot be tested without unpaid cloud or non-repeatable compose | KD-12 rationale |
| Interface surface is large but fixed for 1.0: start/resume/signal/cancel/checkpoint/retry/timer/compensation/inspect/recover/finalize | MCPP-G090 acceptance; MCPP-050 effects |
| Journaled effects ≠ state-mode merge semantics | ADR-0004 neutral risk; G090 conflict policy |
| SQLite is already in-tree and restart-testable | KD-9 pattern; kit `coordination_storage.py`; aligns with local-test mandate |

If this decision is deferred, parallel lanes invent incompatible retry loops,
claim “durable” for process-local queues, or hard-depend on Restate/Dapr without
a local CI path. Gate 17 cannot close; MCPP-050…053 lack a stable adapter
mandate and second-adapter admission rule.

Who is affected: DurableExecutor interface authors (MCPP-050), SQLite journal
implementers (MCPP-051), crash-recovery and accelerate binding authors
(MCPP-052…053), operators reading evidence-bundle claims about resume safety,
and any peer that must fail closed on missing journal or stale fencing tokens.

## Decision

**MCP++ 1.0 defines `DurableExecutor` in the Mcp-Plus-Plus / mcplusplus spec
tree and uses a SQLite journaled executor as the mandatory production-capable
adapter.** Restate and Dapr are evaluated below and are **not** mandatory.
Either MAY become an optional second adapter only when a repeatable local
compose environment works without unpaid cloud. Implementations MUST fail
closed when journal durability, idempotency keys, or fencing tokens are missing
on paths that claim crash-safe resume.

### 1. Spec-owned DurableExecutor contract

| Rule | Normative statement |
| --- | --- |
| Definition locus | The **`DurableExecutor`** interface, journal record shapes, and crash-recovery receipt bindings are defined in the **spec repo / mcplusplus package** (schemas + architecture prose), not reinvented per runtime. |
| Runtime adapters | Accelerate (and other runtimes) **consume** the interface via adapters; they MUST NOT ship a second private durable contract for MCP++ 1.0 portable claims. |
| Version | Interface family for 1.0 is **`DurableExecutor@1`** (detail in MCPP-050). Related labels: `DurableJournalRecord@1`, `CrashRecoveryReceipt@1`. |
| Not a full engine rewrite | MCP++ must not reimplement a commercial workflow product end-to-end; it **must** have a stable durable contract and at least one local, testable adapter. |

Normative method surface (typed request/result for each lands in MCPP-050):

| Method family | Intent |
| --- | --- |
| `start` | Begin a durable execution under a declared task / envelope identity. |
| `resume` | Continue after checkpoint or process restart from journaled state. |
| `signal` | Deliver an external signal without inventing a parallel lifecycle. |
| `cancel` | Persist cancellation; subsequent effects fail closed as cancelled. |
| `checkpoint` | Commit durable progress before externally visible work continues. |
| `retry` | Retry under journaled policy; not a substitute for crash recovery. |
| `timer` (durable) | Schedule work that survives process death when the journal says so. |
| `compensation` | Record and drive compensating actions for committed effects. |
| `inspect` | Read execution/journal status for operators and evidence bundles. |
| `recover` | Reconstruct runnable state after kill; reject stale fences. |
| `finalize` | Terminal success/failure binding; outputs align with signed receipts. |

Rules:

| Rule | Normative statement |
| --- | --- |
| Journaled transitions | Externally visible step transitions map to journal records and MAY emit Event DAG events; validators of the DAG are not the journal authority. |
| Final outputs | Final outputs bind to signed receipts / portable execution results when those profiles apply (envelope work in MCPP-030 family). |
| Fail closed | Missing required journal commits, unknown executor adapter ids on claimed paths, or recovery without a valid fencing epoch MUST fail closed. |

### 2. Mandatory adapter: SQLite journaled executor

| Rule | Normative statement |
| --- | --- |
| Mandatory adapter | The **mandatory** production-capable DurableExecutor adapter for MCP++ 1.0 is a **SQLite journaled executor**. |
| Local testability | Crash recovery MUST be demonstrable **locally** (process kill → restart → resume) without unpaid cloud services or non-repeatable remote clusters. |
| Durability features | The journal MUST use SQLite durability suitable for restart tests (WAL or equivalent documented mode) and transactional commit of journal records. |
| Idempotency | Externally visible steps carry **idempotency keys**; retries and recover MUST NOT re-commit the same side effect after a successful journal commit. |
| Cancellation and obligations | Cancel state, timers, and deontic obligations that the executor accepted MUST survive restart when journaled. |
| Fencing | Recovery and exclusive resume MUST reject **stale fencing tokens** / leases (same fail-closed spirit as single-authority CAS; not the same store as `StateRef` unless explicitly bound). |
| Placement | Implementation package target: `ipfs_accelerate_py/mcp_server/mcplusplus/durable/` (e.g. `sqlite_executor.py`, `journal.py`) per MCPP-051. |
| Conformance claims | Gate 17 and REQ-DUR-01 close only when this adapter (or a later Accepted supersession) passes crash recovery without duplicate effects. |

SQLite as a **durable execution journal** is related to but distinct from SQLite
as the mandatory **single-authority state** backend (ADR-0004 / KD-9). A runtime
MAY use one SQLite file or separate files; the journal’s authority is step
commit and recovery, not CRDT merge or multi-mode `StateRef` semantics.

### 3. Restate evaluation (optional second adapter only)

| Criterion | Evaluation |
| --- | --- |
| Product fit | Restate provides durable handlers, journaled invocations, and strong “exactly-once effect” tooling attractive for multi-step agent workflows. |
| Local testability today | Full Restate stack requires a Restate server process and language SDK wiring. Not present as a mandatory in-tree dependency for MCP++ 1.0. |
| Unpaid cloud | Managed Restate Cloud (or equivalent) is **not** an acceptable sole CI path for mandatory conformance. |
| Compose | A **second adapter** MAY be admitted only if a **repeatable local compose** (Docker Compose or equivalent) boots Restate + the adapter, is scriptable in CI without secrets paid accounts, and proves the same DurableExecutor contract (including crash recovery semantics as defined for the interface). |
| Status for MCP++ 1.0 | **Not mandatory.** Restate absence is a **documented non-blocker** for MCPP-051 and gate 17. |
| Decision | **Reject Restate as the mandatory executor.** Defer optional Restate adapter until local compose + contract tests exist under a follow-on task; do not block SQLite journal work. |

### 4. Dapr evaluation (optional second adapter only)

| Criterion | Evaluation |
| --- | --- |
| Product fit | Dapr workflows / actors offer durable orchestration, state stores, and sidecar patterns used in some multi-service agent deployments. |
| Local testability today | Dapr requires sidecar or equivalent control plane, plus a state store configuration. Heavier than an in-process SQLite journal for unit and crash-recovery tests. |
| Unpaid cloud | Hosted Dapr or cloud-only state stores are **not** an acceptable sole CI path for mandatory conformance. |
| Compose | A **second adapter** MAY be admitted only if a **repeatable local compose** runs Dapr (or Dapr workflow components) + the adapter without unpaid cloud, and proves the DurableExecutor contract. |
| Status for MCP++ 1.0 | **Not mandatory.** Dapr absence is a **documented non-blocker** for MCPP-051 and gate 17. |
| Decision | **Reject Dapr as the mandatory executor.** Defer optional Dapr adapter until local compose + contract tests exist under a follow-on task; do not block SQLite journal work. |

### 5. Second-adapter admission rule (fail closed)

| Rule | Normative statement |
| --- | --- |
| When allowed | An optional Restate, Dapr, or other external engine adapter MAY land only after: (1) DurableExecutor@1 exists; (2) SQLite journal adapter exists and remains the mandatory path; (3) **repeatable local compose** is checked into the repository (or an official subpath) and runs without unpaid cloud credentials. |
| What it must prove | Same interface surface and crash-recovery properties: no duplicate committed side effects after kill-restart; cancel/obligation persistence; stale fence reject; idempotent retry. |
| What it must not do | Replace SQLite as the mandatory adapter for MCP++ 1.0 conformance claims; require cloud-only CI; fold engine-specific lifecycle into a competing public task model that conflicts with A2A (KD-13). |
| Fail closed | If local compose is non-repeatable, flaky, or cloud-gated, the external adapter MUST NOT be claimed production-capable for MCP++ 1.0 gates. |

### 6. Explicit non-claims and separations

| Separation | Normative statement |
| --- | --- |
| In-memory retry ≠ crash recovery | A successful retry inside one process lifetime does **not** satisfy gate 17. |
| Journal ≠ Event DAG validator | Causal parents and DAG ordering remain Profile F concerns; the journal is the authority for step commit and recover. |
| Journal ≠ state mode merge | CRDT/Automerge and single-authority CAS (ADR-0004) are not substitutes for durable step journals. |
| Transport ≠ executor authority | PeerID / TLS identity never grants durable resume rights (KD-14); fencing and journal ownership do. |

### 7. Decision checklist (`DurableExecutorDecision@1`)

A reader may treat the following as the interface label **`DurableExecutorDecision@1`**:

1. DurableExecutor is defined in the spec/mcplusplus tree (`DurableExecutor@1`).
2. Mandatory production-capable adapter is the **SQLite journaled executor**, locally crash-recovery testable.
3. Restate evaluated: capable product, **not mandatory**; optional only with repeatable local compose.
4. Dapr evaluated: capable product, **not mandatory**; optional only with repeatable local compose.
5. Second adapter admission is fail-closed without unpaid cloud and without displacing SQLite as mandatory.
6. Absence of Restate/Dapr is a non-blocker for SQLite journal implementation and gate 17 evidence.
7. In-memory retry is explicitly rejected as crash-recovery evidence.

## Alternatives

### Alternative A: Restate as the mandatory DurableExecutor

- **Summary:** Require Restate server + SDK for all MCP++ durable claims.
- **Expected benefits:** Mature journaled invocation model; less custom journal code.
- **Why not chosen:** Local, unpaid-cloud crash-recovery CI is not guaranteed; raises operator and CI cost; KD-12 requires a SQLite journaled first adapter and fail-closed external engines. Restate remains an optional second adapter under §5.

### Alternative B: Dapr workflows as the mandatory DurableExecutor

- **Summary:** Require Dapr sidecars/workflows for all durable agent steps.
- **Expected benefits:** Polyglot sidecar ecosystem; existing enterprise deployments.
- **Why not chosen:** Heavier local footprint; compose/cloud ambiguity; same KD-12 fail-closed rule. Dapr remains optional under §5.

### Alternative C: In-process memory queue labeled “durable”

- **Summary:** Keep steps in RAM with retry loops; claim crash recovery from successful retries.
- **Expected benefits:** Fast unit tests; zero dependencies.
- **Why not chosen:** G090 refinement and gate 17 require kill-restart without duplicate side effects. Memory is not a journal across process death.

### Alternative D: Temporal (or other external engines) as mandatory without evaluation

- **Summary:** Pick Temporal/Cadence/etc. as the only engine.
- **Expected benefits:** Popular workflow UX.
- **Why not chosen:** Same local-compose and unpaid-cloud constraints as Restate/Dapr; not required by the sealed plan. Any such engine would face the same second-adapter admission rule.

### Alternative E: Fold journaling into Event DAG validators or StateRef providers

- **Summary:** Treat DAG append or state CAS as the only durability mechanism.
- **Expected benefits:** Fewer packages.
- **Why not chosen:** Conflates causal history, consistency modes, and step-commit fences; G090 conflict policy forbids folding journaling into Event DAG validators; ADR-0004 separates merge semantics from crash recovery.

### Alternative F: Do nothing / status quo

- **Summary:** Defer executor choice until MCPP-050 implementation starts.
- **Why not chosen:** Wave 3 ADRs exist so Wave durable work (MCPP-G090) does not invent incompatible adapters (MCPP-G020). Plan KD-12 already decides; this ADR records Restate/Dapr evaluation and consequences.

## Consequences

### Positive

- Parallel lanes share one contract: DurableExecutor@1 with a SQLite journaled mandatory adapter.
- Gate 17 has a concrete, local evidence path (MCPP-051…052) without cloud accounts.
- Restate and Dapr evaluation is recorded; their absence cannot block SQLite work (MCPP-051 acceptance).
- Clear second-adapter admission rule prevents silent hard-deps on non-repeatable stacks.
- Separation from Event DAG validators and state modes keeps PR-11 scope coherent.

### Negative

- Custom SQLite journal and fencing semantics must be designed and tested (implementation cost in MCPP-050…052).
- Optional Restate/Dapr adapters, if ever added, increase CI matrix and adapter surface.
- Operators cannot assume a managed workflow SaaS is part of MCP++ 1.0 mandatory conformance.
- Method surface is large (start through finalize); schema and test work is non-trivial.

### Neutral / residual risks

- Exact SQLite schema for journal rows, WAL pragmas, and multi-process lock policy are specified in MCPP-050…051, not frozen here beyond durability and fail-closed intent.
- Mapping journal transitions to Event DAG event types is MCPP-050 acceptance detail.
- Accelerate binding (MCPP-053) may need careful integration with existing workflow_engine / task_queue modules without creating a second public lifecycle.
- A future Accepted ADR may elevate a second adapter after compose evidence exists; until then SQLite remains mandatory.
- Shared SQLite files between state provider and journal need careful table/namespace separation if colocated.

## Evidence

| Claim in Decision | Evidence (path, test, or operational check) | Notes |
| --- | --- | --- |
| DurableExecutor defined in spec repo; SQLite first adapter | Plan KD-12; gate 17; REQ-DUR-01; MCPP-G090 | Interface + adapter not yet landed (`missing`) |
| Restate evaluated; not mandatory | This ADR §3; plan §15; MCPP-051 “Restate/Dapr absence is a documented non-blocker” | Optional only with local compose |
| Dapr evaluated; not mandatory | This ADR §4; same plan/todo anchors | Optional only with local compose |
| Second adapter only with repeatable local compose / no unpaid cloud | KD-12 rationale; G090 evidence source policy | Fail closed otherwise |
| Crash recovery ≠ in-memory retry | G090 refinement; gate 17 wording | MCPP-052 must kill process |
| Journal separate from Event DAG validators | G090 conflict policy; ADR-0004 residual risk | Separate packages |
| SQLite local durability presence in tree | kit `coordination_storage.py`; KD-9 pattern | Index use ≠ durable journal, but shows SQLite readiness |
| Downstream interface methods | MCPP-G090 acceptance; MCPP-050 effects | Typed requests/results in MCPP-050 |

Evidence classes used: sealed plan key decisions (design authority for this
wave), objectives evidence policy, traceability matrix (gap status). SQLite
journal implementation and gate 17 artifacts are **not** claimed complete by
this ADR.

## Verification

How a future reader confirms this ADR still holds:

1. **Document presence (this task):**
   ```text
   test -s ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/0005-durable-executor.md
   ```
2. **Mandatory adapter still SQLite journal:** inspect Decision §2 and, once
   landed, `ipfs_accelerate_py/mcplusplus/docs/architecture/durable-execution.md`
   plus `ipfs_accelerate_py/mcp_server/mcplusplus/durable/sqlite_executor.py`.
3. **Restate/Dapr remain non-mandatory unless compose exists:** no mandatory
   dependency on Restate/Dapr in MCP++ 1.0 conformance without a superseding ADR
   and checked-in local compose evidence.
4. **Unit journal properties (later):**  
   `python -m pytest -q test/api/test_mcplusplus_durable_sqlite.py`
5. **Crash recovery (later / gate 17):**  
   `cd ipfs_accelerate_py && python -m pytest -q test/api/test_mcplusplus_durable_crash_recovery.py`
6. **Staleness signals:** Restate or Dapr claimed as the only durable path;
   in-memory retry accepted as crash recovery; unpaid-cloud-only CI for
   mandatory durable claims; journaling folded into Event DAG validators as the
   sole durability mechanism; absence of SQLite journal adapter while claiming
   gate 17 closed.

## Review triggers

- [ ] Source anchors no longer match the Decision statement
- [ ] A recorded negative consequence becomes unacceptable
- [ ] A rejected alternative (Restate-mandatory, Dapr-mandatory, memory-as-durable) becomes viable without unpaid cloud and with repeatable local compose for *mandatory* claims
- [ ] Security or trust-boundary changes touch fencing, cancel persistence, or resume authority
- [ ] A second adapter lands with full local compose and contract tests and needs elevation (superseding ADR)
- [ ] Superseding design is Accepted under a new ADR number

When superseding: create a new ADR number; set this file to **Superseded** with
`Superseded-by`; set the successor’s `Supersedes`; do not delete this file.

## Notes (optional)

### Downstream task map

| Concern | Follow-on |
| --- | --- |
| DurableExecutor interface + journal/Event DAG mapping | MCPP-050 |
| SQLite journaled adapter (idempotency, cancel, fences) | MCPP-051 |
| Crash-recovery integration test (gate 17) | MCPP-052 |
| Accelerate runtime bind start/resume/cancel + Event DAG | MCPP-053 |
| Optional Restate adapter (only with local compose) | Follow-on after MCPP-051; non-blocking |
| Optional Dapr adapter (only with local compose) | Follow-on after MCPP-051; non-blocking |

### Interface label

Task interface id: **`DurableExecutorDecision@1`** — the normative checklist in
Decision §7.

### Sealed defaults preserved

This ADR records plan KD-12 without reopening it. Restate and Dapr are
evaluated and rejected as mandatory adapters; the SQLite journaled executor
remains the mandatory production-capable path; second adapters are admitted only
under the local-compose / no-unpaid-cloud rule. Refinements (method family
table, admission checklist, journal vs state/Event DAG separations) stay inside
that default and cite current-tree evidence.

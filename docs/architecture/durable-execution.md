# Durable Execution (`DurableExecutor@1`)

**Status:** Normative (MCP++ 1.0 interface contract)  
**Interfaces:** `DurableExecutor@1`, `DurableJournalRecord@1`, `CrashRecoveryReceipt@1`  
**Schema:** `schemas/durable/durable-executor-1.schema.json`  
**Task (docs packaging):** MCPP-078 · Goal `MCPP-G170` · Bundle `mcplusplus/1.0/docs-architecture`  
**Schema markers:**

| Interface | Schema marker |
| --- | --- |
| Method request | `mcp++/durable/executor-request@1` |
| Method result | `mcp++/durable/executor-result@1` |
| Journal record | `mcp++/durable/journal-record@1` |
| Crash-recovery receipt | `mcp++/durable/crash-recovery-receipt@1` |

**Authority:** Plan KD-12; gate 17; goal `MCPP-G090`; tasks `MCPP-050`…`MCPP-053`; ADR-0005.  
**Depends on:** ADR-0005 (`MCPP-017`), ExecutionEnvelope family + validators (`MCPP-033`), StateProvider@1 (`MCPP-036`).  
**Related architecture:** [overview.md](overview.md), [state-model.md](state-model.md), [trust-boundaries.md](trust-boundaries.md), [threat-model.md](threat-model.md).  
**Related specs:** [execution-envelope.md](../spec/execution-envelope.md), [event-dag-ordering.md](../spec/event-dag-ordering.md), [state-ref.md](../spec/state-ref.md), ADR-0001 (spec/runtime ownership), ADR-0003 (conformance levels), ADR-0004 (state modes).

| Section family | Authority class |
| --- | --- |
| Interface methods, journal, fail-closed rules (§3–§9) | **normative** |
| Adapter placement and DuckDB/Quack primary (§10) | **normative** (ADR-0005) |
| Conformance mapping (§11) | **normative** scoring vocabulary |
| Profile-bundle relevance (§15) | **normative** packaging (KD-17) |
| Migration (§16) | **non-normative** operator guidance |
| This document alone as gate-17 closure | **not production-admitted** |

Normative keywords **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are used as described in RFC 2119.

Schema acceptance is **structural** only (ADR-0003). Crash recovery, idempotent side-effect commit, fencing, and receipt signature verification are higher conformance levels proven by adapters and tests (`MCPP-051`…`MCPP-053`). Documentation prose does not admit production deployment by itself.

---

## 1. Purpose

Multi-step agent work must survive process death without repeating committed
side effects or losing cancellation and deontic obligations. MCP++ therefore
defines a single durable-execution contract in the spec tree:

1. **`DurableExecutor@1`** — typed methods for start, resume, signal, cancel,
   checkpoint, retry, durable timer, compensation, inspect, recover, and
   finalize.
2. **`DurableJournalRecord@1`** — append-only journal rows that are the
   authority for step commit and recovery.
3. **`CrashRecoveryReceipt@1`** — evidence that recover reconstructed runnable
   state without replaying committed effects.

Runtimes (accelerate and others) **consume** this interface via adapters. They
**MUST NOT** ship a second private durable contract for MCP++ 1.0 portable
claims (ADR-0001 / ADR-0005).

This chapter is the interface specification. The primary production-capable
adapter is the **DuckDB/Quack journaled executor** (ADR-0005). SQLite is an
explicit fallback. Restate and Dapr are optional second adapters only under
the local-compose admission rule.

### 1.1 Non-goals

- Reimplementing a commercial workflow engine end-to-end.
- Using Event DAG validators as the journal authority (Profile F remains
  causal history; the journal owns step commit and recover).
- Using StateRef merge / CAS as a substitute for durable step journals
  (ADR-0004).
- Treating in-process memory retry as crash recovery (gate 17).

---

## 2. Architecture

```text
  requester / runtime              DurableExecutor@1                 Journal + Event DAG
        |                                |                                    |
        |-- start(envelope_cid) -------->|-- append journal: started -------->|
        |                                |-- (MAY) emit event_type=envelope -->|
        |                                |-- run step under fences            |
        |-- checkpoint / side-effect --->|-- append journal: checkpointed --->|
        |                                |-- (MAY) emit event_type=decision -->|
        |         process kill           |                                    |
        |-- recover(fencing_token) ----->|-- reconstruct from journal ------->|
        |                                |-- reject stale fences              |
        |-- resume --------------------->|-- continue from last commit ------->|
        |-- finalize(result_cid) ------->|-- bind signed ExecutionReceipt@1 ->|
        |                                |-- emit event_type=receipt -------->|
```

| Layer | Authority | Must not be used as |
| --- | --- | --- |
| **Journal** (`DurableJournalRecord@1`) | Step commit, recover, cancel persistence, timers, fencing epoch | Sole causal audit trail |
| **Event DAG** (Profile F) | Partial-order provenance, audit, replay of published events | Crash-recovery journal |
| **StateProvider@1** | Shared mutable / immutable state under `StateRef@1` modes | Durable step fence without a journal |
| **ExecutionEnvelope / Result / Receipt** | Portable request, attempt outcome, signed attestation | Process-local retry queue |

Transport PeerID / TLS client cert **MUST NOT** grant durable resume rights
(KD-14). Resume and exclusive recover **MUST** use journal ownership plus
fencing tokens.

---

## 3. Lifecycle states

A durable execution progresses through closed status values:

| Status | Meaning |
| --- | --- |
| `pending` | Accepted identity reserved; no runnable journal head yet |
| `running` | Active; may accept checkpoint, signal, timer, cancel |
| `paused` | Waiting on timer, signal, or external input |
| `cancelling` | Cancel recorded; in-flight work must fail closed as cancelled |
| `cancelled` | Terminal cancel |
| `compensating` | Driving compensation for committed effects |
| `compensated` | Terminal after successful compensation |
| `succeeded` | Terminal success; finalize produced / bound a receipt |
| `failed` | Terminal failure; finalize bound a receipt with error |
| `rejected` | Failed closed before durable start (authority, schema, fence) |
| `timed_out` | Terminal timeout |

Terminal statuses: `cancelled`, `compensated`, `succeeded`, `failed`,
`rejected`, `timed_out`. After a terminal status, only `inspect` **MUST**
succeed for that `execution_id`; mutating methods **MUST** fail closed.

---

## 4. Interface surface

Every method **MUST** use the typed request and result shapes defined in
`durable-executor-1.schema.json`. Implementations **MAY** expose language-native
methods that map 1:1 to these shapes; wire and evidence bundles **SHOULD** use
the JSON Schema markers.

| Method | Request | Result | Intent |
| --- | --- | --- | --- |
| `start` | `StartRequest` | `StartResult` | Begin durable execution under a declared envelope identity |
| `resume` | `ResumeRequest` | `ResumeResult` | Continue after checkpoint or process restart from journaled state |
| `signal` | `SignalRequest` | `SignalResult` | Deliver an external signal without a parallel lifecycle |
| `cancel` | `CancelRequest` | `CancelResult` | Persist cancellation; subsequent effects fail closed as cancelled |
| `checkpoint` | `CheckpointRequest` | `CheckpointResult` | Commit durable progress before further externally visible work |
| `retry` | `RetryRequest` | `RetryResult` | Retry under journaled policy (not a substitute for crash recovery) |
| `timer` | `TimerRequest` | `TimerResult` | Schedule work that survives process death when journaled |
| `compensation` | `CompensationRequest` | `CompensationResult` | Record and drive compensating actions for committed effects |
| `inspect` | `InspectRequest` | `InspectResult` | Read execution / journal status for operators and evidence |
| `recover` | `RecoverRequest` | `RecoverResult` | Reconstruct runnable state after kill; reject stale fences |
| `finalize` | `FinalizeRequest` | `FinalizeResult` | Terminal binding; outputs bind to signed receipts |

### 4.1 Common request fields

All method requests **MUST** carry:

| Field | Type | Notes |
| --- | --- | --- |
| `schema` | const | `mcp++/durable/executor-request@1` |
| `method` | enum | One of the eleven method names above |
| `request_id` | string | Caller-supplied id for correlation of the call itself |
| `issued_at_ms` | int | Wall-clock ms; informational only |

Most mutating methods also carry:

| Field | Type | Notes |
| --- | --- | --- |
| `execution_id` | string | Stable durable execution identity (assigned on `start`) |
| `fencing_token` | integer | Exclusive-work epoch; stale tokens **MUST** be rejected |
| `idempotency_key` | string | Required for externally visible commits |

### 4.2 Common result fields

All method results **MUST** carry:

| Field | Type | Notes |
| --- | --- | --- |
| `schema` | const | `mcp++/durable/executor-result@1` |
| `method` | enum | Echo of the request method |
| `request_id` | string | Echo of the request |
| `ok` | boolean | Structural success of the method call |
| `status` | enum | Current execution status after the call (or `rejected` if not started) |
| `error` | object \| null | Portable-style closed error when `ok` is false |

When a call journals a transition, results **SHOULD** include:

| Field | Type | Notes |
| --- | --- | --- |
| `journal_seq` | integer | Monotonic journal sequence for this execution |
| `journal_record_cid` | CID | Content id of the `DurableJournalRecord@1` when minted |
| `event_cid` | CID \| null | Event DAG node for the journaled transition when emitted |

---

## 5. Method contracts

### 5.1 `start`

**Request (`StartRequest`):**

| Field | Required | Notes |
| --- | --- | --- |
| `envelope_cid` | yes | CID of `ExecutionEnvelope@1` to execute |
| `idempotency_key` | yes | Same key + envelope **MUST** return the same `execution_id` without re-starting |
| `correlation_id` | no | Observability; defaults from envelope when omitted |
| `executor_did` | no | Intended executor identity |
| `initial_checkpoint_cid` | no | Optional pre-seeded progress document |
| `parent_execution_id` | no | Child / continuation linkage |
| `claim_fencing_token` | no | Initial exclusive claim; if omitted, adapter assigns epoch `1` |

**Result (`StartResult`):** `execution_id`, assigned `fencing_token`, initial
`journal_seq`, `status` (`running` or `rejected`), optional `event_cid`.

Rules:

1. `start` **MUST** validate envelope structural identity before journaling.
2. Duplicate `idempotency_key` for an existing non-terminal execution **MUST**
   return the prior `execution_id` (idempotent accept), not a second journal root.
3. Portable / cross-trust envelopes **MUST** carry authority proofs; missing
   proofs **MUST** fail closed (`status: rejected`).

### 5.2 `resume`

**Request (`ResumeRequest`):** `execution_id`, `fencing_token` (required),
optional `from_checkpoint_id`, optional `after_recover` boolean.

**Result (`ResumeResult`):** current `status`, `last_checkpoint_id`,
`journal_seq`, optional `event_cid`.

Rules:

1. `resume` **MUST** load the latest committed journal head.
2. Stale or missing `fencing_token` **MUST** fail closed.
3. Resume after process death **SHOULD** be preceded by `recover` when the
   adapter cannot prove exclusive ownership of the journal lease.

### 5.3 `signal`

**Request (`SignalRequest`):** `execution_id`, `signal_name`, optional
`payload_cid`, optional `fencing_token`.

**Result (`SignalResult`):** `accepted`, `journal_seq`, optional `event_cid`.

Rules:

1. Signals **MUST NOT** invent a parallel task lifecycle (KD-13 / A2A).
2. Unknown `execution_id` or terminal status **MUST** fail closed.
3. Accepted signals **MUST** be journaled before delivery to running steps is
   acknowledged.

### 5.4 `cancel`

**Request (`CancelRequest`):** `execution_id`, optional `reason`, optional
`fencing_token`, optional `idempotency_key`.

**Result (`CancelResult`):** `status` (`cancelling` or `cancelled`),
`journal_seq`, optional `event_cid`.

Rules:

1. Cancel **MUST** be durable: after journal commit, restarts **MUST** observe
   cancelled / cancelling and **MUST NOT** commit new external side effects.
2. Accepted deontic obligations that require cancel-time cleanup **SHOULD** be
   driven via `compensation` or finalize error paths, not silently dropped.

### 5.5 `checkpoint`

**Request (`CheckpointRequest`):** `execution_id`, `fencing_token`,
`idempotency_key`, `progress_cid`, optional `committed_side_effects[]`,
optional `obligation_cids[]`, optional `state_transition_cids[]`.

**Result (`CheckpointResult`):** `checkpoint_id`, `journal_seq`, optional
`event_cid`.

Rules:

1. Checkpoint is the fence before further externally visible work continues.
2. Each entry in `committed_side_effects` **MUST** carry an `idempotency_key`
   and **MUST NOT** be re-applied after a successful journal commit for that key.
3. Checkpoint **MUST** be transactional with respect to the journal adapter
   (all-or-nothing append of the journal record).

### 5.6 `retry`

**Request (`RetryRequest`):** `execution_id`, optional `fencing_token`,
optional `reason`, optional `max_attempts`, optional `idempotency_key`.

**Result (`RetryResult`):** `attempt`, `journal_seq`, `status`, optional
`event_cid`.

Rules:

1. Retry is an in-policy re-attempt under journal control.
2. A successful in-memory retry **MUST NOT** be claimed as crash recovery
   (ADR-0005 / gate 17).
3. Retry **MUST NOT** re-commit side effects already journaled as committed.

### 5.7 `timer` (durable)

**Request (`TimerRequest`):** `execution_id`, `timer_id`, either `fire_at_ms`
or `delay_ms`, optional `payload_cid`, optional `fencing_token`,
`durable: true` (const for this interface).

**Result (`TimerResult`):** `timer_id`, `fire_at_ms`, `journal_seq`,
`status` of timer (`scheduled` \| `fired` \| `cancelled`), optional `event_cid`.

Rules:

1. Durable timers **MUST** survive process death when the journal records them.
2. Timer fire after restart **MUST** be idempotent for the same `timer_id`.
3. Cancel of the parent execution **MUST** cancel outstanding durable timers
   or fail closed on fire.

### 5.8 `compensation`

**Request (`CompensationRequest`):** `execution_id`, `target_effect_ids[]` or
`target_effect_cids[]`, optional `compensation_plan_cid`, optional
`fencing_token`, `idempotency_key`.

**Result (`CompensationResult`):** `compensation_id`, `status`
(`compensating` \| `compensated` \| `failed`), `journal_seq`, optional
`event_cid`.

Rules:

1. Compensation applies only to effects previously journaled as committed and
   marked compensatable.
2. Compensation outcomes **MUST** be journaled; partial compensation **MUST**
   remain inspectable.

### 5.9 `inspect`

**Request (`InspectRequest`):** `execution_id` and/or `correlation_id`,
optional `include_journal` (boolean), optional `include_timers`.

**Result (`InspectResult`):** `status`, `fencing_token`, `last_checkpoint_id`,
`journal_frontier_seq`, `cancel_state`, `obligation_cids[]`, `timers[]`,
optional `journal_records[]`, optional `receipt_cid`.

Rules:

1. `inspect` is read-only and **MUST NOT** advance fencing epochs.
2. Evidence bundles **SHOULD** use `inspect` snapshots plus journal CIDs.

### 5.10 `recover`

**Request (`RecoverRequest`):** optional `execution_id` (omit to scan adapter
recovery set), required `fencing_token` for exclusive recover of a specific
execution (or `claim_new_fencing_token: true` to advance epoch), optional
`after_kill: true`.

**Result (`RecoverResult`):** `recovered[]` entries (`execution_id`,
`status`, `last_checkpoint_id`, `journal_seq`), `rejected_stale[]`,
`crash_recovery_receipt` (`CrashRecoveryReceipt@1`).

Rules:

1. Recover **MUST** reconstruct runnable state solely from durable journal
   records (and referenced CIDs), not from process memory.
2. Stale fencing tokens **MUST** be rejected and listed in `rejected_stale`.
3. Recover **MUST NOT** re-apply side effects whose journal records already
   mark them committed.
4. A successful recover **MUST** mint or update a `CrashRecoveryReceipt@1`
   suitable for gate-17 evidence.

### 5.11 `finalize`

**Request (`FinalizeRequest`):** `execution_id`, `fencing_token`,
`terminal_status`, `result_cid` (CID of `ExecutionResult@1`), optional
`receipt_cid` (pre-minted), optional `output_cids[]`, `idempotency_key`,
optional `sign_receipt` (boolean, default true for cross-trust).

**Result (`FinalizeResult`):** `terminal_status`, `result_cid`, `receipt_cid`,
`event_cid`, `journal_seq`, `signature_present` boolean.

Rules (final outputs bind to signed receipts):

1. `finalize` is the only method that transitions to a success/failure terminal
   status with portable outputs.
2. `result_cid` **MUST** reference an `ExecutionResult@1` whose `envelope_cid`
   matches the execution’s start envelope.
3. The executor **MUST** bind final outputs through an `ExecutionReceipt@1`:
   - `receipt.envelope_cid` = start envelope CID
   - `receipt.result_cid` = `result_cid`
   - `receipt.output_cids` **MUST** equal the result’s output set (and the
     request’s `output_cids` when provided)
   - `receipt.status` **MUST** equal `terminal_status` / result status
   - Cross-trust-domain finalization **MUST** set a non-null `signature`
     (plan gate 15 / receipt-signed conformance)
4. The journaled finalize transition **MUST** record `receipt_cid` and
   **SHOULD** emit an Event DAG event with `event_type: "receipt"`.
5. After successful finalize, mutating methods **MUST** fail closed.

---

## 6. Journal records (`DurableJournalRecord@1`)

Each journaled transition is an append-only record:

| Field | Required | Notes |
| --- | --- | --- |
| `schema` | yes | `mcp++/durable/journal-record@1` |
| `execution_id` | yes | Durable execution identity |
| `journal_seq` | yes | Monotonic per execution, starting at 1 |
| `transition` | yes | Closed transition kind (see §7) |
| `idempotency_key` | conditional | Required for externally visible commits |
| `fencing_token` | yes | Epoch that authored the record |
| `envelope_cid` | yes | Start envelope |
| `checkpoint_id` | no | When transition is checkpoint-related |
| `progress_cid` | no | Progress document CID |
| `side_effects` | no | Committed / compensated effect descriptors |
| `result_cid` / `receipt_cid` | no | Finalize bindings |
| `parents` | yes | Prior journal record CIDs or empty for root |
| `created_at_ms` | yes | Informational wall-clock |
| `event_cid` | no | Linked Event DAG node when published |
| `payload_cid` | no | Additional typed payload |
| `canonicalization` | yes on new mints | `mcpp-jcs-v1` |

The journal is the **authority** for:

- whether a side effect is committed,
- cancel and timer persistence,
- fencing epoch and exclusive recover,
- last checkpoint for resume.

Adapters **MUST** commit journal records with durability suitable for
kill-restart tests (SQLite WAL or equivalent documented mode for the mandatory
adapter).

---

## 7. Journal transitions → Event DAG events

Journaled transitions **map** to Profile F Event DAG events. The journal remains
the recovery authority; the DAG is the portable causal history.

### 7.1 Transition catalog

| `transition` | When journaled | Canonical Event DAG `event_type` | Typical payload refs |
| --- | --- | --- | --- |
| `started` | `start` accepts | `envelope` | `envelope_cid`, `execution_id` |
| `resumed` | `resume` continues work | `invocation` | `execution_id`, `checkpoint_id` |
| `signalled` | `signal` accepted | `intent` | `signal_name`, `payload_cid` |
| `cancel_requested` | `cancel` accepted (non-terminal) | `error` | `reason` |
| `cancelled` | cancel reaches terminal | `result` | `status=cancelled` |
| `checkpointed` | `checkpoint` commits | `decision` | `progress_cid`, `checkpoint_id` |
| `side_effect_committed` | checkpoint / step commits effect | `result` | `effect_cid`, `idempotency_key` |
| `retried` | `retry` accepted | `invocation` | `attempt`, `reason` |
| `timer_scheduled` | `timer` scheduled | `intent` | `timer_id`, `fire_at_ms` |
| `timer_fired` | durable timer fires | `invocation` | `timer_id` |
| `timer_cancelled` | timer cancelled | `error` | `timer_id` |
| `compensation_started` | `compensation` begins | `intent` | `compensation_id` |
| `compensation_completed` | compensation terminal | `result` | `status=compensated` |
| `recovered` | `recover` reconstructs | `envelope` | crash-recovery receipt CID |
| `finalized` | `finalize` binds receipt | `receipt` | `receipt_cid`, `result_cid` |

Implementations **MAY** add adapter-local transition names only if they also
declare a mapping into the table above for portable Event DAG publication.
Unknown transitions **MUST NOT** be published as Profile F events without a
mapping.

### 7.2 Emission rules

1. Every **externally visible** journal commit **SHOULD** emit an Event DAG
   node with `parents` linking prior event CIDs for the same execution (and
   envelope parents when starting).
2. The journal record’s `event_cid` **MUST** equal the minted event when an
   event is published for that transition.
3. Event payload **MUST** reference journal identity (`execution_id`,
   `journal_seq` or `journal_record_cid`) so auditors can reconcile DAG and
   journal without treating validators as the journal store.
4. Wall-clock event timestamps are informational; causal order **MUST** come
   from `parents` (Profile F).
5. Missing Event DAG emission **MUST NOT** roll back a successful journal
   commit; evidence bundles **MAY** treat missing `event_cid` as incomplete
   provenance but still valid crash recovery.

### 7.3 Example mapping (`checkpointed`)

```json
{
  "schema": "mcp++/durable/journal-record@1",
  "execution_id": "dexec_01HZX…",
  "journal_seq": 4,
  "transition": "checkpointed",
  "idempotency_key": "step-2-commit",
  "fencing_token": 1,
  "envelope_cid": "bafkrei…envelope",
  "checkpoint_id": "cp_4",
  "progress_cid": "bafkrei…progress",
  "parents": ["bafkrei…journal-3"],
  "created_at_ms": 1783872060000,
  "event_cid": "bafkrei…event-4",
  "canonicalization": "mcpp-jcs-v1"
}
```

Corresponding Event DAG node (conceptual):

```json
{
  "event_type": "decision",
  "parents": ["bafkrei…event-3"],
  "payload": {
    "execution_id": "dexec_01HZX…",
    "journal_seq": 4,
    "journal_record_cid": "bafkrei…journal-4",
    "transition": "checkpointed",
    "progress_cid": "bafkrei…progress",
    "checkpoint_id": "cp_4"
  }
}
```

---

## 8. Final outputs and signed receipts

Final outputs of a durable execution **MUST** bind to an `ExecutionReceipt@1`
(see execution-envelope family).

| Binding | Rule |
| --- | --- |
| Envelope | Receipt `envelope_cid` = journal root envelope |
| Result | Receipt `result_cid` = finalize `result_cid` |
| Outputs | Receipt `output_cids` = result outputs; no silent drop or add |
| Status | Receipt `status` matches terminal execution status |
| Signature | Cross-trust finalize **MUST** sign; same-trust **MAY** omit with explicit local policy |
| Event DAG | Receipt `event_cid` / finalize journal `event_cid` link the receipt node |
| Journal | Finalize journal record stores `receipt_cid` |

`CrashRecoveryReceipt@1` is **not** a substitute for `ExecutionReceipt@1`.
Crash-recovery receipts attest recover safety; execution receipts attest
terminal work products.

### 8.1 `CrashRecoveryReceipt@1` fields

| Field | Notes |
| --- | --- |
| `schema` | `mcp++/durable/crash-recovery-receipt@1` |
| `adapter_id` | e.g. `duckdb-quack-journal@1` (primary) or `sqlite-journal@1` (fallback) |
| `recovered_at_ms` | Wall-clock of recover |
| `execution_ids` | Recovered set |
| `journal_frontier` | Map or list of `execution_id` → `journal_seq` |
| `rejected_stale_fencing_tokens` | Stale claims rejected |
| `side_effects_not_replayed` | Idempotency keys of committed effects skipped on recover |
| `receipt_cid` | Optional self-CID after content addressing |
| `signature` | Optional adapter/operator signature over the receipt |

---

## 9. Fail-closed rules

| Condition | Required behavior |
| --- | --- |
| Missing journal durability on a path claiming crash-safe resume | Reject / fail closed |
| Stale `fencing_token` on resume, checkpoint, recover, finalize | Reject |
| Retry or recover of already-committed `idempotency_key` side effect | Skip re-apply; return prior commit identity |
| Mutating call after terminal status | Reject |
| Unknown `execution_id` | Reject |
| Finalize without `result_cid` / receipt binding | Reject |
| Cross-trust finalize without receipt signature | Reject at receipt-signed conformance |
| Second adapter without local compose (Restate/Dapr/etc.) | Must not claim MCP++ 1.0 mandatory durable conformance |

---

## 10. Adapter requirements

### 10.1 Primary: DuckDB / Quack journaled executor

Per ADR-0005 (2026-08-16 correction):

- Package target: `ipfs_accelerate_py/mcp_server/mcplusplus/durable/`
  (`sqlite_executor.py`, `journal.py`) plus
  `ipfs_accelerate_py/mcp_server/mcplusplus/storage/engine.py`.
- Engine default is DuckDB. Quack and DuckLake are loaded with local `LOAD`
  only (never network `INSTALL`). SQLite is an explicit fallback.
- Crash recovery demonstrable locally (process kill → restart → resume).
- Transactional journal append (DuckDB checkpoint on close; SQLite WAL fallback).
- Idempotency keys, cancel/obligation persistence, stale fence rejection.

### 10.2 Optional second adapters

Restate, Dapr, or other engines **MAY** implement `DurableExecutor@1` only when:

1. This interface and the DuckDB/Quack adapter exist,
2. Repeatable local compose is checked in and runs without unpaid cloud,
3. Contract tests prove the same crash-recovery properties.

### 10.3 Accelerate binding

`MCPP-053` binds accelerate task dispatch so `start` / `resume` / `cancel`
flow through `DurableExecutor@1` and journaled transitions may emit Event DAG
events. Accelerate **MUST NOT** expose a competing public task lifecycle
(KD-13).

---

## 11. Conformance and evidence

| Level (ADR-0003) | What counts |
| --- | --- |
| `structural` | Requests/results/journal records validate against the schema |
| `canonical` | Journal and receipt CIDs use `mcpp-jcs-v1` |
| `cryptographic` | Receipt signatures verify (Ed25519) |
| `policy-enforced` | Cancel and obligations survive restart under accepted policy |
| `receipt-signed` | Finalize binds signed `ExecutionReceipt@1` |
| `proof-verified` | Out of scope for mandatory durable adapter (Profile F ZK separate) |

Gate 17 / REQ-DUR-01 close only when an adapter passes crash recovery without
duplicate committed side effects (`MCPP-052`), not when this document alone
exists.

Suggested validation path for this interface task:

```bash
test -s ipfs_accelerate_py/mcplusplus/docs/architecture/durable-execution.md
python -m json.tool ipfs_accelerate_py/mcplusplus/schemas/durable/durable-executor-1.schema.json > /dev/null
```

Downstream:

```bash
python -m pytest -q test/api/test_mcplusplus_durable_sqlite.py
cd ipfs_accelerate_py && python -m pytest -q test/api/test_mcplusplus_durable_crash_recovery.py
```

---

## 12. Interface checklist (`DurableExecutor@1`)

A reader may treat the following as the interface label **`DurableExecutor@1`**:

1. Eleven methods exist with typed request/result pairs in schema and prose.
2. Journaled transitions use `DurableJournalRecord@1` and map to Event DAG
   `event_type` values per §7.
3. `finalize` binds final outputs to `ExecutionReceipt@1` (signed for
   cross-trust).
4. `recover` emits `CrashRecoveryReceipt@1` and rejects stale fencing tokens.
5. Journal is recovery authority; Event DAG is provenance; StateProvider is
   state modes — not interchangeable.
6. Primary adapter path remains DuckDB/Quack journaled executor (ADR-0005).
7. In-memory retry is not crash recovery.

---

## 13. Downstream task map

| Concern | Task |
| --- | --- |
| This interface + schema | MCPP-050 (this document) |
| DuckDB/Quack journaled adapter | MCPP-051 |
| Crash-recovery integration test (gate 17) | MCPP-052 |
| Accelerate runtime bind | MCPP-053 |
| Optional Restate/Dapr adapters | Follow-on; non-blocking |

---

## 14. References

- ADR-0005: `docs/architecture/decisions/0005-durable-executor.md`
- Execution envelope family: `docs/spec/execution-envelope.md`
- Event DAG: `docs/spec/event-dag-ordering.md`
- StateRef: `docs/spec/state-ref.md`
- Schema: `schemas/durable/durable-executor-1.schema.json`
- Sealed plan KD-12 / gate 17: `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md`
- Traceability REQ-DUR-01: `docs/roadmap/mcplusplus-1.0-gap-closure.md`
- Architecture overview (bundles): [overview.md](overview.md)
- State model: [state-model.md](state-model.md)
- Trust boundaries: [trust-boundaries.md](trust-boundaries.md)
- Threat model: [threat-model.md](threat-model.md)

---

## 15. Profile-bundle relevance (KD-17)

Durable execution is **cross-cutting**. It is not itself one of the five profile
bundles, but it **supports** honest packaging:

| Bundle | Relationship to DurableExecutor@1 |
| --- | --- |
| **Evidence Core** (A, B, F) | Journaled transitions **MAY** emit Event DAG events; finalize binds Envelope/Result/Receipt lineage |
| **Secure Delegation** (C, D) | `start` / portable envelopes **MUST** fail closed without required authority proofs; cancel and obligations survive restart when journaled |
| **Federated Mesh** (E, G) | Transport identity **MUST NOT** grant resume rights; fencing aligns with exclusive-task rejection of stale completions |
| **Commerce** (H) | Payment settlement **MUST NOT** substitute for durable resume authority or UCAN/policy allow |
| **Verified Execution** | Cross-trust `finalize` **MUST** bind signed `ExecutionReceipt@1` when claiming `receipt-signed`; crash-recovery receipts are not substitutes for execution receipts |

---

## 16. Migration (operator guidance)

**Authority class: non-normative.**

| From | To | Notes |
| --- | --- | --- |
| In-process retry loops | `DurableExecutor@1` + DuckDB/Quack journal | In-memory success is not crash recovery |
| Custom workflow SaaS as sole path | DuckDB/Quack primary adapter first | Restate/Dapr only with local compose (ADR-0005 §5) |
| Event DAG append as “commit” | Journal commit + optional DAG publish | DAG is provenance; journal is recovery authority |
| State CAS as step fence only | Explicit journal checkpoint + idempotency keys | State modes remain ADR-0004 |
| PeerID-gated resume | Fencing token + journal ownership | KD-14 |
| Unsigned cross-trust finalize | Signed `ExecutionReceipt@1` | Required for Verified Execution / `receipt-signed` claims |

Suggested rollout: (1) validate envelopes structurally, (2) wire DuckDB/Quack
journal for start/checkpoint/recover, (3) prove kill-restart without duplicate
side effects, (4) only then advertise crash-safe resume in evidence bundles.

---

## 17. Explicit non-claims

This chapter **does not** claim:

- That gate 17 is closed without adapter crash-recovery evidence.
- That Restate or Dapr are mandatory.
- That schema acceptance equals implemented durability.
- That deployments have empty residual risk or meet every ADR-0003 level.

G170 documentation policy forbids over-claim language that asserts unproven
deployment fitness, empty residual risk, universal conformance, or unverified
proof strength. Prefer named conformance levels and test commands.

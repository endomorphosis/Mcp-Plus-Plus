# Execution Envelope Family (ExecutionEnvelope@1)

**Status:** Normative (MCP++ 1.0)  
**Interfaces:** `ExecutionEnvelope@1`, `ExecutionResult@1`, `ExecutionReceipt@1`, `PortableError@1`  
**Schemas:**

| Interface | Schema path | Schema marker |
| --- | --- | --- |
| `ExecutionEnvelope@1` | `schemas/execution/execution-envelope-1.schema.json` | `mcp++/execution/envelope@1` |
| `ExecutionResult@1` | `schemas/execution/execution-result-1.schema.json` | `mcp++/execution/result@1` |
| `ExecutionReceipt@1` | `schemas/execution/execution-receipt-1.schema.json` | `mcp++/execution/receipt@1` |
| `PortableError@1` | `schemas/execution/portable-error-1.schema.json` | `mcp++/execution/portable-error@1` |

**Authority:** Plan KD-7; goal `MCPP-G050`; tasks `MCPP-030`…`MCPP-034`.  
**Related:** [cid-native-artifacts.md](cid-native-artifacts.md) (Profile B), [ucan-delegation.md](ucan-delegation.md) (C), [temporal-deontic-policy.md](temporal-deontic-policy.md) (D), [event-dag-ordering.md](event-dag-ordering.md) (F), [risk-scheduling.md](risk-scheduling.md) (G), ADR-0002 (crypto), ADR-0003 (conformance levels).

Normative keywords **MUST**, **SHOULD**, and **MAY** are used as described in RFC 2119.

---

## 1. Purpose

MCP++ profiles historically overlapped execution semantics: Profile B defined
CID-native envelopes and receipts; Profile G defined task receipts; Profile C/D
attached proofs and decisions; Profile F linked event nodes. Those modules remain
valid modular contents.

This chapter defines **one canonical portable carrier family** so peers exchange
a single top-level shape:

1. **ExecutionEnvelope@1** — what is authorized to run (request).
2. **ExecutionResult@1** — attempt-scoped outcome.
3. **ExecutionReceipt@1** — content-addressed attestation of a result.
4. **PortableError@1** — portable failure description.

Adapters map existing Profile B and G artifacts into this family **without
silent CID breakage** (historical bytes and CIDs remain readable under their
recorded algorithms).

Schema acceptance is **structural** only (ADR-0003). Signing, attenuation,
policy enforcement, and proof verification are higher conformance levels.

---

## 2. Lifecycle

```text
  requester                     executor                      Event DAG
      |                             |                              |
      |-- ExecutionEnvelope@1 ----->|                              |
      |   (identity, authority,     |                              |
      |    intent, IO, constraints, |                              |
      |    state, policy, parents)  |                              |
      |                             |-- evaluate C/D proofs ------>|
      |                             |-- execute under DurableExec  |
      |                             |-- ExecutionResult@1          |
      |                             |-- ExecutionReceipt@1 -------->|
      |<----- receipt / error ------|   (event_cid, signature)     |
```

1. A requester mints an **ExecutionEnvelope@1** (or adapts a historical B envelope).
2. The executor validates authority (Profile C) and policy (Profile D) at
   execution time. Transport PeerID / TLS client cert **MUST NOT** grant UCAN
   capabilities (KD-14). Payment **MUST NOT** grant authorization (KD-14).
3. The executor produces an **ExecutionResult@1** for the attempt.
4. The executor mints an **ExecutionReceipt@1** that binds envelope + result,
   optionally signs it, and publishes an Event DAG node (`event_cid`).
5. On failure, `error` carries a **PortableError@1** (or `null` on success).

Wall-clock timestamps (`created_at_ms`, `started_at_ms`, `finished_at_ms`) are
**informational**. Causal order **MUST** come from `parents` and logical clocks /
Event DAG links, not from wall-clock comparison alone.

---

## 3. Shared primitives

### 3.1 Schema marker

Every object in this family **MUST** include a `schema` string equal to its
closed marker (table above). Unknown or mismatched markers **MUST** fail
structural validation for that interface.

### 3.2 CIDs

CID fields **MUST** match:

```
^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58,})$
```

New mints **SHOULD** use CIDv1 (`raw` + `sha2-256` unless an existing artifact
already declares another multicodec) under `mcpp-jcs-v1` canonicalization
(ADR-0002, KD-4/KD-5). Historical CIDv0 (`Qm…`) and longer CIDv1 forms remain
readable.

### 3.3 Identities

Principal identities **MUST** be DID-compatible (`did:…`). Executor and
requester objects **MAY** carry `key_id` and optional transport `peer_id`.
`peer_id` is observational only.

### 3.4 Canonicalization

When an object is content-addressed or signed, new mints **MUST** declare
`canonicalization: "mcpp-jcs-v1"` (RFC 8785 JCS). Signature input **MUST** be
the canonical UTF-8 bytes of the object with the `signature` field omitted (or
null) and object keys ordered per JCS.

---

## 4. ExecutionEnvelope@1

The envelope is the top-level **request carrier**. Profiles B/C/D/F/G remain
modular: the envelope holds CID references (and small inline constraints), not
re-encoded profile documents.

### 4.1 Coverage map

| Concern | Fields |
| --- | --- |
| **Identity** | `schema`, `interface_cid`, `method`, `requester`, `audience` |
| **Authority** | `authority.proof_cids`, `authority.proof_cid`, `authority.delegation_cids`, `authority.resource`, `authority.ability` |
| **Intent** | `intent_cid` |
| **Inputs / outputs** | `input_cid`, `expected_output_schema_cid` |
| **Constraints** | `constraints`, `constraints_cid`, `deadline_ms`, `declared_side_effects` |
| **State** | `state_refs[]` (`state_ref_cid`, optional `mode`, `access`) |
| **Policy** | `policy_cid`, `decision_cid` |
| **Provenance** | `parents[]`, `created_at_ms`, `correlation_id`, `nonce`, `metadata_cid`, optional `profile_b_envelope_cid` |

### 4.2 Required fields

| Field | Type | Notes |
| --- | --- | --- |
| `schema` | const | `mcp++/execution/envelope@1` |
| `interface_cid` | CID | Profile A interface |
| `input_cid` | CID | Canonical input |
| `intent_cid` | CID | Plan-to-act object |
| `parents` | CID[] | Causal parents; may be empty |
| `created_at_ms` | int | Wall-clock ms |
| `correlation_id` | string | Observability hook |
| `requester` | object | `{ did, key_id?, peer_id? }` |
| `authority` | object | At least `proof_cids` (array; may be empty only for non-portable local trust) |

### 4.3 Authority rules

- Invocations that claim **portable / cross-trust** authority **MUST** supply at
  least one proof in `authority.proof_cids` or `authority.proof_cid`.
- Executors **MUST** validate proofs at execution time (Profile C), not only at
  session open.
- Empty `proof_cids` is permitted only for same-trust-domain local execution that
  does **not** claim portable authority on the wire.

### 4.4 State handles

Each `state_refs[]` entry references a future `StateRef@1` (or historical handle)
by CID. When `mode` is present it **MUST** be exactly one of
`immutable`, `single_authority`, `causal`, `crdt`, `consensus` (KD-8) and **MUST**
match the referenced StateRef.

### 4.5 Minimal example

```json
{
  "schema": "mcp++/execution/envelope@1",
  "interface_cid": "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
  "method": "repo.status",
  "input_cid": "bafkreihtwdlu4jntm7yl2mgsfzqgr4on37vr7inuld2dql2p4rmqafybti",
  "intent_cid": "bafkreicssskybdf32rmzlbtge5bxyv4v6c6eac322pbrsr3azlb4fkxiqi",
  "policy_cid": "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku",
  "parents": [],
  "created_at_ms": 1783872000000,
  "correlation_id": "task-001",
  "requester": { "did": "did:key:z6MkrequesterExample" },
  "authority": {
    "proof_cids": ["bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"],
    "proof_cid": "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"
  },
  "constraints": { "timeout_ms": 30000, "max_retries": 3 },
  "state_refs": [],
  "canonicalization": "mcpp-jcs-v1"
}
```

---

## 5. ExecutionResult@1

An **ExecutionResult@1** records one attempt against an envelope. It is
attempt-scoped and may be unsigned. Durable executors **MAY** retain multiple
results (one per attempt); the receipt attests the chosen terminal result.

### 5.1 Required outcome fields

Results **MUST** include (nullable where noted):

| Field | Notes |
| --- | --- |
| `status` | `succeeded` \| `failed` \| `cancelled` \| `rejected` \| `timed_out` \| `compensated` |
| `output_cids` | Array of output CIDs (empty when none published) |
| `state_transitions` | Array of state transition records |
| `side_effects` | Array of observed side-effect records |
| `decision_cid` | Policy decision CID or `null` |
| `delegation_cid` | Effective delegation CID or `null` |
| `executor` | `{ did, key_id?, runtime?, runtime_version?, peer_id? }` |
| `retry` | `{ attempt, max_attempts?, previous_result_cid?, reason? }` |
| `duration_ms` | Non-negative duration |
| `error` | `PortableError@1` or `null` (null on success) |
| `proofs` | Proof CIDs checked or emitted |
| `envelope_cid` | Envelope this result answers |
| `started_at_ms` / `finished_at_ms` | Wall-clock bounds |

Optional but defined: `signature`, `signature_alg`, `event_cid`,
`primary_output_cid`, `proof_cid`, `resource_use_cid`, `correlation_id`,
`canonicalization`.

### 5.2 Status vs error

- On `status: "succeeded"`, `error` **MUST** be `null` and `output_cids` **SHOULD**
  be non-empty when the method produces outputs.
- On any non-success status, `error` **SHOULD** be a `PortableError@1` with a
  stable `code` and matching `failure_class` / `retryable` flags.

### 5.3 State transitions and side effects

Each **state transition** includes at least `state_ref_cid` and **MAY** include
`mode`, `from_version`, `to_version`, `transition_cid`, and `op`
(`read` \| `write` \| `cas` \| `merge` \| `lease` \| `fence`).

Each **side effect** includes at least `kind` and **MAY** include `effect_cid`,
`description`, and `compensatable`. Side-effect descriptions **MUST NOT** embed
secrets or confidential plaintext.

---

## 6. ExecutionReceipt@1

An **ExecutionReceipt@1** is the immutable attestation suitable for audit,
disputes, cross-trust verification, and Event DAG linkage.

### 6.1 Required fields

Receipts **MUST** include every result outcome field listed in §5.1, plus:

| Field | Notes |
| --- | --- |
| `result_cid` | CID of the attested `ExecutionResult@1` |
| `signature` | Signature string or `null` (null only same-trust) |
| `event_cid` | Event DAG node CID or `null` before mint |

Also defined: `receipt_cid` (self-address after content addressing),
`signature_alg`, `policy_cid`, `parents`, `canonicalization`, and adapter
fields `profile_b_receipt_cid` / `profile_g_task_receipt_cid`.

### 6.2 Signing and cross-trust

- Receipts **MUST** be content-addressed.
- Cross-trust-domain receipts **MUST** be signed with Ed25519 over
  `mcpp-jcs-v1` canonical bytes and independently verifiable (plan gate 15).
- Same-trust-domain receipts **MAY** omit `signature` (`null`).
- Structural validators **MUST NOT** treat presence of `signature` as
  cryptographic proof (ADR-0003: `structural` ≠ `receipt-signed`).

### 6.3 Event linkage

When a receipt is published into Profile F, `event_cid` **SHOULD** identify the
event node that links `envelope_cid`, `result_cid` / `output_cids`,
`decision_cid`, and `receipt_cid` (or their equivalents) into the DAG.

### 6.4 Minimal success receipt (shape)

```json
{
  "schema": "mcp++/execution/receipt@1",
  "envelope_cid": "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
  "result_cid": "bafkreihtwdlu4jntm7yl2mgsfzqgr4on37vr7inuld2dql2p4rmqafybti",
  "status": "succeeded",
  "output_cids": ["bafkreicssskybdf32rmzlbtge5bxyv4v6c6eac322pbrsr3azlb4fkxiqi"],
  "state_transitions": [],
  "side_effects": [],
  "decision_cid": "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku",
  "delegation_cid": "bafkreifvvgbz4eh6tfl5s4n3y2m1k0j9h8g7f6e5d4c3b2a1z0y9x8w7v6u",
  "executor": {
    "did": "did:key:z6MkexecutorExample",
    "runtime": "ipfs_accelerate_py",
    "runtime_version": "3.2.0"
  },
  "retry": { "attempt": 1 },
  "duration_ms": 12.5,
  "error": null,
  "proofs": ["bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"],
  "signature": null,
  "signature_alg": null,
  "event_cid": "bafkreieventnodeexample0123456789abcdefghijklmnopqrs",
  "started_at_ms": 1783872001100,
  "finished_at_ms": 1783872001113,
  "canonicalization": "mcpp-jcs-v1"
}
```

*(Example CIDs are illustrative; real values must satisfy the CID pattern and
content-address their payloads.)*

---

## 7. PortableError@1

`PortableError@1` is the only normative error object for this family.

| Field | Required | Notes |
| --- | --- | --- |
| `schema` | yes | `mcp++/execution/portable-error@1` |
| `code` | yes | Stable machine code (`E_…`) |
| `message` | yes | Human summary; no secrets |
| `retryable` | yes | Whether retry is permitted |
| `failure_class` | yes | See §7.1 |
| `path` | no | JSON Pointer into envelope/input |
| `details_cid` | no | Structured details blob |
| `cause_cids` | no | Prior error CIDs |
| `rpc_code` / `http_status` | no | Transport mappings |
| `observed_at_ms` / `correlation_id` | no | Observability |

### 7.1 Failure classes

| Class | Meaning |
| --- | --- |
| `none` | Not a failure (reserved; usually unused on error objects) |
| `retryable` | Transient fault; safe to retry under policy |
| `permanent` | Will not succeed without changing inputs/envelope |
| `policy` | Profile D denial |
| `authority` | Profile C / UCAN denial |
| `fenced` | Stale fence / exclusive claim loss (Profile G) |
| `resource` | Quota / budget / capacity |
| `cancelled` | Caller or system cancellation |
| `timeout` | Deadline / timeout exceeded |
| `internal` | Executor internal fault |

`failure_class` aligns with Profile G `TaskReceipt.failure_class` and extends it
with portable `cancelled` / `timeout` / `internal` values.

---

## 8. Relationship to existing profiles

| Profile | Relationship |
| --- | --- |
| **A (IDL)** | `interface_cid` points at Interface Descriptor |
| **B (CID artifacts)** | Intent/decision/receipt builders remain; adapters map to Envelope@1 / Receipt@1 without rewriting historical CIDs (`profile_b_*_cid` fields) |
| **C (UCAN)** | `authority.proof_cids` / `delegation_cid` / `proofs` |
| **D (Policy)** | `policy_cid` / `decision_cid` |
| **F (Event DAG)** | `event_cid`, `parents` |
| **G (Risk/scheduling)** | Task receipts adapt via `profile_g_task_receipt_cid`; status/attempt/resource fields map into Result/Receipt |
| **H (Payments)** | Payment success never authorizes an envelope (KD-14); AccessReceipt remains commercial evidence only |

Adapters (MCPP-031, MCPP-032) **MUST NOT** mutate historical fixtures. They
produce Envelope@1 / Receipt@1 views that reference original CIDs.

---

## 9. Conformance levels (ADR-0003)

| Level | Meaning for this family |
| --- | --- |
| `structural` | JSON Schema validation of markers and fields |
| `canonical` | Identical JCS bytes / digest / CID across languages |
| `cryptographic` | Real Ed25519 verify of authority proofs |
| `policy-enforced` | Decision matches current policy evaluation |
| `receipt-signed` | Receipt signature verifies over canonical bytes |
| `proof-verified` | Attached proofs / ZK / witnesses verify |

A schema that accepts a `signature` field is **not** “implemented”
cryptography.

---

## 10. Security considerations

1. **Fail closed** on missing authority for portable claims, expired proofs,
   expanded capabilities, audience mismatch, and stale fences.
2. **Do not** treat transport identity or payment as execution authority.
3. **Do not** put confidential plaintext into envelope metadata, errors, Event
   DAG metadata, or logs (KD-15).
4. **Idempotency:** durable executors **MUST** use `constraints.idempotency_key`
   (or equivalent journal keys) so crash recovery does not duplicate committed
   side effects.
5. **Retry:** only when `PortableError.retryable` is true and the effect model
   permits; in-memory retry is not crash recovery (ADR-0005).

---

## 11. Validation

Structural validation of the schema documents:

```bash
python -m json.tool ipfs_accelerate_py/mcplusplus/schemas/execution/execution-envelope-1.schema.json > /dev/null
python -m json.tool ipfs_accelerate_py/mcplusplus/schemas/execution/execution-result-1.schema.json > /dev/null
python -m json.tool ipfs_accelerate_py/mcplusplus/schemas/execution/execution-receipt-1.schema.json > /dev/null
python -m json.tool ipfs_accelerate_py/mcplusplus/schemas/execution/portable-error-1.schema.json > /dev/null
```

Four-language vectors, Profile B/G adapters, and accelerate emission are covered
by follow-on tasks (`MCPP-031`…`MCPP-034`), not by this schema chapter alone.

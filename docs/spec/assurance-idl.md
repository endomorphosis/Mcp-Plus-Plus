# Assurance IDL — OperationSpec@1

**Status:** Normative (Assurance IDL operation contract)
**Release:** `formal-claim-algebra-v1`
**Schema:** `facp/operation-spec@1`
**Owning task:** FACP-032
**Goal:** FACP-G310 (Canonical Contract Compiler)
**Authority:** MCP++ Assurance IDL; extends Profile A MCP-IDL with closed assurance fields
**Companion schemas:** `facp/evidence-envelope@1`, `facp/formal-claim-algebra-v1@1`

This specification defines **OperationSpec@1**: the versioned, closed, bounded
machine-readable contract for every migrated effectful (and pure) operation in
the Formal Assurance Control Plane (FACP). It extends MCP-IDL interface
descriptors with assurance obligations without introducing a new MCP++ profile.

Later tasks compile this IDL into codecs, bindings, AdmissionToken,
EffectReceipt, and cross-language identity (FACP-033+). This document does
**not** claim Lean-checked proofs or byte-identical CID agreement.

## 1. Goals

- Provide one **closed operation contract** that can describe all four-path
  migrated operations (Datasets, Accelerate, Kit, SwissKnife presentation).
- Make authority, policy, confirmation, lease, observation, evidence, and
  outcomes **enumerated**, never free-form strings or boolean `success`.
- Bound every string, array, and resource limit; reject floats on
  security-critical numeric fields.
- Remain compatible with MCP-IDL discovery: OperationSpec complements Interface
  Descriptors; it does not replace baseline MCP messages.
- Fail closed on unknown fields, unknown enum spellings, and missing required
  dimensions of the contract.

## 2. Relationship to MCP-IDL

| Concern | MCP-IDL (Profile A) | Assurance IDL (this document) |
| --- | --- | --- |
| Discovery shape | Interface Descriptor methods/schemas | OperationSpec binds one operation identity |
| Compatibility | `interface_cid` set operations | Closed effect/obligation classes + CID schema refs |
| Authority | Explicitly non-authoritative descriptors | Closed `*_obligation` enums; no free-form authority |
| Outcomes | Method output schemas | Closed Formal Claim Algebra outcome algebra |
| Bounds | Optional resource hints | Required integer `resource_bounds` |

Descriptors remain **not authority**. OperationSpec declares which host-side
obligations the Effect Admission Kernel must satisfy before a handler may run.
Browser-authored `allow`, `consent`, `dry_run`, or confirmation tokens MUST NOT
appear as OperationSpec fields and MUST NOT satisfy any obligation enum.

## 3. Closure, bounds, and versioning

| Property | Normative meaning |
| --- | --- |
| **Versioned** | Every instance MUST set `schema` to `facp/operation-spec@1` and `schema_version` to integer `1`. |
| **Closed** | Only the properties and enum constructors listed here are admissible. Unknown fields fail closed (`additionalProperties` / `unevaluatedProperties` false). |
| **Bounded** | Strings, arrays, and integers carry finite `maxLength` / `maxItems` / `maximum` limits. |
| **No critical floats** | Resource bounds and versions are JSON integers. Floats are forbidden in normative numeric positions. |
| **No free-form authority** | Authority is only `authority_obligation` ∈ closed enum. |
| **No free-form outcomes** | Outcomes are only `allowed_outcomes[]` ⊆ closed Formal Claim Algebra outcome algebra. Boolean `success` is forbidden. |

Stable schema validation error codes include: `UNKNOWN_FIELD`, `MISSING_FIELD`,
`UNKNOWN_ENUM`, `INVALID_TYPE`, `FORBIDDEN_FLOAT`, `INVALID_CID`,
`FREE_FORM_AUTHORITY`, `FREE_FORM_OUTCOME`, `FORBIDDEN_SUCCESS_BOOLEAN`.

## 4. OperationSpec product

```text
OperationSpec {
  schema:                 "facp/operation-spec@1"
  schema_version:         1
  operation_id:           dotted stable id
  namespace:               owning package/repo namespace
  name:                   local operation name
  version:                positive integer
  input_schema_cid:       CIDv1
  output_schema_cid:      CIDv1
  error_codes[]:          bounded identifiers
  effect_class:           pure | read | write | process | credential |
                          install | repository | publish | payment |
                          private | legal | irreversible
  idempotency_class:      pure_idempotent | idempotent |
                          at_most_once | non_idempotent
  reversibility_class:    reversible | compensatable | irreversible
  authority_obligation:   none | actor_authenticated | capability_verified
  policy_obligation:      none | host_policy_required |
                          host_policy_with_obligations
  confirmation_obligation: none | one_use_confirmation_required
  lease_obligation:       none | lease_required
  observation_obligation: none | independent_observation_required |
                          delegated_observation_allowed
  evidence_class:         none | hermetic | conditional | live
  allowed_outcomes[]:     Unavailable | Rejected | Simulated | Attempted |
                          Unknown | Observed | Verified | Failed | Compensated
  resource_bounds:        integer size/time limits
}
```

Normative JSON Schema:
`Mcp-Plus-Plus/schemas/assurance/v1/operation-spec.schema.json`.

## 5. Field semantics

### 5.1 Identity and schemas

| Field | Meaning |
| --- | --- |
| `operation_id` | Stable dotted identity (for example `datasets.download`). MUST be unique within a compiled contract set. |
| `namespace` | Owning namespace (`ipfs_datasets_py`, `ipfs_accelerate_py`, `ipfs_kit_py`, `swissknife`, …). |
| `name` | Local name within the namespace. |
| `version` | Monotonic positive integer contract revision for this `operation_id`. |
| `input_schema_cid` / `output_schema_cid` | CIDv1 (lowercase multibase base32) of the closed input/output schemas. |
| `error_codes` | Bounded snake_case error identifiers for the operation surface. These are **not** outcome algebra values and MUST NOT encode authority grants. |

### 5.2 Effect, idempotency, and reversibility

| `effect_class` | Meaning |
| --- | --- |
| `pure` | No externally observable side effect; presentation/projection only. |
| `read` | Observes state without durable mutation. |
| `write` | Durable state mutation. |
| `process` | Spawns or controls an external process. |
| `credential` | Touches secrets or credential material. |
| `install` | Package/dependency installation. |
| `repository` | Repository mutation (commit, push, ref update). |
| `publish` | Publishes artifacts to an external audience. |
| `payment` | Payment or settlement effect. |
| `private` | Private/tenant-sensitive effect requiring stronger isolation. |
| `legal` | Rights/license/legal disposition effect. |
| `irreversible` | Effect class that cannot be undone even with compensation tooling. |

| `idempotency_class` | Meaning |
| --- | --- |
| `pure_idempotent` | Pure; retries are observationally identical. |
| `idempotent` | Same arguments yield the same durable effect. |
| `at_most_once` | Duplicate application is unsafe without fencing. |
| `non_idempotent` | Retries may multiply effects. |

| `reversibility_class` | Meaning |
| --- | --- |
| `reversible` | Effect can be undone by an inverse operation. |
| `compensatable` | Effect requires an explicit compensating action. |
| `irreversible` | No safe inverse or compensation; unknown outcomes must not blind-retry. |

### 5.3 Obligations (closed; not free-form authority)

Obligations declare what the host Effect Admission Kernel must establish. They
are **not** runtime authority decisions and MUST NOT accept free-form strings.

| Field | Closed constructors |
| --- | --- |
| `authority_obligation` | `none`, `actor_authenticated`, `capability_verified` |
| `policy_obligation` | `none`, `host_policy_required`, `host_policy_with_obligations` |
| `confirmation_obligation` | `none`, `one_use_confirmation_required` |
| `lease_obligation` | `none`, `lease_required` |
| `observation_obligation` | `none`, `independent_observation_required`, `delegated_observation_allowed` |

Payment, browser consent, UI confirmation tokens, and local policy objects do
**not** satisfy `authority_obligation` or `policy_obligation`.

### 5.4 Evidence class and allowed outcomes

| `evidence_class` | Meaning |
| --- | --- |
| `none` | No environment qualification required (pure projection). |
| `hermetic` | Hermetic evidence is sufficient. |
| `conditional` | Named host/capability gates required. |
| `live` | Live qualification required for production claims. |

`allowed_outcomes` MUST be a non-empty unique subset of the Formal Claim Algebra
closed outcome algebra:

`Unavailable | Rejected | Simulated | Attempted | Unknown | Observed | Verified | Failed | Compensated`

Generic `success: true` / `success: false` fields are forbidden on OperationSpec
and on migrated production result surfaces described by this contract.

### 5.5 Resource bounds (integer-only)

`resource_bounds` MUST include:

| Field | Unit | Role |
| --- | --- | --- |
| `max_input_bytes` | bytes | Input payload ceiling |
| `max_output_bytes` | bytes | Output payload ceiling |
| `max_duration_ms` | milliseconds | Wall-time ceiling |
| `max_memory_bytes` | bytes | Memory ceiling |

Optional integer fields: `max_cpu_ms`, `max_effect_retries`.

All bound fields are JSON integers with finite maxima. Floats are forbidden.

## 6. Minimal JSON shape (example)

```json
{
  "schema": "facp/operation-spec@1",
  "schema_version": 1,
  "operation_id": "datasets.download",
  "namespace": "ipfs_datasets_py",
  "name": "download",
  "version": 1,
  "input_schema_cid": "bafkreifxone36h5jwjwulvkf27le3lmwon7jz65tzo27luipw55q7tcevu",
  "output_schema_cid": "bafkreify4h4axvyk4b4ey6cvurixgg3ul7o3m52j2i7wg67jbavxl2kxlm",
  "error_codes": ["unavailable", "rejected", "failed", "unknown_effect"],
  "effect_class": "write",
  "idempotency_class": "at_most_once",
  "reversibility_class": "compensatable",
  "authority_obligation": "capability_verified",
  "policy_obligation": "host_policy_required",
  "confirmation_obligation": "none",
  "lease_obligation": "lease_required",
  "observation_obligation": "independent_observation_required",
  "evidence_class": "live",
  "allowed_outcomes": [
    "Unavailable",
    "Rejected",
    "Attempted",
    "Unknown",
    "Observed",
    "Verified",
    "Failed",
    "Compensated"
  ],
  "resource_bounds": {
    "max_input_bytes": 1048576,
    "max_output_bytes": 67108864,
    "max_duration_ms": 60000,
    "max_memory_bytes": 268435456,
    "max_cpu_ms": 30000,
    "max_effect_retries": 1
  }
}
```

## 7. Coverage of migrated operations

OperationSpec@1 MUST be able to describe every four-path migrated operation
without inventing free-form authority or outcome fields. Representative
classifications:

| Path | Example `operation_id` | Typical effect | Notes |
| --- | --- | --- | --- |
| Datasets | `datasets.download`, `datasets.upload`, `datasets.get`, `datasets.save`, `datasets.pin`, `datasets.semantic` | `read` / `write` | Closed FCA outcomes; no stub `success` |
| Accelerate | `accelerate.capability_probe`, `accelerate.inference` | `read` / `process` | Live probe evidence; simulation only under explicit test mode |
| Kit | `kit.storage_select`, `kit.proof_role_transition` | `read` / `write` | Live qualification + proof-role freshness |
| SwissKnife | `swissknife.present_evidence`, `swissknife.project_confirmation_intent` | `pure` | Presentation only; `authority_obligation=none`; never constructs host admission |

A pure SwissKnife presentation operation still carries closed `allowed_outcomes`
(commonly including `Observed` for display binding and `Unavailable` /
`Rejected` for missing host evidence) and MUST NOT introduce browser authority
fields.

## 8. Prohibited shapes

The following MUST fail closed at schema validation or deterministic admission:

- Unknown top-level or `resource_bounds` properties
- Missing required fields
- Unknown enum spellings for any closed class/obligation/outcome
- Float values in `schema_version`, `version`, or any resource bound
- Free-form fields named like `authority`, `authorization`, `outcome`,
  `success`, `allowed`, `consent`, or `dry_run`
- Empty `error_codes` or empty `allowed_outcomes`
- Non-CIDv1 `input_schema_cid` / `output_schema_cid` strings
- Unbounded strings or arrays beyond schema maxima

## 9. Security considerations

- OperationSpec declares obligations; only the Effect Admission Kernel
  constructs argument-bound AdmissionTokens (FACP-038+).
- Schema CIDs authenticate **bytes**, not semantic truth of handler behavior.
- Canonical DAG-CBOR / CID profile for signed OperationSpec identity is owned by
  FACP-033; this document pins the logical closed shape only.
- Extending MCP-IDL here MUST NOT add a new MCP++ profile letter.

## 10. Normative artifacts

| Artifact | Path |
| --- | --- |
| This specification | `Mcp-Plus-Plus/docs/spec/assurance-idl.md` |
| OperationSpec@1 JSON Schema | `Mcp-Plus-Plus/schemas/assurance/v1/operation-spec.schema.json` |
| Spec tests | `Mcp-Plus-Plus/tests-py/integration/test_assurance_idl_spec.py` |
| Evidence product vocabulary | `Mcp-Plus-Plus/docs/spec/formal-claim-algebra-v1.md` |
| EvidenceEnvelope@1 schema | `Mcp-Plus-Plus/schemas/assurance/v1/evidence-envelope.schema.json` |

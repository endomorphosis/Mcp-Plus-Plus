# Effect Admission Kernel — Effect Classes and Admission Typestate

**Status:** Normative (Effect Admission Kernel contract)
**Release:** `formal-claim-algebra-v1`
**Schema:** `facp/effect-admission@1`
**Owning task:** FACP-038
**Goal:** FACP-G320 (Effect Admission Kernel)
**Bundle:** `facp/admission/spec`
**Companion:** `Mcp-Plus-Plus/docs/spec/assurance-idl.md` (OperationSpec@1);
`Mcp-Plus-Plus/schemas/assurance/v1/operation-spec.schema.json`;
`Mcp-Plus-Plus/docs/spec/formal-claim-algebra-v1.md` (closed outcomes)

This specification defines the **closed effect-class vocabulary**, the
**admission typestate machine**, the **mechanical derivation of AdmissionToken
obligations** from OperationSpec@1 fields, and the **handler unlock rule** for
the Formal Assurance Control Plane (FACP) Effect Admission Kernel (EAK).

FACP-039 implements the restricted runtime kernel. This document does **not** claim
a live kernel implementation, Lean-checked proofs, or transport wiring.

## 1. Goals

- Classify every migrated operation with exactly one closed `effect_class`.
- Require the closed typestate path from `Proposed` through `ReceiptSealed`,
  with explicit exceptional terminals including `Unknown` and
  `CompensationRequired`.
- Derive AdmissionToken obligations **mechanically** from OperationSpec
  obligation fields — never from free-form authority strings, browser
  `allow`/`consent`/`dry_run`, peer assertions, payment proofs, or model output.
- Unlock effectful handlers **only** with a current argument-bound token
  constructed by the host Effect Admission Kernel.

## 2. Terminal safety statement

No effectful handler on a migrated path MAY execute unless the host Effect
Admission Kernel has issued a current, argument-bound `AdmissionToken@1` whose
obligations were derived from the operation's closed OperationSpec@1. Browser,
prompt, model, peer, payment, and caller-selected tenant inputs MUST NOT
construct, forge, or widen that token.

An ambiguous external effect MUST enter typestate `Unknown`. A compensatable
effect that requires an explicit compensating action MUST enter typestate
`CompensationRequired`. Neither state MAY be relabeled as success, and neither
MAY be blind-retried when `reversibility_class=irreversible`.

## 3. Closed effect classes

Every migrated operation MUST carry exactly one `effect_class` from the closed
set below. The vocabulary is identical to OperationSpec@1 (`FACP-032`) and MUST
NOT be extended by transport adapters or UI code.

| `effect_class` | Meaning | Typical handler unlock |
| --- | --- | --- |
| `pure` | No externally observable side effect; presentation/projection only. | No effectful unlock; MUST NOT mint host AdmissionTokens. |
| `read` | Observes state without durable mutation. | Kernel-issued token required. |
| `write` | Durable state mutation. | Kernel-issued token required. |
| `process` | Spawns or controls an external process. | Kernel-issued token required. |
| `credential` | Touches secrets or credential material. | Kernel-issued token required. |
| `install` | Package/dependency installation. | Kernel-issued token required. |
| `repository` | Repository mutation (commit, push, ref update). | Kernel-issued token required. |
| `publish` | Publishes artifacts to an external audience. | Kernel-issued token required. |
| `payment` | Payment or settlement effect. | Kernel-issued token required; payment NEVER grants authority. |
| `private` | Private/tenant-sensitive effect requiring stronger isolation. | Kernel-issued token required. |
| `legal` | Rights/license/legal disposition effect. | Kernel-issued token required. |
| `irreversible` | Effect class that cannot be undone even with compensation tooling. | Kernel-issued token required; Unknown forbids blind replay. |

**Classification completeness:** every four-path migrated operation (Datasets,
Accelerate, Kit, SwissKnife presentation) MUST be assigned one constructor from
this table. Unclassified operations fail closed and MUST NOT be admitted.

## 4. Closed admission typestate

### 4.1 Happy-path states (ordered)

```text
Proposed
  -> ContractResolved
  -> ActorAuthenticated
  -> CapabilityVerified
  -> PolicyEvaluated
  -> ObligationsSatisfied
  -> ConfirmationSatisfied
  -> LeaseHeld
  -> Reserved
  -> Started
  -> Observed
  -> ReceiptSealed
```

| State | Meaning |
| --- | --- |
| `Proposed` | Intent received; no contract binding yet. |
| `ContractResolved` | OperationSpec@1 located and validated; effect class bound. |
| `ActorAuthenticated` | Actor identity established when required; skipped only when `authority_obligation=none`. |
| `CapabilityVerified` | Capability/delegation chain verified when required. |
| `PolicyEvaluated` | Host policy evaluated; unknown/untranslatable policy fails closed to `Rejected`. |
| `ObligationsSatisfied` | Derived token obligations (non-confirmation/lease) established. |
| `ConfirmationSatisfied` | One-use confirmation consumed when required; otherwise vacuous. |
| `LeaseHeld` | Fresh lease held when required; otherwise vacuous. |
| `Reserved` | Kernel issues argument-bound `AdmissionToken@1`; effect reserved. |
| `Started` | Handler may run **only** with the current kernel-issued token. |
| `Observed` | Independent or delegated observation recorded. |
| `ReceiptSealed` | `EffectReceipt@1` sealed; typestate terminal success path. |

Skipping a non-vacuous step is forbidden. Vacuous steps (obligation=`none`)
MAY advance automatically without inventing evidence.

### 4.2 Exceptional and terminal states (explicit)

| State | Kind | Meaning |
| --- | --- | --- |
| `Rejected` | terminal | Admission denied (policy, capability, confirmation, or schema). |
| `Unavailable` | terminal | Required capability/backend absent; no effect started. |
| `Failed` | terminal | Effect attempted and failed under observation. |
| `Unknown` | terminal-until-reconciled | External effect outcome is ambiguous; **explicit**. |
| `CompensationRequired` | holding | Compensatable effect requires an explicit compensating action; **explicit**. |
| `Compensated` | terminal | Required compensation completed and observed. |
| `Aborted` | terminal | Reserved/started effect cancelled before observation without external ambiguity. |

`Unknown` and `CompensationRequired` are first-class typestate constructors.
They MUST appear in the normative vocabulary and MUST NOT be encoded as
boolean `success`, free-form strings, or silent fall-through to `Observed`.

### 4.3 Legal transitions (fail-closed)

Only the following transition families are admitted. Any other edge fails
closed with `ILLEGAL_TYPESTATE_TRANSITION`.

**Forward happy path:** each consecutive pair in §4.1.

**Early denial / unavailability** (from any pre-`Reserved` state):

- `* -> Rejected`
- `* -> Unavailable`

**Post-start observation:**

- `Started -> Observed`
- `Started -> Failed`
- `Started -> Unknown`
- `Started -> Aborted`
- `Started -> CompensationRequired` (only if `reversibility_class=compensatable`)

**Unknown reconciliation** (no blind retry into `Reserved`/`Started` when
`reversibility_class=irreversible`):

- `Unknown -> Observed`
- `Unknown -> Failed`
- `Unknown -> CompensationRequired` (only if `reversibility_class=compensatable`)
- `Unknown -> Aborted` (only if reconciliation proves no external effect)

**Compensation:**

- `CompensationRequired -> Compensated`
- `CompensationRequired -> Failed`
- `Observed -> CompensationRequired` (only if `reversibility_class=compensatable` and compensation is still owed)

**Seal:**

- `Observed -> ReceiptSealed`
- `Compensated -> ReceiptSealed`
- `Failed -> ReceiptSealed` (failure receipt)
- `Rejected -> ReceiptSealed` (rejection receipt)
- `Unavailable -> ReceiptSealed`
- `Aborted -> ReceiptSealed`

## 5. Mechanical token-obligation derivation

AdmissionToken obligations are a **pure function** of the OperationSpec@1
obligation fields plus universal token bindings. Implementations MUST compute
the set below; they MUST NOT accept caller-supplied obligation lists.

### 5.1 Closed obligation constructors

| Constructor | When derived |
| --- | --- |
| `kernel_issued` | Always. Only the Effect Admission Kernel may mint the token. |
| `operation_bound` | Always. Token binds `operation_id`. |
| `effect_class_bound` | Always. Token binds the closed `effect_class`. |
| `argument_bound` | Always. Token binds `argument_cid`. |
| `nonce_bound` | Always. One-use nonce. |
| `expiry_bound` | Always. Finite `not_after`. |
| `actor_bound` | `authority_obligation ∈ {actor_authenticated, capability_verified}` |
| `capability_bound` | `authority_obligation = capability_verified` |
| `delegation_bound` | `authority_obligation = capability_verified` |
| `policy_bound` | `policy_obligation ∈ {host_policy_required, host_policy_with_obligations}` |
| `policy_obligations_bound` | `policy_obligation = host_policy_with_obligations` |
| `confirmation_bound` | `confirmation_obligation = one_use_confirmation_required` |
| `lease_bound` | `lease_obligation = lease_required` |
| `observation_bound` | `observation_obligation ∈ {independent_observation_required, delegated_observation_allowed}` |

### 5.2 Derivation algorithm (normative)

```text
derive_token_obligations(spec) -> set:
  out := {
    kernel_issued, operation_bound, effect_class_bound,
    argument_bound, nonce_bound, expiry_bound
  }
  if spec.authority_obligation = actor_authenticated:
    out := out ∪ {actor_bound}
  if spec.authority_obligation = capability_verified:
    out := out ∪ {actor_bound, capability_bound, delegation_bound}
  if spec.policy_obligation = host_policy_required:
    out := out ∪ {policy_bound}
  if spec.policy_obligation = host_policy_with_obligations:
    out := out ∪ {policy_bound, policy_obligations_bound}
  if spec.confirmation_obligation = one_use_confirmation_required:
    out := out ∪ {confirmation_bound}
  if spec.lease_obligation = lease_required:
    out := out ∪ {lease_bound}
  if spec.observation_obligation ≠ none:
    out := out ∪ {observation_bound}
  if spec.effect_class = pure:
    # Pure presentation never yields a host effect unlock token.
    return ∅
  return out
```

Unknown obligation enum spellings fail closed (`UNKNOWN_ENUM`). Free-form
keys such as `authority`, `consent`, `allowed`, `dry_run`, `grant`, or
`success` fail closed (`FREE_FORM_AUTHORITY`).

### 5.3 Token minting locus

Only the host Effect Admission Kernel constructs `AdmissionToken@1`, and only
on the transition into `Reserved` after all derived obligations for that
operation are satisfied. SwissKnife / browser presentation code MUST NOT mint
tokens and MUST NOT treat UI confirmation as `authority_obligation` or
`policy_obligation` satisfaction.

## 6. Handler unlock rule

An effectful handler (`effect_class ≠ pure`) is unlocked if and only if all of
the following hold:

1. Current typestate is `Reserved` or `Started`.
2. A token is present with `admission_token_issuer = effect_admission_kernel`.
3. The token's satisfied obligations cover `derive_token_obligations(spec)`.
4. `operation_id` and `argument_cid` match the call in hand.
5. The token is not expired or revoked.
6. Typestate is not `Unknown`, `CompensationRequired`, `Rejected`,
   `Unavailable`, `Failed`, `Aborted`, `Compensated`, or `ReceiptSealed`.

If any clause fails, the handler MUST NOT run (`HANDLER_NOT_UNLOCKED`).

Pure handlers never unlock via AdmissionToken. They also MUST NOT accept a
caller-supplied token as authority.

## 7. Outcome algebra binding

Typestate is distinct from the Formal Claim Algebra closed outcome algebra:

`Unavailable | Rejected | Simulated | Attempted | Unknown | Observed | Verified | Failed | Compensated`

Mapping constraints:

| Typestate | Permitted sealed outcomes (non-exhaustive) |
| --- | --- |
| `Unknown` | `Unknown` (required); MUST NOT seal as `Observed`/`Verified` without reconciliation |
| `CompensationRequired` | Must not seal until `Compensated` or `Failed`; outcome `Compensated` only after compensation |
| `Observed` | `Observed` / `Verified` (when evidence permits) |
| `Failed` | `Failed` |
| `Rejected` | `Rejected` |
| `Unavailable` | `Unavailable` |

Generic `success: true` / `success: false` is forbidden on migrated production
paths.

## 8. Migrated operation coverage

Representative classifications (every row MUST validate against OperationSpec@1
and yield mechanical token obligations under §5):

| Path | Example `operation_id` | `effect_class` | Notes |
| --- | --- | --- | --- |
| Datasets | `datasets.download`, `datasets.upload`, `datasets.save`, `datasets.pin` | `write` | Token required; Unknown/Compensated allowed |
| Datasets | `datasets.get` | `read` | Token required |
| Datasets | `datasets.semantic` | `process` | Token required |
| Accelerate | `accelerate.capability_probe` | `read` | Live probe; token required |
| Accelerate | `accelerate.inference` | `process` | Simulated only in explicit test mode |
| Kit | `kit.storage_select` | `read` | Token required |
| Kit | `kit.proof_role_transition` | `write` | Confirmation + lease; irreversible reversibility |
| SwissKnife | `swissknife.present_evidence`, `swissknife.project_confirmation_intent` | `pure` | No host token; presentation only |

Every constructor in §3 MUST appear in the normative vocabulary even when a
particular release wave has not yet migrated an operation of that class.

## 9. Prohibited shapes

The following MUST fail closed:

- Unknown `effect_class`, typestate, token-obligation, or issuer spellings
- Unknown top-level fields on `facp/effect-admission@1` instances
- Free-form authority / outcome / success / consent / dry_run fields
- Caller-, browser-, peer-, payment-, or model-issued AdmissionTokens
- Advancing to `Started` without a kernel-issued token (effectful ops)
- Blind replay from `Unknown` when `reversibility_class=irreversible`
- Relabeling `Unknown` or `CompensationRequired` as `Observed` without the
  legal transitions in §4.3
- Floats on schema_version or other security-critical integers

Stable error codes include: `UNKNOWN_FIELD`, `MISSING_FIELD`, `UNKNOWN_ENUM`,
`INVALID_TYPE`, `FORBIDDEN_FLOAT`, `FREE_FORM_AUTHORITY`, `FREE_FORM_OUTCOME`,
`FORBIDDEN_SUCCESS_BOOLEAN`, `ILLEGAL_TYPESTATE_TRANSITION`,
`TOKEN_OBLIGATION_MISMATCH`, `HANDLER_NOT_UNLOCKED`,
`NON_KERNEL_TOKEN_ISSUER`, `BLIND_UNKNOWN_REPLAY`,
`COMPENSATION_REQUIRED_EXPLICIT`.

## 10. Normative vocabulary (machine-readable)

```json
{
  "schema": "facp/effect-admission-vocab@1",
  "schema_version": 1,
  "task_id": "FACP-038",
  "goal_id": "FACP-G320",
  "bundle": "facp/admission/spec",
  "instance_schema": "facp/effect-admission@1",
  "fail_closed": true,
  "kernel_only_token_issuer": true,
  "unknown_explicit": true,
  "compensation_required_explicit": true,
  "effect_classes": [
    "pure",
    "read",
    "write",
    "process",
    "credential",
    "install",
    "repository",
    "publish",
    "payment",
    "private",
    "legal",
    "irreversible"
  ],
  "typestate_happy_path": [
    "Proposed",
    "ContractResolved",
    "ActorAuthenticated",
    "CapabilityVerified",
    "PolicyEvaluated",
    "ObligationsSatisfied",
    "ConfirmationSatisfied",
    "LeaseHeld",
    "Reserved",
    "Started",
    "Observed",
    "ReceiptSealed"
  ],
  "typestate_exceptional": [
    "Rejected",
    "Unavailable",
    "Failed",
    "Unknown",
    "CompensationRequired",
    "Compensated",
    "Aborted"
  ],
  "token_obligation_constructors": [
    "kernel_issued",
    "operation_bound",
    "effect_class_bound",
    "argument_bound",
    "nonce_bound",
    "expiry_bound",
    "actor_bound",
    "capability_bound",
    "delegation_bound",
    "policy_bound",
    "policy_obligations_bound",
    "confirmation_bound",
    "lease_bound",
    "observation_bound"
  ],
  "admission_token_issuer": ["effect_admission_kernel"],
  "handler_unlock_typestates": ["Reserved", "Started"],
  "closed_outcomes": [
    "Unavailable",
    "Rejected",
    "Simulated",
    "Attempted",
    "Unknown",
    "Observed",
    "Verified",
    "Failed",
    "Compensated"
  ]
}
```

## 11. Security considerations

- OperationSpec declares obligations; only the Effect Admission Kernel
  constructs argument-bound AdmissionTokens.
- Payment, peer attestations, and browser consent do not satisfy
  `authority_obligation` or `policy_obligation`.
- Canonical DAG-CBOR identity for `AdmissionToken@1` / `EffectReceipt@1` is
  owned by FACP-033; this document pins typestate and obligation semantics.
- FACP-039 owns the restricted runtime kernel; FACP-040/041 own transport and
  SwissKnife negative gates.

## 12. Normative artifacts

| Artifact | Path |
| --- | --- |
| This specification | `Mcp-Plus-Plus/docs/spec/effect-admission-kernel.md` |
| EffectAdmission@1 JSON Schema | `Mcp-Plus-Plus/schemas/assurance/v1/effect-admission.schema.json` |
| Spec tests | `Mcp-Plus-Plus/tests-py/integration/test_effect_admission_spec.py` |
| OperationSpec@1 | `Mcp-Plus-Plus/docs/spec/assurance-idl.md` |
| Evidence product vocabulary | `Mcp-Plus-Plus/docs/spec/formal-claim-algebra-v1.md` |

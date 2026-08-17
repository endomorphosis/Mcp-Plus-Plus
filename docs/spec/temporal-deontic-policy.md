# Profile D: Temporal Deontic Policy Evaluation

**Status:** Normative (MCP++ 1.0 draft → interface-stable)  
**Interfaces:** `PolicyEvaluator@1`, `PolicyDecision@1`  
**Schema markers:** `mcp++/profile-d-policy@1`, `mcp++/profile-d-policy-decision@1`  
**Canonicalization:** `mcpp-jcs-v1` (ADR-0002)  
**Reference implementation:** `tests-py/validators/policy_evaluation.py`

This document expands the MCP++ temporal deontic policy profile: how policies
are derived, represented, delegated, evaluated, and turned into immutable
decisions and receipts. It also defines the **deterministic evaluator
interface** used by conformance validators and runtime gates.

## 1. Where the policy engine fits

Temporal deontic logic is used at two points:

1) **Prompt → Delegation**: interpret user intent into a policy and mint delegations.
2) **Intent → Decision → Receipt**: evaluate whether the proposed action is allowed *right now*, and what obligations it creates.

Authority (Profile C UCAN), policy compliance (Profile D), and execution receipts
remain **distinct**. A valid transport identity or a statement commitment does
**not** authorize execution.

## 2. Policy Representation (`policy_cid`)

A policy MUST be content-addressed to a `policy_cid` and SHOULD be versioned.

Policies express:

- **Permissions** (what is allowed)
- **Prohibitions** (what is forbidden)
- **Obligations** (what must be done, often with deadlines)
- **Temporal constraints** (validity windows, deadlines, revocations)

The project does not need to standardize one policy language immediately, but it MUST standardize:

- canonicalization rules (`mcpp-jcs-v1`),
- how `policy_cid` is referenced from delegations and intents,
- minimum decision semantics (`PolicyDecision@1`),
- the deterministic evaluator contract (`PolicyEvaluator@1`).

### 2.1 Clause document shapes

Implementations MUST accept both of the following equivalent forms:

**Multi-clause policy**

```json
{
  "schema": "mcp++/profile-d-policy@1",
  "version": "v1",
  "clauses": [
    {
      "clause_id": "p-1",
      "clause_type": "permission",
      "actor": "did:key:z6Mk…",
      "action": "tool/execute",
      "resource": "weather-api",
      "valid_from": "2024-01-01T00:00:00Z",
      "valid_until": "2024-12-31T23:59:59Z"
    }
  ]
}
```

**Single-clause document** (fixture / simple wire form)

```json
{
  "type": "permission",
  "action": "tool/execute",
  "resource": "weather-api",
  "temporal_constraints": {
    "valid_from": "2024-01-01T00:00:00Z",
    "valid_until": "2024-12-31T23:59:59Z"
  }
}
```

`type` / `clause_type` MUST be one of `permission`, `prohibition`, `obligation`.

Temporal timestamp fields MUST be ISO-8601 when present. Structural validators
MUST reject malformed timestamps; they MUST NOT silently ignore them.

## 3. Minimal Logic Interface (Non-Normative)

A common representation uses operators:

- $P(action, t)$ — permitted at time $t$
- $F(action, t)$ — forbidden at time $t$
- $O(outcome, deadline)$ — obligated before deadline

A compiled policy may encode clauses such as:

- Permission: $P(actor, action(resource), t \in [t_0,t_1])$
- Prohibition: $F(actor, action(resource), condition)$
- Obligation: $O(actor, produce(receipt\_cid), deadline)$

Archive example clause (literal phrasing): “forbidden to call tool X after revocation”.

## 4. Prompt → Policy Extraction → Delegation

Given a prompt like:

> “Have model B summarize this dataset, but only for these topics, only for 24 hours, and don’t exfiltrate.”

A planner extracts *normative clauses* (actors, resources, actions, time bounds, constraints), compiles them into a formal/compiled policy, and stores:

- `policy_cid`: formal text + compiled executable form

Then a delegation token is minted that:

- encodes the hard “who can do what” authority,
- references `policy_cid` for richer constraints and audit.

## 5. Runtime: Intent → Decision

When a peer wants to execute an action, it submits:

- `intent_cid` / intent object
- `ucan_proofs[]` (or equivalent delegation chain)
- `context_cids[]` / context roots (state snapshots, prior events)
- logical evaluation time

Evaluators MUST:

1. Validate delegation proofs (cryptographic chain validity when claimed)
2. Evaluate policy *against the intent and the current context*
3. Produce a `decision_cid` that records:
   - verdict (`allow` / `deny` / `allow_with_obligations`)
   - proofs checked
   - policy version
   - obligations spawned
   - fired rules, facts, and decision commitment

Archive phrasing (literal): return decision_cid (content addressed + optionally signed)

Decisions SHOULD be signed by evaluators.

### 5.1 Wire Decision Result (Normative)

The `mcp++/policy/evaluate` JSON-RPC method returns a minimal decision object:

- `decision` — `allow` | `deny` | `allow_with_obligations` (strings; REQUIRED)
- `obligations[]` — spawned obligations (OPTIONAL)
- `allowed` — convenience boolean mirroring the verdict (OPTIONAL)
- `policy_cid`, `witness` — OPTIONAL provenance

Validated by `PolicyDecision` wire models. CID-native deployments add
`policy_cid` / `witness`; extra fields are permitted for forward compatibility.

---

## 6. PolicyEvaluator@1 (Normative)

| Field | Value |
| --- | --- |
| Interface label | `PolicyEvaluator@1` |
| Decision interface | `PolicyDecision@1` |
| Decision schema marker | `mcp++/profile-d-policy-decision@1` |
| Reference module | `tests-py/validators/policy_evaluation.py` |
| Versioning rule | Breaking changes require `PolicyEvaluator@2` / a new schema marker |

### 6.1 Inputs

`evaluate` accepts the following inputs (names are logical; language bindings MAY
use kwargs or a single request object):

| Input | Required | Meaning |
| --- | --- | --- |
| `intent` | **yes** | Proposed action object: actor/action/resource/`intent_cid` |
| `policy` / `policies` | **yes** (at least one) | Policy document(s) to evaluate |
| `delegation` | no | Delegation proof object or list; structural invalidity is deny |
| `context_roots` | conditional | Observed context root map (`name → root_cid`) |
| `expected_context_roots` | no | Authoritative roots; mismatch → **stale root deny** |
| `required_context_keys` | no | Keys that MUST appear in `context_roots` |
| `logical_time` | conditional | ISO-8601 or epoch seconds; **never** wall-clock inside the evaluator |
| `prior_events` | no | Prior event records (revocation / provenance facts) |
| `policy_version` | no | Expected version when the policy declares one |
| `signature` | no | Optional detached signature attached to the decision output |

Closed-world rule: when no policy document is supplied, the verdict is **deny**.

### 6.2 Determinism

For the same logical inputs, `PolicyEvaluator@1` MUST return the same:

- `decision` verdict
- ordered `obligations`, `fired_rules`, `facts`, `deadlines`, `compensation`
- `decision_commitment`
- `decision_cid`

Implementations MUST NOT consult wall-clock time, random sources, or mutable
global registries during evaluation. Temporal windows are evaluated only against
the supplied `logical_time`. When a clause has temporal bounds and
`logical_time` is absent, that clause is inactive (fail-closed).

Clause iteration order MUST be stable: sort by `(clause_id, clause_type, action, source_index)`.

### 6.3 Fail-closed gates (normative order)

Evaluation MUST apply the following gates **before** deontic matching, in order.
Any gate that fires produces `decision=deny` with a stable `reason_code`:

| Order | Condition | `reason_code` |
| --- | ---: | --- |
| 1 | `intent` is not an object | `invalid_input` |
| 2 | `logical_time` present but not parseable | `invalid_input` |
| 3 | `delegation` supplied and structurally invalid / marked revoked | `delegation_invalid` |
| 4 | Required context key missing from `context_roots` | `missing_context` |
| 5 | Observed root CID ≠ expected root CID for a named key | `stale_root` |
| 6 | Declared policy version ≠ expected `policy_version` | `policy_version_mismatch` |
| 7 | Prior event records a revocation targeting the intent or policy | `revoked_before_execution` |

**Missing context** and **stale root** are always deny. There is no “best effort”
evaluation when required roots are absent or diverge from the expected head.

### 6.4 Deontic matching

After gates pass, matching clauses are those that are temporally active at
`logical_time` and whose scope covers the intent.

Resolution rules (deterministic):

1. Any matching **prohibition** → `deny` (`reason_code=prohibition_matched`).
2. Else if at least one matching **permission** and one or more **obligations**
   (including human-approval obligations) → `allow_with_obligations`.
3. Else if at least one matching **permission** → `allow`.
4. Else → `deny` (`reason_code=no_matching_permission`).

Pattern matching:

- `*` matches any value.
- `prefix/*` matches values with that prefix.
- Empty actor/action defaults to `*`.
- **Permissions** and **prohibitions** match on actor + action + resource.
- **Obligations** match on actor + resource. Their `action` field names the
  *obligated act* (for example `audit/log`), not the intent method. An
  obligation MAY further restrict intent methods via `on_action` / `applies_to`.

When multiple policies are supplied, prohibitions across the **entire set** win
(most restrictive). Permissions and obligations are unioned with stable ordering.

### 6.5 Human approval and compensation

- A `human_approval: true` metadata flag on a permission or obligation MUST be
  surfaced as an **obligation** (status `pending`), never as an implicit allow
  without obligations.
- Compensation metadata on obligation clauses MUST be copied into the decision’s
  `compensation[]` list (ordered by clause id). Compensation is recorded, not
  executed, by the evaluator.

### 6.6 Outputs — PolicyDecision@1

Every evaluation returns a `PolicyDecision@1` object:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `schema` | string | yes | `mcp++/profile-d-policy-decision@1` |
| `interface` | string | yes | `PolicyDecision@1` |
| `decision` | string | yes | `allow` \| `deny` \| `allow_with_obligations` |
| `granted` / `allowed` | bool | yes | true iff decision is allow* |
| `decision_cid` | CID | yes | Content-address of the decision body |
| `decision_commitment` | hex | yes | sha2-256 of canonical decision body |
| `evaluated_at` | ISO-8601 | yes | Canonicalized from `logical_time` or epoch zero |
| `policy_cid` | CID | yes when policy present | Primary policy identifier |
| `intent_cid` | CID/string | yes when present on intent | |
| `justification` | string | yes | Stable human-readable reason |
| `reason_code` | string | on deny paths | Machine-stable gate/match code |
| `obligations[]` | object[] | when spawned | Ordered; includes deadlines/status |
| `fired_rules[]` | object[] | yes (may be empty) | Matched clauses |
| `facts[]` | object[] | yes (may be empty) | Context / match facts |
| `deadlines[]` | object[] | when obligations have deadlines | |
| `compensation[]` | object[] | when declared | |
| `human_approval` | object \| null | when required | `{required, clause_id, status}` |
| `signature` | string \| null | optional | Detached evaluator signature |

`decision_commitment` and optional ZKP **statement** certificates are provenance
commitments only. They are **not** verified zero-knowledge proofs of correct
policy evaluation unless an admitted Profile D circuit and verification key are
present (see §11). Implementations MUST fail closed: structural validation,
deterministic fixtures, or a self-declared flag MUST NOT label a certificate as
`verified` or `zero_knowledge: true`.

### 6.7 Content addressing

`decision_cid` MUST be computed under `mcpp-jcs-v1` over the decision body
**excluding** the `decision_cid`, `decision_commitment`, and `signature` fields
themselves (those are derived after canonicalization of the logical body). The
reference implementation mints the body first, then attaches CID and commitment.

Identical inputs MUST yield identical `decision_cid` values across languages that
claim `PolicyEvaluator@1`.

## 7. Execution → Receipt → Obligations

Execution emits a `receipt_cid` that binds:

- the `intent_cid`
- produced `output_cid`
- observed side effects
- the `decision_cid`

Receipts become the audit substrate for:

- disputes and rollbacks
- risk scoring
- compliance proofs

An allow decision that creates an obligation is **incomplete** until the
obligation is satisfied or compensated. Obligation lifecycle events
(`obligation_created`, `obligation_satisfied`, `obligation_violated`,
`compensation_required`, `compensation_completed`, `compensation_failed`) are
specified by the obligation-event suite and MUST be content-addressed.

## 8. Violations and Compensating Obligations

Temporal deontic systems are useful because they can model:

- missed deadlines (obligation violations)
- compensating obligations (e.g., “if exfiltration occurs, rotate secrets and notify within 1 hour”)

MCP++ standardizes how violations are recorded in:

- `decision_cid` (as detected at evaluation time — e.g. overdue status)
- `event_cid` / receipts (as observed during obligation lifecycle)

## 9. Delegation Chains and “Speaks-For”

Delegation often looks like:

User → Planner model → Worker model → Tool peer

Implementations MAY model “on behalf of” / “speaks-for” relationships as part of
policy evaluation, but this is non-normative until a concrete interoperable
representation is chosen. Profile C remains the cryptographic authority gate;
Profile D does not replace UCAN verification.

## 10. Security Considerations

- Authorization MUST be checked at execution time, not just at delegation time.
- Evaluators MUST have access to sufficient context (via context roots) to make a
  correct decision; missing or stale roots are **deny**.
- Policy evaluation should be sandboxed and resource-limited.
- Conflicting policies resolve by the deterministic rule in §6.4 (prohibitions win).
- Human-approval requirements are obligations, not implicit allow.

## 11. Profile D Policy-Evaluation ZKP Certificate (Normative)

Profile D names the optional policy-evaluation proof profile
`profile_d_policy_evaluation@v1`. It allows a peer to prove the public
commitments of an evaluated policy decision without disclosing the private
policy text, request context, evaluator trace, or witness.

The public statement schema is `mcp++/profile-d-policy-zkp-statement@1` and
MUST contain exactly:

- `circuit_ref`
- `policy_commitment`
- `context_commitment`
- `decision_commitment`
- `verdict`
- `obligations_commitment`

Commitments MUST use canonical compact, recursively key-sorted UTF-8 JSON and
SHA-256. The decision commitment MUST bind the verdict and the complete ordered
obligation list. The certificate schema is
`mcp++/profile-d-policy-zkp-certificate@1`; its `public_inputs` value MUST be
identical to `public_statement`.

A certificate MUST be `statement_only`, with `proof: null`,
`verified: false`, and `zero_knowledge: false`, unless all of the following
admission gates are true:

1. The circuit is production-admitted.
2. The trusted setup is production-admitted.
3. The verification key is production-admitted.
4. A cryptographic verifier accepts the proof against the complete public
   statement and an explicitly admitted circuit/key allowlist.

Implementations MUST fail closed. Structural validation, deterministic test
fixtures, simulated proofs, or a self-declared admission flag are insufficient
to label a certificate verified or zero knowledge. Consumers MUST treat
statement-only certificates as provenance commitments only; they do not grant
authorization and do not prove the private policy relation.

## 12. Conformance notes

| Check | Where |
| --- | --- |
| Structural policy / decision shape | `PolicyEvaluationValidator` |
| Deterministic evaluate() | `PolicyEvaluator` (`PolicyEvaluator@1`) |
| Integration fixtures | `tests-py/integration/test_policy_evaluation.py` |
| Future negative vectors | policy version mismatch, missing context, stale root, conflicts |

Language ports that claim Profile D MUST implement the same gate order and
verdict resolution as §6 so cross-language `decision_cid` values agree for
shared vectors.

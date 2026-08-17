# Profile G: Risk Scoring, Neighborhood Coordination, and Scheduling

**Status:** Normative (MCP++ 1.0)  
**Interface family:** `ProfileGNormative@1`  
**Profile key:** `mcp++/risk-scheduling`  
**Profile version:** `1.0`  
**Artifact schema major:** `1` (wire markers `mcp++/profile-g/<kind>@1`)  
**Capability negotiation:** `mcp++/risk-scheduling` with `versions: ["1.0"]`  
**Authority:** Plan KD-11; goal `MCPP-G130`; tasks `MCPP-066`…`MCPP-069`; ADR-0004 §4  
**Related:** `StateRef@1` (`state-ref.md`); `ConsensusPlugin@1` (`consensus-plugin.md`);
Event DAG (`event-dag-ordering.md`); ExecutionEnvelope family (`execution-envelope.md`);
canonicalization `mcpp-jcs-v1` (`canonicalization-mcpp-jcs-v1.md`); CID-native
artifacts (`cid-native-artifacts.md`); MCP-IDL (`mcp-idl.md`)

**Codec / harness alignment (informative):**  
`tests-py/validators/profile_g.py` (and TS/Go/Rust codec tests);  
`conformance/vectors/profile_g_{artifacts,protocol}_{valid,invalid}.json`;  
`conformance/vectors/profile_g_three_peer.json`;  
`tests-py/harness/profile_g_three_peer.py`

The words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are to
be interpreted as described by RFC 2119 and RFC 8174 when capitalized.

---

## 0. Supersession notice (normative)

This document is the **single normative Profile G coordination specification**
for MCP++ 1.0. It reconciles the former draft chapter, registry sketch text,
codec field sets, and three-peer harness semantics into one wire contract.

| Prior text | Treatment under MCP++ 1.0 |
| --- | --- |
| This file’s earlier **Draft (Mostly Non-Normative)** chapter | **Superseded.** All sections below with RFC 2119 language are normative. |
| Registry `mcp++-profiles-draft.md` §10.2–§10.3 and §11 language that treated scheduling / risk as wholly non-normative, or titled the profile “Neighborhood Consensus” without guarantee labels | **Superseded for Profile G wire behavior.** The registry remains a discovery index; **this chapter is authoritative** for artifact shapes, claim/lease/fence rules, majority requirements, and honest labels. Heuristic sketches (LSH, Fibonacci heaps) stay non-normative (§15). |
| Informal marketing that “neighborhood consensus” implies **BFT** or a **global total order** | **Superseded and forbidden.** Profile G provides **local coordination** and optional **majority approval** only (§2, §8). |
| Any document that claims Profile G results as `crash_consensus` or `bft` without a separate `ConsensusPlugin@1` escalation | **Superseded.** Escalation MUST use `ConsensusPlugin@1` with a new evidence record and a new declared guarantee (`consensus-plugin.md` §3). |
| Coverage claims that “all validators” are complete while omitting Profile G codec vectors | **Superseded** by codec + three-peer evidence requirements in §14. |

Implementations that still quote superseded draft wording MUST treat this chapter
as controlling. When prose and codec vectors disagree, **codec vectors plus this
chapter’s MUST/MUST NOT rules** win for structural acceptance; when this chapter
and a harness fixture disagree on exclusive-work safety, **fail closed**
(reject the unsafe completion).

---

## 1. Purpose and non-goals

### 1.1 Purpose

Profile G defines how MCP++ peers:

1. **Score risk** from content-addressed evidence (immutable history).
2. **Advertise neighborhood capacity** and attest schedule proposals.
3. **Prioritize** ready work with a deterministic priority tuple.
4. **Claim, lease, fence, complete, and reconcile** exclusive and shared tasks
   under **local** coordination rules.
5. Bind outcomes to Profile B receipts / ExecutionEnvelope@1 and Profile F
   Event DAG parents without inventing a second global chain.

### 1.2 Non-goals (normative boundaries)

Profile G **MUST NOT** be described or implemented as:

| Claim | Status |
| --- | --- |
| Global consensus / one chain that totally orders all peers | **Out of scope.** Local coordination only. |
| Byzantine fault tolerance (`bft`) | **Out of scope** for neighborhood agreement. |
| Crash-tolerant quorum protocols (Raft/Paxos class) | **Out of scope** unless escalated via `ConsensusPlugin@1` with label `crash_consensus`. |
| Silent upgrade of neighborhood ballots into stronger guarantees | **Forbidden.** |
| Replacement of Profile C authority or Profile D policy | **Forbidden.** Claim/lease success does not grant UCAN caps or policy allow. |
| Cryptographic signature verification of neighborhood attestations | **Not required** at structural codec conformance (fields are structural strings). Trust-layer verification is a higher conformance level (REQ-G-02). |

**Acceptance (MCPP-066 / REQ-G-03 / REQ-G-06):** Local coordination is
**explicitly not** global consensus. Contradictory earlier text is marked
superseded in §0.

---

## 2. Guarantee model: local coordination ≠ global consensus

### 2.1 Honest labels

When Profile G outcomes feed `StateRef@1` `mode: consensus` or
`ConsensusPlugin@1` evidence, the guarantee label **MUST** be exactly one of:

| Label | Profile G use |
| --- | --- |
| `coordination` | Best-effort neighborhood alignment, frontier sync, risk-scheduler signals. **No** crash or Byzantine safety claim. |
| `majority_approval` | Threshold approval among a **declared peer set** for that neighborhood only. |

Profile G **MUST NOT** emit or accept evidence labeled `crash_consensus` or
`bft` for neighborhood records, attestations, claim resolutions, or three-peer
majority placement. Those labels require a separate plugin with real protocol
evidence (`consensus-plugin.md` §3.1–§3.2).

### 2.2 Locality

- **Neighborhood** means a declared, bounded peer set (trust domain, resource
  class overlay, or explicit member list)—not the entire MCP++ network.
- Agreement inside a neighborhood **does not** imply agreement outside it.
- Partition of the required majority **MUST** fail closed for exclusive work
  (`G_COORDINATION_UNAVAILABLE` / `G_QUORUM_UNAVAILABLE`), not invent a split-brain winner.
- Escalation to stronger consensus **MAY** occur when risk thresholds or
  conflicts demand it; escalation **MUST** change the declared guarantee label
  and evidence format.

### 2.3 Archive framing (retained)

Archive phrasing remains correct and is elevated to normative intent:

> Neighborhood agreement is a **coordination optimization**, not a consensus
> requirement for the global system.

---

## 3. Interface identity and negotiation

| Field | Value |
| --- | --- |
| Profile key | `mcp++/risk-scheduling` |
| Negotiated version | `1.0` |
| Artifact schema major | `1` |
| Lease clock | `unix-ms-with-logical-epoch` |
| Required transport parity (when both offered) | `jsonrpc-http`, `mcp+p2p` |

### 3.1 Capability advertisement

Clients request Profile G during MCP `initialize`, for example:

```json
{
  "capabilities": {
    "experimental": {
      "mcp++/risk-scheduling": { "versions": ["1.0"] }
    }
  }
}
```

A server that accepts Profile G **MUST** advertise at least:

```json
{
  "version": "1.0",
  "artifact_schema_major": 1,
  "lease_clock": "unix-ms-with-logical-epoch",
  "transports": ["jsonrpc-http", "mcp+p2p"]
}
```

(Transports MAY be a subset if only one binding is implemented; methods that
claim parity **MUST** produce identical semantic digests across offered
transports—see §12.)

Operations under Profile G without a negotiated capability **MUST** fail with
`G_CAPABILITY_NOT_NEGOTIATED`.

### 3.2 Method surface (normative names)

| Method | HTTP binding (informative) |
| --- | --- |
| `mcp++/risk/profile` | `GET /mcp/risk/profile` |
| `mcp++/goals/create` | `POST /mcp/goals` |
| `mcp++/goals/get` | `GET /mcp/goals/{cid}` |
| `mcp++/goals/list` | `GET /mcp/goals` |
| `mcp++/goals/decompose` | `POST /mcp/goals/{cid}/decompose` |
| `mcp++/goals/select` | `POST /mcp/goals/{cid}/select` |
| `mcp++/tasks/create` | `POST /mcp/tasks` |
| `mcp++/tasks/get` | `GET /mcp/tasks/{cid}` |
| `mcp++/tasks/list` | `GET /mcp/tasks` |
| `mcp++/tasks/ready` | `GET /mcp/tasks/ready` |
| `mcp++/risk/assess` | `POST /mcp/risk/assess` |
| `mcp++/risk/evidence` | `GET /mcp/risk/evidence` |
| `mcp++/risk/history` | `GET /mcp/risk/history` |
| `mcp++/neighborhood/query` | `POST /mcp/neighborhood/query` |
| `mcp++/neighborhood/attest` | `POST /mcp/neighborhood/attest` |
| `mcp++/schedule/frontier` | `GET /mcp/schedule/frontier` |
| `mcp++/schedule/status` | `GET /mcp/schedule/status/{task_cid}` |
| `mcp++/schedule/propose` | `POST /mcp/schedule/proposals` |
| `mcp++/schedule/claim` | `POST /mcp/schedule/claims` |
| `mcp++/schedule/renew` | `POST /mcp/schedule/claims/{claim_cid}/renew` |
| `mcp++/schedule/release` | `POST /mcp/schedule/claims/{claim_cid}/release` |
| `mcp++/schedule/resolve` | `POST /mcp/schedule/resolutions` |
| `mcp++/schedule/reconcile` | `POST /mcp/schedule/reconcile` |

Mutation methods **MUST** accept an envelope that can carry `artifact_cid`,
`idempotency_key`, `correlation_id`, `parents`, `proof_cid`, and
`policy_decision_cid`, and **MUST** return at least
`artifact`, `artifact_cid`, `event_cid`, and `replayed`.

---

## 4. Shared wire rules

### 4.1 Canonical bytes and CIDs

1. Artifacts **MUST** be JSON objects with **no floats**, **no `NaN`/`Infinity`**,
   and string keys only.
2. Canonical bytes **MUST** be RFC 8785-style sorted-key compact JSON
   (`sort_keys=true`, separators `,` `:`, `ensure_ascii=false`, `allow_nan=false`)
   as implemented by the Profile G codec (`canonical_profile_g_bytes`).
3. Artifact CIDs **MUST** be **CIDv1**, multicodec **dag-json** (`0xa9 0x02` in the
   codec path used by `profile_g_artifact_cid`), multihash **sha2-256** (code 18),
   32-byte digest, base32 lower-case multibase (`b…`).
4. Any field typed as CID in this chapter **MUST** satisfy that CIDv1/sha2-256
   shape when present as a content id string.

### 4.2 Common header fields

Every Profile G artifact kind in §5 **MUST** include:

| Field | Type | Rules |
| --- | --- | --- |
| `schema` | string | Exactly `mcp++/profile-g/<kind-slug>@1` for that kind. |
| `created_at_ms` | integer | Non-negative unix milliseconds (informational). |
| `parents` | CID[] | Sorted unique; length `0…max_parents` (default 32). Causal links only—**not** wall-clock order. |
| `correlation_id` | string | Non-empty, ≤128 bytes, no NUL. |

Unknown fields **MUST** be rejected (`G_INVALID_ARTIFACT`). Missing required
fields **MUST** be rejected. Empty strings and NULs in strings **MUST** be
rejected.

### 4.3 Size and numeric limits (defaults)

| Limit | Default |
| --- | --- |
| `max_artifact_bytes` | 1 048 576 |
| `max_parents` | 32 |
| `max_dependencies` | 256 |
| `max_evidence` | 256 |
| `max_neighbors` | 64 |
| `min_lease_ms` | 5 000 |
| `max_lease_ms` | 300 000 |
| Millionths range | `0…1_000_000` inclusive |
| Safe integer range | `0…2^53-1` unless a field allows signed values in `±(2^53-1)` |

Exceeding limits **MUST** fail with `G_LIMIT_EXCEEDED` where specified, else
`G_INVALID_ARTIFACT`.

### 4.4 Millionths discipline

Scores, weights, capacities, confidence, and fitness **MUST** be integers in
millionths of full scale (`0` = 0%, `1_000_000` = 100%). Implementations
**MUST NOT** introduce floating-point fields on the Profile G wire.

### 4.5 DID and signature fields

- DIDs **MUST** match `did:<method>:<id>` with the codec’s DID regex.
- Where `signer_did`, `signature_alg`, and `signature` appear, the structural
  codec **MUST** require non-empty strings. Cryptographic verification of
  `signature` is **not** required for structural conformance; trust validation
  **MAY** additionally resolve the signer DID and verify (REQ-G-02, higher level).

---

## 5. Artifact kinds (normative field sets)

Kind names are codec identifiers. Schema slugs appear in `schema`.

| Kind | Schema marker |
| --- | --- |
| `Goal` | `mcp++/profile-g/goal@1` |
| `Subgoal` | `mcp++/profile-g/subgoal@1` |
| `PlanBranch` | `mcp++/profile-g/plan-branch@1` |
| `PlanSelection` | `mcp++/profile-g/plan-selection@1` |
| `TaskSpec` | `mcp++/profile-g/task@1` |
| `RiskModel` | `mcp++/profile-g/risk-model@1` |
| `RiskEvidence` | `mcp++/profile-g/risk-evidence@1` |
| `RiskAssessment` | `mcp++/profile-g/risk-assessment@1` |
| `NeighborhoodRecord` | `mcp++/profile-g/neighborhood-record@1` |
| `NeighborhoodAttestation` | `mcp++/profile-g/neighborhood-attestation@1` |
| `ScheduleProposal` | `mcp++/profile-g/schedule-proposal@1` |
| `TaskClaim` | `mcp++/profile-g/task-claim@1` |
| `ClaimResolution` | `mcp++/profile-g/claim-resolution@1` |
| `TaskReceipt` | `mcp++/profile-g/task-receipt@1` |

### 5.1 Goal

| Field | Type | Notes |
| --- | --- | --- |
| `owner_did` | DID | Goal owner. |
| `objective_cid` | CID | Objective document. |
| `policy_cid` | CID | Governing policy. |
| `parent_goal_cids` | CID[] | Sorted unique, 0…32. |
| `labels` | string[] | Sorted unique, 0…32; each ≤64 bytes. |

### 5.2 Subgoal

| Field | Type | Notes |
| --- | --- | --- |
| `goal_cid` | CID | Parent goal. |
| `parent_subgoal_cid` | CID \| null | Optional hierarchy. |
| `objective_cid` | CID | |
| `decomposition_method` | string | ≤128 bytes. |
| `decomposer_cid` | CID | |
| `selection_cid` | CID \| null | Selected plan when known. |

### 5.3 PlanBranch

| Field | Type | Notes |
| --- | --- | --- |
| `subgoal_cid` | CID | |
| `candidate_input_cids` | CID[] | Sorted unique, 0…64. |
| `task_template_cids` | CID[] | Sorted unique, 1…256. |
| `evaluator_cid` | CID | |
| `score_millionths` | millionths | Branch fitness. |
| `explanation_cid` | CID | |

### 5.4 PlanSelection

| Field | Type | Notes |
| --- | --- | --- |
| `subgoal_cid` | CID | |
| `plan_branch_cid` | CID | Chosen branch. |
| `selector_did` | DID | |
| `proof_cid` | CID | Authority/proof binding. |
| `policy_decision_cid` | CID | Profile D decision. |
| `reason_cid` | CID | |

### 5.5 TaskSpec

| Field | Type | Notes |
| --- | --- | --- |
| `subgoal_cid` | CID | |
| `plan_branch_cid` | CID | |
| `selection_cid` | CID | |
| `interface_cid` | CID | MCP-IDL / tool interface. |
| `input_cid` | CID | |
| `tool` | string | ≤256 bytes. |
| `dependency_task_cids` | CID[] | Sorted unique, 0…`max_dependencies`. |
| `idempotency_key` | string | ≤128 bytes; scopes retries. |
| `resource_class` | string | ≤128 bytes. |
| `deadline_ms` | int \| null | Absolute deadline when set. |
| `expected_value_millionths` | millionths | Scheduler value signal. |
| `max_attempts` | int | 1…100. |
| `execution_mode` | enum | `idempotent` \| `compensatable` \| `exclusive`. |

**Execution modes (normative):**

| Mode | Meaning |
| --- | --- |
| `idempotent` | Duplicate successful completions with identical outputs MAY collapse; conflicting outputs are errors. |
| `compensatable` | Failure MAY require compensation path (`next_state: compensation-required`). |
| `exclusive` | At most one successful completion per task identity under fencing; majority resolution required before lease (§8). |

### 5.6 RiskModel

| Field | Type | Notes |
| --- | --- | --- |
| `name` | string | |
| `version` | string | |
| `factor_names` | string[] | Sorted unique, 1…64. |
| `weight_millionths` | map | Keys **exactly** `factor_names`; values millionths; at least one non-zero weight. |
| `saturation_millionths` | map | Keys **exactly** `factor_names`; values 1…1_000_000. |
| `algorithm` | enum | Only `weighted-saturated-sum-v1` in 1.0. |
| `missing_evidence` | enum | `deny` \| `challenge` \| `max-risk`. |
| `max_history_events` | int | 1…`max_evidence`. |
| `risk_buckets` | int[] | Strictly increasing millionths thresholds; last entry **MUST** be `1_000_000`. |

### 5.7 RiskEvidence

| Field | Type | Notes |
| --- | --- | --- |
| `subject_cid` | CID | Entity or task under observation. |
| `evidence_type` | enum | See below. |
| `observed_cids` | CID[] | Sorted unique, 1…`max_evidence`. |
| `observer_did` | DID | |
| `observed_at_ms` | int | |
| `expires_at_ms` | int | **MUST** be `> observed_at_ms`. |
| `classification` | enum | `public` \| `trust-domain` \| `confidential` \| `restricted`. |
| `redacted_cid` | CID \| null | Redacted view when classification requires it. |
| `signer_did` | DID | |
| `signature_alg` | string | Structural. |
| `signature` | string | Structural. |

**`evidence_type` closed set:**  
`policy-denial`, `authority-failure`, `obligation-overdue`, `execution-failure`,
`timeout`, `resource-overrun`, `dispute`, `rollback`, `archive-inclusion`,
`capacity-health`.

Immutable Event DAG history is the preferred evidence substrate: once artifacts
are CID-native, risk **SHOULD** be derived from that history rather than
ephemeral logs.

### 5.8 RiskAssessment

| Field | Type | Notes |
| --- | --- | --- |
| `task_cid` | CID | |
| `subject_did` | DID | Assessed principal. |
| `model_cid` | CID | RiskModel artifact. |
| `evidence_cids` | CID[] | Sorted unique, 0…`max_evidence`. |
| `factor_millionths` | map | Factor → millionths. |
| `score_millionths` | millionths | Aggregate score. |
| `confidence_millionths` | millionths | |
| `action` | enum | `allow` \| `challenge` \| `review` \| `deny`. |
| `assessed_at_ms` | int | |
| `expires_at_ms` | int | |

Expired assessments **MUST NOT** authorize new claims.

### 5.9 NeighborhoodRecord

| Field | Type | Notes |
| --- | --- | --- |
| `peer_did` | DID | Advertised peer. |
| `interface_cids` | CID[] | Sorted unique, 1…128. |
| `resource_classes` | string[] | Sorted unique, 1…64. |
| `capacity_millionths` | millionths | Available capacity. |
| `health_evidence_cid` | CID | |
| `trust_domain_cid` | CID | Neighborhood / domain boundary. |
| `reachable_artifact_cids` | CID[] | Sorted unique, 0…128. |
| `valid_from_ms` | int | |
| `expires_at_ms` | int | |
| `signer_did` | DID | |
| `signature_alg` | string | Structural. |
| `signature` | string | Structural. |

Expired records **MUST NOT** be used as live candidates for new proposals.

### 5.10 NeighborhoodAttestation

| Field | Type | Notes |
| --- | --- | --- |
| `proposal_cid` | CID | ScheduleProposal under vote. |
| `attester_did` | DID | |
| `record_cid` | CID | Attester’s NeighborhoodRecord. |
| `verdict` | enum | `support` \| `challenge` \| `abstain`. |
| `reason_code` | string | ≤128 bytes. |
| `evidence_cid` | CID \| null | |
| `observed_epoch` | int | ≥1; logical epoch observed. |
| `expires_at_ms` | int | |
| `signer_did` | DID | |
| `signature_alg` | string | Structural. |
| `signature` | string | Structural. |

Attestations feed **majority_approval** math only for the declared set. They
**MUST NOT** be relabeled as BFT ballots.

### 5.11 ScheduleProposal

| Field | Type | Notes |
| --- | --- | --- |
| `task_cid` | CID | |
| `risk_assessment_cid` | CID | |
| `selection_policy_cid` | CID | |
| `policy_decision_cid` | CID | |
| `logical_epoch` | int | ≥1. |
| `priority_tuple` | 8-tuple | See §7. |
| `candidates` | object[] | 1…`max_neighbors`; ordered by `candidate_key` (§8.2). |

Each candidate object **MUST** contain:

| Field | Type |
| --- | --- |
| `peer_did` | DID |
| `record_cid` | CID |
| `capability_fit_millionths` | millionths |

### 5.12 TaskClaim

| Field | Type | Notes |
| --- | --- | --- |
| `task_cid` | CID | |
| `proposal_cid` | CID | |
| `claimant_did` | DID | |
| `record_cid` | CID | Claimant NeighborhoodRecord. |
| `logical_epoch` | int | ≥1. |
| `requested_lease_ms` | int | In `[min_lease_ms, max_lease_ms]`. |
| `risk_bucket` | int | ≥0; bucket index from RiskModel. |
| `capability_fit_millionths` | millionths | |
| `expected_finish_ms` | int | |
| `proof_cid` | CID | Profile C proof. |
| `policy_decision_cid` | CID | Profile D decision. |
| `attempt` | int | 1…100 (**TaskAttempt** counter). |

### 5.13 ClaimResolution

| Field | Type | Notes |
| --- | --- | --- |
| `task_cid` | CID | |
| `logical_epoch` | int | ≥1. |
| `considered_claim_cids` | CID[] | Sorted unique, 1…`max_neighbors`. |
| `accepted_claim_cid` | CID \| null | Required when `outcome=accepted`. |
| `outcome` | enum | `accepted` \| `conflict` \| `released` \| `expired` \| `completed`. |
| `fencing_token` | int | ≥1; see §9. |
| `lease_expires_at_ms` | int \| null | Required when `outcome=accepted`. |
| `attestation_cids` | CID[] | Sorted unique, 0…`max_neighbors`. |
| `quorum_policy_cid` | CID | Declared majority policy. |
| `policy_decision_cid` | CID | |
| `coordination_receipt_cid` | CID \| null | Optional durable receipt. |
| `retry_not_before_ms` | int | Fairness / backoff bound. |
| `resolver_did` | DID | |

### 5.14 TaskReceipt

| Field | Type | Notes |
| --- | --- | --- |
| `task_cid` | CID | |
| `claim_cid` | CID | |
| `resolution_cid` | CID | |
| `fencing_token` | int | ≥1; **MUST** match accepted resolution. |
| `profile_b_receipt_cid` | CID | Profile B / ExecutionReceipt binding. |
| `output_cid` | CID \| null | Required when `status=succeeded`. |
| `status` | enum | `succeeded` \| `failed` \| `cancelled` \| `compensated`. |
| `failure_class` | enum | `none` \| `retryable` \| `permanent` \| `policy` \| `authority` \| `fenced` \| `resource`. |
| `attempt` | int | 1…100. |
| `started_at_ms` | int | |
| `finished_at_ms` | int | |
| `resource_use_cid` | CID | |
| `provider` | string | |
| `provider_version` | string | |
| `next_state` | enum | `complete` \| `ready` \| `blocked` \| `compensation-required`. |

Adapters **MAY** map `TaskSpec` → `ExecutionEnvelope@1` and `TaskReceipt` →
`ExecutionReceipt@1` / `ExecutionResult@1` without rewriting historical Profile G
CIDs (`envelope_profile_g.py` / MCPP-032).

---

## 6. Protocol concepts (Lease, LogicalEpoch, FencingToken, TaskAttempt)

These are **first-class protocol concepts**. Some are fields embedded in
artifacts rather than independent kinds.

### 6.1 LogicalEpoch

A **LogicalEpoch** is a positive integer coordination generation for a task:

- Epoch `1` is the first claim generation after task creation.
- Higher epochs are opened only after an explicit prior-epoch **expiry** (or
  equivalent fail-closed release) is recorded in the Event DAG.
- Resolving epoch `N` when a prior accepted resolution already has
  `logical_epoch >= N` **MUST** be a no-op return of the prior resolution
  (idempotent), never a second exclusive winner.

### 6.2 Lease

A **Lease** is the exclusive-execution right granted by an accepted
`ClaimResolution`:

| Property | Rule |
| --- | --- |
| Holder | `accepted_claim_cid` claimant |
| Bound | `lease_expires_at_ms` (unix ms) |
| Clock | Negotiated `unix-ms-with-logical-epoch`; wall clock is informational; expiry events are durable DAG records |
| Renew | `mcp++/schedule/renew` MAY extend only while fence and claim remain current |
| Release | `mcp++/schedule/release` ends the lease without completion |
| Expiry | After `lease_expires_at_ms`, peers MUST emit/record `claim_expired` before takeover |

While a lease is unexpired, non-holders **MUST NOT** execute exclusive side
effects for that task.

### 6.3 FencingToken

A **FencingToken** is a positive integer that strictly increases across accepted
resolutions for a task:

```text
fencing_token' = max(logical_epoch, prior_fencing_token + 1)
```

(when no prior resolution exists, treat `prior_fencing_token` as `0`).

Completion and side-effecting execution **MUST** present the **current**
fencing token. Stale tokens **MUST** be rejected with `G_STALE_FENCE`
(REQ-G-04). Tokens **MUST** be strictly increasing across successive accepted
resolutions for the same task.

### 6.4 TaskAttempt

A **TaskAttempt** is the monotonic attempt counter (`attempt` on claims and
receipts), range 1…`max_attempts` from TaskSpec. Exhausting attempts without
success **MUST** stop automatic reclaim under the same proposal without a new
policy decision.

---

## 7. Risk scoring and priority (normative algorithms)

### 7.1 Weighted saturated sum (`weighted-saturated-sum-v1`)

For each factor name `n` in the model:

```text
saturated_n = min(1_000_000, factor_millionths[n] * 1_000_000 // saturation_millionths[n])
weighted   += weight_millionths[n] * saturated_n
total_w    += weight_millionths[n]
score       = min(1_000_000, weighted // total_w)
```

**Risk bucket** is the smallest index `i` such that `score <= risk_buckets[i]`.

Missing factors **MUST** follow `missing_evidence` (`deny` / `challenge` /
`max-risk`) before claim admission.

### 7.2 Priority tuple (frontier order)

`derive_priority_tuple` produces an 8-element tuple for `ScheduleProposal.priority_tuple`:

| Index | Component | Sort sense |
| --- | --- | --- |
| 0 | `0` if ready else `1` | lower first (ready work first) |
| 1 | `deadline_class` | lower first |
| 2 | risk action rank: allow=0, challenge=1, review=2, deny=3 | lower first |
| 3 | `-age_bucket` | older first |
| 4 | `-expected_value_millionths` | higher value first |
| 5 | `-resource_fit_millionths` | better fit first |
| 6 | `retry_not_before_ms` | earlier retry first |
| 7 | `task_cid` (CID string) | deterministic final tie-break |

Schedulers **MUST** order the ready frontier by this tuple lexicographically.
Priority queues (including Fibonacci heaps) are implementation details (§15).

### 7.3 Fairness and starvation

Implementations **MUST**:

1. Honor `retry_not_before_ms` (no busy-spin reclaim).
2. Age ready tasks (`age_bucket`) so lower-value work is not permanently starved
   when risk action is `allow`.
3. Report starved-task counts in release/performance evidence when claiming
   Profile G production readiness.
4. Prefer `challenge`/`review`/`deny` risk actions that **block** admission over
   silent reordering that hides policy outcomes.

---

## 8. Claims, conflict order, fitness, and majority

### 8.1 Claim lifecycle (exclusive mode)

```text
task_created
    → task_claimed (one or more peers, same logical_epoch)
    → claim_resolved (exactly one accepted claim per epoch when majority holds)
    → [optional claim_conflicted for losers]
    → execute under lease + fencing_token
    → task_completed | claim_expired | claim released
    → (on expiry) higher logical_epoch claims / takeover
    → reconcile frontiers after partitions heal
```

### 8.2 Candidate order (proposal)

Candidates in a `ScheduleProposal` **MUST** be sorted by ascending
`candidate_key`:

```text
(risk_bucket, -capability_fit_millionths, expected_finish_ms, peer_did_bytes, record_cid_bytes)
```

### 8.3 Claim conflict order (resolution winner)

Among claims considered in one epoch, the winner **MUST** be the minimum under
`claim_order_key`:

```text
(-logical_epoch, risk_bucket, -capability_fit_millionths, expected_finish_ms,
 claimant_did_bytes, claim_cid_bytes)
```

Notes:

- Higher epoch sorts first when mixed (should not happen inside one resolution).
- Lower risk bucket wins.
- Higher capability fit wins.
- Earlier `expected_finish_ms` wins.
- DID bytes then **claim CID bytes** are the final deterministic tie-break
  (CID-final tie-break conformance vector).

Losers **MUST** be recorded (e.g. `claim_conflicted`) with both winning and
losing claim CIDs. A loser **MUST NOT** execute exclusive side effects.

### 8.4 Majority / quorum requirements (fail-closed)

For `execution_mode: exclusive`:

1. Resolution **MUST** require a **reachable majority** of the declared
   neighborhood (three-peer harness: at least two of three peers reachable from
   the resolver).
2. If majority is unavailable (partition), resolution **MUST** fail with
   `G_COORDINATION_UNAVAILABLE` or `G_QUORUM_UNAVAILABLE`—**not** accept a
   minority lease.
3. Quorum policy is named by `quorum_policy_cid` on `ClaimResolution`.
4. Attestation threshold evaluation for `majority_approval` **MUST** use the
   declared member set and threshold from consensus evidence when bridged to
   `ConsensusPlugin@1`.

For `idempotent` / `compensatable` modes, local coordination **MAY** proceed
with weaker placement, but **MUST still** refuse to label results as BFT.

### 8.5 Capability fitness

`capability_fit_millionths` is the claimant’s self-declared or policy-evaluated
fit for the task’s `interface_cid` and `resource_class`. Resolvers **MUST** use
the claim field as input to `claim_order_key` and **MUST NOT** silently rewrite
it after the claim CID is published.

---

## 9. Expiry, takeover, fencing, and completion

### 9.1 Expiry

After `lease_expires_at_ms`:

1. Peers **MUST NOT** treat the lease as live.
2. An explicit `claim_expired` (or `ClaimResolution` with `outcome: expired`)
   **MUST** be durable before a higher-epoch claim is accepted.
3. Expiry of epoch `N` is the only legal parent path into epoch `N+1` takeover
   claims (in addition to the original task creation for epoch 1).

### 9.2 Takeover

Takeover **MUST**:

1. Reference the prior epoch expiry event as parent.
2. Open a new `logical_epoch`.
3. Run conflict order and majority again.
4. Issue a new strictly larger `fencing_token`.

### 9.3 Completion rules

On `complete` / successful terminal receipt:

| Condition | Required result |
| --- | --- |
| No accepted resolution | `G_NOT_FOUND` |
| Claim CID ≠ accepted claim **or** fencing token ≠ current | `G_STALE_FENCE` or `G_CLAIM_CONFLICT` |
| Lease expired | `G_STALE_FENCE` (stale fence / expired lease path) |
| Prior successful completion with same claim+output | Idempotent return of existing completion |
| Prior successful completion with different output | `G_COMPLETION_CONFLICT` |
| Valid current fence + unexpired lease + no prior success | Emit exactly one `task_completed` |

**Exactly one exclusive success:** After partitions heal, the durable Event DAG
**MUST** contain at most one successful exclusive completion for the task
(REQ-G-05). Dual completion is a release blocker.

### 9.4 Duplicate suppression

- Idempotent mutation keys (`idempotency_key` scoped by principal + method + key)
  **MUST** return the same `artifact_cid` with `replayed: true` on retries.
- Replaying the same Event DAG event **MUST NOT** inflate event counts.
- Rejected completion evidence with identical payload **MUST** be idempotent.

---

## 10. Reconciliation, restart, and Event DAG

### 10.1 Reconciliation

When partitions heal, peers **MUST** exchange content-addressed events until
frontiers converge:

1. Deliver parents before children (causal delivery).
2. Reject graphs with missing parents or cycles (`G_INVALID_ARTIFACT`).
3. A second full exchange after convergence **MUST** create no new events.
4. Archive boundaries, when present, **MUST** be advertised in bounded pages
   (`truncated`, `next_cursor`, `archive_boundaries`).

### 10.2 Restart

Process restart **MUST** rebuild claims, accepted resolutions, fencing tokens,
and terminal state from durable Event DAG / coordination store contents—not
from volatile memory alone. Three-peer conformance requires recovery of
accepted resolution and fence after store reload.

### 10.3 Event DAG linkage

All Profile G coordination events used for exclusive safety **MUST**:

- Carry CIDs that commit to canonical event bodies.
- List parents that precede children.
- Avoid duplicate event CIDs for distinct bodies.

Profile F compaction rules apply; coordination recovery **MUST** still surface
fence and terminal completion evidence.

---

## 11. Error codes

| Code | Meaning |
| --- | --- |
| `G_INVALID_ARTIFACT` | Schema/field/canonical failure |
| `G_CAPABILITY_NOT_NEGOTIATED` | Profile G not negotiated |
| `G_CID_MISMATCH` | Declared CID ≠ bytes |
| `G_AUTHORITY_DENIED` | Profile C rejected |
| `G_POLICY_DENIED` | Profile D rejected |
| `G_NOT_READY` | Dependencies / readiness |
| `G_IDEMPOTENCY_CONFLICT` | Same key, different body |
| `G_CLAIM_CONFLICT` | Claim/lease conflict |
| `G_LEASE_EXPIRED` | Lease past bound |
| `G_STALE_FENCE` | Fencing token not current |
| `G_COMPLETION_CONFLICT` | Competing terminal outputs |
| `G_COORDINATION_UNAVAILABLE` | Majority/neighborhood unavailable |
| `G_QUORUM_UNAVAILABLE` | Quorum policy unsatisfied |
| `G_LIMIT_EXCEEDED` | Size/lease/count limit |
| `G_PROVIDER_UNAVAILABLE` | Backend missing (retryable) |
| `G_EVIDENCE_INVALID` | Risk/attestation evidence unusable |
| `G_REDACTED` | Classification forbids disclosure |
| `G_NOT_FOUND` | Unknown task/claim |

Transport JSON-RPC mappings **SHOULD** use the numbers in accelerate/kit
`profile_g_transport` (`ERROR_NUMBERS`).

---

## 12. Transport parity and provider fallback

1. Semantic results for the same Profile G method and params **MUST** match
   across negotiated transports (`jsonrpc-http` and `mcp+p2p` when both are
   offered)—byte-identical semantic digest of the result object.
2. Provider chains **MAY** fall back (package → CLI → MCP, etc.) when a domain
   provider is unavailable; the successful adapter **MUST** be recorded on
   `TaskReceipt.provider` / `provider_version`.
3. Fallback **MUST NOT** bypass Profile C/D checks or fencing.

---

## 13. Composition with other profiles

| Profile | Composition rule |
| --- | --- |
| **B / ExecutionEnvelope** | TaskSpec/TaskReceipt adapt without silent CID breakage. |
| **C (UCAN)** | Proofs evaluated at claim and execution time; transport identity is not authority. |
| **D (Policy)** | `policy_decision_cid` required on claims/resolutions; deny fails closed. |
| **E (mcp+p2p)** | Optional carriage; same semantic results as HTTP when both offered. |
| **F (Event DAG)** | Parents and event CIDs are the durability substrate. |
| **H (x402)** | Payment **MUST NOT** grant a Profile G lease or execution authority. |
| **StateRef / ConsensusPlugin** | Neighborhood evidence only as `coordination` / `majority_approval`. |

Allow decision for a protected scheduled operation is the intersection:

```text
capability exists
AND Profile C authority valid
AND Profile D policy permits
AND Profile G claim/lease/fence valid when scheduled
AND Profile H commercial condition satisfied when required
```

---

## 14. Conformance

### 14.1 Structural (codec)

Implementations claiming Profile G **MUST** pass:

- `profile_g_artifacts_valid.json` / `profile_g_artifacts_invalid.json`
- Language codec tests for Py/TS/Go/Rust field sets, CID rules, and size limits

Schema acceptance alone is never “implemented” (ADR-0003).

### 14.2 Protocol

Implementations **MUST** pass protocol vectors including:

- capability negotiation
- wire method bindings
- mutation envelope shape
- same-epoch conflict order
- weighted-saturated risk calculation
- CID-final tie-break
- idempotent replay
- transport semantic parity

### 14.3 Three-peer exclusive safety

The durable three-peer scenario **MUST** demonstrate:

| Requirement | Evidence |
| --- | --- |
| Simultaneous claims | Deterministic single winner; loser conflicted |
| Partition | Isolated majority failure (`G_COORDINATION_UNAVAILABLE`) |
| Replay | Event/claim counts stable |
| Restart | Fence and resolution recovered |
| Expired takeover | Higher epoch + higher fence after expiry parent |
| Conflicting completion | Stale fence / completion conflict rejected; exactly one success |
| Reconciliation | Frontiers converge; second pass idle |
| Event DAG integrity | Parents precede children; CID commitment |

### 14.4 Honest labeling

Tests **MUST** fail if a neighborhood/coordination result is labeled `bft`.

---

## 15. Non-normative implementation guidance

The following remain **optional heuristics** and do **not** define wire
interoperability:

- Locality-sensitive hashing (LSH), Hamming sketches, k-NN overlays for peer
  discovery (archive §2).
- Fibonacci heaps (or other priority queues) for frontier maintenance when
  priorities change frequently (archive §3.1; original design chat misspelling
  “fibinocci heap” retained only as a search alias).
- Concrete sketch feature vectors for behavior signatures.

Interoperability requires the **artifact field sets**, **priority/claim order
keys**, **lease/fence/epoch rules**, and **majority fail-closed** behavior in
§4–§10—not a shared LSH parameter set.

### 15.1 Interface contracts and toolset slicing

Nodes **MAY** prioritize intents by interface CID and known MCP-IDL
compatibility, and **MAY** apply toolset slicing under a context budget. See
[mcp-idl.md](mcp-idl.md). Such slicing **MUST NOT** bypass risk action `deny`
or fencing checks.

### 15.2 Open research (non-normative)

- Standard sketches/feature vectors for cross-vendor discovery
- Privacy-preserving exchange of risk evidence beyond `classification` /
  `redacted_cid`
- Operational playbooks for escalating from `majority_approval` to
  `crash_consensus` / `bft` plugins under load

---

## 16. Security considerations

1. **Fail closed** on missing majority, expired lease, stale fence, missing
   mode/policy/proof, and unknown artifact fields.
2. **Never** treat neighborhood majority as BFT or global consensus.
3. **Never** let payment, transport PeerID, or TLS client cert mint a lease.
4. Redacted classifications **MUST NOT** leak restricted evidence over
   public channels (`G_REDACTED`).
5. Signature fields are structural until a trust layer verifies them; do not
   claim cryptographic attestation completeness from codec green alone.
6. Operators withdrawing Profile G from initialize metadata on fence or dual-
   completion failure is the correct incident response (see operations
   runbook)—do not rewrite history.

---

## 17. Document history

| Version | Status | Notes |
| --- | --- | --- |
| Draft (pre-1.0) | Superseded | Mostly non-normative risk/LSH notes; “neighborhood consensus” title without guarantee labels |
| MCP++ 1.0 / `ProfileGNormative@1` | **Normative** | MCPP-066: single reconciling specification; local coordination ≠ global consensus; codecs + three-peer rules inlined |

**End of Profile G normative specification.**

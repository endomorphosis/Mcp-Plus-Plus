# ConsensusPlugin@1 — Honest Guarantee Labels and Plugin Evidence

**Status:** Normative (MCP++ 1.0)  
**Interface:** `ConsensusPlugin@1`  
**Schema markers:** `mcp++/state/consensus-evidence@1`, `mcp++/state/consensus-result@1`  
**Runtime:** `ipfs_accelerate_py/mcp_server/mcplusplus/state/consensus_plugin.py`  
**Authority:** ADR-0004 §4 (`docs/architecture/decisions/0004-state-modes.md`); sealed plan KD-11; gate 12  
**Related:** `StateRef@1` (`state-ref.md`); Profile G risk/neighborhood (`risk-scheduling.md`); ADR-0004 mode enum

This document is the normative specification of **`ConsensusPlugin@1`**: the
contract that backs `StateRef@1` **`mode: consensus`**, the **plugin evidence**
format required for state transitions under that mode, and the **four honest
guarantee labels** that prevent Profile G neighborhood coordination from being
oversold as Byzantine fault tolerance.

---

## 1. Purpose and non-goals

### 1.1 Purpose

- Give every language runtime one closed set of consensus-class **guarantee
  labels** so evidence bundles cannot silently claim BFT for majority or
  neighborhood coordination.
- Define a portable **plugin evidence** record that `mode: consensus` providers
  must validate before accepting a state transition.
- Wire **Profile G neighborhood** records / attestations into that evidence
  format **only** under the guarantees neighborhood agreement actually provides
  (`coordination` and/or `majority_approval`).
- Supply a **deterministic test adapter** that exercises labels and majority
  math without claiming crash consensus or BFT.

### 1.2 Non-goals

- This document does **not** implement Raft, Paxos, PBFT, HotStuff, or any other
  production CFT/BFT engine. Those MAY plug in later under
  `crash_consensus` or `bft` with real evidence and tests.
- This document does **not** replace Profile G codecs, three-peer harnesses, or
  risk-scheduler priority signals (`risk-scheduling.md`).
- This document does **not** authorize silent merge of `single_authority` values
  across Event DAG branches (see MCPP-040 / `state-ref.md` §5).
- Schema acceptance alone is never “implemented” (ADR-0003).

---

## 2. Interface identity

| Field | Value |
| --- | --- |
| Interface label | `ConsensusPlugin@1` |
| Evidence schema marker | `mcp++/state/consensus-evidence@1` |
| Result schema marker | `mcp++/state/consensus-result@1` |
| Consistency mode served | `consensus` (closed StateRef@1 enum) |
| In-tree runtime | `ipfs_accelerate_py/mcp_server/mcplusplus/state/consensus_plugin.py` |
| Versioning rule | Breaking changes require `ConsensusPlugin@2` / new schema markers |

Documents that claim `ConsensusPlugin@1` MUST satisfy the fail-closed rules in
§3–§6.

---

## 3. Guarantee labels (normative, closed enum)

Consensus-class behavior is **not** a single boolean. Plugins and Profile G
coordination MUST use exactly one of the following **honest guarantee labels**
(snake_case wire form; no aliases):

| Label | Meaning (normative intent) | Typical use |
| --- | --- | --- |
| `coordination` | Best-effort ordering or scheduling alignment; **no** safety claim under crash or Byzantine faults. | Neighborhood clustering, local frontier sync, risk-scheduler signals |
| `majority_approval` | Threshold approval among a **declared peer set** under an honest-majority assumption **for that set only**; not global BFT. | Profile G neighborhood majority / attestation-style approval |
| `crash_consensus` | Agreement among non-Byzantine processes that may crash/recover (classic CFT). | Raft/Paxos-class plugins when so declared and tested |
| `bft` | Byzantine fault tolerance under a declared fault bound and membership. | **Only** when a plugin actually implements and tests BFT |

### 3.1 Fail-closed label rules

| Rule | Normative statement |
| --- | --- |
| Exhaustive set | Allowed guarantee labels for MCP++ 1.0 are **exactly** `coordination`, `majority_approval`, `crash_consensus`, `bft`. |
| Required on evidence | Plugin evidence for `mode: consensus` MUST carry exactly one label. Missing or unknown labels are **invalid**. |
| No free-text | Vendor-specific guarantee strings are **invalid** without a superseding ADR. |
| No silent upgrade | Implementations MUST NOT rewrite `coordination` or `majority_approval` evidence into `crash_consensus` or `bft`. Escalation requires a new plugin round, new evidence, and a new declared label. |
| BFT requires engine | Declaring `bft` without a real BFT engine (`implements_bft=true` and tested protocol) is a **fail-closed error**. |
| Profile G bound | Profile G neighborhood agreement is **`coordination` and/or `majority_approval` only**. Labeling a Profile G neighborhood result as `bft` is a **fail-closed error** (MCPP-039 acceptance; REQ-G-03; plan §11; ADR-0004 §4). |

**Acceptance (MCPP-039):** Tests fail if a neighborhood result is labeled BFT.
A deterministic test adapter is supplied.

### 3.2 Profile G is not BFT

Archive and plan language already state that neighborhood agreement is a
**coordination optimization**, not a global consensus requirement
(`risk-scheduling.md` §4; plan KD-11). Normative consequences:

1. Profile G `NeighborhoodRecord` / `NeighborhoodAttestation` flows that produce
   consensus-class state evidence MUST set `evidence_kind: neighborhood` and a
   guarantee in `{coordination, majority_approval}`.
2. Runtime helpers MUST raise when a caller attempts to label such a result
   `bft` or `crash_consensus`.
3. Peers MAY escalate from neighborhood coordination to a stronger plugin
   (`crash_consensus` or `bft`) when conflicts or risk thresholds demand it;
   escalation MUST change the declared guarantee label and evidence format—not
   silently upgrade claims on the same neighborhood ballots.

---

## 4. Plugin evidence format (normative)

### 4.1 Evidence record (`mcp++/state/consensus-evidence@1`)

Unless noted, field names are **snake_case** on the wire.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `schema` | string const | yes | MUST be `mcp++/state/consensus-evidence@1`. |
| `plugin_id` | string | yes | Stable plugin id (e.g. `mcp++/consensus/profile-g-neighborhood@1`). |
| `guarantee` | enum string | yes | Exactly one of the four labels in §3. |
| `state_id` | string | yes | Logical `StateRef@1` id the evidence applies to. |
| `proposal_cid` | CID string | yes | Content id of the proposed value / transition. |
| `evidence_kind` | enum string | yes | `neighborhood` \| `plugin` \| `test`. |
| `members` | string[] | yes | Declared peer/principal set (implementations SHOULD sort uniquely). |
| `approvals` | string[] | yes | Principals that supported the proposal. |
| `rejections` | string[] | yes | Principals that challenged / rejected. |
| `abstentions` | string[] | yes | Principals that abstained. |
| `threshold` | non-negative int | yes | Required approval count for majority-class evaluation; `0` for pure coordination. |
| `round_id` | string | yes | Round / epoch identifier (deterministic string form). |
| `source` | string | no | Provenance tag (`profile_g_neighborhood`, `deterministic_test_adapter`, …). |
| `metadata` | object | no | Non-authoritative annotations; MUST NOT redeclare a conflicting `guarantee`. |

### 4.2 Result record (`mcp++/state/consensus-result@1`)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `schema` | string const | yes | MUST be `mcp++/state/consensus-result@1`. |
| `plugin_id` | string | yes | Plugin that produced the result. |
| `guarantee` | enum string | yes | Same honest label as the evaluated evidence. |
| `state_id` | string | yes | Logical state id. |
| `proposal_cid` | CID string | yes | Evaluated proposal. |
| `accepted` | boolean | yes | Whether the transition is authorized under the declared guarantee. |
| `evidence_kind` | enum string | yes | Echo of evidence kind. |
| `approval_count` | non-negative int | yes | Count of member approvals considered. |
| `threshold` | non-negative int | yes | Threshold used (0 for pure coordination). |
| `members` | string[] | yes | Membership considered. |
| `reason` | string | no | Human-readable acceptance / rejection reason. |
| `round_id` | string | yes | Round identifier. |
| `source` | string | no | Provenance tag. |
| `evidence` | object | no | Embedded evidence snapshot. |

### 4.3 Mode rule

Under `StateRef@1` **`mode: consensus`**:

1. A write / state transition that depends on agreement MUST present valid plugin
   evidence matching the declared guarantee.
2. Absent evidence, or evidence whose label is invalid for its `evidence_kind`,
   the write **fails closed**.
3. Automatic multi-writer merge remains restricted to `crdt` mode (Automerge);
   consensus acceptance is not a substitute for CRDT merge semantics.

---

## 5. Profile G neighborhood wiring

### 5.1 Inputs

Neighborhood wiring consumes Profile G-style structures (field names align with
the Profile G codec inventory):

- **`NeighborhoodRecord`** — peer capacity / health advertisement
  (`peer_did`, interface CIDs, signatures, …). Used to help derive membership
  when an explicit member list is not supplied.
- **`NeighborhoodAttestation`** — ballot on a proposal
  (`attester_did`, `verdict` ∈ {`support`, `challenge`, `abstain`}, …).

The consensus plugin contract does **not** re-specify the full Profile G
artifact schemas; it only defines how ballots map into plugin evidence.

### 5.2 Mapping rules

| Attestation `verdict` | Evidence list |
| --- | --- |
| `support` | `approvals` |
| `challenge` | `rejections` |
| `abstain` | `abstentions` |

| Declared neighborhood guarantee | Acceptance rule |
| --- | --- |
| `coordination` | Best-effort: non-empty support MAY accept; **no** crash/Byzantine safety claim. |
| `majority_approval` | Simple majority among declared `members` (default threshold `⌊n/2⌋+1`), or an explicit non-negative `threshold`. Approvals from non-members are ignored. |
| `crash_consensus` | **Forbidden** for `evidence_kind: neighborhood`. |
| `bft` | **Forbidden** for `evidence_kind: neighborhood` (fail closed). |

### 5.3 Plugin id for G wiring

Default plugin id for neighborhood evidence:

```text
mcp++/consensus/profile-g-neighborhood@1
```

Source tag:

```text
profile_g_neighborhood
```

### 5.4 Escalation

When neighborhood majority is insufficient (conflicts, risk thresholds, or
policy), peers MAY open a **new** consensus plugin round with
`guarantee: crash_consensus` or `guarantee: bft` under a plugin that actually
implements those classes. The new round MUST:

1. Use a distinct `plugin_id` and evidence instance.
2. Declare the stronger label explicitly.
3. Not rewrite historical neighborhood evidence to the stronger label.

---

## 6. Plugin contract (runtime)

### 6.1 Abstract operations

A `ConsensusPlugin@1` implementation exposes at least:

| Operation | Responsibility |
| --- | --- |
| `plugin_id` | Stable identifier. |
| `guarantee` | Honest label this plugin actually provides. |
| `implements_bft` | `true` only for real BFT engines; default `false`. |
| `propose` | Open a round; return initial evidence (pre-ballots). |
| `record_ballot` | Record one principal’s verdict against evidence. |
| `evaluate` | Produce a `ConsensusResult` without upgrading labels. |
| `accept` | Evaluate and fail closed if not accepted. |

### 6.2 Deterministic test adapter

Interface id / plugin id:

```text
mcp++/consensus/deterministic-test@1
```

Normative properties:

| Property | Statement |
| --- | --- |
| Supported guarantees | `coordination` and `majority_approval` only. |
| BFT claim | **Never.** `implements_bft` is always `false`. Constructing the adapter with `guarantee: bft` is a fail-closed error. |
| Determinism | Membership and ballot sets are sorted uniquely; evaluation is independent of ballot interleaving order. |
| Neighborhood path | `evaluate_neighborhood` / `wire_neighborhood_result` refuse `bft` labels. |
| Purpose | Unit and API tests for honest labeling and majority math—not production CFT/BFT. |

---

## 7. Validation checklist

An implementation claims `ConsensusPlugin@1` only when all of the following hold:

1. Guarantee labels are exactly `coordination`, `majority_approval`,
   `crash_consensus`, `bft`.
2. Plugin evidence carries `schema: mcp++/state/consensus-evidence@1` and a
   single valid guarantee.
3. Profile G neighborhood results use `evidence_kind: neighborhood` and only
   `coordination` or `majority_approval`.
4. Attempting to label a neighborhood result `bft` fails closed.
5. `bft` is never declared without a real BFT engine.
6. A deterministic test adapter exists and does not claim BFT.
7. `mode: consensus` transitions without valid evidence fail closed.

---

## 8. Examples

### 8.1 Profile G majority approval (valid)

```json
{
  "schema": "mcp++/state/consensus-evidence@1",
  "plugin_id": "mcp++/consensus/profile-g-neighborhood@1",
  "guarantee": "majority_approval",
  "state_id": "state:demo/neighborhood-head",
  "proposal_cid": "bafkreifzjut3te2nhyekklss27nh3k72ysco7y32koao5eei66wof36n5e",
  "evidence_kind": "neighborhood",
  "members": ["did:key:peer-a", "did:key:peer-b", "did:key:peer-c"],
  "approvals": ["did:key:peer-a", "did:key:peer-b"],
  "rejections": [],
  "abstentions": ["did:key:peer-c"],
  "threshold": 2,
  "round_id": "epoch-7",
  "source": "profile_g_neighborhood",
  "metadata": { "profile_g": true }
}
```

### 8.2 Neighborhood labeled BFT (MUST reject)

```json
{
  "schema": "mcp++/state/consensus-evidence@1",
  "plugin_id": "mcp++/consensus/profile-g-neighborhood@1",
  "guarantee": "bft",
  "state_id": "state:demo/neighborhood-head",
  "proposal_cid": "bafkreifzjut3te2nhyekklss27nh3k72ysco7y32koao5eei66wof36n5e",
  "evidence_kind": "neighborhood",
  "members": ["did:key:peer-a", "did:key:peer-b", "did:key:peer-c"],
  "approvals": ["did:key:peer-a", "did:key:peer-b", "did:key:peer-c"],
  "rejections": [],
  "abstentions": [],
  "threshold": 2,
  "round_id": "epoch-7",
  "source": "profile_g_neighborhood"
}
```

**Why invalid:** Profile G neighborhood agreement is not Byzantine fault
tolerance. Runtimes MUST raise (e.g. `NeighborhoodGuaranteeError`) rather than
accept or rewrite the label.

### 8.3 Crash consensus plugin evidence (valid only for a CFT plugin)

```json
{
  "schema": "mcp++/state/consensus-evidence@1",
  "plugin_id": "mcp++/consensus/raft-local@1",
  "guarantee": "crash_consensus",
  "state_id": "state:demo/raft-value",
  "proposal_cid": "bafkreigh2akiscaildcqabsyg3dfr6chu3fgpregiymsck7e7aqa4s52zy",
  "evidence_kind": "plugin",
  "members": ["n1", "n2", "n3"],
  "approvals": ["n1", "n2"],
  "rejections": [],
  "abstentions": [],
  "threshold": 2,
  "round_id": "term-4-index-18",
  "source": "raft_local"
}
```

This shape is **not** valid with `evidence_kind: neighborhood`.

---

## 9. References

- ADR-0004 state modes / four guarantee labels —
  `ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/0004-state-modes.md`
- StateRef@1 modes and consensus mode backend —
  `ipfs_accelerate_py/mcplusplus/docs/spec/state-ref.md`
- Profile G systems layer (neighborhood as coordination optimization) —
  `ipfs_accelerate_py/mcplusplus/docs/spec/risk-scheduling.md`
- Sealed plan KD-11, gate 12, plan §11 non-claim —
  `docs/architecture/MCPPLUSPLUS_1_0_GAP_CLOSURE_PLAN.md`
- Traceability REQ-ST-04 / REQ-G-03 —
  `ipfs_accelerate_py/mcplusplus/docs/roadmap/mcplusplus-1.0-gap-closure.md`
- Runtime + deterministic test adapter —
  `ipfs_accelerate_py/mcp_server/mcplusplus/state/consensus_plugin.py`
- Label tests —
  `test/api/test_mcplusplus_state_consensus_labels.py`

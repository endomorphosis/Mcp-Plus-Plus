# Formal Claim Algebra v1

**Status:** Normative (vocabulary and product algebra)
**Release:** `formal-claim-algebra-v1`
**Schema:** `facp/formal-claim-algebra-v1@1`
**Owning task:** FACP-009
**Authority:** MCP++ normative semantics; repository adapters MUST NOT broaden this vocabulary

This specification defines the multidimensional **evidence product algebra**:
the closed, bounded, nonoverlapping claim vocabulary that becomes the only
production promotion authority for Formal Assurance Control Plane (FACP)
work. Later tasks define executable promotion rules (FACP-010), Lean encodings
(FACP-011/012), and language projections. This document does **not** claim
Lean-checked proofs.

## 1. Terminal safety statement

No evidence originating as a fixture, simulation, declaration, unchecked hash,
browser policy, expired delegation, stale receipt, or unknown external outcome
MAY be promoted into a live, authorized, observed, current production-success
claim.

Evidence is a **product** of independent dimensions. It is never a single
total ladder.

## 2. Evidence product

An `EvidenceEnvelope` is the Cartesian product of nine closed dimensions.
Every production claim that asserts support, success, verification, currency,
or release admissibility MUST carry an envelope (explicitly or through a
translation-validated projection). Missing dimensions default to the weakest
honest constructor for that dimension and NEVER invent stronger values.

```text
EvidenceEnvelope {
  origin:      absent | declared | fixture | simulated |
               hermetic_observed | live_observed
  integrity:   unchecked | structurally_valid | digest_valid | signature_valid
  authority:   unchecked | absent | valid | expired | revoked | denied
  policy:      unchecked | allowed | denied |
               allowed_with_obligations | indeterminate
  proof:       none | candidate | verified | refuted |
               unknown | verifier_unavailable
  freshness:   current | stale | superseded | withdrawn
  effect:      not_started | reserved | started | externally_unknown |
               observed | compensated | failed
  environment: hermetic | conditional | live
  review:      unreviewed | machine_reviewed | human_reviewed
}
```

### 2.1 Closure, bounds, and nonoverlap

| Property | Normative meaning |
| --- | --- |
| **Closed** | Only the constructors listed for each dimension are admissible. Unknown spellings fail closed. |
| **Bounded** | Each dimension has a finite enumerated carrier; ranks across dimensions are forbidden. |
| **Nonoverlapping** | Dimensions are distinct typed concerns. Identical English spellings in different dimensions (for example `authority.absent` vs `origin.absent`, or `policy.denied` vs `authority.denied`) are **not** interchangeable and do not imply each other. |

No dimension MAY be collapsed into another. No total order over the full
product is normative.

## 3. Dimension semantics

### 3.1 `origin` — provenance of the evidence bytes/values

| Value | Meaning |
| --- | --- |
| `absent` | No evidence artifact is present. |
| `declared` | A human or agent asserted a value without observation. |
| `fixture` | Deterministic test/fixture material. |
| `simulated` | Mock, MagicMock, demo, or simulated backend output. |
| `hermetic_observed` | Observed under hermetic controls without live external dependency. |
| `live_observed` | Observed against a live external system under live qualification. |

Relabeling `fixture` or `simulated` as `live_observed` is illegal.

### 3.2 `integrity` — authenticity of bytes/identity (not semantic truth)

| Value | Meaning |
| --- | --- |
| `unchecked` | No integrity check performed. |
| `structurally_valid` | Shape/schema validation only. |
| `digest_valid` | Cryptographic digest matches canonical bytes. |
| `signature_valid` | Digest validity plus authentic signature/attestation over those bytes. |

Digest or signature validity authenticates **bytes**, never semantic truth of
what those bytes claim.

### 3.3 `authority` — who may authorize the effect

| Value | Meaning |
| --- | --- |
| `unchecked` | Authority not evaluated. |
| `absent` | No delegation/token presented. |
| `valid` | Current, argument-bound, non-revoked authority. |
| `expired` | Previously valid authority past expiry. |
| `revoked` | Explicitly revoked. |
| `denied` | Authority evaluation denied the actor/action. |

Payment, browser consent, UI confirmation, and local policy objects do not
grant `authority.valid`.

### 3.4 `policy` — host policy decision (not browser projection)

| Value | Meaning |
| --- | --- |
| `unchecked` | Policy not evaluated by the host kernel. |
| `allowed` | Host policy allows the exact operation. |
| `denied` | Host policy denies. |
| `allowed_with_obligations` | Allowed only if named obligations remain satisfied. |
| `indeterminate` | Policy could not be decided; fail closed for effects. |

Browser-constructed `allow`/`consent`/`dry_run` fields are presentation inputs,
not `policy.allowed`.

### 3.5 `proof` — semantic truth status relative to a verifier

| Value | Meaning |
| --- | --- |
| `none` | No proof artifact. |
| `candidate` | Proof candidate not yet admitted by a current verifier. |
| `verified` | Admitted by a current, named verifier under stated assumptions. |
| `refuted` | Independently refuted. |
| `unknown` | Proof obligation unresolved. |
| `verifier_unavailable` | Required verifier cannot run; does not become `verified`. |

`unknown` and `candidate` NEVER silently become `verified`.

### 3.6 `freshness` — currency of the evidence relative to the claimed subject

| Value | Meaning |
| --- | --- |
| `current` | Bound to the exact current subject/tree/environment. |
| `stale` | Out of date relative to the claimed subject. |
| `superseded` | Replaced by a newer artifact. |
| `withdrawn` | Explicitly withdrawn. |

Historical campaign receipts are at best `stale` / `superseded`, never
`current` for a new tree.

### 3.7 `effect` — observation of the attempted effect

| Value | Meaning |
| --- | --- |
| `not_started` | No attempt. |
| `reserved` | Resources reserved; effect not started. |
| `started` | Effect started; outcome not independently observed. |
| `externally_unknown` | External outcome unknown; must not be treated as success. |
| `observed` | Independent observation of the effect outcome exists. |
| `compensated` | Compensating action recorded. |
| `failed` | Observed failure. |

`success: true` without `effect.observed` (or stronger closed outcome
`Verified`) is forbidden on migrated production paths.

### 3.8 `environment` — execution environment class

| Value | Meaning |
| --- | --- |
| `hermetic` | No live external dependency required. |
| `conditional` | Requires named host/capability gates. |
| `live` | Live external dependency under live qualification. |

`environment.live` alone is not live qualification; see §4.5.

### 3.9 `review` — review provenance

| Value | Meaning |
| --- | --- |
| `unreviewed` | No review record. |
| `machine_reviewed` | Automated review only. |
| `human_reviewed` | Explicit human review recorded. |

Human review cannot invent missing origin, integrity, authority, or effect
evidence.

## 4. Epistemic distinctions (normative non-collapse)

FACP vocabulary MUST keep the following concerns distinct. Conflating any pair
is an illegal promotion.

### 4.1 Discovery

**Discovery** is inventory or presence knowledge: a component, backend, file,
seed, or API was found. Discovery MAY populate documentation and inventories.
Discovery MUST NOT set `proof.verified`, `effect.observed`,
`origin.live_observed`, `authority.valid`, `freshness.current`, or
`environment.live` qualification.

Inventory facts, claim inventories, and defect corpora are discovery artifacts.
`discovery_is_not_completion` remains true.

### 4.2 Authenticity

**Authenticity** is the `integrity` dimension: structural validity, digests,
and signatures over bytes/identity. Authenticity answers “are these the claimed
bytes?” It does **not** answer “are the claims inside those bytes true?”

Pseudo-CIDs, truncated hashes, UUID placeholders, and HTML-escaped divergent
encodings fail authenticity and MUST remain `integrity.unchecked` or fail
closed before any truth claim.

### 4.3 Truth

**Truth** is the `proof` dimension under a named verifier and assumptions.
Solver candidates, heuristic ranks, and attestation wrappers are not
interchangeable with kernel-verified truth. Truth never overrides missing
observation or expired authority.

### 4.4 Observation

**Observation** is the `effect` dimension (and `origin.*_observed` when the
evidence itself was observed). Observation requires independent evidence that
an effect occurred or failed. Declared, fixture, and simulated outputs are not
observations of production effects.

### 4.5 Live qualification

**Live qualification** is the conjunction needed to treat a capability as
live-production-qualified. Minimally it requires:

- `environment.live`
- `origin.live_observed` (or an equivalent live observation receipt bound into
  the envelope)
- `freshness.current`
- current capability/admission evidence sufficient for the claimed operation
  (authority/policy as required by that operation)

Hermetic green tests, conditional inventory tiers, configuration-only backends,
and zero live-qualified backend counts are honest **non-live** states.
`production_supported` remains false when live qualification is absent.

## 5. Closed outcome algebra

Every effectful operation on a migrated production path MUST use exactly one
of the following outcomes. Generic boolean success fields are forbidden.

| Outcome | Meaning |
| --- | --- |
| `Unavailable` | Required capability/evidence absent. |
| `Rejected` | Admission, authority, or policy rejected the operation. |
| `Simulated` | Result produced under simulation/fixture/mock origin. |
| `Attempted` | Effect started without independent observation. |
| `Unknown` | External or recovery outcome unknown. |
| `Observed` | Effect independently observed. |
| `Verified` | Observed outcome plus required proof/admission obligations. |
| `Failed` | Observed failure. |
| `Compensated` | Compensating action recorded after a prior effect. |

Mapping guide for legacy booleans:

- `success: true` without observation → illegal; must become `Attempted`,
  `Unknown`, `Simulated`, or `Unavailable` as appropriate — never `Observed`
  or `Verified` by relabeling.
- `available: true` / `supported: true` from mocks or defaults → `Unavailable`
  or `Simulated`, never live qualification.
- `verified` / `proven` without current verifier evidence → `proof.candidate`,
  `proof.unknown`, or `proof.verifier_unavailable`, never `proof.verified`.

## 6. Promotion predicates (named; rules in FACP-010)

The kernel names these predicates. Their executable necessary conditions are
owned by FACP-010. This specification only fixes their names and the invariant
that each is a predicate over the evidence **product**, not a ladder rank.

| Predicate | Intended reading |
| --- | --- |
| `production_supported` | Live-qualified production support claim. |
| `effect_successful` | Effect observed successful under admission. |
| `proof_reusable` | Proof may be reused under current verifier/closure. |
| `receipt_authoritative` | Receipt may authorize downstream consumers. |
| `release_admissible` | Release/rights gate may pass. |

A legacy total-ladder rank alone NEVER satisfies any of these predicates.

## 7. Normative non-implications

The following implications are forbidden (fail closed):

1. `origin.fixture` ↛ `origin.live_observed`
2. `origin.simulated` ↛ `origin.live_observed`
3. `origin.declared` ↛ `effect.observed`
4. `integrity.digest_valid` ↛ `proof.verified` (digest ≠ semantic truth)
5. `integrity.signature_valid` ↛ `authority.valid` (authN of bytes ≠ authZ)
6. payment / confirmation token ↛ `authority.valid`
7. browser `policy` / `consent` / `allow` ↛ host `policy.allowed`
8. `proof.candidate` ↛ `proof.verified` without current verifier evidence
9. `environment.hermetic` ↛ `environment.live`
10. inventory/configuration support tier ↛ live qualification
11. `freshness.stale` receipt ↛ `freshness.current`
12. `effect.externally_unknown` ↛ `effect.observed` or outcome `Verified`
13. discovery / inventory presence ↛ completion, proof, or live qualification
14. human or machine review ↛ missing origin/effect/authority evidence
15. any single dimension value ↛ full-product production success

## 8. Seeded legacy claim mapping (conservative, no unsafe promotion)

Every seeded legacy claim from FACP-008 MUST map into this algebra without
acquiring dimensions it did not carry. Legacy ranks and booleans MAY inform at
most the dimensions listed below; all other dimensions stay at their weakest
honest defaults. No mapping below sets `production_supported`,
`effect_successful`, `proof_reusable`, `receipt_authoritative`, or
`release_admissible` by itself (`unsafe_promotion: false` for all rows).

### 8.1 Forbidden generic fields

| Legacy field | May inform | MUST NOT become | Closed outcome substitute |
| --- | --- | --- | --- |
| `success` | possibly `effect.started` only when an attempt is evidenced; otherwise no effect claim | `effect.observed`, outcome `Verified`, live success | `Unavailable` / `Attempted` / `Unknown` / `Simulated` / `Failed` |
| `available` | discovery / inventory presence only | `production_supported`, live qualification | `Unavailable` unless live-qualified |
| `supported` | inventory/configuration note only | `environment.live` + `origin.live_observed` | `Unavailable` or conditional inventory |
| `verified` | at most `proof.candidate` without current verifier | `proof.verified` | keep `candidate` / `unknown` / `verifier_unavailable` |
| `proven` | at most `proof.candidate` | `proof.verified` | same as `verified` |

### 8.2 Total-assurance ladders (explicit seeds)

| Seed ID | Legacy vocabulary | Informs at most | Forbidden fill-ins |
| --- | --- | --- | --- |
| `seed:ladder-accelerate-assurance-level` | `AssuranceLevel` (`unverified`/`candidate`/`solver_checked`/`kernel_verified`/`attested`) | `proof` only (`none`/`candidate`/`verified` approximately; attestation does not set authority) | `origin`, `environment`, `freshness`, `effect`, `authority`, `policy` |
| `seed:ladder-accelerate-database-repair-assurance-level` | repair `AssuranceLevel` (`none`/`heuristic`/`validated`/`solver_checked`/`kernel_verified`/`attested`) | `proof` only; `heuristic`/`validated` map to `candidate` or `unknown`, never `verified` | all other dimensions; must not diverge into a second normative ladder |
| `seed:ladder-accelerate-proof-status` | `ProofStatus` | `proof` and, when `STALE`, `freshness.stale`; refutation → `proof.refuted` | `origin`, `environment`, `effect`, `authority` |
| `seed:ladder-kit-backend-support-tier` | `BackendSupportTier` | discovery/inventory annotation only; conditional tier may note `environment.conditional` as **claim class**, not observation | live qualification, `origin.live_observed`, `production_supported` |

Compatibility rule: legacy ranks MUST NOT acquire evidence dimensions they did
not carry. Adapters that need a full envelope MUST leave unspecified dimensions
weak and fail closed on promotion predicates.

### 8.3 Kit honest distinctions (reference semantics)

| Kit distinction | FCA mapping | Unsafe promotion blocked |
| --- | --- | --- |
| Kernel VFS hermetic / conditional / live claim classes | `environment` claim class; live class still requires live qualification (§4.5) | hermetic green → live |
| Backend support tiers | inventory discovery only | registry presence → support |
| configured → selected provider states | discovery/config vs selectable; selected still needs current receipts | configured → selected → live |
| candidate / admitted / current proof roles | `proof.candidate` vs admitted authorization vs `freshness.current` head | candidate CID = authorization CID |
| receipt freshness | `freshness` | stale/empty receipts → current |
| zero live-qualified backends | honest non-live; `production_supported = false` | inventing live backends |

### 8.4 Defect-family coverage for every seeded corpus entry

Every FACP-008 defect corpus seed belongs to one primary family. Family rules
below cover every seed that lacks a more specific §8.2 row. Each rule sets
`unsafe_promotion: false`.

| Family | Legacy claim shape | Conservative FCA mapping | Blocked promotion |
| --- | --- | --- | --- |
| `false_success` | `success:true` / hardcoded support | outcome `Unavailable`/`Simulated`/`Attempted`/`Unknown`; `origin` fixture/simulated/declared | → `Observed`/`Verified`/live success |
| `mock_capability` | mock available/real labels | `origin.simulated`; outcome `Simulated` or `Unavailable` | → live capability / `live_observed` |
| `pseudo_cid` | raw/truncated/random hash as CID | `integrity.unchecked`; identity claim rejected | → content-identity / digest_valid CID |
| `import_effect` | import-time mutation presented as benign | discovery of impurity only; effect class not production-success | → production success / purity |
| `browser_authority` | browser allow/consent/dry-run | presentation input; `authority.unchecked`/`absent`; host policy unevaluated | → `authority.valid` / `policy.allowed` |
| `mutable_dependency` | floating branch/@main/nightly/lock conflict | release inputs non-current / unknown | → `release_admissible` |
| `stale_proof` | historical receipt / campaign tip | `freshness.stale` or `superseded` | → `freshness.current` / current qualification |
| `missing_recovery` | retry without lease/fence recovery | `effect.externally_unknown` or `Unknown` | → blind success / irreversible retry |
| `license_conflict` | conflicting/missing SPDX | rights unresolved; review may be `unreviewed` | → mechanical `release_admissible` |
| `hermetic_to_live` | hermetic/conditional as live | preserve `environment`; deny live qualification | → `production_supported` |
| `secret_flow` | secret/path into public evidence | out of product algebra scope except fail-closed public claims | → public `Verified` success carrying secrets |
| `canonicalization_conflict` | divergent encodings / pseudo identity | `integrity.unchecked` until CCC pin; inventory-only | → normative identity authority |
| `total_assurance_ladder` | single rank for many concerns | §8.2 proof-only (or inventory-only for support tiers) | → full-product live authorized observed success |

## 9. Machine-readable vocabulary (normative appendix)

Implementations and conformance tests MUST treat the following JSON object as
the closed vocabulary carrier for this release. Prose above is explanatory;
when prose and this block disagree, this block wins for enumerations, and the
terminal safety statement / non-implications win for promotion bans.

```json
{
  "schema": "facp/formal-claim-algebra-v1@1",
  "schema_version": 1,
  "release": "formal-claim-algebra-v1",
  "task_id": "FACP-009",
  "goal_id": "FACP-G110",
  "product_kind": "evidence_product",
  "total_ladder_forbidden": true,
  "discovery_is_not_completion": true,
  "lean_proof_claimed": false,
  "evidence_dimensions": {
    "origin": [
      "absent",
      "declared",
      "fixture",
      "simulated",
      "hermetic_observed",
      "live_observed"
    ],
    "integrity": [
      "unchecked",
      "structurally_valid",
      "digest_valid",
      "signature_valid"
    ],
    "authority": [
      "unchecked",
      "absent",
      "valid",
      "expired",
      "revoked",
      "denied"
    ],
    "policy": [
      "unchecked",
      "allowed",
      "denied",
      "allowed_with_obligations",
      "indeterminate"
    ],
    "proof": [
      "none",
      "candidate",
      "verified",
      "refuted",
      "unknown",
      "verifier_unavailable"
    ],
    "freshness": [
      "current",
      "stale",
      "superseded",
      "withdrawn"
    ],
    "effect": [
      "not_started",
      "reserved",
      "started",
      "externally_unknown",
      "observed",
      "compensated",
      "failed"
    ],
    "environment": [
      "hermetic",
      "conditional",
      "live"
    ],
    "review": [
      "unreviewed",
      "machine_reviewed",
      "human_reviewed"
    ]
  },
  "dimension_order": [
    "origin",
    "integrity",
    "authority",
    "policy",
    "proof",
    "freshness",
    "effect",
    "environment",
    "review"
  ],
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
  ],
  "promotion_predicates": [
    "production_supported",
    "effect_successful",
    "proof_reusable",
    "receipt_authoritative",
    "release_admissible"
  ],
  "forbidden_generic_fields_on_migrated_paths": [
    "success",
    "available",
    "supported",
    "verified",
    "proven"
  ],
  "epistemic_distinctions": {
    "discovery": {
      "definition": "Inventory or presence knowledge; never completion, proof, observation, or live qualification.",
      "may_set": [],
      "must_not_set": [
        "proof.verified",
        "effect.observed",
        "origin.live_observed",
        "authority.valid",
        "freshness.current",
        "environment.live_qualification"
      ]
    },
    "authenticity": {
      "definition": "integrity dimension over bytes/identity; not semantic truth.",
      "dimension": "integrity",
      "must_not_imply": ["proof.verified", "authority.valid"]
    },
    "truth": {
      "definition": "proof dimension under a named current verifier and assumptions.",
      "dimension": "proof",
      "must_not_imply": ["effect.observed", "origin.live_observed", "authority.valid"]
    },
    "observation": {
      "definition": "Independent effect observation and observed origins.",
      "dimensions": ["effect", "origin"],
      "requires_for_production_success": ["effect.observed"]
    },
    "live_qualification": {
      "definition": "Conjunction required before live production support claims.",
      "requires": [
        "environment.live",
        "origin.live_observed",
        "freshness.current"
      ],
      "zero_live_qualified_backends_is_honest_non_live": true
    }
  },
  "non_implications": [
    {"from": "origin.fixture", "to": "origin.live_observed"},
    {"from": "origin.simulated", "to": "origin.live_observed"},
    {"from": "origin.declared", "to": "effect.observed"},
    {"from": "integrity.digest_valid", "to": "proof.verified"},
    {"from": "integrity.signature_valid", "to": "authority.valid"},
    {"from": "payment_or_confirmation", "to": "authority.valid"},
    {"from": "browser_policy_consent_allow", "to": "policy.allowed"},
    {"from": "proof.candidate", "to": "proof.verified"},
    {"from": "environment.hermetic", "to": "environment.live"},
    {"from": "inventory_or_configuration_support", "to": "live_qualification"},
    {"from": "freshness.stale", "to": "freshness.current"},
    {"from": "effect.externally_unknown", "to": "effect.observed"},
    {"from": "discovery", "to": "completion_or_live_qualification"},
    {"from": "review.human_reviewed", "to": "missing_origin_effect_or_authority"},
    {"from": "single_dimension_value", "to": "production_success_product"}
  ],
  "legacy_claim_mappings": {
    "unsafe_promotion_default": false,
    "forbidden_generic_fields": {
      "success": {
        "informs": ["effect"],
        "max_effect": "started",
        "forbidden_outcomes": ["Observed", "Verified"],
        "unsafe_promotion": false
      },
      "available": {
        "informs": ["discovery"],
        "forbidden_predicates": ["production_supported"],
        "unsafe_promotion": false
      },
      "supported": {
        "informs": ["discovery"],
        "forbidden_predicates": ["production_supported"],
        "unsafe_promotion": false
      },
      "verified": {
        "informs": ["proof"],
        "max_proof": "candidate",
        "forbidden_proof": ["verified"],
        "unsafe_promotion": false
      },
      "proven": {
        "informs": ["proof"],
        "max_proof": "candidate",
        "forbidden_proof": ["verified"],
        "unsafe_promotion": false
      }
    },
    "by_seed_id": {
      "seed:ladder-accelerate-assurance-level": {
        "legacy": "AssuranceLevel",
        "informs": ["proof"],
        "value_map": {
          "unverified": "none",
          "none": "none",
          "candidate": "candidate",
          "solver_checked": "candidate",
          "solver_verified": "candidate",
          "kernel_verified": "verified",
          "attested": "verified"
        },
        "must_not_fill": [
          "origin",
          "integrity",
          "authority",
          "policy",
          "freshness",
          "effect",
          "environment",
          "review"
        ],
        "unsafe_promotion": false
      },
      "seed:ladder-accelerate-database-repair-assurance-level": {
        "legacy": "database_repair.AssuranceLevel",
        "informs": ["proof"],
        "value_map": {
          "none": "none",
          "heuristic": "candidate",
          "validated": "candidate",
          "solver_checked": "candidate",
          "kernel_verified": "verified",
          "attested": "verified"
        },
        "must_not_fill": [
          "origin",
          "integrity",
          "authority",
          "policy",
          "freshness",
          "effect",
          "environment",
          "review"
        ],
        "unsafe_promotion": false
      },
      "seed:ladder-accelerate-proof-status": {
        "legacy": "ProofStatus",
        "informs": ["proof", "freshness"],
        "value_map": {
          "unproved": {"proof": "none"},
          "candidate": {"proof": "candidate"},
          "solver_checked": {"proof": "candidate"},
          "kernel_verified": {"proof": "verified"},
          "validated_refuted": {"proof": "refuted"},
          "inconclusive": {"proof": "unknown"},
          "unsupported": {"proof": "verifier_unavailable"},
          "stale": {"proof": "unknown", "freshness": "stale"},
          "error": {"proof": "unknown"}
        },
        "must_not_fill": [
          "origin",
          "integrity",
          "authority",
          "policy",
          "effect",
          "environment",
          "review"
        ],
        "unsafe_promotion": false
      },
      "seed:ladder-kit-backend-support-tier": {
        "legacy": "BackendSupportTier",
        "informs": ["discovery"],
        "optional_environment_annotation": {
          "conditional": "conditional",
          "production": null,
          "configuration-only": null,
          "experimental": null,
          "unsupported": null
        },
        "notes": "Inventory tier is not live qualification; production tier without live receipts does not set environment.live or origin.live_observed.",
        "must_not_fill": [
          "origin",
          "integrity",
          "authority",
          "policy",
          "proof",
          "freshness",
          "effect",
          "review"
        ],
        "forbidden_predicates": ["production_supported"],
        "unsafe_promotion": false
      }
    },
    "by_family": {
      "false_success": {
        "informs": ["origin", "effect"],
        "typical_origin": ["declared", "fixture", "simulated"],
        "forbidden_outcomes": ["Observed", "Verified"],
        "unsafe_promotion": false
      },
      "mock_capability": {
        "informs": ["origin"],
        "forced_origin": "simulated",
        "forbidden_origin": ["live_observed", "hermetic_observed"],
        "unsafe_promotion": false
      },
      "pseudo_cid": {
        "informs": ["integrity"],
        "forced_integrity": "unchecked",
        "forbidden_integrity": ["digest_valid", "signature_valid"],
        "unsafe_promotion": false
      },
      "import_effect": {
        "informs": ["discovery"],
        "forbidden_predicates": ["effect_successful", "production_supported"],
        "unsafe_promotion": false
      },
      "browser_authority": {
        "informs": ["authority", "policy"],
        "max_authority": "absent",
        "max_policy": "unchecked",
        "forbidden_authority": ["valid"],
        "forbidden_policy": ["allowed", "allowed_with_obligations"],
        "unsafe_promotion": false
      },
      "mutable_dependency": {
        "informs": ["freshness"],
        "forbidden_predicates": ["release_admissible"],
        "unsafe_promotion": false
      },
      "stale_proof": {
        "informs": ["freshness"],
        "forced_freshness": "stale",
        "forbidden_freshness": ["current"],
        "unsafe_promotion": false
      },
      "missing_recovery": {
        "informs": ["effect"],
        "max_effect": "externally_unknown",
        "forbidden_outcomes": ["Observed", "Verified"],
        "unsafe_promotion": false
      },
      "license_conflict": {
        "informs": ["review"],
        "forbidden_predicates": ["release_admissible"],
        "unsafe_promotion": false
      },
      "hermetic_to_live": {
        "informs": ["environment"],
        "forbidden_predicates": ["production_supported"],
        "forbidden_environment_promotion": {"from": "hermetic", "to": "live"},
        "unsafe_promotion": false
      },
      "secret_flow": {
        "informs": [],
        "forbidden_predicates": ["receipt_authoritative", "release_admissible"],
        "unsafe_promotion": false
      },
      "canonicalization_conflict": {
        "informs": ["integrity"],
        "forced_integrity": "unchecked",
        "disposition_hint": "inventory_only_do_not_select",
        "unsafe_promotion": false
      },
      "total_assurance_ladder": {
        "informs": ["proof"],
        "coverage": "see by_seed_id for ladder seeds",
        "unsafe_promotion": false
      }
    },
    "kit_honest_distinctions": {
      "kernel_vfs_claim_classes": {
        "informs": ["environment"],
        "unsafe_promotion": false
      },
      "backend_support_tiers": {
        "informs": ["discovery"],
        "unsafe_promotion": false
      },
      "configured_selected_states": {
        "informs": ["discovery"],
        "unsafe_promotion": false
      },
      "proof_roles": {
        "informs": ["proof", "freshness"],
        "unsafe_promotion": false
      },
      "cas_wal_recovery": {
        "informs": ["effect", "freshness"],
        "unsafe_promotion": false
      },
      "receipt_freshness": {
        "informs": ["freshness"],
        "unsafe_promotion": false
      }
    }
  },
  "roadmap_defect_families": [
    "false_success",
    "mock_capability",
    "pseudo_cid",
    "import_effect",
    "browser_authority",
    "mutable_dependency",
    "stale_proof",
    "missing_recovery",
    "license_conflict",
    "hermetic_to_live",
    "secret_flow",
    "canonicalization_conflict",
    "total_assurance_ladder"
  ]
}
```

## 10. Conformance notes

1. Structural conformance for this task is
   `Mcp-Plus-Plus/tests-py/integration/test_formal_claim_algebra_spec.py`.
2. Executable promotion predicates and transition tables are FACP-010.
3. Lean definitions and illegal-promotion theorems are FACP-011/012; this
   document sets `lean_proof_claimed: false`.
4. Compatibility adapters (FACP-017) MUST implement the conservative mappings
   in §8 and MUST NOT broaden constructors or predicates.
5. Ambiguous-claim scanners (FACP-019) MUST treat the forbidden generic fields
   as reject-on-migrated-path.

## 11. Acceptance summary

| Criterion | Where satisfied |
| --- | --- |
| Closed vocabulary | §2, §5, §9 enumerations |
| Bounded carriers | finite enums per dimension/outcome |
| Nonoverlapping dimensions | §2.1 typed concerns; shared spellings are not shared meanings |
| Distinguishes discovery / authenticity / truth / observation / live qualification | §4 |
| Maps every seeded legacy claim without unsafe promotion | §8 + §9 `legacy_claim_mappings` covering all FACP-008 corpus families and explicit ladder seeds |

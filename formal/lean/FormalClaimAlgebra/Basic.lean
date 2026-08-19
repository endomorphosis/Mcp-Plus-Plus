/-!
# Formal Claim Algebra — basic definitions (FACP-011)

Closed, bounded evidence-product algebra matching
`facp/formal-claim-algebra-v1@1` and `facp/promotion-rules@1`.
Definitions are inductive with `DecidableEq`; transitions and
promotion predicates are decidable. No network dependencies.
-/

namespace FormalClaimAlgebra

/-- Normative dimension order (parity with promotion-rules). -/
def dimensionOrder : List String := ["origin", "integrity", "authority", "policy", "proof", "freshness", "effect", "environment", "review"]

/-- Normative promotion predicate order. -/
def predicateOrder : List String := ["production_supported", "effect_successful", "proof_reusable", "receipt_authoritative", "release_admissible"]

/-- Closed `origin` dimension. -/
inductive Origin where
  | absent
  | declared
  | fixture
  | simulated
  | hermetic_observed
  | live_observed
  deriving DecidableEq, Repr, Inhabited, BEq

/-- Constructor names for `origin` (parity table). -/
def originCtorNames : List String := ["absent", "declared", "fixture", "simulated", "hermetic_observed", "live_observed"]

/-- Closed `integrity` dimension. -/
inductive Integrity where
  | unchecked
  | structurally_valid
  | digest_valid
  | signature_valid
  deriving DecidableEq, Repr, Inhabited, BEq

/-- Constructor names for `integrity` (parity table). -/
def integrityCtorNames : List String := ["unchecked", "structurally_valid", "digest_valid", "signature_valid"]

/-- Closed `authority` dimension. -/
inductive Authority where
  | unchecked
  | absent
  | valid
  | expired
  | revoked
  | denied
  deriving DecidableEq, Repr, Inhabited, BEq

/-- Constructor names for `authority` (parity table). -/
def authorityCtorNames : List String := ["unchecked", "absent", "valid", "expired", "revoked", "denied"]

/-- Closed `policy` dimension. -/
inductive Policy where
  | unchecked
  | allowed
  | denied
  | allowed_with_obligations
  | indeterminate
  deriving DecidableEq, Repr, Inhabited, BEq

/-- Constructor names for `policy` (parity table). -/
def policyCtorNames : List String := ["unchecked", "allowed", "denied", "allowed_with_obligations", "indeterminate"]

/-- Closed `proof` dimension. -/
inductive Proof where
  | none
  | candidate
  | verified
  | refuted
  | unknown
  | verifier_unavailable
  deriving DecidableEq, Repr, Inhabited, BEq

/-- Constructor names for `proof` (parity table). -/
def proofCtorNames : List String := ["none", "candidate", "verified", "refuted", "unknown", "verifier_unavailable"]

/-- Closed `freshness` dimension. -/
inductive Freshness where
  | current
  | stale
  | superseded
  | withdrawn
  deriving DecidableEq, Repr, Inhabited, BEq

/-- Constructor names for `freshness` (parity table). -/
def freshnessCtorNames : List String := ["current", "stale", "superseded", "withdrawn"]

/-- Closed `effect` dimension. -/
inductive Effect where
  | not_started
  | reserved
  | started
  | externally_unknown
  | observed
  | compensated
  | failed
  deriving DecidableEq, Repr, Inhabited, BEq

/-- Constructor names for `effect` (parity table). -/
def effectCtorNames : List String := ["not_started", "reserved", "started", "externally_unknown", "observed", "compensated", "failed"]

/-- Closed `environment` dimension. -/
inductive Environment where
  | hermetic
  | conditional
  | live
  deriving DecidableEq, Repr, Inhabited, BEq

/-- Constructor names for `environment` (parity table). -/
def environmentCtorNames : List String := ["hermetic", "conditional", "live"]

/-- Closed `review` dimension. -/
inductive Review where
  | unreviewed
  | machine_reviewed
  | human_reviewed
  deriving DecidableEq, Repr, Inhabited, BEq

/-- Constructor names for `review` (parity table). -/
def reviewCtorNames : List String := ["unreviewed", "machine_reviewed", "human_reviewed"]

/-- Evidence envelope: Cartesian product of the nine closed dimensions. -/
structure EvidenceEnvelope where
  origin : Origin
  integrity : Integrity
  authority : Authority
  policy : Policy
  proof : Proof
  freshness : Freshness
  effect : Effect
  environment : Environment
  review : Review
  deriving DecidableEq, Repr, Inhabited, BEq

/-- Allowed same-dimension transitions for `origin` (parity edges). -/
def originAllowedEdges : List (String × String) :=
  [("absent", "declared"), ("absent", "fixture"), ("absent", "simulated"), ("absent", "hermetic_observed"), ("absent", "live_observed"), ("declared", "hermetic_observed"), ("declared", "live_observed"), ("hermetic_observed", "live_observed")]

/-- Decidable allowed-transition relation for `origin`. -/
def originAllowed (src dst : Origin) : Bool :=
  match src, dst with
  | .absent, .declared => true
  | .absent, .fixture => true
  | .absent, .simulated => true
  | .absent, .hermetic_observed => true
  | .absent, .live_observed => true
  | .declared, .hermetic_observed => true
  | .declared, .live_observed => true
  | .hermetic_observed, .live_observed => true
  | _, _ => false

/-- Forbidden same-dimension relabel edges for `origin` (parity edges). -/
def originForbiddenEdges : List (String × String) := [("fixture", "live_observed"), ("fixture", "hermetic_observed"), ("simulated", "live_observed"), ("simulated", "hermetic_observed")]

/-- Decidable forbidden-relabel relation for `origin`. -/
def originForbidden (src dst : Origin) : Bool :=
  match src, dst with
  | .fixture, .live_observed => true
  | .fixture, .hermetic_observed => true
  | .simulated, .live_observed => true
  | .simulated, .hermetic_observed => true
  | _, _ => false

/-- Allowed same-dimension transitions for `integrity` (parity edges). -/
def integrityAllowedEdges : List (String × String) :=
  [("unchecked", "structurally_valid"), ("unchecked", "digest_valid"), ("unchecked", "signature_valid"), ("structurally_valid", "digest_valid"), ("structurally_valid", "signature_valid"), ("digest_valid", "signature_valid")]

/-- Decidable allowed-transition relation for `integrity`. -/
def integrityAllowed (src dst : Integrity) : Bool :=
  match src, dst with
  | .unchecked, .structurally_valid => true
  | .unchecked, .digest_valid => true
  | .unchecked, .signature_valid => true
  | .structurally_valid, .digest_valid => true
  | .structurally_valid, .signature_valid => true
  | .digest_valid, .signature_valid => true
  | _, _ => false

/-- Forbidden same-dimension relabel edges for `integrity` (parity edges). -/
def integrityForbiddenEdges : List (String × String) := []

/-- Decidable forbidden-relabel relation for `integrity`. -/
def integrityForbidden (_src _dst : Integrity) : Bool := false

/-- Allowed same-dimension transitions for `authority` (parity edges). -/
def authorityAllowedEdges : List (String × String) :=
  [("unchecked", "absent"), ("unchecked", "valid"), ("unchecked", "expired"), ("unchecked", "revoked"), ("unchecked", "denied"), ("absent", "valid"), ("valid", "expired"), ("valid", "revoked"), ("valid", "denied")]

/-- Decidable allowed-transition relation for `authority`. -/
def authorityAllowed (src dst : Authority) : Bool :=
  match src, dst with
  | .unchecked, .absent => true
  | .unchecked, .valid => true
  | .unchecked, .expired => true
  | .unchecked, .revoked => true
  | .unchecked, .denied => true
  | .absent, .valid => true
  | .valid, .expired => true
  | .valid, .revoked => true
  | .valid, .denied => true
  | _, _ => false

/-- Forbidden same-dimension relabel edges for `authority` (parity edges). -/
def authorityForbiddenEdges : List (String × String) := [("expired", "valid"), ("revoked", "valid"), ("denied", "valid")]

/-- Decidable forbidden-relabel relation for `authority`. -/
def authorityForbidden (src dst : Authority) : Bool :=
  match src, dst with
  | .expired, .valid => true
  | .revoked, .valid => true
  | .denied, .valid => true
  | _, _ => false

/-- Allowed same-dimension transitions for `policy` (parity edges). -/
def policyAllowedEdges : List (String × String) :=
  [("unchecked", "allowed"), ("unchecked", "denied"), ("unchecked", "allowed_with_obligations"), ("unchecked", "indeterminate"), ("indeterminate", "allowed"), ("indeterminate", "denied"), ("allowed_with_obligations", "allowed"), ("allowed_with_obligations", "denied")]

/-- Decidable allowed-transition relation for `policy`. -/
def policyAllowed (src dst : Policy) : Bool :=
  match src, dst with
  | .unchecked, .allowed => true
  | .unchecked, .denied => true
  | .unchecked, .allowed_with_obligations => true
  | .unchecked, .indeterminate => true
  | .indeterminate, .allowed => true
  | .indeterminate, .denied => true
  | .allowed_with_obligations, .allowed => true
  | .allowed_with_obligations, .denied => true
  | _, _ => false

/-- Forbidden same-dimension relabel edges for `policy` (parity edges). -/
def policyForbiddenEdges : List (String × String) := [("denied", "allowed")]

/-- Decidable forbidden-relabel relation for `policy`. -/
def policyForbidden (src dst : Policy) : Bool :=
  match src, dst with
  | .denied, .allowed => true
  | _, _ => false

/-- Allowed same-dimension transitions for `proof` (parity edges). -/
def proofAllowedEdges : List (String × String) :=
  [("none", "candidate"), ("none", "unknown"), ("none", "verifier_unavailable"), ("candidate", "verified"), ("candidate", "refuted"), ("candidate", "unknown"), ("candidate", "verifier_unavailable"), ("unknown", "verified"), ("unknown", "refuted"), ("verifier_unavailable", "verified"), ("verified", "refuted"), ("verified", "unknown")]

/-- Decidable allowed-transition relation for `proof`. -/
def proofAllowed (src dst : Proof) : Bool :=
  match src, dst with
  | .none, .candidate => true
  | .none, .unknown => true
  | .none, .verifier_unavailable => true
  | .candidate, .verified => true
  | .candidate, .refuted => true
  | .candidate, .unknown => true
  | .candidate, .verifier_unavailable => true
  | .unknown, .verified => true
  | .unknown, .refuted => true
  | .verifier_unavailable, .verified => true
  | .verified, .refuted => true
  | .verified, .unknown => true
  | _, _ => false

/-- Forbidden same-dimension relabel edges for `proof` (parity edges). -/
def proofForbiddenEdges : List (String × String) := [("candidate", "verified")]

/-- Decidable forbidden-relabel relation for `proof`. -/
def proofForbidden (src dst : Proof) : Bool :=
  match src, dst with
  | .candidate, .verified => true
  | _, _ => false

/-- Allowed same-dimension transitions for `freshness` (parity edges). -/
def freshnessAllowedEdges : List (String × String) :=
  [("current", "stale"), ("current", "superseded"), ("current", "withdrawn"), ("stale", "superseded"), ("stale", "withdrawn"), ("superseded", "withdrawn")]

/-- Decidable allowed-transition relation for `freshness`. -/
def freshnessAllowed (src dst : Freshness) : Bool :=
  match src, dst with
  | .current, .stale => true
  | .current, .superseded => true
  | .current, .withdrawn => true
  | .stale, .superseded => true
  | .stale, .withdrawn => true
  | .superseded, .withdrawn => true
  | _, _ => false

/-- Forbidden same-dimension relabel edges for `freshness` (parity edges). -/
def freshnessForbiddenEdges : List (String × String) := [("stale", "current"), ("superseded", "current"), ("withdrawn", "current"), ("withdrawn", "stale")]

/-- Decidable forbidden-relabel relation for `freshness`. -/
def freshnessForbidden (src dst : Freshness) : Bool :=
  match src, dst with
  | .stale, .current => true
  | .superseded, .current => true
  | .withdrawn, .current => true
  | .withdrawn, .stale => true
  | _, _ => false

/-- Allowed same-dimension transitions for `effect` (parity edges). -/
def effectAllowedEdges : List (String × String) :=
  [("not_started", "reserved"), ("not_started", "started"), ("reserved", "started"), ("started", "externally_unknown"), ("started", "observed"), ("started", "failed"), ("externally_unknown", "observed"), ("externally_unknown", "failed"), ("externally_unknown", "compensated"), ("observed", "compensated"), ("failed", "compensated")]

/-- Decidable allowed-transition relation for `effect`. -/
def effectAllowed (src dst : Effect) : Bool :=
  match src, dst with
  | .not_started, .reserved => true
  | .not_started, .started => true
  | .reserved, .started => true
  | .started, .externally_unknown => true
  | .started, .observed => true
  | .started, .failed => true
  | .externally_unknown, .observed => true
  | .externally_unknown, .failed => true
  | .externally_unknown, .compensated => true
  | .observed, .compensated => true
  | .failed, .compensated => true
  | _, _ => false

/-- Forbidden same-dimension relabel edges for `effect` (parity edges). -/
def effectForbiddenEdges : List (String × String) := [("not_started", "observed"), ("externally_unknown", "observed")]

/-- Decidable forbidden-relabel relation for `effect`. -/
def effectForbidden (src dst : Effect) : Bool :=
  match src, dst with
  | .not_started, .observed => true
  | .externally_unknown, .observed => true
  | _, _ => false

/-- Allowed same-dimension transitions for `environment` (parity edges). -/
def environmentAllowedEdges : List (String × String) :=
  [("hermetic", "conditional"), ("conditional", "live")]

/-- Decidable allowed-transition relation for `environment`. -/
def environmentAllowed (src dst : Environment) : Bool :=
  match src, dst with
  | .hermetic, .conditional => true
  | .conditional, .live => true
  | _, _ => false

/-- Forbidden same-dimension relabel edges for `environment` (parity edges). -/
def environmentForbiddenEdges : List (String × String) := [("hermetic", "live"), ("conditional", "live")]

/-- Decidable forbidden-relabel relation for `environment`. -/
def environmentForbidden (src dst : Environment) : Bool :=
  match src, dst with
  | .hermetic, .live => true
  | .conditional, .live => true
  | _, _ => false

/-- Allowed same-dimension transitions for `review` (parity edges). -/
def reviewAllowedEdges : List (String × String) :=
  [("unreviewed", "machine_reviewed"), ("unreviewed", "human_reviewed"), ("machine_reviewed", "human_reviewed")]

/-- Decidable allowed-transition relation for `review`. -/
def reviewAllowed (src dst : Review) : Bool :=
  match src, dst with
  | .unreviewed, .machine_reviewed => true
  | .unreviewed, .human_reviewed => true
  | .machine_reviewed, .human_reviewed => true
  | _, _ => false

/-- Forbidden same-dimension relabel edges for `review` (parity edges). -/
def reviewForbiddenEdges : List (String × String) := []

/-- Decidable forbidden-relabel relation for `review`. -/
def reviewForbidden (_src _dst : Review) : Bool := false

/-- True when `dst` differs from `src` in exactly one dimension via an allowed edge. -/
def legalSingleDimensionTransition (src dst : EvidenceEnvelope) : Bool :=
  let o := (src.origin == dst.origin)
  let i := (src.integrity == dst.integrity)
  let a := (src.authority == dst.authority)
  let p := (src.policy == dst.policy)
  let pr := (src.proof == dst.proof)
  let f := (src.freshness == dst.freshness)
  let e := (src.effect == dst.effect)
  let env := (src.environment == dst.environment)
  let r := (src.review == dst.review)
  let changed : Nat :=
    (if o then 0 else 1) + (if i then 0 else 1) + (if a then 0 else 1) +
    (if p then 0 else 1) + (if pr then 0 else 1) + (if f then 0 else 1) +
    (if e then 0 else 1) + (if env then 0 else 1) + (if r then 0 else 1)
  if changed != 1 then false
  else if !o then originAllowed src.origin dst.origin
  else if !i then integrityAllowed src.integrity dst.integrity
  else if !a then authorityAllowed src.authority dst.authority
  else if !p then policyAllowed src.policy dst.policy
  else if !pr then proofAllowed src.proof dst.proof
  else if !f then freshnessAllowed src.freshness dst.freshness
  else if !e then effectAllowed src.effect dst.effect
  else if !env then environmentAllowed src.environment dst.environment
  else reviewAllowed src.review dst.review

/-- Unknown transitions are rejected (fail-closed). -/
def unknownTransitionPolicy : String := "reject"

/-- Necessary dimension values for `production_supported` (parity table). -/
def production_supportedNecessary : List (String × List String) := [
  ("origin", ["live_observed"]),
  ("integrity", ["digest_valid", "signature_valid"]),
  ("authority", ["valid"]),
  ("policy", ["allowed", "allowed_with_obligations"]),
  ("freshness", ["current"]),
  ("environment", ["live"])
  ]

/-- Dimension-only check for `production_supported` (evidence bag is external). -/
def production_supportedDimensions (e : EvidenceEnvelope) : Bool :=
  ((e.origin == .live_observed)) &&
  ((e.integrity == .digest_valid) || (e.integrity == .signature_valid)) &&
  ((e.authority == .valid)) &&
  ((e.policy == .allowed) || (e.policy == .allowed_with_obligations)) &&
  ((e.freshness == .current)) &&
  ((e.environment == .live))

/-- Necessary dimension values for `effect_successful` (parity table). -/
def effect_successfulNecessary : List (String × List String) := [
  ("origin", ["hermetic_observed", "live_observed"]),
  ("integrity", ["digest_valid", "signature_valid"]),
  ("authority", ["valid"]),
  ("policy", ["allowed", "allowed_with_obligations"]),
  ("freshness", ["current"]),
  ("effect", ["observed"])
  ]

/-- Dimension-only check for `effect_successful` (evidence bag is external). -/
def effect_successfulDimensions (e : EvidenceEnvelope) : Bool :=
  ((e.origin == .hermetic_observed) || (e.origin == .live_observed)) &&
  ((e.integrity == .digest_valid) || (e.integrity == .signature_valid)) &&
  ((e.authority == .valid)) &&
  ((e.policy == .allowed) || (e.policy == .allowed_with_obligations)) &&
  ((e.freshness == .current)) &&
  ((e.effect == .observed))

/-- Necessary dimension values for `proof_reusable` (parity table). -/
def proof_reusableNecessary : List (String × List String) := [
  ("integrity", ["digest_valid", "signature_valid"]),
  ("proof", ["verified"]),
  ("freshness", ["current"])
  ]

/-- Dimension-only check for `proof_reusable` (evidence bag is external). -/
def proof_reusableDimensions (e : EvidenceEnvelope) : Bool :=
  ((e.integrity == .digest_valid) || (e.integrity == .signature_valid)) &&
  ((e.proof == .verified)) &&
  ((e.freshness == .current))

/-- Necessary dimension values for `receipt_authoritative` (parity table). -/
def receipt_authoritativeNecessary : List (String × List String) := [
  ("origin", ["hermetic_observed", "live_observed"]),
  ("integrity", ["signature_valid"]),
  ("authority", ["valid"]),
  ("policy", ["allowed", "allowed_with_obligations"]),
  ("freshness", ["current"])
  ]

/-- Dimension-only check for `receipt_authoritative` (evidence bag is external). -/
def receipt_authoritativeDimensions (e : EvidenceEnvelope) : Bool :=
  ((e.origin == .hermetic_observed) || (e.origin == .live_observed)) &&
  ((e.integrity == .signature_valid)) &&
  ((e.authority == .valid)) &&
  ((e.policy == .allowed) || (e.policy == .allowed_with_obligations)) &&
  ((e.freshness == .current))

/-- Necessary dimension values for `release_admissible` (parity table). -/
def release_admissibleNecessary : List (String × List String) := [
  ("origin", ["hermetic_observed", "live_observed"]),
  ("integrity", ["signature_valid"]),
  ("authority", ["valid"]),
  ("policy", ["allowed", "allowed_with_obligations"]),
  ("proof", ["verified"]),
  ("freshness", ["current"]),
  ("review", ["machine_reviewed", "human_reviewed"])
  ]

/-- Dimension-only check for `release_admissible` (evidence bag is external). -/
def release_admissibleDimensions (e : EvidenceEnvelope) : Bool :=
  ((e.origin == .hermetic_observed) || (e.origin == .live_observed)) &&
  ((e.integrity == .signature_valid)) &&
  ((e.authority == .valid)) &&
  ((e.policy == .allowed) || (e.policy == .allowed_with_obligations)) &&
  ((e.proof == .verified)) &&
  ((e.freshness == .current)) &&
  ((e.review == .machine_reviewed) || (e.review == .human_reviewed))

/-- All five promotion predicates (dimension halves). -/
def promotionPredicateNames : List String := predicateOrder

/-- Evaluate a named promotion predicate on envelope dimensions. -/
def evalPredicateDimensions (name : String) (e : EvidenceEnvelope) : Bool :=
  match name with
  | "production_supported" => production_supportedDimensions e
  | "effect_successful" => effect_successfulDimensions e
  | "proof_reusable" => proof_reusableDimensions e
  | "receipt_authoritative" => receipt_authoritativeDimensions e
  | "release_admissible" => release_admissibleDimensions e
  | _ => false

/-- Negative rule identifiers mirrored from promotion-rules (names only). -/
def negativeRuleIds : List String := ["digest-to-truth", "payment-to-authority", "hermetic-to-live", "fixture-to-observed", "simulated-to-live-observed", "declared-to-observed", "signature-to-authority", "browser-policy-to-host-policy", "candidate-to-verified", "inventory-to-live-qualification", "stale-to-current", "externally-unknown-to-observed", "discovery-to-completion", "review-fills-missing-evidence", "single-dimension-to-production-success", "success-boolean-to-observed", "mutable-dependency-to-release", "license-conflict-to-release"]

/-- Required core non-implications. -/
def requiredNegativeRuleIds : List String := ["digest-to-truth", "payment-to-authority", "hermetic-to-live", "fixture-to-observed"]

end FormalClaimAlgebra


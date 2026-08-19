import FormalClaimAlgebra.Basic

/-!
# Formal Claim Algebra — illegal-promotion theorems (FACP-012)

Goal: FACP-G110. Bundle: facp/fca/lean-theorems.
Evidence: facp/illegal-promotion-proof@1.

Checked forbidden-relabel edges and cross-dimensional non-implications matching
`facp/formal-claim-algebra-v1@1` §7 and `facp/promotion-rules@1` negative rules.

Every theorem below is machine-checked. This module declares no `sorry`,
`admit`, or `axiom` escape hatches.
-/

namespace FormalClaimAlgebra

/-! ## Theorem registry (names mirrored by the FACP-012 integration test) -/

/-- Canonical theorem names covering every forbidden promotion in scope. -/
def forbiddenPromotionTheoremNames : List String := [
  -- Forbidden same-dimension relabel edges
  "fixture_not_to_live_observed",
  "fixture_not_to_hermetic_observed",
  "simulated_not_to_live_observed",
  "simulated_not_to_hermetic_observed",
  "expired_not_to_valid",
  "revoked_not_to_valid",
  "denied_not_to_valid",
  "policy_denied_not_to_allowed",
  "candidate_forbidden_without_verifier",
  "stale_not_to_current",
  "superseded_not_to_current",
  "withdrawn_not_to_current",
  "withdrawn_not_to_stale",
  "not_started_not_to_observed",
  "externally_unknown_forbidden_without_observation",
  "hermetic_not_to_live",
  "conditional_live_forbidden_without_qualification",
  -- Absolute forbidden ⇒ not allowed (dimensions without evidence-gated overlap)
  "origin_forbidden_implies_not_allowed",
  "authority_forbidden_implies_not_allowed",
  "policy_forbidden_implies_not_allowed",
  "freshness_forbidden_implies_not_allowed",
  "absolute_effect_forbidden_implies_not_allowed",
  -- Cross-dimensional / predicate non-implications (spec §7 + evidence subset)
  "digest_to_truth",
  "signature_to_authority",
  "declared_to_observed",
  "payment_to_authority",
  "browser_policy_to_host_policy",
  "candidate_to_verified",
  "inventory_to_live_qualification",
  "externally_unknown_to_observed",
  "discovery_to_completion",
  "review_fills_missing_evidence",
  "single_dimension_to_production_success",
  "success_boolean_to_observed",
  "mutable_dependency_to_release",
  "license_conflict_to_release",
  "unchecked_hash_not_production",
  "fixture_not_production_supported",
  "simulated_not_production_supported",
  "stale_receipt_not_production_supported",
  "expired_delegation_not_production_supported",
  "revoked_delegation_not_production_supported",
  -- General predicate guards used by non-implications
  "proof_reusable_requires_verified",
  "production_supported_requires_live_origin",
  "production_supported_requires_valid_authority",
  "production_supported_requires_current_freshness",
  "release_admissible_requires_verified_proof"
  ]

/-! ## Forbidden same-dimension edges (absolute relabel bans) -/

theorem fixture_not_to_live_observed :
    originAllowed .fixture .live_observed = false ∧
      originForbidden .fixture .live_observed = true := by native_decide

theorem fixture_not_to_hermetic_observed :
    originAllowed .fixture .hermetic_observed = false ∧
      originForbidden .fixture .hermetic_observed = true := by native_decide

theorem simulated_not_to_live_observed :
    originAllowed .simulated .live_observed = false ∧
      originForbidden .simulated .live_observed = true := by native_decide

theorem simulated_not_to_hermetic_observed :
    originAllowed .simulated .hermetic_observed = false ∧
      originForbidden .simulated .hermetic_observed = true := by native_decide

theorem expired_not_to_valid :
    authorityAllowed .expired .valid = false ∧
      authorityForbidden .expired .valid = true := by native_decide

theorem revoked_not_to_valid :
    authorityAllowed .revoked .valid = false ∧
      authorityForbidden .revoked .valid = true := by native_decide

theorem denied_not_to_valid :
    authorityAllowed .denied .valid = false ∧
      authorityForbidden .denied .valid = true := by native_decide

theorem policy_denied_not_to_allowed :
    policyAllowed .denied .allowed = false ∧
      policyForbidden .denied .allowed = true := by native_decide

/-- Evidence-gated: `candidate → verified` remains forbidden without verifier evidence. -/
theorem candidate_forbidden_without_verifier :
    proofForbidden .candidate .verified = true := by native_decide

theorem stale_not_to_current :
    freshnessAllowed .stale .current = false ∧
      freshnessForbidden .stale .current = true := by native_decide

theorem superseded_not_to_current :
    freshnessAllowed .superseded .current = false ∧
      freshnessForbidden .superseded .current = true := by native_decide

theorem withdrawn_not_to_current :
    freshnessAllowed .withdrawn .current = false ∧
      freshnessForbidden .withdrawn .current = true := by native_decide

theorem withdrawn_not_to_stale :
    freshnessAllowed .withdrawn .stale = false ∧
      freshnessForbidden .withdrawn .stale = true := by native_decide

theorem not_started_not_to_observed :
    effectAllowed .not_started .observed = false ∧
      effectForbidden .not_started .observed = true := by native_decide

/-- Evidence-gated: `externally_unknown → observed` forbidden without observation evidence. -/
theorem externally_unknown_forbidden_without_observation :
    effectForbidden .externally_unknown .observed = true := by native_decide

theorem hermetic_not_to_live :
    environmentAllowed .hermetic .live = false ∧
      environmentForbidden .hermetic .live = true := by native_decide

/-- Evidence-gated: `conditional → live` forbidden without live qualification evidence. -/
theorem conditional_live_forbidden_without_qualification :
    environmentForbidden .conditional .live = true := by native_decide

/-! ## Absolute forbidden edges are never allowed transitions -/

theorem origin_forbidden_implies_not_allowed (src dst : Origin)
    (h : originForbidden src dst = true) :
    originAllowed src dst = false := by
  cases src <;> cases dst <;> simp [originForbidden, originAllowed] at h ⊢

theorem authority_forbidden_implies_not_allowed (src dst : Authority)
    (h : authorityForbidden src dst = true) :
    authorityAllowed src dst = false := by
  cases src <;> cases dst <;> simp [authorityForbidden, authorityAllowed] at h ⊢

theorem policy_forbidden_implies_not_allowed (src dst : Policy)
    (h : policyForbidden src dst = true) :
    policyAllowed src dst = false := by
  cases src <;> cases dst <;> simp [policyForbidden, policyAllowed] at h ⊢

theorem freshness_forbidden_implies_not_allowed (src dst : Freshness)
    (h : freshnessForbidden src dst = true) :
    freshnessAllowed src dst = false := by
  cases src <;> cases dst <;> simp [freshnessForbidden, freshnessAllowed] at h ⊢

/-- Absolute effect ban `not_started → observed` is never an allowed edge. -/
theorem absolute_effect_forbidden_implies_not_allowed :
    effectForbidden .not_started .observed = true →
      effectAllowed .not_started .observed = false := by
  intro _; native_decide

/-! ## Shared weak / strong envelope builders for counterexamples -/

/-- Envelope that satisfies every dimension half of every promotion predicate. -/
def strongEnvelope : EvidenceEnvelope where
  origin := .live_observed
  integrity := .signature_valid
  authority := .valid
  policy := .allowed
  proof := .verified
  freshness := .current
  effect := .observed
  environment := .live
  review := .human_reviewed

/-- Fixture origin with otherwise strong dimensions (fixture evidence subset). -/
def fixtureEnvelope : EvidenceEnvelope :=
  { strongEnvelope with origin := .fixture, environment := .hermetic }

/-- Simulated origin with otherwise strong dimensions. -/
def simulatedEnvelope : EvidenceEnvelope :=
  { strongEnvelope with origin := .simulated, environment := .hermetic }

/-- Declared origin; effect left unobserved (declaration evidence subset). -/
def declaredEnvelope : EvidenceEnvelope :=
  { strongEnvelope with origin := .declared, effect := .not_started, environment := .hermetic }

/-- Unchecked integrity (unchecked-hash evidence subset). -/
def uncheckedHashEnvelope : EvidenceEnvelope :=
  { strongEnvelope with integrity := .unchecked }

/-- Digest-valid authenticity without verified proof (digest-to-truth). -/
def digestOnlyEnvelope : EvidenceEnvelope :=
  { strongEnvelope with integrity := .digest_valid, proof := .none }

/-- Signature-valid authenticity with absent authority (signature-to-authority). -/
def signatureOnlyEnvelope : EvidenceEnvelope :=
  { strongEnvelope with authority := .absent }

/-- Browser/host-policy gap: policy left unchecked (browser-policy evidence). -/
def browserPolicyEnvelope : EvidenceEnvelope :=
  { strongEnvelope with policy := .unchecked }

/-- Payment/peer non-authority: authority absent. -/
def paymentNonAuthorityEnvelope : EvidenceEnvelope :=
  { strongEnvelope with authority := .absent }

/-- Proof candidate without verifier admission. -/
def candidateProofEnvelope : EvidenceEnvelope :=
  { strongEnvelope with proof := .candidate }

/-- Inventory/config support tier: hermetic, non-live origin. -/
def inventoryEnvelope : EvidenceEnvelope :=
  { strongEnvelope with origin := .declared, environment := .hermetic, effect := .not_started }

/-- Stale receipt. -/
def staleReceiptEnvelope : EvidenceEnvelope :=
  { strongEnvelope with freshness := .stale }

/-- Expired delegation. -/
def expiredDelegationEnvelope : EvidenceEnvelope :=
  { strongEnvelope with authority := .expired }

/-- Revoked delegation. -/
def revokedDelegationEnvelope : EvidenceEnvelope :=
  { strongEnvelope with authority := .revoked }

/-- Externally unknown effect. -/
def unknownEffectEnvelope : EvidenceEnvelope :=
  { strongEnvelope with effect := .externally_unknown }

/-- Review present but origin/effect/authority missing. -/
def reviewOnlyEnvelope : EvidenceEnvelope where
  origin := .absent
  integrity := .signature_valid
  authority := .absent
  policy := .allowed
  proof := .verified
  freshness := .current
  effect := .not_started
  environment := .hermetic
  review := .human_reviewed

/-- Single-dimension origin-only product (ladder/single-dimension ban). -/
def originOnlyEnvelope : EvidenceEnvelope where
  origin := .live_observed
  integrity := .unchecked
  authority := .unchecked
  policy := .unchecked
  proof := .none
  freshness := .stale
  effect := .not_started
  environment := .hermetic
  review := .unreviewed

/-- Success-boolean stand-in: started effect without observation. -/
def successBooleanEnvelope : EvidenceEnvelope :=
  { strongEnvelope with effect := .started }

/-- Mutable-dependency stand-in: stale freshness blocks release. -/
def mutableDependencyEnvelope : EvidenceEnvelope :=
  { strongEnvelope with freshness := .stale }

/-- License-conflict stand-in: policy denied blocks release. -/
def licenseConflictEnvelope : EvidenceEnvelope :=
  { strongEnvelope with policy := .denied }

/-! ## Predicate guards -/

theorem proof_reusable_requires_verified (e : EvidenceEnvelope)
    (h : (e.proof == Proof.verified) = false) :
    proof_reusableDimensions e = false := by
  simp [proof_reusableDimensions, h]

theorem production_supported_requires_live_origin (e : EvidenceEnvelope)
    (h : (e.origin == Origin.live_observed) = false) :
    production_supportedDimensions e = false := by
  simp [production_supportedDimensions, h]

theorem production_supported_requires_valid_authority (e : EvidenceEnvelope)
    (h : (e.authority == Authority.valid) = false) :
    production_supportedDimensions e = false := by
  simp [production_supportedDimensions, h]

theorem production_supported_requires_current_freshness (e : EvidenceEnvelope)
    (h : (e.freshness == Freshness.current) = false) :
    production_supportedDimensions e = false := by
  simp [production_supportedDimensions, h]

theorem release_admissible_requires_verified_proof (e : EvidenceEnvelope)
    (h : (e.proof == Proof.verified) = false) :
    release_admissibleDimensions e = false := by
  simp [release_admissibleDimensions, h]

/-! ## Spec §7 / promotion-rules negative non-implications -/

/-- `integrity.digest_valid` ↛ `proof.verified` / `proof_reusable`. -/
theorem digest_to_truth :
    proof_reusableDimensions digestOnlyEnvelope = false ∧
      (digestOnlyEnvelope.proof == .verified) = false ∧
      (digestOnlyEnvelope.integrity == .digest_valid) = true := by native_decide

/-- `integrity.signature_valid` ↛ `authority.valid`. -/
theorem signature_to_authority :
    (signatureOnlyEnvelope.integrity == .signature_valid) = true ∧
      (signatureOnlyEnvelope.authority == .valid) = false ∧
      production_supportedDimensions signatureOnlyEnvelope = false ∧
      receipt_authoritativeDimensions signatureOnlyEnvelope = false := by native_decide

/-- `origin.declared` ↛ `effect.observed`. -/
theorem declared_to_observed :
    (declaredEnvelope.origin == .declared) = true ∧
      (declaredEnvelope.effect == .observed) = false ∧
      effect_successfulDimensions declaredEnvelope = false := by native_decide

/-- Payment/confirmation tokens do not grant `authority.valid` (dimension half). -/
theorem payment_to_authority :
    (paymentNonAuthorityEnvelope.authority == .valid) = false ∧
      production_supportedDimensions paymentNonAuthorityEnvelope = false ∧
      receipt_authoritativeDimensions paymentNonAuthorityEnvelope = false := by native_decide

/-- Browser policy/consent does not set host `policy.allowed` (dimension half). -/
theorem browser_policy_to_host_policy :
    (browserPolicyEnvelope.policy == .allowed) = false ∧
      (browserPolicyEnvelope.policy == .allowed_with_obligations) = false ∧
      production_supportedDimensions browserPolicyEnvelope = false := by native_decide

/-- `proof.candidate` ↛ `proof.verified` / reusable proof. -/
theorem candidate_to_verified :
    (candidateProofEnvelope.proof == .candidate) = true ∧
      (candidateProofEnvelope.proof == .verified) = false ∧
      proof_reusableDimensions candidateProofEnvelope = false ∧
      proofForbidden .candidate .verified = true := by native_decide

/-- Inventory/configuration support ↛ live qualification. -/
theorem inventory_to_live_qualification :
    (inventoryEnvelope.environment == .live) = false ∧
      (inventoryEnvelope.origin == .live_observed) = false ∧
      production_supportedDimensions inventoryEnvelope = false := by native_decide

/-- `effect.externally_unknown` ↛ `effect.observed`. -/
theorem externally_unknown_to_observed :
    (unknownEffectEnvelope.effect == .externally_unknown) = true ∧
      (unknownEffectEnvelope.effect == .observed) = false ∧
      effect_successfulDimensions unknownEffectEnvelope = false ∧
      effectForbidden .externally_unknown .observed = true := by native_decide

/-- Discovery/inventory presence ↛ completion / proof / live qualification. -/
theorem discovery_to_completion :
    production_supportedDimensions inventoryEnvelope = false ∧
      effect_successfulDimensions inventoryEnvelope = false ∧
      proof_reusableDimensions
        { inventoryEnvelope with proof := .none, integrity := .unchecked } = false := by native_decide

/-- Review cannot invent missing origin/effect/authority evidence. -/
theorem review_fills_missing_evidence :
    (reviewOnlyEnvelope.review == .human_reviewed) = true ∧
      (reviewOnlyEnvelope.origin == .live_observed) = false ∧
      (reviewOnlyEnvelope.effect == .observed) = false ∧
      (reviewOnlyEnvelope.authority == .valid) = false ∧
      production_supportedDimensions reviewOnlyEnvelope = false ∧
      effect_successfulDimensions reviewOnlyEnvelope = false := by native_decide

/-- Any single dimension value ↛ full-product production success. -/
theorem single_dimension_to_production_success :
    (originOnlyEnvelope.origin == .live_observed) = true ∧
      production_supportedDimensions originOnlyEnvelope = false ∧
      effect_successfulDimensions originOnlyEnvelope = false ∧
      proof_reusableDimensions originOnlyEnvelope = false ∧
      receipt_authoritativeDimensions originOnlyEnvelope = false ∧
      release_admissibleDimensions originOnlyEnvelope = false := by native_decide

/-- Generic `success:true` without observation ↛ `effect.observed`. -/
theorem success_boolean_to_observed :
    (successBooleanEnvelope.effect == .started) = true ∧
      (successBooleanEnvelope.effect == .observed) = false ∧
      effect_successfulDimensions successBooleanEnvelope = false := by native_decide

/-- Mutable/unpinned dependency stand-in ↛ `release_admissible`. -/
theorem mutable_dependency_to_release :
    (mutableDependencyEnvelope.freshness == .stale) = true ∧
      release_admissibleDimensions mutableDependencyEnvelope = false := by native_decide

/-- License conflict / denied policy ↛ `release_admissible`. -/
theorem license_conflict_to_release :
    (licenseConflictEnvelope.policy == .denied) = true ∧
      release_admissibleDimensions licenseConflictEnvelope = false := by native_decide

/-! ## Evidence-subset dedicated theorems -/

theorem unchecked_hash_not_production :
    (uncheckedHashEnvelope.integrity == .unchecked) = true ∧
      production_supportedDimensions uncheckedHashEnvelope = false ∧
      proof_reusableDimensions uncheckedHashEnvelope = false ∧
      receipt_authoritativeDimensions uncheckedHashEnvelope = false := by native_decide

theorem fixture_not_production_supported :
    (fixtureEnvelope.origin == .fixture) = true ∧
      production_supportedDimensions fixtureEnvelope = false ∧
      originForbidden .fixture .live_observed = true := by native_decide

theorem simulated_not_production_supported :
    (simulatedEnvelope.origin == .simulated) = true ∧
      production_supportedDimensions simulatedEnvelope = false ∧
      originForbidden .simulated .live_observed = true := by native_decide

theorem stale_receipt_not_production_supported :
    (staleReceiptEnvelope.freshness == .stale) = true ∧
      production_supportedDimensions staleReceiptEnvelope = false ∧
      freshnessForbidden .stale .current = true := by native_decide

theorem expired_delegation_not_production_supported :
    (expiredDelegationEnvelope.authority == .expired) = true ∧
      production_supportedDimensions expiredDelegationEnvelope = false ∧
      authorityForbidden .expired .valid = true := by native_decide

theorem revoked_delegation_not_production_supported :
    (revokedDelegationEnvelope.authority == .revoked) = true ∧
      production_supportedDimensions revokedDelegationEnvelope = false ∧
      authorityForbidden .revoked .valid = true := by native_decide

/-- Sanity: the strong envelope satisfies every dimension-half predicate. -/
theorem strong_envelope_satisfies_all_predicates :
    production_supportedDimensions strongEnvelope = true ∧
      effect_successfulDimensions strongEnvelope = true ∧
      proof_reusableDimensions strongEnvelope = true ∧
      receipt_authoritativeDimensions strongEnvelope = true ∧
      release_admissibleDimensions strongEnvelope = true := by native_decide

end FormalClaimAlgebra

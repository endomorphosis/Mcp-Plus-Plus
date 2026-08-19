//! FACP-013: executable Rust Formal Claim Algebra kernel tests.
//!
//! Acceptance:
//! - Rust accepts/rejects every normative vector.
//! - Illegal transitions cannot construct a success type through public APIs.
//! - Exhaustive closed carriers, transition parity, and canonical serialization.
//!
//! `lib.rs` is outside this task's edit scope, so the kernel module is loaded
//! via path include from `src/formal_claim_algebra.rs`.

#![forbid(unsafe_code)]

#[path = "../src/formal_claim_algebra.rs"]
mod formal_claim_algebra;

use formal_claim_algebra::*;
use std::collections::BTreeMap;
use std::str::FromStr;

#[test]
fn kernel_identity_matches_facp_013() {
    assert_eq!(VOCAB_SCHEMA, "facp/formal-claim-algebra-v1@1");
    assert_eq!(RULES_SCHEMA, "facp/promotion-rules@1");
    assert_eq!(TASK_ID, "FACP-013");
    assert_eq!(GOAL_ID, "FACP-G120");
    assert_eq!(BUNDLE, "facp/fca/rust");
    assert_eq!(UNKNOWN_TRANSITION_POLICY, "reject");
    assert_eq!(
        DIMENSION_ORDER,
        [
            "origin",
            "integrity",
            "authority",
            "policy",
            "proof",
            "freshness",
            "effect",
            "environment",
            "review"
        ]
    );
    assert_eq!(
        PREDICATE_ORDER,
        [
            "production_supported",
            "effect_successful",
            "proof_reusable",
            "receipt_authoritative",
            "release_admissible"
        ]
    );
}

#[test]
fn closed_carriers_reject_unknown_spellings() {
    assert!(Origin::from_str("live_observed").is_ok());
    assert!(matches!(
        Origin::from_str("LIVE_OBSERVED"),
        Err(FcaError::UnknownEnum { .. })
    ));
    assert!(matches!(
        Integrity::from_str("maybe_valid"),
        Err(FcaError::UnknownEnum { .. })
    ));
    assert!(matches!(
        Authority::from_str("payment"),
        Err(FcaError::UnknownEnum { .. })
    ));
    assert!(matches!(
        Policy::from_str("browser_allow"),
        Err(FcaError::UnknownEnum { .. })
    ));
    assert!(matches!(
        Proof::from_str("proven"),
        Err(FcaError::UnknownEnum { .. })
    ));
    assert!(matches!(
        Freshness::from_str("fresh"),
        Err(FcaError::UnknownEnum { .. })
    ));
    assert!(matches!(
        Effect::from_str("success"),
        Err(FcaError::UnknownEnum { .. })
    ));
    assert!(matches!(
        Environment::from_str("prod"),
        Err(FcaError::UnknownEnum { .. })
    ));
    assert!(matches!(
        Review::from_str("peer_reviewed"),
        Err(FcaError::UnknownEnum { .. })
    ));
    assert!(matches!(
        ClosedOutcome::from_str("Success"),
        Err(FcaError::UnknownEnum { .. })
    ));
    assert!(matches!(
        PromotionPredicate::from_str("supported"),
        Err(FcaError::UnknownEnum { .. })
    ));
}

#[test]
fn carrier_name_tables_are_exhaustive() {
    assert_eq!(Origin::names().len(), 6);
    assert_eq!(Integrity::names().len(), 4);
    assert_eq!(Authority::names().len(), 6);
    assert_eq!(Policy::names().len(), 5);
    assert_eq!(Proof::names().len(), 6);
    assert_eq!(Freshness::names().len(), 4);
    assert_eq!(Effect::names().len(), 7);
    assert_eq!(Environment::names().len(), 3);
    assert_eq!(Review::names().len(), 3);
    assert_eq!(ClosedOutcome::names().len(), 9);
    for name in Origin::names() {
        assert_eq!(Origin::from_str(name).unwrap().as_str(), *name);
    }
    for name in Proof::names() {
        assert_eq!(Proof::from_str(name).unwrap().as_str(), *name);
    }
    for name in ClosedOutcome::names() {
        assert_eq!(ClosedOutcome::from_str(name).unwrap().as_str(), *name);
    }
}

#[test]
fn canonical_serialization_round_trip_and_unknown_field_rejection() {
    let envelope = EvidenceEnvelope::strong_product();
    let json = envelope.to_canonical_json().expect("serialize");
    let parsed = EvidenceEnvelope::from_canonical_json(&json).expect("parse");
    assert_eq!(parsed, envelope);

    let bad = r#"{"origin":"absent","integrity":"unchecked","authority":"unchecked","policy":"unchecked","proof":"none","freshness":"stale","effect":"not_started","environment":"hermetic","review":"unreviewed","extra":true}"#;
    assert!(EvidenceEnvelope::from_canonical_json(bad).is_err());

    let mut map = envelope.to_dimension_map();
    map.insert("bogus".into(), "value".into());
    assert!(matches!(
        EvidenceEnvelope::from_dimension_map(&map),
        Err(FcaError::UnknownField(_))
    ));

    let mut incomplete: BTreeMap<String, String> = BTreeMap::new();
    incomplete.insert("origin".into(), "absent".into());
    assert!(matches!(
        EvidenceEnvelope::from_dimension_map(&incomplete),
        Err(FcaError::MissingField(_))
    ));
}

#[test]
fn every_normative_vector_accepts_or_rejects_as_expected() {
    let vectors = normative_vectors();
    assert!(
        vectors.len() >= 65,
        "expected full accept+reject suite, got {}",
        vectors.len()
    );
    let mut accept = 0usize;
    let mut reject = 0usize;
    for vector in &vectors {
        evaluate_normative_vector(vector).unwrap_or_else(|e| panic!("{e}"));
        match vector.expectation {
            VectorExpectation::Accept => accept += 1,
            VectorExpectation::Reject => reject += 1,
        }
    }
    assert!(accept >= 40, "accept count too low: {accept}");
    assert!(reject >= 20, "reject count too low: {reject}");
}

#[test]
fn illegal_transitions_cannot_construct_production_success() {
    let bag = EvidenceBag::all_normative();

    // Fixture cannot transition to live_observed, and cannot admit success.
    let fixture = EvidenceEnvelope {
        origin: Origin::Fixture,
        ..EvidenceEnvelope::strong_product()
    };
    assert!(transition_allowed(
        Dimension::Origin,
        "fixture",
        "live_observed",
        &bag
    )
    .is_err());
    assert!(ProductionSuccessClaim::try_admit(fixture.clone(), &bag).is_err());
    assert!(VerifiedClaim::try_admit(fixture, &bag).is_err());

    // Hermetic → live is absolutely forbidden even with live evidence.
    let hermetic = EvidenceEnvelope::weakest();
    assert!(apply_transition(&hermetic, Dimension::Environment, "live", &bag).is_err());

    // Expired authority cannot relabel to valid; success type stays unreachable.
    let expired = EvidenceEnvelope {
        authority: Authority::Expired,
        ..EvidenceEnvelope::strong_product()
    };
    assert!(apply_transition(&expired, Dimension::Authority, "valid", &bag).is_err());
    assert!(ProductionSuccessClaim::try_admit(expired, &bag).is_err());

    // Stale freshness cannot become current.
    let stale = EvidenceEnvelope {
        freshness: Freshness::Stale,
        ..EvidenceEnvelope::strong_product()
    };
    assert!(apply_transition(&stale, Dimension::Freshness, "current", &bag).is_err());
    assert!(ProductionSuccessClaim::try_admit(stale, &bag).is_err());

    // Candidate proof cannot become verified without verifier evidence.
    let empty = EvidenceBag::new();
    assert!(transition_allowed(Dimension::Proof, "candidate", "verified", &empty).is_err());
    let with_verifier = EvidenceBag::from_keys([
        "named_current_verifier",
        "verifier_admission_closure",
    ]);
    assert!(transition_allowed(
        Dimension::Proof,
        "candidate",
        "verified",
        &with_verifier
    )
    .is_ok());

    // Strong product + full evidence admits gated success types.
    let strong = EvidenceEnvelope::strong_product();
    let success = ProductionSuccessClaim::try_admit(strong.clone(), &bag).expect("admit");
    assert_eq!(success.outcome(), ClosedOutcome::Verified);
    assert_eq!(success.envelope(), &strong);
    let verified = VerifiedClaim::try_admit(strong.clone(), &bag).expect("verified");
    assert_eq!(verified.outcome(), ClosedOutcome::Verified);
    assert_eq!(verified.envelope(), &strong);

    let mut bag2 = EvidenceBag::new();
    bag2.insert("named_current_verifier");
    bag2.insert("verifier_admission_closure");
    assert!(bag2.contains_all(&["named_current_verifier", "verifier_admission_closure"]));
}

#[test]
fn dimension_predicate_parity_with_strong_and_weak_envelopes() {
    let strong = EvidenceEnvelope::strong_product();
    assert!(production_supported_dimensions(&strong));
    assert!(effect_successful_dimensions(&strong));
    assert!(proof_reusable_dimensions(&strong));
    assert!(receipt_authoritative_dimensions(&strong));
    assert!(release_admissible_dimensions(&strong));

    let weak = EvidenceEnvelope::weakest();
    assert!(!production_supported_dimensions(&weak));
    assert!(!effect_successful_dimensions(&weak));
    assert!(!proof_reusable_dimensions(&weak));
    assert!(!receipt_authoritative_dimensions(&weak));
    assert!(!release_admissible_dimensions(&weak));

    for pred in PromotionPredicate::all() {
        assert!(predicate_holds(pred, &strong, &EvidenceBag::all_normative()).is_ok());
        assert!(predicate_holds(pred, &weak, &EvidenceBag::all_normative()).is_err());
    }
}

#[test]
fn exhaustive_match_smoke_for_closed_outcomes_and_predicates() {
    // Exhaustive matches: adding a variant without updating these arms fails to compile.
    for outcome in [
        ClosedOutcome::Unavailable,
        ClosedOutcome::Rejected,
        ClosedOutcome::Simulated,
        ClosedOutcome::Attempted,
        ClosedOutcome::Unknown,
        ClosedOutcome::Observed,
        ClosedOutcome::Verified,
        ClosedOutcome::Failed,
        ClosedOutcome::Compensated,
    ] {
        let _ = match outcome {
            ClosedOutcome::Unavailable
            | ClosedOutcome::Rejected
            | ClosedOutcome::Simulated
            | ClosedOutcome::Attempted
            | ClosedOutcome::Unknown
            | ClosedOutcome::Observed
            | ClosedOutcome::Verified
            | ClosedOutcome::Failed
            | ClosedOutcome::Compensated => outcome.as_str(),
        };
    }
    for pred in PromotionPredicate::all() {
        let _ = match pred {
            PromotionPredicate::ProductionSupported
            | PromotionPredicate::EffectSuccessful
            | PromotionPredicate::ProofReusable
            | PromotionPredicate::ReceiptAuthoritative
            | PromotionPredicate::ReleaseAdmissible => necessary_evidence(pred),
        };
    }
}

#[test]
fn transition_table_counts_match_promotion_rules_parity() {
    assert_eq!(ORIGIN_ALLOWED.len(), 8);
    assert_eq!(ORIGIN_FORBIDDEN.len(), 4);
    assert_eq!(INTEGRITY_ALLOWED.len(), 6);
    assert_eq!(AUTHORITY_ALLOWED.len(), 9);
    assert_eq!(AUTHORITY_FORBIDDEN.len(), 3);
    assert_eq!(POLICY_ALLOWED.len(), 8);
    assert_eq!(POLICY_FORBIDDEN.len(), 1);
    assert_eq!(PROOF_ALLOWED.len(), 12);
    assert_eq!(PROOF_FORBIDDEN.len(), 1);
    assert_eq!(FRESHNESS_ALLOWED.len(), 6);
    assert_eq!(FRESHNESS_FORBIDDEN.len(), 4);
    assert_eq!(EFFECT_ALLOWED.len(), 11);
    assert_eq!(EFFECT_FORBIDDEN.len(), 2);
    assert_eq!(ENVIRONMENT_ALLOWED.len(), 2);
    assert_eq!(ENVIRONMENT_FORBIDDEN.len(), 2);
    assert_eq!(REVIEW_ALLOWED.len(), 3);
}

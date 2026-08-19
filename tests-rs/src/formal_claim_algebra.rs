//! Formal Claim Algebra (FCA) executable Rust kernel — FACP-013.
//!
//! Closed, bounded evidence-product algebra matching
//! `facp/formal-claim-algebra-v1@1` and `facp/promotion-rules@1`.
//!
//! Public APIs fail closed: unknown enum spellings are rejected, unknown
//! transitions are rejected, and production-success / verified claim types
//! cannot be constructed without satisfying the normative predicates and
//! evidence bag. There is no public unchecked success constructor.

#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::str::FromStr;
use thiserror::Error;

/// Normative vocabulary / rules identity carried by this kernel.
pub const VOCAB_SCHEMA: &str = "facp/formal-claim-algebra-v1@1";
/// Machine-readable promotion rules schema this kernel implements.
pub const RULES_SCHEMA: &str = "facp/promotion-rules@1";
/// Owning task for the executable Rust projection.
pub const TASK_ID: &str = "FACP-013";
/// Goal bundle for the runtime track.
pub const GOAL_ID: &str = "FACP-G120";
/// Bundle identifier.
pub const BUNDLE: &str = "facp/fca/rust";
/// Unknown transitions are always rejected.
pub const UNKNOWN_TRANSITION_POLICY: &str = "reject";

/// Normative dimension order.
pub const DIMENSION_ORDER: [&str; 9] = [
    "origin",
    "integrity",
    "authority",
    "policy",
    "proof",
    "freshness",
    "effect",
    "environment",
    "review",
];

/// Normative promotion predicate order.
pub const PREDICATE_ORDER: [&str; 5] = [
    "production_supported",
    "effect_successful",
    "proof_reusable",
    "receipt_authoritative",
    "release_admissible",
];

/// Kernel error / rejection codes (fail-closed).
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum FcaError {
    /// Unknown spelling for a closed dimension or predicate.
    #[error("unknown enum value for {dimension}: {value}")]
    UnknownEnum {
        /// Dimension or carrier name.
        dimension: &'static str,
        /// Rejected spelling.
        value: String,
    },
    /// Envelope JSON / map is missing a required dimension field.
    #[error("missing envelope field: {0}")]
    MissingField(&'static str),
    /// Extra/unknown envelope field (canonical parse rejects).
    #[error("unknown envelope field: {0}")]
    UnknownField(String),
    /// Same-dimension transition rejected.
    #[error("transition rejected ({code}): {dimension} {from} -> {to}")]
    TransitionRejected {
        /// Dimension name.
        dimension: &'static str,
        /// Source value.
        from: String,
        /// Destination value.
        to: String,
        /// Stable rejection code.
        code: String,
    },
    /// Promotion predicate does not hold.
    #[error("predicate rejected ({code}): {predicate}")]
    PredicateRejected {
        /// Predicate id.
        predicate: &'static str,
        /// Stable rejection code.
        code: String,
    },
    /// Closed outcome construction rejected.
    #[error("outcome rejected ({code}): {outcome}")]
    OutcomeRejected {
        /// Outcome name.
        outcome: &'static str,
        /// Stable rejection code.
        code: String,
    },
}

/// Closed `origin` dimension.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Origin {
    /// No evidence artifact is present.
    Absent,
    /// Human/agent assertion without observation.
    Declared,
    /// Deterministic test/fixture material.
    Fixture,
    /// Mock/demo/simulated backend output.
    Simulated,
    /// Observed under hermetic controls.
    HermeticObserved,
    /// Observed against a live external system.
    LiveObserved,
}

impl Origin {
    /// Normative constructor names.
    pub const fn names() -> &'static [&'static str] {
        &[
            "absent",
            "declared",
            "fixture",
            "simulated",
            "hermetic_observed",
            "live_observed",
        ]
    }

    /// Canonical snake_case spelling.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Absent => "absent",
            Self::Declared => "declared",
            Self::Fixture => "fixture",
            Self::Simulated => "simulated",
            Self::HermeticObserved => "hermetic_observed",
            Self::LiveObserved => "live_observed",
        }
    }
}

impl fmt::Display for Origin {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl FromStr for Origin {
    type Err = FcaError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "absent" => Ok(Self::Absent),
            "declared" => Ok(Self::Declared),
            "fixture" => Ok(Self::Fixture),
            "simulated" => Ok(Self::Simulated),
            "hermetic_observed" => Ok(Self::HermeticObserved),
            "live_observed" => Ok(Self::LiveObserved),
            other => Err(FcaError::UnknownEnum {
                dimension: "origin",
                value: other.to_string(),
            }),
        }
    }
}

/// Closed `integrity` dimension.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Integrity {
    /// No integrity check performed.
    Unchecked,
    /// Shape/schema validation only.
    StructurallyValid,
    /// Cryptographic digest matches canonical bytes.
    DigestValid,
    /// Digest validity plus authentic signature.
    SignatureValid,
}

impl Integrity {
    /// Normative constructor names.
    pub const fn names() -> &'static [&'static str] {
        &[
            "unchecked",
            "structurally_valid",
            "digest_valid",
            "signature_valid",
        ]
    }

    /// Canonical snake_case spelling.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Unchecked => "unchecked",
            Self::StructurallyValid => "structurally_valid",
            Self::DigestValid => "digest_valid",
            Self::SignatureValid => "signature_valid",
        }
    }
}

impl fmt::Display for Integrity {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl FromStr for Integrity {
    type Err = FcaError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "unchecked" => Ok(Self::Unchecked),
            "structurally_valid" => Ok(Self::StructurallyValid),
            "digest_valid" => Ok(Self::DigestValid),
            "signature_valid" => Ok(Self::SignatureValid),
            other => Err(FcaError::UnknownEnum {
                dimension: "integrity",
                value: other.to_string(),
            }),
        }
    }
}

/// Closed `authority` dimension.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Authority {
    /// Authority not evaluated.
    Unchecked,
    /// No delegation/token presented.
    Absent,
    /// Current, argument-bound, non-revoked authority.
    Valid,
    /// Previously valid authority past expiry.
    Expired,
    /// Explicitly revoked.
    Revoked,
    /// Authority evaluation denied the actor/action.
    Denied,
}

impl Authority {
    /// Normative constructor names.
    pub const fn names() -> &'static [&'static str] {
        &[
            "unchecked",
            "absent",
            "valid",
            "expired",
            "revoked",
            "denied",
        ]
    }

    /// Canonical snake_case spelling.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Unchecked => "unchecked",
            Self::Absent => "absent",
            Self::Valid => "valid",
            Self::Expired => "expired",
            Self::Revoked => "revoked",
            Self::Denied => "denied",
        }
    }
}

impl fmt::Display for Authority {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl FromStr for Authority {
    type Err = FcaError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "unchecked" => Ok(Self::Unchecked),
            "absent" => Ok(Self::Absent),
            "valid" => Ok(Self::Valid),
            "expired" => Ok(Self::Expired),
            "revoked" => Ok(Self::Revoked),
            "denied" => Ok(Self::Denied),
            other => Err(FcaError::UnknownEnum {
                dimension: "authority",
                value: other.to_string(),
            }),
        }
    }
}

/// Closed `policy` dimension (host kernel decisions only).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Policy {
    /// Policy not evaluated by the host kernel.
    Unchecked,
    /// Host policy allows the exact operation.
    Allowed,
    /// Host policy denies.
    Denied,
    /// Allowed only if named obligations remain satisfied.
    AllowedWithObligations,
    /// Policy could not be decided; fail closed for effects.
    Indeterminate,
}

impl Policy {
    /// Normative constructor names.
    pub const fn names() -> &'static [&'static str] {
        &[
            "unchecked",
            "allowed",
            "denied",
            "allowed_with_obligations",
            "indeterminate",
        ]
    }

    /// Canonical snake_case spelling.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Unchecked => "unchecked",
            Self::Allowed => "allowed",
            Self::Denied => "denied",
            Self::AllowedWithObligations => "allowed_with_obligations",
            Self::Indeterminate => "indeterminate",
        }
    }
}

impl fmt::Display for Policy {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl FromStr for Policy {
    type Err = FcaError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "unchecked" => Ok(Self::Unchecked),
            "allowed" => Ok(Self::Allowed),
            "denied" => Ok(Self::Denied),
            "allowed_with_obligations" => Ok(Self::AllowedWithObligations),
            "indeterminate" => Ok(Self::Indeterminate),
            other => Err(FcaError::UnknownEnum {
                dimension: "policy",
                value: other.to_string(),
            }),
        }
    }
}

/// Closed `proof` dimension.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Proof {
    /// No proof artifact.
    None,
    /// Proof candidate not yet admitted.
    Candidate,
    /// Admitted by a current named verifier.
    Verified,
    /// Independently refuted.
    Refuted,
    /// Proof obligation unresolved.
    Unknown,
    /// Required verifier cannot run.
    VerifierUnavailable,
}

impl Proof {
    /// Normative constructor names.
    pub const fn names() -> &'static [&'static str] {
        &[
            "none",
            "candidate",
            "verified",
            "refuted",
            "unknown",
            "verifier_unavailable",
        ]
    }

    /// Canonical snake_case spelling.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::None => "none",
            Self::Candidate => "candidate",
            Self::Verified => "verified",
            Self::Refuted => "refuted",
            Self::Unknown => "unknown",
            Self::VerifierUnavailable => "verifier_unavailable",
        }
    }
}

impl fmt::Display for Proof {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl FromStr for Proof {
    type Err = FcaError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "none" => Ok(Self::None),
            "candidate" => Ok(Self::Candidate),
            "verified" => Ok(Self::Verified),
            "refuted" => Ok(Self::Refuted),
            "unknown" => Ok(Self::Unknown),
            "verifier_unavailable" => Ok(Self::VerifierUnavailable),
            other => Err(FcaError::UnknownEnum {
                dimension: "proof",
                value: other.to_string(),
            }),
        }
    }
}

/// Closed `freshness` dimension.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Freshness {
    /// Bound to the exact current subject.
    Current,
    /// Out of date relative to the claimed subject.
    Stale,
    /// Replaced by a newer artifact.
    Superseded,
    /// Explicitly withdrawn.
    Withdrawn,
}

impl Freshness {
    /// Normative constructor names.
    pub const fn names() -> &'static [&'static str] {
        &["current", "stale", "superseded", "withdrawn"]
    }

    /// Canonical snake_case spelling.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Current => "current",
            Self::Stale => "stale",
            Self::Superseded => "superseded",
            Self::Withdrawn => "withdrawn",
        }
    }
}

impl fmt::Display for Freshness {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl FromStr for Freshness {
    type Err = FcaError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "current" => Ok(Self::Current),
            "stale" => Ok(Self::Stale),
            "superseded" => Ok(Self::Superseded),
            "withdrawn" => Ok(Self::Withdrawn),
            other => Err(FcaError::UnknownEnum {
                dimension: "freshness",
                value: other.to_string(),
            }),
        }
    }
}

/// Closed `effect` dimension.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Effect {
    /// No attempt.
    NotStarted,
    /// Resources reserved; effect not started.
    Reserved,
    /// Effect started; outcome not independently observed.
    Started,
    /// External outcome unknown.
    ExternallyUnknown,
    /// Independent observation of the effect outcome exists.
    Observed,
    /// Compensating action recorded.
    Compensated,
    /// Observed failure.
    Failed,
}

impl Effect {
    /// Normative constructor names.
    pub const fn names() -> &'static [&'static str] {
        &[
            "not_started",
            "reserved",
            "started",
            "externally_unknown",
            "observed",
            "compensated",
            "failed",
        ]
    }

    /// Canonical snake_case spelling.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::NotStarted => "not_started",
            Self::Reserved => "reserved",
            Self::Started => "started",
            Self::ExternallyUnknown => "externally_unknown",
            Self::Observed => "observed",
            Self::Compensated => "compensated",
            Self::Failed => "failed",
        }
    }
}

impl fmt::Display for Effect {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl FromStr for Effect {
    type Err = FcaError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "not_started" => Ok(Self::NotStarted),
            "reserved" => Ok(Self::Reserved),
            "started" => Ok(Self::Started),
            "externally_unknown" => Ok(Self::ExternallyUnknown),
            "observed" => Ok(Self::Observed),
            "compensated" => Ok(Self::Compensated),
            "failed" => Ok(Self::Failed),
            other => Err(FcaError::UnknownEnum {
                dimension: "effect",
                value: other.to_string(),
            }),
        }
    }
}

/// Closed `environment` dimension.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Environment {
    /// No live external dependency required.
    Hermetic,
    /// Requires named host/capability gates.
    Conditional,
    /// Live external dependency under live qualification.
    Live,
}

impl Environment {
    /// Normative constructor names.
    pub const fn names() -> &'static [&'static str] {
        &["hermetic", "conditional", "live"]
    }

    /// Canonical snake_case spelling.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Hermetic => "hermetic",
            Self::Conditional => "conditional",
            Self::Live => "live",
        }
    }
}

impl fmt::Display for Environment {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl FromStr for Environment {
    type Err = FcaError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "hermetic" => Ok(Self::Hermetic),
            "conditional" => Ok(Self::Conditional),
            "live" => Ok(Self::Live),
            other => Err(FcaError::UnknownEnum {
                dimension: "environment",
                value: other.to_string(),
            }),
        }
    }
}

/// Closed `review` dimension.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Review {
    /// No review record.
    Unreviewed,
    /// Automated review only.
    MachineReviewed,
    /// Explicit human review recorded.
    HumanReviewed,
}

impl Review {
    /// Normative constructor names.
    pub const fn names() -> &'static [&'static str] {
        &["unreviewed", "machine_reviewed", "human_reviewed"]
    }

    /// Canonical snake_case spelling.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Unreviewed => "unreviewed",
            Self::MachineReviewed => "machine_reviewed",
            Self::HumanReviewed => "human_reviewed",
        }
    }
}

impl fmt::Display for Review {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl FromStr for Review {
    type Err = FcaError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "unreviewed" => Ok(Self::Unreviewed),
            "machine_reviewed" => Ok(Self::MachineReviewed),
            "human_reviewed" => Ok(Self::HumanReviewed),
            other => Err(FcaError::UnknownEnum {
                dimension: "review",
                value: other.to_string(),
            }),
        }
    }
}

/// Closed outcome algebra for effectful operations.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ClosedOutcome {
    /// Required capability/evidence absent.
    Unavailable,
    /// Admission, authority, or policy rejected the operation.
    Rejected,
    /// Result produced under simulation/fixture/mock origin.
    Simulated,
    /// Effect started without independent observation.
    Attempted,
    /// External or recovery outcome unknown.
    Unknown,
    /// Effect independently observed.
    Observed,
    /// Observed outcome plus required proof/admission obligations.
    Verified,
    /// Observed failure.
    Failed,
    /// Compensating action recorded after a prior effect.
    Compensated,
}

impl ClosedOutcome {
    /// Normative constructor names (PascalCase as in the vocabulary).
    pub const fn names() -> &'static [&'static str] {
        &[
            "Unavailable",
            "Rejected",
            "Simulated",
            "Attempted",
            "Unknown",
            "Observed",
            "Verified",
            "Failed",
            "Compensated",
        ]
    }

    /// Canonical spelling.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Unavailable => "Unavailable",
            Self::Rejected => "Rejected",
            Self::Simulated => "Simulated",
            Self::Attempted => "Attempted",
            Self::Unknown => "Unknown",
            Self::Observed => "Observed",
            Self::Verified => "Verified",
            Self::Failed => "Failed",
            Self::Compensated => "Compensated",
        }
    }
}

impl fmt::Display for ClosedOutcome {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl FromStr for ClosedOutcome {
    type Err = FcaError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "Unavailable" => Ok(Self::Unavailable),
            "Rejected" => Ok(Self::Rejected),
            "Simulated" => Ok(Self::Simulated),
            "Attempted" => Ok(Self::Attempted),
            "Unknown" => Ok(Self::Unknown),
            "Observed" => Ok(Self::Observed),
            "Verified" => Ok(Self::Verified),
            "Failed" => Ok(Self::Failed),
            "Compensated" => Ok(Self::Compensated),
            other => Err(FcaError::UnknownEnum {
                dimension: "closed_outcome",
                value: other.to_string(),
            }),
        }
    }
}

/// Named promotion predicates over the evidence product.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PromotionPredicate {
    /// Live-qualified production support claim.
    ProductionSupported,
    /// Effect observed successful under admission.
    EffectSuccessful,
    /// Proof may be reused under current verifier/closure.
    ProofReusable,
    /// Receipt may authorize downstream consumers.
    ReceiptAuthoritative,
    /// Release/rights gate may pass.
    ReleaseAdmissible,
}

impl PromotionPredicate {
    /// Canonical snake_case id.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::ProductionSupported => "production_supported",
            Self::EffectSuccessful => "effect_successful",
            Self::ProofReusable => "proof_reusable",
            Self::ReceiptAuthoritative => "receipt_authoritative",
            Self::ReleaseAdmissible => "release_admissible",
        }
    }

    /// All predicates in normative order.
    pub const fn all() -> [Self; 5] {
        [
            Self::ProductionSupported,
            Self::EffectSuccessful,
            Self::ProofReusable,
            Self::ReceiptAuthoritative,
            Self::ReleaseAdmissible,
        ]
    }
}

impl fmt::Display for PromotionPredicate {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl FromStr for PromotionPredicate {
    type Err = FcaError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "production_supported" => Ok(Self::ProductionSupported),
            "effect_successful" => Ok(Self::EffectSuccessful),
            "proof_reusable" => Ok(Self::ProofReusable),
            "receipt_authoritative" => Ok(Self::ReceiptAuthoritative),
            "release_admissible" => Ok(Self::ReleaseAdmissible),
            other => Err(FcaError::UnknownEnum {
                dimension: "promotion_predicate",
                value: other.to_string(),
            }),
        }
    }
}

/// Dimension selector for single-dimension transitions.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Dimension {
    /// `origin`
    Origin,
    /// `integrity`
    Integrity,
    /// `authority`
    Authority,
    /// `policy`
    Policy,
    /// `proof`
    Proof,
    /// `freshness`
    Freshness,
    /// `effect`
    Effect,
    /// `environment`
    Environment,
    /// `review`
    Review,
}

impl Dimension {
    /// Canonical name.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Origin => "origin",
            Self::Integrity => "integrity",
            Self::Authority => "authority",
            Self::Policy => "policy",
            Self::Proof => "proof",
            Self::Freshness => "freshness",
            Self::Effect => "effect",
            Self::Environment => "environment",
            Self::Review => "review",
        }
    }
}

impl FromStr for Dimension {
    type Err = FcaError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "origin" => Ok(Self::Origin),
            "integrity" => Ok(Self::Integrity),
            "authority" => Ok(Self::Authority),
            "policy" => Ok(Self::Policy),
            "proof" => Ok(Self::Proof),
            "freshness" => Ok(Self::Freshness),
            "effect" => Ok(Self::Effect),
            "environment" => Ok(Self::Environment),
            "review" => Ok(Self::Review),
            other => Err(FcaError::UnknownEnum {
                dimension: "dimension",
                value: other.to_string(),
            }),
        }
    }
}

/// Evidence envelope: Cartesian product of the nine closed dimensions.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EvidenceEnvelope {
    /// Provenance of the evidence bytes/values.
    pub origin: Origin,
    /// Authenticity of bytes/identity.
    pub integrity: Integrity,
    /// Who may authorize the effect.
    pub authority: Authority,
    /// Host policy decision.
    pub policy: Policy,
    /// Semantic truth status relative to a verifier.
    pub proof: Proof,
    /// Currency of the evidence relative to the claimed subject.
    pub freshness: Freshness,
    /// Observation of the attempted effect.
    pub effect: Effect,
    /// Execution environment class.
    pub environment: Environment,
    /// Review provenance.
    pub review: Review,
}

impl EvidenceEnvelope {
    /// Weakest honest defaults for every dimension (fail-closed starting point).
    pub const fn weakest() -> Self {
        Self {
            origin: Origin::Absent,
            integrity: Integrity::Unchecked,
            authority: Authority::Unchecked,
            policy: Policy::Unchecked,
            proof: Proof::None,
            freshness: Freshness::Stale,
            effect: Effect::NotStarted,
            environment: Environment::Hermetic,
            review: Review::Unreviewed,
        }
    }

    /// Strong envelope satisfying every dimension-half promotion predicate.
    ///
    /// This is raw product data — not a success claim. Use
    /// [`ProductionSuccessClaim::try_admit`] / [`VerifiedClaim::try_admit`]
    /// to obtain gated success types (requires the evidence bag as well).
    pub const fn strong_product() -> Self {
        Self {
            origin: Origin::LiveObserved,
            integrity: Integrity::SignatureValid,
            authority: Authority::Valid,
            policy: Policy::Allowed,
            proof: Proof::Verified,
            freshness: Freshness::Current,
            effect: Effect::Observed,
            environment: Environment::Live,
            review: Review::HumanReviewed,
        }
    }

    /// Parse from a string-keyed dimension map (strict: all nine fields, no extras).
    pub fn from_dimension_map(map: &BTreeMap<String, String>) -> Result<Self, FcaError> {
        for key in map.keys() {
            if !DIMENSION_ORDER.contains(&key.as_str()) {
                return Err(FcaError::UnknownField(key.clone()));
            }
        }
        let get = |name: &'static str| -> Result<&str, FcaError> {
            map.get(name)
                .map(String::as_str)
                .ok_or(FcaError::MissingField(name))
        };
        Ok(Self {
            origin: get("origin")?.parse()?,
            integrity: get("integrity")?.parse()?,
            authority: get("authority")?.parse()?,
            policy: get("policy")?.parse()?,
            proof: get("proof")?.parse()?,
            freshness: get("freshness")?.parse()?,
            effect: get("effect")?.parse()?,
            environment: get("environment")?.parse()?,
            review: get("review")?.parse()?,
        })
    }

    /// Canonical dimension map (stable key order via [`DIMENSION_ORDER`]).
    pub fn to_dimension_map(&self) -> BTreeMap<String, String> {
        let mut map = BTreeMap::new();
        map.insert("origin".into(), self.origin.as_str().into());
        map.insert("integrity".into(), self.integrity.as_str().into());
        map.insert("authority".into(), self.authority.as_str().into());
        map.insert("policy".into(), self.policy.as_str().into());
        map.insert("proof".into(), self.proof.as_str().into());
        map.insert("freshness".into(), self.freshness.as_str().into());
        map.insert("effect".into(), self.effect.as_str().into());
        map.insert("environment".into(), self.environment.as_str().into());
        map.insert("review".into(), self.review.as_str().into());
        map
    }

    /// Canonical JSON serialization hook (deterministic key order via serde struct).
    pub fn to_canonical_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string(self)
    }

    /// Canonical JSON parse hook (deny_unknown_fields).
    pub fn from_canonical_json(text: &str) -> Result<Self, serde_json::Error> {
        serde_json::from_str(text)
    }

    /// Read a single dimension as its canonical string.
    pub fn get_dimension(&self, dimension: Dimension) -> &'static str {
        match dimension {
            Dimension::Origin => self.origin.as_str(),
            Dimension::Integrity => self.integrity.as_str(),
            Dimension::Authority => self.authority.as_str(),
            Dimension::Policy => self.policy.as_str(),
            Dimension::Proof => self.proof.as_str(),
            Dimension::Freshness => self.freshness.as_str(),
            Dimension::Effect => self.effect.as_str(),
            Dimension::Environment => self.environment.as_str(),
            Dimension::Review => self.review.as_str(),
        }
    }

    /// Return a copy with one dimension replaced (no transition validation).
    fn with_dimension_raw(&self, dimension: Dimension, value: &str) -> Result<Self, FcaError> {
        let mut next = self.clone();
        match dimension {
            Dimension::Origin => next.origin = value.parse()?,
            Dimension::Integrity => next.integrity = value.parse()?,
            Dimension::Authority => next.authority = value.parse()?,
            Dimension::Policy => next.policy = value.parse()?,
            Dimension::Proof => next.proof = value.parse()?,
            Dimension::Freshness => next.freshness = value.parse()?,
            Dimension::Effect => next.effect = value.parse()?,
            Dimension::Environment => next.environment = value.parse()?,
            Dimension::Review => next.review = value.parse()?,
        }
        Ok(next)
    }
}

/// Independent evidence bag required by transitions and predicates.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct EvidenceBag {
    keys: BTreeSet<String>,
}

impl EvidenceBag {
    /// Empty bag.
    pub fn new() -> Self {
        Self::default()
    }

    /// Build from an iterator of present evidence keys.
    pub fn from_keys<I, S>(keys: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        Self {
            keys: keys.into_iter().map(Into::into).collect(),
        }
    }

    /// Insert a present evidence key.
    pub fn insert(&mut self, key: impl Into<String>) {
        self.keys.insert(key.into());
    }

    /// True when every required key is present.
    pub fn contains_all(&self, required: &[&str]) -> bool {
        required.iter().all(|k| self.keys.contains(*k))
    }

    /// Borrow the underlying key set.
    pub fn keys(&self) -> &BTreeSet<String> {
        &self.keys
    }

    /// Full evidence bag covering every key referenced by promotion-rules.
    pub fn all_normative() -> Self {
        Self::from_keys([
            "live_qualification_receipt",
            "current_capability_admission",
            "authenticated_host_policy_decision",
            "independent_effect_observation",
            "admission_token",
            "named_current_verifier",
            "verifier_admission_closure",
            "signed_receipt",
            "non_revoked_delegation",
            "exact_source_binding",
            "immutable_dependency_closure",
            "identified_build_environment",
            "current_proofs_and_tests",
            "contract_compatibility",
            "rights_resolution",
            "reproducibility_inputs",
            "signed_provenance",
            "argument_bound_delegation",
            "non_revoked_ucan",
            "canonical_digest_match",
            "authentic_signature",
            "obligations_discharged",
            "human_legal_clearance",
        ])
    }
}

/// Allowed transition edge (optionally evidence-gated).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AllowedEdge {
    /// Source constructor.
    pub from: &'static str,
    /// Destination constructor.
    pub to: &'static str,
    /// Required independent evidence keys (all must be present).
    pub requires_evidence: &'static [&'static str],
}

/// Forbidden same-dimension edge (absolute or evidence-gated).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ForbiddenEdge {
    /// Source constructor.
    pub from: &'static str,
    /// Destination constructor.
    pub to: &'static str,
    /// When set, the edge is forbidden only while these keys are missing.
    pub when_missing_evidence: Option<&'static [&'static str]>,
    /// Absolute relabel ban (evidence never sufficient).
    pub never_sufficient_by_relabel: bool,
    /// Linked negative-rule rejection code when applicable.
    pub rejection_code: &'static str,
}

/// Normative allowed same-dimension edges for `origin`.
pub const ORIGIN_ALLOWED: &[AllowedEdge] = &[
    AllowedEdge {
        from: "absent",
        to: "declared",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "absent",
        to: "fixture",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "absent",
        to: "simulated",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "absent",
        to: "hermetic_observed",
        requires_evidence: &["independent_effect_observation"],
    },
    AllowedEdge {
        from: "absent",
        to: "live_observed",
        requires_evidence: &["live_qualification_receipt"],
    },
    AllowedEdge {
        from: "declared",
        to: "hermetic_observed",
        requires_evidence: &["independent_effect_observation"],
    },
    AllowedEdge {
        from: "declared",
        to: "live_observed",
        requires_evidence: &["live_qualification_receipt", "independent_effect_observation"],
    },
    AllowedEdge {
        from: "hermetic_observed",
        to: "live_observed",
        requires_evidence: &["live_qualification_receipt"],
    },
];

/// Normative forbidden same-dimension edges for `origin`.
pub const ORIGIN_FORBIDDEN: &[ForbiddenEdge] = &[
    ForbiddenEdge {
        from: "fixture",
        to: "live_observed",
        when_missing_evidence: None,
        never_sufficient_by_relabel: false,
        rejection_code: "NONIMP_FIXTURE_TO_OBSERVED",
    },
    ForbiddenEdge {
        from: "fixture",
        to: "hermetic_observed",
        when_missing_evidence: None,
        never_sufficient_by_relabel: false,
        rejection_code: "NONIMP_FIXTURE_TO_OBSERVED",
    },
    ForbiddenEdge {
        from: "simulated",
        to: "live_observed",
        when_missing_evidence: None,
        never_sufficient_by_relabel: false,
        rejection_code: "NONIMP_SIMULATED_TO_LIVE",
    },
    ForbiddenEdge {
        from: "simulated",
        to: "hermetic_observed",
        when_missing_evidence: None,
        never_sufficient_by_relabel: false,
        rejection_code: "NONIMP_SIMULATED_TO_LIVE",
    },
];

/// Normative allowed edges for `integrity`.
pub const INTEGRITY_ALLOWED: &[AllowedEdge] = &[
    AllowedEdge {
        from: "unchecked",
        to: "structurally_valid",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "unchecked",
        to: "digest_valid",
        requires_evidence: &["canonical_digest_match"],
    },
    AllowedEdge {
        from: "unchecked",
        to: "signature_valid",
        requires_evidence: &["canonical_digest_match", "authentic_signature"],
    },
    AllowedEdge {
        from: "structurally_valid",
        to: "digest_valid",
        requires_evidence: &["canonical_digest_match"],
    },
    AllowedEdge {
        from: "structurally_valid",
        to: "signature_valid",
        requires_evidence: &["canonical_digest_match", "authentic_signature"],
    },
    AllowedEdge {
        from: "digest_valid",
        to: "signature_valid",
        requires_evidence: &["authentic_signature"],
    },
];

/// Normative forbidden same-dimension edges for `integrity` (cross-dimension rows omitted).
pub const INTEGRITY_FORBIDDEN: &[ForbiddenEdge] = &[];

/// Normative allowed edges for `authority`.
pub const AUTHORITY_ALLOWED: &[AllowedEdge] = &[
    AllowedEdge {
        from: "unchecked",
        to: "absent",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "unchecked",
        to: "valid",
        requires_evidence: &["argument_bound_delegation", "non_revoked_ucan"],
    },
    AllowedEdge {
        from: "unchecked",
        to: "expired",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "unchecked",
        to: "revoked",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "unchecked",
        to: "denied",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "absent",
        to: "valid",
        requires_evidence: &["argument_bound_delegation", "non_revoked_ucan"],
    },
    AllowedEdge {
        from: "valid",
        to: "expired",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "valid",
        to: "revoked",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "valid",
        to: "denied",
        requires_evidence: &[],
    },
];

/// Normative forbidden edges for `authority`.
pub const AUTHORITY_FORBIDDEN: &[ForbiddenEdge] = &[
    ForbiddenEdge {
        from: "expired",
        to: "valid",
        when_missing_evidence: None,
        never_sufficient_by_relabel: true,
        rejection_code: "FORBIDDEN_RELABEL:authority:expired->valid",
    },
    ForbiddenEdge {
        from: "revoked",
        to: "valid",
        when_missing_evidence: None,
        never_sufficient_by_relabel: true,
        rejection_code: "FORBIDDEN_RELABEL:authority:revoked->valid",
    },
    ForbiddenEdge {
        from: "denied",
        to: "valid",
        when_missing_evidence: None,
        never_sufficient_by_relabel: true,
        rejection_code: "FORBIDDEN_RELABEL:authority:denied->valid",
    },
];

/// Normative allowed edges for `policy`.
pub const POLICY_ALLOWED: &[AllowedEdge] = &[
    AllowedEdge {
        from: "unchecked",
        to: "allowed",
        requires_evidence: &["authenticated_host_policy_decision"],
    },
    AllowedEdge {
        from: "unchecked",
        to: "denied",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "unchecked",
        to: "allowed_with_obligations",
        requires_evidence: &["authenticated_host_policy_decision"],
    },
    AllowedEdge {
        from: "unchecked",
        to: "indeterminate",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "indeterminate",
        to: "allowed",
        requires_evidence: &["authenticated_host_policy_decision"],
    },
    AllowedEdge {
        from: "indeterminate",
        to: "denied",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "allowed_with_obligations",
        to: "allowed",
        requires_evidence: &["obligations_discharged"],
    },
    AllowedEdge {
        from: "allowed_with_obligations",
        to: "denied",
        requires_evidence: &[],
    },
];

/// Normative forbidden edges for `policy`.
pub const POLICY_FORBIDDEN: &[ForbiddenEdge] = &[ForbiddenEdge {
    from: "denied",
    to: "allowed",
    when_missing_evidence: None,
    never_sufficient_by_relabel: true,
    rejection_code: "FORBIDDEN_RELABEL:policy:denied->allowed",
}];

/// Normative allowed edges for `proof`.
pub const PROOF_ALLOWED: &[AllowedEdge] = &[
    AllowedEdge {
        from: "none",
        to: "candidate",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "none",
        to: "unknown",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "none",
        to: "verifier_unavailable",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "candidate",
        to: "verified",
        requires_evidence: &["named_current_verifier", "verifier_admission_closure"],
    },
    AllowedEdge {
        from: "candidate",
        to: "refuted",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "candidate",
        to: "unknown",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "candidate",
        to: "verifier_unavailable",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "unknown",
        to: "verified",
        requires_evidence: &["named_current_verifier", "verifier_admission_closure"],
    },
    AllowedEdge {
        from: "unknown",
        to: "refuted",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "verifier_unavailable",
        to: "verified",
        requires_evidence: &["named_current_verifier", "verifier_admission_closure"],
    },
    AllowedEdge {
        from: "verified",
        to: "refuted",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "verified",
        to: "unknown",
        requires_evidence: &[],
    },
];

/// Normative forbidden edges for `proof`.
pub const PROOF_FORBIDDEN: &[ForbiddenEdge] = &[ForbiddenEdge {
    from: "candidate",
    to: "verified",
    when_missing_evidence: Some(&["named_current_verifier", "verifier_admission_closure"]),
    never_sufficient_by_relabel: false,
    rejection_code: "NONIMP_CANDIDATE_TO_VERIFIED",
}];

/// Normative allowed edges for `freshness`.
pub const FRESHNESS_ALLOWED: &[AllowedEdge] = &[
    AllowedEdge {
        from: "current",
        to: "stale",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "current",
        to: "superseded",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "current",
        to: "withdrawn",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "stale",
        to: "superseded",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "stale",
        to: "withdrawn",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "superseded",
        to: "withdrawn",
        requires_evidence: &[],
    },
];

/// Normative forbidden edges for `freshness`.
pub const FRESHNESS_FORBIDDEN: &[ForbiddenEdge] = &[
    ForbiddenEdge {
        from: "stale",
        to: "current",
        when_missing_evidence: None,
        never_sufficient_by_relabel: false,
        rejection_code: "NONIMP_STALE_TO_CURRENT",
    },
    ForbiddenEdge {
        from: "superseded",
        to: "current",
        when_missing_evidence: None,
        never_sufficient_by_relabel: false,
        rejection_code: "NONIMP_STALE_TO_CURRENT",
    },
    ForbiddenEdge {
        from: "withdrawn",
        to: "current",
        when_missing_evidence: None,
        never_sufficient_by_relabel: false,
        rejection_code: "NONIMP_STALE_TO_CURRENT",
    },
    ForbiddenEdge {
        from: "withdrawn",
        to: "stale",
        when_missing_evidence: None,
        never_sufficient_by_relabel: false,
        rejection_code: "NONIMP_STALE_TO_CURRENT",
    },
];

/// Normative allowed edges for `effect`.
pub const EFFECT_ALLOWED: &[AllowedEdge] = &[
    AllowedEdge {
        from: "not_started",
        to: "reserved",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "not_started",
        to: "started",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "reserved",
        to: "started",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "started",
        to: "externally_unknown",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "started",
        to: "observed",
        requires_evidence: &["independent_effect_observation"],
    },
    AllowedEdge {
        from: "started",
        to: "failed",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "externally_unknown",
        to: "observed",
        requires_evidence: &["independent_effect_observation"],
    },
    AllowedEdge {
        from: "externally_unknown",
        to: "failed",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "externally_unknown",
        to: "compensated",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "observed",
        to: "compensated",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "failed",
        to: "compensated",
        requires_evidence: &[],
    },
];

/// Normative forbidden edges for `effect`.
pub const EFFECT_FORBIDDEN: &[ForbiddenEdge] = &[
    ForbiddenEdge {
        from: "not_started",
        to: "observed",
        when_missing_evidence: None,
        never_sufficient_by_relabel: false,
        rejection_code: "NONIMP_DECLARED_TO_OBSERVED",
    },
    ForbiddenEdge {
        from: "externally_unknown",
        to: "observed",
        when_missing_evidence: Some(&["independent_effect_observation"]),
        never_sufficient_by_relabel: false,
        rejection_code: "NONIMP_UNKNOWN_TO_OBSERVED",
    },
];

/// Normative allowed edges for `environment`.
pub const ENVIRONMENT_ALLOWED: &[AllowedEdge] = &[
    AllowedEdge {
        from: "hermetic",
        to: "conditional",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "conditional",
        to: "live",
        requires_evidence: &["live_qualification_receipt", "current_capability_admission"],
    },
];

/// Normative forbidden edges for `environment`.
pub const ENVIRONMENT_FORBIDDEN: &[ForbiddenEdge] = &[
    ForbiddenEdge {
        from: "hermetic",
        to: "live",
        when_missing_evidence: None,
        never_sufficient_by_relabel: false,
        rejection_code: "NONIMP_HERMETIC_TO_LIVE",
    },
    ForbiddenEdge {
        from: "conditional",
        to: "live",
        when_missing_evidence: Some(&[
            "live_qualification_receipt",
            "current_capability_admission",
        ]),
        never_sufficient_by_relabel: false,
        rejection_code: "NONIMP_INVENTORY_TO_LIVE",
    },
];

/// Normative allowed edges for `review`.
pub const REVIEW_ALLOWED: &[AllowedEdge] = &[
    AllowedEdge {
        from: "unreviewed",
        to: "machine_reviewed",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "unreviewed",
        to: "human_reviewed",
        requires_evidence: &[],
    },
    AllowedEdge {
        from: "machine_reviewed",
        to: "human_reviewed",
        requires_evidence: &[],
    },
];

/// Normative forbidden same-dimension edges for `review` (cross-dimension omitted).
pub const REVIEW_FORBIDDEN: &[ForbiddenEdge] = &[];

fn tables_for(dimension: Dimension) -> (&'static [AllowedEdge], &'static [ForbiddenEdge]) {
    match dimension {
        Dimension::Origin => (ORIGIN_ALLOWED, ORIGIN_FORBIDDEN),
        Dimension::Integrity => (INTEGRITY_ALLOWED, INTEGRITY_FORBIDDEN),
        Dimension::Authority => (AUTHORITY_ALLOWED, AUTHORITY_FORBIDDEN),
        Dimension::Policy => (POLICY_ALLOWED, POLICY_FORBIDDEN),
        Dimension::Proof => (PROOF_ALLOWED, PROOF_FORBIDDEN),
        Dimension::Freshness => (FRESHNESS_ALLOWED, FRESHNESS_FORBIDDEN),
        Dimension::Effect => (EFFECT_ALLOWED, EFFECT_FORBIDDEN),
        Dimension::Environment => (ENVIRONMENT_ALLOWED, ENVIRONMENT_FORBIDDEN),
        Dimension::Review => (REVIEW_ALLOWED, REVIEW_FORBIDDEN),
    }
}

/// Evaluate whether a same-dimension transition is allowed under `evidence`.
pub fn transition_allowed(
    dimension: Dimension,
    from: &str,
    to: &str,
    evidence: &EvidenceBag,
) -> Result<(), FcaError> {
    // Validate spellings against the closed carrier for the dimension.
    let _ = parse_dimension_value(dimension, from)?;
    let _ = parse_dimension_value(dimension, to)?;

    let (allowed, forbidden) = tables_for(dimension);

    for edge in forbidden {
        if edge.from == from && edge.to == to {
            if let Some(needed) = edge.when_missing_evidence {
                if evidence.contains_all(needed) {
                    continue;
                }
                return Err(FcaError::TransitionRejected {
                    dimension: dimension.as_str(),
                    from: from.to_string(),
                    to: to.to_string(),
                    code: edge.rejection_code.to_string(),
                });
            }
            return Err(FcaError::TransitionRejected {
                dimension: dimension.as_str(),
                from: from.to_string(),
                to: to.to_string(),
                code: edge.rejection_code.to_string(),
            });
        }
    }

    for edge in allowed {
        if edge.from == from && edge.to == to {
            if !edge.requires_evidence.is_empty()
                && !evidence.contains_all(edge.requires_evidence)
            {
                return Err(FcaError::TransitionRejected {
                    dimension: dimension.as_str(),
                    from: from.to_string(),
                    to: to.to_string(),
                    code: format!("MISSING_TRANSITION_EVIDENCE:{}", dimension.as_str()),
                });
            }
            return Ok(());
        }
    }

    Err(FcaError::TransitionRejected {
        dimension: dimension.as_str(),
        from: from.to_string(),
        to: to.to_string(),
        code: format!(
            "UNKNOWN_TRANSITION:{}:{}->{}",
            dimension.as_str(),
            from,
            to
        ),
    })
}

/// Apply a validated single-dimension transition, returning the next envelope.
///
/// Illegal / unknown / evidence-deficient transitions return [`Err`] and never
/// produce a gated success type.
pub fn apply_transition(
    envelope: &EvidenceEnvelope,
    dimension: Dimension,
    to: &str,
    evidence: &EvidenceBag,
) -> Result<EvidenceEnvelope, FcaError> {
    let from = envelope.get_dimension(dimension);
    transition_allowed(dimension, from, to, evidence)?;
    envelope.with_dimension_raw(dimension, to)
}

fn parse_dimension_value(dimension: Dimension, value: &str) -> Result<(), FcaError> {
    match dimension {
        Dimension::Origin => {
            value.parse::<Origin>()?;
        }
        Dimension::Integrity => {
            value.parse::<Integrity>()?;
        }
        Dimension::Authority => {
            value.parse::<Authority>()?;
        }
        Dimension::Policy => {
            value.parse::<Policy>()?;
        }
        Dimension::Proof => {
            value.parse::<Proof>()?;
        }
        Dimension::Freshness => {
            value.parse::<Freshness>()?;
        }
        Dimension::Effect => {
            value.parse::<Effect>()?;
        }
        Dimension::Environment => {
            value.parse::<Environment>()?;
        }
        Dimension::Review => {
            value.parse::<Review>()?;
        }
    }
    Ok(())
}

/// Dimension-only half of `production_supported`.
pub fn production_supported_dimensions(e: &EvidenceEnvelope) -> bool {
    matches!(e.origin, Origin::LiveObserved)
        && matches!(
            e.integrity,
            Integrity::DigestValid | Integrity::SignatureValid
        )
        && matches!(e.authority, Authority::Valid)
        && matches!(
            e.policy,
            Policy::Allowed | Policy::AllowedWithObligations
        )
        && matches!(e.freshness, Freshness::Current)
        && matches!(e.environment, Environment::Live)
}

/// Dimension-only half of `effect_successful`.
pub fn effect_successful_dimensions(e: &EvidenceEnvelope) -> bool {
    matches!(
        e.origin,
        Origin::HermeticObserved | Origin::LiveObserved
    ) && matches!(
        e.integrity,
        Integrity::DigestValid | Integrity::SignatureValid
    ) && matches!(e.authority, Authority::Valid)
        && matches!(
            e.policy,
            Policy::Allowed | Policy::AllowedWithObligations
        )
        && matches!(e.freshness, Freshness::Current)
        && matches!(e.effect, Effect::Observed)
}

/// Dimension-only half of `proof_reusable`.
pub fn proof_reusable_dimensions(e: &EvidenceEnvelope) -> bool {
    matches!(
        e.integrity,
        Integrity::DigestValid | Integrity::SignatureValid
    ) && matches!(e.proof, Proof::Verified)
        && matches!(e.freshness, Freshness::Current)
}

/// Dimension-only half of `receipt_authoritative`.
pub fn receipt_authoritative_dimensions(e: &EvidenceEnvelope) -> bool {
    matches!(
        e.origin,
        Origin::HermeticObserved | Origin::LiveObserved
    ) && matches!(e.integrity, Integrity::SignatureValid)
        && matches!(e.authority, Authority::Valid)
        && matches!(
            e.policy,
            Policy::Allowed | Policy::AllowedWithObligations
        )
        && matches!(e.freshness, Freshness::Current)
}

/// Dimension-only half of `release_admissible`.
pub fn release_admissible_dimensions(e: &EvidenceEnvelope) -> bool {
    matches!(
        e.origin,
        Origin::HermeticObserved | Origin::LiveObserved
    ) && matches!(e.integrity, Integrity::SignatureValid)
        && matches!(e.authority, Authority::Valid)
        && matches!(
            e.policy,
            Policy::Allowed | Policy::AllowedWithObligations
        )
        && matches!(e.proof, Proof::Verified)
        && matches!(e.freshness, Freshness::Current)
        && matches!(
            e.review,
            Review::MachineReviewed | Review::HumanReviewed
        )
}

/// Necessary evidence keys for each promotion predicate.
pub fn necessary_evidence(predicate: PromotionPredicate) -> &'static [&'static str] {
    match predicate {
        PromotionPredicate::ProductionSupported => &[
            "live_qualification_receipt",
            "current_capability_admission",
            "authenticated_host_policy_decision",
        ],
        PromotionPredicate::EffectSuccessful => {
            &["independent_effect_observation", "admission_token"]
        }
        PromotionPredicate::ProofReusable => {
            &["named_current_verifier", "verifier_admission_closure"]
        }
        PromotionPredicate::ReceiptAuthoritative => {
            &["signed_receipt", "non_revoked_delegation"]
        }
        PromotionPredicate::ReleaseAdmissible => &[
            "exact_source_binding",
            "immutable_dependency_closure",
            "identified_build_environment",
            "current_proofs_and_tests",
            "contract_compatibility",
            "rights_resolution",
            "reproducibility_inputs",
            "signed_provenance",
        ],
    }
}

fn dimensions_hold(predicate: PromotionPredicate, envelope: &EvidenceEnvelope) -> bool {
    match predicate {
        PromotionPredicate::ProductionSupported => production_supported_dimensions(envelope),
        PromotionPredicate::EffectSuccessful => effect_successful_dimensions(envelope),
        PromotionPredicate::ProofReusable => proof_reusable_dimensions(envelope),
        PromotionPredicate::ReceiptAuthoritative => receipt_authoritative_dimensions(envelope),
        PromotionPredicate::ReleaseAdmissible => release_admissible_dimensions(envelope),
    }
}

/// Evaluate a promotion predicate against envelope dimensions and evidence bag.
pub fn predicate_holds(
    predicate: PromotionPredicate,
    envelope: &EvidenceEnvelope,
    evidence: &EvidenceBag,
) -> Result<(), FcaError> {
    if !dimensions_hold(predicate, envelope) {
        return Err(FcaError::PredicateRejected {
            predicate: predicate.as_str(),
            code: format!("MISSING_DIMENSIONS:{}", predicate.as_str()),
        });
    }
    if !evidence.contains_all(necessary_evidence(predicate)) {
        return Err(FcaError::PredicateRejected {
            predicate: predicate.as_str(),
            code: format!("MISSING_EVIDENCE:{}", predicate.as_str()),
        });
    }
    Ok(())
}

/// Gated production-success claim.
///
/// Fields are private. The only public constructor is [`Self::try_admit`],
/// which requires both `production_supported` and `effect_successful`.
/// Illegal transitions and weak envelopes cannot construct this type.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProductionSuccessClaim {
    envelope: EvidenceEnvelope,
}

impl ProductionSuccessClaim {
    /// Admit a live authorized observed current production-success claim.
    pub fn try_admit(
        envelope: EvidenceEnvelope,
        evidence: &EvidenceBag,
    ) -> Result<Self, FcaError> {
        // Absolute origin bans: fixture/simulated/declared cannot be production success.
        if matches!(
            envelope.origin,
            Origin::Fixture | Origin::Simulated | Origin::Declared | Origin::Absent
        ) {
            return Err(FcaError::PredicateRejected {
                predicate: "production_supported",
                code: "NONIMP_FIXTURE_TO_OBSERVED".into(),
            });
        }
        predicate_holds(
            PromotionPredicate::ProductionSupported,
            &envelope,
            evidence,
        )?;
        predicate_holds(PromotionPredicate::EffectSuccessful, &envelope, evidence)?;
        Ok(Self { envelope })
    }

    /// Borrow the underlying envelope.
    pub fn envelope(&self) -> &EvidenceEnvelope {
        &self.envelope
    }

    /// Closed outcome corresponding to this claim.
    pub fn outcome(&self) -> ClosedOutcome {
        ClosedOutcome::Verified
    }
}

/// Gated `Verified` closed-outcome claim (observed + proof obligations).
///
/// Private fields; only [`Self::try_admit`] constructs it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VerifiedClaim {
    envelope: EvidenceEnvelope,
}

impl VerifiedClaim {
    /// Admit a `Verified` outcome from an envelope + evidence bag.
    pub fn try_admit(
        envelope: EvidenceEnvelope,
        evidence: &EvidenceBag,
    ) -> Result<Self, FcaError> {
        if !matches!(envelope.effect, Effect::Observed) {
            return Err(FcaError::OutcomeRejected {
                outcome: "Verified",
                code: "MISSING_DIMENSIONS:effect_successful".into(),
            });
        }
        if matches!(
            envelope.origin,
            Origin::Fixture | Origin::Simulated | Origin::Declared | Origin::Absent
        ) {
            return Err(FcaError::OutcomeRejected {
                outcome: "Verified",
                code: "NONIMP_FIXTURE_TO_OBSERVED".into(),
            });
        }
        predicate_holds(PromotionPredicate::EffectSuccessful, &envelope, evidence)?;
        predicate_holds(PromotionPredicate::ProofReusable, &envelope, evidence)?;
        Ok(Self { envelope })
    }

    /// Borrow the underlying envelope.
    pub fn envelope(&self) -> &EvidenceEnvelope {
        &self.envelope
    }

    /// Closed outcome tag.
    pub fn outcome(&self) -> ClosedOutcome {
        ClosedOutcome::Verified
    }
}

/// Normative vector kind for the embedded executable suite.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum VectorExpectation {
    /// Transition / predicate / outcome must be accepted.
    Accept,
    /// Transition / predicate / outcome must be rejected.
    Reject,
}

/// Embedded normative vector exercised by the Rust kernel tests.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NormativeVector {
    /// Stable vector id.
    pub id: String,
    /// Vector family.
    pub kind: String,
    /// Accept or reject.
    pub expectation: VectorExpectation,
    /// Optional dimension under test.
    pub dimension: Option<String>,
    /// Optional from value.
    pub from: Option<String>,
    /// Optional to value.
    pub to: Option<String>,
    /// Optional predicate id.
    pub predicate: Option<String>,
    /// Envelope overrides applied on top of [`EvidenceEnvelope::weakest`].
    pub envelope_overrides: Vec<(String, String)>,
    /// Evidence keys present for this vector.
    pub evidence: Vec<String>,
    /// Expected rejection code substring when rejecting (optional).
    pub rejection_code_contains: Option<String>,
}

fn envelope_from_overrides(overrides: &[(String, String)]) -> Result<EvidenceEnvelope, FcaError> {
    let mut map = EvidenceEnvelope::weakest().to_dimension_map();
    for (k, v) in overrides {
        map.insert(k.clone(), v.clone());
    }
    EvidenceEnvelope::from_dimension_map(&map)
}

fn ov(pairs: &[(&str, &str)]) -> Vec<(String, String)> {
    pairs
        .iter()
        .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
        .collect()
}

fn ev(keys: &[&str]) -> Vec<String> {
    keys.iter().map(|s| (*s).to_string()).collect()
}

/// Execute one normative vector against the kernel.
pub fn evaluate_normative_vector(vector: &NormativeVector) -> Result<(), String> {
    let evidence = EvidenceBag::from_keys(vector.evidence.iter().cloned());
    let envelope = envelope_from_overrides(&vector.envelope_overrides)
        .map_err(|e| format!("{}: envelope build: {e}", vector.id))?;

    match vector.kind.as_str() {
        "transition" => {
            let dim = vector
                .dimension
                .as_deref()
                .ok_or_else(|| format!("{}: missing dimension", vector.id))?
                .parse::<Dimension>()
                .map_err(|e| format!("{}: {e}", vector.id))?;
            let from = vector
                .from
                .as_deref()
                .ok_or_else(|| format!("{}: missing from", vector.id))?;
            let to = vector
                .to
                .as_deref()
                .ok_or_else(|| format!("{}: missing to", vector.id))?;
            let mut start_map = EvidenceEnvelope::weakest().to_dimension_map();
            for (k, v) in &vector.envelope_overrides {
                start_map.insert(k.clone(), v.clone());
            }
            start_map.insert(dim.as_str().to_string(), from.to_string());
            let start = EvidenceEnvelope::from_dimension_map(&start_map)
                .map_err(|e| format!("{}: {e}", vector.id))?;
            let result = apply_transition(&start, dim, to, &evidence);
            match (vector.expectation, result) {
                (VectorExpectation::Accept, Ok(_)) => Ok(()),
                (VectorExpectation::Accept, Err(e)) => {
                    Err(format!("{}: expected accept, got {e}", vector.id))
                }
                (VectorExpectation::Reject, Err(e)) => {
                    if let Some(needle) = vector.rejection_code_contains.as_deref() {
                        let msg = e.to_string();
                        if !msg.contains(needle) {
                            return Err(format!(
                                "{}: rejection code missing `{needle}`: {msg}",
                                vector.id
                            ));
                        }
                    }
                    Ok(())
                }
                (VectorExpectation::Reject, Ok(_)) => {
                    Err(format!("{}: expected reject, got accept", vector.id))
                }
            }
        }
        "predicate" => {
            let pred = vector
                .predicate
                .as_deref()
                .ok_or_else(|| format!("{}: missing predicate", vector.id))?
                .parse::<PromotionPredicate>()
                .map_err(|e| format!("{}: {e}", vector.id))?;
            let result = predicate_holds(pred, &envelope, &evidence);
            match (vector.expectation, result) {
                (VectorExpectation::Accept, Ok(())) => Ok(()),
                (VectorExpectation::Accept, Err(e)) => {
                    Err(format!("{}: expected accept, got {e}", vector.id))
                }
                (VectorExpectation::Reject, Err(e)) => {
                    if let Some(needle) = vector.rejection_code_contains.as_deref() {
                        let msg = e.to_string();
                        if !msg.contains(needle) {
                            return Err(format!(
                                "{}: rejection code missing `{needle}`: {msg}",
                                vector.id
                            ));
                        }
                    }
                    Ok(())
                }
                (VectorExpectation::Reject, Ok(())) => {
                    Err(format!("{}: expected reject, got accept", vector.id))
                }
            }
        }
        "production_success" => {
            let result = ProductionSuccessClaim::try_admit(envelope, &evidence);
            match (vector.expectation, result) {
                (VectorExpectation::Accept, Ok(_)) => Ok(()),
                (VectorExpectation::Accept, Err(e)) => {
                    Err(format!("{}: expected accept, got {e}", vector.id))
                }
                (VectorExpectation::Reject, Err(_)) => Ok(()),
                (VectorExpectation::Reject, Ok(_)) => {
                    Err(format!("{}: expected reject, got accept", vector.id))
                }
            }
        }
        "verified_claim" => {
            let result = VerifiedClaim::try_admit(envelope, &evidence);
            match (vector.expectation, result) {
                (VectorExpectation::Accept, Ok(_)) => Ok(()),
                (VectorExpectation::Accept, Err(e)) => {
                    Err(format!("{}: expected accept, got {e}", vector.id))
                }
                (VectorExpectation::Reject, Err(_)) => Ok(()),
                (VectorExpectation::Reject, Ok(_)) => {
                    Err(format!("{}: expected reject, got accept", vector.id))
                }
            }
        }
        other => Err(format!("{}: unknown vector kind `{other}`", vector.id)),
    }
}

fn reject_transition(
    id: &str,
    dimension: &str,
    from: &str,
    to: &str,
    evidence: &[&str],
    code: &str,
) -> NormativeVector {
    NormativeVector {
        id: id.to_string(),
        kind: "transition".into(),
        expectation: VectorExpectation::Reject,
        dimension: Some(dimension.into()),
        from: Some(from.into()),
        to: Some(to.into()),
        predicate: None,
        envelope_overrides: Vec::new(),
        evidence: ev(evidence),
        rejection_code_contains: Some(code.into()),
    }
}

fn reject_predicate(
    id: &str,
    predicate: &str,
    overrides: &[(&str, &str)],
    evidence: &[&str],
    code: &str,
) -> NormativeVector {
    NormativeVector {
        id: id.to_string(),
        kind: "predicate".into(),
        expectation: VectorExpectation::Reject,
        dimension: None,
        from: None,
        to: None,
        predicate: Some(predicate.into()),
        envelope_overrides: ov(overrides),
        evidence: ev(evidence),
        rejection_code_contains: Some(code.into()),
    }
}

/// Full embedded normative vector suite (accept + reject) for FACP-013.
pub fn normative_vectors() -> Vec<NormativeVector> {
    let mut vectors = Vec::new();

    // --- Allowed transitions (accept) ---
    for (dim_name, edges) in [
        ("origin", ORIGIN_ALLOWED),
        ("integrity", INTEGRITY_ALLOWED),
        ("authority", AUTHORITY_ALLOWED),
        ("policy", POLICY_ALLOWED),
        ("proof", PROOF_ALLOWED),
        ("freshness", FRESHNESS_ALLOWED),
        ("effect", EFFECT_ALLOWED),
        ("environment", ENVIRONMENT_ALLOWED),
        ("review", REVIEW_ALLOWED),
    ] {
        for edge in edges {
            vectors.push(NormativeVector {
                id: format!("accept:{dim_name}:{}->{}", edge.from, edge.to),
                kind: "transition".into(),
                expectation: VectorExpectation::Accept,
                dimension: Some(dim_name.into()),
                from: Some(edge.from.into()),
                to: Some(edge.to.into()),
                predicate: None,
                envelope_overrides: Vec::new(),
                evidence: ev(edge.requires_evidence),
                rejection_code_contains: None,
            });
        }
    }

    // --- Forbidden / absolute reject transitions ---
    vectors.extend([
        reject_transition(
            "reject:origin:fixture->live_observed",
            "origin",
            "fixture",
            "live_observed",
            &["live_qualification_receipt"],
            "NONIMP_FIXTURE_TO_OBSERVED",
        ),
        reject_transition(
            "reject:origin:fixture->hermetic_observed",
            "origin",
            "fixture",
            "hermetic_observed",
            &["independent_effect_observation"],
            "NONIMP_FIXTURE_TO_OBSERVED",
        ),
        reject_transition(
            "reject:origin:simulated->live_observed",
            "origin",
            "simulated",
            "live_observed",
            &["live_qualification_receipt"],
            "NONIMP_SIMULATED_TO_LIVE",
        ),
        reject_transition(
            "reject:origin:simulated->hermetic_observed",
            "origin",
            "simulated",
            "hermetic_observed",
            &["independent_effect_observation"],
            "NONIMP_SIMULATED_TO_LIVE",
        ),
        reject_transition(
            "reject:authority:expired->valid",
            "authority",
            "expired",
            "valid",
            &["argument_bound_delegation", "non_revoked_ucan"],
            "FORBIDDEN_RELABEL",
        ),
        reject_transition(
            "reject:authority:revoked->valid",
            "authority",
            "revoked",
            "valid",
            &["argument_bound_delegation", "non_revoked_ucan"],
            "FORBIDDEN_RELABEL",
        ),
        reject_transition(
            "reject:authority:denied->valid",
            "authority",
            "denied",
            "valid",
            &["argument_bound_delegation", "non_revoked_ucan"],
            "FORBIDDEN_RELABEL",
        ),
        reject_transition(
            "reject:policy:denied->allowed",
            "policy",
            "denied",
            "allowed",
            &["authenticated_host_policy_decision"],
            "FORBIDDEN_RELABEL",
        ),
        reject_transition(
            "reject:proof:candidate->verified:missing_evidence",
            "proof",
            "candidate",
            "verified",
            &[],
            "NONIMP_CANDIDATE_TO_VERIFIED",
        ),
        reject_transition(
            "reject:freshness:stale->current",
            "freshness",
            "stale",
            "current",
            &[],
            "NONIMP_STALE_TO_CURRENT",
        ),
        reject_transition(
            "reject:freshness:superseded->current",
            "freshness",
            "superseded",
            "current",
            &[],
            "NONIMP_STALE_TO_CURRENT",
        ),
        reject_transition(
            "reject:freshness:withdrawn->current",
            "freshness",
            "withdrawn",
            "current",
            &[],
            "NONIMP_STALE_TO_CURRENT",
        ),
        reject_transition(
            "reject:freshness:withdrawn->stale",
            "freshness",
            "withdrawn",
            "stale",
            &[],
            "NONIMP_STALE_TO_CURRENT",
        ),
        reject_transition(
            "reject:effect:not_started->observed",
            "effect",
            "not_started",
            "observed",
            &["independent_effect_observation"],
            "NONIMP_DECLARED_TO_OBSERVED",
        ),
        reject_transition(
            "reject:effect:externally_unknown->observed:missing_evidence",
            "effect",
            "externally_unknown",
            "observed",
            &[],
            "NONIMP_UNKNOWN_TO_OBSERVED",
        ),
        reject_transition(
            "reject:environment:hermetic->live",
            "environment",
            "hermetic",
            "live",
            &[
                "live_qualification_receipt",
                "current_capability_admission",
            ],
            "NONIMP_HERMETIC_TO_LIVE",
        ),
        reject_transition(
            "reject:environment:conditional->live:missing_evidence",
            "environment",
            "conditional",
            "live",
            &[],
            "NONIMP_INVENTORY_TO_LIVE",
        ),
        reject_transition(
            "reject:unknown:origin:fixture->declared",
            "origin",
            "fixture",
            "declared",
            &[],
            "UNKNOWN_TRANSITION",
        ),
        reject_transition(
            "reject:origin:absent->live_observed:missing_evidence",
            "origin",
            "absent",
            "live_observed",
            &[],
            "MISSING_TRANSITION_EVIDENCE",
        ),
    ]);

    let strong = ov(&[
        ("origin", "live_observed"),
        ("integrity", "signature_valid"),
        ("authority", "valid"),
        ("policy", "allowed"),
        ("proof", "verified"),
        ("freshness", "current"),
        ("effect", "observed"),
        ("environment", "live"),
        ("review", "human_reviewed"),
    ]);
    let all_ev: Vec<String> = EvidenceBag::all_normative().keys().iter().cloned().collect();

    for pred in PREDICATE_ORDER {
        vectors.push(NormativeVector {
            id: format!("accept:predicate:{pred}"),
            kind: "predicate".into(),
            expectation: VectorExpectation::Accept,
            dimension: None,
            from: None,
            to: None,
            predicate: Some(pred.into()),
            envelope_overrides: strong.clone(),
            evidence: all_ev.clone(),
            rejection_code_contains: None,
        });
    }

    vectors.extend([
        reject_predicate(
            "reject:predicate:production_supported:fixture",
            "production_supported",
            &[
                ("origin", "fixture"),
                ("integrity", "signature_valid"),
                ("authority", "valid"),
                ("policy", "allowed"),
                ("proof", "verified"),
                ("freshness", "current"),
                ("effect", "observed"),
                ("environment", "live"),
                ("review", "human_reviewed"),
            ],
            &[
                "live_qualification_receipt",
                "current_capability_admission",
                "authenticated_host_policy_decision",
            ],
            "MISSING_DIMENSIONS",
        ),
        reject_predicate(
            "reject:predicate:production_supported:stale",
            "production_supported",
            &[
                ("origin", "live_observed"),
                ("integrity", "signature_valid"),
                ("authority", "valid"),
                ("policy", "allowed"),
                ("proof", "verified"),
                ("freshness", "stale"),
                ("effect", "observed"),
                ("environment", "live"),
                ("review", "human_reviewed"),
            ],
            &[
                "live_qualification_receipt",
                "current_capability_admission",
                "authenticated_host_policy_decision",
            ],
            "MISSING_DIMENSIONS",
        ),
        reject_predicate(
            "reject:predicate:production_supported:expired",
            "production_supported",
            &[
                ("origin", "live_observed"),
                ("integrity", "signature_valid"),
                ("authority", "expired"),
                ("policy", "allowed"),
                ("proof", "verified"),
                ("freshness", "current"),
                ("effect", "observed"),
                ("environment", "live"),
                ("review", "human_reviewed"),
            ],
            &[
                "live_qualification_receipt",
                "current_capability_admission",
                "authenticated_host_policy_decision",
            ],
            "MISSING_DIMENSIONS",
        ),
        reject_predicate(
            "reject:predicate:effect_successful:externally_unknown",
            "effect_successful",
            &[
                ("origin", "live_observed"),
                ("integrity", "signature_valid"),
                ("authority", "valid"),
                ("policy", "allowed"),
                ("proof", "verified"),
                ("freshness", "current"),
                ("effect", "externally_unknown"),
                ("environment", "live"),
                ("review", "human_reviewed"),
            ],
            &["independent_effect_observation", "admission_token"],
            "MISSING_DIMENSIONS",
        ),
        reject_predicate(
            "reject:predicate:proof_reusable:candidate",
            "proof_reusable",
            &[
                ("origin", "live_observed"),
                ("integrity", "signature_valid"),
                ("authority", "valid"),
                ("policy", "allowed"),
                ("proof", "candidate"),
                ("freshness", "current"),
                ("effect", "observed"),
                ("environment", "live"),
                ("review", "human_reviewed"),
            ],
            &["named_current_verifier", "verifier_admission_closure"],
            "MISSING_DIMENSIONS",
        ),
        reject_predicate(
            "reject:predicate:proof_reusable:digest_only",
            "proof_reusable",
            &[
                ("origin", "live_observed"),
                ("integrity", "digest_valid"),
                ("authority", "valid"),
                ("policy", "allowed"),
                ("proof", "none"),
                ("freshness", "current"),
                ("effect", "observed"),
                ("environment", "live"),
                ("review", "human_reviewed"),
            ],
            &["named_current_verifier", "verifier_admission_closure"],
            "MISSING_DIMENSIONS",
        ),
        NormativeVector {
            id: "reject:predicate:production_supported:missing_evidence".into(),
            kind: "predicate".into(),
            expectation: VectorExpectation::Reject,
            dimension: None,
            from: None,
            to: None,
            predicate: Some("production_supported".into()),
            envelope_overrides: strong.clone(),
            evidence: Vec::new(),
            rejection_code_contains: Some("MISSING_EVIDENCE".into()),
        },
    ]);

    vectors.push(NormativeVector {
        id: "accept:production_success:strong".into(),
        kind: "production_success".into(),
        expectation: VectorExpectation::Accept,
        dimension: None,
        from: None,
        to: None,
        predicate: None,
        envelope_overrides: strong.clone(),
        evidence: all_ev.clone(),
        rejection_code_contains: None,
    });
    vectors.push(NormativeVector {
        id: "reject:production_success:fixture".into(),
        kind: "production_success".into(),
        expectation: VectorExpectation::Reject,
        dimension: None,
        from: None,
        to: None,
        predicate: None,
        envelope_overrides: ov(&[
            ("origin", "fixture"),
            ("integrity", "signature_valid"),
            ("authority", "valid"),
            ("policy", "allowed"),
            ("proof", "verified"),
            ("freshness", "current"),
            ("effect", "observed"),
            ("environment", "live"),
            ("review", "human_reviewed"),
        ]),
        evidence: all_ev.clone(),
        rejection_code_contains: None,
    });
    vectors.push(NormativeVector {
        id: "reject:production_success:simulated".into(),
        kind: "production_success".into(),
        expectation: VectorExpectation::Reject,
        dimension: None,
        from: None,
        to: None,
        predicate: None,
        envelope_overrides: ov(&[
            ("origin", "simulated"),
            ("integrity", "signature_valid"),
            ("authority", "valid"),
            ("policy", "allowed"),
            ("proof", "verified"),
            ("freshness", "current"),
            ("effect", "observed"),
            ("environment", "live"),
            ("review", "human_reviewed"),
        ]),
        evidence: all_ev.clone(),
        rejection_code_contains: None,
    });
    vectors.push(NormativeVector {
        id: "reject:production_success:hermetic_env".into(),
        kind: "production_success".into(),
        expectation: VectorExpectation::Reject,
        dimension: None,
        from: None,
        to: None,
        predicate: None,
        envelope_overrides: ov(&[
            ("origin", "live_observed"),
            ("integrity", "signature_valid"),
            ("authority", "valid"),
            ("policy", "allowed"),
            ("proof", "verified"),
            ("freshness", "current"),
            ("effect", "observed"),
            ("environment", "hermetic"),
            ("review", "human_reviewed"),
        ]),
        evidence: all_ev.clone(),
        rejection_code_contains: None,
    });
    vectors.push(NormativeVector {
        id: "accept:verified_claim:strong".into(),
        kind: "verified_claim".into(),
        expectation: VectorExpectation::Accept,
        dimension: None,
        from: None,
        to: None,
        predicate: None,
        envelope_overrides: strong,
        evidence: all_ev.clone(),
        rejection_code_contains: None,
    });
    vectors.push(NormativeVector {
        id: "reject:verified_claim:started_only".into(),
        kind: "verified_claim".into(),
        expectation: VectorExpectation::Reject,
        dimension: None,
        from: None,
        to: None,
        predicate: None,
        envelope_overrides: ov(&[
            ("origin", "live_observed"),
            ("integrity", "signature_valid"),
            ("authority", "valid"),
            ("policy", "allowed"),
            ("proof", "verified"),
            ("freshness", "current"),
            ("effect", "started"),
            ("environment", "live"),
            ("review", "human_reviewed"),
        ]),
        evidence: all_ev,
        rejection_code_contains: None,
    });

    vectors
}

#[cfg(test)]
mod unit_smoke {
    use super::*;

    #[test]
    fn weakest_defaults_are_non_success() {
        let e = EvidenceEnvelope::weakest();
        assert!(!production_supported_dimensions(&e));
        assert!(!effect_successful_dimensions(&e));
        assert!(ProductionSuccessClaim::try_admit(e, &EvidenceBag::all_normative()).is_err());
    }
}

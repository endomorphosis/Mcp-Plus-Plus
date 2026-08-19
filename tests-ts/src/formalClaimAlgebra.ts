/**
 * Formal Claim Algebra (FCA) executable TypeScript binding — FACP-018.
 *
 * Closed, bounded evidence-product algebra matching
 * `facp/formal-claim-algebra-v1@1` and `facp/promotion-rules@1`.
 *
 * Public APIs fail closed: unknown enum spellings are rejected, unknown
 * transitions are rejected, and production-success / verified claim types
 * cannot be constructed without satisfying the normative predicates and
 * evidence bag. Browser-supplied policy/consent/allow/dry_run fields cannot
 * construct authority.valid or effect.observed (browser-safe projection).
 */

export const VOCAB_SCHEMA = "facp/formal-claim-algebra-v1@1" as const;
export const RULES_SCHEMA = "facp/promotion-rules@1" as const;
export const TASK_ID = "FACP-018" as const;
export const GOAL_ID = "FACP-G120" as const;
export const BUNDLE = "facp/fca/typescript" as const;
export const UNKNOWN_TRANSITION_POLICY = "reject" as const;

export const DIMENSION_ORDER = [
  "origin",
  "integrity",
  "authority",
  "policy",
  "proof",
  "freshness",
  "effect",
  "environment",
  "review"
] as const;

export const PREDICATE_ORDER = [
  "production_supported",
  "effect_successful",
  "proof_reusable",
  "receipt_authoritative",
  "release_admissible"
] as const;

export type DimensionName = (typeof DIMENSION_ORDER)[number];
export type PredicateName = (typeof PREDICATE_ORDER)[number];

export type FcaError =
  | { kind: "unknown_enum"; dimension: string; value: string }
  | { kind: "missing_field"; field: string }
  | { kind: "unknown_field"; field: string }
  | { kind: "transition_rejected"; dimension: string; from: string; to: string; code: string }
  | { kind: "predicate_rejected"; predicate: string; code: string }
  | { kind: "outcome_rejected"; outcome: string; code: string }
  | { kind: "browser_projection_rejected"; code: string; detail: string };

export function formatFcaError(err: FcaError): string {
  switch (err.kind) {
    case "unknown_enum":
      return `unknown enum value for ${err.dimension}: ${err.value}`;
    case "missing_field":
      return `missing envelope field: ${err.field}`;
    case "unknown_field":
      return `unknown envelope field: ${err.field}`;
    case "transition_rejected":
      return `transition rejected (${err.code}): ${err.dimension} ${err.from} -> ${err.to}`;
    case "predicate_rejected":
      return `predicate rejected (${err.code}): ${err.predicate}`;
    case "outcome_rejected":
      return `outcome rejected (${err.code}): ${err.outcome}`;
    case "browser_projection_rejected":
      return `browser projection rejected (${err.code}): ${err.detail}`;
  }
}

export type Result<T> = { ok: true; value: T } | { ok: false; error: FcaError };

function ok<T>(value: T): Result<T> {
  return { ok: true, value };
}
function err<T = never>(error: FcaError): Result<T> {
  return { ok: false, error };
}

export const ORIGIN_VALUES = ["absent", "declared", "fixture", "simulated", "hermetic_observed", "live_observed"] as const;
export type Origin = (typeof ORIGIN_VALUES)[number];
export function parseOrigin(value: string): Result<Origin> {
  if ((ORIGIN_VALUES as readonly string[]).includes(value)) {
    return ok(value as Origin);
  }
  return err({ kind: "unknown_enum", dimension: "origin", value });
}

export const INTEGRITY_VALUES = ["unchecked", "structurally_valid", "digest_valid", "signature_valid"] as const;
export type Integrity = (typeof INTEGRITY_VALUES)[number];
export function parseIntegrity(value: string): Result<Integrity> {
  if ((INTEGRITY_VALUES as readonly string[]).includes(value)) {
    return ok(value as Integrity);
  }
  return err({ kind: "unknown_enum", dimension: "integrity", value });
}

export const AUTHORITY_VALUES = ["unchecked", "absent", "valid", "expired", "revoked", "denied"] as const;
export type Authority = (typeof AUTHORITY_VALUES)[number];
export function parseAuthority(value: string): Result<Authority> {
  if ((AUTHORITY_VALUES as readonly string[]).includes(value)) {
    return ok(value as Authority);
  }
  return err({ kind: "unknown_enum", dimension: "authority", value });
}

export const POLICY_VALUES = ["unchecked", "allowed", "denied", "allowed_with_obligations", "indeterminate"] as const;
export type Policy = (typeof POLICY_VALUES)[number];
export function parsePolicy(value: string): Result<Policy> {
  if ((POLICY_VALUES as readonly string[]).includes(value)) {
    return ok(value as Policy);
  }
  return err({ kind: "unknown_enum", dimension: "policy", value });
}

export const PROOF_VALUES = ["none", "candidate", "verified", "refuted", "unknown", "verifier_unavailable"] as const;
export type Proof = (typeof PROOF_VALUES)[number];
export function parseProof(value: string): Result<Proof> {
  if ((PROOF_VALUES as readonly string[]).includes(value)) {
    return ok(value as Proof);
  }
  return err({ kind: "unknown_enum", dimension: "proof", value });
}

export const FRESHNESS_VALUES = ["current", "stale", "superseded", "withdrawn"] as const;
export type Freshness = (typeof FRESHNESS_VALUES)[number];
export function parseFreshness(value: string): Result<Freshness> {
  if ((FRESHNESS_VALUES as readonly string[]).includes(value)) {
    return ok(value as Freshness);
  }
  return err({ kind: "unknown_enum", dimension: "freshness", value });
}

export const EFFECT_VALUES = ["not_started", "reserved", "started", "externally_unknown", "observed", "compensated", "failed"] as const;
export type Effect = (typeof EFFECT_VALUES)[number];
export function parseEffect(value: string): Result<Effect> {
  if ((EFFECT_VALUES as readonly string[]).includes(value)) {
    return ok(value as Effect);
  }
  return err({ kind: "unknown_enum", dimension: "effect", value });
}

export const ENVIRONMENT_VALUES = ["hermetic", "conditional", "live"] as const;
export type Environment = (typeof ENVIRONMENT_VALUES)[number];
export function parseEnvironment(value: string): Result<Environment> {
  if ((ENVIRONMENT_VALUES as readonly string[]).includes(value)) {
    return ok(value as Environment);
  }
  return err({ kind: "unknown_enum", dimension: "environment", value });
}

export const REVIEW_VALUES = ["unreviewed", "machine_reviewed", "human_reviewed"] as const;
export type Review = (typeof REVIEW_VALUES)[number];
export function parseReview(value: string): Result<Review> {
  if ((REVIEW_VALUES as readonly string[]).includes(value)) {
    return ok(value as Review);
  }
  return err({ kind: "unknown_enum", dimension: "review", value });
}

export const CLOSED_OUTCOME_VALUES = ["Unavailable", "Rejected", "Simulated", "Attempted", "Unknown", "Observed", "Verified", "Failed", "Compensated"] as const;
export type ClosedOutcome = (typeof CLOSED_OUTCOME_VALUES)[number];
export function parseClosedOutcome(value: string): Result<ClosedOutcome> {
  if ((CLOSED_OUTCOME_VALUES as readonly string[]).includes(value)) {
    return ok(value as ClosedOutcome);
  }
  return err({ kind: "unknown_enum", dimension: "closed_outcome", value });
}

export const PROMOTION_PREDICATE_VALUES = PREDICATE_ORDER;
export type PromotionPredicate = PredicateName;
export function parsePromotionPredicate(value: string): Result<PromotionPredicate> {
  if ((PREDICATE_ORDER as readonly string[]).includes(value)) {
    return ok(value as PromotionPredicate);
  }
  return err({ kind: "unknown_enum", dimension: "promotion_predicate", value });
}

export type Dimension =
  | "origin"
  | "integrity"
  | "authority"
  | "policy"
  | "proof"
  | "freshness"
  | "effect"
  | "environment"
  | "review";

export function parseDimension(value: string): Result<Dimension> {
  if ((DIMENSION_ORDER as readonly string[]).includes(value)) {
    return ok(value as Dimension);
  }
  return err({ kind: "unknown_enum", dimension: "dimension", value });
}

export interface EvidenceEnvelope {
  origin: Origin;
  integrity: Integrity;
  authority: Authority;
  policy: Policy;
  proof: Proof;
  freshness: Freshness;
  effect: Effect;
  environment: Environment;
  review: Review;
}

export function weakestEnvelope(): EvidenceEnvelope {
  return {
    origin: "absent",
    integrity: "unchecked",
    authority: "unchecked",
    policy: "unchecked",
    proof: "none",
    freshness: "stale",
    effect: "not_started",
    environment: "hermetic",
    review: "unreviewed",
  };
}

export function strongProductEnvelope(): EvidenceEnvelope {
  return {
    origin: "live_observed",
    integrity: "signature_valid",
    authority: "valid",
    policy: "allowed",
    proof: "verified",
    freshness: "current",
    effect: "observed",
    environment: "live",
    review: "human_reviewed",
  };
}

export function envelopeToDimensionMap(envelope: EvidenceEnvelope): Record<string, string> {
  const map: Record<string, string> = {};
  for (const dim of DIMENSION_ORDER) {
    map[dim] = envelope[dim];
  }
  return map;
}

export function envelopeFromDimensionMap(
  map: Record<string, string>,
): Result<EvidenceEnvelope> {
  for (const key of Object.keys(map)) {
    if (!(DIMENSION_ORDER as readonly string[]).includes(key)) {
      return err({ kind: "unknown_field", field: key });
    }
  }
  const get = (name: DimensionName): Result<string> => {
    if (!(name in map) || map[name] === undefined) {
      return err({ kind: "missing_field", field: name });
    }
    return ok(map[name]!);
  };
  const originR = (() => { const r = get("origin"); return r.ok ? parseOrigin(r.value) : r; })();
  if (!originR.ok) return originR;
  const integrityR = (() => { const r = get("integrity"); return r.ok ? parseIntegrity(r.value) : r; })();
  if (!integrityR.ok) return integrityR;
  const authorityR = (() => { const r = get("authority"); return r.ok ? parseAuthority(r.value) : r; })();
  if (!authorityR.ok) return authorityR;
  const policyR = (() => { const r = get("policy"); return r.ok ? parsePolicy(r.value) : r; })();
  if (!policyR.ok) return policyR;
  const proofR = (() => { const r = get("proof"); return r.ok ? parseProof(r.value) : r; })();
  if (!proofR.ok) return proofR;
  const freshnessR = (() => { const r = get("freshness"); return r.ok ? parseFreshness(r.value) : r; })();
  if (!freshnessR.ok) return freshnessR;
  const effectR = (() => { const r = get("effect"); return r.ok ? parseEffect(r.value) : r; })();
  if (!effectR.ok) return effectR;
  const environmentR = (() => { const r = get("environment"); return r.ok ? parseEnvironment(r.value) : r; })();
  if (!environmentR.ok) return environmentR;
  const reviewR = (() => { const r = get("review"); return r.ok ? parseReview(r.value) : r; })();
  if (!reviewR.ok) return reviewR;
  return ok({
    origin: originR.value,
    integrity: integrityR.value,
    authority: authorityR.value,
    policy: policyR.value,
    proof: proofR.value,
    freshness: freshnessR.value,
    effect: effectR.value,
    environment: environmentR.value,
    review: reviewR.value,
  });
}

export function envelopeToCanonicalJson(envelope: EvidenceEnvelope): string {
  // Deterministic key order via DIMENSION_ORDER.
  const ordered: Record<string, string> = {};
  for (const dim of DIMENSION_ORDER) {
    ordered[dim] = envelope[dim];
  }
  return JSON.stringify(ordered);
}

export function envelopeFromCanonicalJson(text: string): Result<EvidenceEnvelope> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return err({ kind: "unknown_field", field: "<invalid_json>" });
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return err({ kind: "unknown_field", field: "<non_object>" });
  }
  const obj = parsed as Record<string, unknown>;
  const map: Record<string, string> = {};
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v !== "string") {
      return err({ kind: "unknown_enum", dimension: k, value: String(v) });
    }
    map[k] = v;
  }
  return envelopeFromDimensionMap(map);
}

export function getDimension(envelope: EvidenceEnvelope, dimension: Dimension): string {
  return envelope[dimension];
}

function withDimensionRaw(
  envelope: EvidenceEnvelope,
  dimension: Dimension,
  value: string,
): Result<EvidenceEnvelope> {
  const map = envelopeToDimensionMap(envelope);
  map[dimension] = value;
  return envelopeFromDimensionMap(map);
}

export class EvidenceBag {
  private readonly keys: Set<string>;

  constructor(keys: Iterable<string> = []) {
    this.keys = new Set(keys);
  }

  static fromKeys(keys: Iterable<string>): EvidenceBag {
    return new EvidenceBag(keys);
  }

  insert(key: string): void {
    this.keys.add(key);
  }

  containsAll(required: readonly string[]): boolean {
    return required.every((k) => this.keys.has(k));
  }

  keySet(): ReadonlySet<string> {
    return this.keys;
  }

  static allNormative(): EvidenceBag {
    return EvidenceBag.fromKeys([
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
    ]);
  }
}

export interface AllowedEdge {
  readonly from: string;
  readonly to: string;
  readonly requiresEvidence: readonly string[];
}

export interface ForbiddenEdge {
  readonly from: string;
  readonly to: string;
  readonly whenMissingEvidence: readonly string[] | null;
  readonly neverSufficientByRelabel: boolean;
  readonly rejectionCode: string;
}

export const ORIGIN_ALLOWED: readonly AllowedEdge[] = [
  { from: "absent", to: "declared", requiresEvidence: [] as const },
  { from: "absent", to: "fixture", requiresEvidence: [] as const },
  { from: "absent", to: "simulated", requiresEvidence: [] as const },
  { from: "absent", to: "hermetic_observed", requiresEvidence: ["independent_effect_observation"] as const },
  { from: "absent", to: "live_observed", requiresEvidence: ["live_qualification_receipt"] as const },
  { from: "declared", to: "hermetic_observed", requiresEvidence: ["independent_effect_observation"] as const },
  { from: "declared", to: "live_observed", requiresEvidence: ["live_qualification_receipt", "independent_effect_observation"] as const },
  { from: "hermetic_observed", to: "live_observed", requiresEvidence: ["live_qualification_receipt"] as const },
];

export const ORIGIN_FORBIDDEN: readonly ForbiddenEdge[] = [
  { from: "fixture", to: "live_observed", whenMissingEvidence: null, neverSufficientByRelabel: false, rejectionCode: "NONIMP_FIXTURE_TO_OBSERVED" },
  { from: "fixture", to: "hermetic_observed", whenMissingEvidence: null, neverSufficientByRelabel: false, rejectionCode: "NONIMP_FIXTURE_TO_OBSERVED" },
  { from: "simulated", to: "live_observed", whenMissingEvidence: null, neverSufficientByRelabel: false, rejectionCode: "NONIMP_SIMULATED_TO_LIVE" },
  { from: "simulated", to: "hermetic_observed", whenMissingEvidence: null, neverSufficientByRelabel: false, rejectionCode: "NONIMP_SIMULATED_TO_LIVE" },
];

export const INTEGRITY_ALLOWED: readonly AllowedEdge[] = [
  { from: "unchecked", to: "structurally_valid", requiresEvidence: [] as const },
  { from: "unchecked", to: "digest_valid", requiresEvidence: ["canonical_digest_match"] as const },
  { from: "unchecked", to: "signature_valid", requiresEvidence: ["canonical_digest_match", "authentic_signature"] as const },
  { from: "structurally_valid", to: "digest_valid", requiresEvidence: ["canonical_digest_match"] as const },
  { from: "structurally_valid", to: "signature_valid", requiresEvidence: ["canonical_digest_match", "authentic_signature"] as const },
  { from: "digest_valid", to: "signature_valid", requiresEvidence: ["authentic_signature"] as const },
];

export const INTEGRITY_FORBIDDEN: readonly ForbiddenEdge[] = [
];

export const AUTHORITY_ALLOWED: readonly AllowedEdge[] = [
  { from: "unchecked", to: "absent", requiresEvidence: [] as const },
  { from: "unchecked", to: "valid", requiresEvidence: ["argument_bound_delegation", "non_revoked_ucan"] as const },
  { from: "unchecked", to: "expired", requiresEvidence: [] as const },
  { from: "unchecked", to: "revoked", requiresEvidence: [] as const },
  { from: "unchecked", to: "denied", requiresEvidence: [] as const },
  { from: "absent", to: "valid", requiresEvidence: ["argument_bound_delegation", "non_revoked_ucan"] as const },
  { from: "valid", to: "expired", requiresEvidence: [] as const },
  { from: "valid", to: "revoked", requiresEvidence: [] as const },
  { from: "valid", to: "denied", requiresEvidence: [] as const },
];

export const AUTHORITY_FORBIDDEN: readonly ForbiddenEdge[] = [
  { from: "expired", to: "valid", whenMissingEvidence: null, neverSufficientByRelabel: true, rejectionCode: "FORBIDDEN_RELABEL:authority:expired->valid" },
  { from: "revoked", to: "valid", whenMissingEvidence: null, neverSufficientByRelabel: true, rejectionCode: "FORBIDDEN_RELABEL:authority:revoked->valid" },
  { from: "denied", to: "valid", whenMissingEvidence: null, neverSufficientByRelabel: true, rejectionCode: "FORBIDDEN_RELABEL:authority:denied->valid" },
];

export const POLICY_ALLOWED: readonly AllowedEdge[] = [
  { from: "unchecked", to: "allowed", requiresEvidence: ["authenticated_host_policy_decision"] as const },
  { from: "unchecked", to: "denied", requiresEvidence: [] as const },
  { from: "unchecked", to: "allowed_with_obligations", requiresEvidence: ["authenticated_host_policy_decision"] as const },
  { from: "unchecked", to: "indeterminate", requiresEvidence: [] as const },
  { from: "indeterminate", to: "allowed", requiresEvidence: ["authenticated_host_policy_decision"] as const },
  { from: "indeterminate", to: "denied", requiresEvidence: [] as const },
  { from: "allowed_with_obligations", to: "allowed", requiresEvidence: ["obligations_discharged"] as const },
  { from: "allowed_with_obligations", to: "denied", requiresEvidence: [] as const },
];

export const POLICY_FORBIDDEN: readonly ForbiddenEdge[] = [
  { from: "denied", to: "allowed", whenMissingEvidence: null, neverSufficientByRelabel: true, rejectionCode: "FORBIDDEN_RELABEL:policy:denied->allowed" },
];

export const PROOF_ALLOWED: readonly AllowedEdge[] = [
  { from: "none", to: "candidate", requiresEvidence: [] as const },
  { from: "none", to: "unknown", requiresEvidence: [] as const },
  { from: "none", to: "verifier_unavailable", requiresEvidence: [] as const },
  { from: "candidate", to: "verified", requiresEvidence: ["named_current_verifier", "verifier_admission_closure"] as const },
  { from: "candidate", to: "refuted", requiresEvidence: [] as const },
  { from: "candidate", to: "unknown", requiresEvidence: [] as const },
  { from: "candidate", to: "verifier_unavailable", requiresEvidence: [] as const },
  { from: "unknown", to: "verified", requiresEvidence: ["named_current_verifier", "verifier_admission_closure"] as const },
  { from: "unknown", to: "refuted", requiresEvidence: [] as const },
  { from: "verifier_unavailable", to: "verified", requiresEvidence: ["named_current_verifier", "verifier_admission_closure"] as const },
  { from: "verified", to: "refuted", requiresEvidence: [] as const },
  { from: "verified", to: "unknown", requiresEvidence: [] as const },
];

export const PROOF_FORBIDDEN: readonly ForbiddenEdge[] = [
  { from: "candidate", to: "verified", whenMissingEvidence: ["named_current_verifier", "verifier_admission_closure"] as const, neverSufficientByRelabel: false, rejectionCode: "NONIMP_CANDIDATE_TO_VERIFIED" },
];

export const FRESHNESS_ALLOWED: readonly AllowedEdge[] = [
  { from: "current", to: "stale", requiresEvidence: [] as const },
  { from: "current", to: "superseded", requiresEvidence: [] as const },
  { from: "current", to: "withdrawn", requiresEvidence: [] as const },
  { from: "stale", to: "superseded", requiresEvidence: [] as const },
  { from: "stale", to: "withdrawn", requiresEvidence: [] as const },
  { from: "superseded", to: "withdrawn", requiresEvidence: [] as const },
];

export const FRESHNESS_FORBIDDEN: readonly ForbiddenEdge[] = [
  { from: "stale", to: "current", whenMissingEvidence: null, neverSufficientByRelabel: false, rejectionCode: "NONIMP_STALE_TO_CURRENT" },
  { from: "superseded", to: "current", whenMissingEvidence: null, neverSufficientByRelabel: false, rejectionCode: "NONIMP_STALE_TO_CURRENT" },
  { from: "withdrawn", to: "current", whenMissingEvidence: null, neverSufficientByRelabel: false, rejectionCode: "NONIMP_STALE_TO_CURRENT" },
  { from: "withdrawn", to: "stale", whenMissingEvidence: null, neverSufficientByRelabel: false, rejectionCode: "NONIMP_STALE_TO_CURRENT" },
];

export const EFFECT_ALLOWED: readonly AllowedEdge[] = [
  { from: "not_started", to: "reserved", requiresEvidence: [] as const },
  { from: "not_started", to: "started", requiresEvidence: [] as const },
  { from: "reserved", to: "started", requiresEvidence: [] as const },
  { from: "started", to: "externally_unknown", requiresEvidence: [] as const },
  { from: "started", to: "observed", requiresEvidence: ["independent_effect_observation"] as const },
  { from: "started", to: "failed", requiresEvidence: [] as const },
  { from: "externally_unknown", to: "observed", requiresEvidence: ["independent_effect_observation"] as const },
  { from: "externally_unknown", to: "failed", requiresEvidence: [] as const },
  { from: "externally_unknown", to: "compensated", requiresEvidence: [] as const },
  { from: "observed", to: "compensated", requiresEvidence: [] as const },
  { from: "failed", to: "compensated", requiresEvidence: [] as const },
];

export const EFFECT_FORBIDDEN: readonly ForbiddenEdge[] = [
  { from: "not_started", to: "observed", whenMissingEvidence: null, neverSufficientByRelabel: false, rejectionCode: "NONIMP_DECLARED_TO_OBSERVED" },
  { from: "externally_unknown", to: "observed", whenMissingEvidence: ["independent_effect_observation"] as const, neverSufficientByRelabel: false, rejectionCode: "NONIMP_UNKNOWN_TO_OBSERVED" },
];

export const ENVIRONMENT_ALLOWED: readonly AllowedEdge[] = [
  { from: "hermetic", to: "conditional", requiresEvidence: [] as const },
  { from: "conditional", to: "live", requiresEvidence: ["live_qualification_receipt", "current_capability_admission"] as const },
];

export const ENVIRONMENT_FORBIDDEN: readonly ForbiddenEdge[] = [
  { from: "hermetic", to: "live", whenMissingEvidence: null, neverSufficientByRelabel: false, rejectionCode: "NONIMP_HERMETIC_TO_LIVE" },
  { from: "conditional", to: "live", whenMissingEvidence: ["live_qualification_receipt", "current_capability_admission"] as const, neverSufficientByRelabel: false, rejectionCode: "NONIMP_INVENTORY_TO_LIVE" },
];

export const REVIEW_ALLOWED: readonly AllowedEdge[] = [
  { from: "unreviewed", to: "machine_reviewed", requiresEvidence: [] as const },
  { from: "unreviewed", to: "human_reviewed", requiresEvidence: [] as const },
  { from: "machine_reviewed", to: "human_reviewed", requiresEvidence: [] as const },
];

export const REVIEW_FORBIDDEN: readonly ForbiddenEdge[] = [
];

function tablesFor(dimension: Dimension): {
  allowed: readonly AllowedEdge[];
  forbidden: readonly ForbiddenEdge[];
} {
  switch (dimension) {
    case "origin":
      return { allowed: ORIGIN_ALLOWED, forbidden: ORIGIN_FORBIDDEN };
    case "integrity":
      return { allowed: INTEGRITY_ALLOWED, forbidden: INTEGRITY_FORBIDDEN };
    case "authority":
      return { allowed: AUTHORITY_ALLOWED, forbidden: AUTHORITY_FORBIDDEN };
    case "policy":
      return { allowed: POLICY_ALLOWED, forbidden: POLICY_FORBIDDEN };
    case "proof":
      return { allowed: PROOF_ALLOWED, forbidden: PROOF_FORBIDDEN };
    case "freshness":
      return { allowed: FRESHNESS_ALLOWED, forbidden: FRESHNESS_FORBIDDEN };
    case "effect":
      return { allowed: EFFECT_ALLOWED, forbidden: EFFECT_FORBIDDEN };
    case "environment":
      return { allowed: ENVIRONMENT_ALLOWED, forbidden: ENVIRONMENT_FORBIDDEN };
    case "review":
      return { allowed: REVIEW_ALLOWED, forbidden: REVIEW_FORBIDDEN };
  }
}

function parseDimensionValue(dimension: Dimension, value: string): Result<string> {
  let parsed: Result<string>;
  switch (dimension) {
    case "origin":
      parsed = parseOrigin(value);
      break;
    case "integrity":
      parsed = parseIntegrity(value);
      break;
    case "authority":
      parsed = parseAuthority(value);
      break;
    case "policy":
      parsed = parsePolicy(value);
      break;
    case "proof":
      parsed = parseProof(value);
      break;
    case "freshness":
      parsed = parseFreshness(value);
      break;
    case "effect":
      parsed = parseEffect(value);
      break;
    case "environment":
      parsed = parseEnvironment(value);
      break;
    case "review":
      parsed = parseReview(value);
      break;
  }
  if (!parsed.ok) return parsed;
  return ok(value);
}

export function transitionAllowed(
  dimension: Dimension,
  from: string,
  to: string,
  evidence: EvidenceBag,
): Result<true> {
  const fromR = parseDimensionValue(dimension, from);
  if (!fromR.ok) return fromR;
  const toR = parseDimensionValue(dimension, to);
  if (!toR.ok) return toR;

  const { allowed, forbidden } = tablesFor(dimension);

  for (const edge of forbidden) {
    if (edge.from === from && edge.to === to) {
      if (edge.whenMissingEvidence !== null) {
        if (evidence.containsAll(edge.whenMissingEvidence)) {
          continue;
        }
        return err({
          kind: "transition_rejected",
          dimension,
          from,
          to,
          code: edge.rejectionCode,
        });
      }
      return err({
        kind: "transition_rejected",
        dimension,
        from,
        to,
        code: edge.rejectionCode,
      });
    }
  }

  for (const edge of allowed) {
    if (edge.from === from && edge.to === to) {
      if (edge.requiresEvidence.length > 0 && !evidence.containsAll(edge.requiresEvidence)) {
        return err({
          kind: "transition_rejected",
          dimension,
          from,
          to,
          code: `MISSING_TRANSITION_EVIDENCE:${dimension}`,
        });
      }
      return ok(true);
    }
  }

  return err({
    kind: "transition_rejected",
    dimension,
    from,
    to,
    code: `UNKNOWN_TRANSITION:${dimension}:${from}->${to}`,
  });
}

export function applyTransition(
  envelope: EvidenceEnvelope,
  dimension: Dimension,
  to: string,
  evidence: EvidenceBag,
): Result<EvidenceEnvelope> {
  const from = getDimension(envelope, dimension);
  const allowed = transitionAllowed(dimension, from, to, evidence);
  if (!allowed.ok) return allowed;
  return withDimensionRaw(envelope, dimension, to);
}

export function productionSupportedDimensions(e: EvidenceEnvelope): boolean {
  return (
    e.origin === "live_observed" &&
    (e.integrity === "digest_valid" || e.integrity === "signature_valid") &&
    e.authority === "valid" &&
    (e.policy === "allowed" || e.policy === "allowed_with_obligations") &&
    e.freshness === "current" &&
    e.environment === "live"
  );
}

export function effectSuccessfulDimensions(e: EvidenceEnvelope): boolean {
  return (
    (e.origin === "hermetic_observed" || e.origin === "live_observed") &&
    (e.integrity === "digest_valid" || e.integrity === "signature_valid") &&
    e.authority === "valid" &&
    (e.policy === "allowed" || e.policy === "allowed_with_obligations") &&
    e.freshness === "current" &&
    e.effect === "observed"
  );
}

export function proofReusableDimensions(e: EvidenceEnvelope): boolean {
  return (
    (e.integrity === "digest_valid" || e.integrity === "signature_valid") &&
    e.proof === "verified" &&
    e.freshness === "current"
  );
}

export function receiptAuthoritativeDimensions(e: EvidenceEnvelope): boolean {
  return (
    (e.origin === "hermetic_observed" || e.origin === "live_observed") &&
    e.integrity === "signature_valid" &&
    e.authority === "valid" &&
    (e.policy === "allowed" || e.policy === "allowed_with_obligations") &&
    e.freshness === "current"
  );
}

export function releaseAdmissibleDimensions(e: EvidenceEnvelope): boolean {
  return (
    (e.origin === "hermetic_observed" || e.origin === "live_observed") &&
    e.integrity === "signature_valid" &&
    e.authority === "valid" &&
    (e.policy === "allowed" || e.policy === "allowed_with_obligations") &&
    e.proof === "verified" &&
    e.freshness === "current" &&
    (e.review === "machine_reviewed" || e.review === "human_reviewed")
  );
}

export function necessaryEvidence(predicate: PromotionPredicate): readonly string[] {
  switch (predicate) {
    case "production_supported":
      return [
        "live_qualification_receipt",
        "current_capability_admission",
        "authenticated_host_policy_decision",
      ];
    case "effect_successful":
      return ["independent_effect_observation", "admission_token"];
    case "proof_reusable":
      return ["named_current_verifier", "verifier_admission_closure"];
    case "receipt_authoritative":
      return ["signed_receipt", "non_revoked_delegation"];
    case "release_admissible":
      return [
        "exact_source_binding",
        "immutable_dependency_closure",
        "identified_build_environment",
        "current_proofs_and_tests",
        "contract_compatibility",
        "rights_resolution",
        "reproducibility_inputs",
        "signed_provenance",
      ];
  }
}

function dimensionsHold(predicate: PromotionPredicate, envelope: EvidenceEnvelope): boolean {
  switch (predicate) {
    case "production_supported":
      return productionSupportedDimensions(envelope);
    case "effect_successful":
      return effectSuccessfulDimensions(envelope);
    case "proof_reusable":
      return proofReusableDimensions(envelope);
    case "receipt_authoritative":
      return receiptAuthoritativeDimensions(envelope);
    case "release_admissible":
      return releaseAdmissibleDimensions(envelope);
  }
}

export function predicateHolds(
  predicate: PromotionPredicate,
  envelope: EvidenceEnvelope,
  evidence: EvidenceBag,
): Result<true> {
  if (!dimensionsHold(predicate, envelope)) {
    return err({
      kind: "predicate_rejected",
      predicate,
      code: `MISSING_DIMENSIONS:${predicate}`,
    });
  }
  if (!evidence.containsAll(necessaryEvidence(predicate))) {
    return err({
      kind: "predicate_rejected",
      predicate,
      code: `MISSING_EVIDENCE:${predicate}`,
    });
  }
  return ok(true);
}

/**
 * Gated production-success claim. Envelope is private; only tryAdmit constructs it.
 */
export class ProductionSuccessClaim {
  private constructor(private readonly _envelope: EvidenceEnvelope) {}

  static tryAdmit(envelope: EvidenceEnvelope, evidence: EvidenceBag): Result<ProductionSuccessClaim> {
    if (
      envelope.origin === "fixture" ||
      envelope.origin === "simulated" ||
      envelope.origin === "declared" ||
      envelope.origin === "absent"
    ) {
      return err({
        kind: "predicate_rejected",
        predicate: "production_supported",
        code: "NONIMP_FIXTURE_TO_OBSERVED",
      });
    }
    const a = predicateHolds("production_supported", envelope, evidence);
    if (!a.ok) return a;
    const b = predicateHolds("effect_successful", envelope, evidence);
    if (!b.ok) return b;
    return ok(new ProductionSuccessClaim(envelope));
  }

  envelope(): EvidenceEnvelope {
    return this._envelope;
  }

  outcome(): ClosedOutcome {
    return "Verified";
  }
}

/**
 * Gated Verified closed-outcome claim. Envelope private; only tryAdmit constructs it.
 */
export class VerifiedClaim {
  private constructor(private readonly _envelope: EvidenceEnvelope) {}

  static tryAdmit(envelope: EvidenceEnvelope, evidence: EvidenceBag): Result<VerifiedClaim> {
    if (envelope.effect !== "observed") {
      return err({
        kind: "outcome_rejected",
        outcome: "Verified",
        code: "MISSING_DIMENSIONS:effect_successful",
      });
    }
    if (
      envelope.origin === "fixture" ||
      envelope.origin === "simulated" ||
      envelope.origin === "declared" ||
      envelope.origin === "absent"
    ) {
      return err({
        kind: "outcome_rejected",
        outcome: "Verified",
        code: "NONIMP_FIXTURE_TO_OBSERVED",
      });
    }
    const a = predicateHolds("effect_successful", envelope, evidence);
    if (!a.ok) return a;
    const b = predicateHolds("proof_reusable", envelope, evidence);
    if (!b.ok) return b;
    return ok(new VerifiedClaim(envelope));
  }

  envelope(): EvidenceEnvelope {
    return this._envelope;
  }

  outcome(): ClosedOutcome {
    return "Verified";
  }
}

/** Browser presentation inputs — never host admission authority. */
export interface BrowserSuppliedFields {
  policy?: unknown;
  consent?: unknown;
  allow?: unknown;
  dry_run?: unknown;
  policy_decision?: unknown;
  confirmation_token?: unknown;
  [key: string]: unknown;
}

export const BROWSER_CLAIM_TOKENS = [
  "browser_policy",
  "browser_consent",
  "browser_allow",
  "browser_dry_run",
  "browser_policy_consent_allow",
] as const;

/**
 * Browser-safe projection: map presentation fields to a fail-closed envelope.
 * Never constructs authority.valid, policy.allowed, or effect.observed from
 * browser-supplied policy/consent/allow/dry_run fields.
 */
export function projectBrowserSafeEnvelope(
  fields: BrowserSuppliedFields = {},
): EvidenceEnvelope {
  void fields; // intentionally ignored for admission dimensions
  const base = weakestEnvelope();
  // Presentation intent at best: declared origin; authority/policy unevaluated;
  // effect not started (never observed from browser fields alone).
  return {
    ...base,
    origin: "declared",
    authority: "unchecked",
    policy: "unchecked",
    effect: "not_started",
    proof: "none",
    freshness: "stale",
    integrity: "unchecked",
    environment: "hermetic",
    review: "unreviewed",
  };
}

/**
 * Reject any attempt to construct authority.valid or effect.observed (or
 * policy.allowed) from browser-supplied policy/consent fields / claim tokens.
 */
export function rejectBrowserAuthorityOrObservation(input: {
  fields?: BrowserSuppliedFields;
  claimTokens?: readonly string[];
  requestedAuthority?: string;
  requestedPolicy?: string;
  requestedEffect?: string;
}): Result<never> {
  const fields = input.fields ?? {};
  const tokens = new Set(input.claimTokens ?? []);
  const browserKeys = ["policy", "consent", "allow", "dry_run", "policy_decision", "confirmation_token"];
  const hasBrowserFields = browserKeys.some((k) => k in fields && fields[k] !== undefined);
  const hasBrowserTokens = BROWSER_CLAIM_TOKENS.some((t) => tokens.has(t)) ||
    [...tokens].some((t) => t.startsWith("browser_"));

  if (!hasBrowserFields && !hasBrowserTokens) {
    return err({
      kind: "browser_projection_rejected",
      code: "NONIMP_BROWSER_TO_HOST_POLICY",
      detail: "no browser-supplied fields or claim tokens present",
    });
  }

  const reqAuth = input.requestedAuthority;
  const reqPol = input.requestedPolicy;
  const reqEff = input.requestedEffect;

  if (reqAuth === "valid") {
    return err({
      kind: "browser_projection_rejected",
      code: "NONIMP_PAYMENT_TO_AUTHORITY",
      detail: "browser policy/consent cannot construct authority.valid",
    });
  }
  if (reqPol === "allowed" || reqPol === "allowed_with_obligations") {
    return err({
      kind: "browser_projection_rejected",
      code: "NONIMP_BROWSER_TO_HOST_POLICY",
      detail: "browser policy/consent cannot construct policy.allowed",
    });
  }
  if (reqEff === "observed") {
    return err({
      kind: "browser_projection_rejected",
      code: "NONIMP_DECLARED_TO_OBSERVED",
      detail: "browser policy/consent cannot construct effect.observed",
    });
  }

  // Even without an explicit request, refuse constructing strong dims from browser inputs.
  return err({
    kind: "browser_projection_rejected",
    code: "NONIMP_BROWSER_TO_HOST_POLICY",
    detail: "browser-supplied fields are presentation-only; host admission required",
  });
}

/**
 * Attempt to build an envelope from browser fields into requested strong dims.
 * Always fails closed for authority.valid / policy.allowed / effect.observed.
 */
export function tryConstructFromBrowserFields(
  fields: BrowserSuppliedFields,
  requested: Partial<EvidenceEnvelope> = {},
): Result<EvidenceEnvelope> {
  const blocked = rejectBrowserAuthorityOrObservation({
    fields,
    requestedAuthority: requested.authority,
    requestedPolicy: requested.policy,
    requestedEffect: requested.effect,
  });
  if (!blocked.ok) {
    // If caller asked for strong dims, surface that rejection; otherwise still reject construction path.
    if (
      requested.authority === "valid" ||
      requested.policy === "allowed" ||
      requested.policy === "allowed_with_obligations" ||
      requested.effect === "observed"
    ) {
      return blocked;
    }
  }
  // Safe path: only the browser-safe projection is allowed.
  if (
    requested.authority === "valid" ||
    requested.policy === "allowed" ||
    requested.policy === "allowed_with_obligations" ||
    requested.effect === "observed"
  ) {
    return rejectBrowserAuthorityOrObservation({
      fields,
      requestedAuthority: requested.authority,
      requestedPolicy: requested.policy,
      requestedEffect: requested.effect,
    });
  }
  return ok(projectBrowserSafeEnvelope(fields));
}

export type VectorExpectation = "accept" | "reject";

export interface NormativeVector {
  id: string;
  kind: string;
  expectation: VectorExpectation;
  dimension?: string;
  from?: string;
  to?: string;
  predicate?: string;
  envelopeOverrides: Array<[string, string]>;
  evidence: string[];
  rejectionCodeContains?: string;
}

function envelopeFromOverrides(overrides: Array<[string, string]>): Result<EvidenceEnvelope> {
  const map = envelopeToDimensionMap(weakestEnvelope());
  for (const [k, v] of overrides) {
    map[k] = v;
  }
  return envelopeFromDimensionMap(map);
}

export function evaluateNormativeVector(vector: NormativeVector): Result<true> {
  const evidence = EvidenceBag.fromKeys(vector.evidence);
  const envelopeR = envelopeFromOverrides(vector.envelopeOverrides);
  if (!envelopeR.ok) {
    return err(envelopeR.error);
  }
  const envelope = envelopeR.value;

  const check = (result: Result<unknown>): Result<true> => {
    if (vector.expectation === "accept") {
      if (result.ok) return ok(true);
      return err(result.error);
    }
    // reject
    if (!result.ok) {
      if (vector.rejectionCodeContains) {
        const msg = formatFcaError(result.error);
        if (!msg.includes(vector.rejectionCodeContains) && !("code" in result.error && String((result.error as { code?: string }).code ?? "").includes(vector.rejectionCodeContains))) {
          return err({
            kind: "transition_rejected",
            dimension: vector.dimension ?? "?",
            from: vector.from ?? "?",
            to: vector.to ?? "?",
            code: `EXPECTED_CODE:${vector.rejectionCodeContains}:GOT:${msg}`,
          });
        }
      }
      return ok(true);
    }
    return err({
      kind: "transition_rejected",
      dimension: vector.dimension ?? "?",
      from: vector.from ?? "?",
      to: vector.to ?? "?",
      code: `EXPECTED_REJECT:${vector.id}`,
    });
  };

  switch (vector.kind) {
    case "transition": {
      const dimR = parseDimension(vector.dimension ?? "");
      if (!dimR.ok) return dimR;
      const from = vector.from ?? "";
      const to = vector.to ?? "";
      const startMap = envelopeToDimensionMap(weakestEnvelope());
      for (const [k, v] of vector.envelopeOverrides) {
        startMap[k] = v;
      }
      startMap[dimR.value] = from;
      const startR = envelopeFromDimensionMap(startMap);
      if (!startR.ok) return startR;
      return check(applyTransition(startR.value, dimR.value, to, evidence));
    }
    case "predicate": {
      const predR = parsePromotionPredicate(vector.predicate ?? "");
      if (!predR.ok) return predR;
      return check(predicateHolds(predR.value, envelope, evidence));
    }
    case "production_success":
      return check(ProductionSuccessClaim.tryAdmit(envelope, evidence));
    case "verified_claim":
      return check(VerifiedClaim.tryAdmit(envelope, evidence));
    default:
      return err({
        kind: "unknown_enum",
        dimension: "vector_kind",
        value: vector.kind,
      });
  }
}

function rejectTransition(
  id: string,
  dimension: string,
  from: string,
  to: string,
  evidence: string[],
  code: string,
): NormativeVector {
  return {
    id,
    kind: "transition",
    expectation: "reject",
    dimension,
    from,
    to,
    envelopeOverrides: [],
    evidence,
    rejectionCodeContains: code,
  };
}

function rejectPredicate(
  id: string,
  predicate: string,
  overrides: Array<[string, string]>,
  evidence: string[],
  code: string,
): NormativeVector {
  return {
    id,
    kind: "predicate",
    expectation: "reject",
    predicate,
    envelopeOverrides: overrides,
    evidence,
    rejectionCodeContains: code,
  };
}

export function normativeVectors(): NormativeVector[] {
  const vectors: NormativeVector[] = [];
  const tables: Array<[string, readonly AllowedEdge[]]> = [
    ["origin", ORIGIN_ALLOWED],
    ["integrity", INTEGRITY_ALLOWED],
    ["authority", AUTHORITY_ALLOWED],
    ["policy", POLICY_ALLOWED],
    ["proof", PROOF_ALLOWED],
    ["freshness", FRESHNESS_ALLOWED],
    ["effect", EFFECT_ALLOWED],
    ["environment", ENVIRONMENT_ALLOWED],
    ["review", REVIEW_ALLOWED],
  ];
  for (const [dimName, edges] of tables) {
    for (const edge of edges) {
      vectors.push({
        id: `accept:${dimName}:${edge.from}->${edge.to}`,
        kind: "transition",
        expectation: "accept",
        dimension: dimName,
        from: edge.from,
        to: edge.to,
        envelopeOverrides: [],
        evidence: [...edge.requiresEvidence],
      });
    }
  }

  vectors.push(
    rejectTransition("reject:origin:fixture->live_observed", "origin", "fixture", "live_observed", ["live_qualification_receipt"], "NONIMP_FIXTURE_TO_OBSERVED"),
    rejectTransition("reject:origin:fixture->hermetic_observed", "origin", "fixture", "hermetic_observed", ["independent_effect_observation"], "NONIMP_FIXTURE_TO_OBSERVED"),
    rejectTransition("reject:origin:simulated->live_observed", "origin", "simulated", "live_observed", ["live_qualification_receipt"], "NONIMP_SIMULATED_TO_LIVE"),
    rejectTransition("reject:origin:simulated->hermetic_observed", "origin", "simulated", "hermetic_observed", ["independent_effect_observation"], "NONIMP_SIMULATED_TO_LIVE"),
    rejectTransition("reject:authority:expired->valid", "authority", "expired", "valid", ["argument_bound_delegation", "non_revoked_ucan"], "FORBIDDEN_RELABEL"),
    rejectTransition("reject:authority:revoked->valid", "authority", "revoked", "valid", ["argument_bound_delegation", "non_revoked_ucan"], "FORBIDDEN_RELABEL"),
    rejectTransition("reject:authority:denied->valid", "authority", "denied", "valid", ["argument_bound_delegation", "non_revoked_ucan"], "FORBIDDEN_RELABEL"),
    rejectTransition("reject:policy:denied->allowed", "policy", "denied", "allowed", ["authenticated_host_policy_decision"], "FORBIDDEN_RELABEL"),
    rejectTransition("reject:proof:candidate->verified:missing_evidence", "proof", "candidate", "verified", [], "NONIMP_CANDIDATE_TO_VERIFIED"),
    rejectTransition("reject:freshness:stale->current", "freshness", "stale", "current", [], "NONIMP_STALE_TO_CURRENT"),
    rejectTransition("reject:freshness:superseded->current", "freshness", "superseded", "current", [], "NONIMP_STALE_TO_CURRENT"),
    rejectTransition("reject:freshness:withdrawn->current", "freshness", "withdrawn", "current", [], "NONIMP_STALE_TO_CURRENT"),
    rejectTransition("reject:freshness:withdrawn->stale", "freshness", "withdrawn", "stale", [], "NONIMP_STALE_TO_CURRENT"),
    rejectTransition("reject:effect:not_started->observed", "effect", "not_started", "observed", ["independent_effect_observation"], "NONIMP_DECLARED_TO_OBSERVED"),
    rejectTransition("reject:effect:externally_unknown->observed:missing_evidence", "effect", "externally_unknown", "observed", [], "NONIMP_UNKNOWN_TO_OBSERVED"),
    rejectTransition("reject:environment:hermetic->live", "environment", "hermetic", "live", ["live_qualification_receipt", "current_capability_admission"], "NONIMP_HERMETIC_TO_LIVE"),
    rejectTransition("reject:environment:conditional->live:missing_evidence", "environment", "conditional", "live", [], "NONIMP_INVENTORY_TO_LIVE"),
    rejectTransition("reject:unknown:origin:fixture->declared", "origin", "fixture", "declared", [], "UNKNOWN_TRANSITION"),
    rejectTransition("reject:origin:absent->live_observed:missing_evidence", "origin", "absent", "live_observed", [], "MISSING_TRANSITION_EVIDENCE"),
  );

  const strong: Array<[string, string]> = [
    ["origin", "live_observed"],
    ["integrity", "signature_valid"],
    ["authority", "valid"],
    ["policy", "allowed"],
    ["proof", "verified"],
    ["freshness", "current"],
    ["effect", "observed"],
    ["environment", "live"],
    ["review", "human_reviewed"],
  ];
  const allEv = [...EvidenceBag.allNormative().keySet()];

  for (const pred of PREDICATE_ORDER) {
    vectors.push({
      id: `accept:predicate:${pred}`,
      kind: "predicate",
      expectation: "accept",
      predicate: pred,
      envelopeOverrides: [...strong],
      evidence: [...allEv],
    });
  }

  vectors.push(
    rejectPredicate(
      "reject:predicate:production_supported:fixture",
      "production_supported",
      [
        ["origin", "fixture"],
        ["integrity", "signature_valid"],
        ["authority", "valid"],
        ["policy", "allowed"],
        ["proof", "verified"],
        ["freshness", "current"],
        ["effect", "observed"],
        ["environment", "live"],
        ["review", "human_reviewed"],
      ],
      ["live_qualification_receipt", "current_capability_admission", "authenticated_host_policy_decision"],
      "MISSING_DIMENSIONS",
    ),
    rejectPredicate(
      "reject:predicate:production_supported:stale",
      "production_supported",
      [
        ["origin", "live_observed"],
        ["integrity", "signature_valid"],
        ["authority", "valid"],
        ["policy", "allowed"],
        ["proof", "verified"],
        ["freshness", "stale"],
        ["effect", "observed"],
        ["environment", "live"],
        ["review", "human_reviewed"],
      ],
      ["live_qualification_receipt", "current_capability_admission", "authenticated_host_policy_decision"],
      "MISSING_DIMENSIONS",
    ),
    rejectPredicate(
      "reject:predicate:production_supported:expired",
      "production_supported",
      [
        ["origin", "live_observed"],
        ["integrity", "signature_valid"],
        ["authority", "expired"],
        ["policy", "allowed"],
        ["proof", "verified"],
        ["freshness", "current"],
        ["effect", "observed"],
        ["environment", "live"],
        ["review", "human_reviewed"],
      ],
      ["live_qualification_receipt", "current_capability_admission", "authenticated_host_policy_decision"],
      "MISSING_DIMENSIONS",
    ),
    rejectPredicate(
      "reject:predicate:effect_successful:externally_unknown",
      "effect_successful",
      [
        ["origin", "live_observed"],
        ["integrity", "signature_valid"],
        ["authority", "valid"],
        ["policy", "allowed"],
        ["proof", "verified"],
        ["freshness", "current"],
        ["effect", "externally_unknown"],
        ["environment", "live"],
        ["review", "human_reviewed"],
      ],
      ["independent_effect_observation", "admission_token"],
      "MISSING_DIMENSIONS",
    ),
    rejectPredicate(
      "reject:predicate:proof_reusable:candidate",
      "proof_reusable",
      [
        ["origin", "live_observed"],
        ["integrity", "signature_valid"],
        ["authority", "valid"],
        ["policy", "allowed"],
        ["proof", "candidate"],
        ["freshness", "current"],
        ["effect", "observed"],
        ["environment", "live"],
        ["review", "human_reviewed"],
      ],
      ["named_current_verifier", "verifier_admission_closure"],
      "MISSING_DIMENSIONS",
    ),
    rejectPredicate(
      "reject:predicate:proof_reusable:digest_only",
      "proof_reusable",
      [
        ["origin", "live_observed"],
        ["integrity", "digest_valid"],
        ["authority", "valid"],
        ["policy", "allowed"],
        ["proof", "none"],
        ["freshness", "current"],
        ["effect", "observed"],
        ["environment", "live"],
        ["review", "human_reviewed"],
      ],
      ["named_current_verifier", "verifier_admission_closure"],
      "MISSING_DIMENSIONS",
    ),
    {
      id: "reject:predicate:production_supported:missing_evidence",
      kind: "predicate",
      expectation: "reject",
      predicate: "production_supported",
      envelopeOverrides: [...strong],
      evidence: [],
      rejectionCodeContains: "MISSING_EVIDENCE",
    },
  );

  vectors.push({
    id: "accept:production_success:strong",
    kind: "production_success",
    expectation: "accept",
    envelopeOverrides: [...strong],
    evidence: [...allEv],
  });
  vectors.push({
    id: "reject:production_success:fixture",
    kind: "production_success",
    expectation: "reject",
    envelopeOverrides: [
      ["origin", "fixture"],
      ["integrity", "signature_valid"],
      ["authority", "valid"],
      ["policy", "allowed"],
      ["proof", "verified"],
      ["freshness", "current"],
      ["effect", "observed"],
      ["environment", "live"],
      ["review", "human_reviewed"],
    ],
    evidence: [...allEv],
  });
  vectors.push({
    id: "reject:production_success:simulated",
    kind: "production_success",
    expectation: "reject",
    envelopeOverrides: [
      ["origin", "simulated"],
      ["integrity", "signature_valid"],
      ["authority", "valid"],
      ["policy", "allowed"],
      ["proof", "verified"],
      ["freshness", "current"],
      ["effect", "observed"],
      ["environment", "live"],
      ["review", "human_reviewed"],
    ],
    evidence: [...allEv],
  });
  vectors.push({
    id: "reject:production_success:hermetic_env",
    kind: "production_success",
    expectation: "reject",
    envelopeOverrides: [
      ["origin", "live_observed"],
      ["integrity", "signature_valid"],
      ["authority", "valid"],
      ["policy", "allowed"],
      ["proof", "verified"],
      ["freshness", "current"],
      ["effect", "observed"],
      ["environment", "hermetic"],
      ["review", "human_reviewed"],
    ],
    evidence: [...allEv],
  });
  vectors.push({
    id: "accept:verified_claim:strong",
    kind: "verified_claim",
    expectation: "accept",
    envelopeOverrides: [...strong],
    evidence: [...allEv],
  });
  vectors.push({
    id: "reject:verified_claim:started_only",
    kind: "verified_claim",
    expectation: "reject",
    envelopeOverrides: [
      ["origin", "live_observed"],
      ["integrity", "signature_valid"],
      ["authority", "valid"],
      ["policy", "allowed"],
      ["proof", "verified"],
      ["freshness", "current"],
      ["effect", "started"],
      ["environment", "live"],
      ["review", "human_reviewed"],
    ],
    evidence: [...allEv],
  });

  return vectors;
}

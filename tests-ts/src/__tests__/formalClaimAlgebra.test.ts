/**
 * FACP-018: executable TypeScript Formal Claim Algebra binding tests.
 *
 * Acceptance:
 * - TypeScript accepts/rejects every normative vector.
 * - Browser-supplied policy/consent fields cannot construct authority.valid
 *   or effect.observed (browser-safe projection).
 * - Illegal transitions cannot construct a success type through public APIs.
 */

import { describe, it, expect } from 'vitest';
import {
  VOCAB_SCHEMA,
  RULES_SCHEMA,
  TASK_ID,
  GOAL_ID,
  BUNDLE,
  UNKNOWN_TRANSITION_POLICY,
  DIMENSION_ORDER,
  PREDICATE_ORDER,
  ORIGIN_VALUES,
  INTEGRITY_VALUES,
  AUTHORITY_VALUES,
  POLICY_VALUES,
  PROOF_VALUES,
  FRESHNESS_VALUES,
  EFFECT_VALUES,
  ENVIRONMENT_VALUES,
  REVIEW_VALUES,
  CLOSED_OUTCOME_VALUES,
  ORIGIN_ALLOWED,
  ORIGIN_FORBIDDEN,
  INTEGRITY_ALLOWED,
  AUTHORITY_ALLOWED,
  AUTHORITY_FORBIDDEN,
  POLICY_ALLOWED,
  POLICY_FORBIDDEN,
  PROOF_ALLOWED,
  PROOF_FORBIDDEN,
  FRESHNESS_ALLOWED,
  FRESHNESS_FORBIDDEN,
  EFFECT_ALLOWED,
  EFFECT_FORBIDDEN,
  ENVIRONMENT_ALLOWED,
  ENVIRONMENT_FORBIDDEN,
  REVIEW_ALLOWED,
  parseOrigin,
  parseIntegrity,
  parseAuthority,
  parsePolicy,
  parseProof,
  parseFreshness,
  parseEffect,
  parseEnvironment,
  parseReview,
  parseClosedOutcome,
  parsePromotionPredicate,
  weakestEnvelope,
  strongProductEnvelope,
  envelopeToCanonicalJson,
  envelopeFromCanonicalJson,
  envelopeFromDimensionMap,
  envelopeToDimensionMap,
  EvidenceBag,
  transitionAllowed,
  applyTransition,
  productionSupportedDimensions,
  effectSuccessfulDimensions,
  proofReusableDimensions,
  receiptAuthoritativeDimensions,
  releaseAdmissibleDimensions,
  predicateHolds,
  necessaryEvidence,
  ProductionSuccessClaim,
  VerifiedClaim,
  normativeVectors,
  evaluateNormativeVector,
  formatFcaError,
  projectBrowserSafeEnvelope,
  rejectBrowserAuthorityOrObservation,
  tryConstructFromBrowserFields,
  BROWSER_CLAIM_TOKENS,
} from '../formalClaimAlgebra.js';

describe('FACP-018 TypeScript FCA binding', () => {
  it('kernel identity matches FACP-018', () => {
    expect(VOCAB_SCHEMA).toBe('facp/formal-claim-algebra-v1@1');
    expect(RULES_SCHEMA).toBe('facp/promotion-rules@1');
    expect(TASK_ID).toBe('FACP-018');
    expect(GOAL_ID).toBe('FACP-G120');
    expect(BUNDLE).toBe('facp/fca/typescript');
    expect(UNKNOWN_TRANSITION_POLICY).toBe('reject');
    expect([...DIMENSION_ORDER]).toEqual([
      'origin',
      'integrity',
      'authority',
      'policy',
      'proof',
      'freshness',
      'effect',
      'environment',
      'review',
    ]);
    expect([...PREDICATE_ORDER]).toEqual([
      'production_supported',
      'effect_successful',
      'proof_reusable',
      'receipt_authoritative',
      'release_admissible',
    ]);
  });

  it('closed carriers reject unknown spellings', () => {
    expect(parseOrigin('live_observed').ok).toBe(true);
    expect(parseOrigin('LIVE_OBSERVED').ok).toBe(false);
    expect(parseIntegrity('maybe_valid').ok).toBe(false);
    expect(parseAuthority('payment').ok).toBe(false);
    expect(parsePolicy('browser_allow').ok).toBe(false);
    expect(parseProof('proven').ok).toBe(false);
    expect(parseFreshness('fresh').ok).toBe(false);
    expect(parseEffect('success').ok).toBe(false);
    expect(parseEnvironment('prod').ok).toBe(false);
    expect(parseReview('peer_reviewed').ok).toBe(false);
    expect(parseClosedOutcome('Success').ok).toBe(false);
    expect(parsePromotionPredicate('supported').ok).toBe(false);
  });

  it('carrier name tables are exhaustive', () => {
    expect(ORIGIN_VALUES).toHaveLength(6);
    expect(INTEGRITY_VALUES).toHaveLength(4);
    expect(AUTHORITY_VALUES).toHaveLength(6);
    expect(POLICY_VALUES).toHaveLength(5);
    expect(PROOF_VALUES).toHaveLength(6);
    expect(FRESHNESS_VALUES).toHaveLength(4);
    expect(EFFECT_VALUES).toHaveLength(7);
    expect(ENVIRONMENT_VALUES).toHaveLength(3);
    expect(REVIEW_VALUES).toHaveLength(3);
    expect(CLOSED_OUTCOME_VALUES).toHaveLength(9);
    for (const name of ORIGIN_VALUES) {
      const parsed = parseOrigin(name);
      expect(parsed.ok).toBe(true);
      if (parsed.ok) expect(parsed.value).toBe(name);
    }
    for (const name of PROOF_VALUES) {
      const parsed = parseProof(name);
      expect(parsed.ok).toBe(true);
      if (parsed.ok) expect(parsed.value).toBe(name);
    }
    for (const name of CLOSED_OUTCOME_VALUES) {
      const parsed = parseClosedOutcome(name);
      expect(parsed.ok).toBe(true);
      if (parsed.ok) expect(parsed.value).toBe(name);
    }
  });

  it('canonical serialization round-trips and rejects unknown fields', () => {
    const envelope = strongProductEnvelope();
    const json = envelopeToCanonicalJson(envelope);
    const parsed = envelopeFromCanonicalJson(json);
    expect(parsed.ok).toBe(true);
    if (parsed.ok) expect(parsed.value).toEqual(envelope);

    const bad =
      '{"origin":"absent","integrity":"unchecked","authority":"unchecked","policy":"unchecked","proof":"none","freshness":"stale","effect":"not_started","environment":"hermetic","review":"unreviewed","extra":true}';
    expect(envelopeFromCanonicalJson(bad).ok).toBe(false);

    const map = envelopeToDimensionMap(envelope);
    map['bogus'] = 'value';
    const unknown = envelopeFromDimensionMap(map);
    expect(unknown.ok).toBe(false);
    if (!unknown.ok) expect(unknown.error.kind).toBe('unknown_field');

    const incomplete: Record<string, string> = { origin: 'absent' };
    const missing = envelopeFromDimensionMap(incomplete);
    expect(missing.ok).toBe(false);
    if (!missing.ok) expect(missing.error.kind).toBe('missing_field');
  });

  it('every normative vector accepts or rejects as expected', () => {
    const vectors = normativeVectors();
    expect(vectors.length).toBeGreaterThanOrEqual(65);
    let accept = 0;
    let reject = 0;
    for (const vector of vectors) {
      const result = evaluateNormativeVector(vector);
      expect(result.ok, `${vector.id}: ${result.ok ? '' : formatFcaError(result.error)}`).toBe(
        true,
      );
      if (vector.expectation === 'accept') accept += 1;
      else reject += 1;
    }
    expect(accept).toBeGreaterThanOrEqual(40);
    expect(reject).toBeGreaterThanOrEqual(20);
  });

  it('illegal transitions cannot construct production success', () => {
    const bag = EvidenceBag.allNormative();

    const fixture = { ...strongProductEnvelope(), origin: 'fixture' as const };
    expect(transitionAllowed('origin', 'fixture', 'live_observed', bag).ok).toBe(false);
    expect(ProductionSuccessClaim.tryAdmit(fixture, bag).ok).toBe(false);
    expect(VerifiedClaim.tryAdmit(fixture, bag).ok).toBe(false);

    const hermetic = weakestEnvelope();
    expect(applyTransition(hermetic, 'environment', 'live', bag).ok).toBe(false);

    const expired = { ...strongProductEnvelope(), authority: 'expired' as const };
    expect(applyTransition(expired, 'authority', 'valid', bag).ok).toBe(false);
    expect(ProductionSuccessClaim.tryAdmit(expired, bag).ok).toBe(false);

    const stale = { ...strongProductEnvelope(), freshness: 'stale' as const };
    expect(applyTransition(stale, 'freshness', 'current', bag).ok).toBe(false);
    expect(ProductionSuccessClaim.tryAdmit(stale, bag).ok).toBe(false);

    const empty = new EvidenceBag();
    expect(transitionAllowed('proof', 'candidate', 'verified', empty).ok).toBe(false);
    const withVerifier = EvidenceBag.fromKeys([
      'named_current_verifier',
      'verifier_admission_closure',
    ]);
    expect(transitionAllowed('proof', 'candidate', 'verified', withVerifier).ok).toBe(true);

    const strong = strongProductEnvelope();
    const success = ProductionSuccessClaim.tryAdmit(strong, bag);
    expect(success.ok).toBe(true);
    if (success.ok) {
      expect(success.value.outcome()).toBe('Verified');
      expect(success.value.envelope()).toEqual(strong);
    }
    const verified = VerifiedClaim.tryAdmit(strong, bag);
    expect(verified.ok).toBe(true);
    if (verified.ok) {
      expect(verified.value.outcome()).toBe('Verified');
      expect(verified.value.envelope()).toEqual(strong);
    }
  });

  it('dimension predicate parity with strong and weak envelopes', () => {
    const strong = strongProductEnvelope();
    expect(productionSupportedDimensions(strong)).toBe(true);
    expect(effectSuccessfulDimensions(strong)).toBe(true);
    expect(proofReusableDimensions(strong)).toBe(true);
    expect(receiptAuthoritativeDimensions(strong)).toBe(true);
    expect(releaseAdmissibleDimensions(strong)).toBe(true);

    const weak = weakestEnvelope();
    expect(productionSupportedDimensions(weak)).toBe(false);
    expect(effectSuccessfulDimensions(weak)).toBe(false);
    expect(proofReusableDimensions(weak)).toBe(false);
    expect(receiptAuthoritativeDimensions(weak)).toBe(false);
    expect(releaseAdmissibleDimensions(weak)).toBe(false);

    const bag = EvidenceBag.allNormative();
    for (const pred of PREDICATE_ORDER) {
      expect(predicateHolds(pred, strong, bag).ok).toBe(true);
      expect(predicateHolds(pred, weak, bag).ok).toBe(false);
      expect(necessaryEvidence(pred).length).toBeGreaterThan(0);
    }
  });

  it('transition table counts match promotion-rules parity', () => {
    expect(ORIGIN_ALLOWED).toHaveLength(8);
    expect(ORIGIN_FORBIDDEN).toHaveLength(4);
    expect(INTEGRITY_ALLOWED).toHaveLength(6);
    expect(AUTHORITY_ALLOWED).toHaveLength(9);
    expect(AUTHORITY_FORBIDDEN).toHaveLength(3);
    expect(POLICY_ALLOWED).toHaveLength(8);
    expect(POLICY_FORBIDDEN).toHaveLength(1);
    expect(PROOF_ALLOWED).toHaveLength(12);
    expect(PROOF_FORBIDDEN).toHaveLength(1);
    expect(FRESHNESS_ALLOWED).toHaveLength(6);
    expect(FRESHNESS_FORBIDDEN).toHaveLength(4);
    expect(EFFECT_ALLOWED).toHaveLength(11);
    expect(EFFECT_FORBIDDEN).toHaveLength(2);
    expect(ENVIRONMENT_ALLOWED).toHaveLength(2);
    expect(ENVIRONMENT_FORBIDDEN).toHaveLength(2);
    expect(REVIEW_ALLOWED).toHaveLength(3);
  });

  it('browser-safe projection cannot construct authority or observation', () => {
    const fields = {
      policy: { outcome: 'allow' },
      consent: 'granted',
      allow: true,
      dry_run: false,
      policy_decision: { outcome: 'allow' },
      confirmation_token: 'ui-token',
    };

    const projected = projectBrowserSafeEnvelope(fields);
    expect(projected.authority).not.toBe('valid');
    expect(projected.policy).not.toBe('allowed');
    expect(projected.policy).not.toBe('allowed_with_obligations');
    expect(projected.effect).not.toBe('observed');
    expect(projected.authority).toBe('unchecked');
    expect(projected.policy).toBe('unchecked');
    expect(projected.effect).toBe('not_started');

    // Differing only by browser allow/consent still yields identical admission dims.
    const denied = projectBrowserSafeEnvelope({ consent: 'denied', allow: false });
    expect(denied.authority).toBe(projected.authority);
    expect(denied.policy).toBe(projected.policy);
    expect(denied.effect).toBe(projected.effect);

    const rejectAuth = rejectBrowserAuthorityOrObservation({
      fields,
      requestedAuthority: 'valid',
    });
    expect(rejectAuth.ok).toBe(false);
    if (!rejectAuth.ok) {
      expect(rejectAuth.error.kind).toBe('browser_projection_rejected');
      expect(formatFcaError(rejectAuth.error)).toMatch(/authority\.valid|NONIMP_/);
    }

    const rejectObs = rejectBrowserAuthorityOrObservation({
      fields,
      requestedEffect: 'observed',
    });
    expect(rejectObs.ok).toBe(false);
    if (!rejectObs.ok) {
      expect(formatFcaError(rejectObs.error)).toMatch(/effect\.observed|NONIMP_/);
    }

    const rejectPol = rejectBrowserAuthorityOrObservation({
      fields,
      claimTokens: ['browser_policy', 'browser_consent'],
      requestedPolicy: 'allowed',
    });
    expect(rejectPol.ok).toBe(false);
    if (!rejectPol.ok) {
      expect(rejectPol.error.code).toBe('NONIMP_BROWSER_TO_HOST_POLICY');
    }

    const constructAuth = tryConstructFromBrowserFields(fields, {
      authority: 'valid',
      policy: 'allowed',
      effect: 'observed',
    });
    expect(constructAuth.ok).toBe(false);

    const safeOnly = tryConstructFromBrowserFields(fields, {});
    expect(safeOnly.ok).toBe(true);
    if (safeOnly.ok) {
      expect(safeOnly.value.authority).toBe('unchecked');
      expect(safeOnly.value.effect).toBe('not_started');
      expect(safeOnly.value.policy).toBe('unchecked');
    }

    // Browser claim tokens alone cannot promote host policy.
    for (const token of BROWSER_CLAIM_TOKENS) {
      const r = rejectBrowserAuthorityOrObservation({
        claimTokens: [token],
        requestedPolicy: 'allowed',
      });
      expect(r.ok).toBe(false);
    }

    // Success types remain unreachable from browser projection + empty evidence.
    expect(ProductionSuccessClaim.tryAdmit(projected, new EvidenceBag()).ok).toBe(false);
    expect(VerifiedClaim.tryAdmit(projected, EvidenceBag.allNormative()).ok).toBe(false);
  });
});

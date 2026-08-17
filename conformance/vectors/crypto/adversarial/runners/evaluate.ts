/**
 * AdversarialVector@1 TypeScript runner (MCPP-044).
 *
 * Loads shared fixtures and asserts every listed case fails closed using the
 * TypeScript DelegationProof@1 verifier for cryptographic cases and portable
 * fail-closed rules for attenuation / revocation / authority separation.
 *
 * Run from tests-ts: npx tsx ../conformance/vectors/crypto/adversarial/runners/evaluate.ts
 */
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { UCANDelegationValidator } from '../../../../tests-ts/src/validators/ucanDelegation.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const FIXTURES = join(ROOT, 'fixtures');

const REQUIRED = [
  'forged_signature',
  'altered_bytes',
  'wrong_audience',
  'expanded_capabilities',
  'expanded_resources',
  'expired',
  'future_nbf',
  'revoked',
  'missing_proof',
  'replay',
  'wrong_executor',
  'wrong_policy_cid',
  'valid_peerid_invalid_ucan',
] as const;

type Fixture = Record<string, unknown> & {
  id?: string;
  token?: Record<string, unknown>;
  chain?: Record<string, unknown>[];
  request?: Record<string, unknown>;
  issuer_public_keys?: Record<string, string>;
  expected_reason_codes?: string[];
  invocation?: Record<string, unknown>;
  peer_authenticated?: boolean;
  ucan_present?: boolean;
  ucan_valid?: boolean;
  peer_id?: string;
  revocation_record?: Record<string, unknown>;
  token_signature_valid?: boolean;
  replay_count?: number;
};

function load(caseId: string): Fixture {
  return JSON.parse(readFileSync(join(FIXTURES, `${caseId}.json`), 'utf8'));
}

function stripMeta(token: Record<string, unknown>): Record<string, unknown> {
  const out = { ...token };
  delete out.canonical_signing_bytes_hex;
  return out;
}

function cryptoFails(token: Record<string, unknown>, keys: Record<string, string>): boolean {
  const v = new UCANDelegationValidator({ issuerPublicKeys: keys, requireSignatures: true });
  const result = v.verifyDelegationProof(stripMeta(token), { issuerPublicKeys: keys });
  return !result.isValid;
}

function attenuateFails(chain: Record<string, unknown>[], request: Record<string, unknown>, seen = new Set<string>()): { denied: boolean; reason: string } {
  const now = Number(request.now ?? Date.now() / 1000);
  const audience = String(request.audience ?? '');
  const resource = String(request.resource ?? '');
  const method = String(request.method ?? '');
  const executor = request.executor == null ? '' : String(request.executor);
  const policyCid = request.policy_cid == null ? '' : String(request.policy_cid);

  if (!chain.length) return { denied: true, reason: 'empty_chain' };
  if (!audience || !resource || !method) return { denied: true, reason: 'invalid_token' };

  // Replay
  for (const t of chain) {
    const nonce = String(t.nnc ?? t.jti ?? t.nonce ?? '');
    if (nonce) {
      if (seen.has(nonce)) return { denied: true, reason: 'replayed' };
      seen.add(nonce);
    }
  }

  // Time
  for (const t of chain) {
    const exp = t.exp ?? t.expiry ?? t.expiration;
    const nbf = t.nbf ?? t.not_before;
    if (exp != null && Number(exp) <= now) return { denied: true, reason: 'expired' };
    if (nbf != null && Number(nbf) > now) return { denied: true, reason: 'not_yet_valid' };
  }

  // Audience leaf
  const leaf = chain[chain.length - 1];
  const leafAud = String(leaf.aud ?? leaf.audience ?? '');
  if (leafAud !== audience) return { denied: true, reason: 'audience_mismatch' };

  // Continuity
  for (let i = 1; i < chain.length; i++) {
    const prevAud = String(chain[i - 1].aud ?? chain[i - 1].audience ?? '');
    const iss = String(chain[i].iss ?? chain[i].issuer ?? '');
    if (prevAud !== iss) return { denied: true, reason: 'issuer_audience_continuity_failed' };
  }

  // Executor
  const bound = String(leaf.executor ?? leaf.exe ?? '');
  if (bound && bound !== executor) return { denied: true, reason: 'executor_binding_failed' };

  // Policy
  if (request.require_policy_cid || request.required_policy_cid) {
    const required = String(request.required_policy_cid ?? '');
    if (!policyCid) return { denied: true, reason: 'policy_cid_required' };
    if (required && policyCid !== required) return { denied: true, reason: 'policy_cid_mismatch' };
    const tokenPol = String(leaf.policy_cid ?? leaf.pol ?? '');
    if (tokenPol && policyCid !== tokenPol) return { denied: true, reason: 'policy_cid_mismatch' };
  }

  // Capability attenuation (segment cover)
  const capsOf = (t: Record<string, unknown>) => {
    const att = (t.att ?? t.capabilities ?? []) as Array<Record<string, unknown>>;
    return att.map((c) => ({
      resource: String(c.resource ?? c.with ?? ''),
      ability: String(c.ability ?? c.can ?? c.method ?? ''),
    })).filter((c) => c.resource && c.ability);
  };
  const covers = (parent: string, child: string) => {
    if (parent === '*' || parent === child) return true;
    if (parent.endsWith('/*')) return child.startsWith(parent.slice(0, -1)) && child.length > parent.length - 1;
    return false;
  };
  for (let i = 1; i < chain.length; i++) {
    const parents = capsOf(chain[i - 1]).filter((c) => c.ability !== 'ucan/DELEGATE' && c.ability !== '*');
    const children = capsOf(chain[i]).filter((c) => c.ability !== 'ucan/DELEGATE');
    for (const child of children) {
      const ok = parents.some((p) => covers(p.resource, child.resource) && covers(p.ability, child.ability));
      if (!ok) {
        const resOk = parents.some((p) => covers(p.resource, child.resource));
        if (!resOk) return { denied: true, reason: 'resource_attenuation_failed' };
        return { denied: true, reason: 'method_attenuation_failed' };
      }
    }
  }
  // Request granted by leaf
  const leafCaps = capsOf(leaf);
  if (!leafCaps.some((c) => covers(c.resource, resource) && covers(c.ability, method))) {
    return { denied: true, reason: 'capability_not_granted' };
  }
  return { denied: false, reason: 'ok' };
}

function evaluate(caseId: string): { fail_closed: boolean; reasons: string[] } {
  const fx = load(caseId);
  const keys = (fx.issuer_public_keys ?? {}) as Record<string, string>;

  if (caseId === 'forged_signature' || caseId === 'altered_bytes') {
    const bad = cryptoFails(fx.token as Record<string, unknown>, keys);
    return { fail_closed: bad, reasons: bad ? ['invalid_signature'] : ['accepted'] };
  }
  if (caseId === 'missing_proof') {
    const inv = fx.invocation ?? {};
    const missing = !('proof_cid' in inv);
    return { fail_closed: missing, reasons: missing ? ['missing_proof_cid'] : ['accepted'] };
  }
  if (caseId === 'revoked') {
    // Fail closed: presence of a revocation record targeting token cid.
    const token = fx.token as Record<string, unknown>;
    const rec = fx.revocation_record as Record<string, unknown>;
    const delCid = String((fx as { delegation_cid?: string }).delegation_cid ?? token?.cid ?? '');
    const match = String(rec?.revoked_delegation_cid ?? '') === delCid;
    return { fail_closed: match, reasons: match ? ['revoked'] : ['not_revoked'] };
  }
  if (caseId === 'valid_peerid_invalid_ucan') {
    const peerOk = !!fx.peer_authenticated;
    const cryptoBad = fx.token ? cryptoFails(fx.token as Record<string, unknown>, keys) : true;
    const fail = peerOk && (fx.ucan_valid === false || cryptoBad || !fx.ucan_present);
    return { fail_closed: fail, reasons: fail ? ['peerid_not_authority', 'invalid_ucan'] : ['accepted'] };
  }
  if (caseId === 'replay') {
    const seen = new Set<string>();
    const chain = (fx.chain ?? []).map((t) => stripMeta(t));
    const req = fx.request ?? {};
    const first = attenuateFails(chain, req, seen);
    if (first.denied) return { fail_closed: true, reasons: [first.reason] };
    const second = attenuateFails(chain, req, seen);
    return { fail_closed: second.denied, reasons: [second.reason] };
  }
  const chain = (fx.chain ?? []).map((t) => stripMeta(t));
  const result = attenuateFails(chain, fx.request ?? {});
  return { fail_closed: result.denied, reasons: [result.reason] };
}

function main(): void {
  const failures: string[] = [];
  for (const id of REQUIRED) {
    const v = evaluate(id);
    if (!v.fail_closed) failures.push(`${id}: not fail-closed ${JSON.stringify(v)}`);
  }
  // Ensure fixture files exist
  const files = new Set(readdirSync(FIXTURES));
  for (const id of REQUIRED) {
    if (!files.has(`${id}.json`)) failures.push(`missing fixture ${id}.json`);
  }
  if (failures.length) {
    console.error(JSON.stringify({ language: 'typescript', failures }, null, 2));
    process.exit(1);
  }
  console.log(JSON.stringify({ language: 'typescript', total: REQUIRED.length, fail_closed: REQUIRED.length }, null, 2));
}

main();

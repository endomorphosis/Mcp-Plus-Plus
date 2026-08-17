/**
 * UCAN Delegation Validator (TypeScript) — DelegationProof@1
 * Profile C: UCAN delegation chains with Ed25519 over mcpp-jcs-v1.
 *
 * Spec: docs/spec/ucan-delegation.md
 * Crypto: ADR-0002 (EdDSA/Ed25519, explicit kid, DID-compatible iss/aud,
 *         signatures over mcpp-jcs-v1 canonical bytes)
 * Levels: ADR-0003 structural vs cryptographic
 */

import { createPublicKey, verify as cryptoVerify } from 'node:crypto';
import { ZodError } from 'zod';
import { UCANTokenSchema, DelegationChainSchema } from '../models.js';
import { ALGORITHM_ID, canonicalizeBytes } from './canonicalJcs.js';

export const INTERFACE = 'DelegationProof@1';
export const CANONICAL_ALGORITHM = ALGORITHM_ID;
export const SIGNATURE_ALG_EDDSA = 'EdDSA';
export const SIGNATURE_ALG_ED25519 = 'Ed25519';

export interface LevelResult {
  valid: boolean;
  errors: string[];
  reason_code: string | null;
}

export interface ValidationResult {
  isValid: boolean;
  messageType: string;
  errors: string[];
  warnings: string[];
  metadata: Record<string, unknown>;
}

const SIG_META_KEYS = new Set([
  'signature',
  'sig',
  'signatures',
  'public_key',
  'publicKey',
  'public_key_b64',
  'issuer_public_key',
  'header',
  'protected',
  'alg',
  'kid',
  'signature_alg',
  'signatureAlg',
]);

const B58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';

function b64urlEncode(raw: Uint8Array): string {
  return Buffer.from(raw).toString('base64url');
}

function b64urlDecode(value: string): Buffer {
  const text = String(value || '').trim();
  if (!text) throw new Error('empty_base64url');
  for (const ch of text) {
    if (!/[A-Za-z0-9_-]/.test(ch)) throw new Error('invalid_base64url');
  }
  const decoded = Buffer.from(text, 'base64url');
  if (b64urlEncode(decoded) !== text) throw new Error('noncanonical_base64url');
  return decoded;
}

function base58btcDecode(value: string): Buffer {
  const text = String(value || '').trim();
  if (!text) return Buffer.alloc(0);
  let acc = 0n;
  for (const ch of text) {
    const idx = B58.indexOf(ch);
    if (idx < 0) throw new Error('invalid_base58btc');
    acc = acc * 58n + BigInt(idx);
  }
  let hex = acc.toString(16);
  if (hex.length % 2) hex = '0' + hex;
  const raw = acc === 0n ? Buffer.alloc(0) : Buffer.from(hex, 'hex');
  let zeros = 0;
  for (const ch of text) {
    if (ch !== '1') break;
    zeros += 1;
  }
  return Buffer.concat([Buffer.alloc(zeros), raw]);
}

export function ed25519PublicKeyFromDidKey(did: string): Buffer | null {
  const text = String(did || '').trim();
  if (!text.startsWith('did:key:')) return null;
  const mb = text.slice('did:key:'.length);
  if (!mb.startsWith('z')) return null;
  try {
    const decoded = base58btcDecode(mb.slice(1));
    if (decoded.length >= 34 && decoded[0] === 0xed && decoded[1] === 0x01) {
      return Buffer.from(decoded.subarray(2, 34));
    }
  } catch {
    return null;
  }
  return null;
}

function decodePublicKey(value: unknown): Buffer | null {
  if (value == null) return null;
  if (Buffer.isBuffer(value) || value instanceof Uint8Array) {
    const raw = Buffer.from(value);
    return raw.length === 32 ? raw : null;
  }
  if (typeof value === 'object' && !Array.isArray(value)) {
    const obj = value as Record<string, unknown>;
    const alg = String(obj['alg'] || obj['algorithm'] || '')
      .trim()
      .toLowerCase();
    if (alg && alg !== 'ed25519' && alg !== 'eddsa') return null;
    for (const key of [
      'public_key',
      'public_key_b64',
      'public_key_base64',
      'publicKey',
      'key',
      'did_key',
      'did',
    ]) {
      if (key in obj) {
        const decoded = decodePublicKey(obj[key]);
        if (decoded) return decoded;
      }
    }
    if ('public_key_hex' in obj) return decodePublicKey(obj['public_key_hex']);
    return null;
  }
  let text = String(value || '').trim();
  if (!text) return null;
  if (text.startsWith('did:key:')) return ed25519PublicKeyFromDidKey(text);
  if (text.startsWith('ed25519-pub:')) text = text.split(':').slice(1).join(':').trim();
  if (text.length === 64 && /^[0-9a-fA-F]+$/.test(text)) {
    const raw = Buffer.from(text, 'hex');
    return raw.length === 32 ? raw : null;
  }
  try {
    const raw = b64urlDecode(text);
    if (raw.length === 32) return raw;
  } catch {
    /* fall through */
  }
  try {
    const raw = Buffer.from(text, 'base64');
    if (raw.length === 32) return raw;
  } catch {
    return null;
  }
  return null;
}

function decodeSignature(value: unknown): Buffer | null {
  if (value == null) return null;
  if (Buffer.isBuffer(value) || value instanceof Uint8Array) {
    const raw = Buffer.from(value);
    return raw.length === 64 ? raw : null;
  }
  let text = String(value || '').trim();
  if (!text) return null;
  if (text.startsWith('ed25519:')) text = text.slice('ed25519:'.length).trim();
  else if (text.startsWith('ed25519-hex:') || text.startsWith('hex:')) {
    try {
      const raw = Buffer.from(text.split(':').slice(1).join(':').trim(), 'hex');
      return raw.length === 64 ? raw : null;
    } catch {
      return null;
    }
  }
  if (text.length === 128 && /^[0-9a-fA-F]+$/.test(text)) {
    const raw = Buffer.from(text, 'hex');
    return raw.length === 64 ? raw : null;
  }
  try {
    const raw = b64urlDecode(text);
    return raw.length === 64 ? raw : null;
  } catch {
    return null;
  }
}

function signingObjectFromToken(token: Record<string, unknown>): Record<string, unknown> {
  if (token['payload'] && typeof token['payload'] === 'object' && !Array.isArray(token['payload'])) {
    const body = { ...(token['payload'] as Record<string, unknown>) };
    for (const k of Object.keys(body)) {
      if (SIG_META_KEYS.has(k)) delete body[k];
    }
    return body;
  }
  const body: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(token)) {
    if (!SIG_META_KEYS.has(k) && k !== 'token') body[k] = v;
  }
  return body;
}

export function canonicalSigningBytes(token: Record<string, unknown>): Uint8Array {
  return canonicalizeBytes(signingObjectFromToken(token));
}

export function compactSigningInput(
  header: Record<string, unknown>,
  payload: Record<string, unknown>,
): Buffer {
  const h = b64urlEncode(canonicalizeBytes(header));
  const p = b64urlEncode(canonicalizeBytes(payload));
  return Buffer.from(`${h}.${p}`, 'ascii');
}

export function verifyEd25519(
  publicKey: Uint8Array,
  message: Uint8Array,
  signature: Uint8Array,
): boolean {
  if (publicKey.length !== 32 || signature.length !== 64) return false;
  try {
    const key = createPublicKey({
      key: Buffer.concat([
        // SPKI prefix for raw Ed25519 public key (RFC 8410)
        Buffer.from('302a300506032b6570032100', 'hex'),
        Buffer.from(publicKey),
      ]),
      format: 'der',
      type: 'spki',
    });
    return cryptoVerify(null, Buffer.from(message), key, Buffer.from(signature));
  } catch {
    return false;
  }
}

function level(
  valid: boolean,
  errors: string[] = [],
  reason_code: string | null = null,
): LevelResult {
  return { valid, errors: [...errors], reason_code };
}

function attachLevels(
  result: ValidationResult,
  structural: LevelResult,
  cryptographic: LevelResult,
): void {
  result.metadata['interface'] = INTERFACE;
  result.metadata['canonical_algorithm'] = CANONICAL_ALGORITHM;
  result.metadata['levels'] = { structural, cryptographic };
  if (structural.valid && cryptographic.valid) {
    result.metadata['conformance_level'] = 'cryptographic';
  } else if (structural.valid) {
    result.metadata['conformance_level'] = 'structural';
  } else {
    result.metadata['conformance_level'] = null;
  }
}

function emptyResult(messageType: string): ValidationResult {
  return {
    isValid: true,
    messageType,
    errors: [],
    warnings: [],
    metadata: {},
  };
}

export interface UCANValidatorOptions {
  issuerPublicKeys?: Record<string, unknown>;
  requireSignatures?: boolean;
}

export class UCANValidator {
  private issuerPublicKeys: Record<string, unknown>;
  private requireSignatures: boolean;

  constructor(options: UCANValidatorOptions = {}) {
    this.issuerPublicKeys = { ...(options.issuerPublicKeys || {}) };
    this.requireSignatures = Boolean(options.requireSignatures);
  }

  validateToken(token: Record<string, unknown>): ValidationResult {
    const result = emptyResult('ucan_token');
    try {
      UCANTokenSchema.parse(token);
    } catch (error) {
      if (error instanceof ZodError) {
        result.isValid = false;
        error.issues.forEach((issue) => {
          result.errors.push(`${issue.path.join('.')}: ${issue.message}`);
        });
      }
    }

    const keys = this.issuerPublicKeys;
    const { structuralErrors, cryptoErrors, cryptoReason, hasSig, cryptoOk } =
      this.validateTokenLevels(token, 0, keys);
    // Prefer zod structural when schema applies; merge hand-checks for aliases.
    const structuralOk = result.isValid && structuralErrors.length === 0;
    if (!structuralOk) {
      for (const err of structuralErrors) {
        if (!result.errors.includes(err)) result.errors.push(err);
      }
      result.isValid = false;
    }
    if (hasSig && !cryptoOk) {
      result.isValid = false;
      for (const err of cryptoErrors) {
        if (!result.errors.includes(err)) result.errors.push(err);
      }
    }
    attachLevels(
      result,
      level(structuralOk, structuralOk ? [] : result.errors, structuralOk ? null : 'structural_invalid'),
      level(
        structuralOk && cryptoOk,
        cryptoErrors,
        structuralOk && cryptoOk ? null : cryptoReason || (hasSig ? 'invalid_signature' : 'missing_signature'),
      ),
    );
    return result;
  }

  validateChain(chain: Record<string, unknown>): ValidationResult {
    const result = emptyResult('delegation_chain');
    try {
      DelegationChainSchema.parse(chain);
    } catch (error) {
      if (error instanceof ZodError) {
        result.isValid = false;
        error.issues.forEach((issue) => {
          result.errors.push(`${issue.path.join('.')}: ${issue.message}`);
        });
      }
    }
    const structuralOk = result.isValid;
    attachLevels(
      result,
      level(structuralOk, result.errors, structuralOk ? null : 'structural_invalid'),
      level(false, ['chain_object_crypto_not_evaluated'], 'chain_object_crypto_not_evaluated'),
    );
    return result;
  }

  validateDelegationChain(
    tokens: Record<string, unknown>[],
    options: {
      issuerPublicKeys?: Record<string, unknown>;
      requireSignatures?: boolean;
    } = {},
  ): ValidationResult {
    const result = emptyResult('delegation_chain');
    result.metadata['chainLength'] = tokens.length;

    const keys = { ...this.issuerPublicKeys, ...(options.issuerPublicKeys || {}) };
    const requireSig =
      options.requireSignatures === undefined
        ? this.requireSignatures
        : Boolean(options.requireSignatures);

    if (!Array.isArray(tokens) || tokens.length === 0) {
      result.isValid = false;
      result.errors.push(
        !Array.isArray(tokens)
          ? 'Delegation chain must be a list'
          : 'Delegation chain cannot be empty',
      );
      attachLevels(
        result,
        level(false, result.errors, 'empty_chain'),
        level(false, ['structural_failed'], 'structural_failed'),
      );
      return result;
    }

    const structuralErrors: string[] = [];
    const cryptoErrors: string[] = [];
    let cryptoReason: string | null = null;
    let sawSignature = false;
    let allCryptoOk = true;

    for (let i = 0; i < tokens.length; i++) {
      const token = tokens[i];
      if (token === undefined) continue;
      const tokenResult = this.validateTokenSchemaOnly(token);
      if (!tokenResult.isValid) {
        result.isValid = false;
        structuralErrors.push(`Token ${i}: ${tokenResult.errors.join(', ')}`);
        result.errors.push(`Token ${i}: ${tokenResult.errors.join(', ')}`);
      }

      const levels = this.validateTokenLevels(token, i, keys);
      structuralErrors.push(...levels.structuralErrors);
      for (const err of levels.structuralErrors) {
        if (!result.errors.includes(err)) {
          result.errors.push(err);
          result.isValid = false;
        }
      }
      if (levels.hasSig) sawSignature = true;
      if (levels.cryptoErrors.length) cryptoErrors.push(...levels.cryptoErrors);
      if (!levels.cryptoOk) {
        allCryptoOk = false;
        if (cryptoReason == null) cryptoReason = levels.cryptoReason;
        if (levels.hasSig || requireSig) {
          for (const err of levels.cryptoErrors) {
            if (!result.errors.includes(err)) result.errors.push(err);
          }
          if (levels.hasSig || requireSig) result.isValid = result.isValid && levels.cryptoOk;
          if (levels.hasSig && !levels.cryptoOk) result.isValid = false;
        }
      }
    }

    // Check chain continuity (aud of token[i] should match iss of token[i+1])
    for (let i = 0; i < tokens.length - 1; i++) {
      const current = tokens[i];
      const next = tokens[i + 1];
      if (current === undefined || next === undefined) continue;
      const currentAud = current['aud'] ?? current['audience'];
      const nextIss = next['iss'] ?? next['issuer'];
      if (currentAud !== nextIss) {
        result.isValid = false;
        const msg =
          `Chain broken between token ${i} and ${i + 1}: ` +
          `aud(${String(currentAud)}) != iss(${String(nextIss)})`;
        result.errors.push(msg);
        structuralErrors.push(msg);
      }
    }

    if (requireSig && !allCryptoOk) {
      result.isValid = false;
      if (!cryptoErrors.length) cryptoErrors.push('signatures_required');
      for (const err of cryptoErrors) {
        if (!result.errors.includes(err)) result.errors.push(err);
      }
    }

    // Structural validity is independent of cryptographic errors.
    const structuralValid = structuralErrors.length === 0;
    if (!structuralValid) result.isValid = false;

    const cryptographicOk = allCryptoOk && structuralValid;
    attachLevels(
      result,
      level(structuralValid, structuralErrors, structuralValid ? null : 'structural_invalid'),
      level(
        cryptographicOk,
        cryptoErrors.length
          ? cryptoErrors
          : cryptographicOk
            ? []
            : ['missing_signature'],
        cryptographicOk
          ? null
          : cryptoReason || (sawSignature ? 'invalid_signature' : 'missing_signature'),
      ),
    );
    result.metadata['require_signatures'] = requireSig;
    // Ensure forged signatures flip isValid even if structuralValid.
    if (sawSignature && !allCryptoOk) result.isValid = false;
    return result;
  }

  verifyDelegationProof(
    token: Record<string, unknown>,
    options: { publicKey?: unknown; issuerPublicKeys?: Record<string, unknown> } = {},
  ): ValidationResult {
    const result = emptyResult('delegation_proof');
    const keys = { ...this.issuerPublicKeys, ...(options.issuerPublicKeys || {}) };
    const iss = String(token['iss'] ?? token['issuer'] ?? '').trim();
    if (options.publicKey != null && iss) keys[iss] = options.publicKey;

    const levels = this.validateTokenLevels(token, 0, keys, true);
    for (const err of levels.structuralErrors) result.errors.push(err);
    for (const err of levels.cryptoErrors) result.errors.push(err);
    const structuralOk = levels.structuralErrors.length === 0;
    const cryptographicOk = structuralOk && levels.cryptoOk;
    result.isValid = cryptographicOk;
    attachLevels(
      result,
      level(structuralOk, levels.structuralErrors, structuralOk ? null : 'structural_invalid'),
      level(
        cryptographicOk,
        levels.cryptoErrors,
        cryptographicOk ? null : levels.cryptoReason || 'invalid_signature',
      ),
    );
    if (cryptographicOk) {
      result.metadata['signature_alg'] = SIGNATURE_ALG_EDDSA;
      result.metadata['signing_algorithm'] = CANONICAL_ALGORITHM;
    }
    return result;
  }

  validateInvocation(invocation: Record<string, unknown>): ValidationResult {
    const result = emptyResult('ucan_invocation');

    if (!invocation['interface_cid']) {
      result.isValid = false;
      result.errors.push('Missing interface_cid');
    }
    if (!invocation['input_cid']) {
      result.isValid = false;
      result.errors.push('Missing input_cid');
    }
    if (!invocation['proof_cid']) {
      result.isValid = false;
      result.errors.push('Missing proof_cid for invocation');
    }

    attachLevels(
      result,
      level(result.isValid, result.errors, result.isValid ? null : 'structural_invalid'),
      level(false, ['proof_bundle_not_resolved'], 'proof_bundle_not_resolved'),
    );
    return result;
  }

  private validateTokenSchemaOnly(token: Record<string, unknown>): ValidationResult {
    const result = emptyResult('ucan_token');
    // Support both UCAN shorthand and full-name records.
    const iss = token['iss'] ?? token['issuer'];
    const aud = token['aud'] ?? token['audience'];
    const att = token['att'] ?? token['capabilities'];
    const exp = token['exp'] ?? token['expiry'] ?? token['expiration'];
    if (iss == null || String(iss).trim() === '') {
      result.isValid = false;
      result.errors.push('missing iss');
    }
    if (aud == null || String(aud).trim() === '') {
      result.isValid = false;
      result.errors.push('missing aud');
    }
    if (att == null) {
      result.isValid = false;
      result.errors.push('missing att');
    } else if (!Array.isArray(att)) {
      result.isValid = false;
      result.errors.push('att must be a list');
    }
    if (exp == null) {
      result.isValid = false;
      result.errors.push('missing exp');
    }
    return result;
  }

  private validateTokenLevels(
    token: Record<string, unknown> | string,
    index: number,
    issuerPublicKeys: Record<string, unknown>,
    _forceCrypto = false,
  ): {
    structuralErrors: string[];
    cryptoErrors: string[];
    cryptoReason: string | null;
    hasSig: boolean;
    cryptoOk: boolean;
  } {
    if (typeof token === 'string') {
      return this.validateCompactToken(token, index, issuerPublicKeys);
    }
    if (token == null || typeof token !== 'object' || Array.isArray(token)) {
      return {
        structuralErrors: [`Token at index ${index} must be an object`],
        cryptoErrors: ['structural_failed'],
        cryptoReason: 'structural_failed',
        hasSig: false,
        cryptoOk: false,
      };
    }

    const nested = token['token'] ?? token['ucan'] ?? token['jwt'];
    if (typeof nested === 'string' && nested.split('.').length === 3) {
      return this.validateCompactToken(nested, index, issuerPublicKeys);
    }

    const structuralErrors: string[] = [];
    const cryptoErrors: string[] = [];
    const iss = token['iss'] ?? token['issuer'];
    const aud = token['aud'] ?? token['audience'];
    const att = token['att'] ?? token['capabilities'];
    const exp = token['exp'] ?? token['expiry'] ?? token['expiration'];

    if (iss == null || String(iss).trim() === '') {
      structuralErrors.push(`Token at index ${index} missing required field: iss`);
    }
    if (aud == null || String(aud).trim() === '') {
      structuralErrors.push(`Token at index ${index} missing required field: aud`);
    }
    if (att == null) {
      structuralErrors.push(`Token at index ${index} missing required field: att`);
    } else if (!Array.isArray(att)) {
      structuralErrors.push(`Token at index ${index}: 'att' must be a list`);
    }
    if (exp == null) {
      structuralErrors.push(`Token at index ${index} missing required field: exp`);
    }

    const sigRaw = token['signature'] ?? token['sig'];
    const hasSig = sigRaw != null && String(sigRaw).trim() !== '';
    if (!hasSig) {
      cryptoErrors.push(`Token at index ${index}: missing signature`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'missing_signature',
        hasSig: false,
        cryptoOk: false,
      };
    }

    const header = (token['header'] ?? token['protected']) as Record<string, unknown> | undefined;
    let alg: unknown = header && typeof header === 'object' ? header['alg'] : undefined;
    let kid: unknown = header && typeof header === 'object' ? header['kid'] : undefined;
    alg = alg ?? token['alg'] ?? token['signature_alg'] ?? token['signatureAlg'];
    kid = kid ?? token['kid'];

    if (alg != null) {
      const algText = String(alg).trim();
      if (['none', 'None', 'NONE', ''].includes(algText)) {
        cryptoErrors.push(`Token at index ${index}: algorithm_or_version_downgrade`);
        return {
          structuralErrors,
          cryptoErrors,
          cryptoReason: 'algorithm_or_version_downgrade',
          hasSig: true,
          cryptoOk: false,
        };
      }
      if (
        ![SIGNATURE_ALG_EDDSA, SIGNATURE_ALG_ED25519, 'ed25519', 'Ed25519'].includes(algText)
      ) {
        cryptoErrors.push(`Token at index ${index}: unsupported_signature_alg:${algText}`);
        return {
          structuralErrors,
          cryptoErrors,
          cryptoReason: 'unsupported_signature_alg',
          hasSig: true,
          cryptoOk: false,
        };
      }
    }

    const issuer = String(iss ?? '').trim();
    if ((kid == null || String(kid).trim() === '') && !issuer.startsWith('did:key:')) {
      cryptoErrors.push(`Token at index ${index}: missing_kid`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'missing_kid',
        hasSig: true,
        cryptoOk: false,
      };
    }

    const signature = decodeSignature(sigRaw);
    if (!signature) {
      cryptoErrors.push(`Token at index ${index}: invalid_signature_encoding`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'invalid_signature_encoding',
        hasSig: true,
        cryptoOk: false,
      };
    }

    const publicKey = this.resolvePublicKey(token, issuerPublicKeys, String(kid || ''));
    if (!publicKey) {
      cryptoErrors.push(`Token at index ${index}: verification_key_unavailable`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'verification_key_unavailable',
        hasSig: true,
        cryptoOk: false,
      };
    }

    let message: Uint8Array;
    if (header && typeof header === 'object' && token['payload'] && typeof token['payload'] === 'object') {
      message = compactSigningInput(header, token['payload'] as Record<string, unknown>);
    } else if (header && typeof header === 'object') {
      message = compactSigningInput(header, signingObjectFromToken(token));
    } else {
      message = canonicalSigningBytes(token);
    }

    if (!verifyEd25519(publicKey, message, signature)) {
      cryptoErrors.push(`Token at index ${index}: invalid_signature`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'invalid_signature',
        hasSig: true,
        cryptoOk: false,
      };
    }

    return {
      structuralErrors,
      cryptoErrors,
      cryptoReason: null,
      hasSig: true,
      cryptoOk: true,
    };
  }

  private validateCompactToken(
    token: string,
    index: number,
    issuerPublicKeys: Record<string, unknown>,
  ): {
    structuralErrors: string[];
    cryptoErrors: string[];
    cryptoReason: string | null;
    hasSig: boolean;
    cryptoOk: boolean;
  } {
    const structuralErrors: string[] = [];
    const cryptoErrors: string[] = [];
    const parts = token.split('.');
    if (parts.length !== 3 || !parts[0] || !parts[1] || !parts[2]) {
      structuralErrors.push(`Token at index ${index} missing required field: att`);
      structuralErrors.push(`Token at index ${index} missing required field: exp`);
      cryptoErrors.push(`Token at index ${index}: unsigned_or_malformed_token`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'unsigned_or_malformed_token',
        hasSig: false,
        cryptoOk: false,
      };
    }

    let header: Record<string, unknown>;
    let payload: Record<string, unknown>;
    let signature: Buffer;
    try {
      header = JSON.parse(b64urlDecode(parts[0]).toString('utf8')) as Record<string, unknown>;
      payload = JSON.parse(b64urlDecode(parts[1]).toString('utf8')) as Record<string, unknown>;
      signature = b64urlDecode(parts[2]);
    } catch {
      structuralErrors.push(`Token at index ${index} missing required field: iss`);
      cryptoErrors.push(`Token at index ${index}: malformed_token`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'malformed_token',
        hasSig: true,
        cryptoOk: false,
      };
    }

    for (const field of ['iss', 'aud', 'att', 'exp']) {
      if (!(field in payload)) {
        structuralErrors.push(`Token at index ${index} missing required field: ${field}`);
      }
    }
    if ('att' in payload && !Array.isArray(payload['att'])) {
      structuralErrors.push(`Token at index ${index}: 'att' must be a list`);
    }

    const headerKeys = Object.keys(header).sort().join(',');
    if (headerKeys !== ['alg', 'kid', 'typ', 'v'].sort().join(',')) {
      cryptoErrors.push(`Token at index ${index}: algorithm_or_version_downgrade`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'algorithm_or_version_downgrade',
        hasSig: true,
        cryptoOk: false,
      };
    }
    if (header['alg'] !== SIGNATURE_ALG_EDDSA || header['typ'] !== 'UCAN' || header['v'] !== 1) {
      cryptoErrors.push(`Token at index ${index}: algorithm_or_version_downgrade`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'algorithm_or_version_downgrade',
        hasSig: true,
        cryptoOk: false,
      };
    }
    if (!String(header['kid'] || '').trim()) {
      cryptoErrors.push(`Token at index ${index}: missing_kid`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'missing_kid',
        hasSig: true,
        cryptoOk: false,
      };
    }
    if (signature.length !== 64) {
      cryptoErrors.push(`Token at index ${index}: invalid_signature_encoding`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'invalid_signature_encoding',
        hasSig: true,
        cryptoOk: false,
      };
    }

    try {
      if (b64urlEncode(canonicalizeBytes(header)) !== parts[0]) {
        cryptoErrors.push(`Token at index ${index}: noncanonical_header`);
        return {
          structuralErrors,
          cryptoErrors,
          cryptoReason: 'noncanonical_header',
          hasSig: true,
          cryptoOk: false,
        };
      }
      if (b64urlEncode(canonicalizeBytes(payload)) !== parts[1]) {
        cryptoErrors.push(`Token at index ${index}: noncanonical_payload`);
        return {
          structuralErrors,
          cryptoErrors,
          cryptoReason: 'noncanonical_payload',
          hasSig: true,
          cryptoOk: false,
        };
      }
    } catch {
      cryptoErrors.push(`Token at index ${index}: canonicalization_failed`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'canonicalization_failed',
        hasSig: true,
        cryptoOk: false,
      };
    }

    let publicKey = decodePublicKey(issuerPublicKeys[String(payload['iss'] || '')]);
    if (!publicKey) publicKey = ed25519PublicKeyFromDidKey(String(payload['iss'] || ''));
    if (!publicKey) {
      cryptoErrors.push(`Token at index ${index}: verification_key_unavailable`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'verification_key_unavailable',
        hasSig: true,
        cryptoOk: false,
      };
    }

    const message = Buffer.from(`${parts[0]}.${parts[1]}`, 'ascii');
    if (!verifyEd25519(publicKey, message, signature)) {
      cryptoErrors.push(`Token at index ${index}: invalid_signature`);
      return {
        structuralErrors,
        cryptoErrors,
        cryptoReason: 'invalid_signature',
        hasSig: true,
        cryptoOk: false,
      };
    }

    return {
      structuralErrors,
      cryptoErrors,
      cryptoReason: null,
      hasSig: true,
      cryptoOk: true,
    };
  }

  private resolvePublicKey(
    token: Record<string, unknown>,
    issuerPublicKeys: Record<string, unknown>,
    kid: string,
  ): Buffer | null {
    for (const keyName of ['public_key', 'publicKey', 'issuer_public_key', 'public_key_b64']) {
      if (keyName in token) {
        const raw = decodePublicKey(token[keyName]);
        if (raw) return raw;
      }
    }
    const issuer = String(token['iss'] ?? token['issuer'] ?? '').trim();
    if (issuer && issuer in issuerPublicKeys) {
      const entry = issuerPublicKeys[issuer];
      if (
        entry &&
        typeof entry === 'object' &&
        !Array.isArray(entry) &&
        kid &&
        kid in (entry as Record<string, unknown>) &&
        !['public_key', 'public_key_b64', 'alg', 'algorithm', 'key'].some(
          (k) => k in (entry as Record<string, unknown>),
        )
      ) {
        const raw = decodePublicKey((entry as Record<string, unknown>)[kid]);
        if (raw) return raw;
      }
      const raw = decodePublicKey(entry);
      if (raw) return raw;
    }
    if (issuer) {
      const raw = ed25519PublicKeyFromDidKey(issuer);
      if (raw) return raw;
    }
    return null;
  }
}

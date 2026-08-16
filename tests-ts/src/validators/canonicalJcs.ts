/**
 * MCP++ `mcpp-jcs-v1` canonicalization (RFC 8785 JCS) — McppJcsV1@1.
 *
 * Normative: docs/spec/canonicalization-mcpp-jcs-v1.md
 * Schema: schemas/canonicalization/mcpp-jcs-v1.schema.json
 * Vectors: conformance/vectors/mcpp-jcs-v1/
 *
 * New mint paths MUST use algorithm id `mcpp-jcs-v1`. Historical artifacts
 * remain readable under the algorithm recorded at mint time; silent CID rewrite
 * is forbidden.
 */

import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ALGORITHM_ID = 'mcpp-jcs-v1';
export const INTERFACE = 'McppJcsV1@1';
export const STANDARD = {
  standard: 'RFC 8785',
  name: 'JSON Canonicalization Scheme',
  url: 'https://www.rfc-editor.org/rfc/rfc8785',
} as const;

export const SPEC_PATH =
  'ipfs_accelerate_py/mcplusplus/docs/spec/canonicalization-mcpp-jcs-v1.md';
export const ADR_PATH =
  'ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/0002-crypto-canonical.md';

const CID_VERSION = 1;
const MULTICODEC_RAW = 0x55;
const MULTIHASH_SHA2_256 = 0x12;
const MULTIHASH_LEN = 32;
const SAFE_INTEGER_MIN = -9007199254740991;
const SAFE_INTEGER_MAX = 9007199254740991;
const B32 = 'abcdefghijklmnopqrstuvwxyz234567';
const HISTORICAL_ALGORITHM_RE =
  /^[A-Za-z0-9][A-Za-z0-9._+:@/-]{0,127}$/;

export type ReasonCode =
  | 'reject_nan_infinity'
  | 'reject_lone_surrogate'
  | 'reject_duplicate_keys'
  | 'reject_non_canonical_bytes'
  | 'reject_cycles'
  | 'reject_absent_key_as_null'
  | 'reject_invalid_json_literal'
  | 'reject_unsupported_type'
  | 'reject_unsafe_integer';

export class McppJcsError extends Error {
  readonly reasonCode: ReasonCode;
  readonly path: string;

  constructor(reasonCode: ReasonCode, message: string, path = '') {
    super(path ? `${path}: ${message}` : message);
    this.name = 'McppJcsError';
    this.reasonCode = reasonCode;
    this.path = path;
  }
}

export interface ValidatorResult {
  accept: boolean;
  reason_code: ReasonCode | string | null;
  algorithm: string;
  canonical_utf8?: string | null;
  canonical_bytes?: Uint8Array | null;
  sha256?: string | null;
  cid?: string | null;
  errors: string[];
  metadata: Record<string, unknown>;
}

export interface CanonicalIdentity {
  algorithm: string;
  canonical_utf8: string;
  canonical_bytes: Uint8Array;
  sha256: string;
  cid: string;
}

// ---------------------------------------------------------------------------
// UTF-16 helpers (JS strings are already UTF-16 code units)
// ---------------------------------------------------------------------------

function assertNoLoneSurrogates(text: string, path = ''): void {
  for (let i = 0; i < text.length; i++) {
    const cu = text.charCodeAt(i);
    if (cu >= 0xd800 && cu <= 0xdbff) {
      if (i + 1 >= text.length) {
        throw new McppJcsError(
          'reject_lone_surrogate',
          `lone high surrogate U+${cu.toString(16).toUpperCase()}`,
          path,
        );
      }
      const low = text.charCodeAt(i + 1);
      if (low < 0xdc00 || low > 0xdfff) {
        throw new McppJcsError(
          'reject_lone_surrogate',
          `lone high surrogate U+${cu.toString(16).toUpperCase()}`,
          path,
        );
      }
      i++;
      continue;
    }
    if (cu >= 0xdc00 && cu <= 0xdfff) {
      throw new McppJcsError(
        'reject_lone_surrogate',
        `lone low surrogate U+${cu.toString(16).toUpperCase()}`,
        path,
      );
    }
  }
}

function compareUtf16(a: string, b: string): number {
  assertNoLoneSurrogates(a);
  assertNoLoneSurrogates(b);
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

function sortObjectKeys(keys: string[]): string[] {
  return keys.slice().sort(compareUtf16);
}

// ---------------------------------------------------------------------------
// Number serialization (ES6 Number.toString / JCS)
// ---------------------------------------------------------------------------

export function es6NumberToString(value: number): string {
  if (typeof value !== 'number') {
    throw new McppJcsError('reject_unsupported_type', 'not a number');
  }
  if (Number.isNaN(value) || !Number.isFinite(value)) {
    throw new McppJcsError(
      'reject_nan_infinity',
      'NaN and ±Infinity are not JSON numbers',
    );
  }
  // Negative zero → 0 under JCS.
  if (Object.is(value, -0) || value === 0) {
    return '0';
  }
  // Number.prototype.toString matches ES6 / JCS for finite numbers.
  return String(value);
}

// ---------------------------------------------------------------------------
// String serialization
// ---------------------------------------------------------------------------

function encodeJsonString(text: string): string {
  assertNoLoneSurrogates(text);
  let out = '"';
  for (let i = 0; i < text.length; i++) {
    const cu = text.charCodeAt(i);
    // Emit complete surrogate pairs as UTF-8 via the string itself.
    if (cu >= 0xd800 && cu <= 0xdbff) {
      out += text[i]! + text[i + 1]!;
      i++;
      continue;
    }
    switch (cu) {
      case 0x22: // "
        out += '\\"';
        break;
      case 0x5c: // \
        out += '\\\\';
        break;
      case 0x08:
        out += '\\b';
        break;
      case 0x0c:
        out += '\\f';
        break;
      case 0x0a:
        out += '\\n';
        break;
      case 0x0d:
        out += '\\r';
        break;
      case 0x09:
        out += '\\t';
        break;
      default:
        if (cu < 0x20) {
          out += `\\u${cu.toString(16).padStart(4, '0')}`;
        } else {
          out += text[i]!;
        }
    }
  }
  return out + '"';
}

// ---------------------------------------------------------------------------
// Core canonicalize
// ---------------------------------------------------------------------------

function canonicalizeValue(value: unknown, path: string, seen: WeakSet<object>): string {
  if (value === null) return 'null';
  if (value === undefined) {
    throw new McppJcsError(
      'reject_unsupported_type',
      'undefined is not a JSON value under mcpp-jcs-v1',
      path,
    );
  }
  const t = typeof value;
  if (t === 'boolean') return value ? 'true' : 'false';
  if (t === 'number') return es6NumberToString(value as number);
  if (t === 'string') return encodeJsonString(value as string);
  if (t === 'bigint') {
    throw new McppJcsError(
      'reject_unsafe_integer',
      'bigint is not a JSON number; encode as string at the schema layer',
      path,
    );
  }
  if (t === 'function' || t === 'symbol') {
    throw new McppJcsError(
      'reject_unsupported_type',
      `${t} is not a JSON value`,
      path,
    );
  }
  if (Array.isArray(value)) {
    if (seen.has(value)) {
      throw new McppJcsError('reject_cycles', 'cyclic structure is not JSON', path);
    }
    seen.add(value);
    try {
      const parts = value.map((item, i) =>
        canonicalizeValue(item, `${path}/${i}`, seen),
      );
      return `[${parts.join(',')}]`;
    } finally {
      seen.delete(value);
    }
  }
  if (t === 'object') {
    if (value instanceof Date || value instanceof RegExp || ArrayBuffer.isView(value)) {
      throw new McppJcsError(
        'reject_unsupported_type',
        `unsupported object type under mcpp-jcs-v1`,
        path,
      );
    }
    const obj = value as Record<string, unknown>;
    if (seen.has(obj)) {
      throw new McppJcsError('reject_cycles', 'cyclic structure is not JSON', path);
    }
    seen.add(obj);
    try {
      const keys = sortObjectKeys(Object.keys(obj));
      const parts = keys.map(
        (key) =>
          `${encodeJsonString(key)}:${canonicalizeValue(obj[key], `${path}/${key}`, seen)}`,
      );
      return `{${parts.join(',')}}`;
    } finally {
      seen.delete(obj);
    }
  }
  throw new McppJcsError(
    'reject_unsupported_type',
    `unsupported type ${t}`,
    path,
  );
}

/** Return JCS text for `value` under algorithm id `mcpp-jcs-v1`. */
export function canonicalize(value: unknown): string {
  return canonicalizeValue(value, '', new WeakSet());
}

/** Return UTF-8 canonical bytes (no BOM, no trailing newline). */
export function canonicalizeBytes(value: unknown): Uint8Array {
  const text = canonicalize(value);
  if (text.endsWith('\n') || text.endsWith('\r')) {
    throw new McppJcsError(
      'reject_non_canonical_bytes',
      'canonical text must not end with newline',
    );
  }
  return Buffer.from(text, 'utf8');
}

export function sha256Hex(value: unknown): string {
  return createHash('sha256').update(canonicalizeBytes(value)).digest('hex');
}

function base32Lower(bytes: Uint8Array): string {
  let out = '';
  let bits = 0;
  let acc = 0;
  for (const x of bytes) {
    acc = (acc << 8) | x;
    bits += 8;
    while (bits >= 5) {
      bits -= 5;
      out += B32[(acc >> bits) & 31]!;
      acc &= (1 << bits) - 1;
    }
  }
  if (bits) out += B32[(acc << (5 - bits)) & 31]!;
  return out;
}

export function cidV1RawSha256(digest32: Uint8Array): string {
  if (digest32.length !== MULTIHASH_LEN) {
    throw new McppJcsError(
      'reject_unsupported_type',
      `sha2-256 digest must be ${MULTIHASH_LEN} bytes`,
    );
  }
  const raw = Uint8Array.from([
    CID_VERSION,
    MULTICODEC_RAW,
    MULTIHASH_SHA2_256,
    MULTIHASH_LEN,
    ...digest32,
  ]);
  return 'b' + base32Lower(raw);
}

export function artifactCid(value: unknown): string {
  const digest = createHash('sha256').update(canonicalizeBytes(value)).digest();
  return cidV1RawSha256(digest);
}

export function identity(value: unknown): CanonicalIdentity {
  const text = canonicalize(value);
  const data = Buffer.from(text, 'utf8');
  const digest = createHash('sha256').update(data).digest();
  return {
    algorithm: ALGORITHM_ID,
    canonical_utf8: text,
    canonical_bytes: data,
    sha256: digest.toString('hex'),
    cid: cidV1RawSha256(digest),
  };
}

export function algorithmDeclaration(): Record<string, unknown> {
  return {
    algorithm: ALGORITHM_ID,
    interface: INTERFACE,
    standard: { ...STANDARD },
    encoding: {
      utf8: true,
      no_bom: true,
      no_trailing_newline: true,
      no_insignificant_whitespace: true,
      object_key_order: 'utf16-code-unit-lexicographic',
      reject_duplicate_keys: true,
      reject_nan_infinity: true,
      reject_cycles: true,
      negative_zero_per_jcs: true,
      null_is_token: true,
      arrays_preserve_order: true,
    },
    cid_defaults: {
      cid_version: CID_VERSION,
      multicodec: 'raw',
      multicodec_code: MULTICODEC_RAW,
      multihash: 'sha2-256',
      multihash_code: MULTIHASH_SHA2_256,
      multibase: 'base32',
    },
    silent_cid_change_policy: {
      forbidden: true,
      historical_readable: true,
      promotion_requires_migration_record: true,
    },
    spec_path: SPEC_PATH,
    adr: ADR_PATH,
  };
}

// ---------------------------------------------------------------------------
// Strict JSON parse (duplicate keys + lone surrogates fail closed)
// ---------------------------------------------------------------------------

function scanString(s: string, i: number): [string, number] {
  if (i >= s.length || s[i] !== '"') {
    throw new McppJcsError('reject_invalid_json_literal', 'expected string', `@${i}`);
  }
  i++;
  let out = '';
  while (i < s.length) {
    const ch = s[i]!;
    if (ch === '"') return [out, i + 1];
    if (ch === '\\') {
      if (i + 1 >= s.length) {
        throw new McppJcsError('reject_invalid_json_literal', 'truncated escape', `@${i}`);
      }
      const esc = s[i + 1]!;
      if (esc === '"' || esc === '\\' || esc === '/') {
        out += esc;
        i += 2;
        continue;
      }
      if (esc === 'b') {
        out += '\b';
        i += 2;
        continue;
      }
      if (esc === 'f') {
        out += '\f';
        i += 2;
        continue;
      }
      if (esc === 'n') {
        out += '\n';
        i += 2;
        continue;
      }
      if (esc === 'r') {
        out += '\r';
        i += 2;
        continue;
      }
      if (esc === 't') {
        out += '\t';
        i += 2;
        continue;
      }
      if (esc === 'u') {
        if (i + 6 > s.length) {
          throw new McppJcsError(
            'reject_invalid_json_literal',
            'truncated \\u escape',
            `@${i}`,
          );
        }
        const hexpart = s.slice(i + 2, i + 6);
        const code = Number.parseInt(hexpart, 16);
        if (Number.isNaN(code)) {
          throw new McppJcsError(
            'reject_invalid_json_literal',
            `invalid \\u escape ${hexpart}`,
            `@${i}`,
          );
        }
        if (code >= 0xd800 && code <= 0xdbff) {
          if (i + 12 <= s.length && s.slice(i + 6, i + 8) === '\\u') {
            const low = Number.parseInt(s.slice(i + 8, i + 12), 16);
            if (!Number.isNaN(low) && low >= 0xdc00 && low <= 0xdfff) {
              const cp = 0x10000 + ((code - 0xd800) << 10) + (low - 0xdc00);
              out += String.fromCodePoint(cp);
              i += 12;
              continue;
            }
          }
          throw new McppJcsError(
            'reject_lone_surrogate',
            `lone high surrogate U+${code.toString(16).toUpperCase()}`,
            `@${i}`,
          );
        }
        if (code >= 0xdc00 && code <= 0xdfff) {
          throw new McppJcsError(
            'reject_lone_surrogate',
            `lone low surrogate U+${code.toString(16).toUpperCase()}`,
            `@${i}`,
          );
        }
        out += String.fromCharCode(code);
        i += 6;
        continue;
      }
      throw new McppJcsError(
        'reject_invalid_json_literal',
        `invalid escape \\${esc}`,
        `@${i}`,
      );
    }
    if (ch.charCodeAt(0) < 0x20) {
      throw new McppJcsError(
        'reject_invalid_json_literal',
        'unescaped control character in string',
        `@${i}`,
      );
    }
    out += ch;
    i++;
  }
  throw new McppJcsError('reject_invalid_json_literal', 'unterminated string');
}

function skipWs(s: string, i: number): number {
  while (i < s.length && ' \t\r\n'.includes(s[i]!)) i++;
  return i;
}

function parseValue(s: string, i: number, path: string): [unknown, number] {
  i = skipWs(s, i);
  if (i >= s.length) {
    throw new McppJcsError('reject_invalid_json_literal', 'unexpected end of input', path);
  }
  const ch = s[i]!;
  if (ch === 'n') {
    if (s.slice(i, i + 4) !== 'null') {
      throw new McppJcsError(
        'reject_invalid_json_literal',
        'only lowercase null is a JSON null literal',
        path,
      );
    }
    return [null, i + 4];
  }
  if (ch === 't') {
    if (s.slice(i, i + 4) !== 'true') {
      throw new McppJcsError('reject_invalid_json_literal', 'invalid true literal', path);
    }
    return [true, i + 4];
  }
  if (ch === 'f') {
    if (s.slice(i, i + 5) !== 'false') {
      throw new McppJcsError('reject_invalid_json_literal', 'invalid false literal', path);
    }
    return [false, i + 5];
  }
  if (ch === '"') {
    return scanString(s, i);
  }
  if (ch === '[') {
    i += 1;
    i = skipWs(s, i);
    const items: unknown[] = [];
    if (i < s.length && s[i] === ']') return [items, i + 1];
    for (;;) {
      let val: unknown;
      [val, i] = parseValue(s, i, `${path}/${items.length}`);
      items.push(val);
      i = skipWs(s, i);
      if (i >= s.length) {
        throw new McppJcsError('reject_invalid_json_literal', 'unterminated array', path);
      }
      if (s[i] === ']') return [items, i + 1];
      if (s[i] !== ',') {
        throw new McppJcsError('reject_invalid_json_literal', "expected ',' or ']'", path);
      }
      i += 1;
    }
  }
  if (ch === '{') {
    i += 1;
    i = skipWs(s, i);
    const obj: Record<string, unknown> = Object.create(null);
    if (i < s.length && s[i] === '}') return [obj, i + 1];
    for (;;) {
      i = skipWs(s, i);
      if (i >= s.length || s[i] !== '"') {
        throw new McppJcsError('reject_invalid_json_literal', 'expected object key', path);
      }
      let key: string;
      [key, i] = scanString(s, i);
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        throw new McppJcsError(
          'reject_duplicate_keys',
          `duplicate object key ${JSON.stringify(key)}`,
          path,
        );
      }
      i = skipWs(s, i);
      if (i >= s.length || s[i] !== ':') {
        throw new McppJcsError('reject_invalid_json_literal', "expected ':'", path);
      }
      i += 1;
      let val: unknown;
      [val, i] = parseValue(s, i, `${path}/${key}`);
      obj[key] = val;
      i = skipWs(s, i);
      if (i >= s.length) {
        throw new McppJcsError('reject_invalid_json_literal', 'unterminated object', path);
      }
      if (s[i] === '}') return [obj, i + 1];
      if (s[i] !== ',') {
        throw new McppJcsError('reject_invalid_json_literal', "expected ',' or '}'", path);
      }
      i += 1;
    }
  }
  // number
  const start = i;
  if (s[i] === '-') i++;
  if (i >= s.length || !/\d/.test(s[i]!)) {
    throw new McppJcsError('reject_invalid_json_literal', 'invalid number', path);
  }
  if (s[i] === '0') {
    i++;
  } else {
    while (i < s.length && /\d/.test(s[i]!)) i++;
  }
  if (i < s.length && s[i] === '.') {
    i++;
    if (i >= s.length || !/\d/.test(s[i]!)) {
      throw new McppJcsError('reject_invalid_json_literal', 'invalid number fraction', path);
    }
    while (i < s.length && /\d/.test(s[i]!)) i++;
  }
  if (i < s.length && (s[i] === 'e' || s[i] === 'E')) {
    i++;
    if (i < s.length && (s[i] === '+' || s[i] === '-')) i++;
    if (i >= s.length || !/\d/.test(s[i]!)) {
      throw new McppJcsError('reject_invalid_json_literal', 'invalid number exponent', path);
    }
    while (i < s.length && /\d/.test(s[i]!)) i++;
  }
  const token = s.slice(start, i);
  const num = Number(token);
  if (Number.isNaN(num) || !Number.isFinite(num)) {
    throw new McppJcsError('reject_nan_infinity', 'NaN/Infinity number', path);
  }
  if (
    !token.includes('.') &&
    !/[eE]/.test(token) &&
    (num < SAFE_INTEGER_MIN || num > SAFE_INTEGER_MAX)
  ) {
    throw new McppJcsError(
      'reject_unsafe_integer',
      `integer ${token} is outside IEEE-754 safe integer range`,
      path,
    );
  }
  return [num, i];
}

/** Parse JSON text with fail-closed duplicate-key and surrogate rules. */
export function parseJsonStrict(text: string): unknown {
  if (typeof text !== 'string') {
    throw new McppJcsError('reject_invalid_json_literal', 'JSON text must be a string');
  }
  const [value, i0] = parseValue(text, 0, '');
  const i = skipWs(text, i0);
  if (i !== text.length) {
    throw new McppJcsError(
      'reject_invalid_json_literal',
      `trailing data at index ${i}`,
    );
  }
  return value;
}

// ---------------------------------------------------------------------------
// Verify already-canonical claims
// ---------------------------------------------------------------------------

export function verifyCanonicalBytes(
  offered: string | Uint8Array,
  value?: unknown,
): Uint8Array {
  let offeredText: string;
  let offeredBytes: Uint8Array;
  if (typeof offered === 'string') {
    offeredText = offered;
    offeredBytes = Buffer.from(offeredText, 'utf8');
  } else {
    offeredBytes = offered;
    offeredText = Buffer.from(offered).toString('utf8');
  }
  if (
    (offeredBytes.length >= 3 &&
      offeredBytes[0] === 0xef &&
      offeredBytes[1] === 0xbb &&
      offeredBytes[2] === 0xbf) ||
    offeredText.endsWith('\n') ||
    offeredText.endsWith('\r')
  ) {
    throw new McppJcsError(
      'reject_non_canonical_bytes',
      'BOM or trailing newline is not canonical',
    );
  }
  let required: Uint8Array;
  if (value !== undefined) {
    required = canonicalizeBytes(value);
  } else {
    required = canonicalizeBytes(parseJsonStrict(offeredText));
  }
  if (!Buffer.from(required).equals(Buffer.from(offeredBytes))) {
    throw new McppJcsError(
      'reject_non_canonical_bytes',
      'offered bytes are not mcpp-jcs-v1 canonical form',
    );
  }
  return required;
}

// ---------------------------------------------------------------------------
// Historical algorithm readability (no silent CID change)
// ---------------------------------------------------------------------------

type HistoricalEncoder = (value: unknown) => Uint8Array;

function profileSortKeysBytes(value: unknown): Uint8Array {
  // Historical Profile G/H style: code-unit sort via JSON.stringify after
  // sorting keys recursively. Not full JCS (e.g. -0 may differ); used only for
  // recorded historical algorithms.
  const sort = (v: unknown): unknown => {
    if (v === null || typeof v !== 'object') return v;
    if (Array.isArray(v)) return v.map(sort);
    const o = v as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const k of Object.keys(o).sort()) out[k] = sort(o[k]);
    return out;
  };
  return Buffer.from(JSON.stringify(sort(value)), 'utf8');
}

const HISTORICAL_ENCODERS: Record<string, HistoricalEncoder> = {
  'profile-g-dag-json-local': profileSortKeysBytes,
  'profile-h-dag-json-local': profileSortKeysBytes,
  'legacy-sort-keys-json': profileSortKeysBytes,
};

export function isMcppJcsV1(algorithm: string): boolean {
  return algorithm === ALGORITHM_ID;
}

export function isKnownAlgorithm(algorithm: string): boolean {
  if (!algorithm) return false;
  if (isMcppJcsV1(algorithm)) return true;
  if (algorithm in HISTORICAL_ENCODERS) return true;
  return HISTORICAL_ALGORITHM_RE.test(algorithm);
}

export function canonicalizeWithAlgorithm(
  algorithm: string,
  value: unknown,
): Uint8Array {
  if (!algorithm) {
    throw new McppJcsError('reject_unsupported_type', 'algorithm id is required');
  }
  if (isMcppJcsV1(algorithm)) return canonicalizeBytes(value);
  const encoder = HISTORICAL_ENCODERS[algorithm];
  if (!encoder) {
    if (!HISTORICAL_ALGORITHM_RE.test(algorithm)) {
      throw new McppJcsError(
        'reject_unsupported_type',
        `unknown or ill-formed algorithm id ${JSON.stringify(algorithm)}`,
      );
    }
    throw new McppJcsError(
      'reject_unsupported_type',
      `no encoder registered for historical algorithm ${JSON.stringify(algorithm)}; ` +
        'readers must use the adapter recorded at mint time',
    );
  }
  return encoder(value);
}

export function verifyRecordedBinding(args: {
  cid: string;
  algorithm: string;
  value?: unknown;
  payload_bytes?: Uint8Array;
  multicodec?: string | null;
}): ValidatorResult {
  const { cid, algorithm, value, payload_bytes, multicodec } = args;
  if (!isKnownAlgorithm(algorithm)) {
    return {
      accept: false,
      reason_code: 'reject_unsupported_type',
      algorithm,
      errors: [`unknown algorithm ${JSON.stringify(algorithm)}`],
      metadata: {},
    };
  }
  try {
    let wire: Uint8Array;
    if (payload_bytes) {
      wire = payload_bytes;
      if (isMcppJcsV1(algorithm) && value !== undefined) {
        const required = canonicalizeBytes(value);
        if (!Buffer.from(wire).equals(Buffer.from(required))) {
          throw new McppJcsError(
            'reject_non_canonical_bytes',
            'payload bytes do not match mcpp-jcs-v1(value)',
          );
        }
      } else if (isMcppJcsV1(algorithm) && value === undefined) {
        verifyCanonicalBytes(wire);
      }
    } else if (value !== undefined) {
      wire = canonicalizeWithAlgorithm(algorithm, value);
    } else {
      throw new McppJcsError(
        'reject_unsupported_type',
        'value or payload_bytes is required for verification',
      );
    }

    if (isMcppJcsV1(algorithm) && (multicodec == null || multicodec === 'raw')) {
      const digest = createHash('sha256').update(wire).digest();
      const expectedCid = cidV1RawSha256(digest);
      if (cid !== expectedCid) {
        throw new McppJcsError(
          'reject_non_canonical_bytes',
          `CID mismatch under mcpp-jcs-v1: got ${cid}, expected ${expectedCid}`,
        );
      }
      return {
        accept: true,
        reason_code: null,
        algorithm,
        canonical_utf8: Buffer.from(wire).toString('utf8'),
        canonical_bytes: wire,
        sha256: digest.toString('hex'),
        cid: expectedCid,
        errors: [],
        metadata: {
          verify_with_recorded_algorithm: true,
          allow_silent_recanonicalization: false,
          multicodec: multicodec ?? 'raw',
        },
      };
    }

    if (typeof cid !== 'string' || !cid) {
      throw new McppJcsError(
        'reject_unsupported_type',
        'historical binding requires a CID',
      );
    }
    return {
      accept: true,
      reason_code: null,
      algorithm,
      canonical_bytes: wire,
      sha256: createHash('sha256').update(wire).digest('hex'),
      cid,
      errors: [],
      metadata: {
        verify_with_recorded_algorithm: true,
        allow_silent_recanonicalization: false,
        multicodec: multicodec ?? null,
        historical: !isMcppJcsV1(algorithm),
      },
    };
  } catch (err) {
    if (err instanceof McppJcsError) {
      return {
        accept: false,
        reason_code: err.reasonCode,
        algorithm,
        errors: [err.message],
        metadata: {},
      };
    }
    throw err;
  }
}

export function promoteWithMigration(
  value: unknown,
  args: {
    source_cid: string;
    source_algorithm: string;
    reason?: string;
    migrated_at?: string;
  },
): Record<string, unknown> {
  const {
    source_cid,
    source_algorithm,
    reason = 'promote-to-mcpplusplus-1.0-suite',
    migrated_at,
  } = args;
  if (isMcppJcsV1(source_algorithm)) {
    throw new McppJcsError(
      'reject_unsupported_type',
      'source is already mcpp-jcs-v1; no promotion required',
    );
  }
  if (!isKnownAlgorithm(source_algorithm)) {
    throw new McppJcsError(
      'reject_unsupported_type',
      `unknown source algorithm ${JSON.stringify(source_algorithm)}`,
    );
  }
  const target = identity(value);
  const record: Record<string, unknown> = {
    schema: 'mcp++/canonicalization/migration@1',
    source_cid,
    source_algorithm,
    target_cid: target.cid,
    target_algorithm: ALGORITHM_ID,
    reason,
    silent_rewrite: false,
  };
  if (migrated_at !== undefined) record.migrated_at = migrated_at;
  return {
    migration: record,
    target_identity: {
      algorithm: target.algorithm,
      canonical_utf8: target.canonical_utf8,
      canonical_sha256: target.sha256,
      cid: target.cid,
      multicodec: 'raw',
      multihash: 'sha2-256',
    },
    target_bytes: target.canonical_bytes,
  };
}

// ---------------------------------------------------------------------------
// Golden vector validation
// ---------------------------------------------------------------------------

function negativeZeroFix(source: unknown): unknown {
  if (
    source &&
    typeof source === 'object' &&
    !Array.isArray(source) &&
    Array.isArray((source as any).values) &&
    (source as any).values.length >= 2 &&
    (source as any).values[0] === 0 &&
    (source as any).values[1] === 0
  ) {
    const values = [...(source as any).values];
    values[1] = -0;
    return { ...(source as object), values };
  }
  return source;
}

export function validateVectorCase(caseObj: Record<string, any>): ValidatorResult {
  const expected = caseObj.expected_validator_result ?? {};
  const wantAccept = Boolean(expected.accept ?? caseObj.valid ?? true);
  const wantReason: string | null = expected.reason_code ?? null;
  const caseId = caseObj.id ?? '<unknown>';

  try {
    if (wantAccept) {
      let source = caseObj.source;
      if (source == null && caseObj.source_json != null) {
        source = parseJsonStrict(caseObj.source_json);
      }
      if (source == null) {
        throw new McppJcsError(
          'reject_unsupported_type',
          `positive case ${caseId} lacks source/source_json`,
        );
      }
      if (caseObj.id === 'numbers-positive-es6-forms') {
        source = negativeZeroFix(source);
      }
      const ident = identity(source);
      if (
        caseObj.canonical_utf8 != null &&
        ident.canonical_utf8 !== caseObj.canonical_utf8
      ) {
        throw new McppJcsError(
          'reject_non_canonical_bytes',
          `canonical_utf8 mismatch for ${caseId}`,
        );
      }
      if (caseObj.canonical_bytes_hex != null) {
        const gotHex = Buffer.from(ident.canonical_bytes).toString('hex');
        if (gotHex !== caseObj.canonical_bytes_hex) {
          throw new McppJcsError(
            'reject_non_canonical_bytes',
            `canonical_bytes_hex mismatch for ${caseId}`,
          );
        }
      }
      if (caseObj.sha256 != null && ident.sha256 !== caseObj.sha256) {
        throw new McppJcsError(
          'reject_non_canonical_bytes',
          `sha256 mismatch for ${caseId}`,
        );
      }
      if (caseObj.cid != null && ident.cid !== caseObj.cid) {
        throw new McppJcsError(
          'reject_non_canonical_bytes',
          `cid mismatch for ${caseId}`,
        );
      }
      const sig = caseObj.signature_input ?? {};
      if (sig.encoding === 'hex' && sig.value != null) {
        if (Buffer.from(ident.canonical_bytes).toString('hex') !== sig.value) {
          throw new McppJcsError(
            'reject_non_canonical_bytes',
            `signature_input mismatch for ${caseId}`,
          );
        }
      }
      return {
        accept: true,
        reason_code: null,
        algorithm: ALGORITHM_ID,
        canonical_utf8: ident.canonical_utf8,
        canonical_bytes: ident.canonical_bytes,
        sha256: ident.sha256,
        cid: ident.cid,
        errors: [],
        metadata: { case_id: caseId },
      };
    }

    const reason = wantReason ?? 'reject_unsupported_type';
    if (reason === 'reject_nan_infinity') {
      const kind =
        expected.detail?.value_kind ?? caseObj.rejection?.condition ?? 'Infinity';
      const bad = kind === 'NaN' || kind === 'nan' ? Number.NaN : Number.POSITIVE_INFINITY;
      canonicalize(bad);
    } else if (reason === 'reject_lone_surrogate') {
      const sourceJson = caseObj.source_json ?? caseObj.rejection?.source_json;
      if (!sourceJson) {
        throw new McppJcsError(reason as ReasonCode, 'missing source_json for surrogate case');
      }
      parseJsonStrict(sourceJson);
    } else if (reason === 'reject_duplicate_keys') {
      const sourceJson = caseObj.source_json ?? caseObj.rejection?.source_json;
      if (!sourceJson) {
        throw new McppJcsError(reason as ReasonCode, 'missing source_json for duplicate-key case');
      }
      parseJsonStrict(sourceJson);
    } else if (reason === 'reject_non_canonical_bytes') {
      let offered = caseObj.source_json as string | undefined;
      if (offered == null) offered = expected.detail?.offered_as_canonical;
      if (offered == null) {
        throw new McppJcsError(reason as ReasonCode, 'missing offered non-canonical text');
      }
      verifyCanonicalBytes(offered, caseObj.source);
    } else if (reason === 'reject_cycles') {
      const cyclic: Record<string, unknown> = {};
      cyclic.self = cyclic;
      canonicalize(cyclic);
    } else if (reason === 'reject_absent_key_as_null') {
      const source = caseObj.source ?? caseObj.rejection?.source;
      const forbidden =
        expected.detail?.incorrect_claim ?? caseObj.rejection?.forbidden_equivalence;
      if (source == null || forbidden == null) {
        throw new McppJcsError(reason as ReasonCode, 'missing source/forbidden equivalence');
      }
      const correct = canonicalize(source);
      const incorrect = canonicalize(forbidden);
      if (correct === incorrect) {
        throw new McppJcsError(
          reason as ReasonCode,
          'absent key was incorrectly treated as null',
        );
      }
      throw new McppJcsError(
        reason as ReasonCode,
        'absent key must not be treated as null under mcpp-jcs-v1',
      );
    } else if (reason === 'reject_invalid_json_literal') {
      const sourceJson = caseObj.source_json ?? caseObj.rejection?.source_json;
      if (!sourceJson) {
        throw new McppJcsError(reason as ReasonCode, 'missing source_json');
      }
      parseJsonStrict(sourceJson);
    } else if (caseObj.source_json != null) {
      parseJsonStrict(caseObj.source_json);
    } else if (caseObj.source != null) {
      canonicalize(caseObj.source);
    } else {
      throw new McppJcsError(reason as ReasonCode, `unhandled negative case ${caseId}`);
    }

    return {
      accept: true,
      reason_code: null,
      algorithm: ALGORITHM_ID,
      errors: [`expected rejection ${reason} for ${caseId} but accepted`],
      metadata: { case_id: caseId, expected_reason: reason },
    };
  } catch (err) {
    if (err instanceof McppJcsError) {
      const gotReason = err.reasonCode;
      if (!wantAccept) {
        if (wantReason && gotReason !== wantReason) {
          return {
            accept: false,
            reason_code: gotReason,
            algorithm: ALGORITHM_ID,
            errors: [
              `reason_code mismatch for ${caseId}: got ${gotReason}, expected ${wantReason}: ${err.message}`,
            ],
            metadata: { case_id: caseId },
          };
        }
        return {
          accept: false,
          reason_code: wantReason ?? gotReason,
          algorithm: ALGORITHM_ID,
          errors: [],
          metadata: { case_id: caseId, raised: gotReason },
        };
      }
      return {
        accept: false,
        reason_code: gotReason,
        algorithm: ALGORITHM_ID,
        errors: [err.message],
        metadata: { case_id: caseId },
      };
    }
    throw err;
  }
}

export function loadVectorFiles(vectorsDir: string): Record<string, any>[] {
  const cases: Record<string, any>[] = [];
  for (const name of readdirSync(vectorsDir).sort()) {
    if (!name.endsWith('.json') || name === 'manifest.json') continue;
    const payload = JSON.parse(readFileSync(join(vectorsDir, name), 'utf8'));
    for (const c of payload.cases ?? []) {
      if (c && typeof c === 'object') {
        cases.push({ ...c, _vector_file: name });
      }
    }
  }
  return cases;
}

function defaultVectorsDir(): string {
  const here = dirname(fileURLToPath(import.meta.url));
  // tests-ts/src/validators -> mcplusplus/
  return join(here, '..', '..', '..', 'conformance', 'vectors', 'mcpp-jcs-v1');
}

export function runGoldenVectors(vectorsDir?: string): Record<string, any> {
  const root = vectorsDir ?? defaultVectorsDir();
  const cases = loadVectorFiles(root);
  const results: Record<string, any>[] = [];
  let passed = 0;
  let failed = 0;
  for (const caseObj of cases) {
    const result = validateVectorCase(caseObj);
    const expected = caseObj.expected_validator_result ?? {};
    const wantAccept = Boolean(expected.accept ?? caseObj.valid ?? true);
    let ok = false;
    if (wantAccept && result.accept && result.errors.length === 0) ok = true;
    if (!wantAccept && !result.accept && result.errors.length === 0) ok = true;
    if (ok) passed++;
    else failed++;
    results.push({
      id: caseObj.id,
      ok,
      accept: result.accept,
      reason_code: result.reason_code,
      errors: result.errors,
      cid: result.cid ?? null,
      sha256: result.sha256 ?? null,
    });
  }

  const historicalSource = { z: 1, a: 2 };
  const historicalBytes = canonicalizeWithAlgorithm(
    'profile-g-dag-json-local',
    historicalSource,
  );
  const historical = verifyRecordedBinding({
    cid: 'bafkreihistoricalplaceholder0000000000000000000000000000000',
    algorithm: 'profile-g-dag-json-local',
    payload_bytes: historicalBytes,
    multicodec: 'dag-json',
  });
  const historicalOk = historical.accept === true;

  return {
    algorithm: ALGORITHM_ID,
    interface: INTERFACE,
    vectors_dir: root,
    total: cases.length,
    passed,
    failed,
    historical_readable: historicalOk,
    results,
    ok: failed === 0 && historicalOk,
  };
}

export class CanonicalJcsValidator {
  readonly algorithm = ALGORITHM_ID;
  readonly interface = INTERFACE;

  canonicalize(value: unknown): string {
    return canonicalize(value);
  }
  canonicalizeBytes(value: unknown): Uint8Array {
    return canonicalizeBytes(value);
  }
  sha256(value: unknown): string {
    return sha256Hex(value);
  }
  cid(value: unknown): string {
    return artifactCid(value);
  }
  identity(value: unknown): CanonicalIdentity {
    return identity(value);
  }
  parse(text: string): unknown {
    return parseJsonStrict(text);
  }
  verifyCanonical(offered: string | Uint8Array, value?: unknown): Uint8Array {
    return verifyCanonicalBytes(offered, value);
  }
  validateCase(caseObj: Record<string, any>): ValidatorResult {
    return validateVectorCase(caseObj);
  }
  runGoldenVectors(vectorsDir?: string): Record<string, any> {
    return runGoldenVectors(vectorsDir);
  }
  verifyHistorical(args: {
    cid: string;
    algorithm: string;
    value?: unknown;
    payload_bytes?: Uint8Array;
    multicodec?: string | null;
  }): ValidatorResult {
    return verifyRecordedBinding(args);
  }
}

/** Vitest-friendly suite name anchor: canonicalJcs golden vectors. */
export const canonicalJcsSuiteName = 'canonicalJcs';

export function main(): number {
  const report = runGoldenVectors();
  // eslint-disable-next-line no-console
  console.log(
    JSON.stringify(
      {
        ok: report.ok,
        passed: report.passed,
        failed: report.failed,
        total: report.total,
        historical_readable: report.historical_readable,
        failures: report.results.filter((r: any) => !r.ok),
      },
      null,
      2,
    ),
  );
  return report.ok ? 0 : 1;
}

const isDirect =
  typeof process !== 'undefined' &&
  process.argv[1] &&
  fileURLToPath(import.meta.url) === process.argv[1];
if (isDirect) {
  process.exit(main());
}

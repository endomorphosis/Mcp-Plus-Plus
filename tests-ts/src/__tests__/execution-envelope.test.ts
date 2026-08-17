/**
 * MCPP-033: four-language ExecutionEnvelope@1 family validators and vectors.
 *
 * Interface: ExecutionEnvelopeValidator@1
 * Track: envelope-validators
 *
 * Mirrors the positive/negative catalog in:
 *   - tests-py/integration/test_execution_envelope.py
 *   - tests-go/execution_envelope_test.go
 *   - tests-rs/tests/execution_envelope_test.rs
 *
 * Structural acceptance only (ADR-0003). Same case ids must accept/reject
 * identically across languages.
 */

import { describe, it, expect } from 'vitest';

// ---------------------------------------------------------------------------
// Interface / markers
// ---------------------------------------------------------------------------

export const INTERFACE = 'ExecutionEnvelopeValidator@1';
export const TASK_ID = 'MCPP-033';

const SCHEMA_ENVELOPE = 'mcp++/execution/envelope@1';
const SCHEMA_RESULT = 'mcp++/execution/result@1';
const SCHEMA_RECEIPT = 'mcp++/execution/receipt@1';
const SCHEMA_ERROR = 'mcp++/execution/portable-error@1';

const CID_A = 'bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi';
const CID_B = 'bafkreihtwdlu4jntm7yl2mgsfzqgr4on37vr7inuld2dql2p4rmqafybti';
const CID_C = 'bafkreicssskybdf32rmzlbtge5bxyv4v6c6eac322pbrsr3azlb4fkxiqi';
const CID_D = 'bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku';

const DID_REQUESTER = 'did:key:z6MkrequesterExample0001';
const DID_EXECUTOR = 'did:key:z6MkexecutorExample00001';

const CID_RE = /^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58,})$/;
const DID_RE = /^did:[a-z0-9]+:[A-Za-z0-9._:%-]+(?:[/?#][^\x00]*)?$/;

const STATUS_VALUES = new Set([
  'succeeded',
  'failed',
  'cancelled',
  'rejected',
  'timed_out',
  'compensated',
]);

const FAILURE_CLASSES = new Set([
  'none',
  'retryable',
  'permanent',
  'policy',
  'authority',
  'fenced',
  'resource',
  'cancelled',
  'timeout',
  'internal',
]);

type Kind = 'envelope' | 'result' | 'receipt' | 'error';

interface ValidationResult {
  is_valid: boolean;
  errors: string[];
}

// ---------------------------------------------------------------------------
// ExecutionEnvelopeValidator@1 (structural)
// ---------------------------------------------------------------------------

function isValidCid(v: unknown): boolean {
  return typeof v === 'string' && CID_RE.test(v);
}

function isValidDid(v: unknown): boolean {
  return typeof v === 'string' && DID_RE.test(v);
}

function isNonNegInt(v: unknown): boolean {
  return typeof v === 'number' && Number.isInteger(v) && v >= 0 && !Object.is(v, -0);
}

function add(result: ValidationResult, msg: string): void {
  result.errors.push(msg);
  result.is_valid = false;
}

export function validatePortableError(error: unknown): ValidationResult {
  const result: ValidationResult = { is_valid: true, errors: [] };
  if (typeof error !== 'object' || error === null || Array.isArray(error)) {
    add(result, 'error must be an object');
    return result;
  }
  const e = error as Record<string, unknown>;
  if (e.schema !== SCHEMA_ERROR) add(result, `schema must be ${SCHEMA_ERROR}`);
  for (const key of ['code', 'message', 'retryable', 'failure_class'] as const) {
    if (!(key in e)) add(result, `missing required field: ${key}`);
  }
  if ('failure_class' in e && !FAILURE_CLASSES.has(String(e.failure_class))) {
    add(result, `invalid failure_class: ${String(e.failure_class)}`);
  }
  if ('retryable' in e && typeof e.retryable !== 'boolean') {
    add(result, 'retryable must be a boolean');
  }
  if ('details_cid' in e && e.details_cid != null && !isValidCid(e.details_cid)) {
    add(result, 'invalid CID at /details_cid');
  }
  return result;
}

export function validateEnvelope(envelope: unknown): ValidationResult {
  const result: ValidationResult = { is_valid: true, errors: [] };
  if (typeof envelope !== 'object' || envelope === null || Array.isArray(envelope)) {
    add(result, 'envelope must be an object');
    return result;
  }
  const env = envelope as Record<string, unknown>;
  if (env.schema !== SCHEMA_ENVELOPE) add(result, `schema must be ${SCHEMA_ENVELOPE}`);

  for (const key of [
    'schema',
    'interface_cid',
    'input_cid',
    'intent_cid',
    'parents',
    'created_at_ms',
    'correlation_id',
    'requester',
    'authority',
  ] as const) {
    if (!(key in env)) add(result, `missing required field: ${key}`);
  }

  for (const key of [
    'interface_cid',
    'input_cid',
    'intent_cid',
    'policy_cid',
    'decision_cid',
    'constraints_cid',
    'expected_output_schema_cid',
    'metadata_cid',
    'profile_b_envelope_cid',
  ] as const) {
    if (key in env && env[key] != null && !isValidCid(env[key])) {
      add(result, `invalid CID at /${key}`);
    }
  }

  if ('parents' in env) {
    if (!Array.isArray(env.parents)) add(result, 'parents must be an array');
    else {
      env.parents.forEach((p, i) => {
        if (!isValidCid(p)) add(result, `invalid parent CID at /parents/${i}`);
      });
    }
  }

  if ('created_at_ms' in env && !isNonNegInt(env.created_at_ms)) {
    add(result, 'created_at_ms must be a non-negative integer');
  }

  if (
    'correlation_id' in env &&
    (typeof env.correlation_id !== 'string' ||
      env.correlation_id.length < 1 ||
      env.correlation_id.length > 128)
  ) {
    add(result, 'correlation_id must be a string of length 1..128');
  }

  if ('requester' in env) {
    const req = env.requester;
    if (typeof req !== 'object' || req === null || !isValidDid((req as { did?: unknown }).did)) {
      add(result, 'requester.did must be a valid DID');
    }
  }

  if ('authority' in env) {
    const auth = env.authority;
    if (typeof auth !== 'object' || auth === null || Array.isArray(auth)) {
      add(result, 'authority must be an object');
    } else {
      const a = auth as Record<string, unknown>;
      if (!('proof_cids' in a)) add(result, 'authority.proof_cids is required');
      else if (!Array.isArray(a.proof_cids)) add(result, 'authority.proof_cids must be an array');
      else {
        a.proof_cids.forEach((cid, i) => {
          if (!isValidCid(cid)) add(result, `invalid CID at /authority/proof_cids/${i}`);
        });
      }
      if (a.proof_cid != null && !isValidCid(a.proof_cid)) {
        add(result, 'invalid CID at /authority/proof_cid');
      }
    }
  }

  if ('canonicalization' in env && env.canonicalization != null && env.canonicalization !== 'mcpp-jcs-v1') {
    add(result, "canonicalization must be 'mcpp-jcs-v1' when present");
  }

  return result;
}

export function validateResult(resultObj: unknown): ValidationResult {
  const result: ValidationResult = { is_valid: true, errors: [] };
  if (typeof resultObj !== 'object' || resultObj === null || Array.isArray(resultObj)) {
    add(result, 'result must be an object');
    return result;
  }
  const r = resultObj as Record<string, unknown>;
  if (r.schema !== SCHEMA_RESULT) add(result, `schema must be ${SCHEMA_RESULT}`);

  for (const key of [
    'schema',
    'envelope_cid',
    'status',
    'output_cids',
    'state_transitions',
    'side_effects',
    'decision_cid',
    'delegation_cid',
    'executor',
    'retry',
    'duration_ms',
    'error',
    'proofs',
    'started_at_ms',
    'finished_at_ms',
  ] as const) {
    if (!(key in r)) add(result, `missing required field: ${key}`);
  }

  if ('status' in r && !STATUS_VALUES.has(String(r.status))) {
    add(result, `invalid status: ${String(r.status)}`);
  }
  if (r.status === 'succeeded' && r.error != null) {
    add(result, 'error must be null when status is succeeded');
  }
  if ('envelope_cid' in r && r.envelope_cid != null && !isValidCid(r.envelope_cid)) {
    add(result, 'invalid CID at /envelope_cid');
  }
  if ('output_cids' in r) {
    if (!Array.isArray(r.output_cids)) add(result, 'output_cids must be an array');
    else {
      r.output_cids.forEach((cid, i) => {
        if (!isValidCid(cid)) add(result, `invalid CID at /output_cids/${i}`);
      });
    }
  }
  if ('executor' in r) {
    const ex = r.executor;
    if (typeof ex !== 'object' || ex === null || !isValidDid((ex as { did?: unknown }).did)) {
      add(result, 'executor.did must be a valid DID');
    }
  }
  if (r.error != null) {
    const pe = validatePortableError(r.error);
    if (!pe.is_valid) {
      result.errors.push(...pe.errors);
      result.is_valid = false;
    }
  }
  if ('started_at_ms' in r && !isNonNegInt(r.started_at_ms)) {
    add(result, 'started_at_ms must be a non-negative integer');
  }
  if ('finished_at_ms' in r && !isNonNegInt(r.finished_at_ms)) {
    add(result, 'finished_at_ms must be a non-negative integer');
  }
  if (
    isNonNegInt(r.started_at_ms) &&
    isNonNegInt(r.finished_at_ms) &&
    (r.finished_at_ms as number) < (r.started_at_ms as number)
  ) {
    add(result, 'finished_at_ms must be >= started_at_ms');
  }
  return result;
}

export function validateReceipt(receipt: unknown): ValidationResult {
  const result: ValidationResult = { is_valid: true, errors: [] };
  if (typeof receipt !== 'object' || receipt === null || Array.isArray(receipt)) {
    add(result, 'receipt must be an object');
    return result;
  }
  const rc = receipt as Record<string, unknown>;
  if (rc.schema !== SCHEMA_RECEIPT) add(result, `schema must be ${SCHEMA_RECEIPT}`);

  for (const key of [
    'schema',
    'envelope_cid',
    'result_cid',
    'status',
    'output_cids',
    'state_transitions',
    'side_effects',
    'decision_cid',
    'delegation_cid',
    'executor',
    'retry',
    'duration_ms',
    'error',
    'proofs',
    'signature',
    'event_cid',
    'started_at_ms',
    'finished_at_ms',
  ] as const) {
    if (!(key in rc)) add(result, `missing required field: ${key}`);
  }

  for (const key of [
    'envelope_cid',
    'result_cid',
    'intent_cid',
    'receipt_cid',
    'decision_cid',
    'delegation_cid',
    'proof_cid',
    'event_cid',
    'primary_output_cid',
    'resource_use_cid',
    'policy_cid',
    'profile_b_receipt_cid',
    'profile_g_task_receipt_cid',
  ] as const) {
    if (key in rc && rc[key] != null && !isValidCid(rc[key])) {
      add(result, `invalid CID at /${key}`);
    }
  }

  if ('output_cids' in rc) {
    if (!Array.isArray(rc.output_cids)) add(result, 'output_cids must be an array');
    else {
      rc.output_cids.forEach((cid, i) => {
        if (!isValidCid(cid)) add(result, `invalid CID at /output_cids/${i}`);
      });
    }
  }

  if ('status' in rc && !STATUS_VALUES.has(String(rc.status))) {
    add(result, `invalid status: ${String(rc.status)}`);
  }
  if (rc.status === 'succeeded' && rc.error != null) {
    add(result, 'error must be null when status is succeeded');
  }

  if ('executor' in rc) {
    const ex = rc.executor;
    if (typeof ex !== 'object' || ex === null || !isValidDid((ex as { did?: unknown }).did)) {
      add(result, 'executor.did must be a valid DID');
    }
  }

  if ('retry' in rc) {
    const retry = rc.retry;
    if (
      typeof retry !== 'object' ||
      retry === null ||
      typeof (retry as { attempt?: unknown }).attempt !== 'number' ||
      !Number.isInteger((retry as { attempt: number }).attempt) ||
      (retry as { attempt: number }).attempt < 1
    ) {
      add(result, 'retry.attempt must be an integer >= 1');
    }
  }

  if (rc.error != null) {
    const pe = validatePortableError(rc.error);
    if (!pe.is_valid) {
      result.errors.push(...pe.errors);
      result.is_valid = false;
    }
  }

  for (const ts of ['started_at_ms', 'finished_at_ms'] as const) {
    if (ts in rc && !isNonNegInt(rc[ts])) {
      add(result, `${ts} must be a non-negative integer`);
    }
  }
  if (
    isNonNegInt(rc.started_at_ms) &&
    isNonNegInt(rc.finished_at_ms) &&
    (rc.finished_at_ms as number) < (rc.started_at_ms as number)
  ) {
    add(result, 'finished_at_ms must be >= started_at_ms');
  }

  if ('canonicalization' in rc && rc.canonicalization != null && rc.canonicalization !== 'mcpp-jcs-v1') {
    add(result, "canonicalization must be 'mcpp-jcs-v1' when present");
  }

  return result;
}

/** ExecutionEnvelopeValidator@1 dispatch. */
export function validateKind(kind: Kind, payload: unknown): boolean {
  switch (kind) {
    case 'envelope':
      return validateEnvelope(payload).is_valid;
    case 'result':
      return validateResult(payload).is_valid;
    case 'receipt':
      return validateReceipt(payload).is_valid;
    case 'error':
      return validatePortableError(payload).is_valid;
    default:
      throw new Error(`unknown kind: ${kind}`);
  }
}

// ---------------------------------------------------------------------------
// Shared fixtures / catalog (ids MUST match py/go/rs)
// ---------------------------------------------------------------------------

function deepClone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v)) as T;
}

function baseEnvelope(): Record<string, unknown> {
  return {
    schema: SCHEMA_ENVELOPE,
    interface_cid: CID_A,
    method: 'repo.status',
    input_cid: CID_B,
    intent_cid: CID_C,
    policy_cid: CID_D,
    parents: [],
    created_at_ms: 1783872000000,
    correlation_id: 'task-001',
    requester: { did: DID_REQUESTER },
    authority: {
      proof_cids: [CID_D],
      proof_cid: CID_D,
    },
    constraints: { timeout_ms: 30000, max_retries: 3 },
    state_refs: [],
    canonicalization: 'mcpp-jcs-v1',
  };
}

function basePortableError(): Record<string, unknown> {
  return {
    schema: SCHEMA_ERROR,
    code: 'E_POLICY_DENIED',
    message: 'policy denied execution',
    retryable: false,
    failure_class: 'policy',
  };
}

function baseResultSucceeded(): Record<string, unknown> {
  return {
    schema: SCHEMA_RESULT,
    envelope_cid: CID_A,
    status: 'succeeded',
    output_cids: [CID_B],
    state_transitions: [],
    side_effects: [],
    decision_cid: CID_D,
    delegation_cid: CID_C,
    executor: { did: DID_EXECUTOR },
    retry: { attempt: 1 },
    duration_ms: 12.5,
    error: null,
    proofs: [CID_D],
    started_at_ms: 1783872001100,
    finished_at_ms: 1783872001113,
    canonicalization: 'mcpp-jcs-v1',
  };
}

function baseResultFailed(): Record<string, unknown> {
  const obj = baseResultSucceeded();
  obj.status = 'failed';
  obj.output_cids = [];
  obj.error = basePortableError();
  return obj;
}

function baseReceiptSucceeded(): Record<string, unknown> {
  return {
    schema: SCHEMA_RECEIPT,
    envelope_cid: CID_A,
    result_cid: CID_B,
    status: 'succeeded',
    output_cids: [CID_C],
    state_transitions: [],
    side_effects: [],
    decision_cid: CID_D,
    delegation_cid: CID_C,
    executor: {
      did: DID_EXECUTOR,
      runtime: 'ipfs_accelerate_py',
      runtime_version: '3.2.0',
    },
    retry: { attempt: 1 },
    duration_ms: 12.5,
    error: null,
    proofs: [CID_D],
    signature: null,
    signature_alg: null,
    event_cid: CID_A,
    started_at_ms: 1783872001100,
    finished_at_ms: 1783872001113,
    canonicalization: 'mcpp-jcs-v1',
  };
}

function baseReceiptFailed(): Record<string, unknown> {
  const obj = baseReceiptSucceeded();
  obj.status = 'failed';
  obj.output_cids = [];
  obj.error = basePortableError();
  return obj;
}

interface VectorCase {
  id: string;
  kind: Kind;
  payload: Record<string, unknown>;
  expectValid: boolean;
}

function vectorCatalog(): VectorCase[] {
  const cases: VectorCase[] = [
    { id: 'pos-envelope-minimal', kind: 'envelope', payload: baseEnvelope(), expectValid: true },
    {
      id: 'pos-envelope-with-parents',
      kind: 'envelope',
      payload: { ...baseEnvelope(), parents: [CID_A, CID_B] },
      expectValid: true,
    },
    { id: 'pos-result-succeeded', kind: 'result', payload: baseResultSucceeded(), expectValid: true },
    {
      id: 'pos-result-failed-with-error',
      kind: 'result',
      payload: baseResultFailed(),
      expectValid: true,
    },
    {
      id: 'pos-receipt-succeeded',
      kind: 'receipt',
      payload: baseReceiptSucceeded(),
      expectValid: true,
    },
    { id: 'pos-receipt-failed', kind: 'receipt', payload: baseReceiptFailed(), expectValid: true },
    { id: 'pos-portable-error', kind: 'error', payload: basePortableError(), expectValid: true },
  ];

  // Envelope negatives
  {
    const p = baseEnvelope();
    p.schema = 'mcp++/execution/envelope@0';
    cases.push({ id: 'neg-envelope-wrong-schema', kind: 'envelope', payload: p, expectValid: false });
  }
  {
    const p = baseEnvelope();
    delete p.interface_cid;
    cases.push({
      id: 'neg-envelope-missing-interface-cid',
      kind: 'envelope',
      payload: p,
      expectValid: false,
    });
  }
  {
    const p = baseEnvelope();
    p.interface_cid = 'not-a-cid';
    cases.push({ id: 'neg-envelope-invalid-cid', kind: 'envelope', payload: p, expectValid: false });
  }
  {
    const p = baseEnvelope();
    p.requester = { did: 'not-a-did' };
    cases.push({ id: 'neg-envelope-invalid-did', kind: 'envelope', payload: p, expectValid: false });
  }
  {
    const p = baseEnvelope();
    p.authority = { proof_cids: ['bad-cid'] };
    cases.push({
      id: 'neg-envelope-invalid-proof-cid',
      kind: 'envelope',
      payload: p,
      expectValid: false,
    });
  }
  {
    const p = baseEnvelope();
    p.canonicalization = 'jcs-v0';
    cases.push({
      id: 'neg-envelope-bad-canonicalization',
      kind: 'envelope',
      payload: p,
      expectValid: false,
    });
  }
  {
    const p = baseEnvelope();
    p.created_at_ms = -1;
    cases.push({
      id: 'neg-envelope-negative-timestamp',
      kind: 'envelope',
      payload: p,
      expectValid: false,
    });
  }
  {
    const p = baseEnvelope();
    p.correlation_id = '';
    cases.push({
      id: 'neg-envelope-empty-correlation',
      kind: 'envelope',
      payload: p,
      expectValid: false,
    });
  }
  {
    const p = baseEnvelope();
    p.parents = ['not-a-cid'];
    cases.push({ id: 'neg-envelope-bad-parent', kind: 'envelope', payload: p, expectValid: false });
  }
  {
    const p = baseEnvelope();
    const auth = { ...(p.authority as Record<string, unknown>) };
    delete auth.proof_cids;
    p.authority = auth;
    cases.push({
      id: 'neg-envelope-missing-proof-cids',
      kind: 'envelope',
      payload: p,
      expectValid: false,
    });
  }

  // Error negatives
  {
    const p = basePortableError();
    p.schema = 'mcp++/execution/portable-error@0';
    cases.push({ id: 'neg-error-wrong-schema', kind: 'error', payload: p, expectValid: false });
  }
  {
    const p = basePortableError();
    delete p.code;
    cases.push({ id: 'neg-error-missing-code', kind: 'error', payload: p, expectValid: false });
  }
  {
    const p = basePortableError();
    p.failure_class = 'bogus';
    cases.push({ id: 'neg-error-bad-failure-class', kind: 'error', payload: p, expectValid: false });
  }
  {
    const p = basePortableError();
    p.retryable = 'yes';
    cases.push({ id: 'neg-error-nonbool-retryable', kind: 'error', payload: p, expectValid: false });
  }

  // Result negatives
  {
    const p = baseResultSucceeded();
    p.schema = 'mcp++/execution/result@0';
    cases.push({ id: 'neg-result-wrong-schema', kind: 'result', payload: p, expectValid: false });
  }
  {
    const p = baseResultSucceeded();
    delete p.status;
    cases.push({ id: 'neg-result-missing-status', kind: 'result', payload: p, expectValid: false });
  }
  {
    const p = baseResultSucceeded();
    p.status = 'running';
    cases.push({ id: 'neg-result-bad-status', kind: 'result', payload: p, expectValid: false });
  }
  {
    const p = baseResultSucceeded();
    p.error = basePortableError();
    cases.push({
      id: 'neg-result-succeeded-with-error',
      kind: 'result',
      payload: p,
      expectValid: false,
    });
  }
  {
    const p = baseResultSucceeded();
    p.envelope_cid = 'not-a-cid';
    cases.push({
      id: 'neg-result-invalid-envelope-cid',
      kind: 'result',
      payload: p,
      expectValid: false,
    });
  }

  // Receipt negatives
  {
    const p = baseReceiptSucceeded();
    p.schema = 'mcp++/execution/receipt@0';
    cases.push({ id: 'neg-receipt-wrong-schema', kind: 'receipt', payload: p, expectValid: false });
  }
  {
    const p = baseReceiptSucceeded();
    delete p.result_cid;
    cases.push({
      id: 'neg-receipt-missing-result-cid',
      kind: 'receipt',
      payload: p,
      expectValid: false,
    });
  }
  {
    const p = baseReceiptSucceeded();
    p.envelope_cid = 'not-a-cid';
    cases.push({ id: 'neg-receipt-invalid-cid', kind: 'receipt', payload: p, expectValid: false });
  }
  {
    const p = baseReceiptSucceeded();
    p.status = 'running';
    cases.push({ id: 'neg-receipt-bad-status', kind: 'receipt', payload: p, expectValid: false });
  }
  {
    const p = baseReceiptSucceeded();
    p.error = basePortableError();
    cases.push({
      id: 'neg-receipt-succeeded-with-error',
      kind: 'receipt',
      payload: p,
      expectValid: false,
    });
  }
  {
    const p = baseReceiptSucceeded();
    p.started_at_ms = 100;
    p.finished_at_ms = 1;
    cases.push({ id: 'neg-receipt-time-order', kind: 'receipt', payload: p, expectValid: false });
  }
  {
    const p = baseReceiptSucceeded();
    p.executor = { did: 'not-a-did' };
    cases.push({
      id: 'neg-receipt-bad-executor-did',
      kind: 'receipt',
      payload: p,
      expectValid: false,
    });
  }
  {
    const p = baseReceiptSucceeded();
    p.retry = { attempt: 0 };
    cases.push({
      id: 'neg-receipt-retry-attempt-zero',
      kind: 'receipt',
      payload: p,
      expectValid: false,
    });
  }

  return cases;
}

const EXPECTED_POSITIVE_IDS = new Set([
  'pos-envelope-minimal',
  'pos-envelope-with-parents',
  'pos-result-succeeded',
  'pos-result-failed-with-error',
  'pos-receipt-succeeded',
  'pos-receipt-failed',
  'pos-portable-error',
]);

const EXPECTED_NEGATIVE_IDS = new Set([
  'neg-envelope-wrong-schema',
  'neg-envelope-missing-interface-cid',
  'neg-envelope-invalid-cid',
  'neg-envelope-invalid-did',
  'neg-envelope-invalid-proof-cid',
  'neg-envelope-bad-canonicalization',
  'neg-envelope-negative-timestamp',
  'neg-envelope-empty-correlation',
  'neg-envelope-bad-parent',
  'neg-envelope-missing-proof-cids',
  'neg-error-wrong-schema',
  'neg-error-missing-code',
  'neg-error-bad-failure-class',
  'neg-error-nonbool-retryable',
  'neg-result-wrong-schema',
  'neg-result-missing-status',
  'neg-result-bad-status',
  'neg-result-succeeded-with-error',
  'neg-result-invalid-envelope-cid',
  'neg-receipt-wrong-schema',
  'neg-receipt-missing-result-cid',
  'neg-receipt-invalid-cid',
  'neg-receipt-bad-status',
  'neg-receipt-succeeded-with-error',
  'neg-receipt-time-order',
  'neg-receipt-bad-executor-did',
  'neg-receipt-retry-attempt-zero',
]);

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ExecutionEnvelopeValidator@1 interface', () => {
  it('exports interface constants', () => {
    expect(INTERFACE).toBe('ExecutionEnvelopeValidator@1');
    expect(TASK_ID).toBe('MCPP-033');
  });

  it('catalog ids match expected sets', () => {
    const catalog = vectorCatalog();
    const pos = new Set(catalog.filter((c) => c.expectValid).map((c) => c.id));
    const neg = new Set(catalog.filter((c) => !c.expectValid).map((c) => c.id));
    expect(pos).toEqual(EXPECTED_POSITIVE_IDS);
    expect(neg).toEqual(EXPECTED_NEGATIVE_IDS);
    const ids = catalog.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe('ExecutionEnvelopeValidator@1 vectors', () => {
  const catalog = vectorCatalog();

  it.each(catalog)('$id ($kind) expectValid=$expectValid', (c) => {
    const ok = validateKind(c.kind, deepClone(c.payload));
    expect(ok).toBe(c.expectValid);
  });

  it('accepts all positives', () => {
    for (const c of catalog.filter((x) => x.expectValid)) {
      expect(validateKind(c.kind, c.payload), c.id).toBe(true);
    }
  });

  it('rejects all negatives', () => {
    for (const c of catalog.filter((x) => !x.expectValid)) {
      expect(validateKind(c.kind, c.payload), c.id).toBe(false);
    }
  });
});

describe('ExecutionEnvelope@1 cross-kind invariants', () => {
  it('succeeded result requires null error', () => {
    const payload = baseResultSucceeded();
    expect(validateKind('result', payload)).toBe(true);
    payload.error = basePortableError();
    expect(validateKind('result', payload)).toBe(false);
  });

  it('failed result carries portable error', () => {
    const payload = baseResultFailed();
    expect(validateKind('result', payload)).toBe(true);
    expect(validateKind('error', payload.error as Record<string, unknown>)).toBe(true);
  });

  it('receipt requires result_cid', () => {
    const payload = baseReceiptSucceeded();
    delete payload.result_cid;
    expect(validateKind('receipt', payload)).toBe(false);
  });
});

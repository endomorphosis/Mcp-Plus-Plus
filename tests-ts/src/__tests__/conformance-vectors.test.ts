/**
 * Cross-language conformance: validate shared vectors against canonical schemas.
 * Same conformance/vectors/*.json as py/rs/go so the four mirrors can't drift.
 */
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'fs';
import { join } from 'path';
import {
  InitializeResultSchema,
  PolicyDecisionSchema,
  P2PMessageSchema,
  DelegationSchema,
  DAGEventSchema,
  ExecutionReceiptSchema,
  SessionErrorSchema,
  BusMessageSchema,
  AuditEntrySchema,
  WasmProofResultSchema,
  ZKProofArtifactSchema,
} from '../models';

const MODELS: Record<string, any> = {
  InitializeResult: InitializeResultSchema,
  PolicyDecision: PolicyDecisionSchema,
  P2PMessage: P2PMessageSchema,
  Delegation: DelegationSchema,
  DAGEvent: DAGEventSchema,
  ExecutionReceipt: ExecutionReceiptSchema,
  SessionError: SessionErrorSchema,
  BusMessage: BusMessageSchema,
  AuditEntry: AuditEntrySchema,
  WasmProofResult: WasmProofResultSchema,
  ZKProofArtifact: ZKProofArtifactSchema,
};

const VEC_DIR = join(__dirname, '..', '..', '..', 'conformance', 'vectors');

describe('conformance vectors', () => {
  const vectors = readdirSync(VEC_DIR)
    .filter((fn) => fn.endsWith('.json'))
    .map((fn) => [fn, JSON.parse(readFileSync(join(VEC_DIR, fn), 'utf8'))] as const)
    // Profile-specific suites have their own codecs and intentionally omit the
    // canonical {model, payload} envelope.
    .filter(([, v]) => 'model' in v || 'payload' in v);

  it.each(vectors)('%s validates against its model', (fn, v) => {
    const schema = MODELS[v.model];
    expect(schema, `unknown model ${v.model}`).toBeDefined();
    expect(() => schema.parse(v.payload)).not.toThrow();
  });
});

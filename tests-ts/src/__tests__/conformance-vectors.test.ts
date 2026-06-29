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
} from '../models';

const MODELS: Record<string, any> = {
  InitializeResult: InitializeResultSchema,
  PolicyDecision: PolicyDecisionSchema,
  P2PMessage: P2PMessageSchema,
  Delegation: DelegationSchema,
  DAGEvent: DAGEventSchema,
  ExecutionReceipt: ExecutionReceiptSchema,
};

const VEC_DIR = join(__dirname, '..', '..', '..', 'conformance', 'vectors');

describe('conformance vectors', () => {
  const files = readdirSync(VEC_DIR).filter((f) => f.endsWith('.json'));
  it.each(files)('%s validates against its model', (fn) => {
    const v = JSON.parse(readFileSync(join(VEC_DIR, fn), 'utf8'));
    const schema = MODELS[v.model];
    expect(schema, `unknown model ${v.model}`).toBeDefined();
    expect(() => schema.parse(v.payload)).not.toThrow();
  });
});

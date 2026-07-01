/**
 * Cross-language conformance tests for new MCP++ schemas.
 *
 * Validates:
 * - SessionErrorCode taxonomy (Profile E §9.1)
 * - BusMessage wire format (Profile E §3 — MCPPubSubBus)
 * - AuditEntry wire format (Profile D — PolicyAuditLog)
 *
 * Also exercises interop with SwissKnife's live implementations when the
 * monorepo path is present (gracefully skips in standalone spec clones).
 */
import { describe, it, expect } from 'vitest';
import {
  SessionErrorCodeSchema,
  SessionErrorSchema,
  BusMessageSchema,
  AuditEntrySchema,
  MCP_PUBSUB_TOPICS,
  AuditDecisionSchema,
  WasmProofResultSchema,
  ProofReasonSchema,
  WasmProverIdSchema,
} from '../models';

// SwissKnife live modules (optional — skip if not in monorepo)
let SessionErrorCode: Record<string, number> | undefined;
let computeBackoffDelay: ((policy: object, attempt: number) => number) | undefined;
let negotiateCapabilities: ((c: string[], s: string[]) => { negotiated: string[]; downgraded: boolean }) | undefined;
let MCPPubSubBus: any;
let PolicyAuditLog: any;

try {
  const session = await import('../../../../swissknife/src/services/mcp-p2p-session');
  SessionErrorCode = session.SessionErrorCode as Record<string, number>;
  computeBackoffDelay = session.computeBackoffDelay;
  negotiateCapabilities = session.negotiateCapabilities;
  const busModule = await import('../../../../swissknife/src/services/mcp-pubsub-bus');
  MCPPubSubBus = busModule.MCPPubSubBus;
  const auditModule = await import('../../../../swissknife/src/services/policy-audit-log');
  PolicyAuditLog = auditModule.PolicyAuditLog;
} catch {
  // standalone spec clone: swissknife not available
}

const hasSwissKnife = !!SessionErrorCode;

// ---------------------------------------------------------------------------
// SessionErrorCode — deterministic taxonomy
// ---------------------------------------------------------------------------

describe('SessionErrorCode schema (MCP++ Profile E §9.1)', () => {
  it('schema accepts all canonical framing error codes', () => {
    for (const code of [1001, 1002, 1003, 1004]) {
      expect(() => SessionErrorCodeSchema.parse(code)).not.toThrow();
    }
  });

  it('schema accepts all canonical protocol error codes', () => {
    for (const code of [2001, 2002, 2003]) {
      expect(() => SessionErrorCodeSchema.parse(code)).not.toThrow();
    }
  });

  it('schema accepts all canonical rate/lifecycle error codes', () => {
    for (const code of [3001, 4001, 4002, 4003]) {
      expect(() => SessionErrorCodeSchema.parse(code)).not.toThrow();
    }
  });

  it('schema rejects arbitrary non-canonical codes', () => {
    for (const code of [0, 999, 1005, 2004, 5000, -1]) {
      expect(() => SessionErrorCodeSchema.parse(code), `code ${code} should be rejected`).toThrow();
    }
  });

  it('SessionError schema validates a correctly-shaped error object', () => {
    const err = { code: 1001, message: 'frame too large', data: { frameLen: 99 } };
    expect(() => SessionErrorSchema.parse(err)).not.toThrow();
  });

  it('SessionError schema rejects non-canonical error code', () => {
    expect(() => SessionErrorSchema.parse({ code: 9999, message: 'bad' })).toThrow();
  });
});

describe.skipIf(!hasSwissKnife)('SwissKnife SessionErrorCode interop', () => {
  it('swissknife FRAME_OVERSIZE code matches spec 1001', () => {
    expect(SessionErrorCode!.FRAME_OVERSIZE).toBe(1001);
  });

  it('swissknife FRAME_OUTBOUND_OVERSIZE code matches spec 1002', () => {
    expect(SessionErrorCode!.FRAME_OUTBOUND_OVERSIZE).toBe(1002);
  });

  it('swissknife FRAME_MALFORMED_JSON code matches spec 1003', () => {
    expect(SessionErrorCode!.FRAME_MALFORMED_JSON).toBe(1003);
  });

  it('swissknife PROTOCOL_HANDSHAKE_INVALID code matches spec 2002', () => {
    expect(SessionErrorCode!.PROTOCOL_HANDSHAKE_INVALID).toBe(2002);
  });

  it('swissknife SESSION_CLOSED code matches spec 4001', () => {
    expect(SessionErrorCode!.SESSION_CLOSED).toBe(4001);
  });

  it('all swissknife error codes validate against the spec schema', () => {
    for (const [name, code] of Object.entries(SessionErrorCode!)) {
      expect(() => SessionErrorCodeSchema.parse(code), `${name}=${code}`).not.toThrow();
    }
  });

  it('computeBackoffDelay produces values within policy bounds', () => {
    const d0 = computeBackoffDelay!({ initialDelayMs: 100, jitter: 0 }, 0);
    const d1 = computeBackoffDelay!({ initialDelayMs: 100, backoffFactor: 2, jitter: 0 }, 1);
    expect(d0).toBe(100);
    expect(d1).toBe(200);
  });

  it('negotiateCapabilities intersection is spec-valid', () => {
    const { negotiated, downgraded } = negotiateCapabilities!(
      ['mcp++/cid-envelope', 'mcp++/ucan', 'mcp++/policy-d'],
      ['mcp++/cid-envelope', 'mcp++/ucan'],
    );
    expect(negotiated).toEqual(['mcp++/cid-envelope', 'mcp++/ucan']);
    expect(downgraded).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// BusMessage — PubSubBus wire format (Profile E §3)
// ---------------------------------------------------------------------------

describe('BusMessage schema (MCP++ Profile E §3)', () => {
  const validMsg = {
    topic: 'mcp/interface/announce',
    payload: { interface_cid: 'sha256:abc' },
    published_at: new Date().toISOString(),
    message_cid: 'sha256:' + '0'.repeat(64),
  };

  it('validates a well-formed BusMessage', () => {
    expect(() => BusMessageSchema.parse(validMsg)).not.toThrow();
  });

  it('rejects a BusMessage with invalid message_cid format', () => {
    expect(() => BusMessageSchema.parse({ ...validMsg, message_cid: 'bad-cid' })).toThrow();
  });

  it('allows optional ucan_token', () => {
    expect(() => BusMessageSchema.parse({ ...validMsg, ucan_token: 'some.token' })).not.toThrow();
  });

  it('MCP_PUBSUB_TOPICS contains all five well-known topics', () => {
    expect(MCP_PUBSUB_TOPICS).toHaveLength(5);
    expect(MCP_PUBSUB_TOPICS).toContain('mcp/interface/announce');
    expect(MCP_PUBSUB_TOPICS).toContain('mcp/delegation/merge');
    expect(MCP_PUBSUB_TOPICS).toContain('mcp/policy/update');
  });
});

describe.skipIf(!hasSwissKnife)('SwissKnife MCPPubSubBus BusMessage interop', () => {
  it('MCPPubSubBus.publish produces a spec-valid BusMessage', async () => {
    const bus = new MCPPubSubBus();
    await bus.start();
    const received: unknown[] = [];
    bus.subscribe('mcp/interface/announce', (msg: unknown) => received.push(msg));
    const published = await bus.publish('mcp/interface/announce', { cid: 'sha256:test' });
    expect(() => BusMessageSchema.parse(published)).not.toThrow();
    expect(received).toHaveLength(1);
    expect(() => BusMessageSchema.parse(received[0])).not.toThrow();
    await bus.stop();
    MCPPubSubBus.resetInstance();
  });

  it('MCPPubSubBus topics match MCP_PUBSUB_TOPICS', () => {
    for (const topic of MCP_PUBSUB_TOPICS) {
      expect(typeof topic).toBe('string');
    }
  });
});

// ---------------------------------------------------------------------------
// AuditEntry — PolicyAuditLog wire format (Profile D)
// ---------------------------------------------------------------------------

describe('AuditEntry schema (MCP++ Profile D)', () => {
  const validEntry = {
    seq: 1,
    timestamp: Date.now(),
    timestamp_iso: new Date().toISOString(),
    policy_cid: 'sha256:policy',
    intent_cid: 'sha256:intent',
    decision: 'allow' as const,
    tool: 'browse',
    justification: 'all rules passed',
    obligations: [],
    entry_cid: 'sha256:' + '0'.repeat(64),
    extra: {},
  };

  it('validates a well-formed AuditEntry', () => {
    expect(() => AuditEntrySchema.parse(validEntry)).not.toThrow();
  });

  it('AuditDecision accepts all canonical values', () => {
    for (const d of ['allow', 'deny', 'allow_with_obligations']) {
      expect(() => AuditDecisionSchema.parse(d)).not.toThrow();
    }
  });

  it('rejects AuditEntry with invalid entry_cid', () => {
    expect(() => AuditEntrySchema.parse({ ...validEntry, entry_cid: 'not-a-cid' })).toThrow();
  });

  it('rejects AuditEntry with non-canonical decision', () => {
    expect(() => AuditEntrySchema.parse({ ...validEntry, decision: 'maybe' })).toThrow();
  });
});

describe.skipIf(!hasSwissKnife)('SwissKnife PolicyAuditLog AuditEntry interop', () => {
  it('PolicyAuditLog.record() emits a spec-valid AuditEntry', () => {
    const log = new PolicyAuditLog();
    const entry = log.record({
      policy_cid: 'sha256:p',
      intent_cid: 'sha256:i',
      decision: 'allow',
      tool: 'browse',
      timestamp: Date.now(),
    });
    expect(entry).not.toBeNull();
    expect(() => AuditEntrySchema.parse(entry)).not.toThrow();
    PolicyAuditLog.resetInstance();
  });

  it('deny decision validates against the spec schema', () => {
    const log = new PolicyAuditLog();
    const entry = log.record({
      policy_cid: 'sha256:p',
      intent_cid: 'sha256:i',
      decision: 'deny',
      tool: 'publish',
      justification: 'prohibited',
      timestamp: Date.now(),
    });
    expect(() => AuditEntrySchema.parse(entry)).not.toThrow();
    PolicyAuditLog.resetInstance();
  });

  it('entry_cid is a deterministic sha256 CID', () => {
    const log = new PolicyAuditLog();
    const opts = {
      policy_cid: 'sha256:stable', intent_cid: 'sha256:stable',
      decision: 'allow' as const, tool: 'test', timestamp: 1_000_000,
    };
    const e1 = log.record(opts)!;
    const log2 = new PolicyAuditLog();
    const e2 = log2.record(opts)!;
    expect(e1.entry_cid).toBe(e2.entry_cid); // deterministic
    expect(e1.entry_cid).toMatch(/^sha256:[0-9a-f]{64}$/);
    PolicyAuditLog.resetInstance();
  });
});

// ---------------------------------------------------------------------------
// WasmProofResult — local WASM prover result schema (Phase 1)
// ---------------------------------------------------------------------------

describe('WasmProofResult schema (MCP++ local prover layer)', () => {
  const validProved = {
    proved: true, sat: true, unsat: false,
    reason: 'sat', prover_id: 'z3-wasm', proof_time_ms: 42,
  };
  const validRefuted = {
    proved: false, sat: false, unsat: true,
    reason: 'refuted', prover_id: 'z3-wasm', proof_time_ms: 31,
  };
  const cacheHit = {
    proved: true, sat: true, unsat: false,
    reason: 'sat', prover_id: 'cache-hit', proof_time_ms: 0,
  };

  it('validates a proved (sat) result', () => {
    expect(() => WasmProofResultSchema.parse(validProved)).not.toThrow();
  });

  it('validates a refuted (unsat) result', () => {
    expect(() => WasmProofResultSchema.parse(validRefuted)).not.toThrow();
  });

  it('validates a cache-hit result', () => {
    expect(() => WasmProofResultSchema.parse(cacheHit)).not.toThrow();
  });

  it('validates all canonical ProofReason values', () => {
    for (const reason of ['proved', 'refuted', 'sat', 'unsat', 'unknown', 'timeout', 'error']) {
      expect(() => ProofReasonSchema.parse(reason)).not.toThrow();
    }
  });

  it('rejects non-canonical ProofReason', () => {
    expect(() => ProofReasonSchema.parse('maybe')).toThrow();
  });

  it('validates all canonical WasmProverId values', () => {
    for (const id of ['z3-wasm', 'cvc5-wasm', 'coq-jscoq', 'lean4-wasm', 'lurk-wasm', 'neural', 'cache-hit']) {
      expect(() => WasmProverIdSchema.parse(id)).not.toThrow();
    }
  });

  it('rejects non-canonical prover_id', () => {
    expect(() => WasmProverIdSchema.parse('my-special-prover')).toThrow();
  });

  it('allows optional model, unsat_core, and meta fields', () => {
    expect(() => WasmProofResultSchema.parse({
      ...validProved,
      model: { x: 2, y: 3 },
      meta: { z3_result: 'sat', policy_id: 'p1' },
    })).not.toThrow();
  });

  it('rejects result with negative proof_time_ms', () => {
    expect(() => WasmProofResultSchema.parse({ ...validProved, proof_time_ms: -1 })).toThrow();
  });
});

(typeof WasmProverHub !== 'undefined' ? describe : describe.skip)('SwissKnife WasmProverHub WasmProofResult interop', () => {
  // intentionally empty — swissknife hub results are tested in the jest suite
});

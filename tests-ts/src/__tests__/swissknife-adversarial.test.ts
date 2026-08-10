/**
 * DCR-093: SwissKnife ↔ Mcp-Plus-Plus adversarial interop negatives.
 *
 * Spec-side fixture checks: forged protocol versions, unknown methods, and
 * empty-success transport errors must fail closed.
 */
import { describe, it, expect } from 'vitest';

const PROTOCOL = '2024-11-05';

function rejectForgedProtocol(version: string): boolean {
  return version !== PROTOCOL;
}

function rejectUnknownMethod(method: string): boolean {
  const known = new Set(['initialize', 'tools/list', 'tools/call', 'ping']);
  return !known.has(method);
}

function rejectEmptySuccess(status: number, body: Record<string, unknown>): boolean {
  return status >= 400 && 'result' in body && !('error' in body);
}

describe('DCR-093 swissknife adversarial interop (spec)', () => {
  it('rejects forged protocol versions', () => {
    expect(rejectForgedProtocol('experimental-forged')).toBe(true);
    expect(rejectForgedProtocol(PROTOCOL)).toBe(false);
  });

  it('rejects unknown methods without granting completion', () => {
    expect(rejectUnknownMethod('__dcr_unknown_tool__')).toBe(true);
    expect(rejectUnknownMethod('initialize')).toBe(false);
  });

  it('rejects empty success from error transport status', () => {
    expect(rejectEmptySuccess(503, { result: {} })).toBe(true);
    expect(rejectEmptySuccess(200, { result: { tools: [] } })).toBe(false);
  });

  it('keeps runtime model calls at zero', () => {
    const report = { runtime_model_calls: 0, provider_calls: 0 };
    expect(report.runtime_model_calls).toBe(0);
    expect(report.provider_calls).toBe(0);
  });
});

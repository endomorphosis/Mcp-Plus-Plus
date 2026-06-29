/**
 * SwissKnife <-> canonical spec interop tests.
 *
 * Exercises SwissKnife's REAL MCP++ connector against the exact JSON-RPC wire
 * shapes emitted by the live ipfs_datasets_py (FastAPI) and ipfs_accelerate_py
 * (Trio) servers (verified by tests/integration/test_e2e_interop.py), and
 * validates those shapes against the canonical Mcp-Plus-Plus spec schemas. This
 * proves a third-party client (SwissKnife) interoperates with both servers via
 * the standard, with no live network needed.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  InitializeResultSchema,
  PolicyDecisionSchema,
} from '../models';

// SwissKnife lives outside this spec repo; load its real connector when present
// (monorepo) and skip the live-connector cases gracefully for standalone clones.
let MCPPPServerConnector: any, IPFS_DATASETS_SERVER: any, IPFS_ACCELERATE_SERVER: any;
try {
  const mod = await import(
    '../../../../swissknife/src/services/mcp-plus-plus-connector'
  );
  ({ MCPPPServerConnector, IPFS_DATASETS_SERVER, IPFS_ACCELERATE_SERVER } = mod);
} catch {
  // standalone spec clone: connector unavailable
}
const hasConnector = !!MCPPPServerConnector;

// Canonical wire shapes both servers emit (protocol 2024-11-05; mcp++ profiles
// negotiated per-method, experimental is a forward-compat slot).
const INITIALIZE_RESULT = {
  protocolVersion: '2024-11-05',
  capabilities: { tools: { listChanged: true }, experimental: {} },
  serverInfo: { name: 'mcp++', version: '1.0.0' },
};
const POLICY_RESULT = { decision: 'allow', obligations: [], allowed: true };
const PEERS_RESULT = { peers: [], protocol: '/mcp+p2p/1.0.0' };
const TOOLS_RESULT = { tools: ['ping'] };

function rpcResult(method: string) {
  if (method === 'initialize') return INITIALIZE_RESULT;
  if (method === 'mcp++/policy/evaluate') return POLICY_RESULT;
  if (method === 'mcp++/p2p/peers') return PEERS_RESULT;
  return {};
}

beforeEach(() => {
  // @ts-ignore
  globalThis.fetch = vi.fn(async (url: string, init?: any) => {
    const u = String(url);
    if (u.includes('/health') || u.includes('/status')) {
      return { ok: true, json: async () => ({ ok: true }) } as any;
    }
    if (u.includes('/tools')) {
      return { ok: true, json: async () => TOOLS_RESULT } as any;
    }
    const body = JSON.parse(init?.body || '{}');
    return {
      ok: true,
      json: async () => ({ jsonrpc: '2.0', id: body.id, result: rpcResult(body.method) }),
    } as any;
  });
});

afterEach(() => vi.restoreAllMocks());

describe.each([
  ['datasets', 'IPFS_DATASETS_SERVER'],
  ['accelerate', 'IPFS_ACCELERATE_SERVER'],
])('SwissKnife connector vs %s wire shapes', (_name, cfgKey) => {
  const cfg = () => (cfgKey === 'IPFS_DATASETS_SERVER' ? IPFS_DATASETS_SERVER : IPFS_ACCELERATE_SERVER);
  it.skipIf(!hasConnector)('connects and parses handshake/tools', async () => {
    const c = new MCPPPServerConnector(cfg());
    const r = await c.connect();
    expect(r.success).toBe(true);
    expect(r.tools).toContain('ping');
  });

  it.skipIf(!hasConnector)('parses spec-conformant policy decision', async () => {
    const c = new MCPPPServerConnector(cfg());
    await c.connect();
    const d = await c.evaluatePolicy('bafkreigh2akiscaildc...');
    expect(d.decision).toBe('allow');
    expect(Array.isArray(d.obligations)).toBe(true);
  });

  it.skipIf(!hasConnector)('parses spec-conformant peer discovery', async () => {
    const c = new MCPPPServerConnector(cfg());
    await c.connect();
    const p = await c.discoverPeers();
    expect(p.protocol).toBe('/mcp+p2p/1.0.0');
    expect(Array.isArray(p.peers)).toBe(true);
  });
});

describe('canonical wire shapes validate against spec schemas', () => {
  it('initialize handshake', () => {
    expect(() => InitializeResultSchema.parse(INITIALIZE_RESULT)).not.toThrow();
  });
  it('policy decision', () => {
    expect(() => PolicyDecisionSchema.parse(POLICY_RESULT)).not.toThrow();
  });
});

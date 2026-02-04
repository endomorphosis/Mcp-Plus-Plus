/**
 * Tests for MCP++ TypeScript Validators
 */

import { describe, it, expect } from 'vitest';
import {
  MCPTypedValidator,
  validateMCPRequest,
  validateMCPResponse,
  validateMCPNotification,
} from '../validators/baseMCP.js';
import { MCPIDLValidator } from '../validators/mcpIDL.js';
import { CIDValidator } from '../validators/cidArtifacts.js';
import { UCANValidator } from '../validators/ucanDelegation.js';
import { PolicyValidator } from '../validators/policyEvaluation.js';
import { TransportValidator } from '../validators/transport.js';
import { EventDAGValidator } from '../validators/eventDAG.js';

describe('Base MCP Validator', () => {
  const validator = new MCPTypedValidator();

  it('should validate a valid request', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'tools/call',
      params: { name: 'test_tool', arguments: {} },
      id: 1,
    };

    const result = validator.validateRequest(payload);
    expect(result.isValid).toBe(true);
    expect(result.errors).toHaveLength(0);
    expect(result.messageType).toBe('tools/call');
  });

  it('should reject request with missing jsonrpc', () => {
    const payload = {
      method: 'ping',
      id: 1,
    };

    const result = validator.validateRequest(payload);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it('should validate a valid response', () => {
    const payload = {
      jsonrpc: '2.0',
      id: 1,
      result: { success: true },
    };

    const result = validator.validateResponse(payload);
    expect(result.isValid).toBe(true);
    expect(result.metadata.hasResult).toBe(true);
  });

  it('should validate a valid notification', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'notifications/progress',
      params: { progress: 50 },
    };

    const result = validator.validateNotification(payload);
    expect(result.isValid).toBe(true);
  });

  it('should reject strict mode violations (extra fields)', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'ping',
      id: 1,
      extraField: 'not_allowed',
    };

    const result = validator.validateRequest(payload);
    expect(result.isValid).toBe(false);
  });

  it('should validate method-specific params for tools/call', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'tools/call',
      params: { name: 'calculator', arguments: { x: 10, y: 20 } },
      id: 1,
    };

    const result = validator.validateRequest(payload);
    expect(result.isValid).toBe(true);
  });

  it('should detect missing required params for tools/call', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'tools/call',
      params: { arguments: {} }, // Missing 'name'
      id: 1,
    };

    const result = validator.validateRequest(payload);
    expect(result.isValid).toBe(false);
  });
});

describe('MCP-IDL Validator', () => {
  const validator = new MCPIDLValidator();

  it('should validate a complete interface descriptor', () => {
    const descriptor = {
      name: 'Calculator',
      namespace: 'com.example',
      version: '1.0.0',
      methods: [
        {
          name: 'add',
          params: { x: 'number', y: 'number' },
          returns: { result: 'number' },
        },
      ],
      errors: [],
      requires: [],
      compatibility: { min_version: '1.0.0' },
    };

    const result = validator.validateDescriptor(descriptor);
    expect(result.isValid).toBe(true);
  });

  it('should reject descriptor with missing required fields', () => {
    const descriptor = {
      name: 'Calculator',
      namespace: 'com.example',
      // Missing version, methods, errors, compatibility
    };

    const result = validator.validateDescriptor(descriptor);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });
});

describe('CID Artifacts Validator', () => {
  const validator = new CIDValidator();

  it('should validate execution envelope with valid CIDs', () => {
    const envelope = {
      interface_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      input_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      parents: [],
      timestamp: '2024-01-01T00:00:00Z',
    };

    const result = validator.validateEnvelope(envelope);
    expect(result.isValid).toBe(true);
  });

  it('should reject envelope with invalid CID format', () => {
    const envelope = {
      interface_cid: 'invalid-cid',
      input_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      parents: [],
      timestamp: '2024-01-01T00:00:00Z',
    };

    const result = validator.validateEnvelope(envelope);
    expect(result.isValid).toBe(false);
  });

  it('should validate execution receipt', () => {
    const receipt = {
      envelope_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      output_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      success: true,
    };

    const result = validator.validateReceipt(receipt);
    expect(result.isValid).toBe(true);
  });
});

describe('UCAN Delegation Validator', () => {
  const validator = new UCANValidator();

  it('should validate UCAN token', () => {
    const token = {
      iss: 'did:key:z6Mkf...', 
      aud: 'did:key:z6Mko...',
      att: [{ can: 'file/read', with: 'ipfs://...' }],
      exp: Math.floor(Date.now() / 1000) + 3600,
    };

    const result = validator.validateToken(token);
    expect(result.isValid).toBe(true);
  });

  it('should reject token with missing required fields', () => {
    const token = {
      iss: 'did:key:z6Mkf...',
      // Missing aud, att, exp
    };

    const result = validator.validateToken(token);
    expect(result.isValid).toBe(false);
  });

  it('should validate delegation chain', () => {
    const chain = {
      root: {
        iss: 'did:key:z6Mkf...',
        aud: 'did:key:z6Mko...',
        att: [{ can: 'file/read' }],
        exp: Math.floor(Date.now() / 1000) + 3600,
      },
      chain: [],
      proof_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
    };

    const result = validator.validateChain(chain);
    expect(result.isValid).toBe(true);
  });
});

describe('Policy Evaluation Validator', () => {
  const validator = new PolicyValidator();

  it('should validate policy with all fields', () => {
    const policy = {
      policy_type: 'permission',
      action: 'file:read',
      subject: 'user:alice',
      resource: 'file:///data/report.pdf',
      temporal: {
        not_before: '2024-01-01T00:00:00Z',
        not_after: '2024-12-31T23:59:59Z',
      },
    };

    const result = validator.validatePolicy(policy);
    expect(result.isValid).toBe(true);
  });

  it('should validate policy decision', () => {
    const decision = {
      decision: 'allow',
      policy_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
    };

    const result = validator.validateDecision(decision);
    expect(result.isValid).toBe(true);
  });

  it('should validate decision with obligations', () => {
    const decision = {
      decision: 'allow_with_obligations',
      policy_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      obligations: [{ action: 'log', deadline: '2024-01-02T00:00:00Z' }],
    };

    const result = validator.validateDecision(decision);
    expect(result.isValid).toBe(true);
  });
});

describe('Transport Protocol Validator', () => {
  const validator = new TransportValidator();

  it('should validate transport message', () => {
    const message = {
      protocol_id: '/mcp+p2p/1.0.0',
      length: 100,
      payload: {
        jsonrpc: '2.0',
        method: 'ping',
        id: 1,
      },
    };

    const result = validator.validateMessage(message);
    expect(result.isValid).toBe(true);
  });

  it('should validate transport session', () => {
    const session = {
      session_id: 'session-123',
      state: 'ready',
      peer_address: '/ip4/127.0.0.1/tcp/5000',
    };

    const result = validator.validateSession(session);
    expect(result.isValid).toBe(true);
  });

  it('should reject invalid protocol ID', () => {
    const message = {
      protocol_id: '/invalid/1.0.0',
      length: 100,
      payload: {
        jsonrpc: '2.0',
        method: 'ping',
        id: 1,
      },
    };

    const result = validator.validateMessage(message);
    expect(result.isValid).toBe(false);
  });
});

describe('Event DAG Validator', () => {
  const validator = new EventDAGValidator();

  it('should validate single event', () => {
    const event = {
      event_type: 'invocation',
      event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      parents: [],
      timestamp: '2024-01-01T00:00:00Z',
      payload: { method: 'test' },
    };

    const result = validator.validateEvent(event);
    expect(result.isValid).toBe(true);
  });

  it('should validate DAG with multiple events', () => {
    const events = [
      {
        event_type: 'invocation',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
        parents: [],
        timestamp: '2024-01-01T00:00:00Z',
        payload: {},
      },
      {
        event_type: 'result',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdH',
        parents: ['QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG'],
        timestamp: '2024-01-01T00:00:01Z',
        payload: {},
      },
    ];

    const result = validator.validateDAG(events);
    expect(result.isValid).toBe(true);
    expect(result.metadata.eventCount).toBe(2);
  });
});

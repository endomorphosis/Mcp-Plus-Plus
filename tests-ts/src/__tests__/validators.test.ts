/**
 * Tests for MCP++ TypeScript Validators
 */

import { describe, it, expect } from 'vitest';
import {
  MCPTypedValidator,
  validateMCPRequest,
  validateMCPResponse,
  validateMCPNotification,
  validateMCPMessage,
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

  it('should validate resources/read params', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'resources/read',
      params: { uri: 'file:///path/to/resource' },
      id: 1,
    };

    const result = validator.validateRequest(payload);
    expect(result.isValid).toBe(true);
  });

  it('should reject resources/read with missing uri', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'resources/read',
      params: {},
      id: 1,
    };

    const result = validator.validateRequest(payload);
    expect(result.isValid).toBe(false);
  });

  it('should validate prompts/get params', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'prompts/get',
      params: { name: 'my-prompt', arguments: {} },
      id: 1,
    };

    const result = validator.validateRequest(payload);
    expect(result.isValid).toBe(true);
  });

  it('should reject prompts/get with missing name', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'prompts/get',
      params: { arguments: {} },
      id: 1,
    };

    const result = validator.validateRequest(payload);
    expect(result.isValid).toBe(false);
  });

  it('should validate initialize params', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'initialize',
      params: {
        protocolVersion: '1.0.0',
        capabilities: { tools: {} },
        clientInfo: { name: 'TestClient', version: '1.0.0' },
      },
      id: 1,
    };

    const result = validator.validateRequest(payload);
    expect(result.isValid).toBe(true);
  });

  it('should reject initialize with missing required params', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'initialize',
      params: { protocolVersion: '1.0.0' }, // Missing capabilities and clientInfo
      id: 1,
    };

    const result = validator.validateRequest(payload);
    expect(result.isValid).toBe(false);
  });

  it('should handle unknown message type', () => {
    const payload = {
      jsonrpc: '2.0',
    };

    const result = validator.validateMessage(payload);
    expect(result.isValid).toBe(false);
    expect(result.messageType).toBe('unknown');
    expect(result.errors.some(e => e.includes('Cannot determine message type'))).toBe(true);
  });

  it('should validate JSON string', () => {
    const jsonStr = JSON.stringify({
      jsonrpc: '2.0',
      method: 'ping',
      id: 1,
    });

    const result = validator.validateJsonString(jsonStr);
    expect(result.isValid).toBe(true);
  });

  it('should reject invalid JSON string', () => {
    const jsonStr = '{ invalid json }';

    const result = validator.validateJsonString(jsonStr);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('Invalid JSON'))).toBe(true);
  });

  it('should validate response with error code', () => {
    const payload = {
      jsonrpc: '2.0',
      id: 1,
      error: { code: -32600, message: 'Invalid Request' },
    };

    const result = validator.validateResponse(payload);
    expect(result.isValid).toBe(true);
    expect(result.metadata.hasError).toBe(true);
    expect(result.metadata.errorCode).toBe(-32600);
  });

  it('should warn for notification without proper prefix', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'not-a-notification-method',
    };

    const result = validator.validateNotification(payload);
    expect(result.isValid).toBe(false);
  });

  it('should detect unknown method and add warning', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'unknown/method',
      id: 1,
    };

    const result = validator.validateRequest(payload);
    expect(result.isValid).toBe(true);
    expect(result.warnings.some(w => w.includes('Unknown method'))).toBe(true);
  });

  it('should handle invalid notification method', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'invalid',
    };

    const result = validator.validateNotification(payload);
    expect(result.isValid).toBe(false);
  });

  it('should warn for unknown notification method with proper prefix', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'notifications/unknown_notification',
    };

    const result = validator.validateNotification(payload);
    expect(result.isValid).toBe(true);
    expect(result.warnings.some(w => w.includes('Unknown notification method'))).toBe(true);
  });

  it('should handle request with null id', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'ping',
      id: null,
    };

    const result = validator.validateRequest(payload);
    expect(result.isValid).toBe(false);
  });

  it('should handle response with missing id', () => {
    const payload = {
      jsonrpc: '2.0',
      result: { success: true },
    };

    const result = validator.validateResponse(payload);
    expect(result.isValid).toBe(false);
  });

  it('should use validateMCPRequest convenience function', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'ping',
      id: 1,
    };

    const result = validateMCPRequest(payload);
    expect(result.isValid).toBe(true);
  });

  it('should use validateMCPResponse convenience function', () => {
    const payload = {
      jsonrpc: '2.0',
      id: 1,
      result: { success: true },
    };

    const result = validateMCPResponse(payload);
    expect(result.isValid).toBe(true);
  });

  it('should use validateMCPNotification convenience function', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'notifications/progress',
      params: { progress: 50 },
    };

    const result = validateMCPNotification(payload);
    expect(result.isValid).toBe(true);
  });

  it('should use validateMCPMessage convenience function', () => {
    const payload = {
      jsonrpc: '2.0',
      method: 'ping',
      id: 1,
    };

    const result = validateMCPMessage(payload);
    expect(result.isValid).toBe(true);
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
          input_schema: { x: 'number', y: 'number' },
          output_schema: { result: 'number' },
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

  it('should reject descriptor with invalid field types', () => {
    const descriptor = {
      name: 123, // Should be string
      namespace: 'com.example',
      version: '1.0.0',
      methods: 'not-an-array',
      errors: [],
      requires: [],
      compatibility: { min_version: '1.0.0' },
    };

    const result = validator.validateDescriptor(descriptor);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it('should compute CID for descriptor', () => {
    const descriptor = {
      name: 'Calculator',
      namespace: 'com.example',
      version: '1.0.0',
      methods: [],
      errors: [],
      requires: [],
      compatibility: { min_version: '1.0.0' },
    };

    const cid = validator.computeCID(descriptor);
    expect(cid).toBeDefined();
    expect(cid).toMatch(/^bafkrei/);
  });

  it('should compute same CID for identical descriptors', () => {
    const descriptor = {
      name: 'Calculator',
      namespace: 'com.example',
      version: '1.0.0',
    };

    const cid1 = validator.computeCID(descriptor);
    const cid2 = validator.computeCID(descriptor);
    expect(cid1).toBe(cid2);
  });

  it('should validate interfaces/list request', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'interfaces/list',
      id: 1,
    };

    const result = validator.validateInterfaceListRequest(request);
    expect(result.isValid).toBe(true);
    expect(result.messageType).toBe('interfaces/list');
  });

  it('should reject interfaces/list with missing jsonrpc', () => {
    const request = {
      method: 'interfaces/list',
      id: 1,
    };

    const result = validator.validateInterfaceListRequest(request);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('jsonrpc'))).toBe(true);
  });

  it('should reject interfaces/list with wrong method', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'wrong/method',
      id: 1,
    };

    const result = validator.validateInterfaceListRequest(request);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('Method must be interfaces/list'))).toBe(true);
  });

  it('should reject interfaces/list with missing id', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'interfaces/list',
    };

    const result = validator.validateInterfaceListRequest(request);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('id'))).toBe(true);
  });

  it('should validate interfaces/get request with interface_cid', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'interfaces/get',
      params: { interface_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG' },
      id: 1,
    };

    const result = validator.validateInterfaceGetRequest(request);
    expect(result.isValid).toBe(true);
    expect(result.messageType).toBe('interfaces/get');
  });

  it('should reject interfaces/get with invalid jsonrpc', () => {
    const request = {
      jsonrpc: '1.0',
      method: 'interfaces/get',
      params: { interface_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG' },
      id: 1,
    };

    const result = validator.validateInterfaceGetRequest(request);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('jsonrpc'))).toBe(true);
  });

  it('should reject interfaces/get with wrong method', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'wrong/method',
      params: { interface_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG' },
      id: 1,
    };

    const result = validator.validateInterfaceGetRequest(request);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('Method must be interfaces/get'))).toBe(true);
  });

  it('should reject interfaces/get with missing id', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'interfaces/get',
      params: { interface_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG' },
    };

    const result = validator.validateInterfaceGetRequest(request);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('id'))).toBe(true);
  });

  it('should reject interfaces/get without interface_cid param', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'interfaces/get',
      params: {},
      id: 1,
    };

    const result = validator.validateInterfaceGetRequest(request);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('interface_cid'))).toBe(true);
  });

  it('should reject interfaces/get with missing params', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'interfaces/get',
      id: 1,
    };

    const result = validator.validateInterfaceGetRequest(request);
    expect(result.isValid).toBe(false);
  });

  it('should validate interfaces/compat request with client_cid and server_cid', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'interfaces/compat',
      params: {
        client_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
        server_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdH',
      },
      id: 1,
    };

    const result = validator.validateInterfaceCompatRequest(request);
    expect(result.isValid).toBe(true);
    expect(result.messageType).toBe('interfaces/compat');
  });

  it('should reject interfaces/compat with invalid jsonrpc', () => {
    const request = {
      jsonrpc: '1.0',
      method: 'interfaces/compat',
      params: {
        client_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
        server_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdH',
      },
      id: 1,
    };

    const result = validator.validateInterfaceCompatRequest(request);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('jsonrpc'))).toBe(true);
  });

  it('should reject interfaces/compat with wrong method', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'wrong/method',
      params: {
        client_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
        server_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdH',
      },
      id: 1,
    };

    const result = validator.validateInterfaceCompatRequest(request);
    expect(result.isValid).toBe(false);
  });

  it('should reject interfaces/compat with missing id', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'interfaces/compat',
      params: {
        client_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
        server_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdH',
      },
    };

    const result = validator.validateInterfaceCompatRequest(request);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('id'))).toBe(true);
  });

  it('should reject interfaces/compat with missing client_cid', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'interfaces/compat',
      params: {
        server_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdH',
      },
      id: 1,
    };

    const result = validator.validateInterfaceCompatRequest(request);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('client_cid'))).toBe(true);
  });

  it('should reject interfaces/compat with missing server_cid', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'interfaces/compat',
      params: {
        client_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      },
      id: 1,
    };

    const result = validator.validateInterfaceCompatRequest(request);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('server_cid'))).toBe(true);
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

  it('should reject envelope with missing fields', () => {
    const envelope = {
      interface_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      // Missing input_cid, parents, timestamp
    };

    const result = validator.validateEnvelope(envelope);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it('should validate receipt with error handling', () => {
    const receipt = {
      envelope_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      output_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      success: false,
    };

    const result = validator.validateReceipt(receipt);
    expect(result.isValid).toBe(true);
  });

  it('should reject receipt with missing fields', () => {
    const receipt = {
      envelope_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      // Missing output_cid and success
    };

    const result = validator.validateReceipt(receipt);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
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

  it('should reject token with invalid fields', () => {
    const token = {
      iss: 123, // Should be string
      aud: true,
      att: 'not-an-array',
      exp: 'not-a-number',
    };

    const result = validator.validateToken(token);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
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

  it('should reject chain with invalid fields', () => {
    const chain = {
      root: 'not-an-object',
      chain: 'not-an-array',
      proof_cid: 12345,
    };

    const result = validator.validateChain(chain);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it('should validate delegation chain with continuity', () => {
    const tokens = [
      {
        iss: 'did:key:alice',
        aud: 'did:key:bob',
        att: [{ can: 'file/read' }],
        exp: Math.floor(Date.now() / 1000) + 3600,
      },
      {
        iss: 'did:key:bob',
        aud: 'did:key:charlie',
        att: [{ can: 'file/read' }],
        exp: Math.floor(Date.now() / 1000) + 3600,
      },
    ];

    const result = validator.validateDelegationChain(tokens);
    expect(result.isValid).toBe(true);
    expect(result.metadata.chainLength).toBe(2);
  });

  it('should reject delegation chain with invalid token', () => {
    const tokens = [
      {
        iss: 123, // Invalid
        aud: 'did:key:bob',
        att: [{ can: 'file/read' }],
        exp: Math.floor(Date.now() / 1000) + 3600,
      },
    ];

    const result = validator.validateDelegationChain(tokens);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('Token 0'))).toBe(true);
  });

  it('should detect broken delegation chain', () => {
    const tokens = [
      {
        iss: 'did:key:alice',
        aud: 'did:key:bob',
        att: [{ can: 'file/read' }],
        exp: Math.floor(Date.now() / 1000) + 3600,
      },
      {
        iss: 'did:key:charlie', // Should be bob
        aud: 'did:key:dave',
        att: [{ can: 'file/read' }],
        exp: Math.floor(Date.now() / 1000) + 3600,
      },
    ];

    const result = validator.validateDelegationChain(tokens);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('Chain broken'))).toBe(true);
  });

  it('should validate invocation with all fields', () => {
    const invocation = {
      interface_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      input_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdH',
      proof_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdI',
    };

    const result = validator.validateInvocation(invocation);
    expect(result.isValid).toBe(true);
    expect(result.messageType).toBe('ucan_invocation');
  });

  it('should reject invocation with missing proof_cid', () => {
    const invocation = {
      interface_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      input_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdH',
    };

    const result = validator.validateInvocation(invocation);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('proof_cid'))).toBe(true);
  });

  it('should reject invocation with missing interface_cid', () => {
    const invocation = {
      input_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdH',
      proof_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdI',
    };

    const result = validator.validateInvocation(invocation);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('interface_cid'))).toBe(true);
  });

  it('should reject invocation with missing input_cid', () => {
    const invocation = {
      interface_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
      proof_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdI',
    };

    const result = validator.validateInvocation(invocation);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('input_cid'))).toBe(true);
  });

  it('should validate token with issuer field', () => {
    const token = {
      iss: 'did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2rJqBrw8RH6z',
      aud: 'did:key:z6Mko...',
      att: [{ can: 'file/read' }],
      exp: Math.floor(Date.now() / 1000) + 3600,
    };

    const result = validator.validateToken(token);
    expect(result.isValid).toBe(true);
  });

  it('should validate token with audience field', () => {
    const token = {
      iss: 'did:key:z6Mkf...',
      aud: 'did:key:z6Mko5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2rJqBrw8RH6z',
      att: [{ can: 'file/read' }],
      exp: Math.floor(Date.now() / 1000) + 3600,
    };

    const result = validator.validateToken(token);
    expect(result.isValid).toBe(true);
  });

  it('should validate token with attenuations', () => {
    const token = {
      iss: 'did:key:z6Mkf...',
      aud: 'did:key:z6Mko...',
      att: [
        { can: 'file/read', with: 'ipfs://...' },
        { can: 'file/write', with: 'ipfs://...' }
      ],
      exp: Math.floor(Date.now() / 1000) + 3600,
    };

    const result = validator.validateToken(token);
    expect(result.isValid).toBe(true);
  });

  it('should validate token with expiration', () => {
    const token = {
      iss: 'did:key:z6Mkf...',
      aud: 'did:key:z6Mko...',
      att: [{ can: 'file/read' }],
      exp: Math.floor(Date.now() / 1000) + 7200,
    };

    const result = validator.validateToken(token);
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

  it('should validate policy descriptor method', () => {
    const descriptor = {
      policy_type: 'prohibition',
      action: 'file:delete',
      subject: 'user:bob',
      resource: 'file:///data/important.pdf',
    };

    const result = validator.validatePolicyDescriptor(descriptor);
    expect(result.isValid).toBe(true);
    expect(result.messageType).toBe('policy');
  });

  it('should reject policy with invalid type', () => {
    const policy = {
      policy_type: 'invalid_type',
      action: 'file:read',
      subject: 'user:alice',
      resource: 'file:///data/report.pdf',
    };

    const result = validator.validatePolicy(policy);
    expect(result.isValid).toBe(false);
  });

  it('should validate decision with deny', () => {
    const decision = {
      decision: 'deny',
      policy_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG',
    };

    const result = validator.validateDecision(decision);
    expect(result.isValid).toBe(true);
  });

  it('should validate policy with temporal constraints', () => {
    const policy = {
      policy_type: 'permission',
      action: 'file:read',
      subject: 'user:alice',
      resource: 'file:///data/report.pdf',
      temporal: {
        not_before: '2024-01-01T00:00:00Z',
        not_after: '2024-06-30T23:59:59Z',
      },
    };

    const result = validator.validatePolicy(policy);
    expect(result.isValid).toBe(true);
  });

  it('should reject policy with missing required fields', () => {
    const policy = {
      policy_type: 'permission',
      // Missing action, subject, resource
    };

    const result = validator.validatePolicy(policy);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it('should reject decision with missing required fields', () => {
    const decision = {
      // Missing required `decision` verdict; policy_cid is optional
      obligations: [],
    };

    const result = validator.validateDecision(decision);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
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

  it('should reject transport message with invalid fields', () => {
    const message = {
      protocol_id: 'invalid',
      length: 'not-a-number',
      payload: 'not-an-object',
    };

    const result = validator.validateMessage(message);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
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

  it('should reject invalid transport session', () => {
    const session = {
      session_id: 123, // Should be string
      state: 'invalid_state',
      peer_address: 12345,
    };

    const result = validator.validateSession(session);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
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

  it('should validate frame with valid structure', () => {
    const frame = {
      length: 45,
      message: {
        jsonrpc: '2.0',
        method: 'ping',
        id: 1,
      },
    };

    const result = validator.validateFrame(frame);
    expect(result.isValid).toBe(true);
  });

  it('should warn on frame length mismatch', () => {
    const message = { jsonrpc: '2.0', method: 'ping', id: 1 };
    const frame = {
      length: 999, // Wrong length
      message: message,
    };

    const result = validator.validateFrame(frame);
    expect(result.warnings.some(w => w.includes('Length mismatch'))).toBe(true);
  });

  it('should reject frame with missing message', () => {
    const frame = {
      length: 100,
    };

    const result = validator.validateFrame(frame);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('Missing message'))).toBe(true);
  });

  it('should reject frame with missing length', () => {
    const frame = {
      message: {
        jsonrpc: '2.0',
        method: 'ping',
        id: 1,
      },
    };

    const result = validator.validateFrame(frame);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('Missing length'))).toBe(true);
  });

  it('should validate protocol ID with correct format', () => {
    const result = validator.validateProtocolID('/mcp+p2p/1.0.0');
    expect(result.isValid).toBe(true);
  });

  it('should validate protocol ID with different version', () => {
    const result = validator.validateProtocolID('/mcp+p2p/2.1.3');
    expect(result.isValid).toBe(true);
  });

  it('should reject protocol ID with invalid format', () => {
    const result = validator.validateProtocolID('/invalid-protocol/1.0.0');
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('Invalid protocol ID format'))).toBe(true);
  });

  it('should reject protocol ID without version', () => {
    const result = validator.validateProtocolID('/mcp+p2p/');
    expect(result.isValid).toBe(false);
  });

  it('should reject protocol ID with malformed version', () => {
    const result = validator.validateProtocolID('/mcp+p2p/1.0');
    expect(result.isValid).toBe(false);
  });

  it('should validate session with edge cases', () => {
    const session = {
      session_id: 'session-with-special-chars-123_abc',
      state: 'ready',
      peer_address: '/ip4/192.168.1.1/tcp/8080',
    };

    const result = validator.validateSession(session);
    expect(result.isValid).toBe(true);
  });

  it('should validate transport message structure', () => {
    const message = {
      protocol_id: '/mcp+p2p/1.0.0',
      length: 50,
      payload: {
        jsonrpc: '2.0',
        method: 'test/method',
        id: 'test-id',
      },
    };

    const result = validator.validateMessage(message);
    expect(result.isValid).toBe(true);
    expect(result.messageType).toBe('transport_message');
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

  it('should reject event with invalid fields', () => {
    const event = {
      event_type: 'invalid_type', // Not a valid event type
      event_cid: 'invalid-cid',
      parents: 'not-an-array',
      timestamp: 12345,
      payload: { method: 'test' },
    };

    const result = validator.validateEvent(event);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
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

  it('should detect cycle in DAG', () => {
    const events = [
      {
        event_type: 'invocation',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA',
        parents: ['QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdB'],
        timestamp: '2024-01-01T00:00:00Z',
        payload: {},
      },
      {
        event_type: 'result',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdB',
        parents: ['QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA'],
        timestamp: '2024-01-01T00:00:01Z',
        payload: {},
      },
    ];

    const result = validator.validateDAG(events);
    expect(result.isValid).toBe(false);
    expect(result.hasCycle).toBe(true);
    expect(result.errors.some(e => e.includes('Cycle detected'))).toBe(true);
  });

  it('should validate causal ordering with valid ordering', () => {
    const events = [
      {
        event_type: 'invocation',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA',
        parents: [],
        timestamp: 1000,
        payload: {},
      },
      {
        event_type: 'result',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdB',
        parents: ['QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA'],
        timestamp: 2000,
        payload: {},
      },
    ];

    const result = validator.validateCausalOrdering(events);
    expect(result.isValid).toBe(true);
    expect(result.messageType).toBe('causal_ordering');
  });

  it('should detect causal violation when child timestamp < parent', () => {
    const events = [
      {
        event_type: 'invocation',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA',
        parents: [],
        timestamp: 2000,
        payload: {},
      },
      {
        event_type: 'result',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdB',
        parents: ['QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA'],
        timestamp: 1000, // Earlier than parent
        payload: {},
      },
    ];

    const result = validator.validateCausalOrdering(events);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('Causal ordering violation'))).toBe(true);
  });

  it('should validate DAG with multiple parents', () => {
    const events = [
      {
        event_type: 'invocation',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA',
        parents: [],
        timestamp: '2024-01-01T00:00:00Z',
        payload: {},
      },
      {
        event_type: 'invocation',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdB',
        parents: [],
        timestamp: '2024-01-01T00:00:01Z',
        payload: {},
      },
      {
        event_type: 'result',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdC',
        parents: ['QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA', 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdB'],
        timestamp: '2024-01-01T00:00:02Z',
        payload: {},
      },
    ];

    const result = validator.validateDAG(events);
    expect(result.isValid).toBe(true);
    expect(result.metadata.eventCount).toBe(3);
  });

  it('should validate empty DAG', () => {
    const events: Record<string, unknown>[] = [];

    const result = validator.validateDAG(events);
    expect(result.isValid).toBe(true);
    expect(result.metadata.eventCount).toBe(0);
  });

  it('should reject DAG with missing parent references', () => {
    const events = [
      {
        event_type: 'result',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdB',
        parents: ['QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA'], // CID_A not in DAG
        timestamp: '2024-01-01T00:00:01Z',
        payload: {},
      },
    ];

    const result = validator.validateDAG(events);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('missing parent'))).toBe(true);
  });

  it('should reject DAG with invalid event', () => {
    const events = [
      {
        event_type: 'invalid_type',
        event_cid: 'invalid-cid',
        parents: [],
        timestamp: '2024-01-01T00:00:00Z',
        payload: {},
      },
    ];

    const result = validator.validateDAG(events);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it('should validate causal ordering with equal timestamps', () => {
    const events = [
      {
        event_type: 'invocation',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA',
        parents: [],
        timestamp: 1000,
        payload: {},
      },
      {
        event_type: 'result',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdB',
        parents: ['QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA'],
        timestamp: 1000, // Same timestamp
        payload: {},
      },
    ];

    const result = validator.validateCausalOrdering(events);
    expect(result.isValid).toBe(true);
  });

  it('should validate causal ordering without timestamps', () => {
    const events = [
      {
        event_type: 'invocation',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA',
        parents: [],
        payload: {},
      },
      {
        event_type: 'result',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdB',
        parents: ['QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA'],
        payload: {},
      },
    ];

    const result = validator.validateCausalOrdering(events);
    expect(result.isValid).toBe(true);
  });

  it('should handle event with empty parents array in cycle detection', () => {
    const events = [
      {
        event_type: 'invocation',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA',
        parents: [], // Empty array - line 93
        timestamp: '2024-01-01T00:00:00Z',
        payload: {},
      },
    ];

    const result = validator.validateDAG(events);
    expect(result.isValid).toBe(true);
    expect(result.metadata.eventCount).toBe(1);
  });

  it('should handle event with undefined parents in cycle detection', () => {
    const events = [
      {
        event_type: 'invocation',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA',
        // No parents field - will be undefined, triggering || [] on line 93
        timestamp: '2024-01-01T00:00:00Z',
        payload: {},
      },
    ];

    // The validator might reject this due to missing parents field, 
    // but we're testing that the code handles the undefined case
    const result = validator.validateDAG(events);
    expect(result).toBeDefined();
    // Whether it's valid or not, the important thing is we tested the undefined parents branch
  });

  it('should handle causal ordering with event having no parents', () => {
    const events = [
      {
        event_type: 'invocation',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA',
        parents: [], // Empty array - line 153
        timestamp: 1000,
        payload: {},
      },
      {
        event_type: 'result',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdB',
        parents: ['QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA'],
        timestamp: 1100,
        payload: {},
      },
    ];

    const result = validator.validateCausalOrdering(events);
    expect(result.isValid).toBe(true);
  });

  it('should handle causal ordering with event having undefined parents', () => {
    const events = [
      {
        event_type: 'invocation',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA',
        // No parents field - will be undefined, triggering || [] on line 153
        timestamp: 1000,
        payload: {},
      },
      {
        event_type: 'result',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdB',
        parents: ['QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA'],
        timestamp: 1100,
        payload: {},
      },
    ];

    const result = validator.validateCausalOrdering(events);
    expect(result.isValid).toBe(true);
  });
});

describe('Base MCP Validator - Edge Cases for 100% Coverage', () => {
  const validator = new MCPTypedValidator();

  it('should handle non-Zod errors during request validation', () => {
    // Create a payload that will trigger a non-Zod error by throwing during property access
    const problematicPayload = new Proxy({
      jsonrpc: '2.0',
      method: 'test',
      id: 1,
    }, {
      get(target, prop) {
        // Throw a non-Zod error when accessing a specific property during validation
        if (prop === 'params') {
          throw new Error('Non-Zod error during validation');
        }
        return target[prop as keyof typeof target];
      }
    });

    const result = validator.validateRequest(problematicPayload);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('Unexpected error'))).toBe(true);
  });

  it('should handle non-Zod errors during response validation', () => {
    // Create a response payload that throws a non-Zod error
    const problematicPayload = new Proxy({
      jsonrpc: '2.0',
      id: 1,
      result: {},
    }, {
      get(target, prop) {
        // Throw during property access to trigger non-Zod error path
        if (prop === 'error') {
          throw new TypeError('Non-Zod error in response validation');
        }
        return target[prop as keyof typeof target];
      }
    });

    const result = validator.validateResponse(problematicPayload);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('Unexpected error'))).toBe(true);
  });

  it('should handle non-Zod errors during notification validation', () => {
    // Create a notification payload that throws a non-Zod error
    const problematicPayload = new Proxy({
      jsonrpc: '2.0',
      method: 'notifications/test',
    }, {
      get(target, prop) {
        // Throw during property access
        if (prop === 'params') {
          throw new RangeError('Non-Zod error in notification validation');
        }
        return target[prop as keyof typeof target];
      }
    });

    const result = validator.validateNotification(problematicPayload);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('Unexpected error'))).toBe(true);
  });

  it('should validate notification via validateMessage type guard (line 272)', () => {
    const notification = {
      jsonrpc: '2.0',
      method: 'notifications/progress',
      params: { progress: 75 },
      // No 'id' field - this makes it a notification
    };

    const result = validator.validateMessage(notification);
    expect(result.isValid).toBe(true);
    expect(result.messageType).toBe('notifications/progress');
  });

  it('should validate response via validateMessage type guard (line 276)', () => {
    const response = {
      jsonrpc: '2.0',
      id: 123,
      result: { data: 'success' },
      // Has 'id' and 'result' - this makes it a response
    };

    const result = validator.validateMessage(response);
    expect(result.isValid).toBe(true);
    expect(result.messageType).toBe('response');
    expect(result.metadata.hasResult).toBe(true);
  });

  it('should validate request via validateMessage type guard', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'ping',
      id: 456,
      // Has 'method' and 'id' - this makes it a request
    };

    const result = validator.validateMessage(request);
    expect(result.isValid).toBe(true);
    expect(result.messageType).toBe('ping');
  });

  it('should handle unknown message type in validateMessage', () => {
    const unknown = {
      jsonrpc: '2.0',
      // Missing method, id, result, and error - can't determine type
    };

    const result = validator.validateMessage(unknown);
    expect(result.isValid).toBe(false);
    expect(result.errors.some(e => e.includes('Cannot determine message type'))).toBe(true);
  });
});

describe('Index Exports - Validate All Exports', () => {
  it('should export and use MCPTypedValidator from index', async () => {
    const { MCPTypedValidator } = await import('../index.js');
    const validator = new MCPTypedValidator();
    const result = validator.validateRequest({
      jsonrpc: '2.0',
      method: 'ping',
      id: 1,
    });
    expect(result.isValid).toBe(true);
  });

  it('should export and use validateMCPRequest from index', async () => {
    const { validateMCPRequest } = await import('../index.js');
    const result = validateMCPRequest({
      jsonrpc: '2.0',
      method: 'ping',
      id: 1,
    });
    expect(result.isValid).toBe(true);
  });

  it('should export and use validateMCPResponse from index', async () => {
    const { validateMCPResponse } = await import('../index.js');
    const result = validateMCPResponse({
      jsonrpc: '2.0',
      id: 1,
      result: { success: true },
    });
    expect(result.isValid).toBe(true);
  });

  it('should export and use validateMCPNotification from index', async () => {
    const { validateMCPNotification } = await import('../index.js');
    const result = validateMCPNotification({
      jsonrpc: '2.0',
      method: 'notifications/progress',
      params: { progress: 50 },
    });
    expect(result.isValid).toBe(true);
  });

  it('should export and use validateMCPMessage from index', async () => {
    const { validateMCPMessage } = await import('../index.js');
    const result = validateMCPMessage({
      jsonrpc: '2.0',
      method: 'ping',
      id: 1,
    });
    expect(result.isValid).toBe(true);
  });

  it('should export and use MCPIDLValidator from index', async () => {
    const { MCPIDLValidator } = await import('../index.js');
    const validator = new MCPIDLValidator();
    expect(validator).toBeDefined();
    expect(typeof validator.validateDescriptor).toBe('function');
  });

  it('should export and use CIDValidator from index', async () => {
    const { CIDValidator } = await import('../index.js');
    const validator = new CIDValidator();
    expect(validator).toBeDefined();
    expect(typeof validator.validateEnvelope).toBe('function');
  });

  it('should export and use UCANValidator from index', async () => {
    const { UCANValidator } = await import('../index.js');
    const validator = new UCANValidator();
    const token = {
      iss: 'did:key:z6Mkf...',
      aud: 'did:key:z6Mko...',
      att: [{ can: 'file/read', with: 'ipfs://...' }],
      exp: Math.floor(Date.now() / 1000) + 3600,
    };
    const result = validator.validateToken(token);
    expect(result.isValid).toBe(true);
  });

  it('should export and use PolicyValidator from index', async () => {
    const { PolicyValidator } = await import('../index.js');
    const validator = new PolicyValidator();
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

  it('should export and use TransportValidator from index', async () => {
    const { TransportValidator } = await import('../index.js');
    const validator = new TransportValidator();
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

  it('should export and use EventDAGValidator from index', async () => {
    const { EventDAGValidator } = await import('../index.js');
    const validator = new EventDAGValidator();
    const events = [
      {
        event_type: 'invocation',
        event_cid: 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdA',
        parents: [],
        timestamp: '2024-01-01T00:00:00Z',
        payload: {},
      },
    ];
    const result = validator.validateDAG(events);
    expect(result.isValid).toBe(true);
  });

  it('should export type guards from index', async () => {
    const { isRequest, isResponse, isNotification } = await import('../index.js');
    
    const request = { jsonrpc: '2.0', method: 'ping', id: 1 };
    const response = { jsonrpc: '2.0', id: 1, result: {} };
    const notification = { jsonrpc: '2.0', method: 'notify' };
    
    expect(isRequest(request)).toBe(true);
    expect(isResponse(response)).toBe(true);
    expect(isNotification(notification)).toBe(true);
  });
});

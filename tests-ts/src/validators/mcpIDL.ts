/**
 * MCP-IDL Validator (TypeScript)
 * Profile A: Interface Descriptors with CID computation
 */

import { ZodError } from 'zod';
import { InterfaceDescriptorSchema } from '../models.js';

export interface ValidationResult {
  isValid: boolean;
  messageType: string;
  errors: string[];
  warnings: string[];
  metadata: Record<string, unknown>;
}

export class MCPIDLValidator {
  validateDescriptor(descriptor: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'interface_descriptor',
      errors: [],
      warnings: [],
      metadata: {},
    };

    try {
      InterfaceDescriptorSchema.parse(descriptor);
    } catch (error) {
      if (error instanceof ZodError) {
        result.isValid = false;
        error.issues.forEach((issue) => {
          const path = issue.path.join('.');
          result.errors.push(`${path}: ${issue.message}`);
        });
      }
    }

    return result;
  }

  computeCID(descriptor: Record<string, unknown>): string {
    // Deterministic CID computation (simplified - in production use proper IPLD)
    const normalized = JSON.stringify(descriptor, Object.keys(descriptor).sort());
    let hash = 0;
    for (let i = 0; i < normalized.length; i++) {
      const char = normalized.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    return `bafkrei${Math.abs(hash).toString(36)}`;
  }

  validateInterfaceListRequest(request: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'interfaces/list',
      errors: [],
      warnings: [],
      metadata: {},
    };

    if (!request.jsonrpc || request.jsonrpc !== '2.0') {
      result.isValid = false;
      result.errors.push('Missing or invalid jsonrpc field');
    }

    if (request.method !== 'interfaces/list') {
      result.isValid = false;
      result.errors.push('Method must be interfaces/list');
    }

    if (!request.id) {
      result.isValid = false;
      result.errors.push('Missing id field');
    }

    return result;
  }

  validateInterfaceGetRequest(request: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'interfaces/get',
      errors: [],
      warnings: [],
      metadata: {},
    };

    if (!request.jsonrpc || request.jsonrpc !== '2.0') {
      result.isValid = false;
      result.errors.push('Missing or invalid jsonrpc field');
    }

    if (request.method !== 'interfaces/get') {
      result.isValid = false;
      result.errors.push('Method must be interfaces/get');
    }

    if (!request.id) {
      result.isValid = false;
      result.errors.push('Missing id field');
    }

    const params = request.params as Record<string, unknown>;
    if (!params || !params.interface_cid) {
      result.isValid = false;
      result.errors.push('Missing interface_cid in params');
    }

    return result;
  }

  validateInterfaceCompatRequest(request: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'interfaces/compat',
      errors: [],
      warnings: [],
      metadata: {},
    };

    if (!request.jsonrpc || request.jsonrpc !== '2.0') {
      result.isValid = false;
      result.errors.push('Missing or invalid jsonrpc field');
    }

    if (request.method !== 'interfaces/compat') {
      result.isValid = false;
      result.errors.push('Method must be interfaces/compat');
    }

    if (!request.id) {
      result.isValid = false;
      result.errors.push('Missing id field');
    }

    const params = request.params as Record<string, unknown>;
    if (!params || !params.client_cid || !params.server_cid) {
      result.isValid = false;
      result.errors.push('Missing client_cid or server_cid in params');
    }

    return result;
  }
}

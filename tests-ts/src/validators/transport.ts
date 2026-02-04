/**
 * Transport Protocol Validator (TypeScript)
 * Profile E: mcp+p2p transport layer
 */

import { ZodError } from 'zod';
import { TransportMessageSchema, TransportSessionSchema } from '../models.js';

export interface ValidationResult {
  isValid: boolean;
  messageType: string;
  errors: string[];
  warnings: string[];
  metadata: Record<string, unknown>;
}

export class TransportValidator {
  validateMessage(message: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'transport_message',
      errors: [],
      warnings: [],
      metadata: {},
    };

    try {
      TransportMessageSchema.parse(message);
    } catch (error) {
      if (error instanceof ZodError) {
        result.isValid = false;
        error.issues.forEach((issue) => {
          result.errors.push(`${issue.path.join('.')}: ${issue.message}`);
        });
      }
    }

    return result;
  }

  validateSession(session: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'transport_session',
      errors: [],
      warnings: [],
      metadata: {},
    };

    try {
      TransportSessionSchema.parse(session);
    } catch (error) {
      if (error instanceof ZodError) {
        result.isValid = false;
        error.issues.forEach((issue) => {
          result.errors.push(`${issue.path.join('.')}: ${issue.message}`);
        });
      }
    }

    return result;
  }

  validateProtocolID(protocolID: string): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'protocol_id',
      errors: [],
      warnings: [],
      metadata: {},
    };

    const expectedPattern = /^\/mcp\+p2p\/\d+\.\d+\.\d+$/;
    if (!expectedPattern.test(protocolID)) {
      result.isValid = false;
      result.errors.push(
        `Invalid protocol ID format. Expected /mcp+p2p/X.Y.Z, got: ${protocolID}`
      );
    }

    return result;
  }

  validateFrame(frame: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'transport_frame',
      errors: [],
      warnings: [],
      metadata: {},
    };

    if (!frame.length) {
      result.isValid = false;
      result.errors.push('Missing length field');
    }

    if (!frame.message) {
      result.isValid = false;
      result.errors.push('Missing message field');
    }

    // Check length matches message size
    if (frame.message && frame.length) {
      const messageStr = JSON.stringify(frame.message);
      const actualLength = messageStr.length;
      if (actualLength !== frame.length) {
        result.warnings.push(
          `Length mismatch: declared ${frame.length}, actual ${actualLength}`
        );
      }
    }

    return result;
  }
}

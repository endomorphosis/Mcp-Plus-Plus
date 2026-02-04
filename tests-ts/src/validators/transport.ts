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
}

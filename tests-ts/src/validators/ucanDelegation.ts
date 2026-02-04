/**
 * UCAN Delegation Validator (TypeScript)
 * Profile C: UCAN delegation chains
 */

import { ZodError } from 'zod';
import { UCANTokenSchema, DelegationChainSchema } from '../models.js';

export interface ValidationResult {
  isValid: boolean;
  messageType: string;
  errors: string[];
  warnings: string[];
  metadata: Record<string, unknown>;
}

export class UCANValidator {
  validateToken(token: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'ucan_token',
      errors: [],
      warnings: [],
      metadata: {},
    };

    try {
      UCANTokenSchema.parse(token);
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

  validateChain(chain: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'delegation_chain',
      errors: [],
      warnings: [],
      metadata: {},
    };

    try {
      DelegationChainSchema.parse(chain);
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

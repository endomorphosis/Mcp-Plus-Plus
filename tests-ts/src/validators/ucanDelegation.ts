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

  validateDelegationChain(tokens: Record<string, unknown>[]): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'delegation_chain',
      errors: [],
      warnings: [],
      metadata: { chainLength: tokens.length },
    };

    // Validate each token
    for (let i = 0; i < tokens.length; i++) {
      const tokenResult = this.validateToken(tokens[i]);
      if (!tokenResult.isValid) {
        result.isValid = false;
        result.errors.push(`Token ${i}: ${tokenResult.errors.join(', ')}`);
      }
    }

    // Check chain continuity (aud of token[i] should match iss of token[i+1])
    for (let i = 0; i < tokens.length - 1; i++) {
      const currentAud = tokens[i].aud;
      const nextIss = tokens[i + 1].iss;
      if (currentAud !== nextIss) {
        result.isValid = false;
        result.errors.push(
          `Chain broken between token ${i} and ${i + 1}: ` +
          `aud(${currentAud}) != iss(${nextIss})`
        );
      }
    }

    return result;
  }

  validateInvocation(invocation: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'ucan_invocation',
      errors: [],
      warnings: [],
      metadata: {},
    };

    // Check required fields
    if (!invocation.interface_cid) {
      result.isValid = false;
      result.errors.push('Missing interface_cid');
    }

    if (!invocation.input_cid) {
      result.isValid = false;
      result.errors.push('Missing input_cid');
    }

    if (!invocation.proof_cid) {
      result.isValid = false;
      result.errors.push('Missing proof_cid for invocation');
    }

    return result;
  }
}

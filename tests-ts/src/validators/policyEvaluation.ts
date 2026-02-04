/**
 * Policy Evaluation Validator (TypeScript)
 * Profile D: Temporal deontic policies
 */

import { ZodError } from 'zod';
import { PolicySchema, PolicyDecisionSchema } from '../models.js';

export interface ValidationResult {
  isValid: boolean;
  messageType: string;
  errors: string[];
  warnings: string[];
  metadata: Record<string, unknown>;
}

export class PolicyValidator {
  validatePolicy(policy: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'policy',
      errors: [],
      warnings: [],
      metadata: {},
    };

    try {
      PolicySchema.parse(policy);
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

  validateDecision(decision: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'policy_decision',
      errors: [],
      warnings: [],
      metadata: {},
    };

    try {
      PolicyDecisionSchema.parse(decision);
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

  validatePolicyDescriptor(descriptor: Record<string, unknown>): ValidationResult {
    // Alias for validatePolicy
    return this.validatePolicy(descriptor);
  }
}

/**
 * CID Artifacts Validator (TypeScript)
 * Profile B: Execution envelopes and receipts
 */

import { ZodError } from 'zod';
import { ExecutionEnvelopeSchema, ExecutionReceiptSchema } from '../models.js';

export interface ValidationResult {
  isValid: boolean;
  messageType: string;
  errors: string[];
  warnings: string[];
  metadata: Record<string, unknown>;
}

export class CIDValidator {
  validateEnvelope(envelope: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'execution_envelope',
      errors: [],
      warnings: [],
      metadata: {},
    };

    try {
      ExecutionEnvelopeSchema.parse(envelope);
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

  validateReceipt(receipt: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'execution_receipt',
      errors: [],
      warnings: [],
      metadata: {},
    };

    try {
      ExecutionReceiptSchema.parse(receipt);
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

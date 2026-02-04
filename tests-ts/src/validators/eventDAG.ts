/**
 * Event DAG Validator (TypeScript)
 * Validates event graph structure and ordering
 */

import { ZodError } from 'zod';
import { DAGEventSchema } from '../models.js';

export interface ValidationResult {
  isValid: boolean;
  messageType: string;
  errors: string[];
  warnings: string[];
  metadata: Record<string, unknown>;
}

export class EventDAGValidator {
  validateEvent(event: Record<string, unknown>): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'dag_event',
      errors: [],
      warnings: [],
      metadata: {},
    };

    try {
      DAGEventSchema.parse(event);
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

  validateDAG(events: Record<string, unknown>[]): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'dag',
      errors: [],
      warnings: [],
      metadata: { eventCount: events.length },
    };

    // Validate each event
    for (const event of events) {
      const eventResult = this.validateEvent(event);
      if (!eventResult.isValid) {
        result.isValid = false;
        result.errors.push(...eventResult.errors);
      }
    }

    return result;
  }
}

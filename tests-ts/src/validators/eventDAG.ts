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

  validateDAG(events: Record<string, unknown>[]): ValidationResult & { hasCycle?: boolean } {
    const result: ValidationResult & { hasCycle?: boolean } = {
      isValid: true,
      messageType: 'dag',
      errors: [],
      warnings: [],
      metadata: { eventCount: events.length },
      hasCycle: false,
    };

    // Validate each event
    for (const event of events) {
      const eventResult = this.validateEvent(event);
      if (!eventResult.isValid) {
        result.isValid = false;
        result.errors.push(...eventResult.errors);
      }
    }

    // Check for missing parent references
    const eventCids = new Set(events.map(e => e.event_cid));
    for (const event of events) {
      const parents = event.parents as string[];
      if (parents) {
        for (const parent of parents) {
          if (!eventCids.has(parent)) {
            result.isValid = false;
            result.errors.push(`Event ${event.event_cid} references missing parent: ${parent}`);
          }
        }
      }
    }

    // Check for cycles using DFS
    const hasCycle = this.detectCycle(events);
    if (hasCycle) {
      result.isValid = false;
      result.hasCycle = true;
      result.errors.push('Cycle detected in DAG');
    }

    return result;
  }

  private detectCycle(events: Record<string, unknown>[]): boolean {
    const graph = new Map<string, string[]>();
    const visited = new Set<string>();
    const recursionStack = new Set<string>();

    // Build adjacency list
    for (const event of events) {
      const cid = event.event_cid as string;
      const parents = (event.parents as string[]) || [];
      graph.set(cid, parents);
    }

    const dfs = (node: string): boolean => {
      if (recursionStack.has(node)) {
        return true; // Cycle detected
      }
      if (visited.has(node)) {
        return false;
      }

      visited.add(node);
      recursionStack.add(node);

      const parents = graph.get(node) || [];
      for (const parent of parents) {
        if (dfs(parent)) {
          return true;
        }
      }

      recursionStack.delete(node);
      return false;
    };

    for (const event of events) {
      const cid = event.event_cid as string;
      if (!visited.has(cid)) {
        if (dfs(cid)) {
          return true;
        }
      }
    }

    return false;
  }

  validateCausalOrdering(events: Record<string, unknown>[]): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      messageType: 'causal_ordering',
      errors: [],
      warnings: [],
      metadata: {},
    };

    const timestamps = new Map<string, number>();
    for (const event of events) {
      const cid = event.event_cid as string;
      const timestamp = event.timestamp as number;
      if (timestamp !== undefined) {
        timestamps.set(cid, timestamp);
      }
    }

    // Check that children have timestamps >= parents
    for (const event of events) {
      const cid = event.event_cid as string;
      const timestamp = timestamps.get(cid);
      const parents = (event.parents as string[]) || [];

      if (timestamp !== undefined) {
        for (const parent of parents) {
          const parentTimestamp = timestamps.get(parent);
          if (parentTimestamp !== undefined && timestamp < parentTimestamp) {
            result.isValid = false;
            result.errors.push(
              `Causal ordering violation: ${cid} (${timestamp}) < ${parent} (${parentTimestamp})`
            );
          }
        }
      }
    }

    return result;
  }
}

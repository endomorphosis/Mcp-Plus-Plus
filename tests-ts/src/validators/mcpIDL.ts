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
}

/**
 * Base MCP Protocol Validator (TypeScript)
 * 
 * Provides strict runtime type validation using Zod schemas.
 * Parallel implementation to Python Pydantic validators.
 */

import { ZodError, ZodIssue } from 'zod';
import {
  JSONRPCRequestSchema,
  JSONRPCResponseSchema,
  JSONRPCNotificationSchema,
  InitializeParamsSchema,
  ToolCallParamsSchema,
  ResourceReadParamsSchema,
  PromptGetParamsSchema,
  type JSONRPCRequest,
  type JSONRPCResponse,
  type JSONRPCNotification,
} from '../models.js';

/**
 * Result of a validation check.
 */
export interface ValidationResult {
  isValid: boolean;
  messageType: string;
  errors: string[];
  warnings: string[];
  metadata: Record<string, unknown>;
}

/**
 * Creates a new validation result.
 */
function createValidationResult(
  messageType: string = '',
  isValid: boolean = true
): ValidationResult {
  return {
    isValid,
    messageType,
    errors: [],
    warnings: [],
    metadata: {},
  };
}

/**
 * Adds an error to the validation result.
 */
function addError(result: ValidationResult, error: string): void {
  result.errors.push(error);
  result.isValid = false;
}

/**
 * Adds a warning to the validation result.
 */
function addWarning(result: ValidationResult, warning: string): void {
  result.warnings.push(warning);
}

/**
 * Formats Zod errors into readable strings.
 */
function formatZodError(issue: ZodIssue): string {
  const path = issue.path.join('.');
  return `${path}: ${issue.message}`;
}

/**
 * Type guard to check if payload is a request.
 */
export function isRequest(payload: Record<string, unknown>): payload is JSONRPCRequest {
  const method = payload['method'];
  const id = payload['id'];
  return (
    typeof method === 'string' &&
    id !== undefined &&
    !method.startsWith('notifications/')
  );
}

/**
 * Type guard to check if payload is a response.
 */
export function isResponse(payload: Record<string, unknown>): payload is JSONRPCResponse {
  return (payload['result'] !== undefined || payload['error'] !== undefined) && payload['id'] !== undefined;
}

/**
 * Type guard to check if payload is a notification.
 */
export function isNotification(payload: Record<string, unknown>): payload is JSONRPCNotification {
  return payload['method'] !== undefined && payload['id'] === undefined;
}

/**
 * Type-safe validator for baseline MCP protocol messages.
 * 
 * Uses Zod schemas for runtime validation and provides
 * type guards for static type checking with TypeScript.
 * 
 * Based on the official MCP specification:
 * https://modelcontextprotocol.io/docs/
 */
export class MCPTypedValidator {
  /**
   * Valid MCP methods (comprehensive list).
   */
  private static readonly VALID_METHODS: ReadonlySet<string> = new Set([
    // Lifecycle
    'initialize',
    'initialized',
    'ping',
    // Capabilities
    'capabilities/list',
    // Tools
    'tools/list',
    'tools/call',
    // Resources
    'resources/list',
    'resources/read',
    'resources/subscribe',
    'resources/unsubscribe',
    'resources/templates/list',
    // Prompts
    'prompts/list',
    'prompts/get',
    // Notifications
    'notifications/resources/updated',
    'notifications/resources/list_changed',
    'notifications/tools/list_changed',
    'notifications/prompts/list_changed',
    'notifications/progress',
  ]);

  /**
   * Validates an MCP request message with Zod schemas.
   */
  validateRequest(payload: Record<string, unknown>): ValidationResult {
    const result = createValidationResult('request');

    try {
      const request = JSONRPCRequestSchema.parse(payload);
      result.messageType = request.method;

      // Check if method is known
      if (!MCPTypedValidator.VALID_METHODS.has(request.method)) {
        addWarning(result, `Unknown method: ${request.method}`);
      }

      // Validate method-specific parameters
      if (request.params) {
        this.validateMethodParamsTyped(request.method, request.params, result);
      }
    } catch (error) {
      if (error instanceof ZodError) {
        result.isValid = false;
        error.issues.forEach((issue) => {
          addError(result, formatZodError(issue));
        });
      } else {
        result.isValid = false;
        addError(result, `Unexpected error: ${error}`);
      }
    }

    return result;
  }

  /**
   * Validates an MCP response message with Zod schemas.
   */
  validateResponse(payload: Record<string, unknown>): ValidationResult {
    const result = createValidationResult('response');

    try {
      const response = JSONRPCResponseSchema.parse(payload);

      // Additional validation is handled by Zod schema refinements
      if (response.error) {
        result.metadata['hasError'] = true;
        result.metadata['errorCode'] = response.error.code;
      } else {
        result.metadata['hasResult'] = true;
      }
    } catch (error) {
      if (error instanceof ZodError) {
        result.isValid = false;
        error.issues.forEach((issue) => {
          addError(result, formatZodError(issue));
        });
      } else {
        result.isValid = false;
        addError(result, `Unexpected error: ${error}`);
      }
    }

    return result;
  }

  /**
   * Validates an MCP notification message with Zod schemas.
   */
  validateNotification(payload: Record<string, unknown>): ValidationResult {
    const result = createValidationResult('notification');

    try {
      const notification = JSONRPCNotificationSchema.parse(payload);
      result.messageType = notification.method;

      // Check if it's a valid notification method
      if (!MCPTypedValidator.VALID_METHODS.has(notification.method)) {
        addWarning(result, `Unknown notification method: ${notification.method}`);
      }
    } catch (error) {
      if (error instanceof ZodError) {
        result.isValid = false;
        error.issues.forEach((issue) => {
          addError(result, formatZodError(issue));
        });
      } else {
        result.isValid = false;
        addError(result, `Unexpected error: ${error}`);
      }
    }

    return result;
  }

  /**
   * Validates method-specific parameters using Zod schemas.
   */
  private validateMethodParamsTyped(
    method: string,
    params: Record<string, unknown>,
    result: ValidationResult
  ): void {
    try {
      switch (method) {
        case 'tools/call':
          ToolCallParamsSchema.parse(params);
          break;
        case 'resources/read':
          ResourceReadParamsSchema.parse(params);
          break;
        case 'prompts/get':
          PromptGetParamsSchema.parse(params);
          break;
        case 'initialize':
          InitializeParamsSchema.parse(params);
          break;
      }
    } catch (error) {
      if (error instanceof ZodError) {
        error.issues.forEach((issue) => {
          const path = issue.path.join('.');
          addError(result, `params.${path}: ${issue.message}`);
        });
      }
    }
  }

  /**
   * Validates any MCP message (auto-detect type) with type guards.
   */
  validateMessage(payload: Record<string, unknown>): ValidationResult {
    // Use type guards to determine message type
    if (isNotification(payload)) {
      return this.validateNotification(payload);
    } else if (isRequest(payload)) {
      return this.validateRequest(payload);
    } else if (isResponse(payload)) {
      return this.validateResponse(payload);
    } else {
      const result = createValidationResult('unknown', false);
      addError(result, 'Cannot determine message type');
      return result;
    }
  }

  /**
   * Validates a JSON string as an MCP message.
   */
  validateJsonString(jsonStr: string): ValidationResult {
    try {
      const payload = JSON.parse(jsonStr) as Record<string, unknown>;
      return this.validateMessage(payload);
    } catch (error) {
      const result = createValidationResult('', false);
      addError(result, `Invalid JSON: ${error}`);
      return result;
    }
  }
}

// Convenience functions for one-off validations

/**
 * Validates an MCP request (convenience function).
 */
export function validateMCPRequest(payload: Record<string, unknown>): ValidationResult {
  const validator = new MCPTypedValidator();
  return validator.validateRequest(payload);
}

/**
 * Validates an MCP response (convenience function).
 */
export function validateMCPResponse(payload: Record<string, unknown>): ValidationResult {
  const validator = new MCPTypedValidator();
  return validator.validateResponse(payload);
}

/**
 * Validates an MCP notification (convenience function).
 */
export function validateMCPNotification(payload: Record<string, unknown>): ValidationResult {
  const validator = new MCPTypedValidator();
  return validator.validateNotification(payload);
}

/**
 * Validates any MCP message (convenience function).
 */
export function validateMCPMessage(payload: Record<string, unknown>): ValidationResult {
  const validator = new MCPTypedValidator();
  return validator.validateMessage(payload);
}

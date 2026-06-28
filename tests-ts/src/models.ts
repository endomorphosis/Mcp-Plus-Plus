/**
 * MCP Protocol Models with Zod Runtime Validation
 * 
 * Provides strict runtime type validation using Zod.
 * These schemas enforce the MCP protocol specifications with
 * compile-time TypeScript types and runtime validation.
 */

import { z } from 'zod';

// ============================================================================
// Base JSON-RPC Models
// ============================================================================

export const JSONRPCVersionSchema = z.literal('2.0');
export type JSONRPCVersion = z.infer<typeof JSONRPCVersionSchema>;

export const JSONRPCErrorSchema = z.object({
  code: z.number().int(),
  message: z.string(),
  data: z.record(z.any()).optional(),
}).strict();
export type JSONRPCError = z.infer<typeof JSONRPCErrorSchema>;

export const JSONRPCRequestSchema = z.object({
  jsonrpc: JSONRPCVersionSchema,
  method: z.string().min(1),
  params: z.record(z.any()).optional().default({}),
  id: z.union([z.string(), z.number()]),
}).strict();
export type JSONRPCRequest = z.infer<typeof JSONRPCRequestSchema>;

export const JSONRPCNotificationSchema = z.object({
  jsonrpc: JSONRPCVersionSchema,
  method: z.string().regex(/^notifications\//),
  params: z.record(z.any()).optional().default({}),
}).strict();
export type JSONRPCNotification = z.infer<typeof JSONRPCNotificationSchema>;

export const JSONRPCResponseSchema = z.object({
  jsonrpc: JSONRPCVersionSchema,
  id: z.union([z.string(), z.number()]),
  result: z.any().optional(),
  error: JSONRPCErrorSchema.optional(),
}).strict().refine(
  (data) => {
    const hasResult = data.result !== undefined;
    const hasError = data.error !== undefined;
    return (hasResult && !hasError) || (!hasResult && hasError);
  },
  {
    message: "Response must have exactly one of 'result' or 'error'",
  }
);
export type JSONRPCResponse = z.infer<typeof JSONRPCResponseSchema>;

// ============================================================================
// MCP Protocol Models
// ============================================================================

export const ClientInfoSchema = z.object({
  name: z.string().min(1),
  version: z.string().min(1),
}).passthrough(); // Allow additional properties
export type ClientInfo = z.infer<typeof ClientInfoSchema>;

export const ServerInfoSchema = z.object({
  name: z.string().min(1),
  version: z.string().min(1),
}).passthrough();
export type ServerInfo = z.infer<typeof ServerInfoSchema>;

export const CapabilitiesSchema = z.object({
  tools: z.record(z.any()).optional(),
  resources: z.record(z.any()).optional(),
  prompts: z.record(z.any()).optional(),
}).passthrough();
export type Capabilities = z.infer<typeof CapabilitiesSchema>;

export const InitializeParamsSchema = z.object({
  protocolVersion: z.string(),
  capabilities: CapabilitiesSchema,
  clientInfo: ClientInfoSchema,
}).passthrough();
export type InitializeParams = z.infer<typeof InitializeParamsSchema>;

export const ToolCallParamsSchema = z.object({
  name: z.string().min(1),
  arguments: z.record(z.any()).default({}),
}).strict();
export type ToolCallParams = z.infer<typeof ToolCallParamsSchema>;

export const ResourceReadParamsSchema = z.object({
  uri: z.string().min(1),
}).strict();
export type ResourceReadParams = z.infer<typeof ResourceReadParamsSchema>;

export const PromptGetParamsSchema = z.object({
  name: z.string().min(1),
  arguments: z.record(z.any()).optional().default({}),
}).strict();
export type PromptGetParams = z.infer<typeof PromptGetParamsSchema>;

// ============================================================================
// MCP-IDL (Profile A) Models
// ============================================================================

export const MethodDescriptorSchema = z.object({
  name: z.string().min(1),
  params: z.record(z.any()),
  returns: z.record(z.any()),
  description: z.string().optional(),
}).passthrough();
export type MethodDescriptor = z.infer<typeof MethodDescriptorSchema>;

export const ErrorDescriptorSchema = z.object({
  code: z.number().int(),
  message: z.string().min(1),
  data_schema: z.record(z.any()).optional(),
}).passthrough();
export type ErrorDescriptor = z.infer<typeof ErrorDescriptorSchema>;

export const InterfaceDescriptorSchema = z.object({
  name: z.string().min(1),
  namespace: z.string().min(1),
  version: z.string().min(1),
  methods: z.array(MethodDescriptorSchema).min(1),
  errors: z.array(ErrorDescriptorSchema),
  requires: z.array(z.string()).default([]),
  compatibility: z.record(z.any()),
  semantic_tags: z.array(z.string()).optional(),
  observability: z.record(z.any()).optional(),
  interaction_patterns: z.array(z.string()).optional(),
  resource_cost_hints: z.record(z.any()).optional(),
}).passthrough();
export type InterfaceDescriptor = z.infer<typeof InterfaceDescriptorSchema>;

// ============================================================================
// CID Artifacts (Profile B) Models
// ============================================================================

const CIDPattern = /^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$/;

export const ExecutionEnvelopeSchema = z.object({
  interface_cid: z.string().regex(CIDPattern),
  input_cid: z.string().regex(CIDPattern),
  parents: z.array(z.string()),
  timestamp: z.string(), // ISO 8601
  metadata: z.record(z.any()).optional(),
}).strict();
export type ExecutionEnvelope = z.infer<typeof ExecutionEnvelopeSchema>;

export const ExecutionReceiptSchema = z.object({
  envelope_cid: z.string().regex(CIDPattern),
  output_cid: z.string().regex(CIDPattern),
  success: z.boolean(),
  decision_cid: z.string().regex(CIDPattern).optional(),
  signature: z.string().optional(),
}).strict();
export type ExecutionReceipt = z.infer<typeof ExecutionReceiptSchema>;

// ============================================================================
// UCAN Delegation (Profile C) Models
// ============================================================================

export const UCANTokenSchema = z.object({
  iss: z.string().min(1),
  aud: z.string().min(1),
  att: z.array(z.record(z.any())).min(1),
  exp: z.number().int().positive(),
  prf: z.array(z.string()).optional(),
}).passthrough();
export type UCANToken = z.infer<typeof UCANTokenSchema>;

export const DelegationChainSchema = z.object({
  root: UCANTokenSchema,
  chain: z.array(UCANTokenSchema).default([]),
  proof_cid: z.string().regex(CIDPattern),
}).strict();
export type DelegationChain = z.infer<typeof DelegationChainSchema>;

// ============================================================================
// Policy Evaluation (Profile D) Models
// ============================================================================

export const PolicyTypeSchema = z.enum(['permission', 'prohibition', 'obligation']);
export type PolicyType = z.infer<typeof PolicyTypeSchema>;

export const DecisionTypeSchema = z.enum(['allow', 'deny', 'allow_with_obligations']);
export type DecisionType = z.infer<typeof DecisionTypeSchema>;

export const TemporalConstraintSchema = z.object({
  not_before: z.string().optional(), // ISO 8601
  not_after: z.string().optional(), // ISO 8601
  duration: z.string().optional(), // ISO 8601 duration
}).strict();
export type TemporalConstraint = z.infer<typeof TemporalConstraintSchema>;

export const PolicySchema = z.object({
  policy_type: PolicyTypeSchema,
  action: z.string().min(1),
  subject: z.string().optional(),
  resource: z.string().optional(),
  temporal: TemporalConstraintSchema.optional(),
  conditions: z.record(z.any()).optional(),
}).passthrough();
export type Policy = z.infer<typeof PolicySchema>;

export const PolicyDecisionSchema = z.object({
  decision: DecisionTypeSchema,
  policy_cid: z.string().regex(CIDPattern),
  obligations: z.array(z.record(z.any())).optional(),
  witness: z.record(z.any()).optional(),
}).strict();
export type PolicyDecision = z.infer<typeof PolicyDecisionSchema>;

// ============================================================================
// Event DAG Models
// ============================================================================

export const EventTypeSchema = z.enum([
  'invocation',
  'result',
  'error',
  'delegation',
  'policy_decision',
]);
export type EventType = z.infer<typeof EventTypeSchema>;

export const DAGEventSchema = z.object({
  event_type: EventTypeSchema,
  event_cid: z.string().regex(CIDPattern),
  parents: z.array(z.string()),
  timestamp: z.string(), // ISO 8601
  payload: z.record(z.any()),
}).passthrough();
export type DAGEvent = z.infer<typeof DAGEventSchema>;

// ============================================================================
// Transport (Profile E) Models
// ============================================================================

export const TransportProtocolSchema = z.literal('/mcp+p2p/1.0.0');
export type TransportProtocol = z.infer<typeof TransportProtocolSchema>;

export const TransportMessageSchema = z.object({
  protocol_id: TransportProtocolSchema,
  length: z.number().int().positive(),
  payload: z.union([JSONRPCRequestSchema, JSONRPCResponseSchema, JSONRPCNotificationSchema]),
}).strict();
export type TransportMessage = z.infer<typeof TransportMessageSchema>;

export const SessionStateSchema = z.enum([
  'connection',
  'stream',
  'initialization',
  'ready',
  'closed',
]);
export type SessionState = z.infer<typeof SessionStateSchema>;

export const TransportSessionSchema = z.object({
  session_id: z.string().min(1),
  state: SessionStateSchema,
  peer_address: z.string(),
  capabilities: z.record(z.any()).optional(),
}).passthrough();
export type TransportSession = z.infer<typeof TransportSessionSchema>;

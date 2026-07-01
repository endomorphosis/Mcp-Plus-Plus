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

// Canonical JSON-RPC error codes used by MCP++ servers. Meanings are normative.
export enum ErrorCode {
  ParseError = -32700,
  InvalidRequest = -32600,
  MethodNotFound = -32601,
  InvalidParams = -32602,
  InternalError = -32603,
  ServerError = -32000,
}
export const CANONICAL_ERROR_CODES: number[] = [-32700, -32600, -32601, -32602, -32603, -32000];

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

// Server -> client handshake result. mcp++ profiles negotiated under
// capabilities.experimental as { "mcp++/<profile>": true }.
export const InitializeResultSchema = z.object({
  protocolVersion: z.string().min(1),
  capabilities: CapabilitiesSchema,
  serverInfo: ServerInfoSchema,
}).passthrough();
export type InitializeResult = z.infer<typeof InitializeResultSchema>;

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
  input_schema: z.record(z.any()),
  output_schema: z.record(z.any()),
  description: z.string().optional(),
  errors: z.array(z.string()).default([]),
  streaming: z.boolean().default(false),
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
  errors: z.array(z.string()).default([]),
  requires: z.array(z.string()).default([]),
  compatibility: z.record(z.any()).default({}),
  semantic_tags: z.array(z.string()).optional(),
  observability: z.record(z.any()).optional(),
  interaction_patterns: z.union([z.array(z.string()), z.record(z.any())]).optional(),
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
  timestamp: z.union([z.string(), z.number()]), // ISO 8601 or epoch seconds
  metadata: z.record(z.any()).optional(),
}).strict();
export type ExecutionEnvelope = z.infer<typeof ExecutionEnvelopeSchema>;

export const ExecutionReceiptSchema = z.object({
  success: z.boolean(),
  receipt_cid: z.string().regex(CIDPattern).optional(),
  output_cid: z.string().regex(CIDPattern).optional(),
  envelope_cid: z.string().regex(CIDPattern).optional(),
  error: z.string().nullable().optional(),
  duration_ms: z.number().optional(),
  decision_cid: z.string().regex(CIDPattern).optional(),
  signature: z.string().optional(),
}).passthrough();
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

// Canonical wire delegation (full-name form used by servers + SwissKnife).
// iss/aud/att/exp UCAN tokens map: issuer←iss, audience←aud, capabilities←att, expiry←exp.
export const DelegationSchema = z.object({
  issuer: z.string().min(1),
  audience: z.string().min(1),
  capabilities: z.array(z.record(z.any())).min(1),
  expiry: z.number().int().nullable().optional(),
  not_before: z.number().int().nullable().optional(),
  proof_cid: z.string().nullable().optional(),
  proof_cids: z.array(z.string()).nullable().optional(),
  nonce: z.string().nullable().optional(),
  cid: z.string().nullable().optional(),
}).passthrough();
export type Delegation = z.infer<typeof DelegationSchema>;

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
  decision: z.union([DecisionTypeSchema, z.string()]),
  allowed: z.boolean().optional(),
  policy_cid: z.string().regex(CIDPattern).optional(),
  obligations: z.array(z.record(z.any())).optional(),
  witness: z.record(z.any()).optional(),
}).passthrough();
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
  'intent',
  'decision',
  'receipt',
  'envelope',
]);
export type EventType = z.infer<typeof EventTypeSchema>;

export const DAGEventSchema = z.object({
  event_type: EventTypeSchema,
  event_cid: z.string().regex(CIDPattern),
  parents: z.array(z.string()),
  timestamp: z.union([z.string(), z.number()]), // ISO 8601 or epoch seconds
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

// Canonical application-level message over /mcp+p2p/1.0.0 (4-byte big-endian
// length prefix + this JSON body). De-facto shape from ipfs_accelerate_py /
// ipfs_datasets_py; SwissKnife's payload-bundled variant passes via passthrough.
export const P2PMessageTypeSchema = z.enum(['request', 'response', 'notification', 'event']);
export const P2PMessageSchema = z.object({
  type: z.union([P2PMessageTypeSchema, z.string()]),
  method: z.string().nullable().optional(),
  params: z.record(z.any()).nullable().optional(),
  id: z.string().nullable().optional(),
  result: z.any().optional(),
  error: z.string().nullable().optional(),
  sender: z.string().nullable().optional(),
  timestamp: z.union([z.number(), z.string()]).nullable().optional(),
}).passthrough();
export type P2PMessage = z.infer<typeof P2PMessageSchema>;

// ---------------------------------------------------------------------------
// Session error codes (MCP++ Profile E §9.1 — deterministic error taxonomy)
// ---------------------------------------------------------------------------

/**
 * Deterministic transport-layer error code ranges:
 *   1xxx: Framing errors
 *   2xxx: Protocol errors
 *   3xxx: Rate / policy violations
 *   4xxx: Session lifecycle errors
 */
export const SessionErrorCodeSchema = z.union([
  z.literal(1001), // FRAME_OVERSIZE
  z.literal(1002), // FRAME_OUTBOUND_OVERSIZE
  z.literal(1003), // FRAME_MALFORMED_JSON
  z.literal(1004), // FRAME_TRUNCATED_HEADER
  z.literal(2001), // PROTOCOL_VERSION_MISMATCH
  z.literal(2002), // PROTOCOL_HANDSHAKE_INVALID
  z.literal(2003), // PROTOCOL_NO_COMMON_PROFILE
  z.literal(3001), // RATE_LIMIT_EXCEEDED
  z.literal(4001), // SESSION_CLOSED
  z.literal(4002), // SESSION_READ_ENDED
  z.literal(4003), // SESSION_TIMEOUT
]);
export type SessionErrorCode = z.infer<typeof SessionErrorCodeSchema>;

export const SessionErrorSchema = z.object({
  code: SessionErrorCodeSchema,
  message: z.string().min(1),
  data: z.unknown().optional(),
}).passthrough();
export type SessionError = z.infer<typeof SessionErrorSchema>;

// ---------------------------------------------------------------------------
// PubSub bus message (MCP++ Profile E §3 — MCPPubSubBus BusMessage)
// ---------------------------------------------------------------------------

export const BusMessageSchema = z.object({
  /** The topic this message was published on. */
  topic: z.string().min(1),
  /** Serialisable payload. */
  payload: z.unknown(),
  /** ISO-8601 publish time. */
  published_at: z.string().datetime({ offset: true }).or(z.string().min(1)),
  /** Content-addressed CID: `sha256:<64-hex-chars>`. */
  message_cid: z.string().regex(/^sha256:[0-9a-f]{64}$/),
  /** Optional UCAN proof from the publisher. */
  ucan_token: z.string().optional(),
}).passthrough();
export type BusMessage = z.infer<typeof BusMessageSchema>;

/** Well-known MCP++ pub/sub topic identifiers. */
export const MCP_PUBSUB_TOPICS = [
  'mcp/interface/announce',
  'mcp/receipt/announce',
  'mcp/coord/signal',
  'mcp/delegation/merge',
  'mcp/policy/update',
] as const;
export type MCPPubSubTopic = typeof MCP_PUBSUB_TOPICS[number];

// ---------------------------------------------------------------------------
// Policy audit log entry (MCP++ Profile D — PolicyAuditLog AuditEntry)
// ---------------------------------------------------------------------------

export const AuditDecisionSchema = z.enum(['allow', 'deny', 'allow_with_obligations']);
export type AuditDecision = z.infer<typeof AuditDecisionSchema>;

export const AuditEntrySchema = z.object({
  /** 1-based monotone sequence number within the log. */
  seq: z.number().int().positive(),
  /** Unix timestamp (ms). */
  timestamp: z.number().int().nonnegative(),
  /** ISO-8601 wall clock. */
  timestamp_iso: z.string().min(1),
  policy_cid: z.string().min(1),
  intent_cid: z.string().min(1),
  decision: AuditDecisionSchema,
  actor: z.string().optional(),
  tool: z.string().min(1),
  justification: z.string(),
  obligations: z.array(z.string()),
  /** Content-addressed CID of this entry: `sha256:<64-hex-chars>`. */
  entry_cid: z.string().regex(/^sha256:[0-9a-f]{64}$/),
  extra: z.record(z.unknown()),
}).passthrough();
export type AuditEntry = z.infer<typeof AuditEntrySchema>;

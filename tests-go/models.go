// Package testsmcp provides type-safe validators for MCP and MCP++ protocol messages.
//
// This package implements comprehensive type checking and validation for all MCP
// protocol profiles using Go's strong type system and runtime validation.
package testsmcp

import (
	"encoding/json"
	"fmt"
	"regexp"
	"time"
)

// ============================================================================
// JSON-RPC 2.0 Base Types
// ============================================================================

// JSONRPCRequest represents a JSON-RPC 2.0 request message.
type JSONRPCRequest struct {
	JSONRPC string      `json:"jsonrpc" validate:"required"`
	Method  string      `json:"method" validate:"required,min=1"`
	Params  interface{} `json:"params,omitempty"`
	ID      interface{} `json:"id" validate:"required"`
}

// JSONRPCResponse represents a JSON-RPC 2.0 response message.
type JSONRPCResponse struct {
	JSONRPC string        `json:"jsonrpc" validate:"required,eq=2.0"`
	ID      interface{}   `json:"id" validate:"required"`
	Result  interface{}   `json:"result,omitempty"`
	Error   *JSONRPCError `json:"error,omitempty"`
}

// JSONRPCNotification represents a JSON-RPC 2.0 notification message.
type JSONRPCNotification struct {
	JSONRPC string      `json:"jsonrpc" validate:"required,eq=2.0"`
	Method  string      `json:"method" validate:"required,min=1"`
	Params  interface{} `json:"params,omitempty"`
}

// JSONRPCError represents a JSON-RPC 2.0 error object.
type JSONRPCError struct {
	Code    int         `json:"code" validate:"required"`
	Message string      `json:"message" validate:"required,min=1"`
	Data    interface{} `json:"data,omitempty"`
}

// ============================================================================
// MCP Protocol Types
// ============================================================================

// ClientInfo contains information about the MCP client.
type ClientInfo struct {
	Name    string `json:"name" validate:"required,min=1"`
	Version string `json:"version" validate:"required,min=1"`
}

// ServerInfo contains information about the MCP server.
type ServerInfo struct {
	Name    string `json:"name" validate:"required,min=1"`
	Version string `json:"version" validate:"required,min=1"`
}

// Capabilities represents the capabilities that a client or server supports.
type Capabilities struct {
	Tools     map[string]interface{} `json:"tools,omitempty"`
	Resources map[string]interface{} `json:"resources,omitempty"`
	Prompts   map[string]interface{} `json:"prompts,omitempty"`
}

// InitializeParams contains parameters for the initialize method.
type InitializeParams struct {
	ProtocolVersion string       `json:"protocolVersion" validate:"required"`
	Capabilities    Capabilities `json:"capabilities" validate:"required"`
	ClientInfo      ClientInfo   `json:"clientInfo" validate:"required"`
}

// InitializeResult contains the result of the initialize method.
type InitializeResult struct {
	ProtocolVersion string       `json:"protocolVersion" validate:"required"`
	Capabilities    Capabilities `json:"capabilities" validate:"required"`
	ServerInfo      ServerInfo   `json:"serverInfo" validate:"required"`
}

// ToolCallParams contains parameters for calling a tool.
type ToolCallParams struct {
	Name      string                 `json:"name" validate:"required,min=1"`
	Arguments map[string]interface{} `json:"arguments,omitempty"`
}

// ResourceReadParams contains parameters for reading a resource.
type ResourceReadParams struct {
	URI string `json:"uri" validate:"required,min=1"`
}

// PromptGetParams contains parameters for getting a prompt.
type PromptGetParams struct {
	Name      string                 `json:"name" validate:"required,min=1"`
	Arguments map[string]interface{} `json:"arguments,omitempty"`
}

// ============================================================================
// MCP-IDL (Profile A) Types
// ============================================================================

// InterfaceDescriptor represents an MCP-IDL interface descriptor.
type InterfaceDescriptor struct {
	InterfaceName string                 `json:"interface_name" validate:"required,min=1"`
	Version       string                 `json:"version" validate:"required"`
	Methods       []MethodDescriptor     `json:"methods" validate:"required,min=1,dive"`
	Metadata      map[string]interface{} `json:"metadata,omitempty"`
}

// MethodDescriptor describes a method in an interface.
type MethodDescriptor struct {
	Name        string                 `json:"name"`
	Description string                 `json:"description,omitempty"`
	Parameters  []ParameterDescriptor  `json:"parameters,omitempty"`
	ReturnType  string                 `json:"return_type"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// ParameterDescriptor describes a method parameter.
type ParameterDescriptor struct {
	Name        string `json:"name" validate:"required,min=1"`
	Type        string `json:"type" validate:"required"`
	Description string `json:"description,omitempty"`
	Required    bool   `json:"required"`
}

// InterfaceCompatibility represents the result of a compatibility check.
type InterfaceCompatibility struct {
	Compatible bool     `json:"compatible" validate:"required"`
	Reasons    []string `json:"reasons,omitempty"`
}

// ============================================================================
// CID Artifacts (Profile B) Types
// ============================================================================

// ExecutionEnvelope wraps an MCP invocation with content-addressing.
type ExecutionEnvelope struct {
	InterfaceCID string                 `json:"interface_cid" validate:"required"`
	InputCID     string                 `json:"input_cid" validate:"required"`
	Parents      []string               `json:"parents,omitempty" validate:"dive"`
	Invocation   map[string]interface{} `json:"invocation" validate:"required"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
}

// ExecutionReceipt contains the result of an execution with provenance.
type ExecutionReceipt struct {
	Success    bool                   `json:"success"`
	ReceiptCID string                 `json:"receipt_cid" validate:"required"`
	OutputCID  string                 `json:"output_cid,omitempty"`
	Error      interface{}            `json:"error,omitempty"`
	DurationMS float64                `json:"duration_ms,omitempty"`
	Signature  string                 `json:"signature,omitempty"`
	Metadata   map[string]interface{} `json:"metadata,omitempty"`
}

// ============================================================================
// UCAN Delegation (Profile C) Types
// ============================================================================

// UCANToken represents a User Controlled Authorization Network token.
type UCANToken struct {
	Issuer       string                 `json:"iss" validate:"required"`
	Audience     string                 `json:"aud" validate:"required"`
	Subject      string                 `json:"sub,omitempty"`
	Capabilities []Capability           `json:"att" validate:"required,dive"`
	Expiration   int64                  `json:"exp" validate:"required"`
	NotBefore    int64                  `json:"nbf,omitempty"`
	Proof        []string               `json:"prf,omitempty" validate:"dive"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
}

// Capability represents a capability that can be delegated.
type Capability struct {
	With   string                 `json:"with"`
	Can    string                 `json:"can"`
	Limits map[string]interface{} `json:"limits,omitempty"`
}

// DelegationChain represents a chain of UCAN delegations.
type DelegationChain struct {
	Root   UCANToken   `json:"root" validate:"required"`
	Proofs []UCANToken `json:"proofs,omitempty" validate:"dive"`
}

// ============================================================================
// Policy Evaluation (Profile D) Types
// ============================================================================

// PolicyType represents the type of policy.
type PolicyType string

const (
	PolicyTypePermission  PolicyType = "permission"
	PolicyTypeProhibition PolicyType = "prohibition"
	PolicyTypeObligation  PolicyType = "obligation"
)

// PolicyDescriptor describes a temporal deontic policy.
type PolicyDescriptor struct {
	PolicyCID   string                 `json:"policy_cid" validate:"required"`
	Type        PolicyType             `json:"type" validate:"required"`
	Target      string                 `json:"target" validate:"required"`
	Constraints []PolicyConstraint     `json:"constraints,omitempty" validate:"dive"`
	ValidFrom   time.Time              `json:"valid_from,omitempty"`
	ValidUntil  time.Time              `json:"valid_until,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// PolicyConstraint represents a constraint in a policy.
type PolicyConstraint struct {
	Type      string      `json:"type" validate:"required"`
	Condition string      `json:"condition" validate:"required"`
	Value     interface{} `json:"value,omitempty"`
}

// DecisionType represents the type of policy decision.
type DecisionType string

const (
	DecisionAllow                DecisionType = "allow"
	DecisionDeny                 DecisionType = "deny"
	DecisionAllowWithObligations DecisionType = "allow_with_obligations"
)

// PolicyDecision represents the result of policy evaluation.
type PolicyDecision struct {
	DecisionCID string                 `json:"decision_cid" validate:"required"`
	Decision    DecisionType           `json:"decision" validate:"required"`
	PolicyCID   string                 `json:"policy_cid" validate:"required"`
	Timestamp   time.Time              `json:"timestamp" validate:"required"`
	Obligations []Obligation           `json:"obligations,omitempty" validate:"dive"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// Obligation represents an obligation that must be fulfilled.
type Obligation struct {
	Action   string    `json:"action" validate:"required"`
	Deadline time.Time `json:"deadline,omitempty"`
	Status   string    `json:"status" validate:"required,oneof=pending fulfilled failed"`
}

// ============================================================================
// Transport (Profile E) Types
// ============================================================================

// TransportMessage represents a message in the mcp+p2p transport protocol.
type TransportMessage struct {
	ProtocolID string          `json:"protocol_id" validate:"required"`
	SessionID  string          `json:"session_id" validate:"required"`
	Sequence   uint64          `json:"sequence" validate:"required"`
	Payload    json.RawMessage `json:"payload" validate:"required"`
}

// SessionInit represents a session initialization message.
type SessionInit struct {
	SessionID       string       `json:"session_id" validate:"required"`
	ProtocolVersion string       `json:"protocol_version" validate:"required"`
	Capabilities    Capabilities `json:"capabilities" validate:"required"`
	PeerID          string       `json:"peer_id" validate:"required"`
}

// ============================================================================
// Event DAG Types
// ============================================================================

// Event represents an event in the provenance DAG.
type Event struct {
	EventCID  string                 `json:"event_cid" validate:"required"`
	Type      string                 `json:"type" validate:"required"`
	Parents   []string               `json:"parents,omitempty" validate:"dive"`
	Timestamp time.Time              `json:"timestamp" validate:"required"`
	Actor     string                 `json:"actor,omitempty"`
	Action    string                 `json:"action" validate:"required"`
	Target    string                 `json:"target,omitempty"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

// EventDAG represents a directed acyclic graph of events.
type EventDAG struct {
	Events map[string]*Event `json:"events" validate:"required"`
	Roots  []string          `json:"roots" validate:"required,min=1,dive,cid"`
}

// ============================================================================
// Canonical full-name wire models (cross-server interop parity with py/ts/rs)
// ============================================================================

// Delegation is the canonical full-name delegation record (Profile C) emitted by
// ipfs_accelerate_py, ipfs_datasets_py and SwissKnife. UCAN iss/aud/att/exp map
// onto issuer/audience/capabilities/expiry. Extra fields allowed by default.
type Delegation struct {
	Issuer       string                   `json:"issuer" validate:"required,min=1"`
	Audience     string                   `json:"audience" validate:"required,min=1"`
	Capabilities []map[string]interface{} `json:"capabilities" validate:"required,min=1"`
	Expiry       *int64                   `json:"expiry,omitempty"`
	NotBefore    *int64                   `json:"not_before,omitempty"`
	ProofCID     string                   `json:"proof_cid,omitempty"`
	ProofCIDs    []string                 `json:"proof_cids,omitempty"`
	Nonce        string                   `json:"nonce,omitempty"`
	CID          string                   `json:"cid,omitempty"`
}

// DAGEvent is the canonical DAG event wire form. Timestamp accepts an ISO-8601
// string or epoch seconds; EventType is free-form. Matches both servers.
type DAGEvent struct {
	EventType string                 `json:"event_type" validate:"required"`
	EventCID  string                 `json:"event_cid" validate:"required"`
	Parents   []string               `json:"parents"`
	Timestamp interface{}            `json:"timestamp" validate:"required"`
	Payload   map[string]interface{} `json:"payload" validate:"required"`
}

// PolicyDecisionWire is the de-facto wire result of mcp++/policy/evaluate from
// both servers: {decision, obligations, allowed}. policy_cid optional.
type PolicyDecisionWire struct {
	Decision    string                   `json:"decision" validate:"required"`
	Allowed     *bool                    `json:"allowed,omitempty"`
	PolicyCID   string                   `json:"policy_cid,omitempty"`
	Obligations []map[string]interface{} `json:"obligations,omitempty"`
	Witness     map[string]interface{}   `json:"witness,omitempty"`
}

// P2PMessage is the canonical Profile E application envelope. Only Type is
// required; remaining fields populate per request/response/notification/event.
type P2PMessage struct {
	Type      string                 `json:"type" validate:"required,min=1"`
	Method    string                 `json:"method,omitempty"`
	Params    map[string]interface{} `json:"params,omitempty"`
	ID        string                 `json:"id,omitempty"`
	Result    interface{}            `json:"result,omitempty"`
	Error     string                 `json:"error,omitempty"`
	Sender    string                 `json:"sender,omitempty"`
	Timestamp interface{}            `json:"timestamp,omitempty"`
}

// Canonical JSON-RPC error codes emitted by MCP++ servers (normative meanings).
const (
	ErrParseError     int = -32700
	ErrInvalidRequest int = -32600
	ErrMethodNotFound int = -32601
	ErrInvalidParams  int = -32602
	ErrInternalError  int = -32603
	ErrServerError    int = -32000
)

// ============================================================================
// Canonical session, audit, and proof wire models
// ============================================================================

var sha256CIDPattern = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)

// SHA256CID is the canonical sha256:<64-lowercase-hex> content identifier.
// Validation happens while decoding so every consumer, not only this test
// harness, rejects malformed wire values.
type SHA256CID string

// UnmarshalJSON enforces the canonical SHA-256 CID wire representation.
func (cid *SHA256CID) UnmarshalJSON(data []byte) error {
	var value string
	if err := json.Unmarshal(data, &value); err != nil {
		return err
	}
	if !sha256CIDPattern.MatchString(value) {
		return fmt.Errorf("invalid SHA-256 CID %q", value)
	}
	*cid = SHA256CID(value)
	return nil
}

// SessionErrorCode is a deterministic Profile E transport/session error code.
type SessionErrorCode int

// SessionError is the canonical structured Profile E error envelope.
type SessionError struct {
	Code    SessionErrorCode `json:"code" validate:"required,oneof=1001 1002 1003 1004 2001 2002 2003 3001 4001 4002 4003"`
	Message string           `json:"message" validate:"required,min=1"`
	Data    interface{}      `json:"data,omitempty"`
}

// MCPPubSubTopics lists the five well-known MCP++ bus topics.
var MCPPubSubTopics = [...]string{
	"mcp/interface/announce",
	"mcp/receipt/announce",
	"mcp/coord/signal",
	"mcp/delegation/merge",
	"mcp/policy/update",
}

// BusMessage is the canonical Profile E pub/sub bus message.
type BusMessage struct {
	Topic       string      `json:"topic" validate:"required,min=1"`
	Payload     interface{} `json:"payload" validate:"required"`
	PublishedAt string      `json:"published_at" validate:"required,min=1"`
	MessageCID  SHA256CID   `json:"message_cid" validate:"required"`
	UCANToken   string      `json:"ucan_token,omitempty"`
}

// AuditDecision is a canonical Profile D policy decision.
type AuditDecision string

// AuditEntry is a canonical Profile D policy audit log entry.
type AuditEntry struct {
	Seq           uint64                 `json:"seq" validate:"required,gte=1"`
	Timestamp     uint64                 `json:"timestamp"`
	TimestampISO  string                 `json:"timestamp_iso" validate:"required,min=1"`
	PolicyCID     string                 `json:"policy_cid" validate:"required,min=1"`
	IntentCID     string                 `json:"intent_cid" validate:"required,min=1"`
	Decision      AuditDecision          `json:"decision" validate:"required,oneof=allow deny allow_with_obligations"`
	Actor         string                 `json:"actor,omitempty"`
	Tool          string                 `json:"tool" validate:"required,min=1"`
	Justification string                 `json:"justification"`
	Obligations   []string               `json:"obligations"`
	EntryCID      SHA256CID              `json:"entry_cid" validate:"required"`
	Extra         map[string]interface{} `json:"extra"`
}

// ProofReason is the canonical proof outcome taxonomy.
type ProofReason string

// WasmProverID identifies a canonical local/WASM proof backend.
type WasmProverID string

// WasmProofResult is emitted by a canonical local/WASM proof backend.
type WasmProofResult struct {
	Proved      bool                   `json:"proved"`
	Sat         bool                   `json:"sat"`
	Unsat       bool                   `json:"unsat"`
	Reason      ProofReason            `json:"reason" validate:"required,oneof=proved refuted sat unsat unknown timeout error"`
	ProverID    WasmProverID           `json:"prover_id" validate:"required,oneof=z3-wasm cvc5-wasm coq-jscoq lean4-wasm lurk-wasm neural cache-hit"`
	ProofTimeMS float64                `json:"proof_time_ms" validate:"gte=0"`
	Model       map[string]interface{} `json:"model,omitempty"`
	UnsatCore   []string               `json:"unsat_core,omitempty"`
	Meta        map[string]interface{} `json:"meta,omitempty"`
}

// ZKProofBackend identifies a canonical zero-knowledge proof backend.
type ZKProofBackend string

// ZKProofArtifact is a content-addressed zero-knowledge proof artifact.
type ZKProofArtifact struct {
	Backend      ZKProofBackend `json:"backend" validate:"required,oneof=lurk nova sphinx plonky3 circom"`
	Statement    string         `json:"statement" validate:"required,min=1"`
	ProofBase64  string         `json:"proof_b64" validate:"required,min=1"`
	VKCID        SHA256CID      `json:"vk_cid" validate:"required"`
	PublicInputs []interface{}  `json:"public_inputs"`
	ArtifactCID  SHA256CID      `json:"artifact_cid" validate:"required"`
	ProofTimeMS  float64        `json:"proof_time_ms" validate:"gte=0"`
	LurkExpr     string         `json:"lurk_expr,omitempty"`
}

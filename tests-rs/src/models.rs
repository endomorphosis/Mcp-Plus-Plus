//! MCP Protocol Type Definitions
//!
//! Provides strongly-typed Rust structures for all MCP and MCP++ protocol messages.
//! Uses serde for serialization and serde_valid for runtime validation.

use serde::{Deserialize, Serialize};
use serde_valid::Validate;
use std::collections::HashMap;

/// JSON-RPC 2.0 Request
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
#[serde(deny_unknown_fields)]
pub struct JSONRPCRequest {
    /// Must be exactly "2.0"
    #[validate(pattern = r"^2\.0$")]
    pub jsonrpc: String,
    
    /// Method name
    #[validate(min_length = 1)]
    pub method: String,
    
    /// Optional parameters
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub params: Option<serde_json::Value>,
    
    /// Request identifier
    pub id: RequestId,
}

/// JSON-RPC 2.0 Response
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
#[serde(deny_unknown_fields)]
pub struct JSONRPCResponse {
    /// Must be exactly "2.0"
    #[validate(pattern = r"^2\.0$")]
    pub jsonrpc: String,
    
    /// Result (present on success)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<serde_json::Value>,
    
    /// Error (present on failure)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JSONRPCError>,
    
    /// Request identifier
    pub id: RequestId,
}

/// JSON-RPC 2.0 Notification
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
#[serde(deny_unknown_fields)]
pub struct JSONRPCNotification {
    /// Must be exactly "2.0"
    #[validate(pattern = r"^2\.0$")]
    pub jsonrpc: String,
    
    /// Method name
    #[validate(min_length = 1)]
    pub method: String,
    
    /// Optional parameters
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub params: Option<serde_json::Value>,
}

/// JSON-RPC 2.0 Error
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct JSONRPCError {
    /// Error code
    pub code: i32,
    
    /// Error message
    #[validate(min_length = 1)]
    pub message: String,
    
    /// Optional error data
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<serde_json::Value>,
}

/// Canonical JSON-RPC error codes used by MCP++ servers. Meanings are normative.
pub mod error_code {
    pub const PARSE_ERROR: i32 = -32700;
    pub const INVALID_REQUEST: i32 = -32600;
    pub const METHOD_NOT_FOUND: i32 = -32601;
    pub const INVALID_PARAMS: i32 = -32602;
    pub const INTERNAL_ERROR: i32 = -32603;
    pub const SERVER_ERROR: i32 = -32000;
    pub const CANONICAL: [i32; 6] = [-32700, -32600, -32601, -32602, -32603, -32000];
}

/// Request ID (can be string or number)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(untagged)]
pub enum RequestId {
    String(String),
    Number(i64),
}

/// Initialize method parameters
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct InitializeParams {
    /// Protocol version
    #[validate(pattern = r"^\d+\.\d+\.\d+$")]
    pub protocol_version: String,
    
    /// Client information
    pub client_info: ClientInfo,
    
    /// Client capabilities
    pub capabilities: Capabilities,
}

/// Client/Server information
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct ClientInfo {
    /// Client name
    #[validate(min_length = 1)]
    pub name: String,
    
    /// Client version
    #[validate(min_length = 1)]
    pub version: String,
}

/// Server information (alias for ClientInfo)
pub type ServerInfo = ClientInfo;

/// Initialize result (server -> client handshake). mcp++ profiles negotiated
/// under capabilities.experimental as { "mcp++/<profile>": true }.
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct InitializeResult {
    /// Protocol version (e.g. 2024-11-05)
    #[validate(min_length = 1)]
    pub protocol_version: String,
    /// Server capabilities
    pub capabilities: Capabilities,
    /// Server information
    pub server_info: ServerInfo,
}

/// MCP Capabilities
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Capabilities {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tools: Option<ToolsCapability>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub resources: Option<ResourcesCapability>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompts: Option<PromptsCapability>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub experimental: Option<HashMap<String, serde_json::Value>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolsCapability {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub list_changed: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourcesCapability {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub subscribe: Option<bool>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub list_changed: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PromptsCapability {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub list_changed: Option<bool>,
}

/// Tool call parameters
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct ToolCallParams {
    /// Tool name
    #[validate(min_length = 1)]
    pub name: String,
    
    /// Tool arguments
    #[serde(default)]
    pub arguments: HashMap<String, serde_json::Value>,
}

/// Resource read parameters
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct ResourceReadParams {
    /// Resource URI
    #[validate(min_length = 1)]
    pub uri: String,
}

/// Prompt get parameters
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct PromptGetParams {
    /// Prompt name
    #[validate(min_length = 1)]
    pub name: String,
    
    /// Optional arguments
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub arguments: Option<HashMap<String, serde_json::Value>>,
}

// ========== MCP-IDL (Profile A) ==========

/// Interface descriptor for MCP-IDL
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct InterfaceDescriptor {
    /// Interface name
    #[validate(min_length = 1)]
    pub name: String,
    
    /// Interface version
    #[validate(pattern = r"^\d+\.\d+\.\d+$")]
    pub version: String,
    
    /// Tool definitions
    pub tools: Vec<ToolDefinition>,
    
    /// CID of this descriptor
    #[validate(pattern = r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$")]
    pub interface_cid: String,
}

/// Tool definition in interface descriptor
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct ToolDefinition {
    /// Tool name
    #[validate(min_length = 1)]
    pub name: String,
    
    /// Tool description
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    
    /// Input schema
    pub input_schema: serde_json::Value,
}

// ========== CID Artifacts (Profile B) ==========

/// Execution envelope with CID references
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct ExecutionEnvelope {
    /// Interface CID
    #[validate(pattern = r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$")]
    pub interface_cid: String,
    
    /// Input CID
    #[validate(pattern = r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$")]
    pub input_cid: String,
    
    /// Parent CIDs (can be empty for genesis)
    #[serde(default)]
    pub parents: Vec<String>,
    
    /// Timestamp
    pub timestamp: String,
}

/// Execution receipt
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct ExecutionReceipt {
    /// Envelope CID
    #[validate(pattern = r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$")]
    pub envelope_cid: String,
    
    /// Output CID
    #[validate(pattern = r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$")]
    pub output_cid: String,
    
    /// Signature
    #[validate(min_length = 1)]
    pub signature: String,
    
    /// Receipt CID
    #[validate(pattern = r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$")]
    pub receipt_cid: String,
}

// ========== UCAN Delegation (Profile C) ==========

/// UCAN token for capability delegation
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct UCANToken {
    /// Issuer DID
    #[validate(pattern = r"^did:")]
    pub iss: String,
    
    /// Audience DID
    #[validate(pattern = r"^did:")]
    pub aud: String,
    
    /// Attenuations (capabilities)
    pub att: Vec<Attenuation>,
    
    /// Expiration timestamp
    pub exp: i64,
    
    /// Optional proof CID
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prf: Option<String>,
}

/// Capability attenuation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Attenuation {
    pub resource: String,
    pub ability: String,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub caveats: Option<HashMap<String, serde_json::Value>>,
}

/// Delegation chain
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct DelegationChain {
    /// Chain of UCAN tokens
    #[validate(min_items = 1)]
    pub chain: Vec<UCANToken>,
}

// ========== Policy Evaluation (Profile D) ==========

/// Policy definition
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct Policy {
    /// Policy CID
    #[validate(pattern = r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$")]
    pub policy_cid: String,
    
    /// Policy type
    pub policy_type: PolicyType,
    
    /// Temporal constraints
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temporal: Option<TemporalConstraint>,
    
    /// Policy rules
    pub rules: Vec<PolicyRule>,
}

/// Policy type enumeration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum PolicyType {
    Permission,
    Prohibition,
    Obligation,
}

/// Temporal constraint
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemporalConstraint {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub not_before: Option<String>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub not_after: Option<String>,
}

/// Policy rule
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct PolicyRule {
    /// Rule condition
    #[validate(min_length = 1)]
    pub condition: String,
    
    /// Rule action
    #[validate(min_length = 1)]
    pub action: String,
}

/// Policy decision
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct PolicyDecision {
    /// Decision type
    pub decision: DecisionType,
    
    /// Optional decision CID
    #[serde(skip_serializing_if = "Option::is_none")]
    #[validate(pattern = r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$")]
    pub decision_cid: Option<String>,
    
    /// Optional obligations
    #[serde(skip_serializing_if = "Option::is_none")]
    pub obligations: Option<Vec<Obligation>>,
}

/// Decision type enumeration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DecisionType {
    Allow,
    Deny,
    AllowWithObligations,
}

/// Obligation spawned from policy
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct Obligation {
    /// Obligation description
    #[validate(min_length = 1)]
    pub description: String,
    
    /// Optional deadline
    #[serde(skip_serializing_if = "Option::is_none")]
    pub deadline: Option<String>,
}

// ========== Transport (Profile E) ==========

/// Transport protocol message
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct TransportMessage {
    /// Protocol ID
    #[validate(pattern = r"^/mcp\+p2p/")]
    pub protocol_id: String,
    
    /// Message length
    #[validate(minimum = 1)]
    pub length: u32,
    
    /// Message payload
    pub payload: serde_json::Value,
}

/// Application-level message over /mcp+p2p/1.0.0 (4-byte BE length prefix + JSON).
/// De-facto interop shape from ipfs_accelerate_py / ipfs_datasets_py.
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct P2PMessage {
    /// request|response|notification|event
    #[validate(min_length = 1)]
    pub r#type: String,
    /// JSON-RPC method (requests)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub method: Option<String>,
    /// Method params
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub params: Option<serde_json::Value>,
    /// Correlation id
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub id: Option<String>,
    /// Result (responses)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub result: Option<serde_json::Value>,
    /// Error string (responses)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    /// Sender peer id
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sender: Option<String>,
    /// Emit time
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub timestamp: Option<serde_json::Value>,
}
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct SessionInfo {
    /// Session ID
    #[validate(min_length = 1)]
    pub session_id: String,
    
    /// Peer multiaddr
    #[validate(min_length = 1)]
    pub peer_addr: String,
}

// ========== Event DAG ==========

/// Event in the DAG
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct Event {
    /// Event CID
    #[validate(pattern = r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$")]
    pub event_cid: String,
    
    /// Parent event CIDs (empty for genesis)
    #[serde(default)]
    pub parents: Vec<String>,
    
    /// Event payload
    pub payload: serde_json::Value,
    
    /// Timestamp
    pub timestamp: String,
}

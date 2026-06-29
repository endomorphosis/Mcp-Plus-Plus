"""
Pydantic Models for MCP Protocol Validation

Provides strict runtime type validation using Pydantic v2.
These models enforce the MCP protocol specifications with compile-time
and runtime type safety.
"""

from typing import Any, Dict, List, Literal, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# ============================================================================
# Base JSON-RPC Models
# ============================================================================

class JSONRPCVersion(str, Enum):
    """JSON-RPC protocol version."""
    V2_0 = "2.0"


class JSONRPCError(BaseModel):
    """JSON-RPC error object."""
    model_config = ConfigDict(extra='forbid', strict=True)
    
    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional error data")


class JSONRPCRequest(BaseModel):
    """JSON-RPC request message."""
    model_config = ConfigDict(extra='forbid', strict=True)
    
    jsonrpc: Literal["2.0"] = Field(..., description="JSON-RPC version")
    method: str = Field(..., min_length=1, description="Method name")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Method parameters")
    id: Union[str, int] = Field(..., description="Request identifier")


class JSONRPCNotification(BaseModel):
    """JSON-RPC notification message (no id field)."""
    model_config = ConfigDict(extra='forbid', strict=True)
    
    jsonrpc: Literal["2.0"] = Field(..., description="JSON-RPC version")
    method: str = Field(..., min_length=1, pattern=r"^notifications/", description="Notification method")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Method parameters")


class JSONRPCResponse(BaseModel):
    """JSON-RPC response message."""
    model_config = ConfigDict(extra='forbid', strict=True)
    
    jsonrpc: Literal["2.0"] = Field(..., description="JSON-RPC version")
    id: Union[str, int] = Field(..., description="Request identifier")
    result: Optional[Any] = Field(None, description="Success result")
    error: Optional[JSONRPCError] = Field(None, description="Error object")
    
    @model_validator(mode='after')
    def check_result_or_error(self) -> 'JSONRPCResponse':
        """Ensure exactly one of result or error is present."""
        has_result = self.result is not None
        has_error = self.error is not None
        
        if not has_result and not has_error:
            raise ValueError("Response must contain either 'result' or 'error'")
        if has_result and has_error:
            raise ValueError("Response cannot contain both 'result' and 'error'")
        
        return self


# ============================================================================
# MCP Protocol Models
# ============================================================================

class ClientInfo(BaseModel):
    """Client information for MCP initialization."""
    model_config = ConfigDict(extra='allow', strict=True)
    
    name: str = Field(..., min_length=1, description="Client name")
    version: str = Field(..., min_length=1, description="Client version")


class ServerInfo(BaseModel):
    """Server information for MCP initialization."""
    model_config = ConfigDict(extra='allow', strict=True)
    
    name: str = Field(..., min_length=1, description="Server name")
    version: str = Field(..., min_length=1, description="Server version")


class Capabilities(BaseModel):
    """MCP capabilities."""
    model_config = ConfigDict(extra='allow', strict=True)
    
    tools: Optional[Dict[str, Any]] = Field(None, description="Tool capabilities")
    resources: Optional[Dict[str, Any]] = Field(None, description="Resource capabilities")
    prompts: Optional[Dict[str, Any]] = Field(None, description="Prompt capabilities")


class InitializeParams(BaseModel):
    """Parameters for initialize request."""
    model_config = ConfigDict(extra='allow', strict=True)
    
    protocolVersion: str = Field(..., description="Protocol version")
    capabilities: Capabilities = Field(..., description="Client capabilities")
    clientInfo: ClientInfo = Field(..., description="Client information")


class ToolCallParams(BaseModel):
    """Parameters for tools/call request."""
    model_config = ConfigDict(extra='forbid', strict=True)
    
    name: str = Field(..., min_length=1, description="Tool name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class ResourceReadParams(BaseModel):
    """Parameters for resources/read request."""
    model_config = ConfigDict(extra='forbid', strict=True)
    
    uri: str = Field(..., min_length=1, description="Resource URI")


class PromptGetParams(BaseModel):
    """Parameters for prompts/get request."""
    model_config = ConfigDict(extra='forbid', strict=True)
    
    name: str = Field(..., min_length=1, description="Prompt name")
    arguments: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Prompt arguments")


# ============================================================================
# MCP-IDL (Profile A) Models
# ============================================================================

class MethodDescriptor(BaseModel):
    """Method descriptor for MCP-IDL."""
    model_config = ConfigDict(extra='allow', strict=True)

    name: str = Field(..., min_length=1, description="Method name")
    input_schema: Dict[str, Any] = Field(..., description="Input parameter schema")
    output_schema: Dict[str, Any] = Field(..., description="Output/return schema")
    description: Optional[str] = Field(None, description="Method description")
    errors: List[str] = Field(default_factory=list, description="Error names this method may raise")
    streaming: bool = Field(False, description="Whether the method streams output")


class ErrorDescriptor(BaseModel):
    """Error descriptor for MCP-IDL."""
    model_config = ConfigDict(extra='allow', strict=True)
    
    code: int = Field(..., description="Error code")
    message: str = Field(..., min_length=1, description="Error message template")
    data_schema: Optional[Dict[str, Any]] = Field(None, description="Error data schema")


class InterfaceDescriptor(BaseModel):
    """MCP-IDL interface descriptor."""
    model_config = ConfigDict(extra='allow', strict=True)
    
    name: str = Field(..., min_length=1, description="Interface name")
    namespace: str = Field(..., min_length=1, description="Interface namespace")
    version: str = Field(..., min_length=1, description="Semantic version")
    methods: List[MethodDescriptor] = Field(..., min_length=1, description="Method descriptors")
    errors: List[str] = Field(default_factory=list, description="Interface-level error names")
    requires: List[str] = Field(default_factory=list, description="Required interfaces")
    compatibility: Dict[str, Any] = Field(default_factory=dict, description="Compatibility constraints")
    semantic_tags: Optional[List[str]] = Field(None, description="Semantic tags")
    observability: Optional[Dict[str, Any]] = Field(None, description="Observability config")
    interaction_patterns: Optional[Union[List[str], Dict[str, Any]]] = Field(None, description="Interaction patterns")
    resource_cost_hints: Optional[Dict[str, Any]] = Field(None, description="Resource cost hints")


# ============================================================================
# CID Artifacts (Profile B) Models
# ============================================================================

class ExecutionEnvelope(BaseModel):
    """Execution envelope with CID references."""
    model_config = ConfigDict(extra='forbid', strict=True)
    
    interface_cid: str = Field(..., pattern=r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$", 
                               description="CID of interface descriptor")
    input_cid: str = Field(..., pattern=r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$",
                          description="CID of input data")
    parents: List[str] = Field(..., description="Parent envelope CIDs")
    timestamp: Union[str, float, int] = Field(..., description="ISO 8601 timestamp or epoch seconds")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ExecutionReceipt(BaseModel):
    """Execution receipt with result."""
    model_config = ConfigDict(extra='forbid', strict=True)
    
    envelope_cid: str = Field(..., pattern=r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$",
                             description="CID of execution envelope")
    output_cid: str = Field(..., pattern=r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$",
                           description="CID of output data")
    success: bool = Field(..., description="Execution success flag")
    decision_cid: Optional[str] = Field(None, 
                                       pattern=r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$",
                                       description="CID of policy decision")
    signature: Optional[str] = Field(None, description="Receipt signature")


# ============================================================================
# UCAN Delegation (Profile C) Models
# ============================================================================

class UCANToken(BaseModel):
    """UCAN delegation token."""
    model_config = ConfigDict(extra='allow', strict=True)
    
    iss: str = Field(..., min_length=1, description="Issuer DID")
    aud: str = Field(..., min_length=1, description="Audience DID")
    att: List[Dict[str, Any]] = Field(..., min_length=1, description="Attenuations")
    exp: int = Field(..., gt=0, description="Expiration timestamp")
    prf: Optional[List[str]] = Field(None, description="Proof chain (parent UCANs)")


class DelegationChain(BaseModel):
    """UCAN delegation chain."""
    model_config = ConfigDict(extra='forbid', strict=True)
    
    root: UCANToken = Field(..., description="Root UCAN token")
    chain: List[UCANToken] = Field(default_factory=list, description="Delegation chain")
    proof_cid: str = Field(..., pattern=r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$",
                          description="CID of proof chain")


class Delegation(BaseModel):
    """Canonical wire delegation record (full-name form used by servers/clients).

    This is the interoperable shape emitted by ipfs_accelerate_py, ipfs_datasets_py
    and SwissKnife. `iss/aud/att/exp` UCAN tokens map onto these full names:
    issuer←iss, audience←aud, capabilities←att, expiry←exp, proof chain←prf.
    """
    model_config = ConfigDict(extra='allow', strict=True)

    issuer: str = Field(..., min_length=1, description="Issuer DID")
    audience: str = Field(..., min_length=1, description="Audience DID")
    capabilities: List[Dict[str, Any]] = Field(..., min_length=1, description="Capabilities [{resource, ability}]")
    expiry: Optional[int] = Field(None, description="Expiration epoch seconds (None = no expiry)")
    not_before: Optional[int] = Field(None, description="Not-before epoch seconds")
    proof_cid: Optional[str] = Field(None, description="Single proof bundle CID")
    proof_cids: Optional[List[str]] = Field(None, description="Parent delegation CIDs")
    nonce: Optional[str] = Field(None, description="Replay-protection nonce")
    cid: Optional[str] = Field(None, description="CID of this delegation record")


# ============================================================================
# Policy Evaluation (Profile D) Models
# ============================================================================

class PolicyType(str, Enum):
    """Policy types."""
    PERMISSION = "permission"
    PROHIBITION = "prohibition"
    OBLIGATION = "obligation"


class DecisionType(str, Enum):
    """Policy decision types."""
    ALLOW = "allow"
    DENY = "deny"
    ALLOW_WITH_OBLIGATIONS = "allow_with_obligations"


class TemporalConstraint(BaseModel):
    """Temporal constraint for policies."""
    model_config = ConfigDict(extra='forbid', strict=True)
    
    not_before: Optional[str] = Field(None, description="ISO 8601 start time")
    not_after: Optional[str] = Field(None, description="ISO 8601 end time")
    duration: Optional[str] = Field(None, description="ISO 8601 duration")


class Policy(BaseModel):
    """Deontic policy."""
    model_config = ConfigDict(extra='allow', strict=True)
    
    policy_type: PolicyType = Field(..., description="Policy type")
    action: str = Field(..., min_length=1, description="Action pattern")
    subject: Optional[str] = Field(None, description="Subject pattern")
    resource: Optional[str] = Field(None, description="Resource pattern")
    temporal: Optional[TemporalConstraint] = Field(None, description="Temporal constraints")
    conditions: Optional[Dict[str, Any]] = Field(None, description="Additional conditions")


class PolicyDecision(BaseModel):
    """Policy evaluation decision."""
    model_config = ConfigDict(extra='forbid', strict=True)
    
    decision: DecisionType = Field(..., description="Decision type")
    policy_cid: str = Field(..., pattern=r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$",
                           description="CID of evaluated policy")
    obligations: Optional[List[Dict[str, Any]]] = Field(None, description="Spawned obligations")
    witness: Optional[Dict[str, Any]] = Field(None, description="Evaluation witness data")


# ============================================================================
# Event DAG Models
# ============================================================================

class EventType(str, Enum):
    """Event types in DAG."""
    INVOCATION = "invocation"
    RESULT = "result"
    ERROR = "error"
    DELEGATION = "delegation"
    POLICY_DECISION = "policy_decision"
    INTENT = "intent"
    DECISION = "decision"
    RECEIPT = "receipt"
    ENVELOPE = "envelope"


class DAGEvent(BaseModel):
    """Event in the DAG."""
    model_config = ConfigDict(extra='allow', strict=True)
    
    event_type: Union[EventType, str] = Field(..., description="Event type")
    event_cid: str = Field(..., pattern=r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$",
                          description="CID of this event")
    parents: List[str] = Field(..., description="Parent event CIDs")
    timestamp: Union[str, float, int] = Field(..., description="ISO 8601 timestamp or epoch seconds")
    payload: Dict[str, Any] = Field(..., description="Event payload")


# ============================================================================
# Transport (Profile E) Models
# ============================================================================

class TransportProtocol(str, Enum):
    """Supported transport protocols."""
    MCP_P2P = "/mcp+p2p/1.0.0"


class TransportMessage(BaseModel):
    """Length-prefixed transport message."""
    model_config = ConfigDict(extra='forbid', strict=True)
    
    protocol_id: Literal["/mcp+p2p/1.0.0"] = Field(..., description="Protocol identifier")
    length: int = Field(..., gt=0, description="Message length in bytes")
    payload: Union[JSONRPCRequest, JSONRPCResponse, JSONRPCNotification] = Field(..., 
                                                                                  description="JSON-RPC payload")


class SessionState(str, Enum):
    """Transport session states."""
    CONNECTION = "connection"
    STREAM = "stream"
    INITIALIZATION = "initialization"
    READY = "ready"
    CLOSED = "closed"


class TransportSession(BaseModel):
    """Transport session."""
    model_config = ConfigDict(extra='allow', strict=True)
    
    session_id: str = Field(..., min_length=1, description="Session identifier")
    state: SessionState = Field(..., description="Current state")
    peer_address: str = Field(..., description="Peer multiaddr")
    capabilities: Optional[Dict[str, Any]] = Field(None, description="Negotiated capabilities")

"""
Transport Protocol Validator

Validates Profile E (mcp+p2p transport) according to docs/spec/transport-mcp-p2p.md
"""

from typing import Any, Dict
from .base_mcp import ValidationResult


class TransportValidator:
    """
    Validates mcp+p2p transport protocol compliance.
    
    Based on: docs/spec/transport-mcp-p2p.md
    """
    
    PROTOCOL_ID = "/mcp+p2p/1.0.0"
    
    def validate_protocol_id(self, protocol_id: str) -> ValidationResult:
        """
        Validate protocol identifier.
        
        Spec: transport-mcp-p2p.md:37-51
        Requirement: MUST define libp2p stream protocol identifiers
        
        Args:
            protocol_id: The protocol identifier string
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='protocol_id')
        
        if not protocol_id:
            result.add_error("Protocol ID cannot be empty")
            return result
        
        # Should start with /mcp+p2p/
        if not protocol_id.startswith('/mcp+p2p/'):
            result.add_warning(f"Protocol ID should start with '/mcp+p2p/': {protocol_id}")
        
        return result
    
    def validate_message_framing(self, frame: Dict[str, Any]) -> ValidationResult:
        """
        Validate message framing structure.
        
        Spec: transport-mcp-p2p.md:75-96
        Requirement: MUST define how messages are delimited/framed
        
        Args:
            frame: The message frame structure
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='message_frame')
        
        # Check for length prefix
        if 'length' not in frame:
            result.add_error("Frame missing 'length' field")
        else:
            length = frame['length']
            if not isinstance(length, int) or length < 0:
                result.add_error("Frame length must be a non-negative integer")
        
        # Check for message payload
        if 'message' not in frame:
            result.add_error("Frame missing 'message' payload")
        
        # Validate max message size
        if 'length' in frame and frame['length'] > 16 * 1024 * 1024:  # 16 MiB
            result.add_warning("Frame length exceeds recommended maximum (16 MiB)")
        
        return result
    
    def validate_session_lifecycle(self, session: Dict[str, Any]) -> ValidationResult:
        """
        Validate session lifecycle compliance.
        
        Spec: transport-mcp-p2p.md:53-61
        Requirement: MUST establish connection, open stream, run initialization
        
        Args:
            session: Session lifecycle information
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='session_lifecycle')
        
        required_phases = ['connection', 'stream', 'initialization']
        
        for phase in required_phases:
            if phase not in session:
                result.add_error(f"Session missing required phase: {phase}")
        
        # Validate connection phase
        if 'connection' in session:
            conn = session['connection']
            if 'peer_id' not in conn:
                result.add_error("Connection missing 'peer_id'")
        
        # Validate stream phase
        if 'stream' in session:
            stream = session['stream']
            if 'protocol_id' not in stream:
                result.add_error("Stream missing 'protocol_id'")
        
        # Validate initialization phase
        if 'initialization' in session:
            init = session['initialization']
            if 'handshake' not in init:
                result.add_error("Initialization missing 'handshake'")
        
        return result
    
    def validate_jsonrpc_preservation(
        self, 
        original: Dict[str, Any], 
        transported: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate that JSON-RPC semantics are preserved over transport.
        
        Spec: transport-mcp-p2p.md:60
        Requirement: MUST preserve MCP JSON-RPC semantics
        
        Args:
            original: Original JSON-RPC message
            transported: Message after transport
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='jsonrpc_preservation')
        
        # Check essential JSON-RPC fields are preserved
        jsonrpc_fields = ['jsonrpc', 'id', 'method']
        
        for field in jsonrpc_fields:
            if field in original:
                if field not in transported:
                    result.add_error(f"Field '{field}' lost during transport")
                elif original[field] != transported[field]:
                    result.add_error(f"Field '{field}' modified during transport")
        
        # Check params preservation
        if 'params' in original:
            if 'params' not in transported:
                result.add_error("Params lost during transport")
            # Deep comparison would be needed for full validation
        
        return result
    
    def validate_addressing(self, address: Dict[str, Any]) -> ValidationResult:
        """
        Validate peer addressing and discovery.
        
        Spec: transport-mcp-p2p.md:62-74
        Requirement: MAY use peer IDs and multiaddrs for addressing
        
        Args:
            address: Addressing information
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='addressing')
        
        # Should have peer_id
        if 'peer_id' not in address:
            result.add_warning("Address missing 'peer_id'")
        
        # Should have multiaddrs
        if 'multiaddrs' not in address:
            result.add_warning("Address missing 'multiaddrs'")
        elif not isinstance(address['multiaddrs'], list):
            result.add_error("'multiaddrs' must be a list")
        
        return result

"""
Integration tests for transport protocol (Profile E).

Tests validate compliance with docs/spec/transport-mcp-p2p.md
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from validators.transport import TransportValidator


class TestTransportProtocol:
    """Test mcp+p2p transport protocol validation."""
    
    @pytest.fixture
    def validator(self):
        return TransportValidator()
    
    def test_valid_protocol_id(self, validator):
        """
        Test validation of protocol identifier.
        
        Spec: transport-mcp-p2p.md:48
        Requirement: Protocol ID should be /mcp+p2p/1.0.0
        """
        protocol_id = "/mcp+p2p/1.0.0"
        
        result = validator.validate_protocol_id(protocol_id)
        
        assert result.is_valid
        assert result.message_type == "protocol_id"
    
    def test_custom_protocol_id_warning(self, validator):
        """
        Test that custom protocol IDs generate warnings.
        
        Spec: transport-mcp-p2p.md:44
        """
        protocol_id = "/custom-mcp/1.0.0"
        
        result = validator.validate_protocol_id(protocol_id)
        
        assert result.is_valid
        assert len(result.warnings) > 0
    
    def test_message_framing_length_prefix(self, validator):
        """
        Test validation of length-prefixed message framing.
        
        Spec: transport-mcp-p2p.md:86
        Requirement: SHOULD use length-prefixed framing
        """
        frame = {
            "length": 256,
            "message": {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        }
        
        result = validator.validate_message_framing(frame)
        
        assert result.is_valid
        assert result.message_type == "message_frame"
    
    def test_frame_missing_length(self, validator):
        """
        Test that frames must include length field.
        
        Spec: transport-mcp-p2p.md:80-82
        Requirement: MUST define how messages are delimited/framed
        """
        frame = {
            "message": {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        }
        
        result = validator.validate_message_framing(frame)
        
        assert not result.is_valid
        assert any("length" in error.lower() for error in result.errors)
    
    def test_frame_exceeds_maximum_size(self, validator):
        """
        Test warning for frames exceeding recommended size.
        
        Spec: transport-mcp-p2p.md:95
        Requirement: Should reject frames larger than configured maximum
        """
        frame = {
            "length": 20 * 1024 * 1024,  # 20 MiB
            "message": {"data": "large payload"}
        }
        
        result = validator.validate_message_framing(frame)
        
        assert len(result.warnings) > 0
        assert any("maximum" in warning.lower() for warning in result.warnings)
    
    def test_session_lifecycle_complete(self, validator):
        """
        Test validation of complete session lifecycle.
        
        Spec: transport-mcp-p2p.md:56-60
        Requirement: MUST establish connection, open stream, run initialization
        """
        session = {
            "connection": {
                "peer_id": "12D3KooWABC123",
                "multiaddr": "/ip4/192.168.1.1/tcp/4001"
            },
            "stream": {
                "protocol_id": "/mcp+p2p/1.0.0",
                "stream_id": "stream-1"
            },
            "initialization": {
                "handshake": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {}
                }
            }
        }
        
        result = validator.validate_session_lifecycle(session)
        
        assert result.is_valid
        assert result.message_type == "session_lifecycle"
    
    def test_session_missing_phase(self, validator):
        """
        Test that all session phases are required.
        
        Spec: transport-mcp-p2p.md:56-60
        """
        session = {
            "connection": {
                "peer_id": "12D3KooWABC123"
            }
            # Missing stream and initialization
        }
        
        result = validator.validate_session_lifecycle(session)
        
        assert not result.is_valid
        assert len(result.errors) >= 2
    
    def test_jsonrpc_preservation_over_transport(self, validator):
        """
        Test that JSON-RPC semantics are preserved.
        
        Spec: transport-mcp-p2p.md:60
        Requirement: MUST preserve MCP JSON-RPC semantics
        """
        original = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_weather"}
        }
        
        transported = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_weather"}
        }
        
        result = validator.validate_jsonrpc_preservation(original, transported)
        
        assert result.is_valid
        assert result.message_type == "jsonrpc_preservation"
    
    def test_jsonrpc_modified_during_transport(self, validator):
        """
        Test detection of JSON-RPC modification.
        
        Spec: transport-mcp-p2p.md:77
        Requirement: JSON-RPC payloads MUST be transmitted without semantic modification
        """
        original = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call"
        }
        
        transported = {
            "jsonrpc": "2.0",
            "id": 2,  # Modified
            "method": "tools/call"
        }
        
        result = validator.validate_jsonrpc_preservation(original, transported)
        
        assert not result.is_valid
        assert any("modified" in error.lower() for error in result.errors)
    
    def test_peer_addressing(self, validator):
        """
        Test validation of peer addressing.
        
        Spec: transport-mcp-p2p.md:65
        Requirement: MAY use peer IDs and multiaddrs for addressing
        """
        address = {
            "peer_id": "12D3KooWABC123",
            "multiaddrs": [
                "/ip4/192.168.1.1/tcp/4001",
                "/ip6/::1/tcp/4001"
            ]
        }
        
        result = validator.validate_addressing(address)
        
        assert result.is_valid
        assert result.message_type == "addressing"
    
    def test_multiaddrs_must_be_list(self, validator):
        """
        Test that multiaddrs must be a list.
        
        Spec: transport-mcp-p2p.md:65
        """
        address = {
            "peer_id": "12D3KooWABC123",
            "multiaddrs": "/ip4/192.168.1.1/tcp/4001"  # Should be list
        }
        
        result = validator.validate_addressing(address)
        
        assert not result.is_valid
        assert any("list" in error.lower() for error in result.errors)

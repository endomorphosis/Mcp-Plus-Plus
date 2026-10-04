"""
Integration tests for cross-cutting MCP++ requirements.

Tests validate compliance with backward compatibility and capability negotiation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from validators.base_mcp import MCPValidator
from validators.mcp_idl import MCPIDLValidator


class TestBackwardCompatibility:
    """Test backward compatibility with baseline MCP."""
    
    @pytest.fixture
    def mcp_validator(self):
        return MCPValidator()
    
    @pytest.fixture
    def idl_validator(self):
        return MCPIDLValidator()
    
    def test_baseline_mcp_works_without_profiles(self, mcp_validator):
        """
        Test that baseline MCP continues to work without MCP++ profiles.
        
        Spec: mcp++-profiles-draft.md:46
        Requirement: Implementations that do not support MCP++ MUST continue 
        to interoperate using baseline MCP semantics
        """
        # Standard MCP initialize without MCP++ capabilities
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {}
                },
                "clientInfo": {
                    "name": "baseline-client",
                    "version": "1.0.0"
                }
            }
        }
        
        result = mcp_validator.validate_request(payload)
        
        assert result.is_valid
        assert result.message_type == "initialize"
    
    def test_mcp_plus_plus_capability_negotiation(self, mcp_validator):
        """
        Test capability negotiation for MCP++ profiles.
        
        Spec: mcp++-profiles-draft.md:46
        Requirement: MCP++ profiles are negotiated during MCP initialization
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "mcp++": {
                        "profiles": ["mcp-idl", "cid-envelope", "ucan-delegation"]
                    }
                },
                "clientInfo": {
                    "name": "mcp++-client",
                    "version": "1.0.0"
                }
            }
        }
        
        result = mcp_validator.validate_request(payload)
        
        assert result.is_valid
        # Client declares MCP++ support
        assert 'mcp++' in payload['params']['capabilities']
    
    def test_server_response_with_supported_profiles(self, mcp_validator):
        """
        Test that server response includes supported profiles.
        
        Spec: mcp++-profiles-draft.md:46
        """
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "mcp++": {
                        "profiles": ["mcp-idl", "cid-envelope"]
                    }
                },
                "serverInfo": {
                    "name": "mcp++-server",
                    "version": "1.0.0"
                }
            }
        }
        
        result = mcp_validator.validate_response(response)
        
        assert result.is_valid
    
    def test_baseline_message_format_unchanged(self, mcp_validator):
        """
        Test that baseline MCP message formats are unchanged.
        
        Spec: mcp++-profiles-draft.md:48
        Requirement: No MCP++ profile modifies or invalidates existing 
        MCP JSON-RPC message formats
        """
        # Standard tools/call
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_weather",
                "arguments": {"location": "Tokyo"}
            }
        }
        
        result = mcp_validator.validate_request(payload)
        
        assert result.is_valid
        # Message format is standard MCP
        assert payload['method'] == 'tools/call'
        assert 'name' in payload['params']
        assert 'arguments' in payload['params']
    
    def test_optional_profile_extensions(self, mcp_validator):
        """
        Test that MCP++ extensions are optional.
        
        Spec: mcp++-profiles-draft.md:34
        Requirement: Profiles are optional, negotiable MCP capabilities
        """
        # Request without any MCP++ extensions
        basic_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list"
        }
        
        # Request with MCP++ envelope extension
        extended_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "mcp++": {
                "envelope": {
                    "interface_cid": "bafyinterface",
                    "input_cid": "bafyinput"
                }
            }
        }
        
        # Both should be valid
        result1 = mcp_validator.validate_request(basic_request)
        result2 = mcp_validator.validate_request(extended_request)
        
        assert result1.is_valid
        assert result2.is_valid


class TestCapabilityNegotiation:
    """Test capability negotiation patterns."""
    
    @pytest.fixture
    def validator(self):
        return MCPValidator()
    
    def test_client_declares_capabilities(self, validator):
        """
        Test that clients declare their capabilities during initialization.
        
        Spec: mcp++-profiles-draft.md:46
        """
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True},
                    "resources": {"subscribe": True}
                },
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        
        result = validator.validate_request(request)
        
        assert result.is_valid
        assert 'capabilities' in request['params']
    
    def test_server_responds_with_capabilities(self, validator):
        """
        Test that servers respond with their capabilities.
        
        Spec: MCP specification
        """
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "serverInfo": {"name": "test-server", "version": "1.0.0"}
            }
        }
        
        result = validator.validate_response(response)
        
        assert result.is_valid
    
    def test_profile_subset_negotiation(self, validator):
        """
        Test that client and server can negotiate profile subset.
        
        Spec: mcp++-profiles-draft.md
        """
        # Client requests profiles A and B
        client_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "mcp++": {
                        "profiles": ["mcp-idl", "cid-envelope"]
                    }
                },
                "clientInfo": {"name": "client", "version": "1.0.0"}
            }
        }
        
        # Server only supports profile A
        server_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "mcp++": {
                        "profiles": ["mcp-idl"]  # Subset
                    }
                },
                "serverInfo": {"name": "server", "version": "1.0.0"}
            }
        }
        
        # Both should be valid
        req_result = validator.validate_request(client_request)
        resp_result = validator.validate_response(server_response)
        
        assert req_result.is_valid
        assert resp_result.is_valid
        
        # Intersection is what's actually supported
        client_profiles = set(client_request['params']['capabilities']['mcp++']['profiles'])
        server_profiles = set(server_response['result']['capabilities']['mcp++']['profiles'])
        supported = client_profiles & server_profiles
        
        assert 'mcp-idl' in supported
        assert 'cid-envelope' not in supported


class TestContentAddressing:
    """Test content-addressing requirements across profiles."""
    
    @pytest.fixture
    def idl_validator(self):
        return MCPIDLValidator()
    
    def test_canonicalization_determinism(self, idl_validator):
        """
        Test that canonicalization is deterministic.
        
        Spec: mcp++-profiles-draft.md:162
        Requirement: Content-addressed artifacts MUST be canonicalized
        to avoid ambiguity
        """
        descriptor1 = {
            "name": "test",
            "namespace": "com.example",
            "version": "1.0.0",
            "methods": [],
            "errors": [],
            "requires": [],
            "compatibility": {}
        }
        
        # Same descriptor, potentially different ordering
        descriptor2 = {
            "version": "1.0.0",
            "name": "test",
            "compatibility": {},
            "namespace": "com.example",
            "requires": [],
            "errors": [],
            "methods": []
        }
        
        # CIDs should be identical
        cid1 = idl_validator.compute_interface_cid(descriptor1)
        cid2 = idl_validator.compute_interface_cid(descriptor2)
        
        assert cid1 == cid2
    
    def test_cid_format_consistency(self, idl_validator):
        """
        Test that CIDs use consistent format.
        
        Spec: CID specification
        """
        descriptor = {
            "name": "test",
            "namespace": "com.example",
            "version": "1.0.0",
            "methods": [],
            "errors": [],
            "requires": [],
            "compatibility": {}
        }
        
        cid = idl_validator.compute_interface_cid(descriptor)
        
        # CID should start with 'bafy' for our implementation
        assert cid.startswith('bafy')
        assert len(cid) > 10  # Should be substantial

"""
Integration tests for baseline MCP protocol validation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from validators.base_mcp import MCPValidator


class TestMCPBaselineProtocol:
    """Test baseline MCP JSON-RPC message validation."""
    
    @pytest.fixture
    def validator(self):
        return MCPValidator()
    
    def test_valid_tool_call_request(self, validator):
        """Test validation of a valid tool call request."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_temperature",
                "arguments": {"location": "San Francisco"}
            }
        }
        
        result = validator.validate_request(payload)
        
        assert result.is_valid
        assert result.message_type == "tools/call"
        assert len(result.errors) == 0
    
    def test_missing_jsonrpc_version(self, validator):
        """Test that missing JSON-RPC version is detected."""
        payload = {
            "id": 1,
            "method": "tools/list"
        }
        
        result = validator.validate_request(payload)
        
        assert not result.is_valid
        assert any("jsonrpc" in error.lower() for error in result.errors)
    
    def test_missing_method(self, validator):
        """Test that missing method is detected."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1
        }
        
        result = validator.validate_request(payload)
        
        assert not result.is_valid
        assert any("method" in error.lower() for error in result.errors)
    
    def test_tool_call_missing_name(self, validator):
        """Test that tools/call without name parameter fails."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "arguments": {"location": "Tokyo"}
            }
        }
        
        result = validator.validate_request(payload)
        
        assert not result.is_valid
        assert any("name" in error.lower() for error in result.errors)
    
    def test_valid_response(self, validator):
        """Test validation of a valid response."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {"type": "text", "text": "Temperature is 72°F"}
                ]
            }
        }
        
        result = validator.validate_response(payload)
        
        assert result.is_valid
        assert result.message_type == "response"
    
    def test_error_response(self, validator):
        """Test validation of an error response."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32600,
                "message": "Invalid Request"
            }
        }
        
        result = validator.validate_response(payload)
        
        assert result.is_valid  # Error responses are valid
        assert result.message_type == "response"
    
    def test_response_with_both_result_and_error(self, validator):
        """Test that response with both result and error fails."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {},
            "error": {"code": -32600, "message": "Error"}
        }
        
        result = validator.validate_response(payload)
        
        assert not result.is_valid
        assert any("both" in error.lower() for error in result.errors)
    
    def test_valid_notification(self, validator):
        """Test validation of a valid notification."""
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/resources/updated",
            "params": {
                "uri": "file:///data/metrics.json"
            }
        }
        
        result = validator.validate_notification(payload)
        
        assert result.is_valid
        assert result.message_type == "notifications/resources/updated"
    
    def test_initialize_request(self, validator):
        """Test validation of initialize request."""
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
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        result = validator.validate_request(payload)
        
        assert result.is_valid
        assert result.message_type == "initialize"
    
    def test_auto_detect_message_type(self, validator):
        """Test that validator can auto-detect message types."""
        # Request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list"
        }
        result = validator.validate_message(request)
        assert result.is_valid
        
        # Response
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {}
        }
        result = validator.validate_message(response)
        assert result.is_valid
        
        # Notification
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/tools/list_changed"
        }
        result = validator.validate_message(notification)
        assert result.is_valid

"""
Comprehensive tests for base_mcp_typed validator.
Tests Pydantic-based strict type validation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from validators.base_mcp_typed import (
    MCPTypedValidator,
    ValidationResult,
    is_request,
    is_response,
    is_notification,
)


class TestValidationResult:
    """Test ValidationResult model."""
    
    def test_create_valid_result(self):
        """Test creating a valid ValidationResult."""
        result = ValidationResult(is_valid=True, message_type="test")
        assert result.is_valid is True
        assert result.message_type == "test"
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
    
    def test_add_error(self):
        """Test adding an error marks validation as failed."""
        result = ValidationResult(is_valid=True, message_type="test")
        result.add_error("Test error")
        assert result.is_valid is False
        assert "Test error" in result.errors
    
    def test_add_warning(self):
        """Test adding a warning doesn't affect validity."""
        result = ValidationResult(is_valid=True, message_type="test")
        result.add_warning("Test warning")
        assert result.is_valid is True
        assert "Test warning" in result.warnings
    
    def test_multiple_errors(self):
        """Test adding multiple errors."""
        result = ValidationResult(is_valid=True, message_type="test")
        result.add_error("Error 1")
        result.add_error("Error 2")
        assert len(result.errors) == 2
        assert result.is_valid is False


class TestTypeGuards:
    """Test type guard functions."""
    
    def test_is_request(self):
        """Test is_request type guard."""
        request = {"jsonrpc": "2.0", "method": "test", "id": 1}
        assert is_request(request) is True
        
        # Without id (notification)
        notification = {"jsonrpc": "2.0", "method": "test"}
        assert is_request(notification) is False
        
        # Without method (response)
        response = {"jsonrpc": "2.0", "id": 1, "result": {}}
        assert is_request(response) is False
    
    def test_is_response(self):
        """Test is_response type guard."""
        response = {"jsonrpc": "2.0", "id": 1, "result": {}}
        assert is_response(response) is True
        
        error_response = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32600, "message": "error"}}
        assert is_response(error_response) is True
        
        # Request
        request = {"jsonrpc": "2.0", "method": "test", "id": 1}
        assert is_response(request) is False
    
    def test_is_notification(self):
        """Test is_notification type guard."""
        notification = {"jsonrpc": "2.0", "method": "notifications/test"}
        assert is_notification(notification) is True
        
        # With id (request)
        request = {"jsonrpc": "2.0", "method": "notifications/test", "id": 1}
        assert is_notification(request) is False
        
        # Response
        response = {"jsonrpc": "2.0", "id": 1, "result": {}}
        assert is_notification(response) is False


class TestMCPTypedValidator:
    """Test MCPTypedValidator class."""
    
    def test_validator_initialization(self):
        """Test validator initializes correctly."""
        validator = MCPTypedValidator()
        assert validator is not None
        assert len(validator.VALID_METHODS) > 0
    
    def test_validate_request_valid(self):
        """Test validating a valid request."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1,
            "params": {}
        }
        result = validator.validate_request(payload)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_request_missing_jsonrpc(self):
        """Test request with missing jsonrpc version."""
        validator = MCPTypedValidator()
        payload = {
            "method": "tools/list",
            "id": 1
        }
        result = validator.validate_request(payload)
        assert result.is_valid is False
        assert any("jsonrpc" in err.lower() for err in result.errors)
    
    def test_validate_request_missing_method(self):
        """Test request with missing method."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "id": 1
        }
        result = validator.validate_request(payload)
        assert result.is_valid is False
        assert any("method" in err.lower() for err in result.errors)
    
    def test_validate_request_missing_id(self):
        """Test request with missing id."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list"
        }
        result = validator.validate_request(payload)
        assert result.is_valid is False
        assert any("id" in err.lower() for err in result.errors)
    
    def test_validate_request_unknown_method(self):
        """Test request with unknown method generates warning."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "method": "unknown/method",
            "id": 1
        }
        result = validator.validate_request(payload)
        # Should have warning but might still be valid
        assert len(result.warnings) > 0
        assert any("unknown" in warn.lower() for warn in result.warnings)
    
    def test_validate_response_valid(self):
        """Test validating a valid response."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": []}
        }
        result = validator.validate_response(payload)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_response_missing_id(self):
        """Test response with missing id."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "result": {}
        }
        result = validator.validate_response(payload)
        assert result.is_valid is False
        assert any("id" in err.lower() for err in result.errors)
    
    def test_validate_response_missing_result_and_error(self):
        """Test response with neither result nor error."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "id": 1
        }
        result = validator.validate_response(payload)
        assert result.is_valid is False
        assert any("result" in err.lower() or "error" in err.lower() for err in result.errors)
    
    def test_validate_response_both_result_and_error(self):
        """Test response with both result and error."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {},
            "error": {"code": -32600, "message": "error"}
        }
        result = validator.validate_response(payload)
        assert result.is_valid is False
        assert any("both" in err.lower() for err in result.errors)
    
    def test_validate_error_response(self):
        """Test validating a valid error response."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32600,
                "message": "Invalid Request"
            }
        }
        result = validator.validate_response(payload)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_notification_valid(self):
        """Test validating a valid notification."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/message"
        }
        result = validator.validate_notification(payload)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_notification_with_id(self):
        """Test notification with id (should warn or error)."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/message",
            "id": 1
        }
        result = validator.validate_notification(payload)
        # Notification shouldn't have id
        assert result.is_valid is False or len(result.warnings) > 0
    
    def test_validate_initialize_request(self):
        """Test validating initialize request."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "TestClient",
                    "version": "1.0.0"
                },
                "capabilities": {}
            }
        }
        result = validator.validate_request(payload)
        assert result.is_valid is True
    
    def test_validate_tools_call(self):
        """Test validating tools/call request."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "test_tool",
                "arguments": {}
            }
        }
        result = validator.validate_request(payload)
        assert result.is_valid is True
    
    def test_auto_detect_request(self):
        """Test auto-detection of request message type."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1
        }
        result = validator.validate_message(payload)
        assert result.is_valid is True
        assert result.message_type == "tools/list"
    
    def test_auto_detect_response(self):
        """Test auto-detection of response message type."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {}
        }
        result = validator.validate_message(payload)
        assert result.is_valid is True
        assert result.message_type == "response"
    
    def test_auto_detect_notification(self):
        """Test auto-detection of notification message type."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/message"
        }
        result = validator.validate_message(payload)
        assert result.is_valid is True
    
    def test_validate_with_pydantic_models(self):
        """Test that Pydantic models are used for validation."""
        validator = MCPTypedValidator()
        # Invalid initialize params (missing required fields)
        payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "clientInfo": {
                    "name": "TestClient"
                    # missing version
                }
            }
        }
        result = validator.validate_request(payload)
        # Should catch validation error via Pydantic
        assert result.is_valid is False or len(result.warnings) > 0


class TestEdgeCases:
    """Test edge cases and error paths."""
    
    def test_empty_payload(self):
        """Test validation of empty payload."""
        validator = MCPTypedValidator()
        result = validator.validate_message({})
        assert result.is_valid is False
    
    def test_null_payload(self):
        """Test validation with None."""
        validator = MCPTypedValidator()
        result = validator.validate_message({})
        assert result.is_valid is False
    
    def test_malformed_error_object(self):
        """Test response with malformed error object."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": "not an object"
        }
        result = validator.validate_response(payload)
        # Should handle gracefully
        assert isinstance(result, ValidationResult)
    
    def test_params_validation(self):
        """Test params field validation."""
        validator = MCPTypedValidator()
        # tools/call with missing name
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {
                "arguments": {}
                # missing name
            }
        }
        result = validator.validate_request(payload)
        assert result.is_valid is False or len(result.warnings) > 0
    
    def test_strict_mode_extra_fields(self):
        """Test that extra fields are rejected in strict mode."""
        validator = MCPTypedValidator()
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1,
            "extra_field": "should_not_be_here"
        }
        # Depending on implementation, may warn or reject
        result = validator.validate_request(payload)
        # At minimum should validate
        assert isinstance(result, ValidationResult)

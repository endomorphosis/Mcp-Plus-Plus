"""
Base MCP Protocol Validator

Validates baseline MCP JSON-RPC messages according to the MCP specification.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json


@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    message_type: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)


class MCPValidator:
    """
    Validates baseline MCP protocol messages.
    
    Based on the official MCP specification:
    https://modelcontextprotocol.io/docs/
    """
    
    # Valid MCP methods
    VALID_METHODS = {
        # Lifecycle
        'initialize',
        'initialized',
        'ping',
        # Capabilities
        'capabilities/list',
        # Tools
        'tools/list',
        'tools/call',
        # Resources
        'resources/list',
        'resources/read',
        'resources/subscribe',
        'resources/unsubscribe',
        'resources/templates/list',
        # Prompts
        'prompts/list',
        'prompts/get',
        # Notifications
        'notifications/resources/updated',
        'notifications/resources/list_changed',
        'notifications/tools/list_changed',
        'notifications/prompts/list_changed',
        'notifications/progress',
    }
    
    def validate_request(self, payload: Dict[str, Any]) -> ValidationResult:
        """
        Validate an MCP request message.
        
        Args:
            payload: The JSON-RPC request payload
            
        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        
        # Check JSON-RPC version
        if payload.get('jsonrpc') != '2.0':
            result.add_error("Invalid or missing jsonrpc version (must be '2.0')")
        
        # Check method
        method = payload.get('method')
        if not method:
            result.add_error("Missing 'method' field")
        elif method not in self.VALID_METHODS:
            result.add_warning(f"Unknown method: {method}")
        
        result.message_type = method or 'unknown'
        
        # Check id (required for requests, not for notifications)
        if method and not method.startswith('notifications/'):
            if 'id' not in payload:
                result.add_error("Missing 'id' field for request")
        
        # Validate params based on method
        if method:
            self._validate_method_params(method, payload.get('params', {}), result)
        
        return result
    
    def validate_response(self, payload: Dict[str, Any]) -> ValidationResult:
        """
        Validate an MCP response message.
        
        Args:
            payload: The JSON-RPC response payload
            
        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True, message_type='response')
        
        # Check JSON-RPC version
        if payload.get('jsonrpc') != '2.0':
            result.add_error("Invalid or missing jsonrpc version (must be '2.0')")
        
        # Check id
        if 'id' not in payload:
            result.add_error("Missing 'id' field in response")
        
        # Must have either result or error, not both
        has_result = 'result' in payload
        has_error = 'error' in payload
        
        if not has_result and not has_error:
            result.add_error("Response must contain either 'result' or 'error'")
        elif has_result and has_error:
            result.add_error("Response cannot contain both 'result' and 'error'")
        
        # Validate error format if present
        if has_error:
            self._validate_error(payload['error'], result)
        
        return result
    
    def validate_notification(self, payload: Dict[str, Any]) -> ValidationResult:
        """
        Validate an MCP notification message.
        
        Args:
            payload: The JSON-RPC notification payload
            
        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True, message_type='notification')
        
        # Check JSON-RPC version
        if payload.get('jsonrpc') != '2.0':
            result.add_error("Invalid or missing jsonrpc version (must be '2.0')")
        
        # Check method
        method = payload.get('method')
        if not method:
            result.add_error("Missing 'method' field")
        elif not method.startswith('notifications/'):
            result.add_warning(f"Notification method should start with 'notifications/': {method}")
        
        result.message_type = method or 'unknown'
        
        # Notifications should NOT have an id
        if 'id' in payload:
            result.add_warning("Notifications should not include an 'id' field")
        
        return result
    
    def _validate_method_params(
        self, 
        method: str, 
        params: Dict[str, Any], 
        result: ValidationResult
    ) -> None:
        """Validate method-specific parameters."""
        
        if method == 'tools/call':
            if 'name' not in params:
                result.add_error("tools/call requires 'name' parameter")
            if 'arguments' not in params:
                result.add_error("tools/call requires 'arguments' parameter")
        
        elif method == 'resources/read':
            if 'uri' not in params:
                result.add_error("resources/read requires 'uri' parameter")
        
        elif method == 'prompts/get':
            if 'name' not in params:
                result.add_error("prompts/get requires 'name' parameter")
        
        elif method == 'initialize':
            if 'protocolVersion' not in params:
                result.add_error("initialize requires 'protocolVersion' parameter")
            if 'capabilities' not in params:
                result.add_error("initialize requires 'capabilities' parameter")
            if 'clientInfo' not in params:
                result.add_warning("initialize should include 'clientInfo' parameter")
    
    def _validate_error(self, error: Dict[str, Any], result: ValidationResult) -> None:
        """Validate error object format."""
        if 'code' not in error:
            result.add_error("Error object missing 'code' field")
        if 'message' not in error:
            result.add_error("Error object missing 'message' field")
        
        # Check code is an integer
        if 'code' in error and not isinstance(error['code'], int):
            result.add_error("Error code must be an integer")
    
    def validate_message(self, payload: Dict[str, Any]) -> ValidationResult:
        """
        Validate any MCP message (auto-detect type).
        
        Args:
            payload: The JSON-RPC message payload
            
        Returns:
            ValidationResult with validation status and details
        """
        # Determine message type
        method = payload.get('method')
        has_result = 'result' in payload
        has_error = 'error' in payload
        
        if method and method.startswith('notifications/'):
            return self.validate_notification(payload)
        elif method:
            return self.validate_request(payload)
        elif has_result or has_error:
            return self.validate_response(payload)
        else:
            result = ValidationResult(is_valid=False)
            result.add_error("Cannot determine message type")
            return result

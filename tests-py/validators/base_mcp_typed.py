"""
Base MCP Protocol Validator with Advanced Type Safety

Uses Pydantic v2 for runtime validation and mypy for static type checking.
Provides strict type enforcement for MCP protocol messages.
"""

from typing import Any, Dict, List, Optional, Protocol, TypeGuard, Union, cast
from pydantic import BaseModel, ValidationError, Field
import json

from .models import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCNotification,
    JSONRPCError,
    InitializeParams,
    ToolCallParams,
    ResourceReadParams,
    PromptGetParams,
    ClientInfo,
    ServerInfo,
    Capabilities,
)


class ValidationResult(BaseModel):
    """Result of a validation check with strict typing."""
    is_valid: bool = Field(..., description="Whether validation passed")
    message_type: str = Field(default="", description="Type of message validated")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    def add_error(self, error: str) -> None:
        """Add an error message and mark validation as failed."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)


class MCPMessage(Protocol):
    """Protocol for MCP messages."""
    jsonrpc: str


def is_request(payload: Dict[str, Any]) -> TypeGuard[Dict[str, Any]]:
    """Type guard to check if payload is a request."""
    return 'method' in payload and 'id' in payload and not payload.get('method', '').startswith('notifications/')


def is_response(payload: Dict[str, Any]) -> TypeGuard[Dict[str, Any]]:
    """Type guard to check if payload is a response."""
    return ('result' in payload or 'error' in payload) and 'id' in payload


def is_notification(payload: Dict[str, Any]) -> TypeGuard[Dict[str, Any]]:
    """Type guard to check if payload is a notification."""
    return 'method' in payload and 'id' not in payload


class MCPTypedValidator:
    """
    Type-safe validator for baseline MCP protocol messages.
    
    Uses Pydantic models for runtime validation and provides
    type guards for static type checking with mypy.
    
    Based on the official MCP specification:
    https://modelcontextprotocol.io/docs/
    """
    
    # Valid MCP methods (comprehensive list)
    VALID_METHODS: frozenset[str] = frozenset({
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
    })
    
    def validate_request(self, payload: Dict[str, Any]) -> ValidationResult:
        """
        Validate an MCP request message with Pydantic models.
        
        Args:
            payload: The JSON-RPC request payload
            
        Returns:
            ValidationResult with validation status and details
            
        Raises:
            ValidationError: If payload doesn't match JSONRPCRequest schema
        """
        result = ValidationResult(is_valid=True, message_type='request')
        
        try:
            # Validate against Pydantic model
            request = JSONRPCRequest.model_validate(payload)
            result.message_type = request.method
            
            # Check if method is known
            if request.method not in self.VALID_METHODS:
                result.add_warning(f"Unknown method: {request.method}")
            
            # Validate method-specific parameters
            if request.params:
                self._validate_method_params_typed(request.method, request.params, result)
            
        except ValidationError as e:
            result.is_valid = False
            for error in e.errors():
                field = '.'.join(str(loc) for loc in error['loc'])
                result.add_error(f"{field}: {error['msg']}")
        
        return result
    
    def validate_response(self, payload: Dict[str, Any]) -> ValidationResult:
        """
        Validate an MCP response message with Pydantic models.
        
        Args:
            payload: The JSON-RPC response payload
            
        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True, message_type='response')
        
        try:
            # Validate against Pydantic model
            response = JSONRPCResponse.model_validate(payload)
            
            # Additional validation is handled by Pydantic model validators
            if response.error:
                result.metadata['has_error'] = True
                result.metadata['error_code'] = response.error.code
            else:
                result.metadata['has_result'] = True
                
        except ValidationError as e:
            result.is_valid = False
            for error in e.errors():
                field = '.'.join(str(loc) for loc in error['loc'])
                result.add_error(f"{field}: {error['msg']}")
        
        return result
    
    def validate_notification(self, payload: Dict[str, Any]) -> ValidationResult:
        """
        Validate an MCP notification message with Pydantic models.
        
        Args:
            payload: The JSON-RPC notification payload
            
        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True, message_type='notification')
        
        try:
            # Validate against Pydantic model
            notification = JSONRPCNotification.model_validate(payload)
            result.message_type = notification.method
            
            # Check if it's a valid notification method
            if notification.method not in self.VALID_METHODS:
                result.add_warning(f"Unknown notification method: {notification.method}")
                
        except ValidationError as e:
            result.is_valid = False
            for error in e.errors():
                field = '.'.join(str(loc) for loc in error['loc'])
                result.add_error(f"{field}: {error['msg']}")
        
        return result
    
    def _validate_method_params_typed(
        self, 
        method: str, 
        params: Dict[str, Any], 
        result: ValidationResult
    ) -> None:
        """Validate method-specific parameters using Pydantic models."""
        
        try:
            if method == 'tools/call':
                ToolCallParams.model_validate(params)
            
            elif method == 'resources/read':
                ResourceReadParams.model_validate(params)
            
            elif method == 'prompts/get':
                PromptGetParams.model_validate(params)
            
            elif method == 'initialize':
                InitializeParams.model_validate(params)
                
        except ValidationError as e:
            for error in e.errors():
                field = '.'.join(str(loc) for loc in error['loc'])
                result.add_error(f"params.{field}: {error['msg']}")
    
    def validate_message(self, payload: Dict[str, Any]) -> ValidationResult:
        """
        Validate any MCP message (auto-detect type) with type guards.
        
        Args:
            payload: The JSON-RPC message payload
            
        Returns:
            ValidationResult with validation status and details
        """
        # Use type guards to determine message type
        if is_notification(payload):
            return self.validate_notification(payload)
        elif is_request(payload):
            return self.validate_request(payload)
        elif is_response(payload):
            return self.validate_response(payload)
        else:
            result = ValidationResult(is_valid=False, message_type='unknown')
            result.add_error("Cannot determine message type")
            return result
    
    def validate_json_string(self, json_str: str) -> ValidationResult:
        """
        Validate a JSON string as an MCP message.
        
        Args:
            json_str: JSON string to validate
            
        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        
        try:
            payload = json.loads(json_str)
            return self.validate_message(payload)
        except json.JSONDecodeError as e:
            result.is_valid = False
            result.add_error(f"Invalid JSON: {e}")
            return result


# Convenience functions for one-off validations

def validate_mcp_request(payload: Dict[str, Any]) -> ValidationResult:
    """Validate an MCP request (convenience function)."""
    validator = MCPTypedValidator()
    return validator.validate_request(payload)


def validate_mcp_response(payload: Dict[str, Any]) -> ValidationResult:
    """Validate an MCP response (convenience function)."""
    validator = MCPTypedValidator()
    return validator.validate_response(payload)


def validate_mcp_notification(payload: Dict[str, Any]) -> ValidationResult:
    """Validate an MCP notification (convenience function)."""
    validator = MCPTypedValidator()
    return validator.validate_notification(payload)


def validate_mcp_message(payload: Dict[str, Any]) -> ValidationResult:
    """Validate any MCP message (convenience function)."""
    validator = MCPTypedValidator()
    return validator.validate_message(payload)

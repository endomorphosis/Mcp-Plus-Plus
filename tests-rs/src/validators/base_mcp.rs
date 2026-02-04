//! Base MCP Protocol Validator
//!
//! Validates baseline MCP protocol messages according to the specification.
//! SPEC: Model Context Protocol specification

use crate::models::*;
use serde_json::Value;
use serde_valid::Validate;
use std::collections::HashSet;
use thiserror::Error;

/// Validation error types
#[derive(Debug, Error)]
pub enum ValidationError {
    #[error("Invalid JSON-RPC version: {0}")]
    InvalidJSONRPCVersion(String),
    
    #[error("Invalid method: {0}")]
    InvalidMethod(String),
    
    #[error("Missing required field: {0}")]
    MissingField(String),
    
    #[error("Validation failed: {0}")]
    ValidationFailed(String),
    
    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),
    
    #[error("Serde validation error: {0}")]
    SerdeValidError(String),
}

/// Result of validation
#[derive(Debug, Clone)]
pub struct ValidationResult {
    pub is_valid: bool,
    pub message_type: String,
    pub errors: Vec<String>,
    pub warnings: Vec<String>,
}

impl ValidationResult {
    pub fn new(message_type: String) -> Self {
        Self {
            is_valid: true,
            message_type,
            errors: Vec::new(),
            warnings: Vec::new(),
        }
    }
    
    pub fn add_error(&mut self, error: String) {
        self.errors.push(error);
        self.is_valid = false;
    }
    
    pub fn add_warning(&mut self, warning: String) {
        self.warnings.push(warning);
    }
}

/// Base MCP Protocol Validator
///
/// Validates MCP protocol messages according to the official specification.
/// Provides strong type checking using Rust's type system and serde validation.
pub struct MCPValidator {
    valid_methods: HashSet<String>,
}

impl Default for MCPValidator {
    fn default() -> Self {
        Self::new()
    }
}

impl MCPValidator {
    /// Create a new validator with all valid MCP methods
    pub fn new() -> Self {
        let valid_methods = vec![
            // Lifecycle
            "initialize",
            "initialized",
            "ping",
            // Capabilities
            "capabilities/list",
            // Tools
            "tools/list",
            "tools/call",
            // Resources
            "resources/list",
            "resources/read",
            "resources/subscribe",
            "resources/unsubscribe",
            "resources/templates/list",
            // Prompts
            "prompts/list",
            "prompts/get",
            // Notifications
            "notifications/resources/updated",
            "notifications/resources/list_changed",
            "notifications/tools/list_changed",
            "notifications/prompts/list_changed",
            // Logging
            "logging/setLevel",
            // Sampling
            "sampling/createMessage",
            // Completion
            "completion/complete",
        ]
        .into_iter()
        .map(String::from)
        .collect();
        
        Self { valid_methods }
    }
    
    /// Validate a JSON-RPC request
    pub fn validate_request(&self, payload: &Value) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("request".to_string());
        
        // Try to deserialize as JSONRPCRequest
        let request: JSONRPCRequest = serde_json::from_value(payload.clone())?;
        
        // Validate using serde_valid
        if let Err(e) = request.validate() {
            result.add_error(format!("Validation error: {}", e));
            return Ok(result);
        }
        
        // Check method validity
        if !self.valid_methods.contains(&request.method) {
            result.add_warning(format!("Unknown method: {}", request.method));
        }
        
        // Validate method-specific parameters
        match request.method.as_str() {
            "initialize" => {
                if let Some(params) = &request.params {
                    if let Err(e) = self.validate_initialize_params(params) {
                        result.add_error(e.to_string());
                    }
                }
            }
            "tools/call" => {
                if let Some(params) = &request.params {
                    if let Err(e) = self.validate_tool_call_params(params) {
                        result.add_error(e.to_string());
                    }
                }
            }
            "resources/read" => {
                if let Some(params) = &request.params {
                    if let Err(e) = self.validate_resource_read_params(params) {
                        result.add_error(e.to_string());
                    }
                }
            }
            "prompts/get" => {
                if let Some(params) = &request.params {
                    if let Err(e) = self.validate_prompt_get_params(params) {
                        result.add_error(e.to_string());
                    }
                }
            }
            _ => {}
        }
        
        Ok(result)
    }
    
    /// Validate a JSON-RPC response
    pub fn validate_response(&self, payload: &Value) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("response".to_string());
        
        // Try to deserialize as JSONRPCResponse
        let response: JSONRPCResponse = serde_json::from_value(payload.clone())?;
        
        // Validate using serde_valid
        if let Err(e) = response.validate() {
            result.add_error(format!("Validation error: {}", e));
            return Ok(result);
        }
        
        // Must have either result or error, not both
        match (&response.result, &response.error) {
            (Some(_), Some(_)) => {
                result.add_error("Response cannot have both result and error".to_string());
            }
            (None, None) => {
                result.add_error("Response must have either result or error".to_string());
            }
            _ => {}
        }
        
        Ok(result)
    }
    
    /// Validate a JSON-RPC notification
    pub fn validate_notification(
        &self,
        payload: &Value,
    ) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("notification".to_string());
        
        // Try to deserialize as JSONRPCNotification
        let notification: JSONRPCNotification = serde_json::from_value(payload.clone())?;
        
        // Validate using serde_valid
        if let Err(e) = notification.validate() {
            result.add_error(format!("Validation error: {}", e));
            return Ok(result);
        }
        
        Ok(result)
    }
    
    /// Validate initialize parameters
    fn validate_initialize_params(&self, params: &Value) -> Result<(), ValidationError> {
        let init_params: InitializeParams = serde_json::from_value(params.clone())?;
        init_params
            .validate()
            .map_err(|e| ValidationError::SerdeValidError(e.to_string()))?;
        Ok(())
    }
    
    /// Validate tool call parameters
    fn validate_tool_call_params(&self, params: &Value) -> Result<(), ValidationError> {
        let tool_params: ToolCallParams = serde_json::from_value(params.clone())?;
        tool_params
            .validate()
            .map_err(|e| ValidationError::SerdeValidError(e.to_string()))?;
        Ok(())
    }
    
    /// Validate resource read parameters
    fn validate_resource_read_params(&self, params: &Value) -> Result<(), ValidationError> {
        let resource_params: ResourceReadParams = serde_json::from_value(params.clone())?;
        resource_params
            .validate()
            .map_err(|e| ValidationError::SerdeValidError(e.to_string()))?;
        Ok(())
    }
    
    /// Validate prompt get parameters
    fn validate_prompt_get_params(&self, params: &Value) -> Result<(), ValidationError> {
        let prompt_params: PromptGetParams = serde_json::from_value(params.clone())?;
        prompt_params
            .validate()
            .map_err(|e| ValidationError::SerdeValidError(e.to_string()))?;
        Ok(())
    }
    
    /// Check if payload is a request (has method and id)
    pub fn is_request(payload: &Value) -> bool {
        payload.get("method").is_some()
            && payload.get("id").is_some()
            && !payload
                .get("method")
                .and_then(Value::as_str)
                .unwrap_or("")
                .starts_with("notifications/")
    }
    
    /// Check if payload is a response (has result or error, and id)
    pub fn is_response(payload: &Value) -> bool {
        (payload.get("result").is_some() || payload.get("error").is_some())
            && payload.get("id").is_some()
    }
    
    /// Check if payload is a notification (has method but no id)
    pub fn is_notification(payload: &Value) -> bool {
        payload.get("method").is_some() && payload.get("id").is_none()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    
    #[test]
    fn test_valid_request() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(result.is_valid);
        assert_eq!(result.message_type, "request");
    }
    
    #[test]
    fn test_invalid_jsonrpc_version() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "1.0",
            "method": "tools/list",
            "id": 1
        });
        
        // Validation catches incorrect version in the result
        let result = validator.validate_request(&payload).unwrap();
        assert!(!result.is_valid, "Should be invalid due to wrong JSON-RPC version");
    }
    
    #[test]
    fn test_valid_response() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "result": {"tools": []},
            "id": 1
        });
        
        let result = validator.validate_response(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_is_request() {
        let payload = json!({
            "method": "tools/list",
            "id": 1
        });
        assert!(MCPValidator::is_request(&payload));
    }
    
    #[test]
    fn test_is_response() {
        let payload = json!({
            "result": {},
            "id": 1
        });
        assert!(MCPValidator::is_response(&payload));
    }
    
    #[test]
    fn test_is_notification() {
        let payload = json!({
            "method": "notifications/test"
        });
        assert!(MCPValidator::is_notification(&payload));
    }
    
    // Additional comprehensive tests for better coverage
    
    #[test]
    fn test_request_missing_jsonrpc() {
        let validator = MCPValidator::new();
        let payload = json!({
            "method": "tools/list",
            "id": 1
        });
        
        let result = validator.validate_request(&payload);
        assert!(result.is_err(), "Should fail due to missing jsonrpc field");
    }
    
    #[test]
    fn test_request_missing_method() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "id": 1
        });
        
        let result = validator.validate_request(&payload);
        assert!(result.is_err(), "Should fail due to missing method");
    }
    
    #[test]
    fn test_request_missing_id() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "tools/list"
        });
        
        let result = validator.validate_request(&payload);
        assert!(result.is_err(), "Should fail due to missing id");
    }
    
    #[test]
    fn test_request_empty_method() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "",
            "id": 1
        });
        
        // Empty method fails validation due to min_length constraint
        let result = validator.validate_request(&payload).unwrap();
        assert!(!result.is_valid, "Empty method should be invalid");
        assert!(!result.errors.is_empty());
    }
    
    #[test]
    fn test_request_with_string_id() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": "request-123"
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_request_unknown_method_warning() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "unknown/method",
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(result.is_valid);
        assert!(!result.warnings.is_empty(), "Should have warning for unknown method");
    }
    
    #[test]
    fn test_request_with_params() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {"filters": ["test"]},
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_initialize_request_valid() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocol_version": "1.0.0",
                "client_info": {
                    "name": "test-client",
                    "version": "1.0.0"
                },
                "capabilities": {}
            },
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_initialize_request_missing_protocol_version() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "client_info": {
                    "name": "test-client",
                    "version": "1.0.0"
                },
                "capabilities": {}
            },
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to missing protocol_version");
    }
    
    #[test]
    fn test_initialize_request_invalid_version_format() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocol_version": "invalid",
                "client_info": {
                    "name": "test-client",
                    "version": "1.0.0"
                },
                "capabilities": {}
            },
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to invalid version format");
    }
    
    #[test]
    fn test_tools_call_request_valid() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_weather",
                "arguments": {"location": "Seattle"}
            },
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_tools_call_request_missing_name() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "arguments": {"location": "Seattle"}
            },
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to missing tool name");
    }
    
    #[test]
    fn test_resources_read_request_valid() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "resources/read",
            "params": {
                "uri": "file:///path/to/resource"
            },
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_resources_read_request_missing_uri() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "resources/read",
            "params": {},
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to missing uri");
    }
    
    #[test]
    fn test_prompts_get_request_valid() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "prompts/get",
            "params": {
                "name": "test-prompt"
            },
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_prompts_get_request_missing_name() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "prompts/get",
            "params": {},
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to missing prompt name");
        assert!(!result.errors.is_empty());
    }
    
    #[test]
    fn test_prompts_get_request_empty_name() {
        // Test with empty name to trigger validate_prompt_get_params error
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "prompts/get",
            "params": {
                "name": ""
            },
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to empty prompt name");
        assert!(!result.errors.is_empty());
    }
    
    #[test]
    fn test_prompts_get_request_with_arguments() {
        // Test prompts/get with valid arguments to cover the closing brace after error check
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "prompts/get",
            "params": {
                "name": "test-prompt",
                "arguments": {"key": "value"}
            },
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        assert!(result.is_valid, "Should be valid with arguments");
    }
    
    #[test]
    fn test_prompts_get_request_no_params() {
        // Test prompts/get without params - covers line 164 (closing brace)
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "prompts/get",
            "id": 1
        });
        
        let result = validator.validate_request(&payload).unwrap();
        // Without params, validation can't check prompt-specific constraints
        // So request is valid at the JSON-RPC level
        assert!(result.is_valid, "Request without params should pass JSON-RPC validation");
    }
    
    #[test]
    fn test_response_with_error() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "error": {
                "code": -32600,
                "message": "Invalid Request"
            },
            "id": 1
        });
        
        let result = validator.validate_response(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_response_with_error_and_data() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "error": {
                "code": -32600,
                "message": "Invalid Request",
                "data": {"detail": "Missing required field"}
            },
            "id": 1
        });
        
        let result = validator.validate_response(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_response_with_both_result_and_error() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "result": {},
            "error": {
                "code": -32600,
                "message": "Invalid Request"
            },
            "id": 1
        });
        
        let result = validator.validate_response(&payload).unwrap();
        assert!(!result.is_valid, "Response cannot have both result and error");
    }
    
    #[test]
    fn test_response_with_neither_result_nor_error() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "id": 1
        });
        
        let result = validator.validate_response(&payload).unwrap();
        assert!(!result.is_valid, "Response must have either result or error");
    }
    
    #[test]
    fn test_response_invalid_jsonrpc_version() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "1.0",
            "result": {},
            "id": 1
        });
        
        let result = validator.validate_response(&payload).unwrap();
        assert!(!result.is_valid, "Should be invalid due to wrong JSON-RPC version");
    }
    
    #[test]
    fn test_response_missing_id() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "result": {}
        });
        
        let result = validator.validate_response(&payload);
        assert!(result.is_err(), "Should fail due to missing id");
    }
    
    #[test]
    fn test_notification_valid() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "notifications/resources/updated"
        });
        
        let result = validator.validate_notification(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_notification_with_params() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "method": "notifications/resources/updated",
            "params": {"uri": "file:///test"}
        });
        
        let result = validator.validate_notification(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_notification_invalid_version() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "1.0",
            "method": "notifications/test"
        });
        
        let result = validator.validate_notification(&payload).unwrap();
        assert!(!result.is_valid, "Should be invalid due to wrong JSON-RPC version");
    }
    
    #[test]
    fn test_notification_missing_method() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0"
        });
        
        let result = validator.validate_notification(&payload);
        assert!(result.is_err(), "Should fail due to missing method");
    }
    
    #[test]
    fn test_is_request_with_notification_method() {
        let payload = json!({
            "method": "notifications/test",
            "id": 1
        });
        // Should not be considered a request if method starts with "notifications/"
        assert!(!MCPValidator::is_request(&payload));
    }
    
    #[test]
    fn test_is_response_with_error() {
        let payload = json!({
            "error": {"code": -32600, "message": "Error"},
            "id": 1
        });
        assert!(MCPValidator::is_response(&payload));
    }
    
    #[test]
    fn test_is_notification_no_method() {
        let payload = json!({
            "id": 1
        });
        assert!(!MCPValidator::is_notification(&payload));
    }
    
    #[test]
    fn test_validation_result_add_error() {
        let mut result = ValidationResult::new("test".to_string());
        assert!(result.is_valid);
        
        result.add_error("Test error".to_string());
        assert!(!result.is_valid);
        assert_eq!(result.errors.len(), 1);
    }
    
    #[test]
    fn test_validation_result_add_warning() {
        let mut result = ValidationResult::new("test".to_string());
        result.add_warning("Test warning".to_string());
        assert!(result.is_valid);
        assert_eq!(result.warnings.len(), 1);
    }
    
    #[test]
    fn test_all_lifecycle_methods() {
        let validator = MCPValidator::new();
        let methods = vec!["initialize", "initialized", "ping"];
        
        for method in methods {
            let payload = json!({
                "jsonrpc": "2.0",
                "method": method,
                "id": 1
            });
            let result = validator.validate_request(&payload).unwrap();
            assert!(result.is_valid, "Method {} should be valid", method);
        }
    }
    
    #[test]
    fn test_all_tool_methods() {
        let validator = MCPValidator::new();
        let methods = vec!["tools/list", "tools/call"];
        
        for method in methods {
            let payload = json!({
                "jsonrpc": "2.0",
                "method": method,
                "id": 1
            });
            let result = validator.validate_request(&payload).unwrap();
            assert!(result.is_valid || !result.warnings.is_empty(), "Method {} should be recognized", method);
        }
    }
    
    #[test]
    fn test_all_resource_methods() {
        let validator = MCPValidator::new();
        let methods = vec![
            "resources/list",
            "resources/read",
            "resources/subscribe",
            "resources/unsubscribe",
            "resources/templates/list"
        ];
        
        for method in methods {
            let payload = json!({
                "jsonrpc": "2.0",
                "method": method,
                "id": 1
            });
            let result = validator.validate_request(&payload).unwrap();
            assert!(result.is_valid || !result.warnings.is_empty(), "Method {} should be recognized", method);
        }
    }
    
    #[test]
    fn test_all_notification_methods() {
        let validator = MCPValidator::new();
        let methods = vec![
            "notifications/resources/updated",
            "notifications/resources/list_changed",
            "notifications/tools/list_changed",
            "notifications/prompts/list_changed"
        ];
        
        for method in methods {
            let payload = json!({
                "jsonrpc": "2.0",
                "method": method
            });
            let result = validator.validate_notification(&payload).unwrap();
            assert!(result.is_valid, "Notification method {} should be valid", method);
        }
    }
    
    #[test]
    fn test_validator_default() {
        let validator = MCPValidator::default();
        assert!(!validator.valid_methods.is_empty());
    }
    
    #[test]
    fn test_error_with_valid_message() {
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "error": {
                "code": -32600,
                "message": "Error message"
            },
            "id": 1
        });
        
        let result = validator.validate_response(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_notification_method_with_id_is_not_request() {
        // Test request with method starting with "notifications/" but has an ID
        // Should be notification, not request
        let payload = json!({
            "method": "notifications/resources/updated",
            "id": 1
        });
        assert!(!MCPValidator::is_request(&payload), "Notification method with ID should not be a request");
    }
    
    #[test]
    fn test_response_both_result_and_error_validation() {
        // Test response with both Some(result) and Some(error)
        let validator = MCPValidator::new();
        let payload = json!({
            "jsonrpc": "2.0",
            "result": {"data": "test"},
            "error": {
                "code": -32600,
                "message": "Error"
            },
            "id": 1
        });
        
        let result = validator.validate_response(&payload).unwrap();
        assert!(!result.is_valid, "Response with both result and error should be invalid");
        assert!(result.errors.iter().any(|e| e.contains("both result and error")));
    }
}

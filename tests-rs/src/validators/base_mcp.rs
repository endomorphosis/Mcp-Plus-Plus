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
        
        // Check JSON-RPC version
        if request.jsonrpc != "2.0" {
            result.add_error(format!("Invalid JSON-RPC version: {}", request.jsonrpc));
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
        
        // Check JSON-RPC version
        if response.jsonrpc != "2.0" {
            result.add_error(format!("Invalid JSON-RPC version: {}", response.jsonrpc));
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
        
        // Check JSON-RPC version
        if notification.jsonrpc != "2.0" {
            result.add_error(format!("Invalid JSON-RPC version: {}", notification.jsonrpc));
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
}

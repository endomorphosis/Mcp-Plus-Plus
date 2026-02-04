//! Transport Protocol Validator (Profile E)
//!
//! Validates mcp+p2p transport protocol messages.
//! SPEC: Transport.md

use crate::models::*;
use crate::validators::base_mcp::{ValidationError, ValidationResult};
use serde_json::Value;
use serde_valid::Validate;

/// Transport Protocol Validator
pub struct TransportValidator;

impl TransportValidator {
    pub fn new() -> Self {
        Self
    }
    
    /// Validate a transport message
    /// SPEC: Transport.md § Message Framing, MUST
    pub fn validate_transport_message(
        &self,
        payload: &Value,
    ) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("transport_message".to_string());
        
        let message: TransportMessage = serde_json::from_value(payload.clone())?;
        
        if let Err(e) = message.validate() {
            result.add_error(format!("Validation error: {}", e));
            return Ok(result);
        }
        
        // Check protocol ID
        if !message.protocol_id.starts_with("/mcp+p2p/") {
            result.add_error("Protocol ID must start with '/mcp+p2p/'".to_string());
        }
        
        // Check length is positive
        if message.length == 0 {
            result.add_error("Message length must be positive".to_string());
        }
        
        Ok(result)
    }
    
    /// Validate session information
    /// SPEC: Transport.md § Session Lifecycle, MUST
    pub fn validate_session(
        &self,
        payload: &Value,
    ) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("session_info".to_string());
        
        let session: SessionInfo = serde_json::from_value(payload.clone())?;
        
        if let Err(e) = session.validate() {
            result.add_error(format!("Validation error: {}", e));
            return Ok(result);
        }
        
        Ok(result)
    }
}

impl Default for TransportValidator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    
    #[test]
    fn test_valid_transport_message() {
        let validator = TransportValidator::new();
        let payload = json!({
            "protocol_id": "/mcp+p2p/1.0.0",
            "length": 256,
            "payload": {"jsonrpc": "2.0", "method": "test"}
        });
        
        let result = validator.validate_transport_message(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_valid_session() {
        let validator = TransportValidator::new();
        let payload = json!({
            "session_id": "session-123",
            "peer_addr": "/ip4/127.0.0.1/tcp/8080"
        });
        
        let result = validator.validate_session(&payload).unwrap();
        assert!(result.is_valid);
    }
}

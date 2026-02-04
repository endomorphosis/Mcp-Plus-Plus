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
    
    // Additional comprehensive tests
    
    #[test]
    fn test_transport_message_invalid_protocol_id() {
        let validator = TransportValidator::new();
        let payload = json!({
            "protocol_id": "/invalid/1.0.0",
            "length": 256,
            "payload": {"jsonrpc": "2.0", "method": "test"}
        });
        
        let result = validator.validate_transport_message(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to invalid protocol_id");
    }
    
    #[test]
    fn test_transport_message_zero_length() {
        let validator = TransportValidator::new();
        let payload = json!({
            "protocol_id": "/mcp+p2p/1.0.0",
            "length": 0,
            "payload": {"jsonrpc": "2.0", "method": "test"}
        });
        
        let result = validator.validate_transport_message(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to zero length");
    }
    
    #[test]
    fn test_transport_message_missing_protocol_id() {
        let validator = TransportValidator::new();
        let payload = json!({
            "length": 256,
            "payload": {"jsonrpc": "2.0", "method": "test"}
        });
        
        let result = validator.validate_transport_message(&payload);
        assert!(result.is_err(), "Should fail due to missing protocol_id");
    }
    
    #[test]
    fn test_transport_message_missing_length() {
        let validator = TransportValidator::new();
        let payload = json!({
            "protocol_id": "/mcp+p2p/1.0.0",
            "payload": {"jsonrpc": "2.0", "method": "test"}
        });
        
        let result = validator.validate_transport_message(&payload);
        assert!(result.is_err(), "Should fail due to missing length");
    }
    
    #[test]
    fn test_transport_message_missing_payload() {
        let validator = TransportValidator::new();
        let payload = json!({
            "protocol_id": "/mcp+p2p/1.0.0",
            "length": 256
        });
        
        let result = validator.validate_transport_message(&payload);
        assert!(result.is_err(), "Should fail due to missing payload");
    }
    
    #[test]
    fn test_transport_message_large_length() {
        let validator = TransportValidator::new();
        let payload = json!({
            "protocol_id": "/mcp+p2p/1.0.0",
            "length": 1048576,
            "payload": {"jsonrpc": "2.0", "method": "test"}
        });
        
        let result = validator.validate_transport_message(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_session_missing_id() {
        let validator = TransportValidator::new();
        let payload = json!({
            "peer_addr": "/ip4/127.0.0.1/tcp/8080"
        });
        
        let result = validator.validate_session(&payload);
        assert!(result.is_err(), "Should fail due to missing session_id");
    }
    
    #[test]
    fn test_session_missing_peer_addr() {
        let validator = TransportValidator::new();
        let payload = json!({
            "session_id": "session-123"
        });
        
        let result = validator.validate_session(&payload);
        assert!(result.is_err(), "Should fail due to missing peer_addr");
    }
    
    #[test]
    fn test_session_ipv6_address() {
        let validator = TransportValidator::new();
        let payload = json!({
            "session_id": "session-123",
            "peer_addr": "/ip6/::1/tcp/8080"
        });
        
        let result = validator.validate_session(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_session_with_p2p_id() {
        let validator = TransportValidator::new();
        let payload = json!({
            "session_id": "session-123",
            "peer_addr": "/ip4/127.0.0.1/tcp/8080/p2p/QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        });
        
        let result = validator.validate_session(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_validator_default() {
        let validator = TransportValidator::default();
        let payload = json!({
            "session_id": "session-123",
            "peer_addr": "/ip4/127.0.0.1/tcp/8080"
        });
        
        let result = validator.validate_session(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_transport_message_invalid_protocol_id_prefix() {
        // Test invalid protocol ID (not starting with "/mcp+p2p/")
        let validator = TransportValidator::new();
        let payload = json!({
            "protocol_id": "/other/1.0.0",
            "length": 256,
            "payload": {"jsonrpc": "2.0", "method": "test"}
        });
        
        let result = validator.validate_transport_message(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to invalid protocol_id");
        // Error comes from serde_valid validation
        assert!(!result.errors.is_empty());
    }
    
    #[test]
    fn test_transport_message_length_zero() {
        // Test message with length == 0
        let validator = TransportValidator::new();
        let payload = json!({
            "protocol_id": "/mcp+p2p/1.0.0",
            "length": 0,
            "payload": {"jsonrpc": "2.0", "method": "test"}
        });
        
        let result = validator.validate_transport_message(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to zero length");
        // Error comes from serde_valid validation
        assert!(!result.errors.is_empty());
    }
    
    #[test]
    fn test_session_empty_session_id_triggers_serde_valid_error() {
        // Test session with empty session_id that triggers serde_valid early return
        let validator = TransportValidator::new();
        let payload = json!({
            "session_id": "",
            "peer_addr": "/ip4/127.0.0.1/tcp/8080"
        });
        
        let result = validator.validate_session(&payload).unwrap();
        assert!(!result.is_valid, "Empty session_id should trigger validation error");
        assert!(!result.errors.is_empty());
    }
}

//! CID Artifacts Validator (Profile B)
//!
//! Validates execution envelopes and receipts.
//! SPEC: CID-Artifacts.md

use crate::models::*;
use crate::validators::base_mcp::{ValidationError, ValidationResult};
use serde_json::Value;
use serde_valid::Validate;

/// CID Artifacts Validator
pub struct CIDArtifactsValidator;

impl CIDArtifactsValidator {
    pub fn new() -> Self {
        Self
    }
    
    /// Validate an execution envelope
    /// SPEC: CID-Artifacts.md § Execution Envelope, MUST
    pub fn validate_envelope(
        &self,
        payload: &Value,
    ) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("execution_envelope".to_string());
        
        let envelope: ExecutionEnvelope = serde_json::from_value(payload.clone())?;
        
        if let Err(e) = envelope.validate() {
            result.add_error(format!("Validation error: {}", e));
            return Ok(result);
        }
        
        // Parents can be empty for genesis events
        if envelope.parents.is_empty() {
            result.add_warning("Envelope has no parents (genesis event)".to_string());
        }
        
        Ok(result)
    }
    
    /// Validate an execution receipt
    /// SPEC: CID-Artifacts.md § Receipt Structure, MUST
    pub fn validate_receipt(&self, payload: &Value) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("execution_receipt".to_string());
        
        let receipt: ExecutionReceipt = serde_json::from_value(payload.clone())?;
        
        if let Err(e) = receipt.validate() {
            result.add_error(format!("Validation error: {}", e));
            return Ok(result);
        }
        // CID-native receipts require output_cid + receipt_cid (parity with py).
        if receipt.output_cid.is_none() {
            result.add_error("Missing required field: output_cid".to_string());
        }
        if receipt.receipt_cid.is_none() {
            result.add_error("Missing required field: receipt_cid".to_string());
        }
        if !result.is_valid {
            return Err(ValidationError::ValidationFailed("missing required receipt fields".to_string()));
        }
        Ok(result)
    }
}

impl Default for CIDArtifactsValidator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    
    #[test]
    fn test_valid_envelope() {
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "interface_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "input_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": ["QmPreviousEvent"],
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_envelope(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_valid_receipt() {
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "envelope_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "output_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "signature": "0x1234567890abcdef",
            "receipt_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        });
        
        let result = validator.validate_receipt(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    // Additional comprehensive tests
    
    #[test]
    fn test_envelope_genesis_no_parents() {
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "interface_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "input_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": [],
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_envelope(&payload).unwrap();
        assert!(result.is_valid);
        assert!(!result.warnings.is_empty(), "Should have warning for genesis event");
    }
    
    #[test]
    fn test_envelope_missing_interface_cid() {
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "input_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": ["QmPreviousEvent"],
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_envelope(&payload);
        assert!(result.is_err(), "Should fail due to missing interface_cid");
    }
    
    #[test]
    fn test_envelope_missing_input_cid() {
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "interface_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": ["QmPreviousEvent"],
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_envelope(&payload);
        assert!(result.is_err(), "Should fail due to missing input_cid");
    }
    
    #[test]
    fn test_envelope_missing_timestamp() {
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "interface_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "input_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": ["QmPreviousEvent"]
        });
        
        let result = validator.validate_envelope(&payload);
        assert!(result.is_err(), "Should fail due to missing timestamp");
    }
    
    #[test]
    fn test_envelope_invalid_cid_format() {
        let validator = CIDArtifactsValidator::new();
        // Use a short string that will deserialize but fail CID regex validation
        let payload = json!({
            "interface_cid": "Qm123",  // Too short for valid CID
            "input_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": ["QmPreviousEvent"],
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_envelope(&payload).unwrap();
        assert!(!result.is_valid, "Invalid CID format should fail");
        assert!(!result.errors.is_empty());
    }
    
    #[test]
    fn test_envelope_with_complex_timestamp() {
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "interface_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "input_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": ["QmPreviousEvent"],
            "timestamp": "2024-01-01T12:34:56.789Z"
        });
        
        let result = validator.validate_envelope(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_envelope_multiple_parents() {
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "interface_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "input_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": [
                "QmParent1APJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnP",
                "QmParent2APJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnP"
            ],
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_envelope(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_receipt_missing_envelope_cid() {
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "output_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "signature": "0x1234567890abcdef",
            "receipt_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        });
        
        let result = validator.validate_receipt(&payload);
        assert!(result.is_ok(), "envelope_cid is optional in de-facto receipt");
    }
    
    #[test]
    fn test_receipt_missing_output_cid() {
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "envelope_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "signature": "0x1234567890abcdef",
            "receipt_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        });
        
        let result = validator.validate_receipt(&payload);
        assert!(result.is_err(), "Should fail due to missing output_cid");
    }
    
    #[test]
    fn test_receipt_missing_signature() {
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "envelope_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "output_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "receipt_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        });
        
        let result = validator.validate_receipt(&payload);
        assert!(result.is_ok(), "signature is optional in de-facto receipt");
    }
    
    #[test]
    fn test_receipt_missing_receipt_cid() {
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "envelope_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "output_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "signature": "0x1234567890abcdef"
        });
        
        let result = validator.validate_receipt(&payload);
        assert!(result.is_err(), "Should fail due to missing receipt_cid");
    }
    
    #[test]
    fn test_receipt_invalid_cid_format() {
        let validator = CIDArtifactsValidator::new();
        // Use a short string that will deserialize but fail CID regex validation
        let payload = json!({
            "envelope_cid": "Qm123",  // Too short for valid CID
            "output_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "signature": "0x1234567890abcdef",
            "receipt_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        });
        
        let result = validator.validate_receipt(&payload).unwrap();
        assert!(!result.is_valid, "Invalid CID format should fail");
        assert!(!result.errors.is_empty());
    }
    
    #[test]
    fn test_validator_default() {
        let validator = CIDArtifactsValidator::default();
        let payload = json!({
            "interface_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "input_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": ["QmPreviousEvent"],
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_envelope(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_envelope_deserializes_but_fails_serde_valid() {
        // Test envelope that deserializes but fails serde_valid validation
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "interface_cid": "Qm123",  // Too short for valid CID regex
            "input_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": ["QmPreviousEvent"],
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_envelope(&payload).unwrap();
        assert!(!result.is_valid, "Invalid CID should fail validation");
        assert!(!result.errors.is_empty());
    }
    
    #[test]
    fn test_envelope_empty_parents_genesis_warning() {
        // Test envelope with empty parents array triggering genesis warning
        let validator = CIDArtifactsValidator::new();
        let payload = json!({
            "interface_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "input_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": [],
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_envelope(&payload).unwrap();
        assert!(result.is_valid);
        assert!(result.warnings.iter().any(|w| w.contains("genesis")));
    }
}

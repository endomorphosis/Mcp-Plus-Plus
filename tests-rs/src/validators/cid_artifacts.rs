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
}

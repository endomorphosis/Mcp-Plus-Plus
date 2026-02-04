//! MCP-IDL Validator (Profile A)
//!
//! Validates interface descriptors and CID computations.
//! SPEC: MCP-IDL.md

use crate::models::*;
use crate::validators::base_mcp::{ValidationError, ValidationResult};
use lazy_static::lazy_static;
use regex::Regex;
use serde_json::Value;
use serde_valid::Validate;

lazy_static! {
    static ref CID_REGEX: Regex = Regex::new(r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|baf[a-zA-Z0-9]{50,})$").unwrap();
}

/// MCP-IDL Validator
pub struct MCPIDLValidator;

impl MCPIDLValidator {
    pub fn new() -> Self {
        Self
    }
    
    /// Validate an interface descriptor
    /// SPEC: MCP-IDL.md § Interface Descriptor Structure, MUST
    pub fn validate_interface_descriptor(
        &self,
        payload: &Value,
    ) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("interface_descriptor".to_string());
        
        let descriptor: InterfaceDescriptor = serde_json::from_value(payload.clone())?;
        
        if let Err(e) = descriptor.validate() {
            result.add_error(format!("Validation error: {}", e));
            return Ok(result);
        }
        
        // Validate interface_cid format
        if !CID_REGEX.is_match(&descriptor.interface_cid) {
            result.add_error("Invalid interface_cid format".to_string());
        }
        
        // Validate tools array is not empty
        if descriptor.tools.is_empty() {
            result.add_warning("Interface has no tools defined".to_string());
        }
        
        Ok(result)
    }
    
    /// Validate CID format
    pub fn validate_cid_format(&self, cid: &str) -> bool {
        CID_REGEX.is_match(cid)
    }
}

impl Default for MCPIDLValidator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    
    #[test]
    fn test_valid_interface_descriptor() {
        let validator = MCPIDLValidator::new();
        let payload = json!({
            "name": "test-interface",
            "version": "1.0.0",
            "tools": [{
                "name": "test_tool",
                "input_schema": {"type": "object"}
            }],
            "interface_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        });
        
        let result = validator.validate_interface_descriptor(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_validate_cid_format() {
        let validator = MCPIDLValidator::new();
        assert!(validator.validate_cid_format("QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"));
        assert!(validator.validate_cid_format("bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"));
        assert!(!validator.validate_cid_format("invalid-cid"));
    }
}

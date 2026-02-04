//! UCAN Delegation Validator (Profile C)
//!
//! Validates UCAN tokens and delegation chains.
//! SPEC: UCAN-Delegation.md

use crate::models::*;
use crate::validators::base_mcp::{ValidationError, ValidationResult};
use serde_json::Value;
use serde_valid::Validate;

/// UCAN Delegation Validator
pub struct UCANDelegationValidator;

impl UCANDelegationValidator {
    pub fn new() -> Self {
        Self
    }
    
    /// Validate a UCAN token
    /// SPEC: UCAN-Delegation.md § UCAN Token Structure, MUST
    pub fn validate_ucan_token(
        &self,
        payload: &Value,
    ) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("ucan_token".to_string());
        
        let token: UCANToken = serde_json::from_value(payload.clone())?;
        
        if let Err(e) = token.validate() {
            result.add_error(format!("Validation error: {}", e));
            return Ok(result);
        }
        
        // Check DIDs start with "did:"
        if !token.iss.starts_with("did:") {
            result.add_error("Issuer must be a DID".to_string());
        }
        if !token.aud.starts_with("did:") {
            result.add_error("Audience must be a DID".to_string());
        }
        
        // Check attenuations are not empty
        if token.att.is_empty() {
            result.add_error("UCAN must have at least one attenuation".to_string());
        }
        
        Ok(result)
    }
    
    /// Validate a delegation chain
    /// SPEC: UCAN-Delegation.md § Delegation Chain, MUST
    pub fn validate_delegation_chain(
        &self,
        payload: &Value,
    ) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("delegation_chain".to_string());
        
        let chain: DelegationChain = serde_json::from_value(payload.clone())?;
        
        if let Err(e) = chain.validate() {
            result.add_error(format!("Validation error: {}", e));
            return Ok(result);
        }
        
        // Validate each token in the chain
        for (i, token) in chain.chain.iter().enumerate() {
            if let Err(e) = token.validate() {
                result.add_error(format!("Token {} validation error: {}", i, e));
            }
        }
        
        Ok(result)
    }
}

impl Default for UCANDelegationValidator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    
    #[test]
    fn test_valid_ucan_token() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        });
        
        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_valid_delegation_chain() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "chain": [{
                "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                "att": [{
                    "resource": "mcp://tools/*",
                    "ability": "execute"
                }],
                "exp": 1735689600
            }]
        });
        
        let result = validator.validate_delegation_chain(&payload).unwrap();
        assert!(result.is_valid);
    }
}

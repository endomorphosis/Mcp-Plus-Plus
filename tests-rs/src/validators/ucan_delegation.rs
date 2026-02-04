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
    
    // Additional comprehensive tests
    
    #[test]
    fn test_ucan_token_invalid_issuer() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "invalid-issuer",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        });
        
        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to invalid issuer");
    }
    
    #[test]
    fn test_ucan_token_invalid_audience() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "invalid-audience",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        });
        
        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to invalid audience");
    }
    
    #[test]
    fn test_ucan_token_empty_attenuations() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [],
            "exp": 1735689600
        });
        
        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(!result.is_valid, "Should fail with empty attenuations");
    }
    
    #[test]
    fn test_ucan_token_missing_issuer() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        });
        
        let result = validator.validate_ucan_token(&payload);
        assert!(result.is_err(), "Should fail due to missing issuer");
    }
    
    #[test]
    fn test_ucan_token_missing_audience() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        });
        
        let result = validator.validate_ucan_token(&payload);
        assert!(result.is_err(), "Should fail due to missing audience");
    }
    
    #[test]
    fn test_ucan_token_missing_expiry() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }]
        });
        
        let result = validator.validate_ucan_token(&payload);
        assert!(result.is_err(), "Should fail due to missing expiry");
    }
    
    #[test]
    fn test_ucan_token_multiple_attenuations() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [
                {
                    "resource": "mcp://tools/*",
                    "ability": "execute"
                },
                {
                    "resource": "mcp://resources/*",
                    "ability": "read"
                }
            ],
            "exp": 1735689600
        });
        
        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_ucan_token_with_proof() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600,
            "prf": "previous-ucan-token"
        });
        
        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_delegation_chain_multiple_tokens() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "chain": [
                {
                    "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                    "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                    "att": [{
                        "resource": "mcp://tools/*",
                        "ability": "execute"
                    }],
                    "exp": 1735689600
                },
                {
                    "iss": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                    "aud": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                    "att": [{
                        "resource": "mcp://tools/specific",
                        "ability": "execute"
                    }],
                    "exp": 1735689600
                }
            ]
        });
        
        let result = validator.validate_delegation_chain(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_delegation_chain_single_token() {
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
    
    #[test]
    fn test_delegation_chain_with_validated_token() {
        // Test delegation chain validation completes without error
        // (Note: The token-level validation in the loop at lines 58-62 is redundant
        // since chain.validate() already validates all tokens via serde_valid)
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
        assert!(result.is_valid, "Valid chain should pass");
    }
    
    #[test]
    fn test_validator_default() {
        let validator = UCANDelegationValidator::default();
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
    fn test_ucan_token_iss_not_starting_with_did() {
        // Test token with iss not starting with "did:"
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        });
        
        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to invalid issuer format");
        // Error comes from serde_valid validation
        assert!(!result.errors.is_empty());
    }
    
    #[test]
    fn test_ucan_token_aud_not_starting_with_did() {
        // Test token with aud not starting with "did:"
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        });
        
        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to invalid audience format");
        // Error comes from serde_valid validation
        assert!(!result.errors.is_empty());
    }
    
    #[test]
    fn test_delegation_chain_multiple_invalid_tokens() {
        // Test delegation chain with multiple invalid tokens
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "chain": [
                {
                    "iss": "key:invalid1",
                    "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                    "att": [{
                        "resource": "mcp://tools/*",
                        "ability": "execute"
                    }],
                    "exp": 1735689600
                },
                {
                    "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                    "aud": "key:invalid2",
                    "att": [{
                        "resource": "mcp://tools/*",
                        "ability": "execute"
                    }],
                    "exp": 1735689600
                }
            ]
        });
        
        let result = validator.validate_delegation_chain(&payload).unwrap();
        assert!(!result.is_valid || !result.errors.is_empty(), "Should detect invalid tokens in chain");
    }
    
    #[test]
    fn test_delegation_chain_empty_chain_triggers_serde_valid_error() {
        // Test delegation chain with empty chain that triggers serde_valid early return
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "chain": []
        });
        
        let result = validator.validate_delegation_chain(&payload).unwrap();
        assert!(!result.is_valid, "Empty chain should trigger validation error");
        assert!(!result.errors.is_empty());
    }
}

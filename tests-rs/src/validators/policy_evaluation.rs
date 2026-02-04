//! Policy Evaluation Validator (Profile D)
//!
//! Validates policy definitions and decisions.
//! SPEC: Policy-Evaluation.md

use crate::models::*;
use crate::validators::base_mcp::{ValidationError, ValidationResult};
use serde_json::Value;
use serde_valid::Validate;

/// Policy Evaluation Validator
pub struct PolicyEvaluationValidator;

impl PolicyEvaluationValidator {
    pub fn new() -> Self {
        Self
    }
    
    /// Validate a policy definition
    /// SPEC: Policy-Evaluation.md § Policy Structure, MUST
    pub fn validate_policy(&self, payload: &Value) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("policy".to_string());
        
        let policy: Policy = serde_json::from_value(payload.clone())?;
        
        if let Err(e) = policy.validate() {
            result.add_error(format!("Validation error: {}", e));
            return Ok(result);
        }
        
        // Check rules are not empty
        if policy.rules.is_empty() {
            result.add_error("Policy must have at least one rule".to_string());
        }
        
        Ok(result)
    }
    
    /// Validate a policy decision
    /// SPEC: Policy-Evaluation.md § Decision Types, MUST
    pub fn validate_decision(
        &self,
        payload: &Value,
    ) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("policy_decision".to_string());
        
        let decision: PolicyDecision = serde_json::from_value(payload.clone())?;
        
        if let Err(e) = decision.validate() {
            result.add_error(format!("Validation error: {}", e));
            return Ok(result);
        }
        
        // If decision is AllowWithObligations, obligations must be present
        if matches!(decision.decision, DecisionType::AllowWithObligations) {
            if decision.obligations.is_none() || decision.obligations.as_ref().unwrap().is_empty()
            {
                result.add_error(
                    "AllowWithObligations decision must have obligations".to_string(),
                );
            }
        }
        
        Ok(result)
    }
}

impl Default for PolicyEvaluationValidator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    
    #[test]
    fn test_valid_policy() {
        let validator = PolicyEvaluationValidator::new();
        let payload = json!({
            "policy_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "policy_type": "permission",
            "rules": [{
                "condition": "time_before('2024-12-31')",
                "action": "allow"
            }]
        });
        
        let result = validator.validate_policy(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_valid_decision() {
        let validator = PolicyEvaluationValidator::new();
        let payload = json!({
            "decision": "allow"
        });
        
        let result = validator.validate_decision(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_decision_with_obligations() {
        let validator = PolicyEvaluationValidator::new();
        let payload = json!({
            "decision": "allow_with_obligations",
            "obligations": [{
                "description": "Log this action",
                "deadline": "2024-12-31T23:59:59Z"
            }]
        });
        
        let result = validator.validate_decision(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    // Additional comprehensive tests
    
    #[test]
    fn test_policy_empty_rules() {
        let validator = PolicyEvaluationValidator::new();
        let payload = json!({
            "policy_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "policy_type": "permission",
            "rules": []
        });
        
        let result = validator.validate_policy(&payload).unwrap();
        assert!(!result.is_valid, "Should fail with empty rules");
    }
    
    #[test]
    fn test_policy_missing_cid() {
        let validator = PolicyEvaluationValidator::new();
        let payload = json!({
            "policy_type": "permission",
            "rules": [{
                "condition": "time_before('2024-12-31')",
                "action": "allow"
            }]
        });
        
        let result = validator.validate_policy(&payload);
        assert!(result.is_err(), "Should fail due to missing policy_cid");
    }
    
    #[test]
    fn test_policy_missing_type() {
        let validator = PolicyEvaluationValidator::new();
        let payload = json!({
            "policy_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "rules": [{
                "condition": "time_before('2024-12-31')",
                "action": "allow"
            }]
        });
        
        let result = validator.validate_policy(&payload);
        assert!(result.is_err(), "Should fail due to missing policy_type");
    }
    
    #[test]
    fn test_policy_with_temporal() {
        let validator = PolicyEvaluationValidator::new();
        let payload = json!({
            "policy_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "policy_type": "permission",
            "temporal": {
                "not_before": "2024-01-01T00:00:00Z",
                "not_after": "2024-12-31T23:59:59Z"
            },
            "rules": [{
                "condition": "time_before('2024-12-31')",
                "action": "allow"
            }]
        });
        
        let result = validator.validate_policy(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_policy_multiple_rules() {
        let validator = PolicyEvaluationValidator::new();
        let payload = json!({
            "policy_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "policy_type": "permission",
            "rules": [
                {
                    "condition": "time_before('2024-12-31')",
                    "action": "allow"
                },
                {
                    "condition": "user_has_role('admin')",
                    "action": "allow"
                }
            ]
        });
        
        let result = validator.validate_policy(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_decision_deny() {
        let validator = PolicyEvaluationValidator::new();
        let payload = json!({
            "decision": "deny"
        });
        
        let result = validator.validate_decision(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_decision_missing_field() {
        let validator = PolicyEvaluationValidator::new();
        let payload = json!({});
        
        let result = validator.validate_decision(&payload);
        assert!(result.is_err(), "Should fail due to missing decision");
    }
    
    #[test]
    fn test_decision_with_obligations_but_empty() {
        let validator = PolicyEvaluationValidator::new();
        let payload = json!({
            "decision": "allow_with_obligations",
            "obligations": []
        });
        
        let result = validator.validate_decision(&payload).unwrap();
        assert!(!result.is_valid, "AllowWithObligations must have obligations");
    }
    
    #[test]
    fn test_decision_with_obligations_missing() {
        let validator = PolicyEvaluationValidator::new();
        let payload = json!({
            "decision": "allow_with_obligations"
        });
        
        let result = validator.validate_decision(&payload).unwrap();
        assert!(!result.is_valid, "AllowWithObligations must have obligations");
    }
    
    #[test]
    fn test_decision_with_cid() {
        let validator = PolicyEvaluationValidator::new();
        let payload = json!({
            "decision": "allow",
            "decision_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        });
        
        let result = validator.validate_decision(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_validator_default() {
        let validator = PolicyEvaluationValidator::default();
        let payload = json!({
            "decision": "allow"
        });
        
        let result = validator.validate_decision(&payload).unwrap();
        assert!(result.is_valid);
    }
}

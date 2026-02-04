"""
Temporal Deontic Policy Validator

Validates Profile D (Temporal Deontic Policy Evaluation) according to docs/spec/temporal-deontic-policy.md
"""

from typing import Any, Dict
from .base_mcp import ValidationResult


class PolicyEvaluationValidator:
    """
    Validates temporal deontic policy representations and decisions.
    
    Based on: docs/spec/temporal-deontic-policy.md
    """
    
    POLICY_TYPES = ['permission', 'prohibition', 'obligation']
    
    def validate_policy(self, policy: Dict[str, Any]) -> ValidationResult:
        """
        Validate a policy representation.
        
        Args:
            policy: The policy object
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='policy')
        
        # Must have policy type
        if 'type' not in policy:
            result.add_error("Policy missing 'type' field")
        elif policy['type'] not in self.POLICY_TYPES:
            result.add_error(f"Invalid policy type: {policy['type']}")
        
        # Should have temporal constraints
        if 'temporal_constraints' not in policy:
            result.add_warning("Policy missing 'temporal_constraints'")
        else:
            self._validate_temporal_constraints(
                policy['temporal_constraints'], 
                result
            )
        
        return result
    
    def _validate_temporal_constraints(
        self, 
        constraints: Dict[str, Any], 
        result: ValidationResult
    ) -> None:
        """Validate temporal constraints format."""
        if 'valid_from' in constraints:
            # Should be ISO 8601 timestamp
            pass  # Simplified for now
        
        if 'valid_until' in constraints:
            # Should be ISO 8601 timestamp
            pass  # Simplified for now
    
    def validate_policy_decision(self, decision: Dict[str, Any]) -> ValidationResult:
        """
        Validate a policy evaluation decision.
        
        Args:
            decision: The decision object
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='policy_decision')
        
        required_fields = ['decision_cid', 'granted', 'evaluated_at']
        
        for field in required_fields:
            if field not in decision:
                result.add_error(f"Decision missing required field: {field}")
        
        return result

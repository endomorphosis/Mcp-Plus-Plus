"""
UCAN Delegation Validator

Validates Profile C (Capability Delegation) according to docs/spec/ucan-delegation.md
"""

from typing import Any, Dict, List
from .base_mcp import ValidationResult


class UCANDelegationValidator:
    """
    Validates UCAN capability delegation chains.
    
    Based on: docs/spec/ucan-delegation.md
    """
    
    def validate_delegation_chain(self, chain: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate a UCAN delegation chain.
        
        Args:
            chain: List of UCAN tokens forming a delegation chain
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='delegation_chain')
        
        if not isinstance(chain, list):
            result.add_error("Delegation chain must be a list")
            return result
        
        if len(chain) == 0:
            result.add_error("Delegation chain cannot be empty")
            return result
        
        # Validate each token in the chain
        for i, token in enumerate(chain):
            self._validate_ucan_token(token, i, result)
        
        return result
    
    def _validate_ucan_token(
        self, 
        token: Dict[str, Any], 
        index: int, 
        result: ValidationResult
    ) -> None:
        """Validate a single UCAN token."""
        if not isinstance(token, dict):
            result.add_error(f"Token at index {index} must be an object")
            return
        
        # Check required UCAN fields
        required_fields = ['iss', 'aud', 'att', 'exp']
        
        for field in required_fields:
            if field not in token:
                result.add_error(f"Token at index {index} missing required field: {field}")
        
        # Validate attenuation (capabilities)
        if 'att' in token:
            if not isinstance(token['att'], list):
                result.add_error(f"Token at index {index}: 'att' must be a list")
    
    def validate_invocation_with_proof(self, invocation: Dict[str, Any]) -> ValidationResult:
        """
        Validate an invocation with delegation proof.
        
        Args:
            invocation: Invocation with proof_cid reference
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='invocation_with_proof')
        
        if 'proof_cid' not in invocation:
            result.add_error("Invocation missing 'proof_cid' reference")
        
        return result

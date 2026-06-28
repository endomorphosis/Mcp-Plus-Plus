"""
CID-Native Execution Artifacts Validator

Validates Profile B (CID-Native Execution Envelopes) according to docs/spec/cid-native-artifacts.md
"""

from typing import Any, Dict, List, Optional
from .base_mcp import ValidationResult


class CIDExecutionValidator:
    """
    Validates CID-native execution envelopes and receipts.
    
    Based on: docs/spec/cid-native-artifacts.md
    """
    
    REQUIRED_ENVELOPE_FIELDS = [
        'interface_cid',
        'input_cid',
    ]
    
    OPTIONAL_ENVELOPE_FIELDS = [
        'intent_cid',
        'policy_cid',
        'proof_cid',
        'parents',
    ]
    
    def validate_execution_envelope(self, envelope: Dict[str, Any]) -> ValidationResult:
        """
        Validate an execution envelope structure.
        
        Args:
            envelope: The execution envelope payload
            
        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=True, message_type='execution_envelope')
        
        # Check required fields
        for field in self.REQUIRED_ENVELOPE_FIELDS:
            if field not in envelope:
                result.add_error(f"Missing required field: {field}")
        
        # Validate CID formats
        if 'interface_cid' in envelope:
            if not self._is_valid_cid_format(envelope['interface_cid']):
                result.add_error(f"Invalid interface_cid format: {envelope['interface_cid']}")
        
        if 'input_cid' in envelope:
            if not self._is_valid_cid_format(envelope['input_cid']):
                result.add_error(f"Invalid input_cid format: {envelope['input_cid']}")
        
        if 'intent_cid' in envelope:
            if not self._is_valid_cid_format(envelope['intent_cid']):
                result.add_error(f"Invalid intent_cid format: {envelope['intent_cid']}")
        
        if 'policy_cid' in envelope:
            if not self._is_valid_cid_format(envelope['policy_cid']):
                result.add_error(f"Invalid policy_cid format: {envelope['policy_cid']}")
        
        if 'proof_cid' in envelope:
            if not self._is_valid_cid_format(envelope['proof_cid']):
                result.add_error(f"Invalid proof_cid format: {envelope['proof_cid']}")
        
        # Validate parents array
        if 'parents' in envelope:
            if not isinstance(envelope['parents'], list):
                result.add_error("'parents' must be an array")
            else:
                for i, parent in enumerate(envelope['parents']):
                    if not self._is_valid_cid_format(parent):
                        result.add_error(f"Invalid parent CID at index {i}: {parent}")
        
        return result
    
    def validate_execution_receipt(self, receipt: Dict[str, Any]) -> ValidationResult:
        """
        Validate an execution receipt.
        
        Args:
            receipt: The execution receipt payload
            
        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=True, message_type='execution_receipt')
        
        # Required fields for receipts
        required_fields = ['output_cid', 'receipt_cid']
        
        for field in required_fields:
            if field not in receipt:
                result.add_error(f"Missing required field: {field}")
        
        # Validate CID formats
        if 'output_cid' in receipt:
            if not self._is_valid_cid_format(receipt['output_cid']):
                result.add_error(f"Invalid output_cid format: {receipt['output_cid']}")
        
        if 'receipt_cid' in receipt:
            if not self._is_valid_cid_format(receipt['receipt_cid']):
                result.add_error(f"Invalid receipt_cid format: {receipt['receipt_cid']}")
        
        # Check for optional signature
        if 'signature' in receipt:
            result.metadata['signed'] = True
        
        return result
    
    def _is_valid_cid_format(self, cid: str) -> bool:
        """
        Check if a string looks like a valid CID.
        
        This is a simplified check. Real implementation should use
        proper CID parsing libraries.
        
        Args:
            cid: The CID string to validate
            
        Returns:
            True if format looks valid
        """
        if not isinstance(cid, str):
            return False

        # Canonical: CIDv1 base32 (b + 58 [a-z2-7]) or legacy CIDv0 (Qm...).
        # Matches real Kubo `ipfs add --cid-version=1` output (e.g. bafkrei...).
        import re as _re
        return bool(_re.match(r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58})$", cid))
    
    def validate_cid_invocation(self, invocation: Dict[str, Any]) -> ValidationResult:
        """
        Validate a CID-wrapped MCP invocation.
        
        Args:
            invocation: The invocation with CID envelope
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='cid_invocation')
        
        # Must have envelope wrapper
        if 'envelope' not in invocation:
            result.add_error("Missing 'envelope' wrapper")
        else:
            # Validate envelope structure
            envelope_result = self.validate_execution_envelope(invocation['envelope'])
            if not envelope_result.is_valid:
                result.errors.extend(envelope_result.errors)
                result.is_valid = False
        
        # Should have actual invocation payload
        if 'invocation' not in invocation:
            result.add_warning("Missing 'invocation' payload")
        
        return result

"""
Integration tests for UCAN delegation (Profile C).

Tests validate compliance with docs/spec/ucan-delegation.md
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from validators.ucan_delegation import UCANDelegationValidator


class TestUCANDelegation:
    """Test UCAN capability delegation validation."""
    
    @pytest.fixture
    def validator(self):
        return UCANDelegationValidator()
    
    def test_valid_delegation_chain(self, validator):
        """
        Test validation of a valid UCAN delegation chain.
        
        Spec: docs/spec/ucan-delegation.md
        Requirement: Delegation chains MUST be validated
        """
        chain = [
            {
                "iss": "did:key:root",
                "aud": "did:key:intermediate",
                "att": [{"can": "tool/execute", "with": "weather-api"}],
                "exp": 1234567890
            },
            {
                "iss": "did:key:intermediate",
                "aud": "did:key:agent",
                "att": [{"can": "tool/execute", "with": "weather-api"}],
                "exp": 1234567890
            }
        ]
        
        result = validator.validate_delegation_chain(chain)
        
        assert result.is_valid
        assert result.message_type == "delegation_chain"
    
    def test_empty_delegation_chain(self, validator):
        """
        Test that empty delegation chains are invalid.
        
        Spec: docs/spec/ucan-delegation.md
        Requirement: Invocations MUST reference a valid delegation chain
        """
        chain = []
        
        result = validator.validate_delegation_chain(chain)
        
        assert not result.is_valid
        assert any("empty" in error.lower() for error in result.errors)
    
    def test_delegation_chain_missing_required_field(self, validator):
        """
        Test that delegation tokens must include required fields.
        
        Spec: docs/spec/ucan-delegation.md
        Requirement: UCAN tokens MUST include iss, aud, att, exp
        """
        chain = [
            {
                "iss": "did:key:root",
                "aud": "did:key:agent",
                # Missing 'att' and 'exp'
            }
        ]
        
        result = validator.validate_delegation_chain(chain)
        
        assert not result.is_valid
        assert any("att" in error.lower() for error in result.errors)
        assert any("exp" in error.lower() for error in result.errors)
    
    def test_invocation_with_proof_reference(self, validator):
        """
        Test validation of invocation with proof_cid reference.
        
        Spec: mcp++-profiles-draft.md:125
        Requirement: Invocations MUST reference a valid delegation chain
        """
        invocation = {
            "method": "tools/call",
            "params": {"name": "get_weather"},
            "proof_cid": "bafyproof123"
        }
        
        result = validator.validate_invocation_with_proof(invocation)
        
        assert result.is_valid
        assert result.message_type == "invocation_with_proof"
    
    def test_invocation_missing_proof(self, validator):
        """
        Test that invocations without proof_cid fail validation.
        
        Spec: mcp++-profiles-draft.md:125
        Requirement: Invocations MUST reference a valid delegation chain
        """
        invocation = {
            "method": "tools/call",
            "params": {"name": "get_weather"}
            # Missing proof_cid
        }
        
        result = validator.validate_invocation_with_proof(invocation)
        
        assert not result.is_valid
        assert any("proof_cid" in error.lower() for error in result.errors)
    
    def test_attenuation_invalid_type(self, validator):
        """
        Test that att field must be a list.
        
        Spec: docs/spec/ucan-delegation.md
        """
        chain = [
            {
                "iss": "did:key:root",
                "aud": "did:key:agent",
                "att": "invalid-not-a-list",  # Should be list
                "exp": 1234567890
            }
        ]
        
        result = validator.validate_delegation_chain(chain)
        
        assert not result.is_valid
        assert any("att" in error.lower() and "list" in error.lower() for error in result.errors)
    
    def test_nested_delegation_chain(self, validator):
        """
        Test validation of multi-level delegation chain.
        
        Spec: docs/spec/ucan-delegation.md
        Requirement: Support nested delegations
        """
        chain = [
            {
                "iss": "did:key:root",
                "aud": "did:key:org",
                "att": [{"can": "*"}],
                "exp": 1234567890
            },
            {
                "iss": "did:key:org",
                "aud": "did:key:team",
                "att": [{"can": "tool/*"}],
                "exp": 1234567890
            },
            {
                "iss": "did:key:team",
                "aud": "did:key:agent",
                "att": [{"can": "tool/execute"}],
                "exp": 1234567890
            }
        ]
        
        result = validator.validate_delegation_chain(chain)
        
        assert result.is_valid
        assert len(chain) == 3

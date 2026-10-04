"""
Integration tests for CID-native execution artifacts.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from validators.cid_artifacts import CIDExecutionValidator


class TestCIDExecutionArtifacts:
    """Test CID-native execution envelope validation."""
    
    @pytest.fixture
    def validator(self):
        return CIDExecutionValidator()
    
    def test_valid_execution_envelope(self, validator):
        """Test validation of a valid execution envelope."""
        envelope = {
            "interface_cid": "bafkreiapj52u5hi7pco5ebplvecv72olbnqglg2e7emwnmme4gguzsnpu4",
            "input_cid": "bafkreigoqjtgmmkhwd5elifk4ggzwals3wfiankxnhnylm6lh67mtjwz3a",
            "intent_cid": "bafkreigtbhe57yqgt5zdwkqk3xdkkpbqmnt77ol62rluu5kvdrxj76tzgi",
            "parents": ["bafkreihojjgp4soxeawgk64e4vhafpz3kdtlastu5hfnbdv5upb6c2cd7e", "bafkreifyiloqasaswqrluaxwzlyyeftgi2vwfyfe3rahohy4vcpat3vxcq"]
        }
        
        result = validator.validate_execution_envelope(envelope)
        
        assert result.is_valid
        assert result.message_type == "execution_envelope"
    
    def test_missing_required_fields(self, validator):
        """Test that missing required fields are detected."""
        envelope = {
            "intent_cid": "bafkreigtbhe57yqgt5zdwkqk3xdkkpbqmnt77ol62rluu5kvdrxj76tzgi"
        }
        
        result = validator.validate_execution_envelope(envelope)
        
        assert not result.is_valid
        assert len(result.errors) >= 2  # Missing interface_cid and input_cid
    
    def test_invalid_cid_format(self, validator):
        """Test that invalid CID format is detected."""
        envelope = {
            "interface_cid": "not-a-valid-cid",
            "input_cid": "bafkreigoqjtgmmkhwd5elifk4ggzwals3wfiankxnhnylm6lh67mtjwz3a"
        }
        
        result = validator.validate_execution_envelope(envelope)
        
        assert not result.is_valid
        assert any("cid" in error.lower() for error in result.errors)
    
    def test_parents_array_validation(self, validator):
        """Test validation of parents array."""
        envelope = {
            "interface_cid": "bafkreiapj52u5hi7pco5ebplvecv72olbnqglg2e7emwnmme4gguzsnpu4",
            "input_cid": "bafkreigoqjtgmmkhwd5elifk4ggzwals3wfiankxnhnylm6lh67mtjwz3a",
            "parents": ["bafkreihojjgp4soxeawgk64e4vhafpz3kdtlastu5hfnbdv5upb6c2cd7e", "invalid-parent"]
        }
        
        result = validator.validate_execution_envelope(envelope)
        
        assert not result.is_valid
        assert any("parent" in error.lower() for error in result.errors)
    
    def test_valid_execution_receipt(self, validator):
        """Test validation of a valid execution receipt."""
        receipt = {
            "output_cid": "bafkreiclrltegoplfz2o3djv7ydnyrozwrr5zkgw6lxmnzaxd7pnqdt62u",
            "receipt_cid": "bafkreif5oexc3wdpabmikptk5lvk6ireyzfyhuuwa2znh7bxbxtvpytfpy",
            "signature": "0x123abc..."
        }
        
        result = validator.validate_execution_receipt(receipt)
        
        assert result.is_valid
        assert result.message_type == "execution_receipt"
        assert result.metadata['signed']
    
    def test_receipt_missing_fields(self, validator):
        """Test that receipt without required fields fails."""
        receipt = {
            "output_cid": "bafkreiclrltegoplfz2o3djv7ydnyrozwrr5zkgw6lxmnzaxd7pnqdt62u"
            # Missing receipt_cid
        }
        
        result = validator.validate_execution_receipt(receipt)
        
        assert not result.is_valid
        assert any("receipt_cid" in error.lower() for error in result.errors)
    
    def test_cid_invocation_with_envelope(self, validator):
        """Test validation of CID-wrapped invocation."""
        invocation = {
            "envelope": {
                "interface_cid": "bafkreiapj52u5hi7pco5ebplvecv72olbnqglg2e7emwnmme4gguzsnpu4",
                "input_cid": "bafkreigoqjtgmmkhwd5elifk4ggzwals3wfiankxnhnylm6lh67mtjwz3a"
            },
            "invocation": {
                "method": "tools/call",
                "params": {"name": "test"}
            }
        }
        
        result = validator.validate_cid_invocation(invocation)
        
        assert result.is_valid
        assert result.message_type == "cid_invocation"

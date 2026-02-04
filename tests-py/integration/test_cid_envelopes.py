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
            "interface_cid": "bafyinterface123",
            "input_cid": "bafyinput456",
            "intent_cid": "bafyintent789",
            "parents": ["bafyparent1", "bafyparent2"]
        }
        
        result = validator.validate_execution_envelope(envelope)
        
        assert result.is_valid
        assert result.message_type == "execution_envelope"
    
    def test_missing_required_fields(self, validator):
        """Test that missing required fields are detected."""
        envelope = {
            "intent_cid": "bafyintent789"
        }
        
        result = validator.validate_execution_envelope(envelope)
        
        assert not result.is_valid
        assert len(result.errors) >= 2  # Missing interface_cid and input_cid
    
    def test_invalid_cid_format(self, validator):
        """Test that invalid CID format is detected."""
        envelope = {
            "interface_cid": "not-a-valid-cid",
            "input_cid": "bafyinput456"
        }
        
        result = validator.validate_execution_envelope(envelope)
        
        assert not result.is_valid
        assert any("cid" in error.lower() for error in result.errors)
    
    def test_parents_array_validation(self, validator):
        """Test validation of parents array."""
        envelope = {
            "interface_cid": "bafyinterface123",
            "input_cid": "bafyinput456",
            "parents": ["bafyparent1", "invalid-parent"]
        }
        
        result = validator.validate_execution_envelope(envelope)
        
        assert not result.is_valid
        assert any("parent" in error.lower() for error in result.errors)
    
    def test_valid_execution_receipt(self, validator):
        """Test validation of a valid execution receipt."""
        receipt = {
            "output_cid": "bafyoutput123",
            "receipt_cid": "bafyreceipt456",
            "signature": "0x123abc..."
        }
        
        result = validator.validate_execution_receipt(receipt)
        
        assert result.is_valid
        assert result.message_type == "execution_receipt"
        assert result.metadata['signed']
    
    def test_receipt_missing_fields(self, validator):
        """Test that receipt without required fields fails."""
        receipt = {
            "output_cid": "bafyoutput123"
            # Missing receipt_cid
        }
        
        result = validator.validate_execution_receipt(receipt)
        
        assert not result.is_valid
        assert any("receipt_cid" in error.lower() for error in result.errors)
    
    def test_cid_invocation_with_envelope(self, validator):
        """Test validation of CID-wrapped invocation."""
        invocation = {
            "envelope": {
                "interface_cid": "bafyinterface123",
                "input_cid": "bafyinput456"
            },
            "invocation": {
                "method": "tools/call",
                "params": {"name": "test"}
            }
        }
        
        result = validator.validate_cid_invocation(invocation)
        
        assert result.is_valid
        assert result.message_type == "cid_invocation"

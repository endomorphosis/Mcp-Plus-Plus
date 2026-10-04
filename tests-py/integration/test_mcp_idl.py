"""
Integration tests for MCP-IDL profile validation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from validators.mcp_idl import MCPIDLValidator


class TestMCPIDLProfile:
    """Test MCP-IDL (Profile A) validation."""
    
    @pytest.fixture
    def validator(self):
        return MCPIDLValidator()
    
    def test_valid_interface_descriptor(self, validator):
        """Test validation of a valid interface descriptor."""
        descriptor = {
            "name": "git",
            "namespace": "com.example.tools",
            "version": "1.2.0",
            "methods": [
                {
                    "name": "repo.status",
                    "input_schema_cid": "bafytest123",
                    "output_schema_cid": "bafytest456"
                }
            ],
            "errors": [
                {"name": "NotFound"},
                {"name": "Unauthorized"}
            ],
            "requires": ["mcp++/cid-envelope"],
            "compatibility": {
                "compatible_with": [],
                "supersedes": []
            },
            "semantic_tags": ["vcs", "git"]
        }
        
        result = validator.validate_descriptor(descriptor)
        
        assert result.is_valid
        assert result.message_type == "interface_descriptor"
        assert 'interface_cid' in result.metadata
    
    def test_missing_required_fields(self, validator):
        """Test that missing required fields are detected."""
        descriptor = {
            "name": "incomplete",
            "namespace": "com.example"
            # Missing version, methods, errors, requires, compatibility
        }
        
        result = validator.validate_descriptor(descriptor)
        
        assert not result.is_valid
        assert len(result.errors) >= 4  # At least 4 missing fields
    
    def test_invalid_version_format(self, validator):
        """Test that invalid semantic version triggers warning."""
        descriptor = {
            "name": "test",
            "namespace": "com.example",
            "version": "v1",  # Invalid semver
            "methods": [],
            "errors": [],
            "requires": [],
            "compatibility": {}
        }
        
        result = validator.validate_descriptor(descriptor)
        
        # Should still be valid but have warning
        assert result.is_valid
        assert len(result.warnings) > 0
        assert any("version" in warning.lower() for warning in result.warnings)
    
    def test_methods_array_validation(self, validator):
        """Test validation of methods array."""
        descriptor = {
            "name": "test",
            "namespace": "com.example",
            "version": "1.0.0",
            "methods": [
                {
                    "name": "method1",
                    "input_schema_cid": "bafytest",
                    "output_schema_cid": "bafytest2"
                },
                {
                    # Missing name
                    "input_schema_cid": "bafytest3"
                }
            ],
            "errors": [],
            "requires": [],
            "compatibility": {}
        }
        
        result = validator.validate_descriptor(descriptor)
        
        assert not result.is_valid
        assert any("method" in error.lower() for error in result.errors)
    
    def test_interface_cid_computation(self, validator):
        """Test that interface_cid is computed consistently."""
        descriptor = {
            "name": "test",
            "namespace": "com.example",
            "version": "1.0.0",
            "methods": [],
            "errors": [],
            "requires": [],
            "compatibility": {}
        }
        
        # Compute CID twice
        cid1 = validator.compute_interface_cid(descriptor)
        cid2 = validator.compute_interface_cid(descriptor)
        
        assert cid1 == cid2
        assert cid1.startswith("bafy")
    
    def test_interface_get_request(self, validator):
        """Test validation of interfaces/get request."""
        params = {
            "interface_cid": "bafytest123"
        }
        
        result = validator.validate_interface_get_request(params)
        
        assert result.is_valid
        assert result.message_type == "interfaces/get"
    
    def test_interface_get_missing_cid(self, validator):
        """Test that interfaces/get without CID fails."""
        params = {}
        
        result = validator.validate_interface_get_request(params)
        
        assert not result.is_valid
        assert any("interface_cid" in error.lower() for error in result.errors)
    
    def test_toolset_select_request(self, validator):
        """Test validation of interfaces/select request."""
        params = {
            "task_hint_cid": "bafytask123",
            "budget": 1000
        }
        
        result = validator.validate_toolset_select_request(params)
        
        assert result.is_valid
        assert result.message_type == "interfaces/select"
        assert result.metadata['has_task_hint']

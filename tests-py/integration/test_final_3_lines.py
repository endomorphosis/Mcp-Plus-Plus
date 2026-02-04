"""
Final 3 lines - lines 105-106, 126 in mcp_idl.py
"""

import pytest
from validators.mcp_idl import MCPIDLValidator


class TestFinal3Lines:
    """Target the final 3 uncovered lines in mcp_idl.py"""
    
    def test_line_126_missing_input_schema_cid(self):
        """Line 126 in mcp_idl.py: Method missing input_schema_cid"""
        validator = MCPIDLValidator()
        descriptor = {
            'name': 'test',
            'version': '1.0.0',
            'methods': [
                {
                    'name': 'method1',
                    'output_schema_cid': 'bafyreigbt'
                    # Intentionally missing input_schema_cid to hit line 126
                }
            ],
            'namespace': 'test',
            'errors': [],
            'requires': [],
            'compatibility': {}
        }
        result = validator.validate_descriptor(descriptor)
        # Should generate warning about missing input_schema_cid
        assert any("input_schema_cid" in str(warn) for warn in result.warnings)
    
    def test_lines_105_106_force_cid_exception(self):
        """Lines 105-106: Force exception in compute_interface_cid"""
        validator = MCPIDLValidator()
        
        # Monkey-patch compute_interface_cid to raise an exception
        original_method = validator.compute_interface_cid
        def mock_compute_cid(descriptor):
            raise Exception("Forced exception for testing")
        
        validator.compute_interface_cid = mock_compute_cid
        
        descriptor = {
            'name': 'test',
            'version': '1.0.0',
            'methods': [],
            'namespace': 'test',
            'errors': [],
            'requires': [],
            'compatibility': {}
        }
        result = validator.validate_descriptor(descriptor)
        
        # Should catch exception and add error
        assert any("Failed to compute interface_cid" in str(err) for err in result.errors)
        
        # Restore original method
        validator.compute_interface_cid = original_method

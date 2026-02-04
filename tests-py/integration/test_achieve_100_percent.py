"""
Comprehensive tests to achieve exactly 100% coverage.
Targeting the 24 remaining uncovered lines with surgical precision.
"""

import pytest
from validators.cid_artifacts import CIDExecutionValidator
from validators.mcp_idl import MCPIDLValidator
from validators.ucan_delegation import UCANDelegationValidator


class TestCIDArtifacts100Coverage:
    """Cover all 11 missing lines in cid_artifacts.py"""
    
    def setup_method(self):
        self.validator = CIDExecutionValidator()
    
    def test_line_58_invalid_intent_cid(self):
        """Hit line 58: Invalid intent_cid format error"""
        envelope = {
            'interface_cid': 'bafyreigbt5ldfjglkdjglkdjf',
            'input_cid': 'bafyreigbt5ldfjglkdjglkdjf',
            'intent_cid': 'invalid-cid-format'
        }
        result = self.validator.validate_execution_envelope(envelope)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any('Invalid intent_cid format' in e for e in errors)
    
    def test_lines_61_62_invalid_policy_cid(self):
        """Hit lines 61-62: Invalid policy_cid format error"""
        envelope = {
            'interface_cid': 'bafyreigbt5ldfjglkdjglkdjf',
            'input_cid': 'bafyreigbt5ldfjglkdjglkdjf',
            'policy_cid': 'bad-policy-cid'
        }
        result = self.validator.validate_execution_envelope(envelope)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any('Invalid policy_cid format' in e for e in errors)
    
    def test_lines_65_66_invalid_proof_cid(self):
        """Hit lines 65-66: Invalid proof_cid format error"""
        envelope = {
            'interface_cid': 'bafyreigbt5ldfjglkdjglkdjf',
            'input_cid': 'bafyreigbt5ldfjglkdjglkdjf',
            'proof_cid': 'xyz123'
        }
        result = self.validator.validate_execution_envelope(envelope)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any('Invalid proof_cid format' in e for e in errors)
    
    def test_line_105_invalid_receipt_cid(self):
        """Hit line 105: Invalid receipt_cid format error"""
        receipt = {
            'envelope_cid': 'bafyreigbt5ldfjglkdjglkdjf',
            'output_cid': 'bafyreigbt5ldfjglkdjglkdjf',
            'receipt_cid': 'notacid'
        }
        result = self.validator.validate_execution_receipt(receipt)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any('Invalid receipt_cid format' in e for e in errors)
    
    def test_line_127_cid_format_non_string(self):
        """Hit line 127: _is_valid_cid_format returns False for non-string"""
        assert self.validator._is_valid_cid_format(12345) == False
        assert self.validator._is_valid_cid_format(None) == False
        assert self.validator._is_valid_cid_format({'not': 'string'}) == False
    
    def test_line_149_missing_envelope_wrapper(self):
        """Hit line 149: Missing envelope wrapper error"""
        invocation = {
            'invocation': {'task': 'test'}
        }
        result = self.validator.validate_cid_invocation(invocation)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any("Missing 'envelope' wrapper" in e for e in errors)
    
    def test_lines_154_155_envelope_errors_propagate(self):
        """Hit lines 154-155: Envelope validation errors propagate"""
        invocation = {
            'envelope': {}  # Missing required fields
        }
        result = self.validator.validate_cid_invocation(invocation)
        assert not result.is_valid
    
    def test_line_159_missing_invocation_payload(self):
        """Hit line 159: Missing invocation payload warning"""
        invocation = {
            'envelope': {
                'interface_cid': 'bafyreigbt5ldfjglkdjglkdjf',
                'input_cid': 'bafyreigbt5ldfjglkdjglkdjf'
            }
        }
        result = self.validator.validate_cid_invocation(invocation)
        warnings = [str(w) for w in result.warnings]
        assert any("Missing 'invocation' payload" in w for w in warnings)


class TestMCPIDL100Coverage:
    """Cover all 9 missing lines in mcp_idl.py"""
    
    def setup_method(self):
        self.validator = MCPIDLValidator()
    
    def test_line_62_empty_name(self):
        """Hit line 62: Empty name string error"""
        descriptor = {
            'name': '',  # Empty string
            'version': '1.0.0',
            'methods': [],
            'namespace': 'test',
            'errors': [],
            'requires': [],
            'compatibility': {}
        }
        result = self.validator.validate_descriptor(descriptor)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any("'name' must be a non-empty string" in e for e in errors)
    
    def test_line_66_non_string_namespace(self):
        """Hit line 66: Namespace not a string error"""
        descriptor = {
            'name': 'test',
            'namespace': 12345,  # Not a string
            'version': '1.0.0',
            'methods': [],
            'errors': [],
            'requires': [],
            'compatibility': {}
        }
        result = self.validator.validate_descriptor(descriptor)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any("'namespace' must be a string" in e for e in errors)
    
    def test_line_70_non_string_version(self):
        """Hit line 70: Version not a string error"""
        descriptor = {
            'name': 'test',
            'version': 2.0,  # Not a string
            'methods': [],
            'namespace': 'test',
            'errors': [],
            'requires': [],
            'compatibility': {}
        }
        result = self.validator.validate_descriptor(descriptor)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any("'version' must be a string" in e for e in errors)
    
    def test_line_86_errors_not_list(self):
        """Hit line 86: Errors field not an array error"""
        descriptor = {
            'name': 'test',
            'version': '1.0.0',
            'methods': [],
            'namespace': 'test',
            'errors': 'not-a-list',  # Should be list
            'requires': [],
            'compatibility': {}
        }
        result = self.validator.validate_descriptor(descriptor)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any("'errors' must be an array" in e for e in errors)
    
    def test_line_91_requires_not_list(self):
        """Hit line 91: Requires field not an array error"""
        descriptor = {
            'name': 'test',
            'version': '1.0.0',
            'methods': [],
            'namespace': 'test',
            'errors': [],
            'requires': 'string',  # Should be list
            'compatibility': {}
        }
        result = self.validator.validate_descriptor(descriptor)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any("'requires' must be an array" in e for e in errors)
    
    def test_line_96_compatibility_not_dict(self):
        """Hit line 96: Compatibility field not an object error"""
        descriptor = {
            'name': 'test',
            'version': '1.0.0',
            'methods': [],
            'namespace': 'test',
            'errors': [],
            'requires': [],
            'compatibility': []  # Should be dict
        }
        result = self.validator.validate_descriptor(descriptor)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any("'compatibility' must be an object" in e for e in errors)
    
    def test_line_139_compatible_with_not_list(self):
        """Hit line 139: compatible_with not an array error"""
        descriptor = {
            'name': 'test',
            'version': '1.0.0',
            'methods': [],
            'namespace': 'test',
            'errors': [],
            'requires': [],
            'compatibility': {
                'compatible_with': 'string'  # Should be list
            }
        }
        result = self.validator.validate_descriptor(descriptor)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any("'compatible_with' must be an array" in e for e in errors)
    
    def test_line_143_supersedes_not_list(self):
        """Hit line 143: supersedes not an array error"""
        descriptor = {
            'name': 'test',
            'version': '1.0.0',
            'methods': [],
            'namespace': 'test',
            'errors': [],
            'requires': [],
            'compatibility': {
                'supersedes': 12345  # Should be list
            }
        }
        result = self.validator.validate_descriptor(descriptor)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any("'supersedes' must be an array" in e for e in errors)
    
    def test_line_246_budget_not_number(self):
        """Hit line 246: Budget parameter not a number error"""
        params = {
            'budget': 'not-a-number'
        }
        result = self.validator.validate_toolset_select_request(params)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any("'budget' parameter must be a number" in e for e in errors)


class TestUCANDelegation100Coverage:
    """Cover all 4 missing lines in ucan_delegation.py"""
    
    def setup_method(self):
        self.validator = UCANDelegationValidator()
    
    def test_lines_31_32_chain_not_list(self):
        """Hit lines 31-32: Delegation chain must be a list error"""
        chain = "not-a-list"
        result = self.validator.validate_delegation_chain(chain)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any("Delegation chain must be a list" in e for e in errors)
    
    def test_lines_52_53_token_not_dict(self):
        """Hit lines 52-53: Token must be an object error"""
        chain = ["string-instead-of-dict"]
        result = self.validator.validate_delegation_chain(chain)
        assert not result.is_valid
        errors = [str(e) for e in result.errors]
        assert any("must be an object" in e for e in errors)

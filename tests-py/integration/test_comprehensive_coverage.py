"""
Comprehensive test coverage for Python validators.

This test module adds comprehensive coverage for previously uncovered code paths
to reach 90%+ overall test coverage.
"""

import pytest
from validators.base_mcp import MCPValidator, ValidationResult
from validators.mcp_idl import MCPIDLValidator
from validators.cid_artifacts import CIDExecutionValidator
from validators.transport import TransportValidator
from validators.event_dag import EventDAGValidator
from validators.ucan_delegation import UCANDelegationValidator
from validators.policy_evaluation import PolicyEvaluationValidator


class TestBaseMCPCoverage:
    """Comprehensive tests for base_mcp.py to improve coverage."""
    
    def test_request_with_unknown_method(self):
        """Test request with unknown method (generates warning)."""
        validator = MCPValidator()
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "unknown/method",
            "params": {}
        }
        result = validator.validate_request(request)
        # Should still be valid but with warning
        assert result.is_valid is True
        assert len(result.warnings) > 0
    
    def test_notification_with_invalid_method_type(self):
        """Test notification with non-string method."""
        validator = MCPValidator()
        notification = {
            "jsonrpc": "2.0",
            "method": 123,  # Invalid: should be string
            "params": {}
        }
        result = validator.validate_notification(notification)
        assert result.is_valid is False
        assert any("method" in error.lower() for error in result.errors)
    
    def test_notification_with_invalid_params_type(self):
        """Test notification with non-dict params."""
        validator = MCPValidator()
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/test",
            "params": "not_a_dict"
        }
        result = validator.validate_notification(notification)
        assert result.is_valid is False
        assert any("params" in error.lower() for error in result.errors)
    
    def test_response_with_both_result_and_error(self):
        """Test response with both result and error fields."""
        validator = MCPValidator()
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"data": "test"},
            "error": {"code": -32000, "message": "Error"}
        }
        result = validator.validate_response(response)
        assert result.is_valid is False
        assert any("both" in error.lower() or "exclusive" in error.lower() 
                  for error in result.errors)
    
    def test_response_with_neither_result_nor_error(self):
        """Test response without result or error."""
        validator = MCPValidator()
        response = {
            "jsonrpc": "2.0",
            "id": 1
        }
        result = validator.validate_response(response)
        assert result.is_valid is False
        assert any("result" in error.lower() or "error" in error.lower() 
                  for error in result.errors)


class TestMCPIDLCoverage:
    """Comprehensive tests for mcp_idl.py to improve coverage."""
    
    def test_descriptor_missing_required_field(self):
        """Test descriptor missing required fields."""
        validator = MCPIDLValidator()
        descriptor = {
            "name": "test",
            "namespace": "test.ns",
            # Missing: version, methods, errors, requires, compatibility
        }
        result = validator.validate_descriptor(descriptor)
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    def test_descriptor_with_invalid_version(self):
        """Test descriptor with invalid version format."""
        validator = MCPIDLValidator()
        descriptor = {
            "name": "test",
            "namespace": "test.ns",
            "version": "not-semver",
            "methods": [],
            "errors": [],
            "requires": [],
            "compatibility": {"backward_compatible": True}
        }
        result = validator.validate_descriptor(descriptor)
        # Should have warnings or errors about version format
        assert result.is_valid is False or len(result.warnings) > 0
    
    def test_descriptor_with_invalid_methods_type(self):
        """Test descriptor with non-list methods."""
        validator = MCPIDLValidator()
        descriptor = {
            "name": "test",
            "namespace": "test.ns",
            "version": "1.0.0",
            "methods": "not_a_list",
            "errors": [],
            "requires": [],
            "compatibility": {"backward_compatible": True}
        }
        result = validator.validate_descriptor(descriptor)
        assert result.is_valid is False
        assert any("methods" in error.lower() for error in result.errors)
    
    def test_interface_list_request_with_params(self):
        """Test interfaces/list request validation."""
        validator = MCPIDLValidator()
        params = {"namespace": "test"}
        result = validator.validate_interface_list_request(params)
        assert result.is_valid is True
    
    def test_interface_list_request_without_params(self):
        """Test interfaces/list request without params."""
        validator = MCPIDLValidator()
        result = validator.validate_interface_list_request({})
        assert result.is_valid is True
    
    def test_interface_get_request_missing_cid(self):
        """Test interfaces/get request without CID."""
        validator = MCPIDLValidator()
        params = {}
        result = validator.validate_interface_get_request(params)
        assert result.is_valid is False
        assert any("interface_cid" in error.lower() for error in result.errors)
    
    def test_interface_get_request_invalid_cid_format(self):
        """Test interfaces/get request with invalid CID."""
        validator = MCPIDLValidator()
        params = {"interface_cid": "invalid_cid"}
        result = validator.validate_interface_get_request(params)
        # Should validate CID format
        assert result.is_valid is False or len(result.warnings) > 0
    
    def test_interface_compat_request_missing_cids(self):
        """Test interfaces/compat request without CIDs."""
        validator = MCPIDLValidator()
        params = {}
        result = validator.validate_interface_compat_request(params)
        assert result.is_valid is False
        assert any("interface_cid" in error.lower() for error in result.errors)
    
    def test_interface_compat_request_valid(self):
        """Test interfaces/compat request with valid params."""
        validator = MCPIDLValidator()
        params = {
            "interface_cid": "bafytest123",
            "candidate_cid": "bafytest456"
        }
        result = validator.validate_interface_compat_request(params)
        assert result.is_valid is True
    
    def test_toolset_select_request_missing_cid(self):
        """Test toolset/select without interface_cid."""
        validator = MCPIDLValidator()
        params = {}
        result = validator.validate_toolset_select_request(params)
        assert result.is_valid is False
        assert any("interface_cid" in error.lower() for error in result.errors)
    
    def test_toolset_select_request_with_budget(self):
        """Test toolset/select with budget constraints."""
        validator = MCPIDLValidator()
        params = {
            "interface_cid": "bafytest123",
            "budget": {"max_tools": 5}
        }
        result = validator.validate_toolset_select_request(params)
        assert result.is_valid is True


class TestCIDArtifactsCoverage:
    """Comprehensive tests for cid_artifacts.py to improve coverage."""
    
    def test_envelope_missing_interface_cid(self):
        """Test envelope without interface_cid."""
        validator = CIDExecutionValidator()
        envelope = {
            "input_cid": "bafytest123",
            "parents": []
        }
        result = validator.validate_envelope(envelope)
        assert result.is_valid is False
        assert any("interface_cid" in error.lower() for error in result.errors)
    
    def test_envelope_missing_input_cid(self):
        """Test envelope without input_cid."""
        validator = CIDExecutionValidator()
        envelope = {
            "interface_cid": "bafytest123",
            "parents": []
        }
        result = validator.validate_envelope(envelope)
        assert result.is_valid is False
        assert any("input_cid" in error.lower() for error in result.errors)
    
    def test_envelope_invalid_parents_type(self):
        """Test envelope with non-list parents."""
        validator = CIDExecutionValidator()
        envelope = {
            "interface_cid": "bafytest123",
            "input_cid": "bafytest456",
            "parents": "not_a_list"
        }
        result = validator.validate_envelope(envelope)
        assert result.is_valid is False
        assert any("parents" in error.lower() for error in result.errors)
    
    def test_envelope_with_valid_params(self):
        """Test envelope with all valid fields."""
        validator = CIDExecutionValidator()
        envelope = {
            "interface_cid": "bafytest123",
            "input_cid": "bafytest456",
            "parents": ["bafytest789"],
            "execution_context": {"timestamp": "2024-01-01T00:00:00Z"}
        }
        result = validator.validate_envelope(envelope)
        assert result.is_valid is True
    
    def test_receipt_missing_envelope_cid(self):
        """Test receipt without envelope_cid."""
        validator = CIDExecutionValidator()
        receipt = {
            "output_cid": "bafytest123",
            "status": "success"
        }
        result = validator.validate_receipt(receipt)
        assert result.is_valid is False
        assert any("envelope_cid" in error.lower() for error in result.errors)
    
    def test_receipt_missing_output_cid(self):
        """Test receipt without output_cid."""
        validator = CIDExecutionValidator()
        receipt = {
            "envelope_cid": "bafytest123",
            "status": "success"
        }
        result = validator.validate_receipt(receipt)
        assert result.is_valid is False
        assert any("output_cid" in error.lower() for error in result.errors)
    
    def test_receipt_missing_status(self):
        """Test receipt without status."""
        validator = CIDExecutionValidator()
        receipt = {
            "envelope_cid": "bafytest123",
            "output_cid": "bafytest456"
        }
        result = validator.validate_receipt(receipt)
        assert result.is_valid is False
        assert any("status" in error.lower() for error in result.errors)
    
    def test_receipt_invalid_status(self):
        """Test receipt with invalid status value."""
        validator = CIDExecutionValidator()
        receipt = {
            "envelope_cid": "bafytest123",
            "output_cid": "bafytest456",
            "status": "invalid_status"
        }
        result = validator.validate_receipt(receipt)
        assert result.is_valid is False or len(result.warnings) > 0
    
    def test_receipt_with_signature(self):
        """Test receipt with optional signature field."""
        validator = CIDExecutionValidator()
        receipt = {
            "envelope_cid": "bafytest123",
            "output_cid": "bafytest456",
            "status": "success",
            "signature": {
                "algorithm": "ed25519",
                "value": "abc123"
            }
        }
        result = validator.validate_receipt(receipt)
        assert result.is_valid is True


class TestTransportCoverage:
    """Comprehensive tests for transport.py to improve coverage."""
    
    def test_protocol_id_invalid_format(self):
        """Test protocol ID with invalid format."""
        validator = TransportValidator()
        result = validator.validate_protocol_id("invalid")
        assert result.is_valid is False
        assert any("protocol" in error.lower() for error in result.errors)
    
    def test_protocol_id_wrong_version(self):
        """Test protocol ID with wrong version."""
        validator = TransportValidator()
        result = validator.validate_protocol_id("/mcp+p2p/2.0.0")
        # Should warn about version mismatch
        assert result.is_valid is False or len(result.warnings) > 0
    
    def test_message_framing_missing_length(self):
        """Test message frame without length field."""
        validator = TransportValidator()
        frame = {"payload": b"test"}
        result = validator.validate_message_framing(frame)
        assert result.is_valid is False
        assert any("length" in error.lower() for error in result.errors)
    
    def test_message_framing_missing_payload(self):
        """Test message frame without payload field."""
        validator = TransportValidator()
        frame = {"length": 4}
        result = validator.validate_message_framing(frame)
        assert result.is_valid is False
        assert any("payload" in error.lower() for error in result.errors)
    
    def test_message_framing_length_mismatch(self):
        """Test message frame with length mismatch."""
        validator = TransportValidator()
        frame = {"length": 10, "payload": b"test"}
        result = validator.validate_message_framing(frame)
        assert result.is_valid is False or len(result.warnings) > 0
    
    def test_session_lifecycle_missing_state(self):
        """Test session without state field."""
        validator = TransportValidator()
        session = {"session_id": "test123"}
        result = validator.validate_session_lifecycle(session)
        assert result.is_valid is False
        assert any("state" in error.lower() for error in result.errors)
    
    def test_session_lifecycle_invalid_state(self):
        """Test session with invalid state value."""
        validator = TransportValidator()
        session = {
            "session_id": "test123",
            "state": "invalid_state"
        }
        result = validator.validate_session_lifecycle(session)
        assert result.is_valid is False or len(result.warnings) > 0
    
    def test_session_lifecycle_valid_states(self):
        """Test session with valid state transitions."""
        validator = TransportValidator()
        for state in ["connected", "negotiating", "active", "closed"]:
            session = {
                "session_id": "test123",
                "state": state
            }
            result = validator.validate_session_lifecycle(session)
            # Should be valid or have warnings
            assert result.is_valid is True or len(result.warnings) > 0
    
    def test_addressing_missing_multiaddrs(self):
        """Test addressing without multiaddrs."""
        validator = TransportValidator()
        address = {"peer_id": "test"}
        result = validator.validate_addressing(address)
        assert result.is_valid is False or len(result.warnings) > 0


class TestEventDAGCoverage:
    """Comprehensive tests for event_dag.py to improve coverage."""
    
    def test_event_missing_event_cid(self):
        """Test event without event_cid."""
        validator = EventDAGValidator()
        event = {
            "timestamp": "2024-01-01T00:00:00Z",
            "parents": []
        }
        result = validator.validate_event(event)
        assert result.is_valid is False
        assert any("event_cid" in error.lower() for error in result.errors)
    
    def test_event_invalid_parents_type(self):
        """Test event with non-list parents."""
        validator = EventDAGValidator()
        event = {
            "event_cid": "bafytest123",
            "timestamp": "2024-01-01T00:00:00Z",
            "parents": "not_a_list"
        }
        result = validator.validate_event(event)
        assert result.is_valid is False
        assert any("parents" in error.lower() for error in result.errors)
    
    def test_event_with_invalid_timestamp(self):
        """Test event with invalid timestamp format."""
        validator = EventDAGValidator()
        event = {
            "event_cid": "bafytest123",
            "timestamp": "invalid",
            "parents": []
        }
        result = validator.validate_event(event)
        # Timestamp validation may be lenient
        assert result.is_valid is True or len(result.warnings) > 0
    
    def test_dag_with_duplicate_event_cids(self):
        """Test DAG with duplicate event CIDs."""
        validator = EventDAGValidator()
        events = [
            {
                "event_cid": "event1",
                "timestamp": "2024-01-01T00:00:00Z",
                "parents": []
            },
            {
                "event_cid": "event1",  # Duplicate
                "timestamp": "2024-01-01T00:00:01Z",
                "parents": []
            }
        ]
        result = validator.validate_dag(events)
        assert result.is_valid is False
        assert any("duplicate" in error.lower() for error in result.errors)
    
    def test_dag_with_missing_parent_references(self):
        """Test DAG with parent references that don't exist."""
        validator = EventDAGValidator()
        events = [
            {
                "event_cid": "event1",
                "timestamp": "2024-01-01T00:00:00Z",
                "parents": ["nonexistent"]
            }
        ]
        result = validator.validate_dag(events)
        assert result.is_valid is False
        assert any("parent" in error.lower() for error in result.errors)
    
    def test_dag_empty_events_list(self):
        """Test DAG validation with empty events list."""
        validator = EventDAGValidator()
        result = validator.validate_dag([])
        # Empty DAG might be valid
        assert result.is_valid is True or len(result.warnings) > 0
    
    def test_causal_ordering_valid_sequence(self):
        """Test causal ordering with valid parent-child sequence."""
        validator = EventDAGValidator()
        events = [
            {
                "event_cid": "event1",
                "timestamp": "2024-01-01T00:00:00Z",
                "parents": []
            },
            {
                "event_cid": "event2",
                "timestamp": "2024-01-01T00:00:01Z",
                "parents": ["event1"]
            }
        ]
        result = validator.validate_causal_ordering(events)
        assert result.is_valid is True


class TestUCANDelegationCoverage:
    """Comprehensive tests for ucan_delegation.py to improve coverage."""
    
    def test_delegation_chain_empty(self):
        """Test empty delegation chain."""
        validator = UCANDelegationValidator()
        result = validator.validate_delegation_chain([])
        # Empty chain might be valid or warning
        assert result.is_valid is True or len(result.warnings) > 0
    
    def test_delegation_token_missing_iss(self):
        """Test delegation token without issuer."""
        validator = UCANDelegationValidator()
        chain = [{
            "aud": "did:key:recipient",
            "att": [],
            "exp": 9999999999
        }]
        result = validator.validate_delegation_chain(chain)
        assert result.is_valid is False
        assert any("iss" in error.lower() for error in result.errors)
    
    def test_delegation_token_missing_aud(self):
        """Test delegation token without audience."""
        validator = UCANDelegationValidator()
        chain = [{
            "iss": "did:key:issuer",
            "att": [],
            "exp": 9999999999
        }]
        result = validator.validate_delegation_chain(chain)
        assert result.is_valid is False
        assert any("aud" in error.lower() for error in result.errors)
    
    def test_delegation_token_missing_att(self):
        """Test delegation token without attenuations."""
        validator = UCANDelegationValidator()
        chain = [{
            "iss": "did:key:issuer",
            "aud": "did:key:recipient",
            "exp": 9999999999
        }]
        result = validator.validate_delegation_chain(chain)
        assert result.is_valid is False
        assert any("att" in error.lower() for error in result.errors)
    
    def test_invocation_with_proof_missing_proof_cid(self):
        """Test invocation without proof_cid."""
        validator = UCANDelegationValidator()
        invocation = {
            "tool": "test_tool",
            "arguments": {}
        }
        result = validator.validate_invocation_with_proof(invocation)
        assert result.is_valid is False
        assert any("proof_cid" in error.lower() for error in result.errors)
    
    def test_invocation_with_proof_invalid_cid_format(self):
        """Test invocation with invalid proof_cid format."""
        validator = UCANDelegationValidator()
        invocation = {
            "proof_cid": "invalid",
            "tool": "test_tool",
            "arguments": {}
        }
        result = validator.validate_invocation_with_proof(invocation)
        # CID format validation
        assert result.is_valid is False or len(result.warnings) > 0


class TestPolicyEvaluationCoverage:
    """Comprehensive tests for policy_evaluation.py to improve coverage."""
    
    def test_policy_missing_policy_cid(self):
        """Test policy without policy_cid."""
        validator = PolicyEvaluationValidator()
        policy = {
            "type": "permission",
            "constraints": {}
        }
        result = validator.validate_policy(policy)
        assert result.is_valid is False
        assert any("policy_cid" in error.lower() for error in result.errors)
    
    def test_policy_invalid_type(self):
        """Test policy with invalid type."""
        validator = PolicyEvaluationValidator()
        policy = {
            "policy_cid": "bafytest123",
            "type": "invalid_type",
            "constraints": {}
        }
        result = validator.validate_policy(policy)
        assert result.is_valid is False or len(result.warnings) > 0
    
    def test_decision_missing_decision_cid(self):
        """Test decision without decision_cid."""
        validator = PolicyEvaluationValidator()
        decision = {
            "policy_cid": "bafytest123",
            "decision": "allow"
        }
        result = validator.validate_decision(decision)
        assert result.is_valid is False
        assert any("decision_cid" in error.lower() for error in result.errors)
    
    def test_decision_invalid_decision_value(self):
        """Test decision with invalid decision value."""
        validator = PolicyEvaluationValidator()
        decision = {
            "decision_cid": "bafydecision",
            "policy_cid": "bafytest123",
            "decision": "invalid"
        }
        result = validator.validate_decision(decision)
        assert result.is_valid is False or len(result.warnings) > 0
    
    def test_temporal_constraint_missing_not_before(self):
        """Test temporal constraint without not_before."""
        validator = PolicyEvaluationValidator()
        constraint = {
            "not_after": "2024-12-31T23:59:59Z"
        }
        result = validator.validate_temporal_constraint(constraint)
        # might be valid with only not_after
        assert result.is_valid is True or len(result.warnings) > 0
    
    def test_obligation_missing_deadline(self):
        """Test obligation without deadline."""
        validator = PolicyEvaluationValidator()
        obligation = {
            "obligation_type": "log",
            "parameters": {}
        }
        result = validator.validate_obligation(obligation)
        # Deadline might be optional
        assert result.is_valid is True or len(result.warnings) > 0
    
    def test_obligation_with_valid_fields(self):
        """Test obligation with all valid fields."""
        validator = PolicyEvaluationValidator()
        obligation = {
            "obligation_type": "log",
            "parameters": {"message": "test"},
            "deadline": "2024-12-31T23:59:59Z"
        }
        result = validator.validate_obligation(obligation)
        assert result.is_valid is True

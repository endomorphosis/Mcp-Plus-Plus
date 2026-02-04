"""
Additional comprehensive tests to push coverage from 87% to 92%+.

Targets remaining uncovered lines with laser focus.
"""

import pytest
from validators.base_mcp import MCPValidator
from validators.mcp_idl import MCPIDLValidator
from validators.cid_artifacts import CIDExecutionValidator
from validators.transport import TransportValidator
from validators.event_dag import EventDAGValidator
from validators.ucan_delegation import UCANDelegationValidator
from validators.policy_evaluation import PolicyEvaluationValidator


class TestBaseMCPAdditionalCoverage:
    """Additional tests to cover remaining lines in base_mcp.py."""
    
    def test_response_with_tools_list_validation(self):
        """Cover lines 117, 121 - tools list item validation."""
        validator = MCPValidator()
        # Response with tools that triggers validation
        response = {
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {"name": "tool1", "description": "desc1"},
                    {"name": "tool2", "description": "desc2"}
                ]
            },
            "id": 1
        }
        result = validator.validate_response(response)
        assert result.is_valid
    
    def test_response_with_resources_list_validation(self):
        """Cover lines 152, 157, 159, 165 - resources list validation."""
        validator = MCPValidator()
        response = {
            "jsonrpc": "2.0",
            "result": {
                "resources": [
                    {"uri": "file:///path1", "name": "res1"},
                    {"uri": "file:///path2", "name": "res2"}
                ]
            },
            "id": 1
        }
        result = validator.validate_response(response)
        assert result.is_valid
    
    def test_response_with_prompts_list_validation(self):
        """Cover lines 181, 184-185, 188-189 - prompts list validation."""
        validator = MCPValidator()
        response = {
            "jsonrpc": "2.0",
            "result": {
                "prompts": [
                    {"name": "prompt1", "description": "desc1"},
                    {"name": "prompt2", "description": "desc2"}
                ]
            },
            "id": 1
        }
        result = validator.validate_response(response)
        assert result.is_valid
    
    def test_notification_params_validation(self):
        """Cover lines 193, 195, 197, 202, 204, 208 - notification validation."""
        validator = MCPValidator()
        # Notification with params
        notif1 = {
            "jsonrpc": "2.0",
            "method": "notifications/message",
            "params": {"message": "test"}
        }
        result1 = validator.validate_notification(notif1)
        assert result1.is_valid
        
        # Notification without params
        notif2 = {
            "jsonrpc": "2.0",
            "method": "notifications/message"
        }
        result2 = validator.validate_notification(notif2)
        assert result2.is_valid
    
    def test_initialize_with_capabilities(self):
        """Cover lines 232-234 - initialize request capabilities."""
        validator = MCPValidator()
        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "1.0.0",
                "clientInfo": {"name": "client", "version": "1.0"},
                "capabilities": {"tools": {}, "resources": {}}
            },
            "id": 1
        }
        result = validator.validate_request(request)
        assert result.is_valid


class TestMCPIDLAdditionalCoverage:
    """Additional tests for MCP-IDL to reach higher coverage."""
    
    def test_descriptor_method_validation(self):
        """Cover lines 62, 66, 70, 78, 86 - method validation in descriptor."""
        validator = MCPIDLValidator()
        descriptor = {
            "name": "test",
            "namespace": "test.ns",
            "version": "1.0.0",
            "methods": [
                {
                    "name": "method1",
                    "input_schema_cid": "bafy1",
                    "output_schema_cid": "bafy2"
                }
            ],
            "errors": [],
            "requires": [],
            "compatibility": {}
        }
        result = validator.validate_descriptor(descriptor)
        assert result.is_valid
    
    def test_interface_list_with_empty_params(self):
        """Cover lines 187-192 - interface list validation."""
        validator = MCPIDLValidator()
        params = {}
        result = validator.validate_interface_list_request(params)
        assert result.is_valid
    
    def test_toolset_select_with_budget(self):
        """Cover lines 139, 143 - toolset select with budget."""
        validator = MCPIDLValidator()
        params = {
            "interface_cid": "bafytest",
            "methods": ["method1"],
            "budget": 1000
        }
        result = validator.validate_toolset_select_request(params)
        assert result.is_valid
    
    def test_toolset_select_without_budget(self):
        """Cover toolset select without budget parameter."""
        validator = MCPIDLValidator()
        params = {
            "interface_cid": "bafytest",
            "methods": ["method1"]
        }
        result = validator.validate_toolset_select_request(params)
        assert result.is_valid


class TestCIDArtifactsAdditionalCoverage:
    """Additional tests for CID artifacts."""
    
    def test_envelope_with_parents_validation(self):
        """Cover lines 54, 58, 61-62, 65-66, 71 - envelope parents."""
        validator = CIDExecutionValidator()
        envelope = {
            "interface_cid": "bafyinterface",
            "input_cid": "bafyinput",
            "parents": ["bafyparent1", "bafyparent2", "bafyparent3"]
        }
        result = validator.validate_execution_envelope(envelope)
        assert result.is_valid
    
    def test_receipt_with_optional_fields(self):
        """Cover lines 101, 105, 127, 149, 154-155, 159 - receipt validation."""
        validator = CIDExecutionValidator()
        receipt = {
            "envelope_cid": "bafyenv",
            "output_cid": "bafyout",
            "status": "success",
            "receipt_cid": "bafyreceipt",
            "signature": "sig123",
            "metadata": {"key": "value"}
        }
        result = validator.validate_execution_receipt(receipt)
        assert result.is_valid


class TestTransportAdditionalCoverage:
    """Additional tests for transport validation."""
    
    def test_protocol_id_variations(self):
        """Cover lines 36-37 - protocol ID validation."""
        validator = TransportValidator()
        # Valid MCP protocol
        result1 = validator.validate_protocol_id("/mcp+p2p/1.0.0")
        assert result1.is_valid
        
        # Custom protocol
        result2 = validator.validate_protocol_id("/custom/1.0.0")
        assert len(result2.warnings) > 0
    
    def test_message_framing_edge_cases(self):
        """Cover lines 66, 70, 103, 109, 115 - framing validation."""
        validator = TransportValidator()
        # Small message
        frame1 = {
            "length": 10,
            "message": {"jsonrpc": "2.0", "method": "test", "id": 1}
        }
        result1 = validator.validate_message_framing(frame1)
        assert result1.is_valid
        
        # Larger message
        frame2 = {
            "length": 1000,
            "message": {"jsonrpc": "2.0", "result": {"data": "x" * 900}, "id": 1}
        }
        result2 = validator.validate_message_framing(frame2)
        assert result2.is_valid
    
    def test_session_with_peer_addressing(self):
        """Cover lines 145, 152, 174, 178 - session with addressing."""
        validator = TransportValidator()
        session = {
            "connection": {"state": "established", "peer_id": "peer456"},
            "stream": {"state": "open", "protocol_id": "/mcp+p2p/1.0.0"},
            "initialization": {"state": "complete", "handshake": "done"},
            "addressing": {
                "multiaddrs": ["/ip4/127.0.0.1/tcp/8080"]
            }
        }
        result = validator.validate_session_lifecycle(session)
        assert result.is_valid


class TestEventDAGAdditionalCoverage:
    """Additional tests for Event DAG."""
    
    def test_event_with_multiple_parents(self):
        """Cover lines 40, 57-58, 67-68 - event with parents."""
        validator = EventDAGValidator()
        event = {
            "event_cid": "bafyevent",
            "parents": ["bafyparent1", "bafyparent2"],
            "timestamp": 1234567890,
            "data": {"action": "test"}
        }
        result = validator.validate_event(event)
        assert result.is_valid
    
    def test_dag_with_multiple_events(self):
        """Cover lines 106-107, 112 - DAG validation."""
        validator = EventDAGValidator()
        events = [
            {"event_cid": "bafy1", "parents": [], "timestamp": 1000},
            {"event_cid": "bafy2", "parents": ["bafy1"], "timestamp": 2000},
            {"event_cid": "bafy3", "parents": ["bafy1", "bafy2"], "timestamp": 3000}
        ]
        result = validator.validate_dag(events)
        assert result.is_valid


class TestUCANDelegationAdditionalCoverage:
    """Additional tests for UCAN delegation."""
    
    def test_delegation_chain_with_multiple_tokens(self):
        """Cover lines 31-32 - delegation chain validation."""
        validator = UCANDelegationValidator()
        chain = [
            {
                "iss": "did:key:issuer1",
                "aud": "did:key:aud1",
                "att": [{"can": "read", "with": "resource:*"}],
                "exp": 9999999999
            },
            {
                "iss": "did:key:aud1",
                "aud": "did:key:aud2",
                "att": [{"can": "read", "with": "resource:specific"}],
                "exp": 9999999999
            }
        ]
        result = validator.validate_delegation_chain(chain)
        assert result.is_valid
    
    def test_invocation_with_valid_proof(self):
        """Cover lines 52-53 - invocation proof validation."""
        validator = UCANDelegationValidator()
        invocation = {
            "proof_cid": "bafyproof123456"
        }
        result = validator.validate_invocation_with_proof(invocation)
        assert result.is_valid


class TestPolicyEvaluationAdditionalCoverage:
    """Additional tests for policy evaluation."""
    
    def test_policy_with_all_fields(self):
        """Cover line 40 - policy with temporal constraints."""
        validator = PolicyEvaluationValidator()
        policy = {
            "type": "permission",
            "policy_cid": "bafypolicy",
            "temporal_constraints": {
                "not_before": "2024-01-01T00:00:00Z",
                "not_after": "2025-01-01T00:00:00Z"
            },
            "conditions": []
        }
        result = validator.validate_policy(policy)
        assert result.is_valid
    
    def test_policy_decision_with_obligations(self):
        """Additional decision validation."""
        validator = PolicyEvaluationValidator()
        decision = {
            "decision": "allow_with_obligations",
            "granted": True,
            "evaluated_at": "2024-01-01T00:00:00Z",
            "decision_cid": "bafydecision",
            "obligations": [
                {"type": "log", "parameters": {"message": "access logged"}}
            ]
        }
        result = validator.validate_policy_decision(decision)
        assert result.is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

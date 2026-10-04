"""
Integration tests for temporal deontic policy evaluation (Profile D).

Tests validate compliance with docs/spec/temporal-deontic-policy.md
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from validators.policy_evaluation import PolicyEvaluationValidator


class TestPolicyEvaluation:
    """Test temporal deontic policy validation."""
    
    @pytest.fixture
    def validator(self):
        return PolicyEvaluationValidator()
    
    def test_valid_permission_policy(self, validator):
        """
        Test validation of a permission policy.
        
        Spec: docs/spec/temporal-deontic-policy.md
        Requirement: Policies MUST express permissions/prohibitions/obligations
        """
        policy = {
            "type": "permission",
            "action": "tool/execute",
            "resource": "weather-api",
            "temporal_constraints": {
                "valid_from": "2024-01-01T00:00:00Z",
                "valid_until": "2024-12-31T23:59:59Z"
            }
        }
        
        result = validator.validate_policy(policy)
        
        assert result.is_valid
        assert result.message_type == "policy"
    
    def test_valid_prohibition_policy(self, validator):
        """
        Test validation of a prohibition policy.
        
        Spec: mcp++-profiles-draft.md:136
        Requirement: Policies MUST express prohibitions
        """
        policy = {
            "type": "prohibition",
            "action": "data/delete",
            "resource": "critical-data",
            "temporal_constraints": {
                "always": True
            }
        }
        
        result = validator.validate_policy(policy)
        
        assert result.is_valid
    
    def test_valid_obligation_policy(self, validator):
        """
        Test validation of an obligation policy.
        
        Spec: mcp++-profiles-draft.md:137
        Requirement: Policies MUST express obligations
        """
        policy = {
            "type": "obligation",
            "action": "audit/log",
            "trigger": "after_execution",
            "temporal_constraints": {
                "deadline": "2024-12-31T23:59:59Z"
            }
        }
        
        result = validator.validate_policy(policy)
        
        assert result.is_valid
    
    def test_policy_missing_type(self, validator):
        """
        Test that policies must specify type.
        
        Spec: docs/spec/temporal-deontic-policy.md
        """
        policy = {
            "action": "tool/execute",
            "temporal_constraints": {}
        }
        
        result = validator.validate_policy(policy)
        
        assert not result.is_valid
        assert any("type" in error.lower() for error in result.errors)
    
    def test_invalid_policy_type(self, validator):
        """
        Test that policy type must be valid.
        
        Spec: docs/spec/temporal-deontic-policy.md
        Requirement: Must be permission, prohibition, or obligation
        """
        policy = {
            "type": "invalid-type",
            "action": "tool/execute",
            "temporal_constraints": {}
        }
        
        result = validator.validate_policy(policy)
        
        assert not result.is_valid
        assert any("invalid" in error.lower() for error in result.errors)
    
    def test_policy_decision_allow(self, validator):
        """
        Test validation of policy decision with 'allow' result.
        
        Spec: cid-native-artifacts.md:86
        Requirement: Decision SHOULD support allow/deny/allow_with_obligations
        """
        decision = {
            "decision_cid": "bafydecision123",
            "granted": True,
            "decision": "allow",
            "evaluated_at": "2024-01-01T12:00:00Z"
        }
        
        result = validator.validate_policy_decision(decision)
        
        assert result.is_valid
        assert result.message_type == "policy_decision"
    
    def test_policy_decision_deny(self, validator):
        """
        Test validation of policy decision with 'deny' result.
        
        Spec: cid-native-artifacts.md:86
        """
        decision = {
            "decision_cid": "bafydecision456",
            "granted": False,
            "decision": "deny",
            "evaluated_at": "2024-01-01T12:00:00Z",
            "reason": "Policy violation: insufficient permissions"
        }
        
        result = validator.validate_policy_decision(decision)
        
        assert result.is_valid
    
    def test_policy_decision_with_obligations(self, validator):
        """
        Test validation of policy decision with obligations.
        
        Spec: mcp++-profiles-draft.md:146
        Requirement: Decisions MAY spawn obligations with deadlines
        """
        decision = {
            "decision_cid": "bafydecision789",
            "granted": True,
            "decision": "allow_with_obligations",
            "evaluated_at": "2024-01-01T12:00:00Z",
            "obligations": [
                {
                    "type": "audit_log",
                    "deadline": "2024-01-01T13:00:00Z"
                }
            ]
        }
        
        result = validator.validate_policy_decision(decision)
        
        assert result.is_valid
    
    def test_policy_decision_missing_required_fields(self, validator):
        """
        Test that policy decisions must include required fields.
        
        Spec: mcp++-profiles-draft.md:144
        Requirement: Runtime MUST emit decision_cid
        """
        decision = {
            "decision_cid": "bafydecision123"
            # Missing granted and evaluated_at
        }
        
        result = validator.validate_policy_decision(decision)
        
        assert not result.is_valid
        assert len(result.errors) >= 2
    
    def test_policy_with_temporal_constraints(self, validator):
        """
        Test validation of temporal constraints.
        
        Spec: docs/spec/temporal-deontic-policy.md
        Requirement: Policies MUST express temporal constraints
        """
        policy = {
            "type": "permission",
            "action": "tool/execute",
            "temporal_constraints": {
                "valid_from": "2024-01-01T00:00:00Z",
                "valid_until": "2024-12-31T23:59:59Z",
                "time_of_day": {"start": "09:00", "end": "17:00"},
                "days_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            }
        }
        
        result = validator.validate_policy(policy)
        
        assert result.is_valid
    
    def test_policy_content_addressed(self, validator):
        """
        Test that policies can be content-addressed.
        
        Spec: mcp++-profiles-draft.md:134
        Requirement: Policies MUST be content-addressed (policy_cid)
        """
        policy = {
            "type": "permission",
            "action": "tool/execute",
            "temporal_constraints": {}
        }
        
        result = validator.validate_policy(policy)
        
        # Should be valid and computable as a CID
        assert result.is_valid
        # In a full implementation, would verify CID computation

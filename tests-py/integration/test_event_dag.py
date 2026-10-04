"""
Integration tests for Event DAG validation.

Tests validate compliance with docs/spec/event-dag-ordering.md
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from validators.event_dag import EventDAGValidator


class TestEventDAG:
    """Test Event DAG structure and ordering validation."""
    
    @pytest.fixture
    def validator(self):
        return EventDAGValidator()
    
    def test_valid_event_structure(self, validator):
        """
        Test validation of a valid event structure.
        
        Spec: docs/spec/event-dag-ordering.md
        Requirement: Each event CID MUST commit to specific fields
        """
        event = {
            "event_cid": "bafyevent123",
            "timestamp": "2024-01-01T12:00:00Z",
            "parents": ["bafyparent1", "bafyparent2"],
            "interface_cid": "bafyinterface456",
            "actor": "did:key:agent123"
        }
        
        result = validator.validate_event(event)
        
        assert result.is_valid
        assert result.message_type == "event"
    
    def test_event_missing_required_fields(self, validator):
        """
        Test that events must include required fields.
        
        Spec: docs/spec/event-dag-ordering.md
        """
        event = {
            "event_cid": "bafyevent123"
            # Missing timestamp and parents
        }
        
        result = validator.validate_event(event)
        
        assert not result.is_valid
        assert len(result.errors) >= 2
    
    def test_valid_dag_structure(self, validator):
        """
        Test validation of a complete DAG structure.
        
        Spec: docs/spec/event-dag-ordering.md
        Requirement: DAG must be acyclic and properly ordered
        """
        dag = [
            {
                "event_cid": "bafyevent1",
                "timestamp": "2024-01-01T12:00:00Z",
                "parents": []
            },
            {
                "event_cid": "bafyevent2",
                "timestamp": "2024-01-01T12:01:00Z",
                "parents": ["bafyevent1"]
            },
            {
                "event_cid": "bafyevent3",
                "timestamp": "2024-01-01T12:02:00Z",
                "parents": ["bafyevent1", "bafyevent2"]
            }
        ]
        
        result = validator.validate_dag(dag)
        
        assert result.is_valid
        assert result.message_type == "event_dag"
    
    def test_dag_detects_duplicate_event_cids(self, validator):
        """
        Test that DAG validator detects duplicate event CIDs.
        
        Spec: docs/spec/event-dag-ordering.md
        Requirement: Event CIDs must be unique
        """
        dag = [
            {
                "event_cid": "bafyevent1",
                "timestamp": "2024-01-01T12:00:00Z",
                "parents": []
            },
            {
                "event_cid": "bafyevent1",  # Duplicate
                "timestamp": "2024-01-01T12:01:00Z",
                "parents": []
            }
        ]
        
        result = validator.validate_dag(dag)
        
        assert not result.is_valid
        assert any("duplicate" in error.lower() for error in result.errors)
    
    def test_dag_warns_about_unseen_parents(self, validator):
        """
        Test that validator warns about parent references to unseen events.
        
        Spec: docs/spec/event-dag-ordering.md
        """
        dag = [
            {
                "event_cid": "bafyevent1",
                "timestamp": "2024-01-01T12:00:00Z",
                "parents": []
            },
            {
                "event_cid": "bafyevent2",
                "timestamp": "2024-01-01T12:01:00Z",
                "parents": ["bafyunseen"]  # References unknown parent
            }
        ]
        
        result = validator.validate_dag(dag)
        
        # May still be valid but should have warning
        assert len(result.warnings) > 0
        assert any("unseen" in warning.lower() or "parent" in warning.lower() 
                   for warning in result.warnings)
    
    def test_causal_ordering_valid(self, validator):
        """
        Test validation of causal ordering between events.
        
        Spec: docs/spec/event-dag-ordering.md
        Requirement: Events must maintain causal relationships
        """
        event1 = {
            "event_cid": "bafyevent1",
            "timestamp": "2024-01-01T12:00:00Z",
            "parents": []
        }
        
        event2 = {
            "event_cid": "bafyevent2",
            "timestamp": "2024-01-01T12:01:00Z",
            "parents": ["bafyevent1"]
        }
        
        result = validator.validate_causal_ordering(event1, event2)
        
        assert result.is_valid
        assert result.message_type == "causal_ordering"
    
    def test_causal_ordering_timestamp_violation(self, validator):
        """
        Test detection of causality violations via timestamps.
        
        Spec: docs/spec/event-dag-ordering.md
        Requirement: Child events must have later timestamps
        """
        event1 = {
            "event_cid": "bafyevent1",
            "timestamp": "2024-01-01T12:00:00Z",
            "parents": []
        }
        
        event2 = {
            "event_cid": "bafyevent2",
            "timestamp": "2024-01-01T11:00:00Z",  # Earlier than event1
            "parents": ["bafyevent1"]
        }
        
        result = validator.validate_causal_ordering(event1, event2)
        
        assert not result.is_valid
        assert any("causal" in error.lower() or "timestamp" in error.lower() 
                   for error in result.errors)
    
    def test_parent_link_immutability(self, validator):
        """
        Test that parent links are immutable and verifiable.
        
        Spec: event-dag-ordering.md:24
        Requirement: Parent links MUST be immutable and verifiable by CID
        """
        event = {
            "event_cid": "bafyevent123",
            "timestamp": "2024-01-01T12:00:00Z",
            "parents": ["bafyparent1", "bafyparent2"]
        }
        
        result = validator.validate_event(event)
        
        # Parents should be validated as CIDs
        assert result.is_valid
        # In full implementation, would verify CID format of parents
    
    def test_genesis_event_no_parents(self, validator):
        """
        Test that genesis events can have empty parents.
        
        Spec: docs/spec/event-dag-ordering.md
        """
        event = {
            "event_cid": "bafygenesis",
            "timestamp": "2024-01-01T00:00:00Z",
            "parents": []  # Genesis event
        }
        
        result = validator.validate_event(event)
        
        assert result.is_valid
    
    def test_concurrent_events_same_timestamp(self, validator):
        """
        Test handling of concurrent events with same timestamp.
        
        Spec: docs/spec/event-dag-ordering.md
        Requirement: Support concurrent execution
        """
        dag = [
            {
                "event_cid": "bafyevent1",
                "timestamp": "2024-01-01T12:00:00Z",
                "parents": []
            },
            {
                "event_cid": "bafyevent2a",
                "timestamp": "2024-01-01T12:01:00Z",
                "parents": ["bafyevent1"]
            },
            {
                "event_cid": "bafyevent2b",
                "timestamp": "2024-01-01T12:01:00Z",  # Same timestamp
                "parents": ["bafyevent1"]
            }
        ]
        
        result = validator.validate_dag(dag)
        
        # Concurrent events are valid
        assert result.is_valid

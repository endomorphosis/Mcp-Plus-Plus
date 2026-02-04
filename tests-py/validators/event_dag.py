"""
Event DAG Validator

Validates Event DAG structures according to docs/spec/event-dag-ordering.md
"""

from typing import Any, Dict, List, Set
from .base_mcp import ValidationResult


class EventDAGValidator:
    """
    Validates Event DAG (Directed Acyclic Graph) structures for provenance.
    
    Based on: docs/spec/event-dag-ordering.md
    """
    
    def validate_event(self, event: Dict[str, Any]) -> ValidationResult:
        """
        Validate a single event structure.
        
        Args:
            event: The event object
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='event')
        
        # Required fields
        required_fields = ['event_cid', 'timestamp', 'parents']
        
        for field in required_fields:
            if field not in event:
                result.add_error(f"Event missing required field: {field}")
        
        # Validate parents array
        if 'parents' in event:
            if not isinstance(event['parents'], list):
                result.add_error("'parents' must be a list")
        
        return result
    
    def validate_dag(self, dag: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate an entire Event DAG.
        
        Args:
            dag: List of events forming a DAG
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='event_dag')
        
        if not isinstance(dag, list):
            result.add_error("DAG must be a list of events")
            return result
        
        # Track seen event CIDs to detect cycles
        seen_cids: Set[str] = set()
        
        for i, event in enumerate(dag):
            # Validate individual event
            event_result = self.validate_event(event)
            if not event_result.is_valid:
                result.errors.extend(event_result.errors)
                result.is_valid = False
            
            # Check for duplicate event CIDs
            if 'event_cid' in event:
                event_cid = event['event_cid']
                if event_cid in seen_cids:
                    result.add_error(f"Duplicate event_cid: {event_cid}")
                seen_cids.add(event_cid)
            
            # Validate parent references exist
            if 'parents' in event and isinstance(event['parents'], list):
                for parent_cid in event['parents']:
                    if parent_cid not in seen_cids and i > 0:
                        result.add_warning(
                            f"Event {event.get('event_cid', i)} references "
                            f"unseen parent: {parent_cid}"
                        )
        
        return result
    
    def validate_causal_ordering(
        self, 
        event1: Dict[str, Any], 
        event2: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate causal ordering between two events.
        
        Args:
            event1: First event
            event2: Second event (should be causally after event1)
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='causal_ordering')
        
        if 'event_cid' not in event1 or 'event_cid' not in event2:
            result.add_error("Both events must have event_cid")
            return result
        
        # Check if event2 references event1 in its parents
        if 'parents' in event2 and isinstance(event2['parents'], list):
            if event1['event_cid'] not in event2['parents']:
                result.add_warning(
                    f"Event {event2['event_cid']} does not reference "
                    f"{event1['event_cid']} as parent"
                )
        
        # Check timestamps
        if 'timestamp' in event1 and 'timestamp' in event2:
            if event2['timestamp'] < event1['timestamp']:
                result.add_error(
                    "Causal violation: event2 timestamp precedes event1"
                )
        
        return result

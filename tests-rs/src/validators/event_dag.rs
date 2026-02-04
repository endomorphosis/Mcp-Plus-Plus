//! Event DAG Validator
//!
//! Validates event structures and DAG properties.
//! SPEC: Event-DAG.md

use crate::models::*;
use crate::validators::base_mcp::{ValidationError, ValidationResult};
use serde_json::Value;
use serde_valid::Validate;
use std::collections::{HashMap, HashSet};

/// Event DAG Validator
pub struct EventDAGValidator;

impl EventDAGValidator {
    pub fn new() -> Self {
        Self
    }
    
    /// Validate an event structure
    /// SPEC: Event-DAG.md § Event Structure, MUST
    pub fn validate_event(&self, payload: &Value) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("event".to_string());
        
        let event: Event = serde_json::from_value(payload.clone())?;
        
        if let Err(e) = event.validate() {
            result.add_error(format!("Validation error: {}", e));
            return Ok(result);
        }
        
        // Parents can be empty for genesis events
        if event.parents.is_empty() {
            result.add_warning("Event has no parents (genesis event)".to_string());
        }
        
        Ok(result)
    }
    
    /// Check DAG acyclicity by detecting cycles
    /// SPEC: Event-DAG.md § DAG Properties, MUST
    pub fn check_acyclicity(&self, events: &[Event]) -> Result<bool, ValidationError> {
        let mut graph: HashMap<String, Vec<String>> = HashMap::new();
        
        // Build adjacency list
        for event in events {
            graph.insert(event.event_cid.clone(), event.parents.clone());
        }
        
        // Check for cycles using DFS
        let mut visited = HashSet::new();
        let mut rec_stack = HashSet::new();
        
        for event in events {
            if !visited.contains(&event.event_cid) {
                if self.has_cycle(&event.event_cid, &graph, &mut visited, &mut rec_stack) {
                    return Ok(false);
                }
            }
        }
        
        Ok(true)
    }
    
    fn has_cycle(
        &self,
        node: &str,
        graph: &HashMap<String, Vec<String>>,
        visited: &mut HashSet<String>,
        rec_stack: &mut HashSet<String>,
    ) -> bool {
        visited.insert(node.to_string());
        rec_stack.insert(node.to_string());
        
        if let Some(parents) = graph.get(node) {
            for parent in parents {
                if !visited.contains(parent) {
                    if self.has_cycle(parent, graph, visited, rec_stack) {
                        return true;
                    }
                } else if rec_stack.contains(parent) {
                    return true;
                }
            }
        }
        
        rec_stack.remove(node);
        false
    }
}

impl Default for EventDAGValidator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    
    #[test]
    fn test_valid_event() {
        let validator = EventDAGValidator::new();
        let payload = json!({
            "event_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": ["QmPreviousEvent"],
            "payload": {"data": "test"},
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_event(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_acyclicity_valid() {
        let validator = EventDAGValidator::new();
        let events = vec![
            Event {
                event_cid: "event1".to_string(),
                parents: vec![],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:00Z".to_string(),
            },
            Event {
                event_cid: "event2".to_string(),
                parents: vec!["event1".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:01Z".to_string(),
            },
        ];
        
        assert!(validator.check_acyclicity(&events).unwrap());
    }
    
    // Additional comprehensive tests
    
    #[test]
    fn test_event_genesis_no_parents() {
        let validator = EventDAGValidator::new();
        let payload = json!({
            "event_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": [],
            "payload": {"data": "genesis"},
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_event(&payload).unwrap();
        assert!(result.is_valid);
        assert!(!result.warnings.is_empty(), "Should have warning for genesis event");
    }
    
    #[test]
    fn test_event_missing_cid() {
        let validator = EventDAGValidator::new();
        let payload = json!({
            "parents": ["QmPreviousEvent"],
            "payload": {"data": "test"},
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_event(&payload);
        assert!(result.is_err(), "Should fail due to missing event_cid");
    }
    
    #[test]
    fn test_event_missing_timestamp() {
        let validator = EventDAGValidator::new();
        let payload = json!({
            "event_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": ["QmPreviousEvent"],
            "payload": {"data": "test"}
        });
        
        let result = validator.validate_event(&payload);
        assert!(result.is_err(), "Should fail due to missing timestamp");
    }
    
    #[test]
    fn test_event_missing_payload() {
        let validator = EventDAGValidator::new();
        let payload = json!({
            "event_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": ["QmPreviousEvent"],
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_event(&payload);
        assert!(result.is_err(), "Should fail due to missing payload");
    }
    
    #[test]
    fn test_event_invalid_cid_format() {
        let validator = EventDAGValidator::new();
        // Use a short string that will deserialize but fail CID regex validation
        let payload = json!({
            "event_cid": "Qm123",  // Too short for valid CID
            "parents": ["QmPreviousEvent"],
            "payload": {"data": "test"},
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_event(&payload).unwrap();
        assert!(!result.is_valid, "Invalid CID format should fail");
        assert!(!result.errors.is_empty());
    }
    
    #[test]
    fn test_event_multiple_parents() {
        let validator = EventDAGValidator::new();
        let payload = json!({
            "event_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": [
                "QmParent1APJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnP",
                "QmParent2APJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnP"
            ],
            "payload": {"data": "merge event"},
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_event(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_acyclicity_with_cycle() {
        let validator = EventDAGValidator::new();
        let events = vec![
            Event {
                event_cid: "event1".to_string(),
                parents: vec!["event2".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:00Z".to_string(),
            },
            Event {
                event_cid: "event2".to_string(),
                parents: vec!["event1".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:01Z".to_string(),
            },
        ];
        
        let is_acyclic = validator.check_acyclicity(&events).unwrap();
        assert!(!is_acyclic, "Should detect cycle");
    }
    
    #[test]
    fn test_acyclicity_complex_dag() {
        let validator = EventDAGValidator::new();
        let events = vec![
            Event {
                event_cid: "event1".to_string(),
                parents: vec![],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:00Z".to_string(),
            },
            Event {
                event_cid: "event2".to_string(),
                parents: vec!["event1".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:01Z".to_string(),
            },
            Event {
                event_cid: "event3".to_string(),
                parents: vec!["event1".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:02Z".to_string(),
            },
            Event {
                event_cid: "event4".to_string(),
                parents: vec!["event2".to_string(), "event3".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:03Z".to_string(),
            },
        ];
        
        assert!(validator.check_acyclicity(&events).unwrap());
    }
    
    #[test]
    fn test_acyclicity_empty_events() {
        let validator = EventDAGValidator::new();
        let events: Vec<Event> = vec![];
        
        assert!(validator.check_acyclicity(&events).unwrap());
    }
    
    #[test]
    fn test_acyclicity_single_event() {
        let validator = EventDAGValidator::new();
        let events = vec![
            Event {
                event_cid: "event1".to_string(),
                parents: vec![],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:00Z".to_string(),
            },
        ];
        
        assert!(validator.check_acyclicity(&events).unwrap());
    }
    
    #[test]
    fn test_validator_default() {
        let validator = EventDAGValidator::default();
        let payload = json!({
            "event_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            "parents": [],
            "payload": {"data": "test"},
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let result = validator.validate_event(&payload).unwrap();
        assert!(result.is_valid);
    }
    
    #[test]
    fn test_acyclicity_self_referencing_cycle() {
        // Test self-referencing cycle (event with itself in parents)
        let validator = EventDAGValidator::new();
        let events = vec![
            Event {
                event_cid: "event1".to_string(),
                parents: vec!["event1".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:00Z".to_string(),
            },
        ];
        
        let is_acyclic = validator.check_acyclicity(&events).unwrap();
        assert!(!is_acyclic, "Should detect self-referencing cycle");
    }
    
    #[test]
    fn test_acyclicity_unvisited_node_with_cycle() {
        // Test cycle starting from an unvisited node
        let validator = EventDAGValidator::new();
        let events = vec![
            Event {
                event_cid: "event1".to_string(),
                parents: vec![],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:00Z".to_string(),
            },
            Event {
                event_cid: "event2".to_string(),
                parents: vec!["event3".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:01Z".to_string(),
            },
            Event {
                event_cid: "event3".to_string(),
                parents: vec!["event2".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:02Z".to_string(),
            },
        ];
        
        let is_acyclic = validator.check_acyclicity(&events).unwrap();
        assert!(!is_acyclic, "Should detect cycle in unvisited branch");
    }
    
    #[test]
    fn test_acyclicity_indirect_cycle_three_nodes() {
        // Test indirect cycle (A → B → C → A)
        let validator = EventDAGValidator::new();
        let events = vec![
            Event {
                event_cid: "eventA".to_string(),
                parents: vec!["eventC".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:00Z".to_string(),
            },
            Event {
                event_cid: "eventB".to_string(),
                parents: vec!["eventA".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:01Z".to_string(),
            },
            Event {
                event_cid: "eventC".to_string(),
                parents: vec!["eventB".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:02Z".to_string(),
            },
        ];
        
        let is_acyclic = validator.check_acyclicity(&events).unwrap();
        assert!(!is_acyclic, "Should detect indirect cycle");
    }
    
    #[test]
    fn test_acyclicity_rec_stack_contains_parent() {
        // Test cycle with rec_stack contains parent branch
        let validator = EventDAGValidator::new();
        let events = vec![
            Event {
                event_cid: "event1".to_string(),
                parents: vec!["event3".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:00Z".to_string(),
            },
            Event {
                event_cid: "event2".to_string(),
                parents: vec!["event1".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:01Z".to_string(),
            },
            Event {
                event_cid: "event3".to_string(),
                parents: vec!["event2".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:02Z".to_string(),
            },
        ];
        
        let is_acyclic = validator.check_acyclicity(&events).unwrap();
        assert!(!is_acyclic, "Should detect cycle with recursion stack");
    }
    
    #[test]
    fn test_acyclicity_deep_recursive_cycle() {
        // Test that triggers the recursive has_cycle return true path (line 80)
        // This requires: node A not visited, recursively checking A finds a cycle
        let validator = EventDAGValidator::new();
        let events = vec![
            Event {
                event_cid: "event1".to_string(),
                parents: vec!["event2".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:00Z".to_string(),
            },
            Event {
                event_cid: "event2".to_string(),
                parents: vec!["event3".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:01Z".to_string(),
            },
            Event {
                event_cid: "event3".to_string(),
                parents: vec!["event4".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:02Z".to_string(),
            },
            Event {
                event_cid: "event4".to_string(),
                parents: vec!["event2".to_string()],  // Creates cycle: 2 -> 3 -> 4 -> 2
                payload: json!({}),
                timestamp: "2024-01-01T00:00:03Z".to_string(),
            },
        ];
        
        let is_acyclic = validator.check_acyclicity(&events).unwrap();
        assert!(!is_acyclic, "Should detect deep recursive cycle");
    }
    
    #[test]
    fn test_acyclicity_with_shared_parent() {
        // Test DAG where multiple nodes share a parent (diamond pattern)
        // This covers line 59 (already visited node), line 80 (return false path), 
        // and line 85 (finish checking parents)
        let validator = EventDAGValidator::new();
        let events = vec![
            Event {
                event_cid: "root".to_string(),
                parents: vec![],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:00Z".to_string(),
            },
            Event {
                event_cid: "left".to_string(),
                parents: vec!["root".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:01Z".to_string(),
            },
            Event {
                event_cid: "right".to_string(),
                parents: vec!["root".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:02Z".to_string(),
            },
            Event {
                event_cid: "merge".to_string(),
                parents: vec!["left".to_string(), "right".to_string()],
                payload: json!({}),
                timestamp: "2024-01-01T00:00:03Z".to_string(),
            },
        ];
        
        let is_acyclic = validator.check_acyclicity(&events).unwrap();
        assert!(is_acyclic, "Diamond DAG should be acyclic");
    }
}

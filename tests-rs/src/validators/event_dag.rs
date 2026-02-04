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
}

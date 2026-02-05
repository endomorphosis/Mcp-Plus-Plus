//! Additional tests to achieve 100% coverage

use mcp_validators::validators::base_mcp::MCPValidator;
use mcp_validators::validators::event_dag::EventDAGValidator;
use mcp_validators::models::Event;
use serde_json::json;

/// Test the is_request helper function
#[test]
fn test_is_request_helper() {
    // Valid request (has method and id, not a notification)
    let request = json!({
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 1
    });
    assert!(MCPValidator::is_request(&request));
    
    // Invalid: notification method should not be classified as request
    let notification = json!({
        "jsonrpc": "2.0",
        "method": "notifications/test",
        "id": 1
    });
    assert!(!MCPValidator::is_request(&notification));
    
    // Invalid: missing id
    let no_id = json!({
        "jsonrpc": "2.0",
        "method": "test"
    });
    assert!(!MCPValidator::is_request(&no_id));
    
    // Invalid: missing method
    let no_method = json!({
        "jsonrpc": "2.0",
        "id": 1
    });
    assert!(!MCPValidator::is_request(&no_method));
}

/// Test the is_response helper function
#[test]
fn test_is_response_helper() {
    // Valid response with result
    let response_result = json!({
        "jsonrpc": "2.0",
        "result": {"data": "test"},
        "id": 1
    });
    assert!(MCPValidator::is_response(&response_result));
    
    // Valid response with error
    let response_error = json!({
        "jsonrpc": "2.0",
        "error": {"code": -32600, "message": "Invalid Request"},
        "id": 1
    });
    assert!(MCPValidator::is_response(&response_error));
    
    // Invalid: missing id
    let no_id = json!({
        "jsonrpc": "2.0",
        "result": {"data": "test"}
    });
    assert!(!MCPValidator::is_response(&no_id));
    
    // Invalid: missing both result and error
    let no_result_error = json!({
        "jsonrpc": "2.0",
        "id": 1
    });
    assert!(!MCPValidator::is_response(&no_result_error));
}

/// Test the is_notification helper function
#[test]
fn test_is_notification_helper() {
    // Valid notification (has method, no id)
    let notification = json!({
        "jsonrpc": "2.0",
        "method": "notifications/test"
    });
    assert!(MCPValidator::is_notification(&notification));
    
    // Invalid: has id (this is a request)
    let with_id = json!({
        "jsonrpc": "2.0",
        "method": "notifications/test",
        "id": 1
    });
    assert!(!MCPValidator::is_notification(&with_id));
    
    // Invalid: missing method
    let no_method = json!({
        "jsonrpc": "2.0"
    });
    assert!(!MCPValidator::is_notification(&no_method));
}

/// Test Default trait implementation
#[test]
fn test_validator_default() {
    let validator: MCPValidator = Default::default();
    let payload = json!({
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 1
    });
    let result = validator.validate_request(&payload).unwrap();
    assert!(result.is_valid);
}

/// Test ValidationResult add_error and add_warning methods
#[test]
fn test_validation_result_methods() {
    use mcp_validators::validators::base_mcp::ValidationResult;
    
    let mut result = ValidationResult::new("test".to_string());
    assert!(result.is_valid);
    assert_eq!(result.message_type, "test");
    assert!(result.errors.is_empty());
    assert!(result.warnings.is_empty());
    
    // Add error should set is_valid to false
    result.add_error("Test error".to_string());
    assert!(!result.is_valid);
    assert_eq!(result.errors.len(), 1);
    assert_eq!(result.errors[0], "Test error");
    
    // Add warning should not affect is_valid
    result.add_warning("Test warning".to_string());
    assert!(!result.is_valid); // Still false from error
    assert_eq!(result.warnings.len(), 1);
    assert_eq!(result.warnings[0], "Test warning");
    
    // Add multiple errors and warnings
    result.add_error("Second error".to_string());
    result.add_warning("Second warning".to_string());
    assert_eq!(result.errors.len(), 2);
    assert_eq!(result.warnings.len(), 2);
}

/// Test parameter validation functions through validate_request
#[test]
fn test_initialize_params_validation() {
    let validator = MCPValidator::new();
    
    // Valid initialize request
    let payload = json!({
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1,
        "params": {
            "protocol_version": "1.0.0",
            "capabilities": {},
            "client_info": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    });
    
    let result = validator.validate_request(&payload).unwrap();
    assert!(result.is_valid);
}

/// Test tool call params validation
#[test]
fn test_tool_call_params_validation() {
    let validator = MCPValidator::new();
    
    // Valid tool call request
    let payload = json!({
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": 1,
        "params": {
            "name": "test_tool",
            "arguments": {
                "param1": "value1"
            }
        }
    });
    
    let result = validator.validate_request(&payload).unwrap();
    assert!(result.is_valid);
}

/// Test resource read params validation
#[test]
fn test_resource_read_params_validation() {
    let validator = MCPValidator::new();
    
    // Valid resource read request
    let payload = json!({
        "jsonrpc": "2.0",
        "method": "resources/read",
        "id": 1,
        "params": {
            "uri": "file:///test.txt"
        }
    });
    
    let result = validator.validate_request(&payload).unwrap();
    assert!(result.is_valid);
}

/// Test prompt get params validation
#[test]
fn test_prompt_get_params_validation() {
    let validator = MCPValidator::new();
    
    // Valid prompt get request
    let payload = json!({
        "jsonrpc": "2.0",
        "method": "prompts/get",
        "id": 1,
        "params": {
            "name": "test_prompt",
            "arguments": {}
        }
    });
    
    let result = validator.validate_request(&payload).unwrap();
    assert!(result.is_valid);
}

/// Test event DAG cycle detection - no cycle case (line 59)
#[test]
fn test_event_dag_no_cycle_already_visited() {
    let validator = EventDAGValidator::new();
    
    // Create events where some nodes are already visited in the DFS
    // This tests the branch at line 59: if !visited.contains(&event.event_cid)
    let events = vec![
        Event {
            event_cid: "event1".to_string(),
            parents: vec!["event2".to_string()],
            payload: json!({"data": "event1"}),
            timestamp: "2024-01-01T00:00:00Z".to_string(),
        },
        Event {
            event_cid: "event2".to_string(),
            parents: vec![],
            payload: json!({"data": "event2"}),
            timestamp: "2024-01-01T00:00:01Z".to_string(),
        },
        Event {
            event_cid: "event3".to_string(),
            parents: vec!["event2".to_string()], // Also points to event2
            payload: json!({"data": "event3"}),
            timestamp: "2024-01-01T00:00:02Z".to_string(),
        },
    ];
    
    let result = validator.check_acyclicity(&events).unwrap();
    assert!(result, "Should not detect a cycle in acyclic DAG");
}

/// Test event DAG cycle detection - has cycle (lines 80, 82)
#[test]
fn test_event_dag_cycle_detection() {
    let validator = EventDAGValidator::new();
    
    // Create a cycle: event1 -> event2 -> event3 -> event1
    let events = vec![
        Event {
            event_cid: "event1".to_string(),
            parents: vec!["event3".to_string()], // Creates cycle
            payload: json!({"data": "event1"}),
            timestamp: "2024-01-01T00:00:00Z".to_string(),
        },
        Event {
            event_cid: "event2".to_string(),
            parents: vec!["event1".to_string()],
            payload: json!({"data": "event2"}),
            timestamp: "2024-01-01T00:00:01Z".to_string(),
        },
        Event {
            event_cid: "event3".to_string(),
            parents: vec!["event2".to_string()],
            payload: json!({"data": "event3"}),
            timestamp: "2024-01-01T00:00:02Z".to_string(),
        },
    ];
    
    let result = validator.check_acyclicity(&events).unwrap();
    assert!(!result, "Should detect cycle in DAG");
}

/// Test event DAG with parent not in visited and in rec_stack (line 80, 82)
#[test]
fn test_event_dag_parent_in_rec_stack() {
    let validator = EventDAGValidator::new();
    
    // Create a self-loop cycle
    let events = vec![
        Event {
            event_cid: "event1".to_string(),
            parents: vec!["event2".to_string()],
            payload: json!({"data": "event1"}),
            timestamp: "2024-01-01T00:00:00Z".to_string(),
        },
        Event {
            event_cid: "event2".to_string(),
            parents: vec!["event1".to_string()], // Cycle
            payload: json!({"data": "event2"}),
            timestamp: "2024-01-01T00:00:01Z".to_string(),
        },
    ];
    
    let result = validator.check_acyclicity(&events).unwrap();
    assert!(!result, "Should detect cycle when parent is in recursion stack");
}

/// Test event DAG with node having no parents (line 85)
#[test]
fn test_event_dag_node_no_parents() {
    let validator = EventDAGValidator::new();
    
    // Genesis events with no parents
    let events = vec![
        Event {
            event_cid: "genesis1".to_string(),
            parents: vec![],
            payload: json!({"data": "genesis1"}),
            timestamp: "2024-01-01T00:00:00Z".to_string(),
        },
        Event {
            event_cid: "genesis2".to_string(),
            parents: vec![],
            payload: json!({"data": "genesis2"}),
            timestamp: "2024-01-01T00:00:01Z".to_string(),
        },
        Event {
            event_cid: "child".to_string(),
            parents: vec!["genesis1".to_string(), "genesis2".to_string()],
            payload: json!({"data": "child"}),
            timestamp: "2024-01-01T00:00:02Z".to_string(),
        },
    ];
    
    let result = validator.check_acyclicity(&events).unwrap();
    assert!(result, "Should handle events with no parents correctly");
}

/// Test event DAG with reference to non-existent parent (line 85 - else branch)
#[test]
fn test_event_dag_missing_parent_reference() {
    let validator = EventDAGValidator::new();
    
    // Event references a parent that's not in the graph
    let events = vec![
        Event {
            event_cid: "event1".to_string(),
            parents: vec!["nonexistent_parent".to_string()],
            payload: json!({"data": "event1"}),
            timestamp: "2024-01-01T00:00:00Z".to_string(),
        },
    ];
    
    // Should not crash, just skip the missing parent
    let result = validator.check_acyclicity(&events).unwrap();
    assert!(result, "Should handle missing parent references gracefully");
}

/// Test invalid initialize params to trigger validation error mapping (line 223)
#[test]
fn test_initialize_params_validation_error() {
    let validator = MCPValidator::new();
    
    // Invalid protocol version format - should fail validation
    let payload = json!({
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1,
        "params": {
            "protocol_version": "invalid-version",
            "capabilities": {},
            "client_info": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    });
    
    let result = validator.validate_request(&payload).unwrap();
    assert!(!result.is_valid, "Should fail validation for invalid protocol version");
    assert!(!result.errors.is_empty());
}

/// Test invalid tool call params to trigger validation error mapping (line 232)
#[test]
fn test_tool_call_params_validation_error() {
    let validator = MCPValidator::new();
    
    // Empty name field - should fail min_length validation
    let payload = json!({
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": 1,
        "params": {
            "name": "",
            "arguments": {}
        }
    });
    
    let result = validator.validate_request(&payload).unwrap();
    assert!(!result.is_valid, "Should fail validation for empty tool name");
    assert!(!result.errors.is_empty());
}

/// Test invalid resource read params to trigger validation error mapping (line 241)
#[test]
fn test_resource_read_params_validation_error() {
    let validator = MCPValidator::new();
    
    // Empty uri field - should fail min_length validation
    let payload = json!({
        "jsonrpc": "2.0",
        "method": "resources/read",
        "id": 1,
        "params": {
            "uri": ""
        }
    });
    
    let result = validator.validate_request(&payload).unwrap();
    assert!(!result.is_valid, "Should fail validation for empty URI");
    assert!(!result.errors.is_empty());
}

/// Test invalid prompt get params to trigger validation error mapping (line 250)
#[test]
fn test_prompt_get_params_validation_error() {
    let validator = MCPValidator::new();
    
    // Empty name field - should fail min_length validation
    let payload = json!({
        "jsonrpc": "2.0",
        "method": "prompts/get",
        "id": 1,
        "params": {
            "name": "",
            "arguments": {}
        }
    });
    
    let result = validator.validate_request(&payload).unwrap();
    assert!(!result.is_valid, "Should fail validation for empty prompt name");
    assert!(!result.errors.is_empty());
}

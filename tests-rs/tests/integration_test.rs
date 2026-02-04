//! Comprehensive integration tests for all validators

use mcp_validators::validators::*;
use serde_json::json;

#[test]
fn test_base_mcp_valid_request() {
    let validator = MCPValidator::new();
    let payload = json!({
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 1
    });
    
    let result = validator.validate_request(&payload).unwrap();
    assert!(result.is_valid, "Request should be valid");
    assert_eq!(result.message_type, "request");
}

#[test]
fn test_base_mcp_valid_response() {
    let validator = MCPValidator::new();
    let payload = json!({
        "jsonrpc": "2.0",
        "result": {"tools": []},
        "id": 1
    });
    
    let result = validator.validate_response(&payload).unwrap();
    assert!(result.is_valid, "Response should be valid");
}

#[test]
fn test_base_mcp_valid_notification() {
    let validator = MCPValidator::new();
    let payload = json!({
        "jsonrpc": "2.0",
        "method": "notifications/test"
    });
    
    let result = validator.validate_notification(&payload).unwrap();
    assert!(result.is_valid, "Notification should be valid");
}

#[test]
fn test_mcp_idl_valid_descriptor() {
    let validator = MCPIDLValidator::new();
    let payload = json!({
        "name": "weather-api",
        "version": "1.0.0",
        "tools": [{
            "name": "get_weather",
            "description": "Get weather data",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                }
            }
        }],
        "interface_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
    });
    
    let result = validator.validate_interface_descriptor(&payload).unwrap();
    assert!(result.is_valid, "Interface descriptor should be valid");
}

#[test]
fn test_cid_artifacts_valid_envelope() {
    let validator = CIDArtifactsValidator::new();
    let payload = json!({
        "interface_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
        "input_cid": "QmZwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
        "parents": ["QmPreviousEvent123456789012345678901234567890"],
        "timestamp": "2024-01-01T00:00:00Z"
    });
    
    let result = validator.validate_envelope(&payload).unwrap();
    assert!(result.is_valid, "Envelope should be valid");
}

#[test]
fn test_cid_artifacts_valid_receipt() {
    let validator = CIDArtifactsValidator::new();
    let payload = json!({
        "envelope_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
        "output_cid": "QmZwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
        "signature": "0x1234567890abcdef1234567890abcdef1234567890abcdef",
        "receipt_cid": "QmXwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
    });
    
    let result = validator.validate_receipt(&payload).unwrap();
    assert!(result.is_valid, "Receipt should be valid");
}

#[test]
fn test_ucan_valid_token() {
    let validator = UCANDelegationValidator::new();
    let payload = json!({
        "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
        "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
        "att": [{
            "resource": "mcp://tools/*",
            "ability": "execute"
        }],
        "exp": 1735689600
    });
    
    let result = validator.validate_ucan_token(&payload).unwrap();
    assert!(result.is_valid, "UCAN token should be valid");
}

#[test]
fn test_ucan_valid_delegation_chain() {
    let validator = UCANDelegationValidator::new();
    let payload = json!({
        "chain": [{
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        }]
    });
    
    let result = validator.validate_delegation_chain(&payload).unwrap();
    assert!(result.is_valid, "Delegation chain should be valid");
}

#[test]
fn test_policy_valid_definition() {
    let validator = PolicyEvaluationValidator::new();
    let payload = json!({
        "policy_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
        "policy_type": "permission",
        "temporal": {
            "not_before": "2024-01-01T00:00:00Z",
            "not_after": "2024-12-31T23:59:59Z"
        },
        "rules": [{
            "condition": "time_before('2024-12-31')",
            "action": "allow"
        }]
    });
    
    let result = validator.validate_policy(&payload).unwrap();
    assert!(result.is_valid, "Policy should be valid");
}

#[test]
fn test_policy_valid_decision() {
    let validator = PolicyEvaluationValidator::new();
    let payload = json!({
        "decision": "allow",
        "decision_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
    });
    
    let result = validator.validate_decision(&payload).unwrap();
    assert!(result.is_valid, "Decision should be valid");
}

#[test]
fn test_policy_decision_with_obligations() {
    let validator = PolicyEvaluationValidator::new();
    let payload = json!({
        "decision": "allow_with_obligations",
        "obligations": [{
            "description": "Log this action within 24 hours",
            "deadline": "2024-12-31T23:59:59Z"
        }]
    });
    
    let result = validator.validate_decision(&payload).unwrap();
    assert!(result.is_valid, "Decision with obligations should be valid");
}

#[test]
fn test_transport_valid_message() {
    let validator = TransportValidator::new();
    let payload = json!({
        "protocol_id": "/mcp+p2p/1.0.0",
        "length": 256,
        "payload": {
            "jsonrpc": "2.0",
            "method": "test",
            "id": 1
        }
    });
    
    let result = validator.validate_transport_message(&payload).unwrap();
    assert!(result.is_valid, "Transport message should be valid");
}

#[test]
fn test_transport_valid_session() {
    let validator = TransportValidator::new();
    let payload = json!({
        "session_id": "session-abc123",
        "peer_addr": "/ip4/127.0.0.1/tcp/8080/p2p/QmYwAPJz"
    });
    
    let result = validator.validate_session(&payload).unwrap();
    assert!(result.is_valid, "Session should be valid");
}

#[test]
fn test_event_dag_valid_event() {
    let validator = EventDAGValidator::new();
    let payload = json!({
        "event_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
        "parents": ["QmZwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"],
        "payload": {"data": "test event"},
        "timestamp": "2024-01-01T00:00:00Z"
    });
    
    let result = validator.validate_event(&payload).unwrap();
    assert!(result.is_valid, "Event should be valid");
}

#[test]
fn test_event_dag_genesis_event() {
    let validator = EventDAGValidator::new();
    let payload = json!({
        "event_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
        "parents": [],
        "payload": {"data": "genesis event"},
        "timestamp": "2024-01-01T00:00:00Z"
    });
    
    let result = validator.validate_event(&payload).unwrap();
    assert!(result.is_valid, "Genesis event should be valid");
    assert!(!result.warnings.is_empty(), "Should have warning about genesis");
}

// Negative tests

#[test]
fn test_base_mcp_invalid_jsonrpc() {
    let validator = MCPValidator::new();
    let payload = json!({
        "jsonrpc": "1.0",
        "method": "tools/list",
        "id": 1
    });
    
    // Validation catches incorrect version in the result
    let result = validator.validate_request(&payload).unwrap();
    assert!(!result.is_valid, "Should be invalid due to wrong JSON-RPC version");
}

#[test]
fn test_base_mcp_response_missing_result_and_error() {
    let validator = MCPValidator::new();
    let payload = json!({
        "jsonrpc": "2.0",
        "id": 1
    });
    
    let result = validator.validate_response(&payload).unwrap();
    assert!(!result.is_valid, "Response without result or error should be invalid");
}

#[test]
fn test_cid_format_validation() {
    let validator = MCPIDLValidator::new();
    
    // Valid CIDs
    assert!(validator.validate_cid_format("QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"));
    assert!(validator.validate_cid_format("bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"));
    
    // Invalid CIDs
    assert!(!validator.validate_cid_format("invalid-cid"));
    assert!(!validator.validate_cid_format("Qm123")); // Too short
    assert!(!validator.validate_cid_format(""));
}

#[test]
fn test_type_guards() {
    // Test request detection
    let request = json!({"method": "test", "id": 1});
    assert!(MCPValidator::is_request(&request));
    
    // Test response detection
    let response = json!({"result": {}, "id": 1});
    assert!(MCPValidator::is_response(&response));
    
    // Test notification detection
    let notification = json!({"method": "test"});
    assert!(MCPValidator::is_notification(&notification));
}

//! Cross-language conformance: validate shared vectors against canonical models.
//! Same conformance/vectors/*.json as py/ts/go so the four mirrors can't drift.

use mcp_validators::models::{
    AuditEntry, BusMessage, Delegation, DAGEvent, ExecutionReceipt, InitializeResult,
    P2PMessage, PolicyDecision, SessionError, WasmProofResult, ZKProofArtifact,
};
use serde_valid::Validate;
use std::fs;
use std::path::PathBuf;

fn vectors_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../conformance/vectors")
}

#[test]
fn test_conformance_vectors() {
    let dir = vectors_dir();
    let mut n = 0;
    for entry in fs::read_dir(&dir).expect("vectors dir") {
        let path = entry.unwrap().path();
        if path.extension().and_then(|s| s.to_str()) != Some("json") {
            continue;
        }
        let raw = fs::read_to_string(&path).unwrap();
        let v: serde_json::Value = serde_json::from_str(&raw).unwrap();
        let model_value = v.get("model");
        let payload_value = v.get("payload");
        if model_value.is_none() && payload_value.is_none() {
            // Profile-specific suites have dedicated codecs and omit the
            // canonical {model, payload} envelope.
            continue;
        }
        let model = model_value
            .and_then(serde_json::Value::as_str)
            .expect("canonical vector model");
        let p = payload_value.expect("canonical vector payload").clone();
        match model {
            "InitializeResult" => {
                serde_json::from_value::<InitializeResult>(p).unwrap().validate().unwrap();
            }
            "PolicyDecision" => {
                serde_json::from_value::<PolicyDecision>(p).unwrap().validate().unwrap();
            }
            "P2PMessage" => {
                serde_json::from_value::<P2PMessage>(p).unwrap().validate().unwrap();
            }
            "Delegation" => {
                serde_json::from_value::<Delegation>(p).unwrap().validate().unwrap();
            }
            "DAGEvent" => {
                serde_json::from_value::<DAGEvent>(p).unwrap().validate().unwrap();
            }
            "ExecutionReceipt" => {
                serde_json::from_value::<ExecutionReceipt>(p).unwrap().validate().unwrap();
            }
            "SessionError" => {
                serde_json::from_value::<SessionError>(p).unwrap().validate().unwrap();
            }
            "BusMessage" => {
                serde_json::from_value::<BusMessage>(p).unwrap().validate().unwrap();
            }
            "AuditEntry" => {
                serde_json::from_value::<AuditEntry>(p).unwrap().validate().unwrap();
            }
            "WasmProofResult" => {
                serde_json::from_value::<WasmProofResult>(p).unwrap().validate().unwrap();
            }
            "ZKProofArtifact" => {
                serde_json::from_value::<ZKProofArtifact>(p).unwrap().validate().unwrap();
            }
            other => panic!("unknown model {} in {:?}", other, path),
        }
        n += 1;
    }
    assert!(n >= 11, "expected vectors, got {}", n);
}

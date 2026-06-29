//! Cross-language conformance: validate shared vectors against canonical models.
//! Same conformance/vectors/*.json as py/ts/go so the four mirrors can't drift.

use mcp_validators::models::{
    Delegation, DAGEvent, ExecutionReceipt, InitializeResult, P2PMessage, PolicyDecision,
};
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
        let model = v["model"].as_str().unwrap();
        let p = v["payload"].clone();
        match model {
            "InitializeResult" => { serde_json::from_value::<InitializeResult>(p).unwrap(); }
            "PolicyDecision" => { serde_json::from_value::<PolicyDecision>(p).unwrap(); }
            "P2PMessage" => { serde_json::from_value::<P2PMessage>(p).unwrap(); }
            "Delegation" => { serde_json::from_value::<Delegation>(p).unwrap(); }
            "DAGEvent" => { serde_json::from_value::<DAGEvent>(p).unwrap(); }
            "ExecutionReceipt" => { serde_json::from_value::<ExecutionReceipt>(p).unwrap(); }
            other => panic!("unknown model {} in {:?}", other, path),
        }
        n += 1;
    }
    assert!(n >= 6, "expected vectors, got {}", n);
}

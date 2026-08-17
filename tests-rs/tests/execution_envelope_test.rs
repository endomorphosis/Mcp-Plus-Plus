//! MCPP-033: four-language ExecutionEnvelope@1 family validators and vectors.
//!
//! Interface: ExecutionEnvelopeValidator@1
//! Track: envelope-validators
//!
//! Mirrors the positive/negative catalog in:
//!   - tests-py/integration/test_execution_envelope.py
//!   - tests-ts/src/__tests__/execution-envelope.test.ts
//!   - tests-go/execution_envelope_test.go
//!
//! Structural acceptance only (ADR-0003). Same case ids must accept/reject
//! identically across languages.

use lazy_static::lazy_static;
use regex::Regex;
use serde_json::{json, Map, Value};
use std::collections::HashSet;

const INTERFACE: &str = "ExecutionEnvelopeValidator@1";
const TASK_ID: &str = "MCPP-033";

const SCHEMA_ENVELOPE: &str = "mcp++/execution/envelope@1";
const SCHEMA_RESULT: &str = "mcp++/execution/result@1";
const SCHEMA_RECEIPT: &str = "mcp++/execution/receipt@1";
const SCHEMA_ERROR: &str = "mcp++/execution/portable-error@1";

const CID_A: &str = "bafkreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi";
const CID_B: &str = "bafkreihtwdlu4jntm7yl2mgsfzqgr4on37vr7inuld2dql2p4rmqafybti";
const CID_C: &str = "bafkreicssskybdf32rmzlbtge5bxyv4v6c6eac322pbrsr3azlb4fkxiqi";
const CID_D: &str = "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku";

const DID_REQUESTER: &str = "did:key:z6MkrequesterExample0001";
const DID_EXECUTOR: &str = "did:key:z6MkexecutorExample00001";

lazy_static! {
    static ref CID_RE: Regex =
        Regex::new(r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58,})$").unwrap();
    static ref DID_RE: Regex =
        Regex::new(r"^did:[a-z0-9]+:[A-Za-z0-9._:%-]+(?:[/?#][^\x00]*)?$").unwrap();
}

const STATUS_VALUES: &[&str] = &[
    "succeeded",
    "failed",
    "cancelled",
    "rejected",
    "timed_out",
    "compensated",
];

const FAILURE_CLASSES: &[&str] = &[
    "none",
    "retryable",
    "permanent",
    "policy",
    "authority",
    "fenced",
    "resource",
    "cancelled",
    "timeout",
    "internal",
];

#[derive(Debug, Clone)]
struct ValidationResult {
    is_valid: bool,
    errors: Vec<String>,
}

impl ValidationResult {
    fn ok() -> Self {
        Self {
            is_valid: true,
            errors: Vec::new(),
        }
    }

    fn add(&mut self, msg: impl Into<String>) {
        self.is_valid = false;
        self.errors.push(msg.into());
    }
}

fn is_valid_cid(v: &Value) -> bool {
    v.as_str().map(|s| CID_RE.is_match(s)).unwrap_or(false)
}

fn is_valid_did(v: &Value) -> bool {
    v.as_str().map(|s| DID_RE.is_match(s)).unwrap_or(false)
}

fn is_non_neg_int(v: &Value) -> bool {
    match v {
        Value::Number(n) => n
            .as_i64()
            .map(|i| i >= 0)
            .or_else(|| n.as_u64().map(|_| true))
            .unwrap_or(false),
        _ => false,
    }
}

fn as_object(v: &Value) -> Option<&Map<String, Value>> {
    v.as_object()
}

// ---------------------------------------------------------------------------
// ExecutionEnvelopeValidator@1 (structural)
// ---------------------------------------------------------------------------

fn validate_portable_error(error: &Value) -> ValidationResult {
    let mut r = ValidationResult::ok();
    let Some(m) = as_object(error) else {
        r.add("error must be an object");
        return r;
    };
    if m.get("schema").and_then(|s| s.as_str()) != Some(SCHEMA_ERROR) {
        r.add(format!("schema must be {SCHEMA_ERROR}"));
    }
    for key in ["code", "message", "retryable", "failure_class"] {
        if !m.contains_key(key) {
            r.add(format!("missing required field: {key}"));
        }
    }
    if let Some(fc) = m.get("failure_class") {
        let s = fc.as_str().unwrap_or("");
        if !FAILURE_CLASSES.contains(&s) {
            r.add(format!("invalid failure_class: {s}"));
        }
    }
    if let Some(rb) = m.get("retryable") {
        if !rb.is_boolean() {
            r.add("retryable must be a boolean");
        }
    }
    if let Some(dc) = m.get("details_cid") {
        if !dc.is_null() && !is_valid_cid(dc) {
            r.add("invalid CID at /details_cid");
        }
    }
    r
}

fn validate_envelope(envelope: &Value) -> ValidationResult {
    let mut r = ValidationResult::ok();
    let Some(m) = as_object(envelope) else {
        r.add("envelope must be an object");
        return r;
    };
    if m.get("schema").and_then(|s| s.as_str()) != Some(SCHEMA_ENVELOPE) {
        r.add(format!("schema must be {SCHEMA_ENVELOPE}"));
    }
    for key in [
        "schema",
        "interface_cid",
        "input_cid",
        "intent_cid",
        "parents",
        "created_at_ms",
        "correlation_id",
        "requester",
        "authority",
    ] {
        if !m.contains_key(key) {
            r.add(format!("missing required field: {key}"));
        }
    }
    for key in [
        "interface_cid",
        "input_cid",
        "intent_cid",
        "policy_cid",
        "decision_cid",
        "constraints_cid",
        "expected_output_schema_cid",
        "metadata_cid",
        "profile_b_envelope_cid",
    ] {
        if let Some(v) = m.get(key) {
            if !v.is_null() && !is_valid_cid(v) {
                r.add(format!("invalid CID at /{key}"));
            }
        }
    }
    if let Some(parents) = m.get("parents") {
        match parents.as_array() {
            None => r.add("parents must be an array"),
            Some(arr) => {
                for (i, p) in arr.iter().enumerate() {
                    if !is_valid_cid(p) {
                        r.add(format!("invalid parent CID at /parents/{i}"));
                    }
                }
            }
        }
    }
    if let Some(ts) = m.get("created_at_ms") {
        if !is_non_neg_int(ts) {
            r.add("created_at_ms must be a non-negative integer");
        }
    }
    if let Some(corr) = m.get("correlation_id") {
        let ok = corr
            .as_str()
            .map(|s| (1..=128).contains(&s.len()))
            .unwrap_or(false);
        if !ok {
            r.add("correlation_id must be a string of length 1..128");
        }
    }
    if let Some(req) = m.get("requester") {
        let did_ok = req
            .as_object()
            .and_then(|o| o.get("did"))
            .map(is_valid_did)
            .unwrap_or(false);
        if !did_ok {
            r.add("requester.did must be a valid DID");
        }
    }
    if let Some(auth) = m.get("authority") {
        match auth.as_object() {
            None => r.add("authority must be an object"),
            Some(a) => {
                if !a.contains_key("proof_cids") {
                    r.add("authority.proof_cids is required");
                } else if let Some(pcs) = a.get("proof_cids") {
                    match pcs.as_array() {
                        None => r.add("authority.proof_cids must be an array"),
                        Some(arr) => {
                            for (i, cid) in arr.iter().enumerate() {
                                if !is_valid_cid(cid) {
                                    r.add(format!("invalid CID at /authority/proof_cids/{i}"));
                                }
                            }
                        }
                    }
                }
                if let Some(pc) = a.get("proof_cid") {
                    if !pc.is_null() && !is_valid_cid(pc) {
                        r.add("invalid CID at /authority/proof_cid");
                    }
                }
            }
        }
    }
    if let Some(c) = m.get("canonicalization") {
        if !c.is_null() && c.as_str() != Some("mcpp-jcs-v1") {
            r.add("canonicalization must be 'mcpp-jcs-v1' when present");
        }
    }
    r
}

fn validate_result(result_obj: &Value) -> ValidationResult {
    let mut r = ValidationResult::ok();
    let Some(m) = as_object(result_obj) else {
        r.add("result must be an object");
        return r;
    };
    if m.get("schema").and_then(|s| s.as_str()) != Some(SCHEMA_RESULT) {
        r.add(format!("schema must be {SCHEMA_RESULT}"));
    }
    for key in [
        "schema",
        "envelope_cid",
        "status",
        "output_cids",
        "state_transitions",
        "side_effects",
        "decision_cid",
        "delegation_cid",
        "executor",
        "retry",
        "duration_ms",
        "error",
        "proofs",
        "started_at_ms",
        "finished_at_ms",
    ] {
        if !m.contains_key(key) {
            r.add(format!("missing required field: {key}"));
        }
    }
    if let Some(st) = m.get("status") {
        let s = st.as_str().unwrap_or("");
        if !STATUS_VALUES.contains(&s) {
            r.add(format!("invalid status: {s}"));
        }
    }
    if m.get("status").and_then(|s| s.as_str()) == Some("succeeded")
        && m.get("error").map(|e| !e.is_null()).unwrap_or(false)
    {
        r.add("error must be null when status is succeeded");
    }
    if let Some(v) = m.get("envelope_cid") {
        if !v.is_null() && !is_valid_cid(v) {
            r.add("invalid CID at /envelope_cid");
        }
    }
    if let Some(outs) = m.get("output_cids") {
        match outs.as_array() {
            None => r.add("output_cids must be an array"),
            Some(arr) => {
                for (i, cid) in arr.iter().enumerate() {
                    if !is_valid_cid(cid) {
                        r.add(format!("invalid CID at /output_cids/{i}"));
                    }
                }
            }
        }
    }
    if let Some(ex) = m.get("executor") {
        let did_ok = ex
            .as_object()
            .and_then(|o| o.get("did"))
            .map(is_valid_did)
            .unwrap_or(false);
        if !did_ok {
            r.add("executor.did must be a valid DID");
        }
    }
    if let Some(err) = m.get("error") {
        if !err.is_null() {
            let pe = validate_portable_error(err);
            if !pe.is_valid {
                r.errors.extend(pe.errors);
                r.is_valid = false;
            }
        }
    }
    if let Some(ts) = m.get("started_at_ms") {
        if !is_non_neg_int(ts) {
            r.add("started_at_ms must be a non-negative integer");
        }
    }
    if let Some(ts) = m.get("finished_at_ms") {
        if !is_non_neg_int(ts) {
            r.add("finished_at_ms must be a non-negative integer");
        }
    }
    if let (Some(start), Some(finish)) = (m.get("started_at_ms"), m.get("finished_at_ms")) {
        if is_non_neg_int(start) && is_non_neg_int(finish) {
            let s = start.as_i64().or_else(|| start.as_u64().map(|u| u as i64)).unwrap_or(0);
            let f = finish.as_i64().or_else(|| finish.as_u64().map(|u| u as i64)).unwrap_or(0);
            if f < s {
                r.add("finished_at_ms must be >= started_at_ms");
            }
        }
    }
    r
}

fn validate_receipt(receipt: &Value) -> ValidationResult {
    let mut r = ValidationResult::ok();
    let Some(m) = as_object(receipt) else {
        r.add("receipt must be an object");
        return r;
    };
    if m.get("schema").and_then(|s| s.as_str()) != Some(SCHEMA_RECEIPT) {
        r.add(format!("schema must be {SCHEMA_RECEIPT}"));
    }
    for key in [
        "schema",
        "envelope_cid",
        "result_cid",
        "status",
        "output_cids",
        "state_transitions",
        "side_effects",
        "decision_cid",
        "delegation_cid",
        "executor",
        "retry",
        "duration_ms",
        "error",
        "proofs",
        "signature",
        "event_cid",
        "started_at_ms",
        "finished_at_ms",
    ] {
        if !m.contains_key(key) {
            r.add(format!("missing required field: {key}"));
        }
    }
    for key in [
        "envelope_cid",
        "result_cid",
        "intent_cid",
        "receipt_cid",
        "decision_cid",
        "delegation_cid",
        "proof_cid",
        "event_cid",
        "primary_output_cid",
        "resource_use_cid",
        "policy_cid",
        "profile_b_receipt_cid",
        "profile_g_task_receipt_cid",
    ] {
        if let Some(v) = m.get(key) {
            if !v.is_null() && !is_valid_cid(v) {
                r.add(format!("invalid CID at /{key}"));
            }
        }
    }
    if let Some(outs) = m.get("output_cids") {
        match outs.as_array() {
            None => r.add("output_cids must be an array"),
            Some(arr) => {
                for (i, cid) in arr.iter().enumerate() {
                    if !is_valid_cid(cid) {
                        r.add(format!("invalid CID at /output_cids/{i}"));
                    }
                }
            }
        }
    }
    if let Some(st) = m.get("status") {
        let s = st.as_str().unwrap_or("");
        if !STATUS_VALUES.contains(&s) {
            r.add(format!("invalid status: {s}"));
        }
    }
    if m.get("status").and_then(|s| s.as_str()) == Some("succeeded")
        && m.get("error").map(|e| !e.is_null()).unwrap_or(false)
    {
        r.add("error must be null when status is succeeded");
    }
    if let Some(ex) = m.get("executor") {
        let did_ok = ex
            .as_object()
            .and_then(|o| o.get("did"))
            .map(is_valid_did)
            .unwrap_or(false);
        if !did_ok {
            r.add("executor.did must be a valid DID");
        }
    }
    if let Some(retry) = m.get("retry") {
        let attempt_ok = retry
            .as_object()
            .and_then(|o| o.get("attempt"))
            .map(|a| is_non_neg_int(a) && a.as_i64().or_else(|| a.as_u64().map(|u| u as i64)).unwrap_or(0) >= 1)
            .unwrap_or(false);
        if !attempt_ok {
            r.add("retry.attempt must be an integer >= 1");
        }
    }
    if let Some(err) = m.get("error") {
        if !err.is_null() {
            let pe = validate_portable_error(err);
            if !pe.is_valid {
                r.errors.extend(pe.errors);
                r.is_valid = false;
            }
        }
    }
    for ts in ["started_at_ms", "finished_at_ms"] {
        if let Some(v) = m.get(ts) {
            if !is_non_neg_int(v) {
                r.add(format!("{ts} must be a non-negative integer"));
            }
        }
    }
    if let (Some(start), Some(finish)) = (m.get("started_at_ms"), m.get("finished_at_ms")) {
        if is_non_neg_int(start) && is_non_neg_int(finish) {
            let s = start.as_i64().or_else(|| start.as_u64().map(|u| u as i64)).unwrap_or(0);
            let f = finish.as_i64().or_else(|| finish.as_u64().map(|u| u as i64)).unwrap_or(0);
            if f < s {
                r.add("finished_at_ms must be >= started_at_ms");
            }
        }
    }
    if let Some(c) = m.get("canonicalization") {
        if !c.is_null() && c.as_str() != Some("mcpp-jcs-v1") {
            r.add("canonicalization must be 'mcpp-jcs-v1' when present");
        }
    }
    r
}

/// ExecutionEnvelopeValidator@1 dispatch.
fn validate_kind(kind: &str, payload: &Value) -> bool {
    match kind {
        "envelope" => validate_envelope(payload).is_valid,
        "result" => validate_result(payload).is_valid,
        "receipt" => validate_receipt(payload).is_valid,
        "error" => validate_portable_error(payload).is_valid,
        other => panic!("unknown kind: {other}"),
    }
}

// ---------------------------------------------------------------------------
// Fixtures / catalog (ids MUST match py/ts/go)
// ---------------------------------------------------------------------------

fn base_envelope() -> Value {
    json!({
        "schema": SCHEMA_ENVELOPE,
        "interface_cid": CID_A,
        "method": "repo.status",
        "input_cid": CID_B,
        "intent_cid": CID_C,
        "policy_cid": CID_D,
        "parents": [],
        "created_at_ms": 1783872000000_i64,
        "correlation_id": "task-001",
        "requester": { "did": DID_REQUESTER },
        "authority": {
            "proof_cids": [CID_D],
            "proof_cid": CID_D
        },
        "constraints": { "timeout_ms": 30000, "max_retries": 3 },
        "state_refs": [],
        "canonicalization": "mcpp-jcs-v1"
    })
}

fn base_portable_error() -> Value {
    json!({
        "schema": SCHEMA_ERROR,
        "code": "E_POLICY_DENIED",
        "message": "policy denied execution",
        "retryable": false,
        "failure_class": "policy"
    })
}

fn base_result_succeeded() -> Value {
    json!({
        "schema": SCHEMA_RESULT,
        "envelope_cid": CID_A,
        "status": "succeeded",
        "output_cids": [CID_B],
        "state_transitions": [],
        "side_effects": [],
        "decision_cid": CID_D,
        "delegation_cid": CID_C,
        "executor": { "did": DID_EXECUTOR },
        "retry": { "attempt": 1 },
        "duration_ms": 12.5,
        "error": null,
        "proofs": [CID_D],
        "started_at_ms": 1783872001100_i64,
        "finished_at_ms": 1783872001113_i64,
        "canonicalization": "mcpp-jcs-v1"
    })
}

fn base_result_failed() -> Value {
    let mut obj = base_result_succeeded();
    let m = obj.as_object_mut().unwrap();
    m.insert("status".into(), json!("failed"));
    m.insert("output_cids".into(), json!([]));
    m.insert("error".into(), base_portable_error());
    obj
}

fn base_receipt_succeeded() -> Value {
    json!({
        "schema": SCHEMA_RECEIPT,
        "envelope_cid": CID_A,
        "result_cid": CID_B,
        "status": "succeeded",
        "output_cids": [CID_C],
        "state_transitions": [],
        "side_effects": [],
        "decision_cid": CID_D,
        "delegation_cid": CID_C,
        "executor": {
            "did": DID_EXECUTOR,
            "runtime": "ipfs_accelerate_py",
            "runtime_version": "3.2.0"
        },
        "retry": { "attempt": 1 },
        "duration_ms": 12.5,
        "error": null,
        "proofs": [CID_D],
        "signature": null,
        "signature_alg": null,
        "event_cid": CID_A,
        "started_at_ms": 1783872001100_i64,
        "finished_at_ms": 1783872001113_i64,
        "canonicalization": "mcpp-jcs-v1"
    })
}

fn base_receipt_failed() -> Value {
    let mut obj = base_receipt_succeeded();
    let m = obj.as_object_mut().unwrap();
    m.insert("status".into(), json!("failed"));
    m.insert("output_cids".into(), json!([]));
    m.insert("error".into(), base_portable_error());
    obj
}

struct VectorCase {
    id: &'static str,
    kind: &'static str,
    payload: Value,
    expect_valid: bool,
}

fn vector_catalog() -> Vec<VectorCase> {
    let mut cases = vec![
        VectorCase {
            id: "pos-envelope-minimal",
            kind: "envelope",
            payload: base_envelope(),
            expect_valid: true,
        },
        VectorCase {
            id: "pos-envelope-with-parents",
            kind: "envelope",
            payload: {
                let mut p = base_envelope();
                p.as_object_mut()
                    .unwrap()
                    .insert("parents".into(), json!([CID_A, CID_B]));
                p
            },
            expect_valid: true,
        },
        VectorCase {
            id: "pos-result-succeeded",
            kind: "result",
            payload: base_result_succeeded(),
            expect_valid: true,
        },
        VectorCase {
            id: "pos-result-failed-with-error",
            kind: "result",
            payload: base_result_failed(),
            expect_valid: true,
        },
        VectorCase {
            id: "pos-receipt-succeeded",
            kind: "receipt",
            payload: base_receipt_succeeded(),
            expect_valid: true,
        },
        VectorCase {
            id: "pos-receipt-failed",
            kind: "receipt",
            payload: base_receipt_failed(),
            expect_valid: true,
        },
        VectorCase {
            id: "pos-portable-error",
            kind: "error",
            payload: base_portable_error(),
            expect_valid: true,
        },
    ];

    // Envelope negatives
    {
        let mut p = base_envelope();
        p.as_object_mut()
            .unwrap()
            .insert("schema".into(), json!("mcp++/execution/envelope@0"));
        cases.push(VectorCase {
            id: "neg-envelope-wrong-schema",
            kind: "envelope",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_envelope();
        p.as_object_mut().unwrap().remove("interface_cid");
        cases.push(VectorCase {
            id: "neg-envelope-missing-interface-cid",
            kind: "envelope",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_envelope();
        p.as_object_mut()
            .unwrap()
            .insert("interface_cid".into(), json!("not-a-cid"));
        cases.push(VectorCase {
            id: "neg-envelope-invalid-cid",
            kind: "envelope",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_envelope();
        p.as_object_mut()
            .unwrap()
            .insert("requester".into(), json!({ "did": "not-a-did" }));
        cases.push(VectorCase {
            id: "neg-envelope-invalid-did",
            kind: "envelope",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_envelope();
        p.as_object_mut()
            .unwrap()
            .insert("authority".into(), json!({ "proof_cids": ["bad-cid"] }));
        cases.push(VectorCase {
            id: "neg-envelope-invalid-proof-cid",
            kind: "envelope",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_envelope();
        p.as_object_mut()
            .unwrap()
            .insert("canonicalization".into(), json!("jcs-v0"));
        cases.push(VectorCase {
            id: "neg-envelope-bad-canonicalization",
            kind: "envelope",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_envelope();
        p.as_object_mut()
            .unwrap()
            .insert("created_at_ms".into(), json!(-1));
        cases.push(VectorCase {
            id: "neg-envelope-negative-timestamp",
            kind: "envelope",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_envelope();
        p.as_object_mut()
            .unwrap()
            .insert("correlation_id".into(), json!(""));
        cases.push(VectorCase {
            id: "neg-envelope-empty-correlation",
            kind: "envelope",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_envelope();
        p.as_object_mut()
            .unwrap()
            .insert("parents".into(), json!(["not-a-cid"]));
        cases.push(VectorCase {
            id: "neg-envelope-bad-parent",
            kind: "envelope",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_envelope();
        p.as_object_mut()
            .unwrap()
            .get_mut("authority")
            .unwrap()
            .as_object_mut()
            .unwrap()
            .remove("proof_cids");
        cases.push(VectorCase {
            id: "neg-envelope-missing-proof-cids",
            kind: "envelope",
            payload: p,
            expect_valid: false,
        });
    }

    // Error negatives
    {
        let mut p = base_portable_error();
        p.as_object_mut()
            .unwrap()
            .insert("schema".into(), json!("mcp++/execution/portable-error@0"));
        cases.push(VectorCase {
            id: "neg-error-wrong-schema",
            kind: "error",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_portable_error();
        p.as_object_mut().unwrap().remove("code");
        cases.push(VectorCase {
            id: "neg-error-missing-code",
            kind: "error",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_portable_error();
        p.as_object_mut()
            .unwrap()
            .insert("failure_class".into(), json!("bogus"));
        cases.push(VectorCase {
            id: "neg-error-bad-failure-class",
            kind: "error",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_portable_error();
        p.as_object_mut()
            .unwrap()
            .insert("retryable".into(), json!("yes"));
        cases.push(VectorCase {
            id: "neg-error-nonbool-retryable",
            kind: "error",
            payload: p,
            expect_valid: false,
        });
    }

    // Result negatives
    {
        let mut p = base_result_succeeded();
        p.as_object_mut()
            .unwrap()
            .insert("schema".into(), json!("mcp++/execution/result@0"));
        cases.push(VectorCase {
            id: "neg-result-wrong-schema",
            kind: "result",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_result_succeeded();
        p.as_object_mut().unwrap().remove("status");
        cases.push(VectorCase {
            id: "neg-result-missing-status",
            kind: "result",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_result_succeeded();
        p.as_object_mut()
            .unwrap()
            .insert("status".into(), json!("running"));
        cases.push(VectorCase {
            id: "neg-result-bad-status",
            kind: "result",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_result_succeeded();
        p.as_object_mut()
            .unwrap()
            .insert("error".into(), base_portable_error());
        cases.push(VectorCase {
            id: "neg-result-succeeded-with-error",
            kind: "result",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_result_succeeded();
        p.as_object_mut()
            .unwrap()
            .insert("envelope_cid".into(), json!("not-a-cid"));
        cases.push(VectorCase {
            id: "neg-result-invalid-envelope-cid",
            kind: "result",
            payload: p,
            expect_valid: false,
        });
    }

    // Receipt negatives
    {
        let mut p = base_receipt_succeeded();
        p.as_object_mut()
            .unwrap()
            .insert("schema".into(), json!("mcp++/execution/receipt@0"));
        cases.push(VectorCase {
            id: "neg-receipt-wrong-schema",
            kind: "receipt",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_receipt_succeeded();
        p.as_object_mut().unwrap().remove("result_cid");
        cases.push(VectorCase {
            id: "neg-receipt-missing-result-cid",
            kind: "receipt",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_receipt_succeeded();
        p.as_object_mut()
            .unwrap()
            .insert("envelope_cid".into(), json!("not-a-cid"));
        cases.push(VectorCase {
            id: "neg-receipt-invalid-cid",
            kind: "receipt",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_receipt_succeeded();
        p.as_object_mut()
            .unwrap()
            .insert("status".into(), json!("running"));
        cases.push(VectorCase {
            id: "neg-receipt-bad-status",
            kind: "receipt",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_receipt_succeeded();
        p.as_object_mut()
            .unwrap()
            .insert("error".into(), base_portable_error());
        cases.push(VectorCase {
            id: "neg-receipt-succeeded-with-error",
            kind: "receipt",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_receipt_succeeded();
        let m = p.as_object_mut().unwrap();
        m.insert("started_at_ms".into(), json!(100));
        m.insert("finished_at_ms".into(), json!(1));
        cases.push(VectorCase {
            id: "neg-receipt-time-order",
            kind: "receipt",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_receipt_succeeded();
        p.as_object_mut()
            .unwrap()
            .insert("executor".into(), json!({ "did": "not-a-did" }));
        cases.push(VectorCase {
            id: "neg-receipt-bad-executor-did",
            kind: "receipt",
            payload: p,
            expect_valid: false,
        });
    }
    {
        let mut p = base_receipt_succeeded();
        p.as_object_mut()
            .unwrap()
            .insert("retry".into(), json!({ "attempt": 0 }));
        cases.push(VectorCase {
            id: "neg-receipt-retry-attempt-zero",
            kind: "receipt",
            payload: p,
            expect_valid: false,
        });
    }

    cases
}

fn expected_positive_ids() -> HashSet<&'static str> {
    [
        "pos-envelope-minimal",
        "pos-envelope-with-parents",
        "pos-result-succeeded",
        "pos-result-failed-with-error",
        "pos-receipt-succeeded",
        "pos-receipt-failed",
        "pos-portable-error",
    ]
    .into_iter()
    .collect()
}

fn expected_negative_ids() -> HashSet<&'static str> {
    [
        "neg-envelope-wrong-schema",
        "neg-envelope-missing-interface-cid",
        "neg-envelope-invalid-cid",
        "neg-envelope-invalid-did",
        "neg-envelope-invalid-proof-cid",
        "neg-envelope-bad-canonicalization",
        "neg-envelope-negative-timestamp",
        "neg-envelope-empty-correlation",
        "neg-envelope-bad-parent",
        "neg-envelope-missing-proof-cids",
        "neg-error-wrong-schema",
        "neg-error-missing-code",
        "neg-error-bad-failure-class",
        "neg-error-nonbool-retryable",
        "neg-result-wrong-schema",
        "neg-result-missing-status",
        "neg-result-bad-status",
        "neg-result-succeeded-with-error",
        "neg-result-invalid-envelope-cid",
        "neg-receipt-wrong-schema",
        "neg-receipt-missing-result-cid",
        "neg-receipt-invalid-cid",
        "neg-receipt-bad-status",
        "neg-receipt-succeeded-with-error",
        "neg-receipt-time-order",
        "neg-receipt-bad-executor-did",
        "neg-receipt-retry-attempt-zero",
    ]
    .into_iter()
    .collect()
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[test]
fn test_interface_constants() {
    assert_eq!(INTERFACE, "ExecutionEnvelopeValidator@1");
    assert_eq!(TASK_ID, "MCPP-033");
}

#[test]
fn test_catalog_ids_match_expected_sets() {
    let catalog = vector_catalog();
    let mut pos = HashSet::new();
    let mut neg = HashSet::new();
    let mut seen = HashSet::new();
    for c in &catalog {
        assert!(seen.insert(c.id), "duplicate case id {}", c.id);
        if c.expect_valid {
            pos.insert(c.id);
        } else {
            neg.insert(c.id);
        }
    }
    assert_eq!(pos, expected_positive_ids());
    assert_eq!(neg, expected_negative_ids());
}

#[test]
fn test_execution_envelope_vectors() {
    for c in vector_catalog() {
        let ok = validate_kind(c.kind, &c.payload);
        assert_eq!(
            ok, c.expect_valid,
            "{} ({}): expected valid={}, got {}",
            c.id, c.kind, c.expect_valid, ok
        );
    }
}

#[test]
fn test_all_positives_accept() {
    for c in vector_catalog() {
        if c.expect_valid {
            assert!(
                validate_kind(c.kind, &c.payload),
                "positive {} rejected",
                c.id
            );
        }
    }
}

#[test]
fn test_all_negatives_reject() {
    for c in vector_catalog() {
        if !c.expect_valid {
            assert!(
                !validate_kind(c.kind, &c.payload),
                "negative {} accepted",
                c.id
            );
        }
    }
}

#[test]
fn test_cross_kind_invariants() {
    let mut payload = base_result_succeeded();
    assert!(validate_kind("result", &payload));
    payload
        .as_object_mut()
        .unwrap()
        .insert("error".into(), base_portable_error());
    assert!(!validate_kind("result", &payload));

    let failed = base_result_failed();
    assert!(validate_kind("result", &failed));
    assert!(validate_kind("error", failed.get("error").unwrap()));

    let mut rc = base_receipt_succeeded();
    rc.as_object_mut().unwrap().remove("result_cid");
    assert!(!validate_kind("receipt", &rc));
}

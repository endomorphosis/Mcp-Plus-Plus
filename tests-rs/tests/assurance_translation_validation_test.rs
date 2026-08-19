//! FACP-035: independent translation validation for the Assurance DAG-CBOR codec.
//!
//! Acceptance:
//! - Validator independently rejects all negative/mutation vectors
//! - Confirms canonical round trips / CIDs
//! - Result binds compiler and validator identities separately
//!
//! `lib.rs` is outside this task's edit scope, so the codec module is loaded
//! via path include from `src/assurance_codec.rs`.

#![forbid(unsafe_code)]

#[path = "../src/assurance_codec.rs"]
mod assurance_codec;

use assurance_codec::*;
use serde_json::Value as JsonValue;
use std::fs;
use std::path::PathBuf;

fn vectors_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../conformance/vectors/assurance-canonical-encoding.json")
}

fn load_vectors() -> JsonValue {
    let path = vectors_path();
    let text = fs::read_to_string(&path).unwrap_or_else(|e| panic!("read {:?}: {e}", path));
    serde_json::from_str(&text).expect("parse assurance-canonical-encoding.json")
}

#[test]
fn codec_and_validator_identity_constants() {
    assert_eq!(TASK_ID, "FACP-035");
    assert_eq!(GOAL_ID, "FACP-G310");
    assert_eq!(BUNDLE, "facp/contracts/rust-codec");
    assert_eq!(DAG_CBOR_PROFILE, "facp/dag-cbor-profile@1");
    assert_eq!(VALIDATION_RESULT_SCHEMA, "facp/translation-validation@1");
    assert_eq!(VALIDATOR_VERSION, 1);

    // Compiler identity is distinct and recorded separately.
    assert_eq!(COMPILER_TASK_ID, "FACP-034");
    assert_eq!(COMPILER_BUNDLE, "facp/contracts/compiler");
    assert_eq!(COMPILER_VERSION, 1);

    let compiler = ComponentIdentity::compiler();
    let validator = ComponentIdentity::validator();
    assert_ne!(compiler.task_id, validator.task_id);
    assert_ne!(compiler.bundle, validator.bundle);
    assert_ne!(compiler.role, validator.role);
    assert_eq!(compiler.role, "compiler");
    assert_eq!(validator.role, "validator");
    assert_eq!(compiler.profile, validator.profile);
    assert_eq!(compiler.goal_id, validator.goal_id);
}

#[test]
fn error_codes_cover_normative_set() {
    for code in [
        "NON_DEFINITE_LENGTH",
        "DUPLICATE_MAP_KEY",
        "UNSORTED_MAP_KEYS",
        "NON_MINIMAL_INTEGER",
        "FORBIDDEN_FLOAT",
        "FORBIDDEN_TAG",
        "INVALID_CID_LINK",
        "NON_STRING_MAP_KEY",
        "MALLEABLE_ENCODING",
        "WRONG_CID_FAMILY",
        "NON_CANONICAL_CID_TEXT",
        "PSEUDO_CID",
        "UNKNOWN_FIELD",
        "REGEX_ONLY_CID",
    ] {
        assert!(
            ERROR_CODES.contains(&code),
            "missing error code {code}"
        );
    }
}

#[test]
fn empty_map_round_trip_and_cid() {
    let enc = encode(&Value::empty_map()).expect("encode");
    assert_eq!(enc, vec![0xa0]);
    let admitted = admit(&enc).expect("admit");
    assert_eq!(admitted, Value::empty_map());
    let cid = cid_for_bytes(&enc, SIGNED_CID_FAMILY).expect("cid");
    assert_eq!(
        cid,
        "bafyreigbtj4x7ip5legnfznufuopl4sg4knzc2cof6duas4b3q2fy6swua"
    );
    bind_cid_to_bytes(&cid, &enc, SIGNED_CID_FAMILY).expect("bind");
}

#[test]
fn reject_permissive_and_pseudo_cids() {
    assert_eq!(
        admit_cid_text(
            "ae4b3280e56e2faf83f414a6e3dabe9d5fbe18976544c05fed121accb85b53fc",
            Some(SIGNED_CID_FAMILY)
        )
        .unwrap_err()
        .code,
        "PSEUDO_CID"
    );
    assert_eq!(
        admit_cid_text(
            "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
            Some(SIGNED_CID_FAMILY)
        )
        .unwrap_err()
        .code,
        "PSEUDO_CID"
    );
    assert_eq!(
        admit_cid_text(
            "BAFYREIGBTJ4X7IP5LEGNFZNUFUOPL4SG4KNZC2COF6DUAS4B3Q2FY6SWUA",
            Some(SIGNED_CID_FAMILY)
        )
        .unwrap_err()
        .code,
        "NON_CANONICAL_CID_TEXT"
    );
}

#[test]
fn regex_only_cid_lookalike_is_rejected() {
    let enc = encode(&Value::empty_map()).unwrap();
    let good = cid_for_bytes(&enc, SIGNED_CID_FAMILY).unwrap();
    let lookalike = format!("bafyrei{}", "a".repeat(good.len() - "bafyrei".len()));
    assert!(lookalike.chars().all(|c| matches!(c, 'a'..='z' | '2'..='7')));
    let err = bind_cid_to_bytes(&lookalike, &enc, SIGNED_CID_FAMILY).unwrap_err();
    assert!(
        matches!(
            err.code,
            "PSEUDO_CID" | "NON_CANONICAL_CID_TEXT" | "WRONG_CID_FAMILY"
        ),
        "unexpected {}",
        err.code
    );
}

#[test]
fn independent_translation_validation_confirms_all_vectors() {
    let vectors = load_vectors();
    assert_eq!(
        vectors.get("schema").and_then(|v| v.as_str()),
        Some(VECTORS_SCHEMA)
    );
    assert_eq!(
        vectors.get("profile").and_then(|v| v.as_str()),
        Some(DAG_CBOR_PROFILE)
    );

    let result = validate_conformance_vectors(&vectors)
        .expect("validate_conformance_vectors");

    // Identities bound separately in the result object.
    assert_eq!(result.compiler_identity.task_id, COMPILER_TASK_ID);
    assert_eq!(result.compiler_identity.bundle, COMPILER_BUNDLE);
    assert_eq!(result.compiler_identity.role, "compiler");
    assert_eq!(result.validator_identity.task_id, TASK_ID);
    assert_eq!(result.validator_identity.bundle, BUNDLE);
    assert_eq!(result.validator_identity.role, "validator");
    assert_ne!(
        result.compiler_identity.task_id,
        result.validator_identity.task_id
    );
    assert_ne!(
        result.compiler_identity.bundle,
        result.validator_identity.bundle
    );

    let receipt = result.to_json();
    assert_eq!(
        receipt.get("schema").and_then(|v| v.as_str()),
        Some(VALIDATION_RESULT_SCHEMA)
    );
    assert_eq!(
        receipt
            .get("identities_bound_separately")
            .and_then(|v| v.as_bool()),
        Some(true)
    );
    assert!(
        receipt.get("compiler_identity").is_some()
            && receipt.get("validator_identity").is_some()
    );
    // Separate object identity: keys are distinct siblings, not a merged blob.
    let compiler_obj = receipt.get("compiler_identity").unwrap();
    let validator_obj = receipt.get("validator_identity").unwrap();
    assert_ne!(compiler_obj, validator_obj);

    let positive_n = vectors
        .get("positive")
        .and_then(|v| v.as_array())
        .map(|a| a.len())
        .unwrap_or(0);
    let negative_n = vectors
        .get("negative")
        .and_then(|v| v.as_array())
        .map(|a| a.len())
        .unwrap_or(0);
    let mutation_n = vectors
        .get("mutations")
        .and_then(|v| v.as_array())
        .map(|a| a.len())
        .unwrap_or(0);

    assert!(
        result.passed,
        "independent validator failed cases: {:?}",
        result
            .cases
            .iter()
            .filter(|c| !c.ok)
            .collect::<Vec<_>>()
    );
    assert_eq!(result.positive_confirmed, positive_n);
    assert_eq!(result.negative_rejected, negative_n);
    assert_eq!(result.mutations_rejected, mutation_n);
    assert!(positive_n >= 12);
    assert!(negative_n >= 10);
    assert!(mutation_n >= 4);
}

#[test]
fn every_negative_and_mutation_vector_is_rejected() {
    let vectors = load_vectors();
    let result = validate_conformance_vectors(&vectors).expect("validate");
    for case in &result.cases {
        if case.kind == "negative" || case.kind == "mutation" {
            assert!(case.ok, "case {} not rejected: {:?}", case.id, case);
            assert_eq!(
                case.expected_error.as_deref(),
                case.observed_error.as_deref(),
                "error code mismatch for {}",
                case.id
            );
        }
    }
}

#[test]
fn every_positive_vector_round_trips_with_exact_cid() {
    let vectors = load_vectors();
    let result = validate_conformance_vectors(&vectors).expect("validate");
    for case in &result.cases {
        if case.kind == "positive" {
            assert!(case.ok, "positive {} failed: {:?}", case.id, case);
            assert!(case.cid.is_some(), "positive {} missing cid", case.id);
        }
    }
}

#[test]
fn does_not_trust_generator_without_validation() {
    // A forged "compiler said so" CID for empty-map bytes must fail bind.
    let enc = encode(&Value::empty_map()).unwrap();
    let forged = "baguqeera2sqr5w35auer2ningx63ebbifdj2vhnelzpyep62ozpf75cucb4a";
    let err = bind_cid_to_bytes(forged, &enc, SIGNED_CID_FAMILY).unwrap_err();
    assert_eq!(err.code, "WRONG_CID_FAMILY");
}

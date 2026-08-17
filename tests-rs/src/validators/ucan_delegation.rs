//! UCAN Delegation Validator (Profile C) — DelegationProof@1
//!
//! Validates UCAN tokens and delegation chains with dual conformance levels:
//! structural (field shape) and cryptographic (Ed25519 over mcpp-jcs-v1 bytes).
//!
//! SPEC: UCAN-Delegation.md
//! Crypto: ADR-0002 (EdDSA/Ed25519, explicit kid, signatures over canonical bytes)
//! Levels: ADR-0003

use crate::models::*;
use crate::validators::base_mcp::{ValidationError, ValidationResult};
use serde_json::{Map, Value};
use serde_valid::Validate;
use std::collections::BTreeMap;

/// DelegationProof@1 interface label.
pub const INTERFACE: &str = "DelegationProof@1";
/// mcpp-jcs-v1 algorithm id used for signature input construction.
pub const CANONICAL_ALGORITHM: &str = "mcpp-jcs-v1";
/// JOSE/UCAN wire algorithm name.
pub const SIGNATURE_ALG_EDDSA: &str = "EdDSA";
/// Profile H style algorithm name (accepted synonym).
pub const SIGNATURE_ALG_ED25519: &str = "Ed25519";

/// SPKI DER prefix for a 32-byte raw Ed25519 public key (RFC 8410).
const ED25519_SPKI_PREFIX: &[u8] = &[
    0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0x00,
];

/// One conformance-level outcome.
#[derive(Debug, Clone)]
pub struct LevelResult {
    /// Whether this level passed.
    pub valid: bool,
    /// Level-specific errors.
    pub errors: Vec<String>,
    /// Stable reason code when invalid.
    pub reason_code: Option<String>,
}

impl LevelResult {
    fn ok() -> Self {
        Self {
            valid: true,
            errors: Vec::new(),
            reason_code: None,
        }
    }

    fn fail(errors: Vec<String>, reason: &str) -> Self {
        Self {
            valid: false,
            errors,
            reason_code: Some(reason.to_string()),
        }
    }
}

/// Dual-level validation outcome for DelegationProof@1.
#[derive(Debug, Clone)]
pub struct DelegationLevels {
    /// Structural shape validity.
    pub structural: LevelResult,
    /// Cryptographic signature validity.
    pub cryptographic: LevelResult,
    /// Highest fully achieved level: "structural" | "cryptographic" | none.
    pub conformance_level: Option<String>,
}

fn attach_levels(result: &mut ValidationResult, levels: &DelegationLevels) {
    // Store level summary in warnings for inspectability without changing ValidationResult shape.
    result.warnings.push(format!(
        "levels:structural={};cryptographic={};conformance={}",
        levels.structural.valid,
        levels.cryptographic.valid,
        levels
            .conformance_level
            .clone()
            .unwrap_or_else(|| "none".to_string())
    ));
    if let Some(ref code) = levels.cryptographic.reason_code {
        result.warnings.push(format!("cryptographic_reason:{code}"));
    }
    for e in &levels.cryptographic.errors {
        if !result.warnings.iter().any(|w| w == e) {
            result.warnings.push(e.clone());
        }
    }
}

fn make_levels(structural: LevelResult, cryptographic: LevelResult) -> DelegationLevels {
    let conformance_level = if structural.valid && cryptographic.valid {
        Some("cryptographic".to_string())
    } else if structural.valid {
        Some("structural".to_string())
    } else {
        None
    };
    DelegationLevels {
        structural,
        cryptographic,
        conformance_level,
    }
}

// ---------------------------------------------------------------------------
// Encoding helpers
// ---------------------------------------------------------------------------

fn b64url_encode(raw: &[u8]) -> String {
    const T: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    let mut out = String::new();
    let mut i = 0;
    while i + 3 <= raw.len() {
        let n = ((raw[i] as u32) << 16) | ((raw[i + 1] as u32) << 8) | (raw[i + 2] as u32);
        out.push(T[((n >> 18) & 63) as usize] as char);
        out.push(T[((n >> 12) & 63) as usize] as char);
        out.push(T[((n >> 6) & 63) as usize] as char);
        out.push(T[(n & 63) as usize] as char);
        i += 3;
    }
    if i < raw.len() {
        let rem = raw.len() - i;
        let n = if rem == 1 {
            (raw[i] as u32) << 16
        } else {
            ((raw[i] as u32) << 16) | ((raw[i + 1] as u32) << 8)
        };
        out.push(T[((n >> 18) & 63) as usize] as char);
        out.push(T[((n >> 12) & 63) as usize] as char);
        if rem == 2 {
            out.push(T[((n >> 6) & 63) as usize] as char);
        }
    }
    out
}

fn b64url_decode(text: &str) -> Result<Vec<u8>, String> {
    let t = text.trim();
    if t.is_empty() {
        return Err("empty_base64url".into());
    }
    for ch in t.chars() {
        if !(ch.is_ascii_alphanumeric() || ch == '-' || ch == '_') {
            return Err("invalid_base64url".into());
        }
    }
    let mut s = t.to_string();
    while s.len() % 4 != 0 {
        s.push('=');
    }
    // Convert url-safe to standard for a small decoder.
    let s = s.replace('-', "+").replace('_', "/");
    let table = |c: u8| -> Option<u8> {
        match c {
            b'A'..=b'Z' => Some(c - b'A'),
            b'a'..=b'z' => Some(c - b'a' + 26),
            b'0'..=b'9' => Some(c - b'0' + 52),
            b'+' => Some(62),
            b'/' => Some(63),
            _ => None,
        }
    };
    let bytes = s.as_bytes();
    let mut out = Vec::new();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'=' {
            break;
        }
        let a = table(bytes[i]).ok_or_else(|| "invalid_base64url".to_string())?;
        let b = table(bytes[i + 1]).ok_or_else(|| "invalid_base64url".to_string())?;
        out.push((a << 2) | (b >> 4));
        if i + 2 >= bytes.len() || bytes[i + 2] == b'=' {
            break;
        }
        let c = table(bytes[i + 2]).ok_or_else(|| "invalid_base64url".to_string())?;
        out.push(((b & 0x0f) << 4) | (c >> 2));
        if i + 3 >= bytes.len() || bytes[i + 3] == b'=' {
            break;
        }
        let d = table(bytes[i + 3]).ok_or_else(|| "invalid_base64url".to_string())?;
        out.push(((c & 0x03) << 6) | d);
        i += 4;
    }
    if b64url_encode(&out) != t {
        return Err("noncanonical_base64url".into());
    }
    Ok(out)
}

const B58: &[u8] = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

fn base58btc_decode(text: &str) -> Result<Vec<u8>, String> {
    if text.is_empty() {
        return Ok(Vec::new());
    }
    let mut acc = vec![0u8];
    for ch in text.chars() {
        let idx = B58
            .iter()
            .position(|&c| c == ch as u8)
            .ok_or_else(|| "invalid_base58btc".to_string())?;
        // acc = acc * 58 + idx
        let mut carry = idx as u32;
        for b in acc.iter_mut().rev() {
            let v = (*b as u32) * 58 + carry;
            *b = (v & 0xff) as u8;
            carry = v >> 8;
        }
        while carry > 0 {
            acc.insert(0, (carry & 0xff) as u8);
            carry >>= 8;
        }
    }
    let mut zeros = 0usize;
    for ch in text.chars() {
        if ch != '1' {
            break;
        }
        zeros += 1;
    }
    let mut out = vec![0u8; zeros];
    // strip leading zeros from acc then append
    let start = acc.iter().position(|&b| b != 0).unwrap_or(acc.len());
    out.extend_from_slice(&acc[start..]);
    Ok(out)
}

/// Extract 32-byte Ed25519 public key from `did:key:z…` (multicodec 0xed01).
pub fn ed25519_public_key_from_did_key(did: &str) -> Option<Vec<u8>> {
    let text = did.trim();
    if !text.starts_with("did:key:") {
        return None;
    }
    let mb = &text["did:key:".len()..];
    if !mb.starts_with('z') {
        return None;
    }
    let decoded = base58btc_decode(&mb[1..]).ok()?;
    if decoded.len() >= 34 && decoded[0] == 0xed && decoded[1] == 0x01 {
        return Some(decoded[2..34].to_vec());
    }
    None
}

fn decode_public_key(value: &Value) -> Option<Vec<u8>> {
    match value {
        Value::String(text) => {
            let mut t = text.trim().to_string();
            if t.starts_with("did:key:") {
                return ed25519_public_key_from_did_key(&t);
            }
            if t.starts_with("ed25519-pub:") {
                t = t["ed25519-pub:".len()..].trim().to_string();
            }
            if t.len() == 64 {
                if let Ok(raw) = hex_decode(&t) {
                    if raw.len() == 32 {
                        return Some(raw);
                    }
                }
            }
            if let Ok(raw) = b64url_decode(&t) {
                if raw.len() == 32 {
                    return Some(raw);
                }
            }
            None
        }
        Value::Object(map) => {
            let alg = map
                .get("alg")
                .or_else(|| map.get("algorithm"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_ascii_lowercase();
            if !alg.is_empty() && alg != "ed25519" && alg != "eddsa" {
                return None;
            }
            for key in [
                "public_key",
                "public_key_b64",
                "public_key_base64",
                "publicKey",
                "key",
                "did_key",
                "did",
            ] {
                if let Some(v) = map.get(key) {
                    if let Some(raw) = decode_public_key(v) {
                        return Some(raw);
                    }
                }
            }
            if let Some(v) = map.get("public_key_hex") {
                return decode_public_key(v);
            }
            None
        }
        _ => None,
    }
}

fn decode_signature(value: &Value) -> Option<Vec<u8>> {
    match value {
        Value::String(text) => {
            let mut t = text.trim().to_string();
            if t.starts_with("ed25519:") {
                t = t["ed25519:".len()..].trim().to_string();
            } else if t.starts_with("ed25519-hex:") || t.starts_with("hex:") {
                let hexpart = t.split_once(':').map(|(_, r)| r.trim()).unwrap_or("");
                if let Ok(raw) = hex_decode(hexpart) {
                    if raw.len() == 64 {
                        return Some(raw);
                    }
                }
                return None;
            }
            if t.len() == 128 {
                if let Ok(raw) = hex_decode(&t) {
                    if raw.len() == 64 {
                        return Some(raw);
                    }
                }
            }
            if let Ok(raw) = b64url_decode(&t) {
                if raw.len() == 64 {
                    return Some(raw);
                }
            }
            None
        }
        _ => None,
    }
}

fn hex_decode(s: &str) -> Result<Vec<u8>, ()> {
    if s.len() % 2 != 0 {
        return Err(());
    }
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).map_err(|_| ()))
        .collect()
}

// ---------------------------------------------------------------------------
// Minimal mcpp-jcs-v1 for UCAN payload domain (objects/arrays/strings/ints/bools/null)
// ---------------------------------------------------------------------------

fn jcs_escape(s: &str) -> String {
    let mut out = String::from("\"");
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{08}' => out.push_str("\\b"),
            '\u{0c}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn canonicalize_value(value: &Value) -> Result<String, String> {
    match value {
        Value::Null => Ok("null".into()),
        Value::Bool(b) => Ok(if *b { "true" } else { "false" }.into()),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.to_string())
            } else if let Some(u) = n.as_u64() {
                Ok(u.to_string())
            } else if let Some(f) = n.as_f64() {
                if !f.is_finite() {
                    return Err("reject_nan_infinity".into());
                }
                // Sufficient for integer-like UCAN exp fields; floats rare in UCAN.
                Ok(ryu_like(f))
            } else {
                Err("reject_unsupported_type".into())
            }
        }
        Value::String(s) => Ok(jcs_escape(s)),
        Value::Array(arr) => {
            let mut parts = Vec::with_capacity(arr.len());
            for item in arr {
                parts.push(canonicalize_value(item)?);
            }
            Ok(format!("[{}]", parts.join(",")))
        }
        Value::Object(map) => {
            // Sort keys by UTF-16 code units (ASCII-compatible for typical UCAN keys).
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort_by(|a, b| utf16_units(a).cmp(&utf16_units(b)));
            let mut parts = Vec::with_capacity(keys.len());
            for k in keys {
                let v = map.get(k).ok_or_else(|| "missing_key".to_string())?;
                parts.push(format!("{}:{}", jcs_escape(k), canonicalize_value(v)?));
            }
            Ok(format!("{{{}}}", parts.join(",")))
        }
    }
}

fn utf16_units(s: &str) -> Vec<u16> {
    s.encode_utf16().collect()
}

fn ryu_like(f: f64) -> String {
    // Compact ES6-ish for common values; UCAN tokens use integers for exp/nbf.
    if f == 0.0 {
        return "0".into();
    }
    let s = format!("{}", f);
    if s.contains('e') || s.contains('E') {
        // normalize
        return s.replace('E', "e");
    }
    s
}

/// Canonical mcpp-jcs-v1 UTF-8 bytes for a JSON value.
pub fn canonicalize_bytes(value: &Value) -> Result<Vec<u8>, String> {
    Ok(canonicalize_value(value)?.into_bytes())
}

fn is_sig_meta(k: &str) -> bool {
    matches!(
        k,
        "signature"
            | "sig"
            | "signatures"
            | "public_key"
            | "publicKey"
            | "public_key_b64"
            | "issuer_public_key"
            | "header"
            | "protected"
            | "alg"
            | "kid"
            | "signature_alg"
            | "signatureAlg"
    )
}

fn signing_object(token: &Map<String, Value>) -> Map<String, Value> {
    if let Some(Value::Object(payload)) = token.get("payload") {
        let mut out = Map::new();
        for (k, v) in payload {
            if !is_sig_meta(k) {
                out.insert(k.clone(), v.clone());
            }
        }
        return out;
    }
    let mut out = Map::new();
    for (k, v) in token {
        if !is_sig_meta(k) && k != "token" {
            out.insert(k.clone(), v.clone());
        }
    }
    out
}

/// Detached-object signing input (mcpp-jcs-v1 bytes of the token without sig meta).
pub fn canonical_signing_bytes(token: &Map<String, Value>) -> Result<Vec<u8>, String> {
    canonicalize_bytes(&Value::Object(signing_object(token)))
}

fn compact_signing_input(header: &Map<String, Value>, payload: &Map<String, Value>) -> Result<Vec<u8>, String> {
    let h = b64url_encode(&canonicalize_bytes(&Value::Object(header.clone()))?);
    let p = b64url_encode(&canonicalize_bytes(&Value::Object(payload.clone()))?);
    Ok(format!("{h}.{p}").into_bytes())
}

/// Verify Ed25519 signature over `message` using the system OpenSSL CLI.
///
/// Fail-closed: missing openssl, encoding errors, and invalid signatures all
/// return false. Uses RFC 8410 SPKI wrapping of the raw 32-byte public key.
pub fn verify_ed25519(public_key: &[u8], message: &[u8], signature: &[u8]) -> bool {
    if public_key.len() != 32 || signature.len() != 64 {
        return false;
    }
    let mut spki = Vec::with_capacity(ED25519_SPKI_PREFIX.len() + 32);
    spki.extend_from_slice(ED25519_SPKI_PREFIX);
    spki.extend_from_slice(public_key);

    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let base = std::env::temp_dir().join(format!("mcpp-ed25519-{}-{}", std::process::id(), stamp));
    let pub_path = base.with_extension("pub.der");
    let msg_path = base.with_extension("msg");
    let sig_path = base.with_extension("sig");

    let write_ok = std::fs::write(&pub_path, &spki).is_ok()
        && std::fs::write(&msg_path, message).is_ok()
        && std::fs::write(&sig_path, signature).is_ok();
    if !write_ok {
        let _ = std::fs::remove_file(&pub_path);
        let _ = std::fs::remove_file(&msg_path);
        let _ = std::fs::remove_file(&sig_path);
        return false;
    }

    let status = std::process::Command::new("openssl")
        .args(["pkeyutl", "-verify", "-pubin", "-inkey"])
        .arg(&pub_path)
        .args(["-rawin", "-in"])
        .arg(&msg_path)
        .arg("-sigfile")
        .arg(&sig_path)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status();

    let _ = std::fs::remove_file(&pub_path);
    let _ = std::fs::remove_file(&msg_path);
    let _ = std::fs::remove_file(&sig_path);

    matches!(status, Ok(s) if s.success())
}

// ---------------------------------------------------------------------------
// Validator
// ---------------------------------------------------------------------------

/// UCAN Delegation Validator
pub struct UCANDelegationValidator {
    issuer_public_keys: BTreeMap<String, Value>,
    require_signatures: bool,
}

impl UCANDelegationValidator {
    /// Create a new validator.
    pub fn new() -> Self {
        Self {
            issuer_public_keys: BTreeMap::new(),
            require_signatures: false,
        }
    }

    /// Register issuer public keys for cryptographic verification.
    pub fn with_issuer_public_keys(mut self, keys: BTreeMap<String, Value>) -> Self {
        self.issuer_public_keys = keys;
        self
    }

    /// Require signatures to pass overall validity.
    pub fn with_require_signatures(mut self, require: bool) -> Self {
        self.require_signatures = require;
        self
    }

    /// Validate a UCAN token (structural + crypto levels).
    /// SPEC: UCAN-Delegation.md § UCAN Token Structure, MUST
    pub fn validate_ucan_token(
        &self,
        payload: &Value,
    ) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("ucan_token".to_string());

        let token: UCANToken = serde_json::from_value(payload.clone())?;

        if let Err(e) = token.validate() {
            result.add_error(format!("Validation error: {}", e));
        }

        if token.att.is_empty() {
            result.add_error("UCAN must have at least one attenuation".to_string());
        }

        let structural_ok = result.is_valid;
        let (crypto_errors, crypto_reason, has_sig, crypto_ok) =
            self.verify_token_crypto(payload, 0);

        if has_sig && !crypto_ok {
            for e in &crypto_errors {
                result.add_error(e.clone());
            }
        }
        if self.require_signatures && !crypto_ok {
            for e in &crypto_errors {
                if !result.errors.contains(e) {
                    result.add_error(e.clone());
                }
            }
        }

        let levels = make_levels(
            if structural_ok {
                LevelResult::ok()
            } else {
                LevelResult::fail(result.errors.clone(), "structural_invalid")
            },
            if structural_ok && crypto_ok {
                LevelResult::ok()
            } else {
                LevelResult::fail(
                    if crypto_errors.is_empty() {
                        vec!["missing_signature".into()]
                    } else {
                        crypto_errors
                    },
                    crypto_reason.as_deref().unwrap_or(if has_sig {
                        "invalid_signature"
                    } else {
                        "missing_signature"
                    }),
                )
            },
        );
        attach_levels(&mut result, &levels);
        Ok(result)
    }

    /// Cryptographic verification of a single delegation proof (DelegationProof@1).
    /// `is_valid` requires both structural and cryptographic success.
    pub fn verify_delegation_proof(
        &self,
        payload: &Value,
    ) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("delegation_proof".to_string());
        // Structural via typed model when possible.
        if let Ok(token) = serde_json::from_value::<UCANToken>(payload.clone()) {
            if let Err(e) = token.validate() {
                result.add_error(format!("Validation error: {}", e));
            }
            if token.att.is_empty() {
                result.add_error("UCAN must have at least one attenuation".to_string());
            }
        } else {
            // Hand structural for full-name / raw objects.
            let obj = payload.as_object();
            if obj.is_none() {
                result.add_error("Token must be an object".into());
            } else {
                let o = obj.unwrap();
                let iss = o.get("iss").or_else(|| o.get("issuer"));
                let aud = o.get("aud").or_else(|| o.get("audience"));
                let att = o.get("att").or_else(|| o.get("capabilities"));
                let exp = o
                    .get("exp")
                    .or_else(|| o.get("expiry"))
                    .or_else(|| o.get("expiration"));
                if iss.is_none() {
                    result.add_error("Token at index 0 missing required field: iss".into());
                }
                if aud.is_none() {
                    result.add_error("Token at index 0 missing required field: aud".into());
                }
                if att.is_none() {
                    result.add_error("Token at index 0 missing required field: att".into());
                }
                if exp.is_none() {
                    result.add_error("Token at index 0 missing required field: exp".into());
                }
            }
        }

        let structural_ok = result.is_valid;
        let (crypto_errors, crypto_reason, _has_sig, crypto_ok) =
            self.verify_token_crypto(payload, 0);
        for e in &crypto_errors {
            result.add_error(e.clone());
        }
        let cryptographic_ok = structural_ok && crypto_ok;
        if !cryptographic_ok {
            result.is_valid = false;
        }
        let levels = make_levels(
            if structural_ok {
                LevelResult::ok()
            } else {
                LevelResult::fail(result.errors.clone(), "structural_invalid")
            },
            if cryptographic_ok {
                LevelResult::ok()
            } else {
                LevelResult::fail(
                    crypto_errors,
                    crypto_reason.as_deref().unwrap_or("invalid_signature"),
                )
            },
        );
        attach_levels(&mut result, &levels);
        Ok(result)
    }

    /// Validate a delegation chain
    /// SPEC: UCAN-Delegation.md § Delegation Chain, MUST
    pub fn validate_delegation_chain(
        &self,
        payload: &Value,
    ) -> Result<ValidationResult, ValidationError> {
        let mut result = ValidationResult::new("delegation_chain".to_string());

        let chain: DelegationChain = serde_json::from_value(payload.clone())?;

        if let Err(e) = chain.validate() {
            result.add_error(format!("Validation error: {}", e));
            let levels = make_levels(
                LevelResult::fail(result.errors.clone(), "structural_invalid"),
                LevelResult::fail(vec!["structural_failed".into()], "structural_failed"),
            );
            attach_levels(&mut result, &levels);
            return Ok(result);
        }

        for (i, token) in chain.chain.iter().enumerate() {
            if let Err(e) = token.validate() {
                result.add_error(format!("Token {} validation error: {}", i, e));
            }
        }

        let structural_ok = result.is_valid;
        let mut crypto_errors = Vec::new();
        let mut crypto_reason = None;
        let mut all_crypto_ok = true;
        let mut saw_sig = false;

        if let Some(arr) = payload.get("chain").and_then(|v| v.as_array()) {
            for (i, tok) in arr.iter().enumerate() {
                let (errs, reason, has_sig, ok) = self.verify_token_crypto(tok, i);
                if has_sig {
                    saw_sig = true;
                }
                if !ok {
                    all_crypto_ok = false;
                    crypto_errors.extend(errs.clone());
                    if crypto_reason.is_none() {
                        crypto_reason = reason;
                    }
                    if has_sig {
                        for e in errs {
                            result.add_error(e);
                        }
                    }
                }
            }
        }

        if self.require_signatures && !all_crypto_ok {
            for e in &crypto_errors {
                if !result.errors.contains(e) {
                    result.add_error(e.clone());
                }
            }
        }

        let levels = make_levels(
            if structural_ok {
                LevelResult::ok()
            } else {
                LevelResult::fail(result.errors.clone(), "structural_invalid")
            },
            if structural_ok && all_crypto_ok {
                LevelResult::ok()
            } else {
                LevelResult::fail(
                    if crypto_errors.is_empty() {
                        vec!["missing_signature".into()]
                    } else {
                        crypto_errors
                    },
                    crypto_reason.as_deref().unwrap_or(if saw_sig {
                        "invalid_signature"
                    } else {
                        "missing_signature"
                    }),
                )
            },
        );
        attach_levels(&mut result, &levels);
        Ok(result)
    }

    fn verify_token_crypto(
        &self,
        token: &Value,
        index: usize,
    ) -> (Vec<String>, Option<String>, bool, bool) {
        let obj = match token.as_object() {
            Some(o) => o,
            None => {
                return (
                    vec![format!("Token at index {index} must be an object")],
                    Some("structural_failed".into()),
                    false,
                    false,
                );
            }
        };

        // Nested compact token.
        for key in ["token", "ucan", "jwt"] {
            if let Some(Value::String(s)) = obj.get(key) {
                if s.matches('.').count() == 2 {
                    return self.verify_compact_token(s, index);
                }
            }
        }

        let sig_raw = obj.get("signature").or_else(|| obj.get("sig"));
        let has_sig = match sig_raw {
            Some(v) => match v {
                Value::String(s) => !s.trim().is_empty(),
                _ => true,
            },
            None => false,
        };
        if !has_sig {
            return (
                vec![format!("Token at index {index}: missing signature")],
                Some("missing_signature".into()),
                false,
                false,
            );
        }

        let header = obj
            .get("header")
            .or_else(|| obj.get("protected"))
            .and_then(|v| v.as_object());
        let mut alg = header
            .and_then(|h| h.get("alg"))
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        if alg.is_none() {
            alg = obj
                .get("alg")
                .or_else(|| obj.get("signature_alg"))
                .or_else(|| obj.get("signatureAlg"))
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());
        }
        let mut kid = header
            .and_then(|h| h.get("kid"))
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        if kid.is_none() {
            kid = obj
                .get("kid")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());
        }

        if let Some(ref a) = alg {
            let a = a.trim();
            if matches!(a, "none" | "None" | "NONE" | "") {
                return (
                    vec![format!("Token at index {index}: algorithm_or_version_downgrade")],
                    Some("algorithm_or_version_downgrade".into()),
                    true,
                    false,
                );
            }
            if a != SIGNATURE_ALG_EDDSA
                && a != SIGNATURE_ALG_ED25519
                && a != "ed25519"
                && a != "Ed25519"
            {
                return (
                    vec![format!(
                        "Token at index {index}: unsupported_signature_alg:{a}"
                    )],
                    Some("unsupported_signature_alg".into()),
                    true,
                    false,
                );
            }
        }

        let iss = obj
            .get("iss")
            .or_else(|| obj.get("issuer"))
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if kid.as_deref().unwrap_or("").trim().is_empty() && !iss.starts_with("did:key:") {
            return (
                vec![format!("Token at index {index}: missing_kid")],
                Some("missing_kid".into()),
                true,
                false,
            );
        }

        let signature = match sig_raw.and_then(decode_signature) {
            Some(s) => s,
            None => {
                return (
                    vec![format!("Token at index {index}: invalid_signature_encoding")],
                    Some("invalid_signature_encoding".into()),
                    true,
                    false,
                );
            }
        };

        let public_key = match self.resolve_public_key(obj, kid.as_deref().unwrap_or("")) {
            Some(k) => k,
            None => {
                return (
                    vec![format!("Token at index {index}: verification_key_unavailable")],
                    Some("verification_key_unavailable".into()),
                    true,
                    false,
                );
            }
        };

        let message = if let Some(h) = header {
            if let Some(Value::Object(payload)) = obj.get("payload") {
                compact_signing_input(h, payload)
            } else {
                compact_signing_input(h, &signing_object(obj))
            }
        } else {
            canonical_signing_bytes(obj)
        };

        let message = match message {
            Ok(m) => m,
            Err(_) => {
                return (
                    vec![format!("Token at index {index}: canonicalization_failed")],
                    Some("canonicalization_failed".into()),
                    true,
                    false,
                );
            }
        };

        if !verify_ed25519(&public_key, &message, &signature) {
            return (
                vec![format!("Token at index {index}: invalid_signature")],
                Some("invalid_signature".into()),
                true,
                false,
            );
        }

        (Vec::new(), None, true, true)
    }

    fn verify_compact_token(
        &self,
        token: &str,
        index: usize,
    ) -> (Vec<String>, Option<String>, bool, bool) {
        let parts: Vec<&str> = token.split('.').collect();
        if parts.len() != 3 || parts.iter().any(|p| p.is_empty()) {
            return (
                vec![
                    format!("Token at index {index} missing required field: att"),
                    format!("Token at index {index} missing required field: exp"),
                    format!("Token at index {index}: unsigned_or_malformed_token"),
                ],
                Some("unsigned_or_malformed_token".into()),
                false,
                false,
            );
        }
        let header_bytes = match b64url_decode(parts[0]) {
            Ok(b) => b,
            Err(_) => {
                return (
                    vec![format!("Token at index {index}: malformed_token")],
                    Some("malformed_token".into()),
                    true,
                    false,
                );
            }
        };
        let payload_bytes = match b64url_decode(parts[1]) {
            Ok(b) => b,
            Err(_) => {
                return (
                    vec![format!("Token at index {index}: malformed_token")],
                    Some("malformed_token".into()),
                    true,
                    false,
                );
            }
        };
        let signature = match b64url_decode(parts[2]) {
            Ok(b) if b.len() == 64 => b,
            _ => {
                return (
                    vec![format!("Token at index {index}: invalid_signature_encoding")],
                    Some("invalid_signature_encoding".into()),
                    true,
                    false,
                );
            }
        };

        let header: Map<String, Value> = match serde_json::from_slice(&header_bytes) {
            Ok(Value::Object(m)) => m,
            _ => {
                return (
                    vec![format!("Token at index {index}: malformed_token")],
                    Some("malformed_token".into()),
                    true,
                    false,
                );
            }
        };
        let payload: Map<String, Value> = match serde_json::from_slice(&payload_bytes) {
            Ok(Value::Object(m)) => m,
            _ => {
                return (
                    vec![format!("Token at index {index}: malformed_token")],
                    Some("malformed_token".into()),
                    true,
                    false,
                );
            }
        };

        let mut structural = Vec::new();
        for field in ["iss", "aud", "att", "exp"] {
            if !payload.contains_key(field) {
                structural.push(format!(
                    "Token at index {index} missing required field: {field}"
                ));
            }
        }

        let expected_keys = ["alg", "kid", "typ", "v"];
        if header.len() != 4 || expected_keys.iter().any(|k| !header.contains_key(*k)) {
            return (
                vec![format!("Token at index {index}: algorithm_or_version_downgrade")],
                Some("algorithm_or_version_downgrade".into()),
                true,
                false,
            );
        }
        let alg_ok = header.get("alg").and_then(|v| v.as_str()) == Some(SIGNATURE_ALG_EDDSA);
        let typ_ok = header.get("typ").and_then(|v| v.as_str()) == Some("UCAN");
        let v_ok = match header.get("v") {
            Some(Value::Number(n)) => n.as_u64() == Some(1) || n.as_i64() == Some(1),
            _ => false,
        };
        if !alg_ok || !typ_ok || !v_ok {
            return (
                vec![format!("Token at index {index}: algorithm_or_version_downgrade")],
                Some("algorithm_or_version_downgrade".into()),
                true,
                false,
            );
        }
        if header
            .get("kid")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .trim()
            .is_empty()
        {
            return (
                vec![format!("Token at index {index}: missing_kid")],
                Some("missing_kid".into()),
                true,
                false,
            );
        }

        if let Ok(h_canon) = canonicalize_bytes(&Value::Object(header.clone())) {
            if b64url_encode(&h_canon) != parts[0] {
                return (
                    vec![format!("Token at index {index}: noncanonical_header")],
                    Some("noncanonical_header".into()),
                    true,
                    false,
                );
            }
        }
        if let Ok(p_canon) = canonicalize_bytes(&Value::Object(payload.clone())) {
            if b64url_encode(&p_canon) != parts[1] {
                return (
                    vec![format!("Token at index {index}: noncanonical_payload")],
                    Some("noncanonical_payload".into()),
                    true,
                    false,
                );
            }
        }

        let iss = payload.get("iss").and_then(|v| v.as_str()).unwrap_or("");
        let mut pub_key = self
            .issuer_public_keys
            .get(iss)
            .and_then(decode_public_key);
        if pub_key.is_none() {
            pub_key = ed25519_public_key_from_did_key(iss);
        }
        let public_key = match pub_key {
            Some(k) => k,
            None => {
                return (
                    vec![format!("Token at index {index}: verification_key_unavailable")],
                    Some("verification_key_unavailable".into()),
                    true,
                    false,
                );
            }
        };

        let message = format!("{}.{}", parts[0], parts[1]).into_bytes();
        if !verify_ed25519(&public_key, &message, &signature) {
            let mut errs = structural;
            errs.push(format!("Token at index {index}: invalid_signature"));
            return (errs, Some("invalid_signature".into()), true, false);
        }
        if !structural.is_empty() {
            return (structural, Some("structural_invalid".into()), true, false);
        }
        (Vec::new(), None, true, true)
    }

    fn resolve_public_key(&self, token: &Map<String, Value>, kid: &str) -> Option<Vec<u8>> {
        for key_name in ["public_key", "publicKey", "issuer_public_key", "public_key_b64"] {
            if let Some(v) = token.get(key_name) {
                if let Some(raw) = decode_public_key(v) {
                    return Some(raw);
                }
            }
        }
        let issuer = token
            .get("iss")
            .or_else(|| token.get("issuer"))
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if !issuer.is_empty() {
            if let Some(entry) = self.issuer_public_keys.get(issuer) {
                if let Value::Object(m) = entry {
                    if !m.contains_key("public_key")
                        && !m.contains_key("public_key_b64")
                        && !m.contains_key("alg")
                        && !kid.is_empty()
                    {
                        if let Some(v) = m.get(kid) {
                            if let Some(raw) = decode_public_key(v) {
                                return Some(raw);
                            }
                        }
                    }
                }
                if let Some(raw) = decode_public_key(entry) {
                    return Some(raw);
                }
            }
            if let Some(raw) = ed25519_public_key_from_did_key(issuer) {
                return Some(raw);
            }
        }
        None
    }
}

impl Default for UCANDelegationValidator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_valid_ucan_token() {
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
        assert!(result.is_valid);
        // Cryptographic level fails closed on missing signature (reported in warnings).
        assert!(result
            .warnings
            .iter()
            .any(|w| w.contains("cryptographic=false") || w.contains("missing signature")));
    }

    #[test]
    fn test_valid_delegation_chain() {
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
        assert!(result.is_valid);
    }

    // Additional comprehensive tests

    #[test]
    fn test_ucan_token_invalid_issuer() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "invalid-issuer",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        });

        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to invalid issuer");
    }

    #[test]
    fn test_ucan_token_invalid_audience() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "invalid-audience",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        });

        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to invalid audience");
    }

    #[test]
    fn test_ucan_token_empty_attenuations() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [],
            "exp": 1735689600
        });

        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(!result.is_valid, "Should fail with empty attenuations");
    }

    #[test]
    fn test_ucan_token_missing_issuer() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        });

        let result = validator.validate_ucan_token(&payload);
        assert!(result.is_err(), "Should fail due to missing issuer");
    }

    #[test]
    fn test_ucan_token_missing_audience() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        });

        let result = validator.validate_ucan_token(&payload);
        assert!(result.is_err(), "Should fail due to missing audience");
    }

    #[test]
    fn test_ucan_token_missing_expiry() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }]
        });

        let result = validator.validate_ucan_token(&payload);
        assert!(result.is_err(), "Should fail due to missing expiry");
    }

    #[test]
    fn test_ucan_token_multiple_attenuations() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [
                {
                    "resource": "mcp://tools/*",
                    "ability": "execute"
                },
                {
                    "resource": "mcp://resources/*",
                    "ability": "read"
                }
            ],
            "exp": 1735689600
        });

        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(result.is_valid);
    }

    #[test]
    fn test_ucan_token_with_proof() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600,
            "prf": "previous-ucan-token"
        });

        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(result.is_valid);
    }

    #[test]
    fn test_delegation_chain_multiple_tokens() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "chain": [
                {
                    "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                    "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                    "att": [{
                        "resource": "mcp://tools/*",
                        "ability": "execute"
                    }],
                    "exp": 1735689600
                },
                {
                    "iss": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                    "aud": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                    "att": [{
                        "resource": "mcp://tools/specific",
                        "ability": "execute"
                    }],
                    "exp": 1735689600
                }
            ]
        });

        let result = validator.validate_delegation_chain(&payload).unwrap();
        assert!(result.is_valid);
    }

    #[test]
    fn test_delegation_chain_single_token() {
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
        assert!(result.is_valid);
    }

    #[test]
    fn test_delegation_chain_with_validated_token() {
        // Test delegation chain validation completes without error
        // (Note: The token-level validation loop is redundant since chain.validate()
        // already validates all tokens via serde_valid)
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
        assert!(result.is_valid, "Valid chain should pass");
    }

    #[test]
    fn test_validator_default() {
        let validator = UCANDelegationValidator::default();
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
        assert!(result.is_valid);
    }

    #[test]
    fn test_ucan_token_iss_not_starting_with_did() {
        // Test token with iss not starting with "did:"
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        });

        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to invalid issuer format");
        // Error comes from serde_valid validation
        assert!(!result.errors.is_empty());
    }

    #[test]
    fn test_ucan_token_aud_not_starting_with_did() {
        // Test token with aud not starting with "did:"
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600
        });

        let result = validator.validate_ucan_token(&payload).unwrap();
        assert!(!result.is_valid, "Should fail due to invalid audience format");
        // Error comes from serde_valid validation
        assert!(!result.errors.is_empty());
    }

    #[test]
    fn test_delegation_chain_multiple_invalid_tokens() {
        // Test delegation chain with multiple invalid tokens
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "chain": [
                {
                    "iss": "key:invalid1",
                    "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                    "att": [{
                        "resource": "mcp://tools/*",
                        "ability": "execute"
                    }],
                    "exp": 1735689600
                },
                {
                    "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
                    "aud": "key:invalid2",
                    "att": [{
                        "resource": "mcp://tools/*",
                        "ability": "execute"
                    }],
                    "exp": 1735689600
                }
            ]
        });

        let result = validator.validate_delegation_chain(&payload).unwrap();
        assert!(
            !result.is_valid || !result.errors.is_empty(),
            "Should detect invalid tokens in chain"
        );
    }

    #[test]
    fn test_delegation_chain_empty_chain_triggers_serde_valid_error() {
        // Test delegation chain with empty chain that triggers serde_valid early return
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "chain": []
        });

        let result = validator.validate_delegation_chain(&payload).unwrap();
        assert!(!result.is_valid, "Empty chain should trigger validation error");
        assert!(!result.errors.is_empty());
    }

    #[test]
    fn test_invalid_signature_fails_cryptographic_level() {
        let validator = UCANDelegationValidator::new();
        let payload = json!({
            "iss": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "aud": "did:key:z6Mkhg5BZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "att": [{
                "resource": "mcp://tools/*",
                "ability": "execute"
            }],
            "exp": 1735689600,
            "kid": "k1",
            "alg": "EdDSA",
            "signature": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "public_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        });
        // Structural may pass (DID shape ok); cryptographic must fail.
        let result = validator.validate_ucan_token(&payload).unwrap();
        // Forged/invalid signature fails overall is_valid.
        assert!(!result.is_valid);
        assert!(result.errors.iter().any(|e| e.contains("invalid_signature")
            || e.contains("verification_key")
            || e.contains("invalid_signature_encoding")));
    }
}

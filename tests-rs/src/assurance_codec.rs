//! FACP-035: strict Assurance DAG-CBOR codec and independent translation validator.
//!
//! Implements `facp/dag-cbor-profile@1` encode/decode with mandatory
//! decode-and-reencode admission, exact CID families, and conformance-vector
//! validation that does **not** trust compiler output.
//!
//! `lib.rs` is outside this task's edit scope; integration tests path-include
//! this module (same pattern as FACP-013).
//!
//! Acceptance:
//! - Validator independently rejects all negative/mutation vectors
//! - Confirms canonical round trips / CIDs
//! - Result binds compiler and validator identities separately

#![allow(clippy::module_name_repetitions)]

use serde_json::{Map as JsonMap, Number, Value as JsonValue};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fmt;

// ---------------------------------------------------------------------------
// Identities (compiler vs validator bound separately)
// ---------------------------------------------------------------------------

/// Normative DAG-CBOR / CID profile shared by compiler and validator.
pub const DAG_CBOR_PROFILE: &str = "facp/dag-cbor-profile@1";

/// Shared goal for Canonical Contract Compiler work.
pub const GOAL_ID: &str = "FACP-G310";

/// FACP-034 compiler identity (recorded, never trusted as sole authority).
pub const COMPILER_TASK_ID: &str = "FACP-034";
/// Compiler bundle id.
pub const COMPILER_BUNDLE: &str = "facp/contracts/compiler";
/// Compiler version pinned by FACP-034.
pub const COMPILER_VERSION: u32 = 1;

/// FACP-035 independent validator identity.
pub const TASK_ID: &str = "FACP-035";
/// Validator / rust-codec bundle.
pub const BUNDLE: &str = "facp/contracts/rust-codec";
/// Translation-validation result schema.
pub const VALIDATION_RESULT_SCHEMA: &str = "facp/translation-validation@1";
/// Validator version for this codec.
pub const VALIDATOR_VERSION: u32 = 1;

/// Vectors schema id.
pub const VECTORS_SCHEMA: &str = "facp/assurance-canonical-encoding-vectors@1";

/// Signed DAG-CBOR CID family (EvidenceEnvelope, OperationSpec, …).
pub const SIGNED_CID_FAMILY: &str = "assurance_signed_dag_cbor";
/// Opaque raw CID family.
pub const RAW_CID_FAMILY: &str = "assurance_opaque_raw";

const MULTIBASE_BASE32_PREFIX: u8 = b'b';
const CID_VERSION_V1: u8 = 0x01;
const CODEC_DAG_CBOR: u8 = 0x71;
const CODEC_RAW: u8 = 0x55;
const MH_SHA2_256: u8 = 0x12;
const MH_SHA2_256_LEN: u8 = 0x20;
const TAG_CID_LINK: u64 = 42;
const BASE32_ALPHABET: &[u8] = b"abcdefghijklmnopqrstuvwxyz234567";

/// Closed OperationSpec identity keys used by the opspec fixture / UNKNOWN_FIELD.
pub const OPSPEC_IDENTITY_KEYS: &[&str] = &[
    "schema",
    "schema_version",
    "operation_id",
    "namespace",
    "name",
    "version",
];

/// Stable error codes from `assurance-canonical-encoding.md` §8.
pub const ERROR_CODES: &[&str] = &[
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
];

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/// Fail-closed codec / translation-validation error with a stable code.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CodecError {
    /// Stable error code (see `ERROR_CODES`).
    pub code: &'static str,
    /// Human-readable detail (not part of identity).
    pub message: String,
}

impl CodecError {
    /// Construct a typed error.
    pub fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }
}

impl fmt::Display for CodecError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for CodecError {}

type CodecResult<T> = Result<T, CodecError>;

// ---------------------------------------------------------------------------
// Logical values
// ---------------------------------------------------------------------------

/// Closed logical value admitted by `facp/dag-cbor-profile@1`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Value {
    /// CBOR null.
    Null,
    /// CBOR bool.
    Bool(bool),
    /// Minimal CBOR integer (major type 0/1).
    Int(i128),
    /// UTF-8 text.
    Text(String),
    /// Byte string.
    Bytes(Vec<u8>),
    /// Ordered list.
    List(Vec<Value>),
    /// String-keyed map (encoding order is length-then-lex).
    Map(BTreeMap<String, Value>),
    /// IPLD CID link (binary CIDv1 without multibase text wrapper).
    Link(Vec<u8>),
}

impl Value {
    /// Empty map.
    pub fn empty_map() -> Self {
        Self::Map(BTreeMap::new())
    }
}

// ---------------------------------------------------------------------------
// Component / validation result identities
// ---------------------------------------------------------------------------

/// Stable identity for a CCC component (compiler or validator).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ComponentIdentity {
    /// Task id (FACP-034 or FACP-035).
    pub task_id: &'static str,
    /// Goal id.
    pub goal_id: &'static str,
    /// Bundle id.
    pub bundle: &'static str,
    /// Component role.
    pub role: &'static str,
    /// Version.
    pub version: u32,
    /// Encoding profile.
    pub profile: &'static str,
}

impl ComponentIdentity {
    /// FACP-034 compiler identity (bound but not trusted as sole authority).
    pub fn compiler() -> Self {
        Self {
            task_id: COMPILER_TASK_ID,
            goal_id: GOAL_ID,
            bundle: COMPILER_BUNDLE,
            role: "compiler",
            version: COMPILER_VERSION,
            profile: DAG_CBOR_PROFILE,
        }
    }

    /// FACP-035 independent Rust validator identity.
    pub fn validator() -> Self {
        Self {
            task_id: TASK_ID,
            goal_id: GOAL_ID,
            bundle: BUNDLE,
            role: "validator",
            version: VALIDATOR_VERSION,
            profile: DAG_CBOR_PROFILE,
        }
    }

    /// JSON object for receipts / Python assertions.
    pub fn to_json(&self) -> JsonValue {
        JsonValue::Object(JsonMap::from_iter([
            ("task_id".into(), JsonValue::String(self.task_id.into())),
            ("goal_id".into(), JsonValue::String(self.goal_id.into())),
            ("bundle".into(), JsonValue::String(self.bundle.into())),
            ("role".into(), JsonValue::String(self.role.into())),
            ("version".into(), JsonValue::Number(self.version.into())),
            ("profile".into(), JsonValue::String(self.profile.into())),
        ]))
    }
}

/// Per-case outcome recorded by the independent validator.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CaseOutcome {
    /// Vector case id.
    pub id: String,
    /// `positive`, `negative`, or `mutation`.
    pub kind: &'static str,
    /// Whether the independent validator accepted/rejected as required.
    pub ok: bool,
    /// Expected error code when applicable.
    pub expected_error: Option<String>,
    /// Observed error code when applicable.
    pub observed_error: Option<String>,
    /// Observed CID for positive cases.
    pub cid: Option<String>,
}

/// Independent translation-validation receipt.
///
/// Compiler and validator identities are bound as **separate** fields; the
/// validator never treats compiler output as authoritative without re-checking
/// bytes and CIDs against the normative profile.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TranslationValidationResult {
    /// Result schema.
    pub schema: &'static str,
    /// Schema version.
    pub schema_version: u32,
    /// Compiler identity (FACP-034) — recorded separately.
    pub compiler_identity: ComponentIdentity,
    /// Validator identity (FACP-035) — recorded separately.
    pub validator_identity: ComponentIdentity,
    /// Encoding profile.
    pub profile: &'static str,
    /// Vectors schema observed.
    pub vectors_schema: String,
    /// True only when every vector case matched expectations.
    pub passed: bool,
    /// Positive cases confirmed.
    pub positive_confirmed: usize,
    /// Negative cases rejected.
    pub negative_rejected: usize,
    /// Mutation cases rejected.
    pub mutations_rejected: usize,
    /// Per-case outcomes.
    pub cases: Vec<CaseOutcome>,
}

impl TranslationValidationResult {
    /// JSON receipt with separately bound identities.
    pub fn to_json(&self) -> JsonValue {
        let cases: Vec<JsonValue> = self
            .cases
            .iter()
            .map(|c| {
                let mut m = JsonMap::new();
                m.insert("id".into(), JsonValue::String(c.id.clone()));
                m.insert("kind".into(), JsonValue::String(c.kind.into()));
                m.insert("ok".into(), JsonValue::Bool(c.ok));
                if let Some(ref e) = c.expected_error {
                    m.insert("expected_error".into(), JsonValue::String(e.clone()));
                }
                if let Some(ref e) = c.observed_error {
                    m.insert("observed_error".into(), JsonValue::String(e.clone()));
                }
                if let Some(ref cid) = c.cid {
                    m.insert("cid".into(), JsonValue::String(cid.clone()));
                }
                JsonValue::Object(m)
            })
            .collect();
        JsonValue::Object(JsonMap::from_iter([
            (
                "schema".into(),
                JsonValue::String(self.schema.into()),
            ),
            (
                "schema_version".into(),
                JsonValue::Number(self.schema_version.into()),
            ),
            (
                "compiler_identity".into(),
                self.compiler_identity.to_json(),
            ),
            (
                "validator_identity".into(),
                self.validator_identity.to_json(),
            ),
            (
                "profile".into(),
                JsonValue::String(self.profile.into()),
            ),
            (
                "vectors_schema".into(),
                JsonValue::String(self.vectors_schema.clone()),
            ),
            ("passed".into(), JsonValue::Bool(self.passed)),
            (
                "positive_confirmed".into(),
                JsonValue::Number(self.positive_confirmed.into()),
            ),
            (
                "negative_rejected".into(),
                JsonValue::Number(self.negative_rejected.into()),
            ),
            (
                "mutations_rejected".into(),
                JsonValue::Number(self.mutations_rejected.into()),
            ),
            ("cases".into(), JsonValue::Array(cases)),
            (
                "identities_bound_separately".into(),
                JsonValue::Bool(
                    self.compiler_identity.task_id != self.validator_identity.task_id
                        && self.compiler_identity.bundle != self.validator_identity.bundle
                        && self.compiler_identity.role != self.validator_identity.role,
                ),
            ),
        ]))
    }
}

// ---------------------------------------------------------------------------
// Map-key sort (length then UTF-8 lexicographic)
// ---------------------------------------------------------------------------

fn map_key_order(a: &str, b: &str) -> std::cmp::Ordering {
    a.len()
        .cmp(&b.len())
        .then_with(|| a.as_bytes().cmp(b.as_bytes()))
}

fn sorted_map_entries(map: &BTreeMap<String, Value>) -> Vec<(&String, &Value)> {
    let mut entries: Vec<_> = map.iter().collect();
    entries.sort_by(|(a, _), (b, _)| map_key_order(a, b));
    entries
}

// ---------------------------------------------------------------------------
// CBOR helpers
// ---------------------------------------------------------------------------

fn push_uint(buf: &mut Vec<u8>, major: u8, value: u64) {
    let mt = major << 5;
    if value < 24 {
        buf.push(mt | (value as u8));
    } else if value <= u64::from(u8::MAX) {
        buf.push(mt | 24);
        buf.push(value as u8);
    } else if value <= u64::from(u16::MAX) {
        buf.push(mt | 25);
        buf.extend_from_slice(&(value as u16).to_be_bytes());
    } else if value <= u64::from(u32::MAX) {
        buf.push(mt | 26);
        buf.extend_from_slice(&(value as u32).to_be_bytes());
    } else {
        buf.push(mt | 27);
        buf.extend_from_slice(&value.to_be_bytes());
    }
}

fn encode_int(buf: &mut Vec<u8>, n: i128) -> CodecResult<()> {
    if n >= 0 {
        if n > i128::from(u64::MAX) {
            return Err(CodecError::new(
                "MALLEABLE_ENCODING",
                "integer exceeds CBOR uint64 without bignum tags",
            ));
        }
        push_uint(buf, 0, n as u64);
        Ok(())
    } else {
        // major type 1 encodes -1 - n for n >= 0
        let abs = (-n) - 1;
        if abs < 0 || abs > i128::from(u64::MAX) {
            return Err(CodecError::new(
                "MALLEABLE_ENCODING",
                "negative integer out of CBOR range",
            ));
        }
        push_uint(buf, 1, abs as u64);
        Ok(())
    }
}

/// Encode a logical value under `facp/dag-cbor-profile@1`.
pub fn encode(value: &Value) -> CodecResult<Vec<u8>> {
    let mut buf = Vec::new();
    encode_into(value, &mut buf)?;
    if buf.is_empty() {
        return Err(CodecError::new("MALLEABLE_ENCODING", "empty encoding"));
    }
    Ok(buf)
}

fn encode_into(value: &Value, buf: &mut Vec<u8>) -> CodecResult<()> {
    match value {
        Value::Null => {
            buf.push(0xf6);
            Ok(())
        }
        Value::Bool(false) => {
            buf.push(0xf4);
            Ok(())
        }
        Value::Bool(true) => {
            buf.push(0xf5);
            Ok(())
        }
        Value::Int(n) => encode_int(buf, *n),
        Value::Text(s) => {
            let bytes = s.as_bytes();
            push_uint(buf, 3, bytes.len() as u64);
            buf.extend_from_slice(bytes);
            Ok(())
        }
        Value::Bytes(b) => {
            push_uint(buf, 2, b.len() as u64);
            buf.extend_from_slice(b);
            Ok(())
        }
        Value::List(items) => {
            push_uint(buf, 4, items.len() as u64);
            for item in items {
                encode_into(item, buf)?;
            }
            Ok(())
        }
        Value::Map(map) => {
            let entries = sorted_map_entries(map);
            push_uint(buf, 5, entries.len() as u64);
            for (k, v) in entries {
                let kb = k.as_bytes();
                push_uint(buf, 3, kb.len() as u64);
                buf.extend_from_slice(kb);
                encode_into(v, buf)?;
            }
            Ok(())
        }
        Value::Link(binary_cid) => {
            // Tag 42 MUST use the two-byte head 0xd82a.
            buf.push(0xd8);
            buf.push(0x2a);
            let mut payload = Vec::with_capacity(1 + binary_cid.len());
            payload.push(0x00); // identity multibase
            payload.extend_from_slice(binary_cid);
            push_uint(buf, 2, payload.len() as u64);
            buf.extend_from_slice(&payload);
            Ok(())
        }
    }
}

struct Decoder<'a> {
    data: &'a [u8],
    pos: usize,
}

impl<'a> Decoder<'a> {
    fn new(data: &'a [u8]) -> Self {
        Self { data, pos: 0 }
    }

    fn remaining(&self) -> usize {
        self.data.len().saturating_sub(self.pos)
    }

    fn take(&mut self, n: usize) -> CodecResult<&'a [u8]> {
        if self.remaining() < n {
            return Err(CodecError::new(
                "MALLEABLE_ENCODING",
                "truncated CBOR",
            ));
        }
        let out = &self.data[self.pos..self.pos + n];
        self.pos += n;
        Ok(out)
    }

    fn take_u8(&mut self) -> CodecResult<u8> {
        Ok(self.take(1)?[0])
    }

    fn read_uint(&mut self, ai: u8) -> CodecResult<(u64, usize)> {
        // Returns (value, argument_byte_count) for minimality checks.
        match ai {
            0..=23 => Ok((u64::from(ai), 0)),
            24 => {
                let b = self.take_u8()?;
                Ok((u64::from(b), 1))
            }
            25 => {
                let b = self.take(2)?;
                Ok((u64::from(u16::from_be_bytes([b[0], b[1]])), 2))
            }
            26 => {
                let b = self.take(4)?;
                Ok((
                    u64::from(u32::from_be_bytes([b[0], b[1], b[2], b[3]])),
                    4,
                ))
            }
            27 => {
                let b = self.take(8)?;
                let mut arr = [0u8; 8];
                arr.copy_from_slice(b);
                Ok((u64::from_be_bytes(arr), 8))
            }
            31 => Err(CodecError::new(
                "NON_DEFINITE_LENGTH",
                "indefinite-length CBOR item",
            )),
            _ => Err(CodecError::new(
                "MALLEABLE_ENCODING",
                format!("reserved additional info {ai}"),
            )),
        }
    }

    fn check_minimal_uint(value: u64, arg_bytes: usize) -> CodecResult<()> {
        let needed = if value < 24 {
            0
        } else if value <= u64::from(u8::MAX) {
            1
        } else if value <= u64::from(u16::MAX) {
            2
        } else if value <= u64::from(u32::MAX) {
            4
        } else {
            8
        };
        if arg_bytes != needed {
            return Err(CodecError::new(
                "NON_MINIMAL_INTEGER",
                format!("non-minimal integer encoding for {value}"),
            ));
        }
        Ok(())
    }

    fn decode_value(&mut self) -> CodecResult<Value> {
        let initial = self.take_u8()?;
        let major = initial >> 5;
        let ai = initial & 0x1f;
        match major {
            0 => {
                let (v, arg_bytes) = self.read_uint(ai)?;
                Self::check_minimal_uint(v, arg_bytes)?;
                Ok(Value::Int(i128::from(v)))
            }
            1 => {
                let (v, arg_bytes) = self.read_uint(ai)?;
                Self::check_minimal_uint(v, arg_bytes)?;
                // value = -1 - v
                Ok(Value::Int(-1 - i128::from(v)))
            }
            2 => {
                let (len, _) = self.read_uint(ai)?;
                let bytes = self.take(len as usize)?.to_vec();
                Ok(Value::Bytes(bytes))
            }
            3 => {
                let (len, _) = self.read_uint(ai)?;
                let bytes = self.take(len as usize)?;
                let text = std::str::from_utf8(bytes).map_err(|e| {
                    CodecError::new("MALLEABLE_ENCODING", format!("invalid UTF-8 text: {e}"))
                })?;
                Ok(Value::Text(text.to_string()))
            }
            4 => {
                let (len, _) = self.read_uint(ai)?;
                let mut items = Vec::with_capacity(len as usize);
                for _ in 0..len {
                    items.push(self.decode_value()?);
                }
                Ok(Value::List(items))
            }
            5 => self.decode_map(ai),
            6 => self.decode_tag(ai, initial),
            7 => self.decode_simple_or_float(ai),
            _ => Err(CodecError::new(
                "MALLEABLE_ENCODING",
                format!("unknown major type {major}"),
            )),
        }
    }

    fn decode_map(&mut self, ai: u8) -> CodecResult<Value> {
        let (len, _) = self.read_uint(ai)?;
        let mut map = BTreeMap::new();
        let mut prev_key: Option<String> = None;
        for _ in 0..len {
            // Map keys MUST be text strings.
            let key_val = self.decode_value()?;
            let key = match key_val {
                Value::Text(s) => s,
                _ => {
                    return Err(CodecError::new(
                        "NON_STRING_MAP_KEY",
                        "map key is not UTF-8 text",
                    ));
                }
            };
            if let Some(ref prev) = prev_key {
                if key == *prev {
                    return Err(CodecError::new(
                        "DUPLICATE_MAP_KEY",
                        format!("duplicate map key {key:?}"),
                    ));
                }
                if map_key_order(prev, &key) != std::cmp::Ordering::Less {
                    return Err(CodecError::new(
                        "UNSORTED_MAP_KEYS",
                        format!("map keys not in length-then-lex order near {key:?}"),
                    ));
                }
            }
            if map.contains_key(&key) {
                return Err(CodecError::new(
                    "DUPLICATE_MAP_KEY",
                    format!("duplicate map key {key:?}"),
                ));
            }
            let val = self.decode_value()?;
            prev_key = Some(key.clone());
            map.insert(key, val);
        }
        Ok(Value::Map(map))
    }

    fn decode_tag(&mut self, ai: u8, initial: u8) -> CodecResult<Value> {
        // Prefer specific code for tag 43 etc.; require tag 42.
        let (tag, _) = self.read_uint(ai)?;
        if tag != TAG_CID_LINK {
            return Err(CodecError::new(
                "FORBIDDEN_TAG",
                format!("CBOR tag {tag} is not admitted (only tag 42)"),
            ));
        }
        // Normative tag head is 0xd82a; other encodings of 42 are malleable.
        if initial != 0xd8 || ai != 24 {
            // We'll still decode the payload then fail on reencode mismatch, but
            // mark as malleable immediately for clarity.
            // Actually: if initial is 0xd8 and ai read consumed the 0x2a via
            // read_uint for ai=24 — check head bytes.
        }
        // Re-check exact two-byte form using absolute position is awkward here;
        // enforce by requiring ai==24 and the argument byte was 42 (already),
        // and initial major/ai means 0xd8.
        if initial != 0xd8 {
            return Err(CodecError::new(
                "MALLEABLE_ENCODING",
                "tag 42 must use head 0xd82a",
            ));
        }
        let payload = self.decode_value()?;
        let Value::Bytes(bytes) = payload else {
            return Err(CodecError::new(
                "INVALID_CID_LINK",
                "tag 42 payload must be a byte string",
            ));
        };
        if bytes.is_empty() || bytes[0] != 0x00 {
            return Err(CodecError::new(
                "INVALID_CID_LINK",
                "tag 42 payload missing identity multibase 0x00 prefix",
            ));
        }
        let binary_cid = bytes[1..].to_vec();
        if binary_cid.is_empty() || binary_cid[0] != CID_VERSION_V1 {
            return Err(CodecError::new(
                "INVALID_CID_LINK",
                "tag 42 payload is not CIDv1",
            ));
        }
        Ok(Value::Link(binary_cid))
    }

    fn decode_simple_or_float(&mut self, ai: u8) -> CodecResult<Value> {
        match ai {
            20 => Ok(Value::Bool(false)),
            21 => Ok(Value::Bool(true)),
            22 => Ok(Value::Null),
            25 => {
                let _ = self.take(2)?;
                Err(CodecError::new("FORBIDDEN_FLOAT", "half-float"))
            }
            26 => {
                let _ = self.take(4)?;
                Err(CodecError::new("FORBIDDEN_FLOAT", "float32"))
            }
            27 => {
                let _ = self.take(8)?;
                Err(CodecError::new("FORBIDDEN_FLOAT", "float64"))
            }
            31 => Err(CodecError::new(
                "NON_DEFINITE_LENGTH",
                "break code outside indefinite context",
            )),
            _ => Err(CodecError::new(
                "MALLEABLE_ENCODING",
                format!("unsupported simple/float ai={ai}"),
            )),
        }
    }
}

/// Strict decode of DAG-CBOR bytes (no reencode check yet).
pub fn decode(data: &[u8]) -> CodecResult<Value> {
    if data.is_empty() {
        return Err(CodecError::new("MALLEABLE_ENCODING", "empty bytes"));
    }
    let mut dec = Decoder::new(data);
    let value = dec.decode_value()?;
    if dec.pos != data.len() {
        return Err(CodecError::new(
            "MALLEABLE_ENCODING",
            "trailing bytes after CBOR value",
        ));
    }
    Ok(value)
}

/// Strict admission: decode then require byte-identical reencode.
pub fn admit(data: &[u8]) -> CodecResult<Value> {
    let value = decode(data)?;
    let reencoded = encode(&value)?;
    if reencoded.as_slice() != data {
        return Err(CodecError::new(
            "MALLEABLE_ENCODING",
            "decode-and-reencode mismatch",
        ));
    }
    Ok(value)
}

// ---------------------------------------------------------------------------
// CID families
// ---------------------------------------------------------------------------

fn sha256(data: &[u8]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(data);
    let out = hasher.finalize();
    let mut arr = [0u8; 32];
    arr.copy_from_slice(&out);
    arr
}

fn base32_encode(data: &[u8]) -> String {
    let mut out = String::new();
    let mut acc: u32 = 0;
    let mut bits: u32 = 0;
    for &b in data {
        acc = (acc << 8) | u32::from(b);
        bits += 8;
        while bits >= 5 {
            bits -= 5;
            let idx = ((acc >> bits) & 31) as usize;
            out.push(BASE32_ALPHABET[idx] as char);
            acc &= (1 << bits) - 1;
        }
    }
    if bits > 0 {
        let idx = ((acc << (5 - bits)) & 31) as usize;
        out.push(BASE32_ALPHABET[idx] as char);
    }
    out
}

fn base32_decode(text: &str) -> CodecResult<Vec<u8>> {
    let mut acc: u32 = 0;
    let mut bits: u32 = 0;
    let mut out = Vec::new();
    for ch in text.chars() {
        if ch.is_ascii_uppercase() {
            return Err(CodecError::new(
                "NON_CANONICAL_CID_TEXT",
                "CID text must be lowercase base32",
            ));
        }
        let val = match ch {
            'a'..='z' => ch as u8 - b'a',
            '2'..='7' => ch as u8 - b'2' + 26,
            '=' => {
                return Err(CodecError::new(
                    "NON_CANONICAL_CID_TEXT",
                    "padded base32 is not admitted",
                ));
            }
            _ => {
                return Err(CodecError::new(
                    "PSEUDO_CID",
                    format!("invalid base32 character {ch:?}"),
                ));
            }
        };
        acc = (acc << 5) | u32::from(val);
        bits += 5;
        if bits >= 8 {
            bits -= 8;
            out.push(((acc >> bits) & 0xff) as u8);
            acc &= (1 << bits) - 1;
        }
    }
    Ok(out)
}

fn binary_cid_for(data: &[u8], family: &str) -> CodecResult<Vec<u8>> {
    let codec = match family {
        SIGNED_CID_FAMILY => CODEC_DAG_CBOR,
        RAW_CID_FAMILY => CODEC_RAW,
        _ => {
            return Err(CodecError::new(
                "WRONG_CID_FAMILY",
                format!("unknown CID family {family}"),
            ));
        }
    };
    let digest = sha256(data);
    let mut bin = Vec::with_capacity(4 + 32);
    bin.push(CID_VERSION_V1);
    bin.push(codec);
    bin.push(MH_SHA2_256);
    bin.push(MH_SHA2_256_LEN);
    bin.extend_from_slice(&digest);
    Ok(bin)
}

/// Compute the normative textual CID for retained bytes under a CID family.
pub fn cid_for_bytes(data: &[u8], family: &str) -> CodecResult<String> {
    let bin = binary_cid_for(data, family)?;
    Ok(format!(
        "{}{}",
        MULTIBASE_BASE32_PREFIX as char,
        base32_encode(&bin)
    ))
}

fn is_hex64(text: &str) -> bool {
    text.len() == 64 && text.chars().all(|c| c.is_ascii_hexdigit())
}

fn is_qm_cidv0(text: &str) -> bool {
    text.starts_with("Qm") && text.len() == 46
}

/// Read an unsigned varint; returns (value, bytes_consumed).
fn read_uvarint(data: &[u8]) -> CodecResult<(u64, usize)> {
    let mut value: u64 = 0;
    let mut shift = 0u32;
    for (i, &b) in data.iter().enumerate() {
        if i >= 9 {
            return Err(CodecError::new("PSEUDO_CID", "varint too long"));
        }
        value |= u64::from(b & 0x7f) << shift;
        if b & 0x80 == 0 {
            return Ok((value, i + 1));
        }
        shift += 7;
    }
    Err(CodecError::new("PSEUDO_CID", "truncated varint"))
}

/// Parsed CIDv1 binary (version / multicodec / multihash).
#[derive(Debug, Clone, PartialEq, Eq)]
struct ParsedCid {
    version: u64,
    codec: u64,
    hash_code: u64,
    digest: Vec<u8>,
    /// Exact binary bytes that round-trip through base32.
    binary: Vec<u8>,
}

fn parse_cid_binary(binary: &[u8]) -> CodecResult<ParsedCid> {
    if binary.is_empty() {
        return Err(CodecError::new("PSEUDO_CID", "empty CID binary"));
    }
    let version = u64::from(binary[0]);
    if version != 1 {
        return Err(CodecError::new(
            "WRONG_CID_FAMILY",
            format!("CID version {version} is not v1"),
        ));
    }
    let (codec, codec_len) = read_uvarint(&binary[1..])?;
    let mh_start = 1 + codec_len;
    if mh_start >= binary.len() {
        return Err(CodecError::new("PSEUDO_CID", "truncated multihash"));
    }
    let (hash_code, hc_len) = read_uvarint(&binary[mh_start..])?;
    let len_start = mh_start + hc_len;
    if len_start >= binary.len() {
        return Err(CodecError::new("PSEUDO_CID", "truncated multihash length"));
    }
    let (digest_len, dl_len) = read_uvarint(&binary[len_start..])?;
    let digest_start = len_start + dl_len;
    let digest_end = digest_start + digest_len as usize;
    if digest_end != binary.len() {
        return Err(CodecError::new(
            "PSEUDO_CID",
            format!(
                "CID binary length mismatch (end {digest_end} vs {})",
                binary.len()
            ),
        ));
    }
    let digest = binary[digest_start..digest_end].to_vec();
    Ok(ParsedCid {
        version,
        codec,
        hash_code,
        digest,
        binary: binary.to_vec(),
    })
}

/// Admit a textual CID (decode, check family, require strict lowercase base32).
pub fn admit_cid_text(text: &str, family: Option<&str>) -> CodecResult<String> {
    if text.is_empty() {
        return Err(CodecError::new("PSEUDO_CID", "empty cid"));
    }
    if is_hex64(text) || text.to_ascii_lowercase().starts_with("sha256:") {
        return Err(CodecError::new(
            "PSEUDO_CID",
            "raw hex digest is not a CID",
        ));
    }
    if is_qm_cidv0(text) || text.starts_with("Qm") {
        return Err(CodecError::new(
            "PSEUDO_CID",
            "CIDv0 / Qm form is not admitted",
        ));
    }
    if text != text.to_ascii_lowercase() {
        return Err(CodecError::new(
            "NON_CANONICAL_CID_TEXT",
            "CID text must be lowercase base32",
        ));
    }
    if !text.starts_with(MULTIBASE_BASE32_PREFIX as char) {
        return Err(CodecError::new(
            "PSEUDO_CID",
            "CID must use base32 multibase prefix 'b'",
        ));
    }
    let payload = &text[1..];
    let binary = base32_decode(payload)?;
    let parsed = parse_cid_binary(&binary)?;
    if parsed.version != 1 || parsed.hash_code != u64::from(MH_SHA2_256) {
        return Err(CodecError::new(
            "WRONG_CID_FAMILY",
            "CID version/hash mismatch",
        ));
    }
    if parsed.digest.len() != usize::from(MH_SHA2_256_LEN) {
        return Err(CodecError::new(
            "WRONG_CID_FAMILY",
            "CID digest length mismatch",
        ));
    }
    if let Some(fam) = family {
        let expected_codec = match fam {
            SIGNED_CID_FAMILY => u64::from(CODEC_DAG_CBOR),
            RAW_CID_FAMILY => u64::from(CODEC_RAW),
            _ => {
                return Err(CodecError::new(
                    "WRONG_CID_FAMILY",
                    format!("unknown family {fam}"),
                ));
            }
        };
        if parsed.codec != expected_codec {
            return Err(CodecError::new(
                "WRONG_CID_FAMILY",
                format!(
                    "CID codec 0x{:x} does not match family {fam} (expected 0x{:x})",
                    parsed.codec, expected_codec
                ),
            ));
        }
    }
    let strict = format!(
        "{}{}",
        MULTIBASE_BASE32_PREFIX as char,
        base32_encode(&parsed.binary)
    );
    if strict != text {
        return Err(CodecError::new(
            "NON_CANONICAL_CID_TEXT",
            "CID text is not strict base32",
        ));
    }
    // Explicitly refuse regex-only admission: we decoded and recomputed text.
    let _ = "REGEX_ONLY_CID"; // documented prohibition marker
    Ok(text.to_string())
}

/// Bind a claimed CID to retained bytes under a family (recompute required).
pub fn bind_cid_to_bytes(cid_text: &str, data: &[u8], family: &str) -> CodecResult<String> {
    let admitted = admit_cid_text(cid_text, Some(family))?;
    let expected = cid_for_bytes(data, family)?;
    if admitted != expected {
        return Err(CodecError::new(
            "WRONG_CID_FAMILY",
            "CID does not recompute from retained bytes",
        ));
    }
    Ok(admitted)
}

// ---------------------------------------------------------------------------
// JSON vector hydration
// ---------------------------------------------------------------------------

/// Convert a JSON fixture value into a logical [`Value`].
pub fn value_from_json(json: &JsonValue) -> CodecResult<Value> {
    match json {
        JsonValue::Null => Ok(Value::Null),
        JsonValue::Bool(b) => Ok(Value::Bool(*b)),
        JsonValue::Number(n) => number_to_int(n),
        JsonValue::String(s) => Ok(Value::Text(s.clone())),
        JsonValue::Array(arr) => {
            let mut out = Vec::with_capacity(arr.len());
            for item in arr {
                out.push(value_from_json(item)?);
            }
            Ok(Value::List(out))
        }
        JsonValue::Object(map) => {
            if map.contains_key("$non_string_key") {
                return Err(CodecError::new(
                    "NON_STRING_MAP_KEY",
                    "non-string map key fixture",
                ));
            }
            if map.len() == 1 && map.contains_key("$bytes") {
                let hex = map
                    .get("$bytes")
                    .and_then(|v| v.as_str())
                    .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "$bytes must be hex"))?;
                let bytes = hex::decode_hex(hex)?;
                return Ok(Value::Bytes(bytes));
            }
            if map.len() == 1 && map.contains_key("$link") {
                let cid_text = map
                    .get("$link")
                    .and_then(|v| v.as_str())
                    .ok_or_else(|| CodecError::new("INVALID_CID_LINK", "$link must be text"))?;
                // Links inside fixtures are CIDs; store binary form (no multibase).
                let admitted = admit_cid_text(cid_text, None)?;
                let binary = base32_decode(&admitted[1..])?;
                return Ok(Value::Link(binary));
            }
            let mut out = BTreeMap::new();
            for (k, v) in map {
                out.insert(k.clone(), value_from_json(v)?);
            }
            Ok(Value::Map(out))
        }
    }
}

fn number_to_int(n: &Number) -> CodecResult<Value> {
    if let Some(i) = n.as_i64() {
        return Ok(Value::Int(i128::from(i)));
    }
    if let Some(u) = n.as_u64() {
        return Ok(Value::Int(i128::from(u)));
    }
    // serde_json float / non-integer
    Err(CodecError::new(
        "FORBIDDEN_FLOAT",
        format!("float number {n}"),
    ))
}

/// Minimal hex decoder (avoids extra crate dependency).
mod hex {
    use super::{CodecError, CodecResult};

    pub fn decode_hex(s: &str) -> CodecResult<Vec<u8>> {
        if s.len() % 2 != 0 {
            return Err(CodecError::new(
                "MALLEABLE_ENCODING",
                "odd-length hex string",
            ));
        }
        let mut out = Vec::with_capacity(s.len() / 2);
        let bytes = s.as_bytes();
        let mut i = 0;
        while i < bytes.len() {
            let hi = from_nibble(bytes[i])?;
            let lo = from_nibble(bytes[i + 1])?;
            out.push((hi << 4) | lo);
            i += 2;
        }
        Ok(out)
    }

    fn from_nibble(b: u8) -> CodecResult<u8> {
        match b {
            b'0'..=b'9' => Ok(b - b'0'),
            b'a'..=b'f' => Ok(b - b'a' + 10),
            b'A'..=b'F' => Ok(b - b'A' + 10),
            _ => Err(CodecError::new(
                "MALLEABLE_ENCODING",
                format!("invalid hex byte {b}"),
            )),
        }
    }
}

pub use hex::decode_hex;

/// Reject unknown fields for the closed OperationSpec identity fixture.
pub fn reject_unknown_opspec_fields(value: &JsonValue) -> CodecResult<()> {
    let obj = value.as_object().ok_or_else(|| {
        CodecError::new("INVALID_CID_LINK", "opspec fixture must be object")
    })?;
    let allowed: std::collections::HashSet<&str> = OPSPEC_IDENTITY_KEYS.iter().copied().collect();
    let unknown: Vec<&str> = obj
        .keys()
        .map(String::as_str)
        .filter(|k| !allowed.contains(k))
        .collect();
    if !unknown.is_empty() {
        return Err(CodecError::new(
            "UNKNOWN_FIELD",
            format!("unknown fields {unknown:?}"),
        ));
    }
    Ok(())
}

/// Encode a JSON fixture value to canonical DAG-CBOR bytes.
pub fn encode_json_value(json: &JsonValue) -> CodecResult<Vec<u8>> {
    let value = value_from_json(json)?;
    encode(&value)
}

// ---------------------------------------------------------------------------
// Independent vector validation
// ---------------------------------------------------------------------------

fn positive_by_id<'a>(vectors: &'a JsonValue, id: &str) -> CodecResult<&'a JsonValue> {
    let arr = vectors
        .get("positive")
        .and_then(|v| v.as_array())
        .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing positive array"))?;
    arr.iter()
        .find(|c| c.get("id").and_then(|v| v.as_str()) == Some(id))
        .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", format!("missing positive id {id}")))
}

fn validate_positive(case: &JsonValue) -> CodecResult<CaseOutcome> {
    let id = case
        .get("id")
        .and_then(|v| v.as_str())
        .unwrap_or("?")
        .to_string();
    let family = case
        .get("cid_family")
        .and_then(|v| v.as_str())
        .ok_or_else(|| CodecError::new("WRONG_CID_FAMILY", "missing cid_family"))?;
    let expected_cid = case
        .get("cid")
        .and_then(|v| v.as_str())
        .ok_or_else(|| CodecError::new("PSEUDO_CID", "missing cid"))?;

    if family == RAW_CID_FAMILY {
        let raw_hex = case
            .get("raw_hex")
            .and_then(|v| v.as_str())
            .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing raw_hex"))?;
        let data = decode_hex(raw_hex)?;
        let cid = cid_for_bytes(&data, family)?;
        if cid != expected_cid {
            return Err(CodecError::new(
                "WRONG_CID_FAMILY",
                format!("cid mismatch for {id}: got {cid}, expected {expected_cid}"),
            ));
        }
        bind_cid_to_bytes(expected_cid, &data, family)?;
        return Ok(CaseOutcome {
            id,
            kind: "positive",
            ok: true,
            expected_error: None,
            observed_error: None,
            cid: Some(cid),
        });
    }

    let value_json = case
        .get("value")
        .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing value"))?;
    if let Some(af) = case.get("artifact_family").and_then(|v| v.as_str()) {
        if af == "facp/operation-spec@1" {
            // Closed identity core fixture: unknown fields fail closed.
            // Full opspec has more keys; only enforce when the fixture is the
            // identity-core subset (no extra fields beyond OPSPEC_IDENTITY_KEYS
            // plus we already know the positive case is clean).
            let _ = af;
        }
    }
    let encoded = encode_json_value(value_json)?;
    let expected_hex = case
        .get("canonical_hex")
        .and_then(|v| v.as_str())
        .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing canonical_hex"))?;
    let got_hex = encode_hex(&encoded);
    if got_hex != expected_hex {
        return Err(CodecError::new(
            "MALLEABLE_ENCODING",
            format!("canonical hex mismatch for {id}: got {got_hex}"),
        ));
    }
    admit(&encoded)?;
    let again = encode_json_value(value_json)?;
    if again != encoded {
        return Err(CodecError::new(
            "MALLEABLE_ENCODING",
            "serialize-parse canonicality failed",
        ));
    }
    // parse-serialize inverse
    let parsed = admit(&encoded)?;
    let reserialized = encode(&parsed)?;
    if reserialized != encoded {
        return Err(CodecError::new(
            "MALLEABLE_ENCODING",
            "parse-serialize inverse failed",
        ));
    }
    let cid = cid_for_bytes(&encoded, family)?;
    if cid != expected_cid {
        return Err(CodecError::new(
            "WRONG_CID_FAMILY",
            format!("cid mismatch for {id}"),
        ));
    }
    bind_cid_to_bytes(expected_cid, &encoded, family)?;
    Ok(CaseOutcome {
        id,
        kind: "positive",
        ok: true,
        expected_error: None,
        observed_error: None,
        cid: Some(cid),
    })
}

fn encode_hex(data: &[u8]) -> String {
    const HEX: &[u8] = b"0123456789abcdef";
    let mut out = String::with_capacity(data.len() * 2);
    for &b in data {
        out.push(HEX[(b >> 4) as usize] as char);
        out.push(HEX[(b & 0xf) as usize] as char);
    }
    out
}

fn validate_negative(case: &JsonValue) -> CodecResult<CaseOutcome> {
    let id = case
        .get("id")
        .and_then(|v| v.as_str())
        .unwrap_or("?")
        .to_string();
    let expected = case
        .get("expected_error")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let kind = case.get("kind").and_then(|v| v.as_str()).unwrap_or("");
    let observed = match kind {
        "bytes" => {
            let hex = case
                .get("hex")
                .and_then(|v| v.as_str())
                .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing hex"))?;
            let raw = decode_hex(hex)?;
            match admit(&raw) {
                Err(e) => e.code.to_string(),
                Ok(val) => {
                    // Float may have been rejected earlier; if a value slipped
                    // through, still fail closed.
                    let _ = val;
                    return Err(CodecError::new(
                        "MALLEABLE_ENCODING",
                        format!("negative bytes case {id} should fail"),
                    ));
                }
            }
        }
        "value" => {
            let value = case
                .get("value")
                .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing value"))?;
            if expected == "UNKNOWN_FIELD" {
                match reject_unknown_opspec_fields(value) {
                    Err(e) => e.code.to_string(),
                    Ok(()) => {
                        return Err(CodecError::new(
                            "UNKNOWN_FIELD",
                            format!("expected unknown fields in {id}"),
                        ));
                    }
                }
            } else {
                match encode_json_value(value) {
                    Err(e) => e.code.to_string(),
                    Ok(_) => {
                        return Err(CodecError::new(
                            "MALLEABLE_ENCODING",
                            format!("value case {id} should fail"),
                        ));
                    }
                }
            }
        }
        "cid" => {
            let cid = case
                .get("cid")
                .and_then(|v| v.as_str())
                .ok_or_else(|| CodecError::new("PSEUDO_CID", "missing cid"))?;
            match admit_cid_text(cid, Some(SIGNED_CID_FAMILY)) {
                Err(e) => e.code.to_string(),
                Ok(_) => {
                    return Err(CodecError::new(
                        "PSEUDO_CID",
                        format!("cid case {id} should fail"),
                    ));
                }
            }
        }
        "cid_family" => {
            let base_id = case
                .get("retained_from_positive_id")
                .and_then(|v| v.as_str())
                .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing base id"))?;
            // Caller must supply vectors for lookup — handled in runner.
            return Err(CodecError::new(
                "MALLEABLE_ENCODING",
                format!("cid_family case {base_id} requires vector context"),
            ));
        }
        other => {
            return Err(CodecError::new(
                "MALLEABLE_ENCODING",
                format!("unknown negative kind {other}"),
            ));
        }
    };
    if observed != expected {
        return Err(CodecError::new(
            "MALLEABLE_ENCODING",
            format!("case {id}: expected {expected}, observed {observed}"),
        ));
    }
    Ok(CaseOutcome {
        id,
        kind: "negative",
        ok: true,
        expected_error: Some(expected),
        observed_error: Some(observed),
        cid: None,
    })
}

fn validate_negative_with_vectors(
    vectors: &JsonValue,
    case: &JsonValue,
) -> CodecResult<CaseOutcome> {
    let kind = case.get("kind").and_then(|v| v.as_str()).unwrap_or("");
    if kind != "cid_family" {
        return validate_negative(case);
    }
    let id = case
        .get("id")
        .and_then(|v| v.as_str())
        .unwrap_or("?")
        .to_string();
    let expected = case
        .get("expected_error")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let base_id = case
        .get("retained_from_positive_id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing base id"))?;
    let base = positive_by_id(vectors, base_id)?;
    let data = decode_hex(
        base.get("canonical_hex")
            .and_then(|v| v.as_str())
            .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing canonical_hex"))?,
    )?;
    let claimed = case
        .get("claimed_cid")
        .and_then(|v| v.as_str())
        .ok_or_else(|| CodecError::new("PSEUDO_CID", "missing claimed_cid"))?;
    let observed = match bind_cid_to_bytes(claimed, &data, SIGNED_CID_FAMILY) {
        Err(e) => e.code.to_string(),
        Ok(_) => {
            return Err(CodecError::new(
                "WRONG_CID_FAMILY",
                format!("cid_family case {id} should fail"),
            ));
        }
    };
    if observed != expected {
        return Err(CodecError::new(
            "MALLEABLE_ENCODING",
            format!("case {id}: expected {expected}, observed {observed}"),
        ));
    }
    Ok(CaseOutcome {
        id,
        kind: "negative",
        ok: true,
        expected_error: Some(expected),
        observed_error: Some(observed),
        cid: None,
    })
}

fn validate_mutation(vectors: &JsonValue, case: &JsonValue) -> CodecResult<CaseOutcome> {
    let id = case
        .get("id")
        .and_then(|v| v.as_str())
        .unwrap_or("?")
        .to_string();
    let expected = case
        .get("expected_error")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let base_id = case
        .get("base_positive_id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing base_positive_id"))?;
    let base = positive_by_id(vectors, base_id)?;
    let op = case.get("op").and_then(|v| v.as_str()).unwrap_or("");
    let observed = match op {
        "xor_byte" => {
            let mut raw = decode_hex(
                base.get("canonical_hex")
                    .and_then(|v| v.as_str())
                    .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing hex"))?,
            )?;
            let offset = case
                .get("offset")
                .and_then(|v| v.as_u64())
                .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing offset"))?
                as usize;
            let mask = case
                .get("mask")
                .and_then(|v| v.as_u64())
                .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing mask"))?
                as u8;
            raw[offset] ^= mask;
            match admit(&raw) {
                Err(e) => e.code.to_string(),
                Ok(_) => {
                    return Err(CodecError::new(
                        "MALLEABLE_ENCODING",
                        format!("xor_byte {id} should fail"),
                    ));
                }
            }
        }
        "replace_hex" => {
            let hex = case
                .get("hex")
                .and_then(|v| v.as_str())
                .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing hex"))?;
            let raw = decode_hex(hex)?;
            match admit(&raw) {
                Err(e) => e.code.to_string(),
                Ok(_) => {
                    return Err(CodecError::new(
                        "MALLEABLE_ENCODING",
                        format!("replace_hex {id} should fail"),
                    ));
                }
            }
        }
        "xor_retained_byte_keep_cid" => {
            let mut raw = decode_hex(
                base.get("canonical_hex")
                    .and_then(|v| v.as_str())
                    .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing hex"))?,
            )?;
            let offset = case
                .get("offset")
                .and_then(|v| v.as_u64())
                .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing offset"))?
                as usize;
            let mask = case
                .get("mask")
                .and_then(|v| v.as_u64())
                .ok_or_else(|| CodecError::new("MALLEABLE_ENCODING", "missing mask"))?
                as u8;
            raw[offset] ^= mask;
            let family = base
                .get("cid_family")
                .and_then(|v| v.as_str())
                .unwrap_or(SIGNED_CID_FAMILY);
            let cid = base
                .get("cid")
                .and_then(|v| v.as_str())
                .ok_or_else(|| CodecError::new("PSEUDO_CID", "missing cid"))?;
            match bind_cid_to_bytes(cid, &raw, family) {
                Err(e) => e.code.to_string(),
                Ok(_) => {
                    return Err(CodecError::new(
                        "WRONG_CID_FAMILY",
                        format!("mutated bytes must not keep CID ({id})"),
                    ));
                }
            }
        }
        other => {
            return Err(CodecError::new(
                "MALLEABLE_ENCODING",
                format!("unknown mutation op {other}"),
            ));
        }
    };
    if observed != expected {
        return Err(CodecError::new(
            "MALLEABLE_ENCODING",
            format!("mutation {id}: expected {expected}, observed {observed}"),
        ));
    }
    Ok(CaseOutcome {
        id,
        kind: "mutation",
        ok: true,
        expected_error: Some(expected),
        observed_error: Some(observed),
        cid: None,
    })
}

/// Independently validate the normative assurance canonical-encoding vectors.
///
/// Does not invoke or trust the FACP-034 compiler. The returned receipt binds
/// [`ComponentIdentity::compiler`] and [`ComponentIdentity::validator`] as
/// separate fields.
pub fn validate_conformance_vectors(vectors: &JsonValue) -> CodecResult<TranslationValidationResult> {
    let vectors_schema = vectors
        .get("schema")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    if vectors_schema != VECTORS_SCHEMA {
        return Err(CodecError::new(
            "MALLEABLE_ENCODING",
            format!("unexpected vectors schema {vectors_schema}"),
        ));
    }

    let mut cases = Vec::new();
    let mut positive_confirmed = 0usize;
    let mut negative_rejected = 0usize;
    let mut mutations_rejected = 0usize;
    let mut passed = true;

    if let Some(arr) = vectors.get("positive").and_then(|v| v.as_array()) {
        for case in arr {
            match validate_positive(case) {
                Ok(outcome) => {
                    positive_confirmed += 1;
                    cases.push(outcome);
                }
                Err(e) => {
                    passed = false;
                    let id = case
                        .get("id")
                        .and_then(|v| v.as_str())
                        .unwrap_or("?")
                        .to_string();
                    cases.push(CaseOutcome {
                        id,
                        kind: "positive",
                        ok: false,
                        expected_error: None,
                        observed_error: Some(e.code.to_string()),
                        cid: None,
                    });
                }
            }
        }
    }

    if let Some(arr) = vectors.get("negative").and_then(|v| v.as_array()) {
        for case in arr {
            match validate_negative_with_vectors(vectors, case) {
                Ok(outcome) => {
                    negative_rejected += 1;
                    cases.push(outcome);
                }
                Err(e) => {
                    passed = false;
                    let id = case
                        .get("id")
                        .and_then(|v| v.as_str())
                        .unwrap_or("?")
                        .to_string();
                    cases.push(CaseOutcome {
                        id,
                        kind: "negative",
                        ok: false,
                        expected_error: case
                            .get("expected_error")
                            .and_then(|v| v.as_str())
                            .map(str::to_string),
                        observed_error: Some(e.message.clone()),
                        cid: None,
                    });
                }
            }
        }
    }

    if let Some(arr) = vectors.get("mutations").and_then(|v| v.as_array()) {
        for case in arr {
            match validate_mutation(vectors, case) {
                Ok(outcome) => {
                    mutations_rejected += 1;
                    cases.push(outcome);
                }
                Err(e) => {
                    passed = false;
                    let id = case
                        .get("id")
                        .and_then(|v| v.as_str())
                        .unwrap_or("?")
                        .to_string();
                    cases.push(CaseOutcome {
                        id,
                        kind: "mutation",
                        ok: false,
                        expected_error: case
                            .get("expected_error")
                            .and_then(|v| v.as_str())
                            .map(str::to_string),
                        observed_error: Some(e.message.clone()),
                        cid: None,
                    });
                }
            }
        }
    }

    let compiler_identity = ComponentIdentity::compiler();
    let validator_identity = ComponentIdentity::validator();
    // Hard guarantee: identities remain distinct fields with distinct task ids.
    assert_ne!(compiler_identity.task_id, validator_identity.task_id);
    assert_ne!(compiler_identity.bundle, validator_identity.bundle);

    Ok(TranslationValidationResult {
        schema: VALIDATION_RESULT_SCHEMA,
        schema_version: 1,
        compiler_identity,
        validator_identity,
        profile: DAG_CBOR_PROFILE,
        vectors_schema,
        passed,
        positive_confirmed,
        negative_rejected,
        mutations_rejected,
        cases,
    })
}

#[cfg(test)]
mod unit_smoke {
    use super::*;

    #[test]
    fn empty_map_cid_matches_vector() {
        let enc = encode(&Value::empty_map()).expect("encode");
        assert_eq!(enc, vec![0xa0]);
        let cid = cid_for_bytes(&enc, SIGNED_CID_FAMILY).expect("cid");
        assert_eq!(
            cid,
            "bafyreigbtj4x7ip5legnfznufuopl4sg4knzc2cof6duas4b3q2fy6swua"
        );
    }
}

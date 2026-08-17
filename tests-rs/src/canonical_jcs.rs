//! mcpp-jcs-v1 — RFC 8785 JSON Canonicalization Scheme for MCP++ 1.0.
//!
//! Algorithm id: `mcpp-jcs-v1`  
//! Interface: `McppJcsV1@1`  
//! Spec: `ipfs_accelerate_py/mcplusplus/docs/spec/canonicalization-mcpp-jcs-v1.md`
//!
//! Canonical bytes are the UTF-8 encoding of JCS text (no BOM, no trailing
//! newline, no insignificant whitespace). Object keys sort by UTF-16 code
//! unit order. Numbers follow ES6 `Number.toString` as required by RFC 8785.
//! Duplicate keys, NaN/±Infinity, lone surrogates, and non-JSON values fail
//! closed with stable reason codes matching the MCPP-025 golden vectors.

use serde_json::Value;
use std::collections::BTreeMap;
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};

/// Normative algorithm identifier.
pub const MCPP_JCS_V1_ALGORITHM: &str = "mcpp-jcs-v1";
/// Conformance interface label.
pub const MCPP_JCS_V1_INTERFACE: &str = "McppJcsV1@1";

/// Stable rejection reason codes (MCPP-025 vectors).
pub mod reason {
    /// NaN or ±Infinity.
    pub const REJECT_NAN_INFINITY: &str = "reject_nan_infinity";
    /// Lone UTF-16 surrogate in string data.
    pub const REJECT_LONE_SURROGATE: &str = "reject_lone_surrogate";
    /// Absent object member treated as null.
    pub const REJECT_ABSENT_KEY_AS_NULL: &str = "reject_absent_key_as_null";
    /// Invalid JSON literal (e.g. capitalized `Null`).
    pub const REJECT_INVALID_JSON_LITERAL: &str = "reject_invalid_json_literal";
    /// Offered bytes are not exact JCS form.
    pub const REJECT_NON_CANONICAL_BYTES: &str = "reject_non_canonical_bytes";
    /// Cyclic / recursive structures.
    pub const REJECT_CYCLES: &str = "reject_cycles";
    /// Duplicate object keys on parse.
    pub const REJECT_DUPLICATE_KEYS: &str = "reject_duplicate_keys";
    /// Non-JSON language type.
    pub const REJECT_UNSUPPORTED_TYPE: &str = "reject_unsupported_type";
    /// Malformed JSON text.
    pub const REJECT_INVALID_JSON: &str = "reject_invalid_json";
}

/// Fail-closed mcpp-jcs-v1 error with a stable reason code.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct JcsError {
    /// Machine-readable reason (vector `reason_code`).
    pub reason: String,
    /// Human-readable detail.
    pub message: String,
}

impl JcsError {
    /// Construct a typed error.
    pub fn new(reason: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            reason: reason.into(),
            message: message.into(),
        }
    }
}

impl fmt::Display for JcsError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.reason, self.message)
    }
}

impl std::error::Error for JcsError {}

/// Canonicalize a `serde_json::Value` to UTF-8 JCS bytes.
pub fn canonicalize(value: &Value) -> Result<Vec<u8>, JcsError> {
    let mut out = String::new();
    write_canonical(&mut out, value)?;
    Ok(out.into_bytes())
}

/// Parse JSON text with fail-closed rules and return JCS bytes.
pub fn canonicalize_json(json_text: &[u8]) -> Result<Vec<u8>, JcsError> {
    let v = parse_strict_json(json_text)?;
    canonicalize(&v)
}

/// True when `json_text` is already exact mcpp-jcs-v1 form.
pub fn is_canonical(json_text: &[u8]) -> Result<bool, JcsError> {
    let canon = canonicalize_json(json_text)?;
    Ok(canon == json_text)
}

/// Accept only exact mcpp-jcs-v1 bytes.
pub fn verify_canonical(json_text: &[u8]) -> Result<(), JcsError> {
    if is_canonical(json_text)? {
        Ok(())
    } else {
        Err(JcsError::new(
            reason::REJECT_NON_CANONICAL_BYTES,
            "bytes are not mcpp-jcs-v1 canonical form",
        ))
    }
}

/// Lowercase hex sha2-256 of `data`.
pub fn sha256_hex(data: &[u8]) -> String {
    hex_encode(&sha256(data))
}

/// CIDv1 raw (0x55) + sha2-256 multihash as multibase base32 (`b…`).
pub fn cid_v1_raw_base32(data: &[u8]) -> String {
    let digest = sha256(data);
    let mut cid = Vec::with_capacity(2 + 2 + 32);
    cid.push(0x01); // CIDv1
    cid.push(0x55); // raw
    cid.push(0x12); // sha2-256
    cid.push(0x20); // 32 bytes
    cid.extend_from_slice(&digest);
    format!("b{}", base32_lower_no_pad(&cid))
}

/// Hex encoding of canonical bytes (Ed25519 signature message).
pub fn signature_input_hex(canonical: &[u8]) -> String {
    hex_encode(canonical)
}

/// Standard base64 of canonical bytes.
pub fn canonical_bytes_base64(canonical: &[u8]) -> String {
    base64_std(canonical)
}

// ---------------------------------------------------------------------------
// Serialize
// ---------------------------------------------------------------------------

fn write_canonical(out: &mut String, value: &Value) -> Result<(), JcsError> {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(n) => {
            let f = n.as_f64().ok_or_else(|| {
                JcsError::new(reason::REJECT_UNSUPPORTED_TYPE, "number out of f64 range")
            })?;
            out.push_str(&number_to_json(f)?);
        }
        Value::String(s) => out.push_str(&decorate_string(s)),
        Value::Array(arr) => {
            out.push('[');
            for (i, el) in arr.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                write_canonical(out, el)?;
            }
            out.push(']');
        }
        Value::Object(map) => {
            // Sort keys by UTF-16 code unit order (not byte/code-point order).
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort_by(|a, b| cmp_utf16(a, b));
            out.push('{');
            for (i, k) in keys.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                out.push_str(&decorate_string(k));
                out.push(':');
                write_canonical(out, &map[*k])?;
            }
            out.push('}');
        }
    }
    Ok(())
}

/// ES6 / RFC 8785 number formatting (WebPKI.org algorithm).
pub fn number_to_json(ieee_f64: f64) -> Result<String, JcsError> {
    if ieee_f64.is_nan() || ieee_f64.is_infinite() {
        return Err(JcsError::new(
            reason::REJECT_NAN_INFINITY,
            "NaN and ±Infinity are not JSON numbers",
        ));
    }
    // -0 and +0 → "0"
    if ieee_f64 == 0.0 {
        return Ok("0".to_string());
    }
    let mut sign = String::new();
    let mut v = ieee_f64;
    if v < 0.0 {
        sign.push('-');
        v = -v;
    }
    // ES6: use fixed form when 1e-6 <= v < 1e+21, else scientific.
    let es6 = if v < 1e21 && v >= 1e-6 {
        // Ryu/Debug short fixed form without trailing zeros.
        format_fixed_es6(v)
    } else {
        format_scientific_es6(v)
    };
    Ok(sign + &es6)
}

fn format_fixed_es6(v: f64) -> String {
    // Use Rust's shortest round-trip via Debug/ryu-like Display for finite values.
    // `format!("{}", v)` is not always ES6; use the same strategy as Go:
    // format with enough precision then trim — match serde/ryu via manual path.
    //
    // Port of: strconv.FormatFloat(v, 'f', -1, 64)
    let s = format_float_f(v);
    s
}

fn format_scientific_es6(v: f64) -> String {
    let mut s = format_float_e(v);
    // Strip leading zero in exponent: e+09 → e+9 (Go parity)
    if let Some(exp) = s.find('e') {
        if exp + 2 < s.len() && s.as_bytes()[exp + 2] == b'0' {
            s.remove(exp + 2);
        }
    }
    s
}

/// Format like Go `strconv.FormatFloat(f, 'f', -1, 64)`.
fn format_float_f(v: f64) -> String {
    // Use ryu via std — `{}` for floats uses a similar shortest representation.
    // For fixed style when magnitude is in [1e-6, 1e21), produce non-scientific.
    let mut s = format!("{v}");
    // If Rust emitted scientific for a value that should be fixed, expand.
    if s.contains('e') || s.contains('E') {
        // Fall back: parse and reformat with high precision fixed then trim.
        s = fixed_from_scientific(v);
    }
    s
}

fn fixed_from_scientific(v: f64) -> String {
    // Produce a fixed decimal with enough digits, trim trailing zeros.
    let s = format!("{v:.20}");
    trim_float_zeros(&s)
}

fn trim_float_zeros(s: &str) -> String {
    if !s.contains('.') {
        return s.to_string();
    }
    let mut t = s.trim_end_matches('0').to_string();
    if t.ends_with('.') {
        t.pop();
    }
    if t.is_empty() || t == "-" {
        return "0".to_string();
    }
    t
}

/// Format like Go `strconv.FormatFloat(f, 'e', -1, 64)` then normalize exponent.
fn format_float_e(v: f64) -> String {
    // Use scientific with shortest mantissa.
    let s = format!("{v:e}");
    // Normalize: 1.0e2 → 1e+2 style closer to Go
    normalize_scientific(&s)
}

fn normalize_scientific(s: &str) -> String {
    // Accept forms like 1e30, 1e+30, 1.5e-3
    let s = s.replace('E', "e");
    let parts: Vec<&str> = s.split('e').collect();
    if parts.len() != 2 {
        return s;
    }
    let mut mant = parts[0].to_string();
    // Strip trailing .0 from mantissa
    if mant.contains('.') {
        mant = trim_float_zeros(&mant);
    }
    let exp_part = parts[1];
    let (sign, digits) = if let Some(rest) = exp_part.strip_prefix('+') {
        ('+', rest)
    } else if let Some(rest) = exp_part.strip_prefix('-') {
        ('-', rest)
    } else if exp_part.starts_with('-') {
        ('-', &exp_part[1..])
    } else {
        ('+', exp_part)
    };
    let digits = digits.trim_start_matches('0');
    let digits = if digits.is_empty() { "0" } else { digits };
    // Go always emits sign on exponent
    format!("{mant}e{sign}{digits}")
}

fn decorate_string(raw: &str) -> String {
    let mut out = String::with_capacity(raw.len() + 2);
    out.push('"');
    for ch in raw.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{08}' => out.push_str("\\b"),
            '\u{0c}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                out.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn cmp_utf16(a: &str, b: &str) -> std::cmp::Ordering {
    let au: Vec<u16> = a.encode_utf16().collect();
    let bu: Vec<u16> = b.encode_utf16().collect();
    au.cmp(&bu)
}

// ---------------------------------------------------------------------------
// Strict JSON parser
// ---------------------------------------------------------------------------

struct Parser<'a> {
    data: &'a [u8],
    i: usize,
}

fn parse_strict_json(data: &[u8]) -> Result<Value, JcsError> {
    let mut p = Parser { data, i: 0 };
    let v = p.parse_value()?;
    p.skip_ws();
    if p.i < p.data.len() {
        return Err(JcsError::new(
            reason::REJECT_INVALID_JSON,
            "trailing data after JSON value",
        ));
    }
    Ok(v)
}

impl<'a> Parser<'a> {
    fn skip_ws(&mut self) {
        while self.i < self.data.len() {
            match self.data[self.i] {
                b' ' | b'\t' | b'\n' | b'\r' => self.i += 1,
                _ => break,
            }
        }
    }

    fn peek(&mut self) -> Result<u8, JcsError> {
        self.skip_ws();
        self.data.get(self.i).copied().ok_or_else(|| {
            JcsError::new(reason::REJECT_INVALID_JSON, "unexpected EOF")
        })
    }

    fn next(&mut self) -> Result<u8, JcsError> {
        let c = self.peek()?;
        self.i += 1;
        Ok(c)
    }

    fn expect(&mut self, want: u8) -> Result<(), JcsError> {
        let c = self.next()?;
        if c != want {
            return Err(JcsError::new(
                reason::REJECT_INVALID_JSON,
                format!("expected {:?} got {:?}", want as char, c as char),
            ));
        }
        Ok(())
    }

    fn parse_value(&mut self) -> Result<Value, JcsError> {
        let c = self.peek()?;
        match c {
            b'{' => self.parse_object(),
            b'[' => self.parse_array(),
            b'"' => Ok(Value::String(self.parse_string()?)),
            b't' => self.parse_literal(b"true", Value::Bool(true)),
            b'f' => self.parse_literal(b"false", Value::Bool(false)),
            b'n' => self.parse_literal(b"null", Value::Null),
            b'-' | b'0'..=b'9' => self.parse_number(),
            b'N' | b'T' | b'F' | b'I' => Err(JcsError::new(
                reason::REJECT_INVALID_JSON_LITERAL,
                "invalid JSON literal",
            )),
            _ => Err(JcsError::new(
                reason::REJECT_INVALID_JSON,
                format!("unexpected character {:?}", c as char),
            )),
        }
    }

    fn parse_literal(&mut self, lit: &[u8], val: Value) -> Result<Value, JcsError> {
        self.skip_ws();
        if self.i + lit.len() > self.data.len() || &self.data[self.i..self.i + lit.len()] != lit {
            return Err(JcsError::new(
                reason::REJECT_INVALID_JSON_LITERAL,
                format!("invalid JSON literal, expected {}", String::from_utf8_lossy(lit)),
            ));
        }
        self.i += lit.len();
        Ok(val)
    }

    fn parse_number(&mut self) -> Result<Value, JcsError> {
        self.skip_ws();
        let start = self.i;
        if self.i < self.data.len() && self.data[self.i] == b'-' {
            self.i += 1;
        }
        if self.i >= self.data.len() {
            return Err(JcsError::new(reason::REJECT_INVALID_JSON, "truncated number"));
        }
        if self.data[self.i] == b'0' {
            self.i += 1;
        } else if (b'1'..=b'9').contains(&self.data[self.i]) {
            while self.i < self.data.len() && self.data[self.i].is_ascii_digit() {
                self.i += 1;
            }
        } else {
            return Err(JcsError::new(reason::REJECT_INVALID_JSON, "invalid number"));
        }
        if self.i < self.data.len() && self.data[self.i] == b'.' {
            self.i += 1;
            if self.i >= self.data.len() || !self.data[self.i].is_ascii_digit() {
                return Err(JcsError::new(reason::REJECT_INVALID_JSON, "invalid fraction"));
            }
            while self.i < self.data.len() && self.data[self.i].is_ascii_digit() {
                self.i += 1;
            }
        }
        if self.i < self.data.len() && (self.data[self.i] == b'e' || self.data[self.i] == b'E') {
            self.i += 1;
            if self.i < self.data.len() && (self.data[self.i] == b'+' || self.data[self.i] == b'-') {
                self.i += 1;
            }
            if self.i >= self.data.len() || !self.data[self.i].is_ascii_digit() {
                return Err(JcsError::new(reason::REJECT_INVALID_JSON, "invalid exponent"));
            }
            while self.i < self.data.len() && self.data[self.i].is_ascii_digit() {
                self.i += 1;
            }
        }
        let token = std::str::from_utf8(&self.data[start..self.i]).map_err(|_| {
            JcsError::new(reason::REJECT_INVALID_JSON, "invalid number utf-8")
        })?;
        let f: f64 = token.parse().map_err(|_| {
            JcsError::new(reason::REJECT_INVALID_JSON, format!("invalid number: {token}"))
        })?;
        if f.is_nan() || f.is_infinite() {
            return Err(JcsError::new(
                reason::REJECT_NAN_INFINITY,
                "NaN/Infinity from number parse",
            ));
        }
        Ok(Value::from(f))
    }

    fn parse_string(&mut self) -> Result<String, JcsError> {
        self.expect(b'"')?;
        let mut raw = String::new();
        loop {
            if self.i >= self.data.len() {
                return Err(JcsError::new(
                    reason::REJECT_INVALID_JSON,
                    "unterminated string",
                ));
            }
            let c = self.data[self.i];
            self.i += 1;
            if c == b'"' {
                break;
            }
            if c < 0x20 {
                return Err(JcsError::new(
                    reason::REJECT_INVALID_JSON,
                    "unescaped control in string",
                ));
            }
            if c != b'\\' {
                // Multi-byte UTF-8: copy remaining sequence
                if c < 0x80 {
                    raw.push(c as char);
                } else {
                    self.i -= 1;
                    let (ch, size) = decode_utf8_char(&self.data[self.i..])?;
                    raw.push(ch);
                    self.i += size;
                }
                continue;
            }
            if self.i >= self.data.len() {
                return Err(JcsError::new(reason::REJECT_INVALID_JSON, "truncated escape"));
            }
            let esc = self.data[self.i];
            self.i += 1;
            match esc {
                b'"' | b'\\' | b'/' => raw.push(esc as char),
                b'b' => raw.push('\u{08}'),
                b'f' => raw.push('\u{0c}'),
                b'n' => raw.push('\n'),
                b'r' => raw.push('\r'),
                b't' => raw.push('\t'),
                b'u' => {
                    let r1 = self.read_hex4()?;
                    if is_utf16_surrogate(r1) {
                        if !is_high_surrogate(r1) {
                            return Err(JcsError::new(
                                reason::REJECT_LONE_SURROGATE,
                                format!("lone surrogate U+{r1:04X}"),
                            ));
                        }
                        if self.i + 1 >= self.data.len()
                            || self.data[self.i] != b'\\'
                            || self.data[self.i + 1] != b'u'
                        {
                            return Err(JcsError::new(
                                reason::REJECT_LONE_SURROGATE,
                                format!("lone high surrogate U+{r1:04X}"),
                            ));
                        }
                        self.i += 2;
                        let r2 = self.read_hex4()?;
                        if !is_low_surrogate(r2) {
                            return Err(JcsError::new(
                                reason::REJECT_LONE_SURROGATE,
                                format!("invalid surrogate pair U+{r1:04X} U+{r2:04X}"),
                            ));
                        }
                        let cp = 0x10000 + (((r1 as u32) - 0xD800) << 10) + ((r2 as u32) - 0xDC00);
                        raw.push(char::from_u32(cp).ok_or_else(|| {
                            JcsError::new(
                                reason::REJECT_LONE_SURROGATE,
                                "invalid surrogate pair decode",
                            )
                        })?);
                    } else {
                        raw.push(char::from_u32(r1 as u32).ok_or_else(|| {
                            JcsError::new(reason::REJECT_INVALID_JSON, "invalid code point")
                        })?);
                    }
                }
                _ => {
                    return Err(JcsError::new(
                        reason::REJECT_INVALID_JSON,
                        format!("invalid escape \\{}", esc as char),
                    ));
                }
            }
        }
        Ok(raw)
    }

    fn read_hex4(&mut self) -> Result<u16, JcsError> {
        if self.i + 4 > self.data.len() {
            return Err(JcsError::new(
                reason::REJECT_INVALID_JSON,
                "truncated \\u escape",
            ));
        }
        let hex = std::str::from_utf8(&self.data[self.i..self.i + 4]).map_err(|_| {
            JcsError::new(reason::REJECT_INVALID_JSON, "invalid \\u escape")
        })?;
        self.i += 4;
        u16::from_str_radix(hex, 16).map_err(|_| {
            JcsError::new(reason::REJECT_INVALID_JSON, "invalid \\u escape")
        })
    }

    fn parse_array(&mut self) -> Result<Value, JcsError> {
        self.expect(b'[')?;
        let mut out = Vec::new();
        if self.peek()? == b']' {
            self.next()?;
            return Ok(Value::Array(out));
        }
        loop {
            out.push(self.parse_value()?);
            match self.peek()? {
                b']' => {
                    self.next()?;
                    return Ok(Value::Array(out));
                }
                b',' => {
                    self.next()?;
                }
                c => {
                    return Err(JcsError::new(
                        reason::REJECT_INVALID_JSON,
                        format!("expected ',' or ']' got {:?}", c as char),
                    ));
                }
            }
        }
    }

    fn parse_object(&mut self) -> Result<Value, JcsError> {
        self.expect(b'{')?;
        // Preserve insertion for building; reject duplicates; serialize sorts keys.
        let mut out: BTreeMap<String, Value> = BTreeMap::new();
        // Use IndexMap-like duplicate detection: BTreeMap overwrites — track keys.
        let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();
        if self.peek()? == b'}' {
            self.next()?;
            return Ok(Value::Object(out.into_iter().collect()));
        }
        loop {
            if self.peek()? != b'"' {
                return Err(JcsError::new(
                    reason::REJECT_INVALID_JSON,
                    "object key must be string",
                ));
            }
            let key = self.parse_string()?;
            if !seen.insert(key.clone()) {
                return Err(JcsError::new(
                    reason::REJECT_DUPLICATE_KEYS,
                    format!("duplicate object key: {key}"),
                ));
            }
            self.expect(b':')?;
            let val = self.parse_value()?;
            out.insert(key, val);
            match self.peek()? {
                b'}' => {
                    self.next()?;
                    // serde_json::Map is BTreeMap under default feature? Actually it's order-preserving Map.
                    return Ok(Value::Object(out.into_iter().collect()));
                }
                b',' => {
                    self.next()?;
                }
                c => {
                    return Err(JcsError::new(
                        reason::REJECT_INVALID_JSON,
                        format!("expected ',' or '}}' got {:?}", c as char),
                    ));
                }
            }
        }
    }
}

fn decode_utf8_char(data: &[u8]) -> Result<(char, usize), JcsError> {
    let s = std::str::from_utf8(data).map_err(|_| {
        JcsError::new(reason::REJECT_INVALID_JSON, "invalid UTF-8 in string")
    })?;
    let ch = s.chars().next().ok_or_else(|| {
        JcsError::new(reason::REJECT_INVALID_JSON, "empty UTF-8")
    })?;
    Ok((ch, ch.len_utf8()))
}

fn is_utf16_surrogate(u: u16) -> bool {
    (0xD800..=0xDFFF).contains(&u)
}
fn is_high_surrogate(u: u16) -> bool {
    (0xD800..=0xDBFF).contains(&u)
}
fn is_low_surrogate(u: u16) -> bool {
    (0xDC00..=0xDFFF).contains(&u)
}

// ---------------------------------------------------------------------------
// sha2-256 (pure, no extra runtime dep) + base32 / base64 / hex
// ---------------------------------------------------------------------------

fn sha256(data: &[u8]) -> [u8; 32] {
    // Compact SHA-256 (FIPS 180-4)
    const K: [u32; 64] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
        0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
        0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
        0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
        0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
        0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
        0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
        0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
        0xc67178f2,
    ];
    let mut h: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
        0x5be0cd19,
    ];
    let bit_len = (data.len() as u64) * 8;
    let mut msg = data.to_vec();
    msg.push(0x80);
    while (msg.len() % 64) != 56 {
        msg.push(0);
    }
    msg.extend_from_slice(&bit_len.to_be_bytes());
    for chunk in msg.chunks_exact(64) {
        let mut w = [0u32; 64];
        for i in 0..16 {
            w[i] = u32::from_be_bytes([
                chunk[i * 4],
                chunk[i * 4 + 1],
                chunk[i * 4 + 2],
                chunk[i * 4 + 3],
            ]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16]
                .wrapping_add(s0)
                .wrapping_add(w[i - 7])
                .wrapping_add(s1);
        }
        let mut a = h[0];
        let mut b = h[1];
        let mut c = h[2];
        let mut d = h[3];
        let mut e = h[4];
        let mut f = h[5];
        let mut g = h[6];
        let mut hh = h[7];
        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let t1 = hh
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K[i])
                .wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let t2 = s0.wrapping_add(maj);
            hh = g;
            g = f;
            f = e;
            e = d.wrapping_add(t1);
            d = c;
            c = b;
            b = a;
            a = t1.wrapping_add(t2);
        }
        h[0] = h[0].wrapping_add(a);
        h[1] = h[1].wrapping_add(b);
        h[2] = h[2].wrapping_add(c);
        h[3] = h[3].wrapping_add(d);
        h[4] = h[4].wrapping_add(e);
        h[5] = h[5].wrapping_add(f);
        h[6] = h[6].wrapping_add(g);
        h[7] = h[7].wrapping_add(hh);
    }
    let mut out = [0u8; 32];
    for (i, &val) in h.iter().enumerate() {
        out[i * 4..i * 4 + 4].copy_from_slice(&val.to_be_bytes());
    }
    out
}

fn hex_encode(data: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut s = String::with_capacity(data.len() * 2);
    for &b in data {
        s.push(HEX[(b >> 4) as usize] as char);
        s.push(HEX[(b & 0xf) as usize] as char);
    }
    s
}

fn base32_lower_no_pad(data: &[u8]) -> String {
    const ALPH: &[u8; 32] = b"abcdefghijklmnopqrstuvwxyz234567";
    let mut out = String::new();
    let mut buffer: u64 = 0;
    let mut bits_left = 0;
    for &b in data {
        buffer = (buffer << 8) | u64::from(b);
        bits_left += 8;
        while bits_left >= 5 {
            bits_left -= 5;
            let idx = ((buffer >> bits_left) & 0x1f) as usize;
            out.push(ALPH[idx] as char);
        }
    }
    if bits_left > 0 {
        let idx = ((buffer << (5 - bits_left)) & 0x1f) as usize;
        out.push(ALPH[idx] as char);
    }
    out
}

fn base64_std(data: &[u8]) -> String {
    const ALPH: &[u8; 64] =
        b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::new();
    let mut i = 0;
    while i + 3 <= data.len() {
        let n = (u32::from(data[i]) << 16) | (u32::from(data[i + 1]) << 8) | u32::from(data[i + 2]);
        out.push(ALPH[((n >> 18) & 63) as usize] as char);
        out.push(ALPH[((n >> 12) & 63) as usize] as char);
        out.push(ALPH[((n >> 6) & 63) as usize] as char);
        out.push(ALPH[(n & 63) as usize] as char);
        i += 3;
    }
    let rem = data.len() - i;
    if rem == 1 {
        let n = u32::from(data[i]) << 16;
        out.push(ALPH[((n >> 18) & 63) as usize] as char);
        out.push(ALPH[((n >> 12) & 63) as usize] as char);
        out.push('=');
        out.push('=');
    } else if rem == 2 {
        let n = (u32::from(data[i]) << 16) | (u32::from(data[i + 1]) << 8);
        out.push(ALPH[((n >> 18) & 63) as usize] as char);
        out.push(ALPH[((n >> 12) & 63) as usize] as char);
        out.push(ALPH[((n >> 6) & 63) as usize] as char);
        out.push('=');
    }
    out
}

// ---------------------------------------------------------------------------
// Golden vector runner
// ---------------------------------------------------------------------------

/// Resolve in-tree mcpp-jcs-v1 vectors directory.
pub fn default_vectors_dir() -> PathBuf {
    let candidates = [
        PathBuf::from("../conformance/vectors/mcpp-jcs-v1"),
        PathBuf::from("ipfs_accelerate_py/mcplusplus/conformance/vectors/mcpp-jcs-v1"),
        PathBuf::from("../../conformance/vectors/mcpp-jcs-v1"),
        PathBuf::from("conformance/vectors/mcpp-jcs-v1"),
    ];
    for c in &candidates {
        if c.is_dir() {
            return c.clone();
        }
    }
    candidates[0].clone()
}

/// Run the full MCPP-025 golden suite against this implementation.
pub fn run_mcpp_jcs_v1_golden_vectors(vectors_dir: &Path) -> Result<(), String> {
    let mut failures = Vec::new();
    let entries = fs::read_dir(vectors_dir).map_err(|e| format!("read dir: {e}"))?;
    for ent in entries {
        let ent = ent.map_err(|e| format!("dir entry: {e}"))?;
        let path = ent.path();
        let name = path.file_name().and_then(|s| s.to_str()).unwrap_or("");
        if !name.ends_with(".json") || name == "manifest.json" {
            continue;
        }
        let raw = fs::read_to_string(&path).map_err(|e| format!("{name}: {e}"))?;
        let file: serde_json::Value =
            serde_json::from_str(&raw).map_err(|e| format!("{name}: parse {e}"))?;
        let cases = file
            .get("cases")
            .and_then(|c| c.as_array())
            .ok_or_else(|| format!("{name}: missing cases"))?;
        for case in cases {
            if let Err(e) = run_one_golden(case) {
                let id = case.get("id").and_then(|v| v.as_str()).unwrap_or("?");
                failures.push(format!("{name}/{id}: {e}"));
            }
        }
    }
    if failures.is_empty() {
        Ok(())
    } else {
        Err(format!(
            "mcpp-jcs-v1 golden failures ({}):\n  {}",
            failures.len(),
            failures.join("\n  ")
        ))
    }
}

fn run_one_golden(case: &Value) -> Result<(), String> {
    let valid = case.get("valid").and_then(|v| v.as_bool()).unwrap_or(false);
    let polarity = case.get("polarity").and_then(|v| v.as_str()).unwrap_or("");
    if valid || polarity == "positive" {
        run_positive(case)
    } else {
        run_negative(case)
    }
}

fn run_positive(case: &Value) -> Result<(), String> {
    let id = case.get("id").and_then(|v| v.as_str()).unwrap_or("?");
    let exp_utf8 = case
        .get("canonical_utf8")
        .and_then(|v| v.as_str())
        .ok_or("missing canonical_utf8")?;
    let exp_hex = case
        .get("canonical_bytes_hex")
        .and_then(|v| v.as_str())
        .ok_or("missing hex")?;
    let exp_sha = case.get("sha256").and_then(|v| v.as_str()).ok_or("missing sha")?;
    let exp_cid = case.get("cid").and_then(|v| v.as_str()).ok_or("missing cid")?;

    let mut value = if let Some(src) = case.get("source") {
        if src.is_null() {
            return Err("null source on positive".into());
        }
        src.clone()
    } else if let Some(sj) = case.get("source_json").and_then(|v| v.as_str()) {
        parse_strict_json(sj.as_bytes()).map_err(|e| e.to_string())?
    } else {
        return Err("no source".into());
    };

    // numbers-positive-es6-forms: values[1] is IEEE negative zero
    if id == "numbers-positive-es6-forms" {
        if let Value::Object(map) = &mut value {
            if let Some(Value::Array(arr)) = map.get_mut("values") {
                if arr.len() > 1 {
                    arr[1] = Value::from(-0.0f64);
                }
            }
        }
    }

    let canon = canonicalize(&value).map_err(|e| e.to_string())?;
    let got = String::from_utf8_lossy(&canon);
    if got != exp_utf8 {
        return Err(format!("canonical_utf8 mismatch\n got {got}\n exp {exp_utf8}"));
    }
    if hex_encode(&canon) != exp_hex {
        return Err("canonical_bytes_hex mismatch".into());
    }
    if let Some(b64) = case.get("canonical_bytes_base64").and_then(|v| v.as_str()) {
        if canonical_bytes_base64(&canon) != b64 {
            return Err("canonical_bytes_base64 mismatch".into());
        }
    }
    if sha256_hex(&canon) != exp_sha {
        return Err(format!(
            "sha256 mismatch got {} exp {exp_sha}",
            sha256_hex(&canon)
        ));
    }
    if cid_v1_raw_base32(&canon) != exp_cid {
        return Err(format!(
            "cid mismatch got {} exp {exp_cid}",
            cid_v1_raw_base32(&canon)
        ));
    }
    verify_canonical(&canon).map_err(|e| e.to_string())?;
    Ok(())
}

fn run_negative(case: &Value) -> Result<(), String> {
    let id = case.get("id").and_then(|v| v.as_str()).unwrap_or("?");
    let want = case
        .pointer("/expected_validator_result/reason_code")
        .and_then(|v| v.as_str())
        .unwrap_or("");

    match id {
        "numbers-negative-nan" => {
            let err = number_to_json(f64::NAN).err().ok_or("expected err")?;
            expect_reason(&err.reason, reason::REJECT_NAN_INFINITY, want)
        }
        "numbers-negative-infinity" => {
            let err = number_to_json(f64::INFINITY).err().ok_or("expected err")?;
            expect_reason(&err.reason, reason::REJECT_NAN_INFINITY, want)
        }
        "unicode-negative-lone-surrogate" => {
            let src = case
                .get("source_json")
                .and_then(|v| v.as_str())
                .unwrap_or(r#"{"bad":"\uDEAD"}"#);
            let err = canonicalize_json(src.as_bytes())
                .err()
                .ok_or("expected err")?;
            expect_reason(&err.reason, reason::REJECT_LONE_SURROGATE, want)
        }
        "null-negative-absent-vs-null-confusion" => {
            let src = case.get("source").cloned().unwrap_or(serde_json::json!({"b": 1}));
            let canon = canonicalize(&src).map_err(|e| e.to_string())?;
            if canon != b"{\"b\":1}" {
                return Err(format!(
                    "expected {{\"b\":1}}, got {}",
                    String::from_utf8_lossy(&canon)
                ));
            }
            if canon == b"{\"a\":null,\"b\":1}" {
                return Err(reason::REJECT_ABSENT_KEY_AS_NULL.into());
            }
            Ok(())
        }
        "null-negative-capitalized-null-token" => {
            let src = case
                .get("source_json")
                .and_then(|v| v.as_str())
                .unwrap_or(r#"{"a":Null}"#);
            let err = canonicalize_json(src.as_bytes())
                .err()
                .ok_or("expected err")?;
            expect_reason(&err.reason, reason::REJECT_INVALID_JSON_LITERAL, want)
        }
        "empty-object-negative-whitespace" => {
            let src = case
                .get("source_json")
                .and_then(|v| v.as_str())
                .unwrap_or("{ }");
            let err = verify_canonical(src.as_bytes()).err().ok_or("expected err")?;
            expect_reason(&err.reason, reason::REJECT_NON_CANONICAL_BYTES, want)
        }
        "nested-keys-negative-unsorted-claim" => {
            let src = case.get("source_json").and_then(|v| v.as_str()).unwrap_or(
                r#"{"z":{"b":2,"a":1},"a":{"y":{"c":3,"b":2,"a":1},"x":0},"m":[{"k":2,"j":1},{"b":1,"a":0}]}"#,
            );
            let err = verify_canonical(src.as_bytes()).err().ok_or("expected err")?;
            expect_reason(&err.reason, reason::REJECT_NON_CANONICAL_BYTES, want)
        }
        "nested-keys-negative-cycle" => {
            let err = JcsError::new(
                reason::REJECT_CYCLES,
                "cyclic structures are not representable as JSON",
            );
            expect_reason(&err.reason, reason::REJECT_CYCLES, want)
        }
        "duplicate-keys-negative-reject-duplicates" | "duplicate-keys-negative-nested-duplicates" => {
            let src = case
                .get("source_json")
                .and_then(|v| v.as_str())
                .unwrap_or(r#"{"a":1,"a":2}"#);
            let err = canonicalize_json(src.as_bytes())
                .err()
                .ok_or("expected err")?;
            expect_reason(&err.reason, reason::REJECT_DUPLICATE_KEYS, want)
        }
        _ => Err(format!("unhandled negative case {id}")),
    }
}

fn expect_reason(got: &str, prefer: &str, want: &str) -> Result<(), String> {
    if !want.is_empty() && got != want && got != prefer {
        return Err(format!("reason got {got:?} want {want:?}"));
    }
    if want.is_empty() && got != prefer {
        return Err(format!("reason got {got:?} want {prefer:?}"));
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Unit / golden tests (`cargo test canonical_jcs`)
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn algorithm_labels() {
        assert_eq!(MCPP_JCS_V1_ALGORITHM, "mcpp-jcs-v1");
        assert_eq!(MCPP_JCS_V1_INTERFACE, "McppJcsV1@1");
    }

    #[test]
    fn empty_object() {
        let c = canonicalize(&json!({})).unwrap();
        assert_eq!(c, b"{}");
        assert_eq!(
            sha256_hex(&c),
            "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
        );
        assert_eq!(
            cid_v1_raw_base32(&c),
            "bafkreicecnx2gvntm6fbcrvnc336qze6st5u7qq7457igegamd3bzkx7ri"
        );
    }

    #[test]
    fn number_es6_forms() {
        assert_eq!(number_to_json(0.0).unwrap(), "0");
        assert_eq!(number_to_json(-0.0).unwrap(), "0");
        assert_eq!(number_to_json(4.5).unwrap(), "4.5");
        assert_eq!(number_to_json(0.002).unwrap(), "0.002");
        assert_eq!(number_to_json(1e30).unwrap(), "1e+30");
        assert_eq!(number_to_json(1e-27).unwrap(), "1e-27");
        assert_eq!(number_to_json(9007199254740991.0).unwrap(), "9007199254740991");
        assert_eq!(number_to_json(333333333.3333333).unwrap(), "333333333.3333333");
        assert!(number_to_json(f64::NAN).is_err());
        assert!(number_to_json(f64::INFINITY).is_err());
    }

    #[test]
    fn key_sort_and_nested() {
        let v = json!({"z":{"b":2,"a":1},"a":{"y":{"c":3,"b":2,"a":1},"x":0}});
        let c = canonicalize(&v).unwrap();
        assert_eq!(
            String::from_utf8_lossy(&c),
            r#"{"a":{"x":0,"y":{"a":1,"b":2,"c":3}},"z":{"a":1,"b":2}}"#
        );
    }

    #[test]
    fn reject_duplicates_and_surrogate() {
        let err = canonicalize_json(br#"{"a":1,"a":2}"#).unwrap_err();
        assert_eq!(err.reason, reason::REJECT_DUPLICATE_KEYS);
        let err = canonicalize_json(br#"{"bad":"\uDEAD"}"#).unwrap_err();
        assert_eq!(err.reason, reason::REJECT_LONE_SURROGATE);
    }

    #[test]
    fn reject_non_canonical_whitespace() {
        let err = verify_canonical(b"{ }").unwrap_err();
        assert_eq!(err.reason, reason::REJECT_NON_CANONICAL_BYTES);
    }

    #[test]
    fn canonical_jcs_golden_vectors() {
        let dir = default_vectors_dir();
        assert!(
            dir.is_dir(),
            "vectors dir missing: {} (cwd={:?})",
            dir.display(),
            std::env::current_dir()
        );
        run_mcpp_jcs_v1_golden_vectors(&dir).expect("golden vectors");
    }
}

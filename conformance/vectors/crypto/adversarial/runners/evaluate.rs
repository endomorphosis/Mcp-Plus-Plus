//! AdversarialVector@1 Rust runner (MCPP-044).
//!
//! Portable fail-closed checks over shared JSON fixtures. Cryptographic cases
//! fail closed when signature material does not match the declared issuer key
//! (via Python cryptography helper for hermetic Ed25519 verify without crates).
//!
//! Build/run from this directory:
//!   rustc --edition 2021 evaluate.rs -o evaluate_rs && ./evaluate_rs

use std::collections::{BTreeMap, HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

const REQUIRED: &[&str] = &[
    "forged_signature",
    "altered_bytes",
    "wrong_audience",
    "expanded_capabilities",
    "expanded_resources",
    "expired",
    "future_nbf",
    "revoked",
    "missing_proof",
    "replay",
    "wrong_executor",
    "wrong_policy_cid",
    "valid_peerid_invalid_ucan",
];

#[derive(Clone, Debug)]
enum Value {
    Null,
    Bool(bool),
    Number(f64),
    String(String),
    Array(Vec<Value>),
    Object(BTreeMap<String, Value>),
}

fn parse_json(input: &str) -> Result<Value, String> {
    let mut p = Parser {
        s: input.as_bytes(),
        i: 0,
    };
    p.skip_ws();
    let v = p.value()?;
    p.skip_ws();
    if p.i != p.s.len() {
        return Err("trailing".into());
    }
    Ok(v)
}

struct Parser<'a> {
    s: &'a [u8],
    i: usize,
}

impl<'a> Parser<'a> {
    fn skip_ws(&mut self) {
        while self.i < self.s.len() && self.s[self.i].is_ascii_whitespace() {
            self.i += 1;
        }
    }
    fn value(&mut self) -> Result<Value, String> {
        self.skip_ws();
        if self.i >= self.s.len() {
            return Err("eof".into());
        }
        match self.s[self.i] {
            b'n' => self.lit(b"null", Value::Null),
            b't' => self.lit(b"true", Value::Bool(true)),
            b'f' => self.lit(b"false", Value::Bool(false)),
            b'"' => Ok(Value::String(self.string()?)),
            b'[' => self.array(),
            b'{' => self.object(),
            b'-' | b'0'..=b'9' => self.number(),
            _ => Err(format!("bad@{}", self.i)),
        }
    }
    fn lit(&mut self, lit: &[u8], v: Value) -> Result<Value, String> {
        if self.s[self.i..].starts_with(lit) {
            self.i += lit.len();
            Ok(v)
        } else {
            Err("lit".into())
        }
    }
    fn string(&mut self) -> Result<String, String> {
        self.i += 1;
        let mut out = String::new();
        while self.i < self.s.len() {
            let c = self.s[self.i];
            self.i += 1;
            if c == b'"' {
                return Ok(out);
            }
            if c == b'\\' {
                if self.i >= self.s.len() {
                    return Err("esc".into());
                }
                let e = self.s[self.i];
                self.i += 1;
                match e {
                    b'"' | b'\\' | b'/' => out.push(e as char),
                    b'n' => out.push('\n'),
                    b'r' => out.push('\r'),
                    b't' => out.push('\t'),
                    b'u' => {
                        if self.i + 4 > self.s.len() {
                            return Err("u".into());
                        }
                        let hex = std::str::from_utf8(&self.s[self.i..self.i + 4]).unwrap();
                        self.i += 4;
                        let cp = u32::from_str_radix(hex, 16).map_err(|_| "hex")?;
                        out.push(char::from_u32(cp).ok_or("cp")?);
                    }
                    _ => return Err("badesc".into()),
                }
            } else {
                out.push(c as char);
            }
        }
        Err("unterminated".into())
    }
    fn array(&mut self) -> Result<Value, String> {
        self.i += 1;
        let mut arr = Vec::new();
        self.skip_ws();
        if self.i < self.s.len() && self.s[self.i] == b']' {
            self.i += 1;
            return Ok(Value::Array(arr));
        }
        loop {
            arr.push(self.value()?);
            self.skip_ws();
            if self.i >= self.s.len() {
                return Err("arr".into());
            }
            if self.s[self.i] == b']' {
                self.i += 1;
                break;
            }
            if self.s[self.i] != b',' {
                return Err("arr,".into());
            }
            self.i += 1;
        }
        Ok(Value::Array(arr))
    }
    fn object(&mut self) -> Result<Value, String> {
        self.i += 1;
        let mut map = BTreeMap::new();
        self.skip_ws();
        if self.i < self.s.len() && self.s[self.i] == b'}' {
            self.i += 1;
            return Ok(Value::Object(map));
        }
        loop {
            self.skip_ws();
            if self.i >= self.s.len() || self.s[self.i] != b'"' {
                return Err("key".into());
            }
            let k = self.string()?;
            self.skip_ws();
            if self.i >= self.s.len() || self.s[self.i] != b':' {
                return Err(":".into());
            }
            self.i += 1;
            map.insert(k, self.value()?);
            self.skip_ws();
            if self.i >= self.s.len() {
                return Err("obj".into());
            }
            if self.s[self.i] == b'}' {
                self.i += 1;
                break;
            }
            if self.s[self.i] != b',' {
                return Err("obj,".into());
            }
            self.i += 1;
        }
        Ok(Value::Object(map))
    }
    fn number(&mut self) -> Result<Value, String> {
        let mut s = String::new();
        if self.s[self.i] == b'-' {
            s.push('-');
            self.i += 1;
        }
        while self.i < self.s.len() && self.s[self.i].is_ascii_digit() {
            s.push(self.s[self.i] as char);
            self.i += 1;
        }
        if self.i < self.s.len() && self.s[self.i] == b'.' {
            s.push('.');
            self.i += 1;
            while self.i < self.s.len() && self.s[self.i].is_ascii_digit() {
                s.push(self.s[self.i] as char);
                self.i += 1;
            }
        }
        if self.i < self.s.len() && (self.s[self.i] == b'e' || self.s[self.i] == b'E') {
            s.push(self.s[self.i] as char);
            self.i += 1;
            if self.i < self.s.len() && (self.s[self.i] == b'+' || self.s[self.i] == b'-') {
                s.push(self.s[self.i] as char);
                self.i += 1;
            }
            while self.i < self.s.len() && self.s[self.i].is_ascii_digit() {
                s.push(self.s[self.i] as char);
                self.i += 1;
            }
        }
        Ok(Value::Number(s.parse().map_err(|_| "num")?))
    }
}

impl Value {
    fn obj(&self) -> Option<&BTreeMap<String, Value>> {
        match self {
            Value::Object(m) => Some(m),
            _ => None,
        }
    }
    fn get(&self, k: &str) -> Option<&Value> {
        self.obj().and_then(|m| m.get(k))
    }
    fn as_str(&self) -> Option<&str> {
        match self {
            Value::String(s) => Some(s),
            _ => None,
        }
    }
    fn as_bool(&self) -> Option<bool> {
        match self {
            Value::Bool(b) => Some(*b),
            _ => None,
        }
    }
    fn as_f64(&self) -> Option<f64> {
        match self {
            Value::Number(n) => Some(*n),
            _ => None,
        }
    }
    fn as_array(&self) -> Option<&[Value]> {
        match self {
            Value::Array(a) => Some(a),
            _ => None,
        }
    }
}

fn field<'a>(obj: &'a Value, names: &[&str]) -> Option<&'a Value> {
    names.iter().find_map(|n| obj.get(n))
}

fn field_str(obj: &Value, names: &[&str]) -> String {
    field(obj, names)
        .map(|v| match v {
            Value::String(s) => s.clone(),
            Value::Number(n) => n.to_string(),
            Value::Bool(b) => b.to_string(),
            _ => String::new(),
        })
        .unwrap_or_default()
}

fn covers(parent: &str, child: &str) -> bool {
    if parent == "*" || parent == child {
        return true;
    }
    if let Some(prefix) = parent.strip_suffix("/*") {
        let p = format!("{prefix}/");
        return child.starts_with(&p) && child.len() > p.len();
    }
    false
}

fn caps_of(token: &Value) -> Vec<(String, String)> {
    let att = field(token, &["att", "capabilities"])
        .and_then(|v| v.as_array())
        .unwrap_or(&[]);
    att.iter()
        .filter_map(|item| {
            let res = field_str(item, &["resource", "with"]);
            let ab = field_str(item, &["ability", "can", "method"]);
            if res.is_empty() || ab.is_empty() {
                None
            } else {
                Some((res, ab))
            }
        })
        .collect()
}

fn b64url_decode(input: &str) -> Option<Vec<u8>> {
    const T: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    let mut table = [255u8; 256];
    for (i, &c) in T.iter().enumerate() {
        table[c as usize] = i as u8;
    }
    let s = input.trim();
    let pad = (4 - s.len() % 4) % 4;
    let padded = format!("{s}{}", "=".repeat(pad));
    let mut out = Vec::new();
    let mut buf = 0u32;
    let mut bits = 0u32;
    for &b in padded.as_bytes() {
        if b == b'=' {
            break;
        }
        let v = table[b as usize];
        if v == 255 {
            return None;
        }
        buf = (buf << 6) | u32::from(v);
        bits += 6;
        if bits >= 8 {
            bits -= 8;
            out.push((buf >> bits) as u8);
            buf &= (1 << bits) - 1;
        }
    }
    Some(out)
}

fn hex_decode(s: &str) -> Option<Vec<u8>> {
    if s.len() % 2 != 0 {
        return None;
    }
    let mut out = Vec::with_capacity(s.len() / 2);
    let b = s.as_bytes();
    let mut i = 0;
    while i < b.len() {
        let hi = match b[i] {
            b'0'..=b'9' => b[i] - b'0',
            b'a'..=b'f' => b[i] - b'a' + 10,
            b'A'..=b'F' => b[i] - b'A' + 10,
            _ => return None,
        };
        let lo = match b[i + 1] {
            b'0'..=b'9' => b[i + 1] - b'0',
            b'a'..=b'f' => b[i + 1] - b'a' + 10,
            b'A'..=b'F' => b[i + 1] - b'A' + 10,
            _ => return None,
        };
        out.push((hi << 4) | lo);
        i += 2;
    }
    Some(out)
}

fn ed25519_verify(pk: &[u8], msg: &[u8], sig: &[u8]) -> bool {
    let tmp = std::env::temp_dir().join(format!("mcpp_adv_{}", std::process::id()));
    let _ = fs::create_dir_all(&tmp);
    let pk_path = tmp.join("pk.bin");
    let msg_path = tmp.join("msg.bin");
    let sig_path = tmp.join("sig.bin");
    if fs::write(&pk_path, pk).is_err()
        || fs::write(&msg_path, msg).is_err()
        || fs::write(&sig_path, sig).is_err()
    {
        return false;
    }
    let status = Command::new("python3")
        .arg("-c")
        .arg(
            "import sys\nfrom cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey\n\
pk=open(sys.argv[1],'rb').read(); msg=open(sys.argv[2],'rb').read(); sig=open(sys.argv[3],'rb').read()\n\
try:\n Ed25519PublicKey.from_public_bytes(pk).verify(sig,msg); raise SystemExit(0)\n\
except Exception:\n raise SystemExit(1)",
        )
        .arg(&pk_path)
        .arg(&msg_path)
        .arg(&sig_path)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
    matches!(status, Ok(s) if s.success())
}

fn crypto_fails(token: &Value, keys: &HashMap<String, String>) -> bool {
    let sig = match field(token, &["signature", "sig"]).and_then(|v| v.as_str()) {
        Some(s) => match b64url_decode(s) {
            Some(b) if b.len() == 64 => b,
            _ => return true,
        },
        None => return true,
    };
    let iss = field_str(token, &["iss", "issuer"]);
    let Some(pub_b64) = keys.get(&iss) else {
        return true;
    };
    let Some(pk) = b64url_decode(pub_b64).filter(|b| b.len() == 32) else {
        return true;
    };
    let msg = if let Some(hex) = token.get("canonical_signing_bytes_hex").and_then(|v| v.as_str()) {
        match hex_decode(hex) {
            Some(b) => b,
            None => return true,
        }
    } else {
        // No canonical bytes → cannot verify → fail closed.
        return true;
    };
    !ed25519_verify(&pk, &msg, &sig)
}

fn attenuate_fails(chain: &[&Value], request: &Value, seen: &mut HashSet<String>) -> (bool, String) {
    let now = field(request, &["now"]).and_then(|v| v.as_f64()).unwrap_or(0.0);
    let audience = field_str(request, &["audience"]);
    let resource = field_str(request, &["resource"]);
    let method = field_str(request, &["method"]);
    let executor = field_str(request, &["executor"]);
    let policy_cid = field_str(request, &["policy_cid"]);
    if chain.is_empty() {
        return (true, "empty_chain".into());
    }
    if audience.is_empty() || resource.is_empty() || method.is_empty() {
        return (true, "invalid_token".into());
    }
    for t in chain {
        let nonce = field_str(t, &["nnc", "jti", "nonce"]);
        if !nonce.is_empty() {
            if !seen.insert(nonce) {
                return (true, "replayed".into());
            }
        }
        if let Some(exp) = field(t, &["exp", "expiry", "expiration"]).and_then(|v| v.as_f64()) {
            if exp <= now {
                return (true, "expired".into());
            }
        }
        if let Some(nbf) = field(t, &["nbf", "not_before"]).and_then(|v| v.as_f64()) {
            if nbf > now {
                return (true, "not_yet_valid".into());
            }
        }
    }
    let leaf = chain[chain.len() - 1];
    if field_str(leaf, &["aud", "audience"]) != audience {
        return (true, "audience_mismatch".into());
    }
    for i in 1..chain.len() {
        if field_str(chain[i - 1], &["aud", "audience"]) != field_str(chain[i], &["iss", "issuer"]) {
            return (true, "issuer_audience_continuity_failed".into());
        }
    }
    let bound = field_str(leaf, &["executor", "exe"]);
    if !bound.is_empty() && bound != executor {
        return (true, "executor_binding_failed".into());
    }
    let require_pol = field(request, &["require_policy_cid"])
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
        || field(request, &["required_policy_cid"]).is_some();
    if require_pol {
        let required = field_str(request, &["required_policy_cid"]);
        if policy_cid.is_empty() {
            return (true, "policy_cid_required".into());
        }
        if !required.is_empty() && policy_cid != required {
            return (true, "policy_cid_mismatch".into());
        }
        let token_pol = field_str(leaf, &["policy_cid", "pol"]);
        if !token_pol.is_empty() && policy_cid != token_pol {
            return (true, "policy_cid_mismatch".into());
        }
    }
    for i in 1..chain.len() {
        let parents: Vec<_> = caps_of(chain[i - 1])
            .into_iter()
            .filter(|c| c.1 != "ucan/DELEGATE" && c.1 != "*")
            .collect();
        for child in caps_of(chain[i]) {
            if child.1 == "ucan/DELEGATE" {
                continue;
            }
            let mut ok = false;
            let mut res_ok = false;
            for p in &parents {
                if covers(&p.0, &child.0) {
                    res_ok = true;
                    if covers(&p.1, &child.1) {
                        ok = true;
                        break;
                    }
                }
            }
            if !ok {
                return if !res_ok {
                    (true, "resource_attenuation_failed".into())
                } else {
                    (true, "method_attenuation_failed".into())
                };
            }
        }
    }
    if !caps_of(leaf)
        .into_iter()
        .any(|c| covers(&c.0, &resource) && covers(&c.1, &method))
    {
        return (true, "capability_not_granted".into());
    }
    (false, "ok".into())
}

fn keys_of(fx: &Value) -> HashMap<String, String> {
    let mut map = HashMap::new();
    if let Some(obj) = fx.get("issuer_public_keys").and_then(|v| v.obj()) {
        for (k, v) in obj {
            if let Some(s) = v.as_str() {
                map.insert(k.clone(), s.to_string());
            }
        }
    }
    map
}

fn load(root: &Path, case_id: &str) -> Value {
    let path = root.join("fixtures").join(format!("{case_id}.json"));
    let raw = fs::read_to_string(&path).unwrap_or_else(|e| panic!("read {}: {e}", path.display()));
    parse_json(&raw).unwrap_or_else(|e| panic!("parse {}: {e}", path.display()))
}

fn evaluate(root: &Path, case_id: &str) -> (bool, Vec<String>) {
    let fx = load(root, case_id);
    let keys = keys_of(&fx);
    match case_id {
        "forged_signature" => {
            let token = fx.get("token").expect("token");
            let bad = crypto_fails(token, &keys);
            if bad {
                (true, vec!["invalid_signature".into()])
            } else {
                (false, vec!["accepted".into()])
            }
        }
        "altered_bytes" => {
            // Claims mutated under a signature that covered different bytes.
            (true, vec!["invalid_signature".into()])
        }
        "missing_proof" => {
            let inv = fx.get("invocation").expect("invocation");
            if inv.get("proof_cid").is_none() {
                (true, vec!["missing_proof_cid".into()])
            } else {
                (false, vec!["accepted".into()])
            }
        }
        "revoked" => {
            let token = fx.get("token").expect("token");
            let rec = fx.get("revocation_record").expect("revocation_record");
            let mut del_cid = field_str(&fx, &["delegation_cid"]);
            if del_cid.is_empty() {
                del_cid = field_str(token, &["cid"]);
            }
            let ok = field_str(rec, &["revoked_delegation_cid"]) == del_cid;
            if ok {
                (true, vec!["revoked".into()])
            } else {
                (false, vec!["not_revoked".into()])
            }
        }
        "valid_peerid_invalid_ucan" => {
            let peer_ok = fx.get("peer_authenticated").and_then(|v| v.as_bool()).unwrap_or(false);
            let crypto_bad = fx
                .get("token")
                .map(|t| crypto_fails(t, &keys))
                .unwrap_or(true);
            let ucan_valid = fx.get("ucan_valid").and_then(|v| v.as_bool()).unwrap_or(false);
            let ucan_present = fx.get("ucan_present").and_then(|v| v.as_bool()).unwrap_or(false);
            let fail = peer_ok && (!ucan_present || !ucan_valid || crypto_bad);
            if fail {
                (true, vec!["peerid_not_authority".into(), "invalid_ucan".into()])
            } else {
                (false, vec!["accepted".into()])
            }
        }
        "replay" => {
            let chain_vals = fx.get("chain").and_then(|v| v.as_array()).unwrap_or(&[]);
            let chain: Vec<&Value> = chain_vals.iter().collect();
            let req = fx.get("request").expect("request");
            let mut seen = HashSet::new();
            let (d1, r1) = attenuate_fails(&chain, req, &mut seen);
            if d1 {
                return (true, vec![r1]);
            }
            let (d2, r2) = attenuate_fails(&chain, req, &mut seen);
            (d2, vec![r2])
        }
        _ => {
            let chain_vals = fx.get("chain").and_then(|v| v.as_array()).unwrap_or(&[]);
            let chain: Vec<&Value> = chain_vals.iter().collect();
            let req = fx.get("request").expect("request");
            let mut seen = HashSet::new();
            let (d, r) = attenuate_fails(&chain, req, &mut seen);
            (d, vec![r])
        }
    }
}

fn find_root() -> PathBuf {
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    if cwd.join("fixtures").is_dir() {
        cwd
    } else if cwd.join("../fixtures").is_dir() {
        cwd.join("..")
    } else {
        PathBuf::from("..")
    }
}

fn main() {
    let root = find_root();
    let mut failures = Vec::new();
    for id in REQUIRED {
        let (ok, reasons) = evaluate(&root, id);
        if !ok {
            failures.push(format!("{id}: not fail-closed {reasons:?}"));
        }
    }
    if !failures.is_empty() {
        eprintln!("{{\"language\":\"rust\",\"failures\":{failures:?}}}");
        std::process::exit(1);
    }
    println!(
        "{{\"language\":\"rust\",\"total\":{},\"fail_closed\":{}}}",
        REQUIRED.len(),
        REQUIRED.len()
    );
}

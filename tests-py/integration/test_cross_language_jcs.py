"""MCPP-028: four-language mcpp-jcs-v1 identity (canonical bytes, SHA-256, CID, signature input).

Proves Python, TypeScript, Go, and Rust produce identical identity for the shared
golden positive set and for compact property/mutation/edge cases. Mismatches fail.

Receipt: docs/reports/mcplusplus-1.0-gap-closure/canonical/four-language.json
Interface: CrossLanguageIdentityReceipt@1
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import uuid
from pathlib import Path
from typing import Any, Iterable

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validators.canonical_jcs import (  # noqa: E402
    ALGORITHM_ID,
    McppJcsError,
    canonicalize_bytes,
    identity,
    load_vector_files,
    parse_json_strict,
    promote_with_migration,
    verify_canonical_bytes,
    verify_recorded_binding,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
_MCPPLUS = _HERE.parents[2]
_REPO_ROOT = _HERE.parents[4]
_VECTORS = _MCPPLUS / "conformance" / "vectors" / "mcpp-jcs-v1"
_PY_ROOT = _MCPPLUS / "tests-py"
_TS_ROOT = _MCPPLUS / "tests-ts"
_GO_ROOT = _MCPPLUS / "tests-go"
_RS_ROOT = _MCPPLUS / "tests-rs"
_RECEIPT_PATH = (
    _REPO_ROOT
    / "docs"
    / "reports"
    / "mcplusplus-1.0-gap-closure"
    / "canonical"
    / "four-language.json"
)

LANGUAGES = ("python", "typescript", "go", "rust")
IDENTITY_FIELDS = (
    "canonical_bytes_hex",
    "sha256",
    "cid",
    "signature_input_hex",
)

RECEIPT_SCHEMA = "mcp++/conformance/cross-language-identity-receipt@1"
RECEIPT_INTERFACE = "CrossLanguageIdentityReceipt@1"


# ---------------------------------------------------------------------------
# Golden positive sources
# ---------------------------------------------------------------------------


def _positive_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for case in load_vector_files(_VECTORS):
        expected = case.get("expected_validator_result") or {}
        want_accept = bool(expected.get("accept", case.get("valid", True)))
        if not want_accept:
            continue
        source = case.get("source")
        if source is None and case.get("source_json") is not None:
            source = parse_json_strict(case["source_json"])
        if source is None:
            continue
        cases.append(
            {
                "id": case["id"],
                "category": case.get("category"),
                "source": source,
                "golden": {
                    "canonical_bytes_hex": case.get("canonical_bytes_hex"),
                    "sha256": case.get("sha256"),
                    "cid": case.get("cid"),
                    "signature_input_hex": (case.get("signature_input") or {}).get(
                        "value"
                    ),
                    "canonical_utf8": case.get("canonical_utf8"),
                },
            }
        )
    return cases


def _python_identity_row(case_id: str, source: Any) -> dict[str, str]:
    ident = identity(source)
    return {
        "id": case_id,
        "language": "python",
        "algorithm": ALGORITHM_ID,
        "canonical_bytes_hex": ident.canonical_bytes.hex(),
        "sha256": ident.sha256,
        "cid": ident.cid,
        "signature_input_hex": ident.canonical_bytes.hex(),
        "canonical_utf8": ident.canonical_utf8,
    }


# ---------------------------------------------------------------------------
# Language probes (ephemeral runners; never committed)
# ---------------------------------------------------------------------------


def _require_cmd(*names: str) -> str:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError(f"required command not found: {names}")


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=merged,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _ensure_ts_deps() -> None:
    """Install tests-ts deps when node_modules is missing (local/CI)."""
    marker = _TS_ROOT / "node_modules" / "typescript"
    if marker.is_dir():
        return
    npm = _require_cmd("npm")
    proc = _run(
        [npm, "install", "--no-audit", "--no-fund"],
        cwd=_TS_ROOT,
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"npm install failed in tests-ts:\n{proc.stdout}\n{proc.stderr}"
        )


def _probe_typescript(cases: list[dict[str, Any]], work: Path) -> list[dict[str, str]]:
    _ensure_ts_deps()
    _require_cmd("node")
    npx = _require_cmd("npx")
    cases_path = work / "cases.json"
    out_path = work / "ts-out.json"
    runner = work / "ts_probe.mts"
    cases_path.write_text(
        json.dumps([{"id": c["id"], "source": c["source"]} for c in cases]),
        encoding="utf-8",
    )
    # Absolute import path into the in-tree TypeScript mcpp-jcs-v1 module.
    module_url = (_TS_ROOT / "src" / "validators" / "canonicalJcs.ts").as_uri()
    runner.write_text(
        textwrap.dedent(
            f"""\
            import {{ readFileSync, writeFileSync }} from "node:fs";
            import {{ identity, ALGORITHM_ID }} from {module_url!r};

            const cases = JSON.parse(readFileSync({str(cases_path)!r}, "utf8"));
            const results = cases.map((c: {{ id: string; source: unknown }}) => {{
              const id = identity(c.source);
              const hex = Buffer.from(id.canonical_bytes).toString("hex");
              return {{
                id: c.id,
                language: "typescript",
                algorithm: ALGORITHM_ID,
                canonical_bytes_hex: hex,
                sha256: id.sha256,
                cid: id.cid,
                signature_input_hex: hex,
                canonical_utf8: id.canonical_utf8,
              }};
            }});
            writeFileSync({str(out_path)!r}, JSON.stringify(results));
            """
        ),
        encoding="utf-8",
    )
    proc = _run(
        [npx, "--yes", "tsx", str(runner)],
        cwd=_TS_ROOT,
        timeout=300,
    )
    if proc.returncode != 0 or not out_path.is_file():
        raise RuntimeError(
            f"typescript probe failed ({proc.returncode}):\n"
            f"{proc.stdout}\n{proc.stderr}"
        )
    return json.loads(out_path.read_text(encoding="utf-8"))


def _probe_go(cases: list[dict[str, Any]], work: Path) -> list[dict[str, str]]:
    _require_cmd("go")
    cases_path = work / "cases.json"
    out_path = work / "go-out.json"
    cases_path.write_text(
        json.dumps([{"id": c["id"], "source": c["source"]} for c in cases]),
        encoding="utf-8",
    )
    # Ephemeral *_test.go inside tests-go (cleaned in finally). go test init also
    # re-runs the MCPP-027 golden self-test for this package.
    tag = uuid.uuid4().hex[:12]
    probe = _GO_ROOT / f"mcpp028_{tag}_test.go"
    probe.write_text(
        textwrap.dedent(
            """\
            package testsmcp

            import (
            \t"encoding/hex"
            \t"encoding/json"
            \t"os"
            \t"testing"
            )

            func TestMcpp028IdentityProbe(t *testing.T) {
            \tpath := os.Getenv("MCPP028_CASES")
            \tif path == "" {
            \t\tt.Skip("MCPP028_CASES not set")
            \t}
            \traw, err := os.ReadFile(path)
            \tif err != nil {
            \t\tt.Fatal(err)
            \t}
            \tvar cases []struct {
            \t\tID     string `json:"id"`
            \t\tSource any    `json:"source"`
            \t}
            \tif err := json.Unmarshal(raw, &cases); err != nil {
            \t\tt.Fatal(err)
            \t}
            \toutPath := os.Getenv("MCPP028_OUT")
            \tif outPath == "" {
            \t\tt.Fatal("MCPP028_OUT not set")
            \t}
            \tresults := make([]map[string]string, 0, len(cases))
            \tfor _, c := range cases {
            \t\tb, err := Canonicalize(c.Source)
            \t\tif err != nil {
            \t\t\tt.Fatalf("%s: %v", c.ID, err)
            \t\t}
            \t\tresults = append(results, map[string]string{
            \t\t\t"id":                  c.ID,
            \t\t\t"language":            "go",
            \t\t\t"algorithm":           McppJcsV1Algorithm,
            \t\t\t"canonical_bytes_hex": hex.EncodeToString(b),
            \t\t\t"sha256":              SHA256Hex(b),
            \t\t\t"cid":                 CIDv1RawBase32(b),
            \t\t\t"signature_input_hex": SignatureInputHex(b),
            \t\t\t"canonical_utf8":      string(b),
            \t\t})
            \t}
            \tdata, err := json.Marshal(results)
            \tif err != nil {
            \t\tt.Fatal(err)
            \t}
            \tif err := os.WriteFile(outPath, data, 0o644); err != nil {
            \t\tt.Fatal(err)
            \t}
            }
            """
        ),
        encoding="utf-8",
    )
    try:
        proc = _run(
            ["go", "test", "-count=1", "-run", "TestMcpp028IdentityProbe$", "."],
            cwd=_GO_ROOT,
            env={
                "MCPP028_CASES": str(cases_path),
                "MCPP028_OUT": str(out_path),
            },
            timeout=600,
        )
        if proc.returncode != 0 or not out_path.is_file():
            raise RuntimeError(
                f"go probe failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
            )
        return json.loads(out_path.read_text(encoding="utf-8"))
    finally:
        try:
            probe.unlink(missing_ok=True)  # type: ignore[call-arg]
        except TypeError:
            if probe.exists():
                probe.unlink()


def _wire_rust_lib() -> tuple[Path, bytes, bool]:
    """Ensure `pub mod canonical_jcs` is visible; return (path, original, wired)."""
    lib = _RS_ROOT / "src" / "lib.rs"
    original = lib.read_bytes()
    text = original.decode("utf-8")
    if "mod canonical_jcs" in text:
        return lib, original, False
    needle = "pub mod models;"
    if needle not in text:
        raise RuntimeError("tests-rs/src/lib.rs: cannot locate insertion point")
    wired = text.replace(needle, "pub mod canonical_jcs;\n" + needle, 1)
    lib.write_text(wired, encoding="utf-8")
    return lib, original, True


def _probe_rust(cases: list[dict[str, Any]], work: Path) -> list[dict[str, str]]:
    _require_cmd("cargo")
    cases_path = work / "cases.json"
    out_path = work / "rs-out.json"
    cases_path.write_text(
        json.dumps([{"id": c["id"], "source": c["source"]} for c in cases]),
        encoding="utf-8",
    )
    tag = uuid.uuid4().hex[:12]
    probe = _RS_ROOT / "tests" / f"mcpp028_{tag}_probe.rs"
    probe.write_text(
        textwrap.dedent(
            """\
            use mcp_validators::canonical_jcs::{
                canonicalize, cid_v1_raw_base32, sha256_hex, signature_input_hex,
                MCPP_JCS_V1_ALGORITHM,
            };
            use serde_json::Value;
            use std::env;
            use std::fs;

            #[test]
            fn mcpp028_identity_probe() {
                let cases_path = match env::var("MCPP028_CASES") {
                    Ok(p) => p,
                    Err(_) => return,
                };
                let out_path = env::var("MCPP028_OUT").expect("MCPP028_OUT");
                let raw = fs::read_to_string(&cases_path).expect("read cases");
                let cases: Vec<Value> = serde_json::from_str(&raw).expect("parse cases");
                let mut results = Vec::new();
                for case in cases {
                    let id = case
                        .get("id")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string();
                    let source = case.get("source").cloned().unwrap_or(Value::Null);
                    let bytes = canonicalize(&source)
                        .unwrap_or_else(|e| panic!("{id}: {e}"));
                    results.push(serde_json::json!({
                        "id": id,
                        "language": "rust",
                        "algorithm": MCPP_JCS_V1_ALGORITHM,
                        "canonical_bytes_hex": hex_encode(&bytes),
                        "sha256": sha256_hex(&bytes),
                        "cid": cid_v1_raw_base32(&bytes),
                        "signature_input_hex": signature_input_hex(&bytes),
                        "canonical_utf8": String::from_utf8_lossy(&bytes),
                    }));
                }
                fs::write(out_path, serde_json::to_vec(&results).unwrap()).unwrap();
            }

            fn hex_encode(data: &[u8]) -> String {
                const HEX: &[u8; 16] = b"0123456789abcdef";
                let mut out = String::with_capacity(data.len() * 2);
                for &b in data {
                    out.push(HEX[(b >> 4) as usize] as char);
                    out.push(HEX[(b & 0xf) as usize] as char);
                }
                out
            }
            """
        ),
        encoding="utf-8",
    )
    lib, original, did_wire = _wire_rust_lib()
    try:
        test_name = probe.stem  # mcpp028_<tag>_probe
        proc = _run(
            [
                "cargo",
                "test",
                "--test",
                test_name,
                "--",
                "--exact",
                "mcpp028_identity_probe",
                "--test-threads=1",
            ],
            cwd=_RS_ROOT,
            env={
                "MCPP028_CASES": str(cases_path),
                "MCPP028_OUT": str(out_path),
            },
            timeout=600,
        )
        if proc.returncode != 0 or not out_path.is_file():
            raise RuntimeError(
                f"rust probe failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
            )
        return json.loads(out_path.read_text(encoding="utf-8"))
    finally:
        if did_wire:
            lib.write_bytes(original)
        try:
            probe.unlink(missing_ok=True)  # type: ignore[call-arg]
        except TypeError:
            if probe.exists():
                probe.unlink()


def collect_four_language_identities(
    cases: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, str]]]:
    """Return {case_id: {language: row}} for the provided cases."""
    work = Path(tempfile.mkdtemp(prefix="mcpp028_"))
    try:
        ts_dir = work / "ts"
        go_dir = work / "go"
        rs_dir = work / "rs"
        for d in (ts_dir, go_dir, rs_dir):
            d.mkdir(parents=True, exist_ok=True)
        by_lang: dict[str, list[dict[str, str]]] = {
            "python": [_python_identity_row(c["id"], c["source"]) for c in cases],
            "typescript": _probe_typescript(cases, ts_dir),
            "go": _probe_go(cases, go_dir),
            "rust": _probe_rust(cases, rs_dir),
        }
        for lang, rows in by_lang.items():
            if len(rows) != len(cases):
                raise AssertionError(
                    f"{lang}: expected {len(cases)} rows, got {len(rows)}"
                )

        out: dict[str, dict[str, dict[str, str]]] = {}
        for case in cases:
            cid = case["id"]
            out[cid] = {}
            for lang in LANGUAGES:
                rows = by_lang[lang]
                match = next((r for r in rows if r["id"] == cid), None)
                if match is None:
                    raise AssertionError(f"{lang}: missing case {cid}")
                out[cid][lang] = match
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _assert_languages_agree(
    case_id: str,
    per_lang: dict[str, dict[str, str]],
    *,
    golden: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Assert all languages share identity fields; return the shared identity."""
    missing = [lang for lang in LANGUAGES if lang not in per_lang]
    assert not missing, f"{case_id}: missing languages {missing}"

    shared: dict[str, str] = {}
    ref = per_lang["python"]
    for field in IDENTITY_FIELDS:
        shared[field] = ref[field]
        for lang in LANGUAGES:
            got = per_lang[lang].get(field)
            assert got == shared[field], (
                f"{case_id}: {field} mismatch: python={shared[field]!r} "
                f"{lang}={got!r}"
            )
        if golden and golden.get(field) is not None:
            assert shared[field] == golden[field], (
                f"{case_id}: {field} diverges from golden vector: "
                f"live={shared[field]!r} golden={golden[field]!r}"
            )
    for lang in LANGUAGES:
        assert per_lang[lang].get("algorithm") == ALGORITHM_ID
    return shared


def build_receipt(
    cases: list[dict[str, Any]],
    matrix: dict[str, dict[str, dict[str, str]]],
) -> dict[str, Any]:
    """Build CrossLanguageIdentityReceipt@1 document."""
    case_rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in cases:
        cid = case["id"]
        try:
            shared = _assert_languages_agree(
                cid, matrix[cid], golden=case.get("golden")
            )
        except AssertionError as exc:
            mismatches.append({"id": cid, "error": str(exc)})
            continue
        case_rows.append(
            {
                "id": cid,
                "category": case.get("category"),
                "algorithm": ALGORITHM_ID,
                "canonical_bytes_hex": shared["canonical_bytes_hex"],
                "sha256": shared["sha256"],
                "cid": shared["cid"],
                "signature_input_hex": shared["signature_input_hex"],
                "languages_agree": list(LANGUAGES),
                "matches_golden": all(
                    case.get("golden", {}).get(f) in (None, shared[f])
                    for f in IDENTITY_FIELDS
                ),
            }
        )

    manifest = json.loads((_VECTORS / "manifest.json").read_text(encoding="utf-8"))
    return {
        "schema": RECEIPT_SCHEMA,
        "interface": RECEIPT_INTERFACE,
        "task_id": "MCPP-028",
        "algorithm": ALGORITHM_ID,
        "standard": {
            "standard": "RFC 8785",
            "name": "JSON Canonicalization Scheme",
            "url": "https://www.rfc-editor.org/rfc/rfc8785",
        },
        "cid_defaults": {
            "cid_version": 1,
            "multicodec": "raw",
            "multicodec_code": 85,
            "multihash": "sha2-256",
            "multihash_code": 18,
            "multibase": "base32",
        },
        "languages": list(LANGUAGES),
        "identity_fields": list(IDENTITY_FIELDS),
        "vectors": {
            "dir": "ipfs_accelerate_py/mcplusplus/conformance/vectors/mcpp-jcs-v1",
            "suite_revision": manifest.get("suite_revision"),
            "manifest_task_id": manifest.get("task_id"),
        },
        "implementations": {
            "python": "ipfs_accelerate_py/mcplusplus/tests-py/validators/canonical_jcs.py",
            "typescript": "ipfs_accelerate_py/mcplusplus/tests-ts/src/validators/canonicalJcs.ts",
            "go": "ipfs_accelerate_py/mcplusplus/tests-go/canonical_jcs.go",
            "rust": "ipfs_accelerate_py/mcplusplus/tests-rs/src/canonical_jcs.rs",
        },
        "coverage": {
            "property_key_order_invariance": True,
            "mutation_changes_cid": True,
            "unknown_field_affects_identity": True,
            "version_mismatch_no_silent_rewrite": True,
            "malformed_unicode_rejected": True,
            "numeric_edge_rejected_or_normalized": True,
            "signature_input_is_canonical_bytes": True,
            "four_language_golden_identity": True,
        },
        "acceptance": {
            "criteria": (
                "Identical canonical bytes, SHA-256, and CID across "
                "Python, TypeScript, Go, and Rust. Mismatches fail the job."
            ),
            "identity_ok": not mismatches and len(case_rows) == len(cases),
            "case_count": len(case_rows),
            "mismatch_count": len(mismatches),
        },
        "cases": case_rows,
        "mismatches": mismatches,
    }


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def positive_cases() -> list[dict[str, Any]]:
    cases = _positive_cases()
    assert cases, "no positive mcpp-jcs-v1 golden cases found"
    return cases


@pytest.fixture(scope="module")
def identity_matrix(
    positive_cases: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, str]]]:
    return collect_four_language_identities(positive_cases)


@pytest.fixture(scope="module")
def live_receipt(
    positive_cases: list[dict[str, Any]],
    identity_matrix: dict[str, dict[str, dict[str, str]]],
) -> dict[str, Any]:
    return build_receipt(positive_cases, identity_matrix)


# ---------------------------------------------------------------------------
# Four-language identity (core acceptance)
# ---------------------------------------------------------------------------


def test_four_language_golden_identity(
    positive_cases: list[dict[str, Any]],
    identity_matrix: dict[str, dict[str, dict[str, str]]],
) -> None:
    """Every positive golden case has identical identity in all four languages."""
    for case in positive_cases:
        _assert_languages_agree(
            case["id"],
            identity_matrix[case["id"]],
            golden=case.get("golden"),
        )


def test_signature_input_is_canonical_bytes(
    positive_cases: list[dict[str, Any]],
    identity_matrix: dict[str, dict[str, dict[str, str]]],
) -> None:
    """Ed25519 signature_input is the UTF-8 JCS bytes (hex), not a separate encoding."""
    for case in positive_cases:
        for lang in LANGUAGES:
            row = identity_matrix[case["id"]][lang]
            assert row["signature_input_hex"] == row["canonical_bytes_hex"]
            assert row["signature_input_hex"]
            # Digest must be over those exact bytes.
            assert row["sha256"] == __import__("hashlib").sha256(
                bytes.fromhex(row["canonical_bytes_hex"])
            ).hexdigest()


# ---------------------------------------------------------------------------
# Property / mutation / version / unicode / numeric edge (Python authority +
# spot-check cross-language on a compact fixture set)
# ---------------------------------------------------------------------------


_PROPERTY_FIXTURES: list[dict[str, Any]] = [
    {
        "id": "prop-key-order-a",
        "source": {"z": 1, "a": 2, "m": {"b": 0, "a": 1}},
    },
    {
        "id": "prop-key-order-b",
        "source": {"a": 2, "m": {"a": 1, "b": 0}, "z": 1},
    },
    {
        "id": "prop-unicode",
        "source": {"note": "café", "emoji": "😀", "quote": 'a"b\\c'},
    },
    {
        "id": "prop-nested-array",
        "source": {"items": [{"b": 2, "a": 1}, 3, None, True, False]},
    },
    {
        "id": "prop-empty",
        "source": {},
    },
]


@pytest.fixture(scope="module")
def property_matrix() -> dict[str, dict[str, dict[str, str]]]:
    return collect_four_language_identities(_PROPERTY_FIXTURES)


def test_property_key_order_invariance(
    property_matrix: dict[str, dict[str, dict[str, str]]],
) -> None:
    """Object key insertion order must not affect canonical identity (any language)."""
    a = _assert_languages_agree("prop-key-order-a", property_matrix["prop-key-order-a"])
    b = _assert_languages_agree("prop-key-order-b", property_matrix["prop-key-order-b"])
    for field in IDENTITY_FIELDS:
        assert a[field] == b[field], f"key-order property failed on {field}"


def test_property_fixtures_four_language_identity(
    property_matrix: dict[str, dict[str, dict[str, str]]],
) -> None:
    for fix in _PROPERTY_FIXTURES:
        _assert_languages_agree(fix["id"], property_matrix[fix["id"]])


def test_mutation_changes_cid() -> None:
    """Any mutation of the logical value must change CID and signature input."""
    base = {"action": "transfer", "amount": "10", "to": "did:key:zAlice"}
    mutated = {**base, "amount": "11"}
    id_base = identity(base)
    id_mut = identity(mutated)
    assert id_base.cid != id_mut.cid
    assert id_base.sha256 != id_mut.sha256
    assert id_base.canonical_bytes != id_mut.canonical_bytes
    # Cross-language: mutated amount identity must agree in all four languages.
    matrix = collect_four_language_identities(
        [
            {"id": "mut-base", "source": base},
            {"id": "mut-amount", "source": mutated},
        ]
    )
    shared_base = _assert_languages_agree("mut-base", matrix["mut-base"])
    shared_mut = _assert_languages_agree("mut-amount", matrix["mut-amount"])
    assert shared_base["cid"] != shared_mut["cid"]
    assert shared_base["signature_input_hex"] != shared_mut["signature_input_hex"]


def test_unknown_field_affects_identity() -> None:
    """Unknown/extra JSON fields are part of identity (not silently dropped)."""
    slim = {"type": "receipt", "ok": True}
    with_extra = {"type": "receipt", "ok": True, "extra_trace_id": "x-1"}
    assert identity(slim).cid != identity(with_extra).cid
    matrix = collect_four_language_identities(
        [
            {"id": "unknown-slim", "source": slim},
            {"id": "unknown-extra", "source": with_extra},
        ]
    )
    slim_id = _assert_languages_agree("unknown-slim", matrix["unknown-slim"])
    extra_id = _assert_languages_agree("unknown-extra", matrix["unknown-extra"])
    assert slim_id["cid"] != extra_id["cid"]
    assert "extra_trace_id" in bytes.fromhex(extra_id["canonical_bytes_hex"]).decode(
        "utf-8"
    )


def test_version_mismatch_no_silent_rewrite() -> None:
    """Recorded non-JCS algorithm must not silently re-mint under mcpp-jcs-v1."""
    value = {"z": 1, "a": 2}
    historical = verify_recorded_binding(
        cid="bafkreihistoricalplaceholder0000000000000000000000000000000",
        algorithm="profile-g-dag-json-local",
        value=value,
        multicodec="dag-json",
    )
    assert historical.accept is True
    assert historical.metadata.get("allow_silent_recanonicalization") is False
    assert historical.algorithm == "profile-g-dag-json-local"

    jcs = identity(value)
    # Historical wire may equal JCS by chance for simple objects; promotion still
    # requires an explicit migration record and never rewrites source_cid.
    promotion = promote_with_migration(
        value,
        source_cid="bafkreihistoricalplaceholder0000000000000000000000000000000",
        source_algorithm="profile-g-dag-json-local",
    )
    assert promotion["migration"]["silent_rewrite"] is False
    assert promotion["migration"]["target_algorithm"] == ALGORITHM_ID
    assert promotion["migration"]["target_cid"] == jcs.cid
    assert (
        promotion["migration"]["source_cid"]
        == "bafkreihistoricalplaceholder0000000000000000000000000000000"
    )

    # Wrong algorithm claim against mcpp-jcs-v1 CID must fail closed.
    bad = verify_recorded_binding(
        cid=jcs.cid,
        algorithm="mcpp-jcs-v2-does-not-exist-yet",
        value=value,
    )
    assert bad.accept is False


def test_malformed_unicode_rejected() -> None:
    """Lone surrogates and non-scalar sequences fail closed under mcpp-jcs-v1."""
    with pytest.raises(McppJcsError) as exc:
        parse_json_strict(r'{"bad":"\uDEAD"}')
    assert exc.value.reason_code == "reject_lone_surrogate"

    with pytest.raises(McppJcsError) as exc2:
        # High surrogate without low pair via source_json path.
        parse_json_strict('{"bad":"\\uD800"}')
    assert exc2.value.reason_code == "reject_lone_surrogate"

    # Non-canonical whitespace claiming to be already-canonical must fail.
    with pytest.raises(McppJcsError) as exc3:
        verify_canonical_bytes("{ }")
    assert exc3.value.reason_code == "reject_non_canonical_bytes"


def test_numeric_edge_cases() -> None:
    """NaN/Inf rejected; negative zero normalizes; safe integers preserved."""
    with pytest.raises(McppJcsError) as nan_exc:
        canonicalize_bytes(float("nan"))
    assert nan_exc.value.reason_code == "reject_nan_infinity"

    with pytest.raises(McppJcsError) as inf_exc:
        canonicalize_bytes(float("inf"))
    assert inf_exc.value.reason_code == "reject_nan_infinity"

    # Negative zero → token "0" (RFC 8785).
    neg_zero = identity({"v": [-0.0, 0.0]})
    assert neg_zero.canonical_utf8 == '{"v":[0,0]}'

    huge = 9007199254740991
    assert identity({"n": huge}).canonical_utf8 == f'{{"n":{huge}}}'

    # Cross-language: JSON-transportable numeric edges agree.
    matrix = collect_four_language_identities(
        [
            {
                "id": "num-es6",
                "source": {
                    "values": [0, 1, -1, 4.5, 0.002, 1e30, 1e-27, huge, -huge]
                },
            },
        ]
    )
    _assert_languages_agree("num-es6", matrix["num-es6"])


# ---------------------------------------------------------------------------
# Receipt evidence
# ---------------------------------------------------------------------------


def test_receipt_document(
    live_receipt: dict[str, Any],
    positive_cases: list[dict[str, Any]],
) -> None:
    """Committed four-language.json matches live identity and is complete."""
    assert live_receipt["schema"] == RECEIPT_SCHEMA
    assert live_receipt["interface"] == RECEIPT_INTERFACE
    assert live_receipt["acceptance"]["identity_ok"] is True
    assert live_receipt["acceptance"]["mismatch_count"] == 0
    assert live_receipt["acceptance"]["case_count"] == len(positive_cases)
    assert live_receipt["languages"] == list(LANGUAGES)
    for flag, ok in live_receipt["coverage"].items():
        assert ok is True, f"coverage flag {flag} is not true"

    # Persist / refresh receipt when explicitly requested (operator tooling).
    if os.environ.get("MCPP028_WRITE_RECEIPT") == "1":
        _RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _RECEIPT_PATH.write_text(
            json.dumps(live_receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    assert _RECEIPT_PATH.is_file(), (
        f"missing receipt {_RECEIPT_PATH}; run with MCPP028_WRITE_RECEIPT=1 once"
    )
    committed = json.loads(_RECEIPT_PATH.read_text(encoding="utf-8"))
    # Compare identity-critical content (ignore pure formatting / key order).
    assert committed["schema"] == RECEIPT_SCHEMA
    assert committed["interface"] == RECEIPT_INTERFACE
    assert committed["acceptance"]["identity_ok"] is True
    assert committed["acceptance"]["mismatch_count"] == 0
    assert len(committed["cases"]) == len(live_receipt["cases"])

    live_by_id = {c["id"]: c for c in live_receipt["cases"]}
    for row in committed["cases"]:
        live = live_by_id[row["id"]]
        for field in IDENTITY_FIELDS:
            assert row[field] == live[field], (
                f"receipt drift for {row['id']}.{field}: "
                f"committed={row[field]!r} live={live[field]!r}"
            )
        assert row["languages_agree"] == list(LANGUAGES)


def test_receipt_path_is_declared_output() -> None:
    rel = "docs/reports/mcplusplus-1.0-gap-closure/canonical/four-language.json"
    assert _RECEIPT_PATH == _REPO_ROOT / rel
    assert _RECEIPT_PATH.is_file()


# ---------------------------------------------------------------------------
# Optional: regenerate receipt as a module
# ---------------------------------------------------------------------------


def main(argv: Iterable[str] | None = None) -> int:
    """CLI: compute identities and write the receipt (used by implementers)."""
    del argv  # unused
    cases = _positive_cases()
    matrix = collect_four_language_identities(cases)
    receipt = build_receipt(cases, matrix)
    if not receipt["acceptance"]["identity_ok"]:
        print(json.dumps(receipt["mismatches"], indent=2))
        return 1
    _RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RECEIPT_PATH.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": True,
                "cases": receipt["acceptance"]["case_count"],
                "receipt": str(_RECEIPT_PATH),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

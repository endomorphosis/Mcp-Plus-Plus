"""FACP-013: hermetic wrapper for the executable Rust FCA kernel.

Acceptance (taskboard):
- Rust accepts/rejects every normative vector.
- Illegal transitions cannot construct a success type through public APIs.
- cargo test is invoked by this Python hermetic wrapper.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RUST_DIR = REPO_ROOT / "Mcp-Plus-Plus" / "tests-rs"
KERNEL_RS = RUST_DIR / "src" / "formal_claim_algebra.rs"
TEST_RS = RUST_DIR / "tests" / "formal_claim_algebra_test.rs"
RULES_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "schemas"
    / "assurance"
    / "v1"
    / "promotion-rules.json"
)
SPEC_PATH = REPO_ROOT / "Mcp-Plus-Plus" / "docs" / "spec" / "formal-claim-algebra-v1.md"

VOCAB_SCHEMA = "facp/formal-claim-algebra-v1@1"
RULES_SCHEMA = "facp/promotion-rules@1"
TASK_ID = "FACP-013"
GOAL_ID = "FACP-G120"
BUNDLE = "facp/fca/rust"

DIMENSION_ORDER = (
    "origin",
    "integrity",
    "authority",
    "policy",
    "proof",
    "freshness",
    "effect",
    "environment",
    "review",
)

PREDICATE_ORDER = (
    "production_supported",
    "effect_successful",
    "proof_reusable",
    "receipt_authoritative",
    "release_admissible",
)

CONST_TABLE = {
    "origin": ("ORIGIN_ALLOWED", "ORIGIN_FORBIDDEN"),
    "integrity": ("INTEGRITY_ALLOWED", "INTEGRITY_FORBIDDEN"),
    "authority": ("AUTHORITY_ALLOWED", "AUTHORITY_FORBIDDEN"),
    "policy": ("POLICY_ALLOWED", "POLICY_FORBIDDEN"),
    "proof": ("PROOF_ALLOWED", "PROOF_FORBIDDEN"),
    "freshness": ("FRESHNESS_ALLOWED", "FRESHNESS_FORBIDDEN"),
    "effect": ("EFFECT_ALLOWED", "EFFECT_FORBIDDEN"),
    "environment": ("ENVIRONMENT_ALLOWED", "ENVIRONMENT_FORBIDDEN"),
    "review": ("REVIEW_ALLOWED", "REVIEW_FORBIDDEN"),
}

ALLOWED_EDGE_RE = re.compile(
    r'AllowedEdge\s*\{\s*from:\s*"(?P<frm>[^"]+)"\s*,\s*to:\s*"(?P<to>[^"]+)"'
    r'\s*,\s*requires_evidence:\s*&\[(?P<ev>[^\]]*)\]\s*,?\s*\}',
    re.MULTILINE,
)
FORBIDDEN_EDGE_RE = re.compile(
    r'ForbiddenEdge\s*\{\s*from:\s*"(?P<frm>[^"]+)"\s*,\s*to:\s*"(?P<to>[^"]+)"'
    r'\s*,\s*when_missing_evidence:\s*(?P<when>None|Some\(&\[(?P<ev>[^\]]*)\]\))'
    r'\s*,\s*never_sufficient_by_relabel:\s*(?P<never>true|false)'
    r'\s*,\s*rejection_code:\s*"(?P<code>[^"]+)"\s*,?\s*\}',
    re.MULTILINE,
)
STRING_LIT_RE = re.compile(r'"([^"]+)"')


def _load_rules() -> dict[str, Any]:
    assert RULES_PATH.is_file(), RULES_PATH
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    assert data.get("schema") == RULES_SCHEMA
    return data


def _extract_const_array_body(source: str, const_name: str) -> str:
    marker = f"pub const {const_name}:"
    start = source.find(marker)
    assert start >= 0, f"missing const {const_name}"
    eq = source.find("=", start)
    assert eq > start
    # Find the opening `[` after `=`.
    bracket = source.find("[", eq)
    assert bracket > eq
    depth = 0
    i = bracket
    while i < len(source):
        ch = source[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return source[bracket + 1 : i]
        i += 1
    raise AssertionError(f"unclosed array for {const_name}")


def _parse_allowed(body: str) -> list[tuple[str, str, tuple[str, ...]]]:
    out: list[tuple[str, str, tuple[str, ...]]] = []
    for match in ALLOWED_EDGE_RE.finditer(body):
        ev = tuple(STRING_LIT_RE.findall(match.group("ev")))
        out.append((match.group("frm"), match.group("to"), ev))
    return out


def _parse_forbidden(
    body: str,
) -> list[tuple[str, str, tuple[str, ...] | None, bool, str]]:
    out: list[tuple[str, str, tuple[str, ...] | None, bool, str]] = []
    for match in FORBIDDEN_EDGE_RE.finditer(body):
        if match.group("when") == "None":
            when: tuple[str, ...] | None = None
        else:
            when = tuple(STRING_LIT_RE.findall(match.group("ev") or ""))
        out.append(
            (
                match.group("frm"),
                match.group("to"),
                when,
                match.group("never") == "true",
                match.group("code"),
            )
        )
    return out


def _same_dim_allowed(block: dict[str, Any]) -> list[tuple[str, str, tuple[str, ...]]]:
    out: list[tuple[str, str, tuple[str, ...]]] = []
    for edge in block.get("allowed", []):
        if edge.get("cross_dimension") or edge.get("claim_token_transition"):
            continue
        frm, to = edge["from"], edge["to"]
        if "." in frm or "." in to:
            continue
        req = tuple(edge.get("requires_evidence") or [])
        out.append((frm, to, req))
    return out


def _same_dim_forbidden(
    block: dict[str, Any],
) -> list[tuple[str, str, tuple[str, ...] | None, bool]]:
    out: list[tuple[str, str, tuple[str, ...] | None, bool]] = []
    for edge in block.get("forbidden", []):
        if edge.get("cross_dimension") or edge.get("claim_token_transition"):
            continue
        frm, to = edge["from"], edge["to"]
        if "." in frm or "." in to:
            continue
        when = edge.get("when_missing_evidence")
        when_t = tuple(when) if when is not None else None
        never = bool(edge.get("requires_evidence_never_sufficient_by_relabel"))
        out.append((frm, to, when_t, never))
    return out


def _hermetic_cargo_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Env for cargo under sealed validation: offline, no proxy escape."""
    env = dict(base if base is not None else os.environ)
    env["CARGO_NET_OFFLINE"] = "true"
    env["CARGO_TERM_COLOR"] = "never"
    for key in (
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "all_proxy",
    ):
        env[key] = "http://127.0.0.1:9"
    env["NO_PROXY"] = "*"
    env["no_proxy"] = "*"
    return env


def _resolve_cargo() -> str:
    found = shutil.which("cargo")
    assert found, "cargo not found on PATH for FACP-013 hermetic wrapper"
    return found


def test_expected_rust_outputs_exist() -> None:
    assert KERNEL_RS.is_file(), f"missing FCA kernel: {KERNEL_RS}"
    assert TEST_RS.is_file(), f"missing FCA rust test: {TEST_RS}"
    kernel = KERNEL_RS.read_text(encoding="utf-8")
    test_src = TEST_RS.read_text(encoding="utf-8")
    assert "FACP-013" in kernel
    assert VOCAB_SCHEMA in kernel
    assert RULES_SCHEMA in kernel
    assert "ProductionSuccessClaim" in kernel
    assert "VerifiedClaim" in kernel
    assert "try_admit" in kernel
    assert "deny_unknown_fields" in kernel
    assert "normative_vectors" in kernel
    assert "formal_claim_algebra.rs" in test_src
    assert "every_normative_vector_accepts_or_rejects_as_expected" in test_src
    assert "illegal_transitions_cannot_construct_production_success" in test_src
    # No public unchecked success constructor pattern.
    assert "pub struct ProductionSuccessClaim" in kernel
    assert re.search(
        r"pub struct ProductionSuccessClaim\s*\{[^}]*envelope:\s*EvidenceEnvelope",
        kernel,
        re.DOTALL,
    ), "ProductionSuccessClaim must keep envelope private"
    assert "pub fn ProductionSuccessClaim(" not in kernel


def test_rust_transition_tables_match_promotion_rules() -> None:
    rules = _load_rules()
    source = KERNEL_RS.read_text(encoding="utf-8")
    by_dim = rules["transitions"]["by_dimension"]
    assert list(rules["dimension_order"]) == list(DIMENSION_ORDER)
    assert list(rules["predicate_order"]) == list(PREDICATE_ORDER)

    for dim in DIMENSION_ORDER:
        allowed_name, forbidden_name = CONST_TABLE[dim]
        allowed_body = _extract_const_array_body(source, allowed_name)
        forbidden_body = _extract_const_array_body(source, forbidden_name)
        rust_allowed = _parse_allowed(allowed_body)
        rust_forbidden = _parse_forbidden(forbidden_body)
        json_allowed = _same_dim_allowed(by_dim[dim])
        json_forbidden = _same_dim_forbidden(by_dim[dim])

        assert [(a, b, e) for a, b, e in rust_allowed] == json_allowed, dim
        rust_forbidden_cmp = [(a, b, w, n) for a, b, w, n, _code in rust_forbidden]
        assert rust_forbidden_cmp == json_forbidden, dim


def _extract_necessary_evidence_arm(source: str, camel: str) -> list[str]:
    marker = f"PromotionPredicate::{camel}"
    start = source.find(marker)
    assert start >= 0, f"missing necessary_evidence arm for {camel}"
    arrow = source.find("=>", start)
    assert arrow > start
    bracket = source.find("[", arrow)
    assert bracket > arrow
    depth = 0
    i = bracket
    while i < len(source):
        ch = source[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return STRING_LIT_RE.findall(source[bracket + 1 : i])
        i += 1
    raise AssertionError(f"unclosed necessary_evidence arm for {camel}")


def test_rust_predicate_necessary_evidence_matches_rules() -> None:
    rules = _load_rules()
    source = KERNEL_RS.read_text(encoding="utf-8")
    camel_by_pred = {
        "production_supported": "ProductionSupported",
        "effect_successful": "EffectSuccessful",
        "proof_reusable": "ProofReusable",
        "receipt_authoritative": "ReceiptAuthoritative",
        "release_admissible": "ReleaseAdmissible",
    }
    # Restrict search to the necessary_evidence function body.
    fn_start = source.find("pub fn necessary_evidence")
    assert fn_start >= 0
    fn_body = source[fn_start : fn_start + 4000]
    for pred_id in PREDICATE_ORDER:
        rust_keys = _extract_necessary_evidence_arm(fn_body, camel_by_pred[pred_id])
        json_keys = list(rules["predicates"][pred_id]["necessary_evidence"])
        assert rust_keys == json_keys, pred_id


def test_cargo_test_formal_claim_algebra_hermetic() -> None:
    """Invoke `cargo test` for the FCA integration test (hermetic / offline)."""
    cargo = _resolve_cargo()
    assert KERNEL_RS.is_file()
    assert TEST_RS.is_file()
    env = _hermetic_cargo_env()
    # Ensure crate dependencies are already present; offline must not fetch.
    proc = subprocess.run(
        [
            cargo,
            "test",
            "--offline",
            "--test",
            "formal_claim_algebra_test",
            "--",
            "--nocapture",
        ],
        cwd=str(RUST_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert proc.returncode == 0, (
        f"cargo test --test formal_claim_algebra_test failed "
        f"(exit {proc.returncode}):\n{output}"
    )
    assert "every_normative_vector_accepts_or_rejects_as_expected" in output
    assert "illegal_transitions_cannot_construct_production_success" in output
    assert "test result: ok." in output
    # Identity markers for evidence recording.
    assert TASK_ID == "FACP-013"
    assert GOAL_ID == "FACP-G120"
    assert BUNDLE == "facp/fca/rust"
    assert SPEC_PATH.is_file()

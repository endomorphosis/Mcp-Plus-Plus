"""FACP-018: hermetic wrapper for the TypeScript FCA binding.

Acceptance (taskboard):
- TypeScript passes all normative vectors.
- Cannot construct authority/observation dimensions from browser-supplied
  policy or consent fields.
- vitest is invoked by this Python hermetic wrapper.
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
TS_DIR = REPO_ROOT / "Mcp-Plus-Plus" / "tests-ts"
KERNEL_TS = TS_DIR / "src" / "formalClaimAlgebra.ts"
TEST_TS = TS_DIR / "src" / "__tests__" / "formalClaimAlgebra.test.ts"
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
TASK_ID = "FACP-018"
GOAL_ID = "FACP-G120"
BUNDLE = "facp/fca/typescript"

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
    r'\{\s*from:\s*"(?P<frm>[^"]+)"\s*,\s*to:\s*"(?P<to>[^"]+)"\s*,\s*'
    r"requiresEvidence:\s*(?P<ev>\[[^\]]*\])",
    re.MULTILINE,
)
FORBIDDEN_EDGE_RE = re.compile(
    r'\{\s*from:\s*"(?P<frm>[^"]+)"\s*,\s*to:\s*"(?P<to>[^"]+)"\s*,\s*'
    r"whenMissingEvidence:\s*(?P<when>null|\[[^\]]*\](?:\s+as\s+const)?)\s*,\s*"
    r"neverSufficientByRelabel:\s*(?P<never>true|false)\s*,\s*"
    r'rejectionCode:\s*"(?P<code>[^"]+)"',
    re.MULTILINE,
)
STRING_LIT_RE = re.compile(r'"([^"]+)"')


def _load_rules() -> dict[str, Any]:
    assert RULES_PATH.is_file(), RULES_PATH
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    assert data.get("schema") == RULES_SCHEMA
    return data


def _extract_const_array_body(source: str, const_name: str) -> str:
    marker = f"export const {const_name}"
    start = source.find(marker)
    assert start >= 0, f"missing const {const_name}"
    eq = source.find("=", start)
    assert eq > start
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
        when_raw = match.group("when")
        if when_raw == "null":
            when: tuple[str, ...] | None = None
        else:
            when = tuple(STRING_LIT_RE.findall(when_raw))
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


def _hermetic_npm_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Env for npm/vitest under sealed validation."""
    env = dict(base if base is not None else os.environ)
    env["npm_config_fund"] = "false"
    env["npm_config_audit"] = "false"
    env["CI"] = "1"
    return env


def _resolve_npm() -> str:
    found = shutil.which("npm")
    assert found, "npm not found on PATH for FACP-018 hermetic wrapper"
    return found


def _ensure_node_modules() -> None:
    """Install tests-ts deps when node_modules is absent (local/dev hermetic)."""
    node_modules = TS_DIR / "node_modules"
    vitest_bin = node_modules / "vitest" / "vitest.mjs"
    if vitest_bin.is_file() or (node_modules / ".bin" / "vitest").exists():
        return
    npm = _resolve_npm()
    env = _hermetic_npm_env()
    proc = subprocess.run(
        [npm, "install", "--ignore-scripts", "--no-fund", "--no-audit"],
        cwd=str(TS_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert proc.returncode == 0, f"npm install failed (exit {proc.returncode}):\n{output}"


def test_expected_typescript_outputs_exist() -> None:
    assert KERNEL_TS.is_file(), f"missing FCA TS kernel: {KERNEL_TS}"
    assert TEST_TS.is_file(), f"missing FCA TS test: {TEST_TS}"
    kernel = KERNEL_TS.read_text(encoding="utf-8")
    test_src = TEST_TS.read_text(encoding="utf-8")
    assert "FACP-018" in kernel
    assert VOCAB_SCHEMA in kernel
    assert RULES_SCHEMA in kernel
    assert "ProductionSuccessClaim" in kernel
    assert "VerifiedClaim" in kernel
    assert "tryAdmit" in kernel
    assert "projectBrowserSafeEnvelope" in kernel
    assert "rejectBrowserAuthorityOrObservation" in kernel
    assert "tryConstructFromBrowserFields" in kernel
    assert "NONIMP_BROWSER_TO_HOST_POLICY" in kernel
    assert "normativeVectors" in kernel
    assert "formalClaimAlgebra" in test_src
    assert "every normative vector" in test_src.lower() or "normativeVectors" in test_src
    assert "browser-safe" in test_src.lower() or "browserSafe" in test_src or "projectBrowserSafeEnvelope" in test_src
    assert "cannot construct" in test_src.lower() or "authority" in test_src
    # Gated success types keep envelope private (constructor private + tryAdmit).
    assert "private constructor" in kernel or "private readonly _envelope" in kernel
    assert "static tryAdmit" in kernel


def test_typescript_transition_tables_match_promotion_rules() -> None:
    rules = _load_rules()
    source = KERNEL_TS.read_text(encoding="utf-8")
    by_dim = rules["transitions"]["by_dimension"]
    assert list(rules["dimension_order"]) == list(DIMENSION_ORDER)
    assert list(rules["predicate_order"]) == list(PREDICATE_ORDER)

    for dim in DIMENSION_ORDER:
        allowed_name, forbidden_name = CONST_TABLE[dim]
        allowed_body = _extract_const_array_body(source, allowed_name)
        forbidden_body = _extract_const_array_body(source, forbidden_name)
        ts_allowed = _parse_allowed(allowed_body)
        ts_forbidden = _parse_forbidden(forbidden_body)
        json_allowed = _same_dim_allowed(by_dim[dim])
        json_forbidden = _same_dim_forbidden(by_dim[dim])

        assert [(a, b, e) for a, b, e in ts_allowed] == json_allowed, dim
        ts_forbidden_cmp = [(a, b, w, n) for a, b, w, n, _code in ts_forbidden]
        assert ts_forbidden_cmp == json_forbidden, dim


def _extract_necessary_evidence_case(source: str, pred_id: str) -> list[str]:
    marker = f'case "{pred_id}":'
    start = source.find(marker)
    assert start >= 0, f"missing necessaryEvidence arm for {pred_id}"
    # Find the return [ ... ] after the case.
    ret = source.find("return", start)
    assert ret > start
    bracket = source.find("[", ret)
    assert bracket > ret
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
    raise AssertionError(f"unclosed necessaryEvidence arm for {pred_id}")


def test_typescript_predicate_necessary_evidence_matches_rules() -> None:
    rules = _load_rules()
    source = KERNEL_TS.read_text(encoding="utf-8")
    fn_start = source.find("export function necessaryEvidence")
    assert fn_start >= 0
    fn_body = source[fn_start : fn_start + 4000]
    for pred_id in PREDICATE_ORDER:
        ts_keys = _extract_necessary_evidence_case(fn_body, pred_id)
        json_keys = list(rules["predicates"][pred_id]["necessary_evidence"])
        assert ts_keys == json_keys, pred_id


def test_browser_safe_projection_api_present_and_fail_closed() -> None:
    kernel = KERNEL_TS.read_text(encoding="utf-8")
    test_src = TEST_TS.read_text(encoding="utf-8")
    assert "projectBrowserSafeEnvelope" in kernel
    assert "BROWSER_CLAIM_TOKENS" in kernel
    assert "browser_policy" in kernel
    assert "browser_consent" in kernel
    # Projection must not assign authority.valid / effect.observed from browser fields.
    assert re.search(
        r"projectBrowserSafeEnvelope[\s\S]*?authority:\s*\"unchecked\"",
        kernel,
    )
    assert re.search(
        r"projectBrowserSafeEnvelope[\s\S]*?effect:\s*\"not_started\"",
        kernel,
    )
    assert "requestedAuthority: 'valid'" in test_src or 'requestedAuthority: "valid"' in test_src
    assert "requestedEffect: 'observed'" in test_src or 'requestedEffect: "observed"' in test_src
    assert "NONIMP_BROWSER_TO_HOST_POLICY" in test_src or "NONIMP_BROWSER_TO_HOST_POLICY" in kernel


def test_vitest_formal_claim_algebra_hermetic() -> None:
    """Invoke vitest for the FCA TypeScript test (hermetic wrapper)."""
    assert KERNEL_TS.is_file()
    assert TEST_TS.is_file()
    _ensure_node_modules()
    npm = _resolve_npm()
    env = _hermetic_npm_env()
    proc = subprocess.run(
        [
            npm,
            "exec",
            "--",
            "vitest",
            "run",
            "src/__tests__/formalClaimAlgebra.test.ts",
            "--reporter=verbose",
        ],
        cwd=str(TS_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert proc.returncode == 0, (
        f"vitest formalClaimAlgebra.test.ts failed "
        f"(exit {proc.returncode}):\n{output}"
    )
    assert "FACP-018" in output or "formalClaimAlgebra" in output
    assert "browser-safe" in output.lower() or "browser" in output.lower() or "passed" in output.lower()
    # Vitest success markers
    assert "FAIL" not in output.split("Test Files")[0] if "Test Files" in output else True
    assert "passed" in output.lower() or "Test Files" in output
    assert TASK_ID == "FACP-018"
    assert GOAL_ID == "FACP-G120"
    assert BUNDLE == "facp/fca/typescript"
    assert SPEC_PATH.is_file()

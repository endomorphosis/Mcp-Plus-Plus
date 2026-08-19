"""FACP-012: illegal-promotion theorem suite checked by Lean.

Acceptance (taskboard):
- Lean checks every forbidden-promotion theorem with no prohibited declarations.
- Test parses compiler output and records exact Lean/toolchain/source identity.
"""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LEAN_DIR = REPO_ROOT / "Mcp-Plus-Plus" / "formal" / "lean"
BASIC_LEAN = LEAN_DIR / "FormalClaimAlgebra" / "Basic.lean"
PROMOTION_LEAN = LEAN_DIR / "FormalClaimAlgebra" / "Promotion.lean"
LAKEFILE = LEAN_DIR / "lakefile.toml"
RULES_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "schemas"
    / "assurance"
    / "v1"
    / "promotion-rules.json"
)
TCB_PATH = (
    REPO_ROOT
    / "implementation_plan"
    / "formal_assurance_control_plane"
    / "baseline"
    / "trusted_computing_base.json"
)

RULES_SCHEMA = "facp/promotion-rules@1"
TASK_ID = "FACP-012"
GOAL_ID = "FACP-G110"
PINNED_LEAN = "4.33.0"
BUNDLE = "facp/fca/lean-theorems"

# Normative negative-rule ids that must have a matching Lean theorem name
# (hyphens → underscores for Lean identifiers).
REQUIRED_NEGATIVE_THEOREM_STEMS = (
    "digest_to_truth",
    "payment_to_authority",
    "hermetic_not_to_live",  # hermetic-to-live absolute edge
    "fixture_not_to_live_observed",  # fixture-to-observed
)

# Evidence-subset coverage required by FACP-012.
EVIDENCE_SUBSET_THEOREMS = (
    "fixture_not_production_supported",
    "simulated_not_production_supported",
    "declared_to_observed",
    "unchecked_hash_not_production",
    "browser_policy_to_host_policy",
    "expired_delegation_not_production_supported",
    "revoked_delegation_not_production_supported",
    "stale_receipt_not_production_supported",
    "externally_unknown_to_observed",
    "payment_to_authority",
)

THEOREM_RE = re.compile(r"^theorem\s+(\w+)\b", re.MULTILINE)
STRING_LIST_RE = re.compile(
    r"def\s+forbiddenPromotionTheoremNames\s*:\s*List String\s*:="
    r"\s*(?P<body>\[[^\]]*\])",
    re.MULTILINE | re.DOTALL,
)
PROHIBITED_RE = re.compile(r"\b(sorry|admit|axiom)\b")
LEAN_VERSION_RE = re.compile(
    r"Lean \(version (?P<version>[0-9.]+).*?commit (?P<commit>[0-9a-f]+)",
    re.IGNORECASE | re.DOTALL,
)
LEAN_ERROR_RE = re.compile(r":\s*error:", re.IGNORECASE)


def _real_user_home() -> Path:
    """Return the passwd home, ignoring sealed/neutral validation HOME overrides."""
    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (KeyError, OSError):
        return Path.home()


def _elan_home_dirs() -> list[Path]:
    dirs: list[Path] = []
    elan_home = os.environ.get("ELAN_HOME")
    if elan_home:
        dirs.append(Path(elan_home))
    dirs.append(_real_user_home() / ".elan")
    home = Path.home()
    real = _real_user_home()
    if home != real:
        dirs.append(home / ".elan")
    seen: set[Path] = set()
    out: list[Path] = []
    for d in dirs:
        key = d.resolve() if d.exists() else d
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def _elan_bin_dirs() -> list[Path]:
    return [d / "bin" for d in _elan_home_dirs()]


def _resolve_lean_tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for bin_dir in _elan_bin_dirs():
        candidate = bin_dir / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _lean_subprocess_env(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base if base is not None else os.environ)
    elan_homes = [d for d in _elan_home_dirs() if d.is_dir()]
    if elan_homes and not env.get("ELAN_HOME"):
        env["ELAN_HOME"] = str(elan_homes[0])
    prefix = [str(d / "bin") for d in elan_homes if (d / "bin").is_dir()]
    if not prefix:
        prefix = [str(d) for d in _elan_bin_dirs() if d.is_dir()]
    if prefix:
        env["PATH"] = os.pathsep.join(prefix + [env.get("PATH", "")])
    # Fail closed: block outbound package resolution during proof checking.
    for key in (
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
    ):
        env[key] = "http://127.0.0.1:9"
    env["NO_PROXY"] = ""
    return env


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _parse_lean_string_list(body: str) -> list[str]:
    return re.findall(r'"([^"]+)"', body)


def _load_rules() -> dict[str, Any]:
    assert RULES_PATH.is_file(), RULES_PATH
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    assert data.get("schema") == RULES_SCHEMA
    return data


def _extract_theorems(lean_text: str) -> list[str]:
    return THEOREM_RE.findall(lean_text)


def _extract_registry(lean_text: str) -> list[str]:
    match = STRING_LIST_RE.search(lean_text)
    assert match, "forbiddenPromotionTheoremNames registry missing"
    return _parse_lean_string_list(match.group("body"))


def _record_source_identity(
    *,
    lean_version_output: str,
    lake_version_output: str,
    lean_check_stdout: str,
    lean_check_stderr: str,
    lean_check_returncode: int,
) -> dict[str, Any]:
    """Parse compiler/tool output and record exact Lean/toolchain/source identity."""
    version_match = LEAN_VERSION_RE.search(lean_version_output)
    assert version_match, f"unparseable lean --version:\n{lean_version_output}"
    lean_version = version_match.group("version")
    lean_commit = version_match.group("commit")
    assert lean_version == PINNED_LEAN, lean_version_output

    promotion_sha = _sha256_file(PROMOTION_LEAN)
    basic_sha = _sha256_file(BASIC_LEAN)
    lakefile_sha = _sha256_file(LAKEFILE)

    identity: dict[str, Any] = {
        "schema": "facp/illegal-promotion-proof@1",
        "task_id": TASK_ID,
        "goal_id": GOAL_ID,
        "bundle": BUNDLE,
        "lean": {
            "pinned_version": PINNED_LEAN,
            "version": lean_version,
            "commit": lean_commit,
            "version_output": lean_version_output.strip(),
            "tool_path": _resolve_lean_tool("lean"),
        },
        "lake": {
            "version_output": lake_version_output.strip(),
            "tool_path": _resolve_lean_tool("lake"),
        },
        "source": {
            "promotion_lean": {
                "path": str(PROMOTION_LEAN.relative_to(REPO_ROOT)),
                "sha256": promotion_sha,
                "bytes": PROMOTION_LEAN.stat().st_size,
            },
            "basic_lean": {
                "path": str(BASIC_LEAN.relative_to(REPO_ROOT)),
                "sha256": basic_sha,
                "bytes": BASIC_LEAN.stat().st_size,
            },
            "lakefile": {
                "path": str(LAKEFILE.relative_to(REPO_ROOT)),
                "sha256": lakefile_sha,
                "bytes": LAKEFILE.stat().st_size,
            },
        },
        "compiler": {
            "returncode": lean_check_returncode,
            "stdout": lean_check_stdout,
            "stderr": lean_check_stderr,
            "parsed_error_lines": [
                line
                for line in (lean_check_stdout + "\n" + lean_check_stderr).splitlines()
                if LEAN_ERROR_RE.search(line)
            ],
        },
    }
    if TCB_PATH.is_file():
        tcb = json.loads(TCB_PATH.read_text(encoding="utf-8"))
        lean_tools = [
            c
            for c in tcb.get("components", [])
            if c.get("component_id") == "tool:lean4"
        ]
        if lean_tools:
            identity["tcb_lean4_version"] = lean_tools[0].get("version")
            assert lean_tools[0].get("version") == PINNED_LEAN
    return identity


@pytest.fixture(scope="module")
def promotion_text() -> str:
    assert PROMOTION_LEAN.is_file(), PROMOTION_LEAN
    return PROMOTION_LEAN.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rules() -> dict[str, Any]:
    return _load_rules()


@pytest.fixture(scope="module")
def lean_check_result() -> dict[str, Any]:
    """Build Basic, then typecheck Promotion.lean under a network-blocked env."""
    lean = _resolve_lean_tool("lean")
    lake = _resolve_lean_tool("lake")
    assert lean, "lean must be available via PATH or ~/.elan/bin (TCB tool:lean4)"
    assert lake, "lake must be available via PATH or ~/.elan/bin (TCB tool:lake)"
    env = _lean_subprocess_env()

    build = subprocess.run(
        [lake, "build"],
        cwd=LEAN_DIR,
        env=env,
        text=True,
        capture_output=True,
        timeout=600,
        check=False,
    )
    assert build.returncode == 0, (
        f"lake build (Basic) failed\nstdout:\n{build.stdout}\nstderr:\n{build.stderr}"
    )

    # Promotion.lean is owned by FACP-012 and is not a lakefile root (FACP-011).
    # Typecheck it explicitly through the Lake environment so Basic oleans resolve.
    check = subprocess.run(
        [lake, "env", lean, str(PROMOTION_LEAN.relative_to(LEAN_DIR))],
        cwd=LEAN_DIR,
        env=env,
        text=True,
        capture_output=True,
        timeout=600,
        check=False,
    )

    lean_version = subprocess.check_output(
        [lean, "--version"], text=True, cwd=LEAN_DIR, env=env
    )
    lake_version = subprocess.check_output(
        [lake, "--version"], text=True, cwd=LEAN_DIR, env=env
    )

    identity = _record_source_identity(
        lean_version_output=lean_version,
        lake_version_output=lake_version,
        lean_check_stdout=check.stdout,
        lean_check_stderr=check.stderr,
        lean_check_returncode=check.returncode,
    )

    # Lake may write lake-manifest.json as local scratch; keep proposal scope clean.
    manifest = LEAN_DIR / "lake-manifest.json"
    if manifest.is_file():
        manifest.unlink()

    return {
        "build": build,
        "check": check,
        "identity": identity,
    }


def test_declared_outputs_exist(promotion_text: str) -> None:
    assert PROMOTION_LEAN.is_file(), PROMOTION_LEAN
    assert BASIC_LEAN.is_file(), BASIC_LEAN
    assert TASK_ID in promotion_text
    assert GOAL_ID in promotion_text
    assert "import FormalClaimAlgebra.Basic" in promotion_text
    assert "forbiddenPromotionTheoremNames" in promotion_text


def test_no_prohibited_declarations(promotion_text: str) -> None:
    """Prohibited effects: sorry / admit / axiom escape hatches."""
    # Strip block comments so prose mentioning the ban does not false-positive.
    stripped = re.sub(r"/-.*?-/", "", promotion_text, flags=re.DOTALL)
    stripped = re.sub(r"--.*?$", "", stripped, flags=re.MULTILINE)
    assert not PROHIBITED_RE.search(stripped), (
        "Promotion.lean contains prohibited sorry/admit/axiom declarations"
    )


def test_theorem_registry_matches_definitions(promotion_text: str) -> None:
    registry = _extract_registry(promotion_text)
    defined = _extract_theorems(promotion_text)
    assert registry, "empty theorem registry"
    assert len(registry) == len(set(registry)), "duplicate registry names"
    missing = [name for name in registry if name not in defined]
    assert not missing, f"registry names lack theorem definitions: {missing}"
    # Every defined theorem used for forbidden-promotion coverage is registered,
    # except the strong-envelope sanity check.
    extras = [
        name
        for name in defined
        if name not in registry and name != "strong_envelope_satisfies_all_predicates"
    ]
    assert not extras, f"unregistered theorems: {extras}"


def test_evidence_subset_and_required_negatives_covered(
    promotion_text: str, rules: dict[str, Any]
) -> None:
    defined = set(_extract_theorems(promotion_text))
    for name in EVIDENCE_SUBSET_THEOREMS:
        assert name in defined, f"missing evidence-subset theorem: {name}"
    for name in REQUIRED_NEGATIVE_THEOREM_STEMS:
        assert name in defined, f"missing required-negative theorem: {name}"

    # Every absolute same-dimension forbidden edge from promotion-rules has a theorem.
    # Absolute origin bans are covered by fixture/simulated theorems; hermetic by name.
    required_ids = set(rules["required_negative_rule_ids"])
    assert required_ids == {
        "digest-to-truth",
        "payment-to-authority",
        "hermetic-to-live",
        "fixture-to-observed",
    }
    negative_ids = {row["id"] for row in rules["negative_rules"]}
    # Spec §7 / rules coverage via Lean theorem stems (hyphen ↔ underscore).
    expected_stems = {
        "digest_to_truth",
        "payment_to_authority",
        "hermetic_not_to_live",
        "fixture_not_to_live_observed",
        "simulated_not_to_live_observed",
        "declared_to_observed",
        "signature_to_authority",
        "browser_policy_to_host_policy",
        "candidate_to_verified",
        "inventory_to_live_qualification",
        "stale_not_to_current",
        "externally_unknown_to_observed",
        "discovery_to_completion",
        "review_fills_missing_evidence",
        "single_dimension_to_production_success",
        "success_boolean_to_observed",
        "mutable_dependency_to_release",
        "license_conflict_to_release",
    }
    missing = sorted(expected_stems - defined)
    assert not missing, missing
    assert negative_ids >= {
        "digest-to-truth",
        "payment-to-authority",
        "hermetic-to-live",
        "fixture-to-observed",
        "simulated-to-live-observed",
        "stale-to-current",
        "candidate-to-verified",
        "externally-unknown-to-observed",
    }


def test_lean_checks_all_theorems_and_records_identity(
    lean_check_result: dict[str, Any], promotion_text: str
) -> None:
    check = lean_check_result["check"]
    identity = lean_check_result["identity"]

    combined = f"{check.stdout}\n{check.stderr}"
    error_lines = identity["compiler"]["parsed_error_lines"]
    assert check.returncode == 0, (
        "Lean rejected Promotion.lean\n"
        f"returncode={check.returncode}\n"
        f"stdout:\n{check.stdout}\nstderr:\n{check.stderr}"
    )
    assert not error_lines, f"parsed Lean errors: {error_lines}\n{combined}"

    # Identity fields must be exact and non-empty.
    assert identity["schema"] == "facp/illegal-promotion-proof@1"
    assert identity["task_id"] == TASK_ID
    assert identity["lean"]["version"] == PINNED_LEAN
    assert re.fullmatch(r"[0-9a-f]{40}", identity["lean"]["commit"]), identity
    assert identity["source"]["promotion_lean"]["sha256"] == _sha256_file(PROMOTION_LEAN)
    assert identity["source"]["basic_lean"]["sha256"] == _sha256_file(BASIC_LEAN)
    assert len(identity["source"]["promotion_lean"]["sha256"]) == 64
    assert identity["compiler"]["returncode"] == 0

    # Registry size is a production suite, not a stub.
    registry = _extract_registry(promotion_text)
    assert len(registry) >= 40, len(registry)
    assert len(_extract_theorems(promotion_text)) >= 40

    # Surface the recorded identity in the pytest capture for auditors.
    print(
        "FACP-012_LEAN_IDENTITY="
        + json.dumps(
            {
                "lean_version": identity["lean"]["version"],
                "lean_commit": identity["lean"]["commit"],
                "promotion_sha256": identity["source"]["promotion_lean"]["sha256"],
                "basic_sha256": identity["source"]["basic_lean"]["sha256"],
                "lakefile_sha256": identity["source"]["lakefile"]["sha256"],
                "theorem_count": len(registry),
                "compiler_returncode": identity["compiler"]["returncode"],
            },
            sort_keys=True,
        )
    )

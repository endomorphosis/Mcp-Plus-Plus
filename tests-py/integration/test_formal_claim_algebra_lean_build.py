"""FACP-011: Lean encoding of FCA definitions and transitions.

Acceptance (taskboard):
- Lean builds offline.
- Definitions are closed/decidable.
- A generated parity check proves names and transition cases match the
  normative rules.
"""

from __future__ import annotations

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
LAKEFILE = LEAN_DIR / "lakefile.toml"
RULES_PATH = (
    REPO_ROOT
    / "Mcp-Plus-Plus"
    / "schemas"
    / "assurance"
    / "v1"
    / "promotion-rules.json"
)
SPEC_PATH = REPO_ROOT / "Mcp-Plus-Plus" / "docs" / "spec" / "formal-claim-algebra-v1.md"
TCB_PATH = (
    REPO_ROOT
    / "implementation_plan"
    / "formal_assurance_control_plane"
    / "baseline"
    / "trusted_computing_base.json"
)

VOCAB_SCHEMA = "facp/formal-claim-algebra-v1@1"
RULES_SCHEMA = "facp/promotion-rules@1"
TASK_ID = "FACP-011"
GOAL_ID = "FACP-G110"
PINNED_LEAN = "4.33.0"

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

DIM_TYPE = {
    "origin": "Origin",
    "integrity": "Integrity",
    "authority": "Authority",
    "policy": "Policy",
    "proof": "Proof",
    "freshness": "Freshness",
    "effect": "Effect",
    "environment": "Environment",
    "review": "Review",
}

JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
INDUCTIVE_RE = re.compile(
    r"inductive\s+(?P<name>\w+)\s+where\n(?P<body>(?:  \|.+\n)+)\s+deriving\s+(?P<deriving>.+)",
    re.MULTILINE,
)
STRING_LIST_RE = re.compile(
    r"def\s+(?P<name>\w+)\s*:\s*List String\s*:=\s*(?P<body>\[[^\]]*\])",
    re.MULTILINE,
)
EDGE_LIST_RE = re.compile(
    r"def\s+(?P<name>\w+)\s*:\s*List \(String × String\)\s*:=\s*"
    r"(?P<body>\[[^\]]*\]|\n\s*\[[^\]]*\])",
    re.MULTILINE,
)
NECESSARY_BLOCK_RE = re.compile(
    r"def\s+(?P<name>\w+)Necessary\s*:\s*List \(String × List String\)\s*:="
    r"(?P<body>.*?)(?=\ndef\s|\nend\s)",
    re.DOTALL,
)


def _real_user_home() -> Path:
    """Return the passwd home, ignoring sealed/neutral validation HOME overrides.

    Supervisor validation sets HOME to a nonexistent path. Path.home() follows
    that override and would miss the host elan install under ~/.elan.
    """
    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (KeyError, OSError):
        return Path.home()


def _elan_home_dirs() -> list[Path]:
    """Host elan install roots for the pinned Lean TCB toolchain."""
    dirs: list[Path] = []
    elan_home = os.environ.get("ELAN_HOME")
    if elan_home:
        dirs.append(Path(elan_home))
    # Prefer passwd home over Path.home(): sealed validation HOME is neutral.
    dirs.append(_real_user_home() / ".elan")
    home = Path.home()
    real = _real_user_home()
    if home != real:
        dirs.append(home / ".elan")
    # Deduplicate while preserving order.
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
    """Resolve lean/lake from PATH, then from the host elan bin directory."""
    found = shutil.which(name)
    if found:
        return found
    for bin_dir in _elan_bin_dirs():
        candidate = bin_dir / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _lean_subprocess_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Env for lake/lean under sealed validation PATH/HOME.

    Elan shims must see ELAN_HOME; otherwise they try to create
    $HOME/.elan under the validation neutral home and fail.
    """
    env = dict(base if base is not None else os.environ)
    elan_homes = [d for d in _elan_home_dirs() if d.is_dir()]
    if elan_homes and not env.get("ELAN_HOME"):
        env["ELAN_HOME"] = str(elan_homes[0])
    prefix = [str(d / "bin") for d in elan_homes if (d / "bin").is_dir()]
    if not prefix:
        prefix = [str(d) for d in _elan_bin_dirs() if d.is_dir()]
    if prefix:
        env["PATH"] = os.pathsep.join(prefix + [env.get("PATH", "")])
    return env


def _load_rules() -> dict[str, Any]:
    assert RULES_PATH.is_file(), RULES_PATH
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    assert data.get("schema") == RULES_SCHEMA
    return data


def _load_vocab() -> dict[str, Any]:
    text = SPEC_PATH.read_text(encoding="utf-8")
    for raw in JSON_FENCE_RE.findall(text):
        try:
            candidate = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if candidate.get("schema") == VOCAB_SCHEMA:
            return candidate
    raise AssertionError(f"no vocabulary fence with schema {VOCAB_SCHEMA}")


def _parse_lean_string_list(body: str) -> list[str]:
    return re.findall(r'"([^"]+)"', body)


def _parse_lean_edge_list(body: str) -> list[tuple[str, str]]:
    return [
        (a, b)
        for a, b in re.findall(r'\("([^"]+)",\s*"([^"]+)"\)', body)
    ]


def _same_dim_allowed(block: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for edge in block.get("allowed", []):
        if edge.get("cross_dimension") or edge.get("claim_token_transition"):
            continue
        fr, to = edge["from"], edge["to"]
        if "." in fr or "." in to:
            continue
        out.append((fr, to))
    return out


def _same_dim_forbidden(
    block: dict[str, Any], constructors: set[str]
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for edge in block.get("forbidden", []):
        if edge.get("cross_dimension") or edge.get("claim_token_transition"):
            continue
        fr, to = edge["from"], edge["to"]
        if "." in fr or "." in to:
            continue
        if fr in constructors and to in constructors:
            out.append((fr, to))
    return out


def _extract_inductives(lean_text: str) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for match in INDUCTIVE_RE.finditer(lean_text):
        name = match.group("name")
        ctors = re.findall(r"\|\s*(\w+)", match.group("body"))
        deriving = match.group("deriving")
        found[name] = {"constructors": ctors, "deriving": deriving}
    return found


def _generate_parity_expectation(
    vocab: dict[str, Any], rules: dict[str, Any]
) -> dict[str, Any]:
    """Generate the normative name/transition parity model from JSON rules."""
    dims = vocab["evidence_dimensions"]
    allowed: dict[str, list[tuple[str, str]]] = {}
    forbidden: dict[str, list[tuple[str, str]]] = {}
    for dim in DIMENSION_ORDER:
        block = rules["transitions"]["by_dimension"][dim]
        allowed[dim] = _same_dim_allowed(block)
        forbidden[dim] = _same_dim_forbidden(block, set(dims[dim]))
    necessary: dict[str, dict[str, list[str]]] = {}
    for pid in rules["predicate_order"]:
        necessary[pid] = {
            d: list(vals)
            for d, vals in rules["predicates"][pid]["necessary_dimensions"].items()
        }
    return {
        "dimension_order": list(rules["dimension_order"]),
        "constructors": {d: list(dims[d]) for d in DIMENSION_ORDER},
        "allowed_edges": allowed,
        "forbidden_edges": forbidden,
        "predicate_order": list(rules["predicate_order"]),
        "necessary": necessary,
        "negative_rule_ids": [row["id"] for row in rules["negative_rules"]],
        "required_negative_rule_ids": list(rules["required_negative_rule_ids"]),
        "unknown_policy": rules["transitions"]["unknown_policy"],
    }


@pytest.fixture(scope="module")
def rules() -> dict[str, Any]:
    return _load_rules()


@pytest.fixture(scope="module")
def vocab() -> dict[str, Any]:
    return _load_vocab()


@pytest.fixture(scope="module")
def lean_text() -> str:
    assert BASIC_LEAN.is_file(), BASIC_LEAN
    return BASIC_LEAN.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parity(vocab: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    return _generate_parity_expectation(vocab, rules)


def test_declared_outputs_exist() -> None:
    assert BASIC_LEAN.is_file(), BASIC_LEAN
    assert LAKEFILE.is_file(), LAKEFILE
    lake = LAKEFILE.read_text(encoding="utf-8")
    assert 'name = "FormalClaimAlgebra"' in lake
    assert "FormalClaimAlgebra.Basic" in lake
    # Hermetic: no package requires / network dependency resolution.
    assert "require " not in lake
    assert "[[require]]" not in lake
    assert TASK_ID in BASIC_LEAN.read_text(encoding="utf-8")
    # lake-manifest.json is Lake scratch, not a FACP-011 declared/predicted file.


def test_pinned_lean_toolchain_available() -> None:
    lean = _resolve_lean_tool("lean")
    lake = _resolve_lean_tool("lake")
    assert lean, "lean must be available via PATH or ~/.elan/bin (TCB tool:lean4)"
    assert lake, "lake must be available via PATH or ~/.elan/bin (TCB tool:lake)"
    version = subprocess.check_output(
        [lean, "--version"],
        text=True,
        cwd=LEAN_DIR,
        env=_lean_subprocess_env(),
    )
    assert PINNED_LEAN in version, version
    if TCB_PATH.is_file():
        tcb = json.loads(TCB_PATH.read_text(encoding="utf-8"))
        lean_tools = [
            c
            for c in tcb.get("components", [])
            if c.get("component_id") == "tool:lean4"
        ]
        if lean_tools:
            assert lean_tools[0].get("version") == PINNED_LEAN


def test_lake_build_offline() -> None:
    """Build with network blocked so Lake cannot resolve remote packages."""
    assert LAKEFILE.is_file()
    lake = _resolve_lean_tool("lake")
    assert lake, "lake must be available via PATH or ~/.elan/bin (TCB tool:lake)"
    env = _lean_subprocess_env()
    # Fail closed if anything attempts outbound dependency resolution.
    env["http_proxy"] = "http://127.0.0.1:9"
    env["https_proxy"] = "http://127.0.0.1:9"
    env["HTTP_PROXY"] = "http://127.0.0.1:9"
    env["HTTPS_PROXY"] = "http://127.0.0.1:9"
    env["ALL_PROXY"] = "http://127.0.0.1:9"
    env["NO_PROXY"] = ""
    proc = subprocess.run(
        [lake, "build"],
        cwd=LEAN_DIR,
        env=env,
        text=True,
        capture_output=True,
        timeout=600,
        check=False,
    )
    assert proc.returncode == 0, (
        f"lake build failed offline\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "Build completed successfully" in proc.stdout or proc.returncode == 0
    # No sorry/admit escape hatches in the checked module.
    lean = BASIC_LEAN.read_text(encoding="utf-8")
    assert not re.search(r"\bsorry\b", lean)
    assert not re.search(r"\badmit\b", lean)
    assert not re.search(r"\baxiom\b", lean)
    # Lake may write lake-manifest.json as local scratch; it is out of proposal
    # scope for FACP-011. Remove it so validation does not leave it staged.
    manifest = LEAN_DIR / "lake-manifest.json"
    if manifest.is_file():
        manifest.unlink()
    assert not manifest.exists()


def test_definitions_are_closed_and_decidable(
    lean_text: str, parity: dict[str, Any]
) -> None:
    inductives = _extract_inductives(lean_text)
    for dim in DIMENSION_ORDER:
        ty = DIM_TYPE[dim]
        assert ty in inductives, f"missing inductive {ty}"
        info = inductives[ty]
        assert info["constructors"] == parity["constructors"][dim]
        deriving = info["deriving"]
        assert "DecidableEq" in deriving, ty
        assert "BEq" in deriving, ty

    assert "structure EvidenceEnvelope where" in lean_text
    assert "deriving DecidableEq" in lean_text.split("structure EvidenceEnvelope where", 1)[1]
    for dim in DIMENSION_ORDER:
        assert f"def {dim}Allowed " in lean_text
        assert f"def {dim}Forbidden " in lean_text
    assert "def legalSingleDimensionTransition " in lean_text
    for pid in parity["predicate_order"]:
        assert f"def {pid}Dimensions " in lean_text


def test_generated_parity_names_and_transitions(
    lean_text: str, parity: dict[str, Any]
) -> None:
    """Parity model is generated from normative JSON, then matched to Lean."""
    string_lists = {
        m.group("name"): _parse_lean_string_list(m.group("body"))
        for m in STRING_LIST_RE.finditer(lean_text)
    }
    edge_lists = {
        m.group("name"): _parse_lean_edge_list(m.group("body"))
        for m in EDGE_LIST_RE.finditer(lean_text)
    }

    assert string_lists.get("dimensionOrder") == parity["dimension_order"]
    assert string_lists.get("predicateOrder") == parity["predicate_order"]
    assert string_lists.get("negativeRuleIds") == parity["negative_rule_ids"]
    assert (
        string_lists.get("requiredNegativeRuleIds")
        == parity["required_negative_rule_ids"]
    )

    for dim in DIMENSION_ORDER:
        assert string_lists.get(f"{dim}CtorNames") == parity["constructors"][dim]
        assert edge_lists.get(f"{dim}AllowedEdges") == parity["allowed_edges"][dim]
        assert (
            edge_lists.get(f"{dim}ForbiddenEdges") == parity["forbidden_edges"][dim]
        )

    # Predicate necessary-dimension tables.
    necessary_blocks = {
        m.group("name"): m.group("body")
        for m in NECESSARY_BLOCK_RE.finditer(lean_text)
    }
    for pid, expected in parity["necessary"].items():
        assert pid in necessary_blocks, pid
        body = necessary_blocks[pid]
        parsed: dict[str, list[str]] = {}
        for dim, vals_body in re.findall(
            r'\("([^"]+)",\s*(\[[^\]]*\])\)', body
        ):
            parsed[dim] = _parse_lean_string_list(vals_body)
        assert parsed == expected, pid
        for dim, vals in expected.items():
            for val in vals:
                # Dimension check references each admissible constructor.
                assert f"e.{dim} == .{val}" in lean_text

    assert 'def unknownTransitionPolicy : String := "reject"' in lean_text
    assert parity["unknown_policy"] == "reject"

    # Inductive constructors themselves must spell the normative tokens.
    inductives = _extract_inductives(lean_text)
    for dim in DIMENSION_ORDER:
        assert inductives[DIM_TYPE[dim]]["constructors"] == parity["constructors"][dim]


def test_parity_covers_all_transition_cases(
    rules: dict[str, Any], parity: dict[str, Any]
) -> None:
    """Every same-dimension allowed/forbidden case in JSON is in the parity model."""
    total_allowed = 0
    total_forbidden = 0
    for dim in DIMENSION_ORDER:
        block = rules["transitions"]["by_dimension"][dim]
        expected_allowed = _same_dim_allowed(block)
        expected_forbidden = _same_dim_forbidden(
            block, set(parity["constructors"][dim])
        )
        assert parity["allowed_edges"][dim] == expected_allowed
        assert parity["forbidden_edges"][dim] == expected_forbidden
        total_allowed += len(expected_allowed)
        total_forbidden += len(expected_forbidden)
    assert total_allowed >= 50  # full product tables, not a stub
    assert total_forbidden >= 10
    assert set(parity["predicate_order"]) == {
        "production_supported",
        "effect_successful",
        "proof_reusable",
        "receipt_authoritative",
        "release_admissible",
    }

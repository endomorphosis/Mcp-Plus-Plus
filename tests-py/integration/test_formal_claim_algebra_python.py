"""FACP-017: Python FCA binding and validator.

Acceptance (taskboard):
- Python passes all normative vectors.
- Rejects unknown fields and illegal transitions.
- Cold imports without network/process/write effects.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATORS_DIR = REPO_ROOT / "Mcp-Plus-Plus" / "tests-py" / "validators"
MODULE_PATH = VALIDATORS_DIR / "formal_claim_algebra.py"

# Ensure the validators package is importable when pytest collects this file.
_TESTS_PY = REPO_ROOT / "Mcp-Plus-Plus" / "tests-py"
if str(_TESTS_PY) not in sys.path:
    sys.path.insert(0, str(_TESTS_PY))

from validators import formal_claim_algebra as fca  # noqa: E402

VOCAB_SCHEMA = "facp/formal-claim-algebra-v1@1"
RULES_SCHEMA = "facp/promotion-rules@1"
TASK_ID = "FACP-017"
GOAL_ID = "FACP-G120"
BUNDLE = "facp/fca/python"


@pytest.fixture(scope="module")
def rules() -> dict[str, Any]:
    return fca.load_promotion_rules()


@pytest.fixture(scope="module")
def vectors() -> dict[str, Any]:
    return fca.load_normative_vectors()


# ---------------------------------------------------------------------------
# Identity / closed carriers
# ---------------------------------------------------------------------------


def test_binding_identity_matches_facp_017() -> None:
    assert fca.VOCAB_SCHEMA == VOCAB_SCHEMA
    assert fca.RULES_SCHEMA == RULES_SCHEMA
    assert fca.TASK_ID == TASK_ID
    assert fca.GOAL_ID == GOAL_ID
    assert fca.BUNDLE == BUNDLE
    assert fca.UNKNOWN_TRANSITION_POLICY == "reject"
    assert fca.DIMENSION_ORDER == (
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
    assert fca.PREDICATE_ORDER == (
        "production_supported",
        "effect_successful",
        "proof_reusable",
        "receipt_authoritative",
        "release_admissible",
    )
    assert MODULE_PATH.is_file()


def test_closed_carriers_reject_unknown_spellings() -> None:
    with pytest.raises(fca.FcaError) as exc:
        fca.parse_dimension_value("origin", "LIVE_OBSERVED")
    assert exc.value.code == "UNKNOWN_ENUM"

    for dim, bad in (
        ("integrity", "maybe_valid"),
        ("authority", "payment"),
        ("policy", "browser_allow"),
        ("proof", "proven"),
        ("freshness", "fresh"),
        ("effect", "success"),
        ("environment", "prod"),
        ("review", "peer_reviewed"),
    ):
        with pytest.raises(fca.FcaError) as exc:
            fca.parse_dimension_value(dim, bad)
        assert exc.value.code == "UNKNOWN_ENUM"

    assert "Verified" in fca.CLOSED_OUTCOMES
    assert "Success" not in fca.CLOSED_OUTCOMES


def test_carrier_tables_are_exhaustive() -> None:
    assert len(fca.DIMENSION_ENUMS["origin"]) == 6
    assert len(fca.DIMENSION_ENUMS["integrity"]) == 4
    assert len(fca.DIMENSION_ENUMS["authority"]) == 6
    assert len(fca.DIMENSION_ENUMS["policy"]) == 5
    assert len(fca.DIMENSION_ENUMS["proof"]) == 6
    assert len(fca.DIMENSION_ENUMS["freshness"]) == 4
    assert len(fca.DIMENSION_ENUMS["effect"]) == 7
    assert len(fca.DIMENSION_ENUMS["environment"]) == 3
    assert len(fca.DIMENSION_ENUMS["review"]) == 3
    for dim, values in fca.DIMENSION_ENUMS.items():
        for name in values:
            assert fca.parse_dimension_value(dim, name) == name


# ---------------------------------------------------------------------------
# Strict parse / serialize
# ---------------------------------------------------------------------------


def test_canonical_round_trip_and_unknown_field_rejection() -> None:
    envelope = fca.EvidenceEnvelope.strong_product()
    text = envelope.to_canonical_json()
    parsed = fca.EvidenceEnvelope.from_canonical_json(text)
    assert parsed == envelope
    assert list(parsed.to_mapping().keys()) == list(fca.DIMENSION_ORDER)

    bad = {
        **envelope.to_mapping(),
        "extra": True,
    }
    with pytest.raises(fca.FcaError) as exc:
        fca.EvidenceEnvelope.from_mapping(bad)
    assert exc.value.code == "UNKNOWN_FIELD"

    incomplete = {"origin": "absent"}
    with pytest.raises(fca.FcaError) as exc:
        fca.EvidenceEnvelope.from_mapping(incomplete)
    assert exc.value.code == "MISSING_FIELD"

    floatish = {**fca.WEAKEST_ENVELOPE, "origin": 1.5}
    with pytest.raises(fca.FcaError) as exc:
        fca.EvidenceEnvelope.from_mapping(floatish)
    assert exc.value.code == "FORBIDDEN_FLOAT"

    arrayish = {**fca.WEAKEST_ENVELOPE, "proof": ["verified"]}
    with pytest.raises(fca.FcaError) as exc:
        fca.EvidenceEnvelope.from_mapping(arrayish)
    assert exc.value.code == "INVALID_TYPE"


# ---------------------------------------------------------------------------
# Normative vectors
# ---------------------------------------------------------------------------


def test_passes_all_normative_vectors(
    rules: dict[str, Any],
    vectors: dict[str, Any],
) -> None:
    assert vectors["schema"] == fca.VECTORS_SCHEMA
    assert len(vectors["positive_vectors"]) >= 40
    assert len(vectors["negative_vectors"]) >= 20
    assert len(vectors["mutation_vectors"]) >= 10

    counts = fca.evaluate_all_normative_vectors(rules, vectors)
    assert counts["accept"] == len(vectors["positive_vectors"])
    assert counts["reject"] == (
        len(vectors["negative_vectors"]) + len(vectors["mutation_vectors"])
    )


def test_positive_and_negative_vectors_individually(
    rules: dict[str, Any],
    vectors: dict[str, Any],
) -> None:
    for case in vectors["positive_vectors"]:
        fca.evaluate_positive_vector(rules, vectors, case)

    for case in vectors["negative_vectors"]:
        code = fca.evaluate_negative_vector(rules, vectors, case)
        assert fca.codes_match(code, case["error_code"]), (
            f"{case['id']}: expected {case['error_code']}, got {code}"
        )


def test_mutation_vectors_reject_with_stable_codes(
    rules: dict[str, Any],
    vectors: dict[str, Any],
) -> None:
    for case in vectors["mutation_vectors"]:
        code = fca.evaluate_mutation_vector(rules, vectors, case)
        assert fca.codes_match(code, case["error_code"]), (
            f"{case['id']}: expected {case['error_code']}, got {code}"
        )


# ---------------------------------------------------------------------------
# Illegal transitions / gated success types
# ---------------------------------------------------------------------------


def test_illegal_transitions_cannot_construct_production_success(
    rules: dict[str, Any],
) -> None:
    bag = fca.EvidenceBag.all_normative()

    fixture = fca.EvidenceEnvelope.strong_product().with_dimension("origin", "fixture")
    with pytest.raises(fca.FcaError) as exc:
        fca.transition_allowed(rules, "origin", "fixture", "live_observed", bag)
    assert "NONIMP_FIXTURE_TO_OBSERVED" in exc.value.code

    with pytest.raises(fca.FcaError):
        fca.ProductionSuccessClaim.try_admit(fixture, bag, rules)
    with pytest.raises(fca.FcaError):
        fca.VerifiedClaim.try_admit(fixture, bag, rules)

    hermetic = fca.EvidenceEnvelope.weakest()
    with pytest.raises(fca.FcaError) as exc:
        fca.apply_transition(rules, hermetic, "environment", "live", bag)
    assert "NONIMP_HERMETIC_TO_LIVE" in exc.value.code

    expired = fca.EvidenceEnvelope.strong_product().with_dimension(
        "authority", "expired"
    )
    with pytest.raises(fca.FcaError) as exc:
        fca.apply_transition(rules, expired, "authority", "valid", bag)
    assert "FORBIDDEN_RELABEL" in exc.value.code
    with pytest.raises(fca.FcaError):
        fca.ProductionSuccessClaim.try_admit(expired, bag, rules)

    stale = fca.EvidenceEnvelope.strong_product().with_dimension("freshness", "stale")
    with pytest.raises(fca.FcaError) as exc:
        fca.apply_transition(rules, stale, "freshness", "current", bag)
    assert "NONIMP_STALE_TO_CURRENT" in exc.value.code

    empty = fca.EvidenceBag.empty()
    with pytest.raises(fca.FcaError) as exc:
        fca.transition_allowed(rules, "proof", "candidate", "verified", empty)
    assert "NONIMP_CANDIDATE_TO_VERIFIED" in exc.value.code or (
        "MISSING_TRANSITION_EVIDENCE" in exc.value.code
    )

    with_verifier = fca.EvidenceBag.from_keys(
        ["named_current_verifier", "verifier_admission_closure"]
    )
    fca.transition_allowed(rules, "proof", "candidate", "verified", with_verifier)

    strong = fca.EvidenceEnvelope.strong_product()
    success = fca.ProductionSuccessClaim.try_admit(strong, bag, rules)
    assert success.outcome == "Verified"
    assert success.envelope == strong
    verified = fca.VerifiedClaim.try_admit(strong, bag, rules)
    assert verified.outcome == "Verified"
    assert verified.envelope == strong


def test_unknown_transition_rejected(rules: dict[str, Any]) -> None:
    with pytest.raises(fca.FcaError) as exc:
        fca.transition_allowed(rules, "origin", "absent", "absent", [])
    assert exc.value.code.startswith("UNKNOWN_TRANSITION")


# ---------------------------------------------------------------------------
# Compatibility construction
# ---------------------------------------------------------------------------


def test_compatibility_construction_is_conservative(rules: dict[str, Any]) -> None:
    success = fca.map_legacy_claim({"success": True})
    assert success.unsafe_promotion is False
    assert success.closed_outcome in {"Unavailable", "Attempted", "Unknown", "Simulated"}
    assert success.envelope.effect in {"not_started", "started"}
    assert success.envelope.effect != "observed"
    assert success.envelope.proof != "verified"
    with pytest.raises(fca.FcaError):
        fca.predicate_holds(
            "production_supported",
            success.envelope,
            fca.EvidenceBag.all_normative(),
            rules,
        )

    verified_bool = fca.map_legacy_claim({"verified": True})
    assert verified_bool.envelope.proof == "candidate"
    assert verified_bool.envelope.proof != "verified"

    available = fca.map_legacy_claim({"available": True})
    assert "discovery" in available.claim_tokens
    assert available.closed_outcome == "Unavailable"

    ladder = fca.map_legacy_claim(
        {"assurance_level": "attested"},
        seed_id="seed:ladder-accelerate-assurance-level",
    )
    assert ladder.envelope.proof == "verified"
    # Proof-only: other dimensions stay weakest — cannot admit production success.
    assert ladder.envelope.origin == "absent"
    assert ladder.envelope.environment == "hermetic"
    with pytest.raises(fca.FcaError):
        fca.ProductionSuccessClaim.try_admit(
            ladder.envelope, fca.EvidenceBag.all_normative(), rules
        )

    repair = fca.map_legacy_claim(
        {"assurance_level": "heuristic"},
        seed_id="seed:ladder-accelerate-database-repair-assurance-level",
    )
    assert repair.envelope.proof == "candidate"

    proof_status = fca.map_legacy_claim(
        {"proof_status": "stale"},
        seed_id="seed:ladder-accelerate-proof-status",
    )
    assert proof_status.envelope.freshness == "stale"
    assert proof_status.envelope.proof == "unknown"

    tier = fca.map_legacy_claim(
        {"tier": "conditional"},
        seed_id="seed:ladder-kit-backend-support-tier",
    )
    assert tier.envelope.environment == "conditional"
    assert tier.envelope.origin != "live_observed"
    with pytest.raises(fca.FcaError):
        fca.predicate_holds(
            "production_supported",
            tier.envelope,
            fca.EvidenceBag.all_normative(),
            rules,
        )

    mock = fca.map_legacy_claim({"mock": True})
    assert mock.envelope.origin == "simulated"
    assert mock.closed_outcome == "Simulated"

    browser = fca.map_legacy_claim({"browser_consent": True})
    assert browser.envelope.authority == "unchecked"
    assert browser.envelope.policy == "unchecked"


# ---------------------------------------------------------------------------
# Cold import (no network / process / write)
# ---------------------------------------------------------------------------


def test_cold_import_without_network_process_or_write_effects() -> None:
    """Import the binding in a child process under side-effect guards."""
    tests_py = str(_TESTS_PY)
    script = r"""
import builtins
import socket
import sys

sys.path.insert(0, %r)

real_open = builtins.open

def guarded_open(file, mode="r", *args, **kwargs):
    mode_str = str(mode)
    if any(c in mode_str for c in "wxa"):
        raise AssertionError(f"write open during import: {file!r} mode={mode_str!r}")
    return real_open(file, mode, *args, **kwargs)

class ForbiddenSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        raise AssertionError("socket during import")

builtins.open = guarded_open
socket.socket = ForbiddenSocket
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(
    AssertionError("create_connection during import")
)

# Block nested process creation inside the import path.
import subprocess as _sp
def _forbidden(*a, **k):
    raise AssertionError("subprocess during import")
_sp.Popen = _forbidden
_sp.run = _forbidden
_sp.call = _forbidden
_sp.check_call = _forbidden
_sp.check_output = _forbidden

import validators.formal_claim_algebra as m
assert m.TASK_ID == "FACP-017"
assert m.BUNDLE == "facp/fca/python"
weakest = m.EvidenceEnvelope.weakest()
assert weakest.origin == "absent"
_ = weakest.to_canonical_json()
compat = m.map_legacy_claim({"success": True})
assert compat.unsafe_promotion is False
print("cold-import-ok")
""" % (tests_py,)

    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        f"cold import failed:\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
    assert "cold-import-ok" in proc.stdout


def test_explicit_rules_load_is_offline_file_read_only() -> None:
    """``load_promotion_rules`` reads a local file; no network required."""
    path = fca.default_promotion_rules_path()
    assert path.is_file()
    data = fca.load_promotion_rules(path)
    assert data["schema"] == RULES_SCHEMA
    assert data["unknown_transition_policy"] == "reject"


def test_module_source_has_no_import_time_side_effect_calls() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    ]
    joined = "\n".join(import_lines)
    for snippet in (
        "subprocess",
        "socket",
        "urllib",
        "requests",
        "http.client",
        "os.system",
        "urllib.request",
    ):
        assert snippet not in joined, f"forbidden import: {snippet}"
    # Ensure load helpers exist but are not invoked at module level.
    assert "def load_promotion_rules" in source
    assert "\nload_promotion_rules(" not in source
    assert "\nload_normative_vectors(" not in source

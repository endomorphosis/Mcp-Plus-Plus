"""FACP-009: structural conformance for formal-claim-algebra-v1.

Acceptance (taskboard):
- Vocabulary is closed, bounded, nonoverlapping.
- Explicitly distinguishes discovery / authenticity / truth / observation /
  live qualification.
- Maps every seeded legacy claim without unsafe promotion.

This test does not claim Lean-checked proofs (FACP-011/012 own that).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC_PATH = REPO_ROOT / "Mcp-Plus-Plus" / "docs" / "spec" / "formal-claim-algebra-v1.md"
BASELINE = (
    REPO_ROOT
    / "implementation_plan"
    / "formal_assurance_control_plane"
    / "baseline"
)
CLAIM_INVENTORY_PATH = BASELINE / "claim_inventory.json"
DEFECT_CORPUS_PATH = BASELINE / "defect_corpus.jsonl"

VOCAB_SCHEMA = "facp/formal-claim-algebra-v1@1"
TASK_ID = "FACP-009"
GOAL_ID = "FACP-G110"

REQUIRED_DIMENSIONS = (
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

EPISTEMIC_KEYS = (
    "discovery",
    "authenticity",
    "truth",
    "observation",
    "live_qualification",
)

JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def _load_spec_text() -> str:
    assert SPEC_PATH.is_file(), f"missing FCA spec: {SPEC_PATH}"
    return SPEC_PATH.read_text(encoding="utf-8")


def _extract_vocab(spec_text: str) -> dict[str, Any]:
    matches = JSON_FENCE_RE.findall(spec_text)
    assert matches, "spec must embed a normative JSON vocabulary fence"
    vocab = None
    for raw in matches:
        try:
            candidate = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if candidate.get("schema") == VOCAB_SCHEMA:
            vocab = candidate
            break
    assert vocab is not None, f"no JSON fence with schema {VOCAB_SCHEMA}"
    return vocab


def _load_inventory() -> dict[str, Any]:
    assert CLAIM_INVENTORY_PATH.is_file(), CLAIM_INVENTORY_PATH
    return json.loads(CLAIM_INVENTORY_PATH.read_text(encoding="utf-8"))


def _load_corpus() -> list[dict[str, Any]]:
    assert DEFECT_CORPUS_PATH.is_file(), DEFECT_CORPUS_PATH
    entries: list[dict[str, Any]] = []
    for line_no, line in enumerate(
        DEFECT_CORPUS_PATH.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        entry = json.loads(line)
        assert entry.get("schema") == "facp/defect-corpus-entry@1", line_no
        entries.append(entry)
    return entries


@pytest.fixture(scope="module")
def spec_text() -> str:
    return _load_spec_text()


@pytest.fixture(scope="module")
def vocab(spec_text: str) -> dict[str, Any]:
    return _extract_vocab(spec_text)


@pytest.fixture(scope="module")
def inventory() -> dict[str, Any]:
    return _load_inventory()


@pytest.fixture(scope="module")
def corpus() -> list[dict[str, Any]]:
    return _load_corpus()


def test_spec_identifies_facp_009_and_forbids_lean_proof_claim(
    spec_text: str, vocab: dict[str, Any]
) -> None:
    assert TASK_ID in spec_text
    assert "formal-claim-algebra-v1" in spec_text
    assert vocab["schema"] == VOCAB_SCHEMA
    assert vocab["task_id"] == TASK_ID
    assert vocab["goal_id"] == GOAL_ID
    assert vocab["product_kind"] == "evidence_product"
    assert vocab["total_ladder_forbidden"] is True
    assert vocab["discovery_is_not_completion"] is True
    assert vocab["lean_proof_claimed"] is False
    assert "does **not** claim" in spec_text or "does not claim" in spec_text.lower()


def test_vocabulary_is_closed_bounded_and_matches_inventory(
    vocab: dict[str, Any], inventory: dict[str, Any]
) -> None:
    expected = inventory["canonical_claim_vocabulary"]
    dims = vocab["evidence_dimensions"]
    assert tuple(vocab["dimension_order"]) == REQUIRED_DIMENSIONS
    assert set(dims) == set(REQUIRED_DIMENSIONS)

    for name in REQUIRED_DIMENSIONS:
        values = dims[name]
        assert isinstance(values, list) and values, name
        assert len(values) == len(set(values)), f"duplicate values in {name}"
        assert values == expected["evidence_dimensions"][name]
        # Bounded: every constructor is a non-empty token.
        for value in values:
            assert isinstance(value, str) and value.strip() == value and value

    assert vocab["closed_outcomes"] == expected["closed_outcomes"]
    assert vocab["promotion_predicates"] == expected["promotion_predicates"]
    assert (
        vocab["forbidden_generic_fields_on_migrated_paths"]
        == expected["forbidden_generic_fields_on_migrated_paths"]
    )
    assert vocab["roadmap_defect_families"] == expected["roadmap_defect_families"]


def test_dimensions_are_nonoverlapping_typed_concerns(
    vocab: dict[str, Any], spec_text: str
) -> None:
    """Shared spellings across dimensions must remain distinct typed concerns."""
    dims = vocab["evidence_dimensions"]
    # Documented shared spellings that must not be collapsed.
    assert "absent" in dims["origin"] and "absent" in dims["authority"]
    assert "unchecked" in dims["integrity"]
    assert "unchecked" in dims["authority"]
    assert "unchecked" in dims["policy"]
    assert "denied" in dims["authority"] and "denied" in dims["policy"]

    lowered = spec_text.lower()
    assert "nonoverlapping" in lowered or "non-overlapping" in lowered
    assert "not interchangeable" in lowered or "do not imply each other" in lowered
    assert vocab["total_ladder_forbidden"] is True
    # No normative total order over the product.
    assert "never a single total ladder" in lowered or "never a single" in lowered


def test_epistemic_distinctions_are_explicit(vocab: dict[str, Any], spec_text: str) -> None:
    distinctions = vocab["epistemic_distinctions"]
    assert tuple(distinctions) == EPISTEMIC_KEYS

    discovery = distinctions["discovery"]
    assert discovery["may_set"] == []
    for banned in (
        "proof.verified",
        "effect.observed",
        "origin.live_observed",
        "authority.valid",
        "freshness.current",
    ):
        assert banned in discovery["must_not_set"]

    assert distinctions["authenticity"]["dimension"] == "integrity"
    assert "proof.verified" in distinctions["authenticity"]["must_not_imply"]

    assert distinctions["truth"]["dimension"] == "proof"
    assert "effect.observed" in distinctions["truth"]["must_not_imply"]

    assert "effect" in distinctions["observation"]["dimensions"]
    assert "effect.observed" in distinctions["observation"]["requires_for_production_success"]

    live = distinctions["live_qualification"]
    for req in ("environment.live", "origin.live_observed", "freshness.current"):
        assert req in live["requires"]
    assert live["zero_live_qualified_backends_is_honest_non_live"] is True

    # Prose sections must name each distinction.
    for key in EPISTEMIC_KEYS:
        needle = key.replace("_", " ")
        assert needle in spec_text.lower(), f"missing prose distinction: {key}"


def test_non_implications_cover_terminal_safety_bans(vocab: dict[str, Any]) -> None:
    pairs = {(row["from"], row["to"]) for row in vocab["non_implications"]}
    required = {
        ("origin.fixture", "origin.live_observed"),
        ("origin.simulated", "origin.live_observed"),
        ("integrity.digest_valid", "proof.verified"),
        ("payment_or_confirmation", "authority.valid"),
        ("browser_policy_consent_allow", "policy.allowed"),
        ("proof.candidate", "proof.verified"),
        ("environment.hermetic", "environment.live"),
        ("inventory_or_configuration_support", "live_qualification"),
        ("freshness.stale", "freshness.current"),
        ("discovery", "completion_or_live_qualification"),
    }
    missing = required - pairs
    assert not missing, f"missing non-implications: {sorted(missing)}"
    assert len(vocab["non_implications"]) >= 12


def test_forbidden_generic_fields_mapped_without_unsafe_promotion(
    vocab: dict[str, Any],
) -> None:
    mappings = vocab["legacy_claim_mappings"]
    assert mappings["unsafe_promotion_default"] is False
    fields = mappings["forbidden_generic_fields"]
    for name in vocab["forbidden_generic_fields_on_migrated_paths"]:
        row = fields[name]
        assert row["unsafe_promotion"] is False, name
        assert "informs" in row and isinstance(row["informs"], list)


def test_every_seeded_corpus_claim_is_mapped_without_unsafe_promotion(
    vocab: dict[str, Any], corpus: list[dict[str, Any]]
) -> None:
    mappings = vocab["legacy_claim_mappings"]
    by_seed = mappings["by_seed_id"]
    by_family = mappings["by_family"]

    assert set(by_family) == set(vocab["roadmap_defect_families"])
    for family, row in by_family.items():
        assert row.get("unsafe_promotion") is False, family

    for seed_id, row in by_seed.items():
        assert row.get("unsafe_promotion") is False, seed_id
        informs = set(row.get("informs") or [])
        # Ladder adaptations may inform at most proof (+ freshness for ProofStatus)
        # or discovery for support tiers — never the full product.
        assert informs <= {
            "proof",
            "freshness",
            "discovery",
        }, seed_id
        must_not_fill = set(row.get("must_not_fill") or [])
        # If a mapping fills only a subset of dimensions, the rest must be listed
        # as must-not-fill OR the mapping is discovery-only.
        if "proof" in informs and "discovery" not in informs:
            for dim in REQUIRED_DIMENSIONS:
                if dim in informs:
                    continue
                assert dim in must_not_fill, f"{seed_id} must not fill {dim}"

    assert corpus, "defect corpus unexpectedly empty"
    unmapped: list[str] = []
    unsafe: list[str] = []
    for entry in corpus:
        seed_id = entry["seed_id"]
        family = entry["family"]
        row = by_seed.get(seed_id) or by_family.get(family)
        if row is None:
            unmapped.append(seed_id)
            continue
        if row.get("unsafe_promotion", True) is not False:
            unsafe.append(seed_id)

    assert not unmapped, f"unmapped seeded legacy claims: {unmapped[:20]}"
    assert not unsafe, f"unsafe promotion mappings: {unsafe[:20]}"


def test_explicit_ladder_seeds_have_conservative_value_maps(
    vocab: dict[str, Any], corpus: list[dict[str, Any]]
) -> None:
    ladder_seeds = [
        e["seed_id"] for e in corpus if e["family"] == "total_assurance_ladder"
    ]
    assert ladder_seeds, "expected total_assurance_ladder seeds from FACP-008"
    by_seed = vocab["legacy_claim_mappings"]["by_seed_id"]
    for seed_id in ladder_seeds:
        assert seed_id in by_seed, seed_id
        row = by_seed[seed_id]
        assert row["unsafe_promotion"] is False
        if seed_id == "seed:ladder-kit-backend-support-tier":
            assert "discovery" in row["informs"]
            assert "production_supported" in row.get("forbidden_predicates", [])
        else:
            assert "proof" in row["informs"]
            assert "value_map" in row


def test_kit_honest_distinctions_are_mapped(vocab: dict[str, Any]) -> None:
    kit = vocab["legacy_claim_mappings"]["kit_honest_distinctions"]
    required = {
        "kernel_vfs_claim_classes",
        "backend_support_tiers",
        "configured_selected_states",
        "proof_roles",
        "cas_wal_recovery",
        "receipt_freshness",
    }
    assert set(kit) == required
    for name, row in kit.items():
        assert row["unsafe_promotion"] is False, name
        assert row.get("informs") is not None


def test_live_qualification_seed_cannot_promote_from_hermetic(
    vocab: dict[str, Any], corpus: list[dict[str, Any]]
) -> None:
    seed = next(
        e for e in corpus if e["seed_id"] == "seed:kit-zero-live-qualified-backends-honest"
    )
    family_row = vocab["legacy_claim_mappings"]["by_family"][seed["family"]]
    assert family_row["unsafe_promotion"] is False
    assert "production_supported" in family_row.get("forbidden_predicates", [])
    live = vocab["epistemic_distinctions"]["live_qualification"]
    assert live["zero_live_qualified_backends_is_honest_non_live"] is True


def test_promotion_predicates_named_but_not_satisfied_by_legacy_ranks(
    vocab: dict[str, Any], spec_text: str
) -> None:
    preds = vocab["promotion_predicates"]
    assert preds == [
        "production_supported",
        "effect_successful",
        "proof_reusable",
        "receipt_authoritative",
        "release_admissible",
    ]
    lowered = spec_text.lower()
    assert "legacy total-ladder rank alone never satisfies" in lowered or (
        "never satisfies any of these predicates" in lowered
    )


def test_value_maps_only_use_closed_proof_and_freshness_constructors(
    vocab: dict[str, Any],
) -> None:
    proof_vals = set(vocab["evidence_dimensions"]["proof"])
    freshness_vals = set(vocab["evidence_dimensions"]["freshness"])
    by_seed = vocab["legacy_claim_mappings"]["by_seed_id"]
    for seed_id, row in by_seed.items():
        value_map = row.get("value_map") or {}
        for legacy, target in value_map.items():
            if isinstance(target, str):
                assert target in proof_vals, f"{seed_id}:{legacy}->{target}"
            elif isinstance(target, dict):
                if "proof" in target:
                    assert target["proof"] in proof_vals, seed_id
                if "freshness" in target:
                    assert target["freshness"] in freshness_vals, seed_id
            else:
                raise AssertionError(f"unexpected value_map target in {seed_id}")

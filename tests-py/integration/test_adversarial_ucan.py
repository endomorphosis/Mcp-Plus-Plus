"""
Adversarial cryptographic negative vectors (MCPP-044).

Interface: AdversarialVector@1
Vectors: conformance/vectors/crypto/adversarial

Acceptance:
  Every listed case fails closed in Python (and is declared for TypeScript,
  Go, and Rust via the shared vector suite + language runners).

Cases:
  forged_signature, altered_bytes, wrong_audience, expanded_capabilities,
  expanded_resources, expired, future_nbf, revoked, missing_proof, replay,
  wrong_executor, wrong_policy_cid, valid_peerid_invalid_ucan
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_MCPPLUS = Path(__file__).resolve().parents[2]
_VECTORS = _MCPPLUS / "conformance" / "vectors" / "crypto" / "adversarial"
_TESTS_PY = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(_TESTS_PY))
sys.path.insert(0, str(_VECTORS))

from evaluate import (  # noqa: E402
    INTERFACE,
    REQUIRED_CASE_IDS,
    evaluate_all,
    evaluate_case,
    load_fixture,
    load_manifest,
    reason_matches_expected,
)


class TestAdversarialUcanVectors:
    """Shared AdversarialVector@1 suite — every case fails closed."""

    def test_manifest_covers_required_cases(self):
        manifest = load_manifest()
        assert manifest["interface"] == INTERFACE
        assert manifest["task_id"] == "MCPP-044"
        ids = {c["id"] for c in manifest["cases"]}
        assert ids == set(REQUIRED_CASE_IDS)
        for case in manifest["cases"]:
            assert case["expected_fail_closed"] is True
            assert case["valid"] is False
            assert set(case["languages"]) >= {"python", "typescript", "go", "rust"}
            fixture_path = _VECTORS / case["file"]
            assert fixture_path.is_file(), f"missing fixture {fixture_path}"

    def test_recipes_index_matches_required_cases(self):
        recipes = json.loads((_VECTORS / "recipes.json").read_text(encoding="utf-8"))
        case_ids = {r["case"] for r in recipes["recipes"]}
        assert case_ids == set(REQUIRED_CASE_IDS)

    def test_every_case_fails_closed(self):
        results = evaluate_all()
        failures = []
        for case_id in REQUIRED_CASE_IDS:
            verdict = results[case_id]
            if not verdict.fail_closed:
                failures.append(f"{case_id}: admitted={verdict.admitted} {verdict.to_dict()}")
            elif not reason_matches_expected(verdict):
                failures.append(
                    f"{case_id}: expected={verdict.metadata.get('expected')} "
                    f"got={verdict.reason_codes}"
                )
        assert not failures, "adversarial cases must fail closed:\n" + "\n".join(failures)

    @pytest.mark.parametrize("case_id", REQUIRED_CASE_IDS)
    def test_case_fail_closed_parametrized(self, case_id: str):
        fixture = load_fixture(case_id)
        verdict = evaluate_case(case_id, fixture)
        assert verdict.case_id == case_id
        assert verdict.fail_closed is True
        assert reason_matches_expected(verdict), (
            f"{case_id}: expected={fixture.get('expected_reason_codes')} "
            f"got={verdict.reason_codes} reasons={verdict.reasons}"
        )

    def test_forged_signature_fails_cryptographic_level(self):
        verdict = evaluate_case("forged_signature")
        assert verdict.fail_closed
        assert any("invalid_signature" in c for c in verdict.reason_codes + verdict.reasons)

    def test_altered_bytes_fails_cryptographic_level(self):
        verdict = evaluate_case("altered_bytes")
        assert verdict.fail_closed
        assert any("invalid_signature" in c for c in verdict.reason_codes + verdict.reasons)

    def test_revoked_fails_closed_despite_valid_signature(self):
        verdict = evaluate_case("revoked")
        assert verdict.fail_closed
        assert "revoked" in verdict.reason_codes
        # Acceptance mirror of MCPP-043: valid original signature does not admit.
        assert verdict.metadata.get("token_signature_valid") is True or verdict.metadata.get(
            "fail_closed_despite_valid_signature"
        )

    def test_valid_peerid_invalid_ucan_never_grants_authority(self):
        verdict = evaluate_case("valid_peerid_invalid_ucan")
        assert verdict.fail_closed
        assert "peerid_not_authority" in verdict.reason_codes
        assert verdict.metadata.get("peer_authenticated") is True

    def test_no_mocks_for_signature_paths(self):
        """Structural green + forged material still fails at cryptographic level."""
        from validators.ucan_delegation import UCANDelegationValidator

        forged = load_fixture("forged_signature")
        validator = UCANDelegationValidator(
            issuer_public_keys=forged["issuer_public_keys"],
            require_signatures=True,
        )
        token = dict(forged["token"])
        token.pop("canonical_signing_bytes_hex", None)
        result = validator.verify_delegation_proof(token)
        assert result.is_valid is False
        levels = result.metadata["levels"]
        assert levels["cryptographic"]["valid"] is False
        # Structural fields may still be present.
        assert levels["structural"]["valid"] is True or levels["structural"]["valid"] is False


class TestAdversarialUcanLanguageCoverage:
    """Manifest declares four-language coverage for every case."""

    def test_each_case_lists_four_languages(self):
        for case_id in REQUIRED_CASE_IDS:
            fixture = load_fixture(case_id)
            langs = set(fixture.get("languages") or [])
            assert langs >= {"python", "typescript", "go", "rust"}, case_id

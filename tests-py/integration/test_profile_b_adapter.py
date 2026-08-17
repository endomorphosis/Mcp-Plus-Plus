"""
Integration tests for ProfileBAdapter@1 (MCPP-031).

Interface: ProfileBAdapter@1
Validator: tests-py/validators/envelope_profile_b.py
Vectors: conformance/vectors/envelope/profile-b-adapter.json

Acceptance:
  Historical B CIDs still verify. Adapter output validates as Envelope@1.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from validators.envelope_profile_b import (  # noqa: E402
    INTERFACE,
    SCHEMA_ENVELOPE,
    SCHEMA_RECEIPT,
    ProfileBAdapter,
    adapt_and_validate_envelope,
    adapt_and_validate_receipt,
    historical_cid_unchanged,
    load_adapter_vectors,
    run_all_vector_cases,
    test_profile_b_adapter_composite_runtime_envelope,
    test_profile_b_adapter_envelope_validates_as_envelope_v1,
    test_profile_b_adapter_execution_receipt_vector,
    test_profile_b_adapter_failed_receipt_maps_portable_error,
    test_profile_b_adapter_historical_b_validator_still_accepts,
    test_profile_b_adapter_interface_constant,
    test_profile_b_adapter_receipt_validates_as_receipt_v1,
    test_profile_b_adapter_vectors_file,
    verify_historical_envelope,
    verify_historical_receipt,
)


class TestProfileBAdapterInterface:
    """Surface constants and facade."""

    def test_profile_b_adapter_interface_constant(self):
        test_profile_b_adapter_interface_constant()
        assert ProfileBAdapter().interface == INTERFACE

    def test_schema_markers(self):
        assert SCHEMA_ENVELOPE == "mcp++/execution/envelope@1"
        assert SCHEMA_RECEIPT == "mcp++/execution/receipt@1"


class TestProfileBAdapterEnvelope:
    """Envelope adaptation + Envelope@1 structural validation."""

    def test_profile_b_adapter_envelope_validates_as_envelope_v1(self):
        test_profile_b_adapter_envelope_validates_as_envelope_v1()

    def test_profile_b_adapter_composite_runtime_envelope(self):
        test_profile_b_adapter_composite_runtime_envelope()

    def test_profile_b_adapter_historical_b_validator_still_accepts(self):
        test_profile_b_adapter_historical_b_validator_still_accepts()


class TestProfileBAdapterReceipt:
    """Receipt adaptation + Receipt@1 structural validation."""

    def test_profile_b_adapter_receipt_validates_as_receipt_v1(self):
        test_profile_b_adapter_receipt_validates_as_receipt_v1()

    def test_profile_b_adapter_execution_receipt_vector(self):
        test_profile_b_adapter_execution_receipt_vector()

    def test_profile_b_adapter_failed_receipt_maps_portable_error(self):
        test_profile_b_adapter_failed_receipt_maps_portable_error()


class TestProfileBAdapterVectors:
    """Conformance vector suite."""

    def test_profile_b_adapter_vectors_file(self):
        test_profile_b_adapter_vectors_file()

    def test_profile_b_adapter_vector_cases_parametrized(self):
        data = load_adapter_vectors()
        assert data.get("interface") == INTERFACE
        for case_id, result in run_all_vector_cases(data):
            assert result.ok, f"{case_id}: {result.errors}"
            if result.historical_kind == "envelope" and result.historical_cid:
                assert historical_cid_unchanged(
                    result.historical_cid, result.adapted, kind="envelope"
                )
            if result.historical_kind == "receipt" and result.historical_cid:
                assert historical_cid_unchanged(
                    result.historical_cid, result.adapted, kind="receipt"
                )


@pytest.mark.parametrize(
    "case",
    load_adapter_vectors().get("cases") or [],
    ids=lambda c: c.get("id", "case"),
)
def test_profile_b_adapter_case(case):
    """One pytest node per conformance vector case."""
    from validators.envelope_profile_b import run_vector_case

    result = run_vector_case(case)
    assert result.ok, f"{case.get('id')}: {result.errors}"

"""
Integration tests for ProfileGAdapter@1 (MCPP-032).

Interface: ProfileGAdapter@1
Validator: tests-py/validators/envelope_profile_g.py
Vectors: conformance/vectors/envelope/profile-g-adapter.json

Acceptance:
  Historical G CIDs still verify. Adapter output validates as Envelope@1.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from validators.envelope_profile_g import (  # noqa: E402
    INTERFACE,
    SCHEMA_ENVELOPE,
    SCHEMA_RECEIPT,
    ProfileGAdapter,
    adapt_and_validate_envelope,
    adapt_and_validate_receipt,
    historical_cid_unchanged,
    load_adapter_vectors,
    run_all_vector_cases,
    test_profile_g_adapter_artifacts_valid_suite_still_verifies,
    test_profile_g_adapter_envelope_validates_as_envelope_v1,
    test_profile_g_adapter_failed_receipt_maps_portable_error,
    test_profile_g_adapter_fenced_failure_class,
    test_profile_g_adapter_historical_g_validator_still_accepts,
    test_profile_g_adapter_interface_constant,
    test_profile_g_adapter_receipt_validates_as_receipt_v1,
    test_profile_g_adapter_task_with_claim_context,
    test_profile_g_adapter_vectors_file,
    verify_historical_task_receipt,
    verify_historical_task_spec,
)


class TestProfileGAdapterInterface:
    """Surface constants and facade."""

    def test_profile_g_adapter_interface_constant(self):
        test_profile_g_adapter_interface_constant()
        assert ProfileGAdapter().interface == INTERFACE

    def test_schema_markers(self):
        assert SCHEMA_ENVELOPE == "mcp++/execution/envelope@1"
        assert SCHEMA_RECEIPT == "mcp++/execution/receipt@1"


class TestProfileGAdapterEnvelope:
    """TaskSpec adaptation + Envelope@1 structural validation."""

    def test_profile_g_adapter_envelope_validates_as_envelope_v1(self):
        test_profile_g_adapter_envelope_validates_as_envelope_v1()

    def test_profile_g_adapter_task_with_claim_context(self):
        test_profile_g_adapter_task_with_claim_context()

    def test_profile_g_adapter_historical_g_validator_still_accepts(self):
        test_profile_g_adapter_historical_g_validator_still_accepts()


class TestProfileGAdapterReceipt:
    """TaskReceipt adaptation + Receipt@1 structural validation."""

    def test_profile_g_adapter_receipt_validates_as_receipt_v1(self):
        test_profile_g_adapter_receipt_validates_as_receipt_v1()

    def test_profile_g_adapter_failed_receipt_maps_portable_error(self):
        test_profile_g_adapter_failed_receipt_maps_portable_error()

    def test_profile_g_adapter_fenced_failure_class(self):
        test_profile_g_adapter_fenced_failure_class()


class TestProfileGAdapterVectors:
    """Conformance vector suite."""

    def test_profile_g_adapter_vectors_file(self):
        test_profile_g_adapter_vectors_file()

    def test_profile_g_adapter_artifacts_valid_suite_still_verifies(self):
        test_profile_g_adapter_artifacts_valid_suite_still_verifies()

    def test_profile_g_adapter_vector_cases_parametrized(self):
        data = load_adapter_vectors()
        assert data.get("interface") == INTERFACE
        for case_id, result in run_all_vector_cases(data):
            assert result.ok, f"{case_id}: {result.errors}"
            if result.historical_kind == "task_receipt" and result.historical_cid:
                if result.adapted:
                    assert historical_cid_unchanged(
                        result.historical_cid, result.adapted, kind="TaskReceipt"
                    )


@pytest.mark.parametrize(
    "case",
    load_adapter_vectors().get("cases") or [],
    ids=lambda c: c.get("id", "case"),
)
def test_profile_g_adapter_case(case):
    """One pytest node per conformance vector case."""
    from validators.envelope_profile_g import run_vector_case

    result = run_vector_case(case)
    assert result.ok, f"{case.get('id')}: {result.errors}"

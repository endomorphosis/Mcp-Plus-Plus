"""
Integration tests for RevocationRecord@1 (MCPP-043).

Interface: RevocationRecord@1
Schema: schemas/delegation/revocation-record-1.schema.json
Validator: tests-py/validators/revocation.py

Acceptance:
  Revoked delegations fail closed even if the signature on the original token
  is valid.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from validators.revocation import (  # noqa: E402
    HAVE_CRYPTO_ED25519,
    INTERFACE,
    SCHEMA_MARKER,
    RevocationLedger,
    RevocationRecordValidator,
    extract_delegation_identifiers,
    load_schema,
    make_signed_revocation_record,
    test_revocation_chain_proof_cid_membership,
    test_revocation_durable_ledger_roundtrip,
    test_revocation_fail_closed_despite_valid_token_signature,
    test_revocation_record_signed_and_discoverable,
    test_revocation_require_ledger_unavailable_fails_closed,
    test_revocation_schema_marker_and_load,
    test_revocation_swissknife_alias_normalization,
    test_revocation_tampered_record_signature_fails,
    test_revocation_unsigned_record_fails_cryptographic_level,
)


class TestRevocationRecordInterface:
    """Structural + cryptographic RevocationRecord@1 surface."""

    def test_interface_constant(self):
        assert INTERFACE == "RevocationRecord@1"
        assert SCHEMA_MARKER == "mcp++/delegation/revocation-record@1"

    def test_revocation_schema_marker_and_load(self):
        test_revocation_schema_marker_and_load()

    def test_revocation_record_signed_and_discoverable(self):
        test_revocation_record_signed_and_discoverable()

    def test_revocation_unsigned_record_fails_cryptographic_level(self):
        test_revocation_unsigned_record_fails_cryptographic_level()

    def test_revocation_tampered_record_signature_fails(self):
        test_revocation_tampered_record_signature_fails()

    def test_revocation_swissknife_alias_normalization(self):
        test_revocation_swissknife_alias_normalization()


class TestRevocationFailClosed:
    """Execution-time fail-closed behaviour (acceptance criterion)."""

    def test_revocation_fail_closed_despite_valid_token_signature(self):
        test_revocation_fail_closed_despite_valid_token_signature()

    def test_revocation_chain_proof_cid_membership(self):
        test_revocation_chain_proof_cid_membership()

    def test_unrevoked_delegation_is_not_denied_by_empty_ledger(self):
        ledger = RevocationLedger()
        validator = RevocationRecordValidator(ledger=ledger)
        token = {
            "iss": "did:key:root",
            "aud": "did:key:agent",
            "att": [{"can": "tool/execute"}],
            "exp": 9999999999,
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        }
        decision = validator.evaluate_delegation(token, token_signature_valid=True)
        assert decision.allowed
        assert decision.reason == "ok"

    def test_extract_identifiers_covers_cid_and_nonce(self):
        ids = extract_delegation_identifiers(
            {
                "cid": "token-cid-1",
                "nonce": "n-1",
                "prf": ["proof-a", "proof-b"],
            }
        )
        assert "token-cid-1" in ids
        assert "n-1" in ids
        assert "proof-a" in ids


class TestRevocationLedger:
    """Durable ledger + discovery semantics."""

    def test_revocation_durable_ledger_roundtrip(self, tmp_path):
        test_revocation_durable_ledger_roundtrip(tmp_path)

    def test_revocation_require_ledger_unavailable_fails_closed(self, tmp_path):
        test_revocation_require_ledger_unavailable_fails_closed(tmp_path)

    def test_discovery_filters_by_method(self):
        if not HAVE_CRYPTO_ED25519:
            pytest.skip("ed25519 unavailable")
        revoked = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
        record, _pub, issuer = make_signed_revocation_record(
            revoked_cid=revoked,
            discovery={"method": "registry", "registry_id": "sk-ucan"},
        )
        ledger = RevocationLedger()
        validator = RevocationRecordValidator(ledger=ledger)
        assert validator.admit_record(record).is_valid
        assert validator.discover_records(method="registry")
        assert not validator.discover_records(method="gossip")
        assert validator.discover_records(issuer=issuer)


class TestRevocationSchemaContract:
    def test_schema_documents_required_effects_fields(self):
        schema = load_schema()
        props = schema["properties"]
        for name in (
            "issuer",
            "revoked_delegation_cid",
            "effective_at",
            "reason",
            "replacement_cid",
            "signature",
            "discovery",
        ):
            assert name in props, name

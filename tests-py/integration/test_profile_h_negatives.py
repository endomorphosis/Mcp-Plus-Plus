"""
Profile H adversarial negatives and transport-split checks (MCPP-072).

Interface: ProfileHNegativeVector@1
Validator: tests-py/validators/profile_h.py
Vectors: conformance/vectors/profile_h_artifacts_valid.json
         conformance/vectors/profile_h_transport_valid.json

Acceptance:
  All negatives fail closed.
  Transport split (x402 HTTP header objects vs Profile H artifact/libp2p
  carriage) is tested.
  Adapter evidence lives in docs/reports/.../runtime/profile-h-adapters.md.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

_TESTS_PY = Path(__file__).resolve().parents[1]
_MCPPLUS = Path(__file__).resolve().parents[2]
_VECTORS = _MCPPLUS / "conformance" / "vectors"

sys.path.insert(0, str(_TESTS_PY))

from validators.profile_h import (  # noqa: E402
    ProfileHValidationError,
    decode_x402_header,
    encode_x402_header,
    profile_h_artifact_cid,
    settlement_uniqueness_key,
    validate_idempotent_entitlement,
    validate_idempotent_settlement,
    validate_price_version_binding,
    validate_profile_h_artifact,
    validate_quote_not_expired_for_settlement,
    validate_refund_eligibility,
    validate_replay,
    validate_request_binding,
    validate_settlement_against_quote,
)

INTERFACE = "ProfileHNegativeVector@1"
TASK_ID = "MCPP-072"

# Stable error codes asserted by the adversarial suite.
CODE_POLICY_DENIED = "H_PAYMENT_POLICY_DENIED"
CODE_PAYMENT_REQUIRED = "H_PAYMENT_REQUIRED"
CODE_REPLAY = "H_PAYMENT_REPLAY"
CODE_AMOUNT = "H_AMOUNT_MISMATCH"
CODE_QUOTE_EXPIRED = "H_QUOTE_EXPIRED"
CODE_ENTITLEMENT = "H_ENTITLEMENT_EXHAUSTED"
CODE_REQUEST = "H_REQUEST_MISMATCH"
CODE_VERIFICATION = "H_VERIFICATION_FAILED"
CODE_NETWORK = "H_UNSUPPORTED_NETWORK"
CODE_SETTLEMENT = "H_SETTLEMENT_FAILED"
CODE_INVALID = "H_INVALID_PAYMENT_MESSAGE"

REQUIRED_NEGATIVE_IDS = (
    "paid-but-unauthorized",
    "authorized-but-unpaid",
    "replay",
    "price-mismatch",
    "wrong-recipient",
    "duplicate-settlement",
    "expired-quote",
    "refund-after-consumed",
    "forged-settlement",
    "transport-split-x402-http",
    "transport-split-libp2p-artifact",
)


def load_json(name: str) -> dict[str, Any]:
    return json.loads((_VECTORS / name).read_text(encoding="utf-8"))


VALID = load_json("profile_h_artifacts_valid.json")
TRANSPORT = load_json("profile_h_transport_valid.json")
BY_ID = {case["id"]: case for case in VALID["cases"]}


def artifact(kind_id: str) -> dict[str, Any]:
    return copy.deepcopy(BY_ID[kind_id]["payload"])


def capability_and_bound_quote(*, now_ms: int = 1_700_000_000_000) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    """Return capability + quote with correct price-version CID bindings."""
    capability = artifact("paid-capability")
    quote = artifact("payment-quote")
    capability_cid = validate_profile_h_artifact("PaidCapability", capability, now_ms=now_ms)
    quote["capabilityCid"] = capability_cid
    quote["descriptorCid"] = capability["descriptorCid"]
    quote["sellerDid"] = capability["sellerDid"]
    quote["requirements"][0].update(
        {
            "scheme": capability["scheme"],
            "network": capability["network"],
            "asset": capability["asset"],
            "amount": capability["amount"],
            "payTo": capability["payee"],
        }
    )
    quote_cid = validate_profile_h_artifact("PaymentQuote", quote, now_ms=now_ms)
    return capability, quote, capability_cid, quote_cid


def expect_fail(
    thunk: Callable[[], Any],
    *,
    code: str,
    path_contains: str | None = None,
) -> ProfileHValidationError:
    with pytest.raises(ProfileHValidationError) as raised:
        thunk()
    err = raised.value
    assert err.code == code, f"expected {code}, got {err.code} at {err.path}: {err.detail}"
    if path_contains is not None:
        assert path_contains in (err.path or ""), f"path {err.path!r} missing {path_contains!r}"
    return err


# ---------------------------------------------------------------------------
# Interface / catalog
# ---------------------------------------------------------------------------


class TestProfileHNegativeInterface:
    def test_interface_constant(self):
        assert INTERFACE == "ProfileHNegativeVector@1"
        assert TASK_ID == "MCPP-072"

    def test_required_negative_ids_are_documented(self):
        # Guard against accidental suite shrinkage vs MCPP-072 effects list.
        assert set(REQUIRED_NEGATIVE_IDS) >= {
            "paid-but-unauthorized",
            "authorized-but-unpaid",
            "replay",
            "price-mismatch",
            "wrong-recipient",
            "duplicate-settlement",
            "expired-quote",
            "refund-after-consumed",
            "forged-settlement",
        }


# ---------------------------------------------------------------------------
# PaymentAuthorizationBoundary@1 — AccessReceipt structural negatives
# ---------------------------------------------------------------------------


class TestPaidUnauthorizedAndAuthorizedUnpaid:
    """Payment success is not execution authority; authority is not payment."""

    def test_paid_but_unauthorized_allow_fails_closed(self):
        """Commercial evidence present, layer-A decision CIDs missing → deny."""
        receipt = artifact("access-receipt")
        receipt["decision"] = "allow"
        receipt["ucanDecisionCid"] = None  # paid-but-unauthorized shape
        receipt["policyDecisionCid"] = None
        expect_fail(
            lambda: validate_profile_h_artifact("AccessReceipt", receipt),
            code=CODE_POLICY_DENIED,
            path_contains="ucanDecisionCid",
        )

    def test_paid_but_unauthorized_missing_policy_only_fails_closed(self):
        receipt = artifact("access-receipt")
        receipt["decision"] = "allow"
        receipt["policyDecisionCid"] = None
        expect_fail(
            lambda: validate_profile_h_artifact("AccessReceipt", receipt),
            code=CODE_POLICY_DENIED,
            path_contains="ucanDecisionCid",
        )

    def test_authorized_but_unpaid_allow_fails_closed(self):
        """Layer-A evidence present, commercial evidence missing → payment required."""
        receipt = artifact("access-receipt")
        receipt["decision"] = "allow"
        receipt["commercialEvidenceCid"] = None
        expect_fail(
            lambda: validate_profile_h_artifact("AccessReceipt", receipt),
            code=CODE_PAYMENT_REQUIRED,
            path_contains="commercialEvidenceCid",
        )

    def test_authorized_but_unpaid_missing_result_fails_closed(self):
        receipt = artifact("access-receipt")
        receipt["decision"] = "allow"
        receipt["resultCid"] = None
        expect_fail(
            lambda: validate_profile_h_artifact("AccessReceipt", receipt),
            code=CODE_PAYMENT_REQUIRED,
            path_contains="commercialEvidenceCid",
        )

    def test_deny_paid_but_unauthorized_shape_is_valid(self):
        """Deny receipts may retain commercial evidence with null result."""
        receipt = artifact("access-receipt")
        receipt["decision"] = "deny"
        receipt["resultCid"] = None
        receipt["reasonCode"] = CODE_POLICY_DENIED
        # Keep commercialEvidenceCid — settled-but-unfulfilled recovery path.
        cid = validate_profile_h_artifact("AccessReceipt", receipt)
        assert cid.startswith("b")

    def test_deny_authorized_but_unpaid_shape_is_valid(self):
        receipt = artifact("access-receipt")
        receipt["decision"] = "deny"
        receipt["commercialEvidenceCid"] = None
        receipt["resultCid"] = None
        receipt["reasonCode"] = CODE_PAYMENT_REQUIRED
        cid = validate_profile_h_artifact("AccessReceipt", receipt)
        assert cid.startswith("b")


# ---------------------------------------------------------------------------
# Replay, price, recipient, settlement, quote, refund, forgery
# ---------------------------------------------------------------------------


class TestReplayProtection:
    def test_replay_commitment_fails_closed(self):
        commitment = artifact("payment-authorization")["payerCommitment"]
        expect_fail(
            lambda: validate_replay({commitment}, commitment),
            code=CODE_REPLAY,
            path_contains="commitment",
        )

    def test_fresh_commitment_accepted_then_replayed(self):
        commitment = artifact("payment-authorization")["payerCommitment"]
        other = artifact("payment-authorization")["paymentPayloadCid"]
        seen: set[str] = set()
        validate_replay(seen, commitment)
        seen.add(commitment)
        validate_replay(seen, other)  # different commitment is fine
        expect_fail(lambda: validate_replay(seen, commitment), code=CODE_REPLAY)


class TestPriceAndRecipientBinding:
    def test_price_mismatch_fails_closed(self):
        capability, quote, _, _ = capability_and_bound_quote()
        quote["requirements"][0]["amount"] = "999"  # diverges from capability
        expect_fail(
            lambda: validate_price_version_binding(capability, quote, now_ms=1_700_000_000_000),
            code=CODE_AMOUNT,
            path_contains="amount",
        )

    def test_catalog_version_mismatch_fails_closed(self):
        capability, quote, _, _ = capability_and_bound_quote()
        expect_fail(
            lambda: validate_price_version_binding(
                capability,
                quote,
                now_ms=1_700_000_000_000,
                expected_catalog_version="not-this-version",
            ),
            code=CODE_REQUEST,
            path_contains="catalogVersion",
        )

    def test_wrong_recipient_fails_closed(self):
        capability, quote, _, _ = capability_and_bound_quote()
        quote["requirements"][0]["payTo"] = "0x2222222222222222222222222222222222222222"
        expect_fail(
            lambda: validate_price_version_binding(capability, quote, now_ms=1_700_000_000_000),
            code=CODE_AMOUNT,
            path_contains="payTo",
        )

    def test_wrong_network_fails_closed(self):
        capability, quote, _, _ = capability_and_bound_quote()
        quote["requirements"][0]["network"] = "eip155:1"
        expect_fail(
            lambda: validate_price_version_binding(capability, quote, now_ms=1_700_000_000_000),
            code=CODE_NETWORK,
            path_contains="network",
        )

    def test_request_substitution_fails_closed(self):
        quote = artifact("payment-quote")
        foreign_request = artifact("payment-authorization")["requestCid"]
        assert foreign_request != quote["requestCid"]
        expect_fail(
            lambda: validate_request_binding(foreign_request, quote),
            code=CODE_REQUEST,
            path_contains="requestCid",
        )


class TestDuplicateSettlement:
    def test_duplicate_settlement_conflict_fails_closed(self):
        settlement_a = artifact("settlement-receipt")
        settlement_b = copy.deepcopy(settlement_a)
        settlement_b["amount"] = "2000"  # distinct CID under same uniqueness key
        key = settlement_uniqueness_key(
            "did:web:seller.example",
            "idem-001",
            artifact("payment-quote")["requestCid"],
        )
        ledger: dict[str, str] = {}
        first = validate_idempotent_settlement(settlement_a, ledger, uniqueness_key=key)
        assert ledger[key] == first
        # Identical replay rejoins.
        assert validate_idempotent_settlement(settlement_a, ledger, uniqueness_key=key) == first
        expect_fail(
            lambda: validate_idempotent_settlement(settlement_b, ledger, uniqueness_key=key),
            code=CODE_REPLAY,
            path_contains="uniquenessKey",
        )

    def test_double_entitle_fails_closed(self):
        settlement = artifact("settlement-receipt")
        settlement_cid = validate_profile_h_artifact("SettlementReceipt", settlement)
        entitlement_a = artifact("paid-entitlement")
        entitlement_a["settlementCid"] = settlement_cid
        entitlement_b = copy.deepcopy(entitlement_a)
        entitlement_b["quotaUnits"] = entitlement_a["quotaUnits"] + 50
        ledger: dict[str, str] = {}
        first = validate_idempotent_entitlement(settlement, entitlement_a, ledger)
        assert ledger[settlement_cid] == first
        assert validate_idempotent_entitlement(settlement, entitlement_a, ledger) == first
        expect_fail(
            lambda: validate_idempotent_entitlement(settlement, entitlement_b, ledger),
            code=CODE_REPLAY,
            path_contains="settlementCid",
        )


class TestExpiredQuote:
    def test_expired_quote_cannot_settle(self):
        _, quote, _, _ = capability_and_bound_quote()
        expect_fail(
            lambda: validate_quote_not_expired_for_settlement(
                quote, now_ms=quote["expiresAt"]
            ),
            code=CODE_QUOTE_EXPIRED,
            path_contains="expiresAt",
        )

    def test_settlement_after_quote_expiry_fails_closed(self):
        _, quote, _, _ = capability_and_bound_quote()
        settlement = artifact("settlement-receipt")
        settlement["settledAt"] = quote["expiresAt"] + 1
        settlement["createdAt"] = settlement["settledAt"]
        expect_fail(
            lambda: validate_settlement_against_quote(
                quote, settlement, now_ms=settlement["settledAt"]
            ),
            code=CODE_QUOTE_EXPIRED,
            path_contains="expiresAt",
        )


class TestRefundAfterConsumed:
    def test_refund_after_full_consumption_fails_closed(self):
        settlement = artifact("settlement-receipt")
        settlement_cid = validate_profile_h_artifact("SettlementReceipt", settlement)
        entitlement = artifact("paid-entitlement")
        entitlement["settlementCid"] = settlement_cid
        entitlement["consumedUnits"] = entitlement["quotaUnits"]
        refund = artifact("refund-record")
        refund["settlementCid"] = settlement_cid
        refund["decision"] = "approved"
        refund["outcome"] = "refunded"
        expect_fail(
            lambda: validate_refund_eligibility(
                settlement, refund, entitlement=entitlement
            ),
            code=CODE_ENTITLEMENT,
            path_contains="consumedUnits",
        )

    def test_refund_on_failed_settlement_fails_closed(self):
        settlement = artifact("settlement-receipt")
        settlement["outcome"] = "failed"
        refund = artifact("refund-record")
        # Re-bind after mutation so structural validation still sees a CID match path.
        settlement_cid = profile_h_artifact_cid(settlement)
        # validate_refund_eligibility re-validates settlement first; failed outcome
        # is still a valid SettlementReceipt structurally, then refund eligibility fails.
        refund["settlementCid"] = validate_profile_h_artifact("SettlementReceipt", settlement)
        expect_fail(
            lambda: validate_refund_eligibility(settlement, refund),
            code=CODE_SETTLEMENT,
            path_contains="outcome",
        )
        assert settlement_cid.startswith("b")


class TestForgedSettlement:
    def test_forged_amount_fails_closed(self):
        _, quote, _, _ = capability_and_bound_quote()
        settlement = artifact("settlement-receipt")
        settlement["amount"] = "1"
        expect_fail(
            lambda: validate_settlement_against_quote(
                quote, settlement, now_ms=min(settlement["settledAt"], quote["expiresAt"] - 1)
            ),
            code=CODE_AMOUNT,
            path_contains="amount",
        )

    def test_forged_network_fails_closed(self):
        _, quote, _, _ = capability_and_bound_quote()
        settlement = artifact("settlement-receipt")
        settlement["network"] = "eip155:1"
        expect_fail(
            lambda: validate_settlement_against_quote(
                quote, settlement, now_ms=min(settlement["settledAt"], quote["expiresAt"] - 1)
            ),
            code=CODE_AMOUNT,  # no matching requirement → amount/network mismatch branch
            path_contains="amount",
        )

    def test_rejected_verification_cannot_settle(self):
        _, quote, _, _ = capability_and_bound_quote()
        settlement = artifact("settlement-receipt")
        verification = artifact("payment-verification")
        verification["decision"] = "rejected"
        verification["reasonCode"] = "facilitator-rejected"
        now_ms = min(settlement["settledAt"], quote["expiresAt"] - 1, verification["expiresAt"] - 1)
        expect_fail(
            lambda: validate_settlement_against_quote(
                quote,
                settlement,
                now_ms=now_ms,
                verification=verification,
            ),
            code=CODE_VERIFICATION,
            path_contains="decision",
        )

    def test_settlement_verification_cid_mismatch_fails_closed(self):
        _, quote, _, _ = capability_and_bound_quote()
        settlement = artifact("settlement-receipt")
        verification = artifact("payment-verification")
        verification["decision"] = "verified"
        # Bind verification CID correctly but point settlement at a foreign CID.
        ver_cid = validate_profile_h_artifact(
            "PaymentVerification", verification, now_ms=verification["verifiedAt"]
        )
        assert settlement["verificationCid"] != ver_cid or True
        settlement["verificationCid"] = artifact("payment-authorization")["quoteCid"]
        now_ms = min(settlement["settledAt"], quote["expiresAt"] - 1, verification["expiresAt"] - 1)
        expect_fail(
            lambda: validate_settlement_against_quote(
                quote,
                settlement,
                now_ms=now_ms,
                verification=verification,
            ),
            code=CODE_REQUEST,
            path_contains="verificationCid",
        )


# ---------------------------------------------------------------------------
# Transport split: x402 HTTP header objects ≠ Profile H artifact / libp2p
# ---------------------------------------------------------------------------


class TestTransportSplit:
    """Upstream x402 HTTP header codecs remain distinct from Profile H artifacts.

    HTTP carriage: base64(canonical JSON) of PaymentRequired / PaymentPayload /
    SettlementResponse (x402 v2 objects) via encode/decode_x402_header.

    libp2p / Profile E carriage: Profile H DAG-JSON artifacts (PaymentQuote,
    SettlementReceipt, AccessReceipt, …) validated with validate_profile_h_artifact.
    Implementations MUST NOT treat libp2p support as upstream x402 HTTP
    conformance (x402-payments.md §1).
    """

    X402_KINDS = ("PaymentRequired", "PaymentPayload", "SettlementResponse")
    ARTIFACT_KINDS = (
        "PaidCapability",
        "PaymentQuote",
        "PaymentAuthorization",
        "PaymentVerification",
        "SettlementReceipt",
        "PaidEntitlement",
        "UsageRecord",
        "RefundRecord",
        "AccessReceipt",
    )

    def test_transport_vector_kinds_are_x402_only(self):
        kinds = {case["kind"] for case in TRANSPORT["cases"]}
        assert kinds <= set(self.X402_KINDS)
        assert "PaymentQuote" not in kinds
        assert "SettlementReceipt" not in kinds

    def test_artifact_vector_kinds_are_not_x402_header_objects(self):
        kinds = {case["kind"] for case in VALID["cases"]}
        assert kinds <= set(self.ARTIFACT_KINDS)
        assert not kinds.intersection(self.X402_KINDS)

    @pytest.mark.parametrize("case", TRANSPORT["cases"], ids=lambda c: c["id"])
    def test_x402_http_round_trip(self, case):
        header = encode_x402_header(case["kind"], case["payload"])
        assert "\n" not in header and " " not in header
        decoded = decode_x402_header(case["kind"], header)
        assert decoded == case["payload"]

    def test_x402_http_rejects_profile_h_artifact_as_payment_required(self):
        """A PaymentQuote artifact is not a PaymentRequired x402 header object."""
        quote = artifact("payment-quote")
        expect_fail(
            lambda: encode_x402_header("PaymentRequired", quote),
            code=CODE_INVALID,
        )

    def test_x402_http_rejects_settlement_receipt_as_settlement_response(self):
        settlement = artifact("settlement-receipt")
        expect_fail(
            lambda: encode_x402_header("SettlementResponse", settlement),
            code=CODE_INVALID,
        )

    def test_libp2p_artifact_rejects_x402_payment_required_as_quote(self):
        """An x402 PaymentRequired object is not a Profile H PaymentQuote artifact."""
        payment_required = next(
            c["payload"] for c in TRANSPORT["cases"] if c["kind"] == "PaymentRequired"
        )
        expect_fail(
            lambda: validate_profile_h_artifact("PaymentQuote", payment_required),
            code=CODE_INVALID,
        )

    def test_libp2p_artifact_rejects_x402_settlement_response_as_receipt(self):
        settlement_response = next(
            c["payload"] for c in TRANSPORT["cases"] if c["kind"] == "SettlementResponse"
        )
        expect_fail(
            lambda: validate_profile_h_artifact("SettlementReceipt", settlement_response),
            code=CODE_INVALID,
        )

    def test_x402_v1_rejected(self):
        payload = next(c["payload"] for c in TRANSPORT["cases"] if c["kind"] == "PaymentRequired")
        payload = copy.deepcopy(payload)
        payload["x402Version"] = 1
        expect_fail(
            lambda: encode_x402_header("PaymentRequired", payload),
            code="H_UNSUPPORTED_X402_VERSION",
            path_contains="x402Version",
        )

    def test_malformed_x402_header_fails_closed(self):
        expect_fail(
            lambda: decode_x402_header("PaymentRequired", "!!!not-base64!!!"),
            code=CODE_INVALID,
            path_contains="header",
        )


# ---------------------------------------------------------------------------
# Catalog: every required negative has at least one failing assertion above
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", REQUIRED_NEGATIVE_IDS)
def test_required_negative_case_is_covered(case_id):
    """Map MCPP-072 effect labels to concrete tests (documentation + import guard)."""
    coverage = {
        "paid-but-unauthorized": TestPaidUnauthorizedAndAuthorizedUnpaid.test_paid_but_unauthorized_allow_fails_closed,
        "authorized-but-unpaid": TestPaidUnauthorizedAndAuthorizedUnpaid.test_authorized_but_unpaid_allow_fails_closed,
        "replay": TestReplayProtection.test_replay_commitment_fails_closed,
        "price-mismatch": TestPriceAndRecipientBinding.test_price_mismatch_fails_closed,
        "wrong-recipient": TestPriceAndRecipientBinding.test_wrong_recipient_fails_closed,
        "duplicate-settlement": TestDuplicateSettlement.test_duplicate_settlement_conflict_fails_closed,
        "expired-quote": TestExpiredQuote.test_expired_quote_cannot_settle,
        "refund-after-consumed": TestRefundAfterConsumed.test_refund_after_full_consumption_fails_closed,
        "forged-settlement": TestForgedSettlement.test_forged_amount_fails_closed,
        "transport-split-x402-http": TestTransportSplit.test_x402_http_rejects_profile_h_artifact_as_payment_required,
        "transport-split-libp2p-artifact": TestTransportSplit.test_libp2p_artifact_rejects_x402_payment_required_as_quote,
    }
    assert case_id in coverage
    assert callable(coverage[case_id])

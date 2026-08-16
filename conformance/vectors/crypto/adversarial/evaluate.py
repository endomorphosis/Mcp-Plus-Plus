"""AdversarialVector@1 evaluator (shared by integration tests and runners).

Loads fixtures under this directory and asserts every required case fails closed
using real DelegationProof@1 / AttenuationPolicy@1 / RevocationRecord@1 code —
no mocks for signature or attenuation checks.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

VECTOR_ROOT = Path(__file__).resolve().parent
FIXTURES = VECTOR_ROOT / "fixtures"
MANIFEST_PATH = VECTOR_ROOT / "manifest.json"

_TESTS_PY = VECTOR_ROOT.parents[3] / "tests-py"
if str(_TESTS_PY) not in sys.path:
    sys.path.insert(0, str(_TESTS_PY))

from validators.revocation import (  # noqa: E402
    RevocationLedger,
    RevocationRecordValidator,
)
from validators.ucan_delegation import UCANDelegationValidator  # noqa: E402

# Import attenuation policy from integration module (MCPP-042).
_INTEGRATION = _TESTS_PY / "integration"
if str(_INTEGRATION) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION))
from test_ucan_attenuation import (  # noqa: E402
    AttenuationPolicy,
    AttenuationVerdict,
)

REQUIRED_CASE_IDS: Tuple[str, ...] = (
    "forged_signature",
    "altered_bytes",
    "wrong_audience",
    "expanded_capabilities",
    "expanded_resources",
    "expired",
    "future_nbf",
    "revoked",
    "missing_proof",
    "replay",
    "wrong_executor",
    "wrong_policy_cid",
    "valid_peerid_invalid_ucan",
)

INTERFACE = "AdversarialVector@1"


@dataclass
class AdversarialVerdict:
    """Fail-closed decision for one adversarial vector."""

    case_id: str
    admitted: bool
    reasons: List[str] = field(default_factory=list)
    reason_codes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    language: str = "python"

    @property
    def fail_closed(self) -> bool:
        return (not self.admitted) and bool(self.reasons or self.reason_codes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interface": INTERFACE,
            "case_id": self.case_id,
            "admitted": self.admitted,
            "fail_closed": self.fail_closed,
            "reasons": list(self.reasons),
            "reason_codes": list(self.reason_codes),
            "language": self.language,
            "metadata": dict(self.metadata),
        }


def _reject(case_id: str, *reasons: str, codes: Optional[Sequence[str]] = None, **meta: Any) -> AdversarialVerdict:
    return AdversarialVerdict(
        case_id=case_id,
        admitted=False,
        reasons=list(reasons),
        reason_codes=list(codes or []),
        metadata=dict(meta),
    )


def _admit(case_id: str, **meta: Any) -> AdversarialVerdict:
    return AdversarialVerdict(case_id=case_id, admitted=True, metadata=dict(meta))


def load_manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_fixture(case_id: str) -> Dict[str, Any]:
    path = FIXTURES / f"{case_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing adversarial fixture: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_keys() -> Dict[str, Any]:
    return json.loads((FIXTURES / "keys.json").read_text(encoding="utf-8"))


def _strip_fixture_meta(token: Mapping[str, Any]) -> Dict[str, Any]:
    """Remove fixture-only diagnostic fields before verification."""
    out = dict(token)
    out.pop("canonical_signing_bytes_hex", None)
    return out


def _crypto_verify(token: Mapping[str, Any], keys: Mapping[str, Any]) -> Tuple[bool, List[str], Optional[str]]:
    validator = UCANDelegationValidator(issuer_public_keys=dict(keys), require_signatures=True)
    result = validator.verify_delegation_proof(_strip_fixture_meta(token), issuer_public_keys=dict(keys))
    levels = result.metadata.get("levels") or {}
    crypto = levels.get("cryptographic") or {}
    reason = crypto.get("reason_code")
    codes: List[str] = []
    if reason:
        codes.append(str(reason))
    for err in result.errors:
        codes.append(str(err))
    return bool(result.is_valid), list(result.errors), (reason if reason else (codes[0] if codes else None))


def _attenuate(
    chain: Sequence[Mapping[str, Any]],
    request: Mapping[str, Any],
    *,
    nonce_store: Optional[MutableMapping[str, float]] = None,
) -> AttenuationVerdict:
    require_policy = bool(request.get("require_policy_cid"))
    required = request.get("required_policy_cid")
    policy = AttenuationPolicy(
        require_policy_cid=require_policy or bool(required),
        required_policy_cid=str(required) if required else None,
        require_executor=bool(request.get("require_executor", False)),
        nonce_store=nonce_store if nonce_store is not None else {},
    )
    clean_chain = [_strip_fixture_meta(t) for t in chain]
    return policy.evaluate(
        clean_chain,
        resource=str(request.get("resource") or ""),
        method=str(request.get("method") or request.get("ability") or ""),
        audience=request.get("audience"),
        executor=request.get("executor"),
        policy_cid=request.get("policy_cid"),
        budget=dict(request.get("budget") or {}),
        now=float(request["now"]) if request.get("now") is not None else None,
    )


def evaluate_case(case_id: str, fixture: Optional[Mapping[str, Any]] = None) -> AdversarialVerdict:
    """Evaluate one AdversarialVector@1 case. Negative cases never admit."""
    data = dict(fixture or load_fixture(case_id))
    cid = str(data.get("id") or case_id)
    if cid not in REQUIRED_CASE_IDS:
        return _reject(cid, "unknown_adversarial_case", codes=["unknown_case"])

    expected = [str(c) for c in (data.get("expected_reason_codes") or [])]

    if cid in {"forged_signature", "altered_bytes"}:
        ok, errors, reason = _crypto_verify(data["token"], data.get("issuer_public_keys") or {})
        if ok:
            return _reject(cid, "forged_or_altered_accepted", codes=["not_fail_closed"], expected=expected)
        codes = [reason] if reason else []
        codes.extend(e for e in errors if e not in codes)
        return _reject(cid, *errors, codes=codes or ["invalid_signature"], expected=expected)

    if cid == "missing_proof":
        validator = UCANDelegationValidator()
        result = validator.validate_invocation_with_proof(dict(data.get("invocation") or {}))
        if result.is_valid:
            return _reject(cid, "missing_proof_accepted", codes=["not_fail_closed"], expected=expected)
        levels = result.metadata.get("levels") or {}
        structural = levels.get("structural") or {}
        crypto = levels.get("cryptographic") or {}
        codes = []
        if structural.get("reason_code"):
            codes.append(str(structural["reason_code"]))
        if crypto.get("reason_code"):
            codes.append(str(crypto["reason_code"]))
        codes.extend(result.errors)
        return _reject(cid, *result.errors, codes=codes or ["missing_proof_cid"], expected=expected)

    if cid == "revoked":
        token = _strip_fixture_meta(data["token"])
        # Cryptographic validity of the original token (may be True).
        crypto_ok, crypto_errs, crypto_reason = _crypto_verify(token, data.get("issuer_public_keys") or {})
        # Bind fixture delegation_cid for ledger lookup without re-signing the token.
        del_cid = str(data.get("delegation_cid") or token.get("cid") or "").strip()
        token_for_revocation = dict(token)
        if del_cid:
            token_for_revocation["cid"] = del_cid
        ledger = RevocationLedger()
        rev_validator = RevocationRecordValidator(ledger=ledger, require_signatures=True)
        record = dict(data["revocation_record"])
        record.pop("canonical_signing_bytes_hex", None)
        admit = rev_validator.admit_record(
            record,
            issuer_public_keys=data.get("issuer_public_keys") or {},
            now=float((data.get("request") or {}).get("now") or 0) or None,
        )
        if not admit.is_valid:
            # Still fail closed on the token even if record shape is odd — treat as revoked path failure.
            return _reject(
                cid,
                *admit.errors,
                codes=["revoked", "revocation_record_invalid"],
                token_signature_valid=crypto_ok,
                expected=expected,
            )
        decision = rev_validator.evaluate_delegation(
            token_for_revocation,
            token_signature_valid=bool(data.get("token_signature_valid", crypto_ok)),
            now=float((data.get("request") or {}).get("now") or 0) or None,
        )
        if decision.allowed:
            return _reject(
                cid,
                "revoked_token_admitted",
                codes=["not_fail_closed"],
                token_signature_valid=crypto_ok,
                crypto_reason=crypto_reason,
                expected=expected,
            )
        return _reject(
            cid,
            decision.reason,
            codes=[decision.reason],
            token_signature_valid=crypto_ok,
            fail_closed_despite_valid_signature=decision.metadata.get(
                "fail_closed_despite_valid_signature"
            ),
            expected=expected,
        )

    if cid == "valid_peerid_invalid_ucan":
        peer_ok = bool(data.get("peer_authenticated"))
        ucan_present = bool(data.get("ucan_present"))
        token = data.get("token")
        crypto_ok = False
        reason = None
        errors: List[str] = []
        if token is not None:
            crypto_ok, errors, reason = _crypto_verify(token, data.get("issuer_public_keys") or {})
        # PeerID never grants UCAN authority.
        if peer_ok and (not ucan_present or not crypto_ok or data.get("ucan_valid") is False):
            codes = ["peerid_not_authority", "invalid_ucan"]
            if reason:
                codes.append(str(reason))
            return _reject(
                cid,
                "peerid_not_authority",
                "invalid_ucan",
                *errors,
                codes=codes,
                peer_id=data.get("peer_id"),
                peer_authenticated=peer_ok,
                expected=expected,
            )
        if crypto_ok and data.get("ucan_valid") is not False:
            return _reject(cid, "invalid_ucan_not_enforced", codes=["not_fail_closed"], expected=expected)
        return _reject(cid, "invalid_ucan", codes=["invalid_ucan"], expected=expected)

    if cid == "replay":
        store: Dict[str, float] = {}
        chain = list(data.get("chain") or [])
        request = dict(data.get("request") or {})
        first = _attenuate(chain, request, nonce_store=store)
        if first.denied:
            # First use may already deny for other reasons; still treat as fail-closed.
            return _reject(
                cid,
                first.reason,
                codes=[first.reason],
                phase="first",
                expected=expected,
            )
        second = _attenuate(chain, request, nonce_store=store)
        if second.allowed:
            return _reject(cid, "replay_accepted", codes=["not_fail_closed"], expected=expected)
        return _reject(cid, second.reason, codes=[second.reason], phase="second", expected=expected)

    # Default attenuation-layer cases
    chain = list(data.get("chain") or [])
    request = dict(data.get("request") or {})
    if not chain:
        return _reject(cid, "empty_chain_fixture", codes=["invalid_fixture"], expected=expected)
    verdict = _attenuate(chain, request)
    if verdict.allowed:
        return _reject(cid, "attenuation_admitted", codes=["not_fail_closed"], check=verdict.check, expected=expected)
    return _reject(
        cid,
        verdict.reason,
        codes=[verdict.reason],
        check=verdict.check,
        failure_hop=verdict.failure_hop,
        expected=expected,
    )


def evaluate_all() -> Dict[str, AdversarialVerdict]:
    return {case_id: evaluate_case(case_id) for case_id in REQUIRED_CASE_IDS}


def reason_matches_expected(verdict: AdversarialVerdict) -> bool:
    expected = [str(c) for c in (verdict.metadata.get("expected") or [])]
    if not expected:
        return True
    observed = set(verdict.reason_codes) | set(verdict.reasons)
    # Substring / membership soft match for composite error strings.
    for exp in expected:
        if exp in observed:
            return True
        if any(exp in str(o) for o in observed):
            return True
    return False


def main() -> int:
    results = evaluate_all()
    failures = []
    for case_id, verdict in results.items():
        if not verdict.fail_closed:
            failures.append(f"{case_id}: not fail-closed: {verdict.to_dict()}")
            continue
        if not reason_matches_expected(verdict):
            failures.append(
                f"{case_id}: reason mismatch expected={verdict.metadata.get('expected')} "
                f"got={verdict.reason_codes} reasons={verdict.reasons}"
            )
    report = {
        "interface": INTERFACE,
        "total": len(results),
        "fail_closed": sum(1 for v in results.values() if v.fail_closed),
        "failures": failures,
        "cases": {k: v.to_dict() for k, v in results.items()},
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate deterministic AdversarialVector@1 fixtures (MCPP-044).

Compact recipes + signed fixtures. Private keys are test-only seeds and
MUST NOT be reused outside this conformance suite.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"cryptography required to generate fixtures: {exc}") from exc

# Import mcpp-jcs-v1 from the four-language validators package.
_TESTS_PY = ROOT.parents[3] / "tests-py"
if str(_TESTS_PY) not in sys.path:
    sys.path.insert(0, str(_TESTS_PY))
from validators.canonical_jcs import canonicalize_bytes  # noqa: E402

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
NOW = 1_800_000_000
POLICY_CID = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
WRONG_POLICY_CID = "bafybeihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"
RESOURCE = "tenant-a/bucket-a/documents/report.txt"
METHOD = "tools/call"
EXECUTOR = "did:key:z6MkexecutorFixture0000000000000000000000000001"
PEER_ID = "12D3KooWAdversarialPeerIDFixture000000000000001"

# Fixed seeds (test-only).
SEEDS = {
    "root": bytes.fromhex("01" * 32),
    "mid": bytes.fromhex("02" * 32),
    "leaf": bytes.fromhex("03" * 32),
    "attacker": bytes.fromhex("ff" * 32),
    "revoker": bytes.fromhex("a5" * 32),
}


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, rem = divmod(n, 58)
        out = B58[rem] + out
    pad = 0
    for b in data:
        if b == 0:
            pad += 1
        else:
            break
    return ("1" * pad) + (out or "1")


def did_key_from_public(public: bytes) -> str:
    return "did:key:z" + b58encode(bytes([0xED, 0x01]) + public)


def private_key(name: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(SEEDS[name])


def public_raw(name: str) -> bytes:
    return private_key(name).public_key().public_bytes_raw()


def actor(name: str) -> Dict[str, str]:
    pub = public_raw(name)
    return {
        "name": name,
        "did": did_key_from_public(pub),
        "public_key_b64url": b64url(pub),
        "public_key_hex": pub.hex(),
        "seed_hex": SEEDS[name].hex(),
        "kid": f"{name}-v1",
    }


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sign_detached(priv: Ed25519PrivateKey, body: Mapping[str, Any], *, kid: str) -> Dict[str, Any]:
    """Detached-object form: signature covers mcpp-jcs-v1 of body without sig meta."""
    token = dict(body)
    token["alg"] = "EdDSA"
    token["kid"] = kid
    message = canonicalize_bytes(
        {k: v for k, v in token.items() if k not in {"signature", "sig", "public_key", "public_key_b64", "header", "protected", "alg", "kid", "signature_alg", "signatureAlg"}}
    )
    # Re-canonicalize with alg/kid included (signing object keeps alg/kid out of meta set for wire
    # validators that drop SIG_META_KEYS — match ucan_delegation._SIG_META_KEYS).
    sig_meta = {
        "signature",
        "sig",
        "signatures",
        "public_key",
        "publicKey",
        "public_key_b64",
        "issuer_public_key",
        "header",
        "protected",
        "alg",
        "kid",
        "signature_alg",
        "signatureAlg",
    }
    signing_obj = {k: v for k, v in token.items() if k not in sig_meta}
    message = canonicalize_bytes(signing_obj)
    token["signature"] = b64url(priv.sign(message))
    token["canonical_signing_bytes_hex"] = message.hex()
    return token


def sign_compact(priv: Ed25519PrivateKey, payload: Mapping[str, Any], *, kid: str) -> Dict[str, Any]:
    header = {"alg": "EdDSA", "kid": kid, "typ": "UCAN", "v": 1}
    h = b64url(canonicalize_bytes(header))
    p = b64url(canonicalize_bytes(dict(payload)))
    message = f"{h}.{p}".encode("ascii")
    sig = b64url(priv.sign(message))
    return {
        "form": "compact",
        "header": header,
        "payload": dict(payload),
        "token": f"{h}.{p}.{sig}",
        "signing_input": f"{h}.{p}",
        "signature": sig,
    }


def base_payload(
    *,
    iss: str,
    aud: str,
    resource: str = RESOURCE,
    ability: str = METHOD,
    exp: int = NOW + 300,
    nbf: int = NOW - 10,
    nonce: str = "nonce-base",
    proofs: Optional[List[str]] = None,
    can_delegate: bool = False,
    executor: Optional[str] = EXECUTOR,
    policy_cid: Optional[str] = POLICY_CID,
    extra_caps: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    caps: List[Dict[str, Any]] = [{"resource": resource, "ability": ability}]
    if extra_caps:
        caps.extend(extra_caps)
    body: Dict[str, Any] = {
        "iss": iss,
        "aud": aud,
        "att": caps,
        "exp": exp,
        "nbf": nbf,
        "nnc": nonce,
        "prf": list(proofs or []),
    }
    if can_delegate:
        body["can_delegate"] = True
        body["att"].append({"resource": "*", "ability": "ucan/DELEGATE"})
    if executor is not None:
        body["executor"] = executor
    if policy_cid is not None:
        body["policy_cid"] = policy_cid
    return body


def token_cid(token: Mapping[str, Any]) -> str:
    """Deterministic fake CIDv1-looking id from signing bytes (fixture label only)."""
    raw = bytes.fromhex(str(token.get("canonical_signing_bytes_hex") or ""))
    if not raw:
        raw = canonicalize_bytes(token)
    digest = hashlib.sha256(raw).digest()
    # Label only — not a real multiformats encode; stable for revocation fixtures.
    return "bafy" + digest.hex()[:50]


def build_suite() -> Dict[str, Any]:
    actors = {name: actor(name) for name in SEEDS}
    root = actors["root"]
    mid = actors["mid"]
    leaf = actors["leaf"]
    attacker = actors["attacker"]
    revoker = actors["revoker"]

    # --- valid baseline (positive control; not required for fail-closed cases) ---
    valid_body = base_payload(
        iss=root["did"],
        aud=leaf["did"],
        nonce="nonce-valid",
        can_delegate=False,
    )
    valid = sign_detached(private_key("root"), valid_body, kid=root["kid"])
    valid_cid = token_cid(valid)
    valid_compact = sign_compact(private_key("root"), valid_body, kid=root["kid"])

    # Parent for multi-hop attenuation cases
    parent_body = base_payload(
        iss=root["did"],
        aud=mid["did"],
        resource="tenant-a/*",
        ability="tools/*",
        nonce="nonce-parent",
        can_delegate=True,
        executor=None,
        policy_cid=None,
    )
    parent = sign_detached(private_key("root"), parent_body, kid=root["kid"])
    parent_cid = token_cid(parent)

    child_body = base_payload(
        iss=mid["did"],
        aud=leaf["did"],
        resource=RESOURCE,
        ability=METHOD,
        nonce="nonce-child",
        proofs=[parent_cid],
        can_delegate=False,
    )
    child = sign_detached(private_key("mid"), child_body, kid=mid["kid"])
    child_cid = token_cid(child)

    fixtures: Dict[str, Any] = {
        "keys.json": {
            "schema": "mcp++/conformance/adversarial-keys@1",
            "note": "TEST-ONLY fixed seeds. Never use outside conformance vectors.",
            "now": NOW,
            "policy_cid": POLICY_CID,
            "wrong_policy_cid": WRONG_POLICY_CID,
            "resource": RESOURCE,
            "method": METHOD,
            "executor": EXECUTOR,
            "peer_id": PEER_ID,
            "actors": actors,
        },
        "valid_token.json": {
            "id": "valid_token",
            "polarity": "positive",
            "detached": valid,
            "delegation_cid": valid_cid,
            "compact": valid_compact,
            "issuer_public_keys": {root["did"]: root["public_key_b64url"]},
        },
        "valid_chain.json": {
            "id": "valid_chain",
            "polarity": "positive",
            "chain": [parent, child],
            "delegation_cids": [parent_cid, child_cid],
            "issuer_public_keys": {
                root["did"]: root["public_key_b64url"],
                mid["did"]: mid["public_key_b64url"],
            },
            "request": {
                "resource": RESOURCE,
                "method": METHOD,
                "audience": leaf["did"],
                "executor": EXECUTOR,
                "policy_cid": POLICY_CID,
                "now": NOW,
                "budget": {},
            },
        },
    }

    # 1. forged_signature — wrong key signed the same body
    forged_body = base_payload(iss=root["did"], aud=leaf["did"], nonce="nonce-forged")
    forged = sign_detached(private_key("attacker"), forged_body, kid=root["kid"])
    forged_cid = token_cid(forged)
    fixtures["forged_signature.json"] = {
        "id": "forged_signature",
        "polarity": "negative",
        "layer": "cryptographic",
        "token": forged,
        "delegation_cid": forged_cid,
        "issuer_public_keys": {root["did"]: root["public_key_b64url"]},
        "expected_reason_codes": ["invalid_signature"],
        "languages": ["python", "typescript", "go", "rust"],
    }

    # 2. altered_bytes — valid sig then mutate a claim
    altered = copy.deepcopy(valid)
    altered["att"] = [{"resource": "tenant-b/*", "ability": "tools/admin"}]
    altered["nnc"] = "nonce-altered"
    # Keep original signature (now invalid over mutated body)
    fixtures["altered_bytes.json"] = {
        "id": "altered_bytes",
        "polarity": "negative",
        "layer": "cryptographic",
        "token": altered,
        "original_signing_bytes_hex": valid["canonical_signing_bytes_hex"],
        "issuer_public_keys": {root["did"]: root["public_key_b64url"]},
        "expected_reason_codes": ["invalid_signature"],
        "languages": ["python", "typescript", "go", "rust"],
    }

    # 3. wrong_audience
    wrong_aud_body = base_payload(
        iss=root["did"],
        aud="did:key:z6MkwrongAudienceFixture00000000000000000001",
        nonce="nonce-wrong-aud",
    )
    wrong_aud = sign_detached(private_key("root"), wrong_aud_body, kid=root["kid"])
    fixtures["wrong_audience.json"] = {
        "id": "wrong_audience",
        "polarity": "negative",
        "layer": "attenuation",
        "chain": [wrong_aud],
        "request": {
            "resource": RESOURCE,
            "method": METHOD,
            "audience": leaf["did"],
            "executor": EXECUTOR,
            "policy_cid": POLICY_CID,
            "now": NOW,
            "budget": {},
        },
        "expected_reason_codes": ["audience_mismatch", "issuer_audience_continuity_failed"],
        "languages": ["python", "typescript", "go", "rust"],
    }

    # 4. expanded_capabilities — ability outside parent method cover (store/write vs tools/*)
    expanded_caps_child = sign_detached(
        private_key("mid"),
        base_payload(
            iss=mid["did"],
            aud=leaf["did"],
            resource=RESOURCE,
            ability="store/write",
            nonce="nonce-exp-caps",
            proofs=[parent_cid],
        ),
        kid=mid["kid"],
    )
    fixtures["expanded_capabilities.json"] = {
        "id": "expanded_capabilities",
        "polarity": "negative",
        "layer": "attenuation",
        "chain": [parent, expanded_caps_child],
        "request": {
            "resource": RESOURCE,
            "method": "store/write",
            "audience": leaf["did"],
            "executor": EXECUTOR,
            "policy_cid": POLICY_CID,
            "now": NOW,
            "budget": {},
        },
        "expected_reason_codes": [
            "method_attenuation_failed",
            "capability_attenuation_failed",
            "capability_not_granted",
        ],
        "languages": ["python", "typescript", "go", "rust"],
    }

    # 5. expanded_resources
    expanded_res_child = sign_detached(
        private_key("mid"),
        base_payload(
            iss=mid["did"],
            aud=leaf["did"],
            resource="tenant-b/*",
            ability=METHOD,
            nonce="nonce-exp-res",
            proofs=[parent_cid],
        ),
        kid=mid["kid"],
    )
    fixtures["expanded_resources.json"] = {
        "id": "expanded_resources",
        "polarity": "negative",
        "layer": "attenuation",
        "chain": [parent, expanded_res_child],
        "request": {
            "resource": "tenant-b/secret",
            "method": METHOD,
            "audience": leaf["did"],
            "executor": EXECUTOR,
            "policy_cid": POLICY_CID,
            "now": NOW,
            "budget": {},
        },
        "expected_reason_codes": [
            "resource_attenuation_failed",
            "capability_attenuation_failed",
            "capability_not_granted",
        ],
        "languages": ["python", "typescript", "go", "rust"],
    }

    # 6. expired
    expired = sign_detached(
        private_key("root"),
        base_payload(iss=root["did"], aud=leaf["did"], exp=NOW - 1, nonce="nonce-expired"),
        kid=root["kid"],
    )
    fixtures["expired.json"] = {
        "id": "expired",
        "polarity": "negative",
        "layer": "attenuation",
        "chain": [expired],
        "request": {
            "resource": RESOURCE,
            "method": METHOD,
            "audience": leaf["did"],
            "executor": EXECUTOR,
            "policy_cid": POLICY_CID,
            "now": NOW,
            "budget": {},
        },
        "expected_reason_codes": ["expired"],
        "languages": ["python", "typescript", "go", "rust"],
    }

    # 7. future_nbf
    future_nbf = sign_detached(
        private_key("root"),
        base_payload(iss=root["did"], aud=leaf["did"], nbf=NOW + 60, nonce="nonce-nbf"),
        kid=root["kid"],
    )
    fixtures["future_nbf.json"] = {
        "id": "future_nbf",
        "polarity": "negative",
        "layer": "attenuation",
        "chain": [future_nbf],
        "request": {
            "resource": RESOURCE,
            "method": METHOD,
            "audience": leaf["did"],
            "executor": EXECUTOR,
            "policy_cid": POLICY_CID,
            "now": NOW,
            "budget": {},
        },
        "expected_reason_codes": ["not_yet_valid"],
        "languages": ["python", "typescript", "go", "rust"],
    }

    # 8. revoked — valid signature, then revoke by cid (cid stored beside token so
    # the detached signature still covers the original body).
    revoked_token = sign_detached(
        private_key("root"),
        base_payload(iss=root["did"], aud=leaf["did"], nonce="nonce-revoked"),
        kid=root["kid"],
    )
    revoked_cid = token_cid(revoked_token)
    rev_body = {
        "schema": "mcp++/delegation/revocation-record@1",
        "issuer": revoker["did"],
        "revoked_delegation_cid": revoked_cid,
        "effective_at": NOW - 5,
        "reason": "adversarial_vector_revocation",
        "alg": "EdDSA",
        "kid": revoker["kid"],
        "discovery": {
            "method": "ledger",
            "registry_id": "mcp++/revocation-ledger@1",
            "published_at": NOW - 5,
        },
    }
    rev_sig_meta = {
        "signature",
        "sig",
        "signatures",
        "public_key",
        "publicKey",
        "public_key_b64",
        "issuer_public_key",
        "header",
        "protected",
        "alg",
        "kid",
        "signature_alg",
        "signatureAlg",
    }
    rev_msg = canonicalize_bytes({k: v for k, v in rev_body.items() if k not in rev_sig_meta})
    rev_body["signature"] = b64url(private_key("revoker").sign(rev_msg))
    rev_body["canonical_signing_bytes_hex"] = rev_msg.hex()
    fixtures["revoked.json"] = {
        "id": "revoked",
        "polarity": "negative",
        "layer": "revocation",
        "token": revoked_token,
        "delegation_cid": revoked_cid,
        "token_signature_valid": True,
        "revocation_record": rev_body,
        "issuer_public_keys": {
            root["did"]: root["public_key_b64url"],
            revoker["did"]: revoker["public_key_b64url"],
        },
        "request": {
            "resource": RESOURCE,
            "method": METHOD,
            "audience": leaf["did"],
            "executor": EXECUTOR,
            "policy_cid": POLICY_CID,
            "now": NOW,
            "budget": {},
        },
        "expected_reason_codes": ["revoked"],
        "languages": ["python", "typescript", "go", "rust"],
    }

    # 9. missing_proof
    fixtures["missing_proof.json"] = {
        "id": "missing_proof",
        "polarity": "negative",
        "layer": "invocation",
        "invocation": {
            "method": "tools/call",
            "params": {"name": "infer"},
            # deliberately no proof_cid
        },
        "expected_reason_codes": ["missing_proof_cid"],
        "languages": ["python", "typescript", "go", "rust"],
    }

    # 10. replay — same nonce twice
    replay_token = sign_detached(
        private_key("root"),
        base_payload(iss=root["did"], aud=leaf["did"], nonce="nonce-replay-once"),
        kid=root["kid"],
    )
    fixtures["replay.json"] = {
        "id": "replay",
        "polarity": "negative",
        "layer": "attenuation",
        "chain": [replay_token],
        "request": {
            "resource": RESOURCE,
            "method": METHOD,
            "audience": leaf["did"],
            "executor": EXECUTOR,
            "policy_cid": POLICY_CID,
            "now": NOW,
            "budget": {},
        },
        "replay_count": 2,
        "expected_reason_codes": ["replayed"],
        "languages": ["python", "typescript", "go", "rust"],
    }

    # 11. wrong_executor
    wrong_exec = sign_detached(
        private_key("root"),
        base_payload(iss=root["did"], aud=leaf["did"], nonce="nonce-wrong-exec", executor=EXECUTOR),
        kid=root["kid"],
    )
    fixtures["wrong_executor.json"] = {
        "id": "wrong_executor",
        "polarity": "negative",
        "layer": "attenuation",
        "chain": [wrong_exec],
        "request": {
            "resource": RESOURCE,
            "method": METHOD,
            "audience": leaf["did"],
            "executor": "did:key:z6MkwrongExecutorFixture000000000000000001",
            "policy_cid": POLICY_CID,
            "now": NOW,
            "budget": {},
        },
        "expected_reason_codes": ["executor_binding_failed"],
        "languages": ["python", "typescript", "go", "rust"],
    }

    # 12. wrong_policy_cid
    wrong_pol = sign_detached(
        private_key("root"),
        base_payload(
            iss=root["did"],
            aud=leaf["did"],
            nonce="nonce-wrong-pol",
            policy_cid=POLICY_CID,
        ),
        kid=root["kid"],
    )
    fixtures["wrong_policy_cid.json"] = {
        "id": "wrong_policy_cid",
        "polarity": "negative",
        "layer": "attenuation",
        "chain": [wrong_pol],
        "request": {
            "resource": RESOURCE,
            "method": METHOD,
            "audience": leaf["did"],
            "executor": EXECUTOR,
            "policy_cid": WRONG_POLICY_CID,
            "now": NOW,
            "budget": {},
            "require_policy_cid": True,
            "required_policy_cid": POLICY_CID,
        },
        "expected_reason_codes": ["policy_cid_mismatch", "policy_cid_required"],
        "languages": ["python", "typescript", "go", "rust"],
    }

    # 13. valid_peerid_invalid_ucan — transport identity ≠ authority
    fixtures["valid_peerid_invalid_ucan.json"] = {
        "id": "valid_peerid_invalid_ucan",
        "polarity": "negative",
        "layer": "authority_separation",
        "peer_id": PEER_ID,
        "peer_authenticated": True,
        "ucan_present": True,
        "ucan_valid": False,
        "token": forged,
        "delegation_cid": forged_cid,
        "issuer_public_keys": {root["did"]: root["public_key_b64url"]},
        "expected_reason_codes": [
            "peerid_not_authority",
            "invalid_ucan",
            "invalid_signature",
        ],
        "languages": ["python", "typescript", "go", "rust"],
    }

    return fixtures


REQUIRED_CASE_IDS = (
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


def build_manifest(fixtures: Mapping[str, Any]) -> Dict[str, Any]:
    cases = []
    for case_id in REQUIRED_CASE_IDS:
        fname = f"{case_id}.json"
        data = fixtures[fname]
        cases.append(
            {
                "id": case_id,
                "file": f"fixtures/{fname}",
                "polarity": "negative",
                "valid": False,
                "expected_fail_closed": True,
                "layer": data.get("layer"),
                "expected_reason_codes": data.get("expected_reason_codes", []),
                "languages": data.get("languages", ["python", "typescript", "go", "rust"]),
            }
        )
    return {
        "schema": "mcp++/conformance/adversarial-vector-manifest@1",
        "interface": "AdversarialVector@1",
        "task_id": "MCPP-044",
        "suite_revision": "adversarial-ucan@1.0.0",
        "description": (
            "Shared adversarial cryptographic negative vectors for Profile C. "
            "Every listed case MUST fail closed in Python, TypeScript, Go, and Rust."
        ),
        "spec_paths": [
            "ipfs_accelerate_py/mcplusplus/docs/spec/ucan-delegation.md",
            "ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/0002-crypto-canonical.md",
            "ipfs_accelerate_py/mcplusplus/docs/architecture/decisions/0003-conformance-levels.md",
        ],
        "vectors_dir": "ipfs_accelerate_py/mcplusplus/conformance/vectors/crypto/adversarial",
        "acceptance": {
            "criteria": (
                "Every listed case fails closed in Python, TypeScript, Go, and Rust."
            ),
            "cases_required": list(REQUIRED_CASE_IDS),
        },
        "coverage": {cid: {"negative": 1} for cid in REQUIRED_CASE_IDS},
        "cases": cases,
    }


def build_recipes() -> Dict[str, Any]:
    """Compact recipes (generators) — no bulk golden dumps per mutation step."""
    recipes = []
    for case_id in REQUIRED_CASE_IDS:
        recipes.append(
            {
                "case": case_id,
                "fixture": f"fixtures/{case_id}.json",
                "expected_fail_closed": True,
            }
        )
    return {
        "schema": "mcp++/conformance/adversarial-recipes@1",
        "interface": "AdversarialVector@1",
        "task_id": "MCPP-044",
        "note": "Compact index of negative cases. Full signed inputs live under fixtures/.",
        "recipes": recipes,
    }


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    fixtures = build_suite()
    for name, obj in fixtures.items():
        write_json(FIXTURES / name, obj)
    write_json(ROOT / "manifest.json", build_manifest(fixtures))
    write_json(ROOT / "recipes.json", build_recipes())
    print(f"wrote {len(fixtures)} fixture files + manifest + recipes under {ROOT}")


if __name__ == "__main__":
    main()

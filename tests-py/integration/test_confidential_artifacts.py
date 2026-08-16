"""
Integration tests for confidential CID-native artifacts (MCPP-074 / MCPP-G150).

Interfaces: EncryptedArtifactRef@1, KeyEnvelope@1, ConfidentialPersistenceReceipt@1
Schema: schemas/confidential/encrypted-artifact-ref-1.schema.json
Spec: docs/spec/cid-native-artifacts.md §8 (KD-15 non-leakage obligations)

Acceptance:
  - No tested persistence path writes plaintext.
  - Altered ciphertext fails verify.
  - Revoked key access fails closed.

Effects coverage:
  unauthorized read, altered ciphertext, wrong recipient, revoked key access,
  accidental plaintext persistence (primary / cache / local fallback),
  Event DAG metadata and log redaction.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import os
import re
import secrets
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

import pytest

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # pragma: no cover
    AESGCM = None  # type: ignore[misc, assignment]

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Paths / interface constants
# ---------------------------------------------------------------------------

_TESTS_ROOT = Path(__file__).resolve().parent.parent
_MCPPLUSPLUS_ROOT = _TESTS_ROOT.parent
_SCHEMA_PATH = (
    _MCPPLUSPLUS_ROOT / "schemas" / "confidential" / "encrypted-artifact-ref-1.schema.json"
)

INTERFACE_REF = "EncryptedArtifactRef@1"
INTERFACE_ENVELOPE = "KeyEnvelope@1"
INTERFACE_RECEIPT = "ConfidentialPersistenceReceipt@1"
SCHEMA_MARKER_REF = "mcp++/confidential/encrypted-artifact-ref@1"
SCHEMA_MARKER_ENVELOPE = "mcp++/confidential/key-envelope@1"
SCHEMA_MARKER_RECEIPT = "mcp++/confidential/persistence-receipt@1"

ABILITY_DECRYPT = "mcp++/confidential/decrypt"
ABILITY_UNWRAP = "mcp++/confidential/unwrap-key"

# Marker secrets used only inside tests; must never appear on disk / logs / DAG.
SECRET_PLAINTEXT = "TOP-SECRET-PAYROLL-SSN-999-00-1234"
SECRET_FRAGMENT = "SSN-999-00-1234"
FORBIDDEN_LOG_KEYS = frozenset(
    {
        "plaintext",
        "plaintext_b64",
        "dek",
        "content_key",
        "raw_key",
        "private_key",
        "unwrapped_key",
    }
)

CID_RE = re.compile(r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{58,})$")


# ---------------------------------------------------------------------------
# Crypto / CID helpers
# ---------------------------------------------------------------------------


def _require_crypto() -> None:
    if AESGCM is None:
        pytest.skip("cryptography AESGCM unavailable")


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64url(value: str) -> bytes:
    text = str(value).strip()
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _base32_lower_nopad(data: bytes) -> str:
    return base64.b32encode(data).decode("ascii").rstrip("=").lower()


def cid_for_bytes(payload: bytes) -> str:
    """Kubo-conformant CIDv1 (raw, sha2-256, base32) -> bafkrei…"""
    digest = hashlib.sha256(payload).digest()
    cid_bytes = bytes([0x01, 0x55, 0x12, 0x20]) + digest
    return "b" + _base32_lower_nopad(cid_bytes)


def canonicalize(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def cid_for_obj(value: Any) -> str:
    return cid_for_bytes(canonicalize(value))


# ---------------------------------------------------------------------------
# In-memory / on-disk confidential persistence harness
# ---------------------------------------------------------------------------


class ConfidentialError(Exception):
    """Fail-closed confidential store error with stable reason code."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


@dataclass
class Principal:
    did: str
    wrap_key: bytes  # 32-byte KEK for direct-AES-256-GCM wraps
    kid: str = "default"


@dataclass
class LogRecord:
    level: str
    event: str
    fields: Dict[str, Any]


@dataclass
class ConfidentialArtifactStore:
    """Reference persistence harness for EncryptedArtifactRef@1 (test scope).

    Persistence paths exercised:
      - primary   (durable ciphertext + ref metadata)
      - cache     (warm ciphertext cache; never plaintext)
      - fallback  (offline/local path when primary is forced down)

    Decrypt keys stay in process memory only. Revocation is consulted fail-closed.
    """

    root: Path
    primary_down: bool = False
    revoked_capability_cids: Set[str] = field(default_factory=set)
    revoked_content_key_ids: Set[str] = field(default_factory=set)
    wrap_keys: Dict[str, bytes] = field(default_factory=dict)
    principals: Dict[str, Principal] = field(default_factory=dict)
    event_dag: List[Dict[str, Any]] = field(default_factory=list)
    logs: List[LogRecord] = field(default_factory=list)
    _memory_deks: Dict[str, bytes] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for name in ("primary", "cache", "fallback", "logs"):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    # -- registration -------------------------------------------------------

    def register_principal(self, principal: Principal) -> None:
        if len(principal.wrap_key) != 32:
            raise ConfidentialError("invalid_wrap_key", "wrap key must be 32 bytes")
        self.principals[principal.did] = principal
        self.wrap_keys[principal.did] = principal.wrap_key

    def revoke_capability(self, capability_cid: str) -> None:
        self.revoked_capability_cids.add(str(capability_cid))
        self._log("info", "capability_revoked", {"capability_cid": capability_cid})

    def revoke_content_key(self, content_key_id: str) -> None:
        self.revoked_content_key_ids.add(str(content_key_id))
        self._memory_deks.pop(content_key_id, None)
        self._log("info", "content_key_revoked", {"content_key_id": content_key_id})

    # -- seal / open --------------------------------------------------------

    def seal(
        self,
        plaintext: bytes | str,
        *,
        recipients: Sequence[str],
        issuer: str,
        plaintext_schema: Mapping[str, Any] | None = None,
        capability_cid: str | None = None,
        correlation_id: str | None = None,
        label: str | None = None,
        force_fallback: bool = False,
        write_cache: bool = True,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Encrypt plaintext and persist only ciphertext + EncryptedArtifactRef."""
        _require_crypto()
        if isinstance(plaintext, str):
            plaintext_bytes = plaintext.encode("utf-8")
        else:
            plaintext_bytes = bytes(plaintext)
        if not recipients:
            raise ConfidentialError("no_recipients", "at least one recipient required")
        for did in recipients:
            if did not in self.principals:
                raise ConfidentialError("unknown_recipient", f"unknown recipient {did}")

        schema_doc = dict(plaintext_schema or {"type": "string", "contentMediaType": "text/plain"})
        plaintext_schema_cid = cid_for_obj(schema_doc)
        content_key_id = "ck-" + secrets.token_hex(8)
        dek = AESGCM.generate_key(bit_length=256)
        self._memory_deks[content_key_id] = dek

        aad = plaintext_schema_cid.encode("utf-8")
        nonce = secrets.token_bytes(12)
        # AESGCM.encrypt returns ciphertext || tag
        body = AESGCM(dek).encrypt(nonce, plaintext_bytes, aad)
        package = nonce + body  # nonce_prepended_ciphertext_tag
        ciphertext_cid = cid_for_bytes(package)

        wrapped_keys: List[Dict[str, Any]] = []
        for did in recipients:
            principal = self.principals[did]
            wrap_nonce = secrets.token_bytes(12)
            wrapped = wrap_nonce + AESGCM(principal.wrap_key).encrypt(wrap_nonce, dek, None)
            entry: Dict[str, Any] = {
                "recipient": did,
                "recipient_kid": principal.kid,
                "key_wrap": "direct-AES-256-GCM",
                "wrapped_key_b64url": _b64url(wrapped),
                "wrap_nonce_b64url": None,
            }
            if capability_cid is not None:
                entry["capability_cid"] = capability_cid
            wrapped_keys.append(entry)

        access_caps: List[Dict[str, Any]] = []
        if capability_cid is not None:
            access_caps.append(
                {
                    "kind": "ucan_proof_cid",
                    "cid": capability_cid,
                    "ability": ABILITY_DECRYPT,
                    "resource": ciphertext_cid,
                }
            )

        key_envelope: Dict[str, Any] = {
            "schema": SCHEMA_MARKER_ENVELOPE,
            "content_key_id": content_key_id,
            "wrapped_keys": wrapped_keys,
            "access_caps": access_caps,
            "epoch": 1,
            "revocation_binding": {
                "mode": "delegation_ledger",
                "ledger_or_registry": "mcpp-test-revocation-ledger",
                "revocation_policy_cid": None,
            },
            "created_at_ms": 1_700_000_000_000,
            "supersedes_content_key_id": None,
        }

        ref: Dict[str, Any] = {
            "schema": SCHEMA_MARKER_REF,
            "ciphertext_cid": ciphertext_cid,
            "algorithm": {
                "content_aead": "AES-256-GCM",
                "key_wrap": "direct-AES-256-GCM",
                "ciphertext_layout": "nonce_prepended_ciphertext_tag",
                "aead_tag_length": 16,
                "aad_binding": "plaintext_schema_cid",
                "hkdf_info": "mcp++/confidential/content-key@1",
            },
            "key_envelope": key_envelope,
            "plaintext_schema_cid": plaintext_schema_cid,
            "protected_digest": None,
            "disclosure_policy_cid": None,
            "retention_policy_cid": None,
            "redaction": {
                "mode": "never-export-plaintext",
                "public_fields": [
                    "schema",
                    "ciphertext_cid",
                    "ref_cid",
                    "plaintext_schema_cid",
                    "redaction.mode",
                ],
                "redaction_receipt_cid": None,
                "notes": None,
            },
            "canonicalization": "mcpp-jcs-v1",
            "issuer": issuer,
            "created_at_ms": 1_700_000_000_000,
            "parents": [],
            "correlation_id": correlation_id,
            "label": label,
            "recipients": [{"recipient": did, "recipient_kid": self.principals[did].kid} for did in recipients],
            "access_caps": list(access_caps),
            "metadata": {"purpose": "mcpp-074-confidential-test"},
        }
        # Self-address without ref_cid field present.
        ref_body = {k: v for k, v in ref.items() if k != "ref_cid"}
        ref["ref_cid"] = cid_for_obj(ref_body)

        receipt = self._persist(ref, package, force_fallback=force_fallback, write_cache=write_cache)
        event = self._append_event_dag(ref, receipt)
        receipt["event_cid"] = event["event_cid"]
        self._write_receipt(receipt)

        # Log only non-secret identifiers.
        self._log(
            "info",
            "confidential_artifact_sealed",
            {
                "ref_cid": ref["ref_cid"],
                "ciphertext_cid": ciphertext_cid,
                "recipient_count": len(recipients),
                "paths": receipt["paths_written"],
            },
        )
        return ref, receipt

    def verify_ciphertext(self, ref: Mapping[str, Any], package: bytes | None = None) -> bool:
        """Verify content-address integrity of ciphertext without disclosure."""
        cid = str(ref["ciphertext_cid"])
        if package is None:
            package = self._load_ciphertext(cid)
        if package is None:
            raise ConfidentialError("ciphertext_missing", "ciphertext bytes unavailable")
        actual = cid_for_bytes(package)
        if actual != cid:
            raise ConfidentialError("ciphertext_integrity_failed", "CID mismatch for ciphertext")
        return True

    def open(
        self,
        ref: Mapping[str, Any],
        *,
        recipient: str,
        capability_cid: str | None = None,
        package: bytes | None = None,
    ) -> bytes:
        """Unwrap and decrypt. Fail closed on authz / integrity / revocation."""
        _require_crypto()
        self.verify_ciphertext(ref, package)

        content_key_id = str(ref["key_envelope"]["content_key_id"])
        if content_key_id in self.revoked_content_key_ids:
            self._log("warning", "decrypt_denied", {"reason": "content_key_revoked", "content_key_id": content_key_id})
            raise ConfidentialError("content_key_revoked", "content key revoked")

        # Capability checks (fail closed when caps are declared).
        declared_caps = list(ref.get("access_caps") or []) + list(
            ref["key_envelope"].get("access_caps") or []
        )
        if declared_caps:
            if capability_cid is None:
                raise ConfidentialError("capability_required", "decrypt capability required")
            if capability_cid in self.revoked_capability_cids:
                self._log(
                    "warning",
                    "decrypt_denied",
                    {"reason": "capability_revoked", "capability_cid": capability_cid},
                )
                raise ConfidentialError("capability_revoked", "capability revoked")
            if not self._capability_authorizes(declared_caps, capability_cid, ref):
                raise ConfidentialError("capability_not_granted", "capability does not authorize unwrap")

        wrap = self._find_wrap(ref, recipient)
        if wrap is None:
            raise ConfidentialError("wrong_recipient", "no wrap for recipient")

        # Per-wrap expiry.
        expires = wrap.get("expires_at_ms")
        if expires is not None and int(expires) < 1_700_000_000_000:
            raise ConfidentialError("wrap_expired", "wrap entry expired")

        wrap_cap = wrap.get("capability_cid")
        if wrap_cap is not None and str(wrap_cap) in self.revoked_capability_cids:
            raise ConfidentialError("capability_revoked", "wrap capability revoked")

        if recipient not in self.wrap_keys:
            raise ConfidentialError("unauthorized_read", "recipient key material unavailable")

        try:
            wrapped = _unb64url(str(wrap["wrapped_key_b64url"]))
            wrap_nonce, wrap_body = wrapped[:12], wrapped[12:]
            dek = AESGCM(self.wrap_keys[recipient]).decrypt(wrap_nonce, wrap_body, None)
        except Exception as exc:
            raise ConfidentialError("unwrap_failed", "failed to unwrap content key") from exc

        if package is None:
            package = self._load_ciphertext(str(ref["ciphertext_cid"]))
        if package is None or len(package) < 13:
            raise ConfidentialError("ciphertext_missing", "ciphertext bytes unavailable")

        nonce, body = package[:12], package[12:]
        aad = str(ref["plaintext_schema_cid"]).encode("utf-8")
        try:
            plaintext = AESGCM(dek).decrypt(nonce, body, aad)
        except Exception as exc:
            raise ConfidentialError("aead_verify_failed", "AEAD open failed") from exc

        # Optional protected digest verification.
        pd = ref.get("protected_digest")
        if isinstance(pd, dict) and pd.get("digest"):
            expected = str(pd["digest"]).lower()
            actual = hashlib.sha256(plaintext).hexdigest()
            if expected not in (actual, _b64url(bytes.fromhex(actual))):
                # Accept hex or b64url forms.
                if expected != actual and expected != _b64url(hashlib.sha256(plaintext).digest()):
                    raise ConfidentialError("protected_digest_mismatch", "plaintext digest mismatch")

        self._log(
            "info",
            "confidential_artifact_opened",
            {
                "ref_cid": ref.get("ref_cid"),
                "ciphertext_cid": ref.get("ciphertext_cid"),
                "recipient": recipient,
            },
        )
        return plaintext

    # -- persistence surfaces -----------------------------------------------

    def _persist(
        self,
        ref: Mapping[str, Any],
        package: bytes,
        *,
        force_fallback: bool,
        write_cache: bool,
    ) -> Dict[str, Any]:
        paths: List[str] = []
        use_fallback = force_fallback or self.primary_down
        if use_fallback:
            self._write_blob(self.root / "fallback", str(ref["ciphertext_cid"]), package)
            self._write_json(self.root / "fallback" / f"{ref['ref_cid']}.ref.json", ref)
            paths.append("local_fallback")
        else:
            self._write_blob(self.root / "primary", str(ref["ciphertext_cid"]), package)
            self._write_json(self.root / "primary" / f"{ref['ref_cid']}.ref.json", ref)
            paths.append("primary")
        if write_cache:
            self._write_blob(self.root / "cache", str(ref["ciphertext_cid"]), package)
            # Cache stores ref metadata only (still no plaintext).
            self._write_json(
                self.root / "cache" / f"{ref['ref_cid']}.meta.json",
                {
                    "ref_cid": ref["ref_cid"],
                    "ciphertext_cid": ref["ciphertext_cid"],
                    "schema": ref["schema"],
                    "redaction": ref.get("redaction"),
                },
            )
            paths.append("cache")

        return {
            "schema": SCHEMA_MARKER_RECEIPT,
            "interface": INTERFACE_RECEIPT,
            "ref_cid": ref["ref_cid"],
            "ciphertext_cid": ref["ciphertext_cid"],
            "plaintext_schema_cid": ref["plaintext_schema_cid"],
            "paths_written": paths,
            "plaintext_written": False,
            "content_key_persisted": False,
            "redaction_mode": (ref.get("redaction") or {}).get("mode"),
            "event_cid": None,
            "kind": "confidential_artifact_persisted",
            "description": "ciphertext-only persistence; plaintext not included",
        }

    def _append_event_dag(self, ref: Mapping[str, Any], receipt: Mapping[str, Any]) -> Dict[str, Any]:
        """Append Event DAG metadata that attests use without disclosure."""
        parents = [e["event_cid"] for e in self.event_dag[-1:]] if self.event_dag else []
        event = {
            "parents": parents,
            "kind": "confidential_artifact_used",
            "ref_cid": ref["ref_cid"],
            "ciphertext_cid": ref["ciphertext_cid"],
            "plaintext_schema_cid": ref["plaintext_schema_cid"],
            "redaction_mode": (ref.get("redaction") or {}).get("mode"),
            "receipt_cid": cid_for_obj(dict(receipt)),
            "description": "decrypt-authorized path available; plaintext not included",
            "metadata": {
                "paths_written": list(receipt.get("paths_written") or []),
                "plaintext_written": False,
            },
        }
        event["event_cid"] = cid_for_obj(event)
        # Guard: never embed secret-bearing keys in DAG nodes.
        self._assert_no_forbidden_keys(event)
        self.event_dag.append(event)
        self._write_json(self.root / "primary" / f"{event['event_cid']}.event.json", event)
        return event

    def _write_receipt(self, receipt: Mapping[str, Any]) -> None:
        self._assert_no_forbidden_keys(receipt)
        self._write_json(self.root / "primary" / f"{receipt['ref_cid']}.receipt.json", receipt)

    def _load_ciphertext(self, ciphertext_cid: str) -> Optional[bytes]:
        for tier in ("primary", "cache", "fallback"):
            path = self.root / tier / ciphertext_cid
            if path.is_file():
                return path.read_bytes()
        return None

    @staticmethod
    def _write_blob(directory: Path, name: str, data: bytes) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    @staticmethod
    def _write_json(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)

    def _log(self, level: str, event: str, fields: Mapping[str, Any]) -> None:
        safe = dict(fields)
        self._assert_no_forbidden_keys(safe)
        # Never log values that look like the test secret.
        rendered = json.dumps(safe, sort_keys=True)
        if SECRET_FRAGMENT in rendered or SECRET_PLAINTEXT in rendered:
            raise ConfidentialError("plaintext_log_leak", "refusing to log plaintext secret")
        self.logs.append(LogRecord(level=level, event=event, fields=safe))
        # Also write a redacted operational log line (no secrets).
        line = json.dumps({"level": level, "event": event, **safe}, sort_keys=True)
        log_path = self.root / "logs" / "operations.jsonl"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    @staticmethod
    def _assert_no_forbidden_keys(value: Any, path: str = "") -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                key_l = str(key).lower()
                if key_l in FORBIDDEN_LOG_KEYS or key_l in {"plaintext", "dek"}:
                    raise ConfidentialError(
                        "forbidden_field",
                        f"forbidden secret field at {path}/{key}",
                    )
                ConfidentialArtifactStore._assert_no_forbidden_keys(item, f"{path}/{key}")
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                ConfidentialArtifactStore._assert_no_forbidden_keys(item, f"{path}/{idx}")

    @staticmethod
    def _find_wrap(ref: Mapping[str, Any], recipient: str) -> Optional[Dict[str, Any]]:
        for entry in ref["key_envelope"].get("wrapped_keys") or []:
            if entry.get("recipient") == recipient:
                return dict(entry)
        return None

    @staticmethod
    def _capability_authorizes(
        caps: Sequence[Mapping[str, Any]], capability_cid: str, ref: Mapping[str, Any]
    ) -> bool:
        for cap in caps:
            if cap.get("kind") == "ucan_proof_cid" and cap.get("cid") == capability_cid:
                ability = cap.get("ability")
                if ability not in (None, ABILITY_DECRYPT, ABILITY_UNWRAP):
                    continue
                resource = cap.get("resource")
                if resource in (None, ref.get("ciphertext_cid"), ref.get("ref_cid")):
                    return True
        return False

    # -- audit helpers used by tests ----------------------------------------

    def scan_persistence_for_plaintext(self, needle: str = SECRET_FRAGMENT) -> List[str]:
        """Return relative paths of any persisted file containing plaintext needle."""
        hits: List[str] = []
        needle_b = needle.encode("utf-8")
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            # Skip the in-memory-only key material; nothing secret should be on disk.
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if needle_b in data or needle.encode("utf-8") in data:
                hits.append(str(path.relative_to(self.root)))
        return hits

    def all_persisted_json(self) -> List[Tuple[str, Any]]:
        out: List[Tuple[str, Any]] = []
        for path in self.root.rglob("*.json"):
            try:
                out.append((str(path.relative_to(self.root)), json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, ValueError):
                continue
        for path in self.root.rglob("*.jsonl"):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
                for i, line in enumerate(lines):
                    if line.strip():
                        out.append((f"{path.relative_to(self.root)}:{i}", json.loads(line)))
            except (OSError, ValueError):
                continue
        return out


def load_encrypted_artifact_schema() -> Dict[str, Any]:
    if not _SCHEMA_PATH.is_file():
        pytest.skip(f"schema missing: {_SCHEMA_PATH}")
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_encrypted_artifact_ref(ref: Mapping[str, Any], schema: Mapping[str, Any] | None = None) -> None:
    if jsonschema is None:
        pytest.skip("jsonschema unavailable")
    schema = schema or load_encrypted_artifact_schema()
    jsonschema.validate(instance=dict(ref), schema=dict(schema))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def crypto_ready():
    _require_crypto()


@pytest.fixture
def schema():
    return load_encrypted_artifact_schema()


@pytest.fixture
def alice() -> Principal:
    return Principal(did="did:key:z6MkAliceRecipientTestKey01", wrap_key=secrets.token_bytes(32), kid="alice-v1")


@pytest.fixture
def bob() -> Principal:
    return Principal(did="did:key:z6MkBobRecipientTestKey0001", wrap_key=secrets.token_bytes(32), kid="bob-v1")


@pytest.fixture
def store(tmp_path, alice, bob, crypto_ready) -> ConfidentialArtifactStore:
    s = ConfidentialArtifactStore(root=tmp_path / "confidential-store")
    s.register_principal(alice)
    s.register_principal(bob)
    return s


# ---------------------------------------------------------------------------
# Schema / interface contracts
# ---------------------------------------------------------------------------


class TestEncryptedArtifactRefSchema:
    def test_interface_constants(self):
        assert INTERFACE_REF == "EncryptedArtifactRef@1"
        assert INTERFACE_ENVELOPE == "KeyEnvelope@1"
        assert INTERFACE_RECEIPT == "ConfidentialPersistenceReceipt@1"
        assert SCHEMA_MARKER_REF.startswith("mcp++/confidential/")

    def test_schema_loads_and_forbids_plaintext_property_names(self, schema):
        assert schema["title"]
        assert "ciphertext_cid" in schema["required"]
        assert "key_envelope" in schema["required"]
        # metadata propertyNames must reject plaintext / raw key field names
        blocked = schema["properties"]["metadata"]["propertyNames"]["not"]["enum"]
        for name in ("plaintext", "plaintext_b64", "dek", "content_key", "raw_key"):
            assert name in blocked

    def test_sealed_ref_validates_against_schema(self, store, schema, alice):
        ref, _receipt = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cid_for_obj({"cap": "decrypt-alice", "n": 1}),
            correlation_id="corr-1",
            label="payroll-batch",
        )
        validate_encrypted_artifact_ref(ref, schema)
        assert ref["schema"] == SCHEMA_MARKER_REF
        assert ref["key_envelope"]["schema"] == SCHEMA_MARKER_ENVELOPE
        assert CID_RE.match(ref["ciphertext_cid"])
        assert CID_RE.match(ref["ref_cid"])
        assert SECRET_PLAINTEXT not in json.dumps(ref)


# ---------------------------------------------------------------------------
# Persistence non-leakage (acceptance criterion 1)
# ---------------------------------------------------------------------------


class TestNoPlaintextPersistence:
    def test_primary_and_cache_never_write_plaintext(self, store, alice):
        ref, receipt = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cid_for_obj({"cap": "c1"}),
        )
        assert receipt["plaintext_written"] is False
        assert receipt["content_key_persisted"] is False
        assert "primary" in receipt["paths_written"]
        assert "cache" in receipt["paths_written"]
        hits = store.scan_persistence_for_plaintext(SECRET_FRAGMENT)
        assert hits == [], f"plaintext leaked into persistence paths: {hits}"

    def test_local_fallback_never_writes_plaintext(self, store, alice):
        store.primary_down = True
        ref, receipt = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            force_fallback=True,
            capability_cid=cid_for_obj({"cap": "fallback-1"}),
        )
        assert "local_fallback" in receipt["paths_written"]
        assert "primary" not in receipt["paths_written"]
        hits = store.scan_persistence_for_plaintext(SECRET_FRAGMENT)
        assert hits == [], f"fallback leaked plaintext: {hits}"
        # Ciphertext still retrievable from fallback tier.
        assert store._load_ciphertext(ref["ciphertext_cid"]) is not None

    def test_event_dag_metadata_has_no_plaintext(self, store, alice):
        ref, receipt = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cid_for_obj({"cap": "dag-1"}),
        )
        assert store.event_dag, "expected Event DAG node"
        for event in store.event_dag:
            blob = json.dumps(event, sort_keys=True)
            assert SECRET_FRAGMENT not in blob
            assert SECRET_PLAINTEXT not in blob
            assert "plaintext" not in event
            assert event["kind"] == "confidential_artifact_used"
            assert event["ref_cid"] == ref["ref_cid"]
            assert event["ciphertext_cid"] == ref["ciphertext_cid"]
            assert event["metadata"]["plaintext_written"] is False
        assert receipt["schema"] == SCHEMA_MARKER_RECEIPT
        assert receipt["interface"] == INTERFACE_RECEIPT

    def test_logs_never_contain_plaintext(self, store, alice):
        store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cid_for_obj({"cap": "log-1"}),
        )
        for record in store.logs:
            rendered = json.dumps(record.fields, sort_keys=True)
            assert SECRET_FRAGMENT not in rendered
            assert SECRET_PLAINTEXT not in rendered
            for key in record.fields:
                assert key.lower() not in FORBIDDEN_LOG_KEYS
        log_file = store.root / "logs" / "operations.jsonl"
        assert log_file.is_file()
        text = log_file.read_text(encoding="utf-8")
        assert SECRET_FRAGMENT not in text
        assert SECRET_PLAINTEXT not in text

    def test_all_persisted_json_surfaces_are_clean(self, store, alice, bob):
        cap = cid_for_obj({"cap": "multi"})
        store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did, bob.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cap,
        )
        store.primary_down = True
        store.seal(
            SECRET_PLAINTEXT + "-again",
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            force_fallback=True,
            capability_cid=cid_for_obj({"cap": "multi-2"}),
        )
        for rel, doc in store.all_persisted_json():
            blob = json.dumps(doc, sort_keys=True)
            assert SECRET_FRAGMENT not in blob, rel
            assert "TOP-SECRET" not in blob, rel


# ---------------------------------------------------------------------------
# Integrity: altered ciphertext fails verify (acceptance criterion 2)
# ---------------------------------------------------------------------------


class TestAlteredCiphertextFailsVerify:
    def test_tampered_package_fails_cid_verify(self, store, alice):
        ref, _ = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cid_for_obj({"cap": "tamper-1"}),
        )
        package = bytearray(store._load_ciphertext(ref["ciphertext_cid"]) or b"")
        assert package
        package[-1] ^= 0x01  # flip last tag bit
        with pytest.raises(ConfidentialError) as exc:
            store.verify_ciphertext(ref, bytes(package))
        assert exc.value.code == "ciphertext_integrity_failed"

    def test_tampered_package_fails_aead_open_even_if_cid_forced(self, store, alice):
        """If an attacker rewrites store under a new CID, AEAD still fails open."""
        ref, _ = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cid_for_obj({"cap": "tamper-2"}),
        )
        package = bytearray(store._load_ciphertext(ref["ciphertext_cid"]) or b"")
        package[20] ^= 0x5A
        # Re-address under the tampered bytes and try open with a forged ref cid field.
        forged = dict(ref)
        forged["ciphertext_cid"] = cid_for_bytes(bytes(package))
        with pytest.raises(ConfidentialError) as exc:
            store.open(
                forged,
                recipient=alice.did,
                capability_cid=cid_for_obj({"cap": "tamper-2"}),
                package=bytes(package),
            )
        assert exc.value.code in {"aead_verify_failed", "unwrap_failed", "capability_not_granted"}

    def test_authorized_roundtrip_succeeds(self, store, alice):
        cap = cid_for_obj({"cap": "ok-1"})
        ref, _ = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cap,
        )
        assert store.verify_ciphertext(ref) is True
        opened = store.open(ref, recipient=alice.did, capability_cid=cap)
        assert opened.decode("utf-8") == SECRET_PLAINTEXT
        # Round-trip must not leave plaintext on disk.
        assert store.scan_persistence_for_plaintext() == []


# ---------------------------------------------------------------------------
# Authorization fail-closed (acceptance criterion 3 + effects)
# ---------------------------------------------------------------------------


class TestUnauthorizedAndRevokedAccess:
    def test_unauthorized_read_without_recipient_key_fails(self, store, alice):
        cap = cid_for_obj({"cap": "authz-1"})
        ref, _ = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cap,
        )
        outsider = "did:key:z6MkOutsiderNoKeyMaterial01"
        with pytest.raises(ConfidentialError) as exc:
            store.open(ref, recipient=outsider, capability_cid=cap)
        assert exc.value.code in {"wrong_recipient", "unauthorized_read"}

    def test_wrong_recipient_fails_closed(self, store, alice, bob):
        cap = cid_for_obj({"cap": "authz-2"})
        ref, _ = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],  # bob is registered but not a wrap recipient
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cap,
        )
        with pytest.raises(ConfidentialError) as exc:
            store.open(ref, recipient=bob.did, capability_cid=cap)
        assert exc.value.code == "wrong_recipient"

    def test_missing_capability_fails_when_caps_declared(self, store, alice):
        cap = cid_for_obj({"cap": "authz-3"})
        ref, _ = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cap,
        )
        with pytest.raises(ConfidentialError) as exc:
            store.open(ref, recipient=alice.did, capability_cid=None)
        assert exc.value.code == "capability_required"

    def test_revoked_capability_fails_closed(self, store, alice):
        cap = cid_for_obj({"cap": "authz-4"})
        ref, _ = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cap,
        )
        # Pre-revocation success proves the path is otherwise valid.
        assert store.open(ref, recipient=alice.did, capability_cid=cap).decode() == SECRET_PLAINTEXT
        store.revoke_capability(cap)
        with pytest.raises(ConfidentialError) as exc:
            store.open(ref, recipient=alice.did, capability_cid=cap)
        assert exc.value.code == "capability_revoked"
        # Revocation does not erase historical ciphertext (honest semantics).
        assert store._load_ciphertext(ref["ciphertext_cid"]) is not None
        assert store.scan_persistence_for_plaintext() == []

    def test_revoked_content_key_fails_closed(self, store, alice):
        cap = cid_for_obj({"cap": "authz-5"})
        ref, _ = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cap,
        )
        ck = ref["key_envelope"]["content_key_id"]
        store.revoke_content_key(ck)
        with pytest.raises(ConfidentialError) as exc:
            store.open(ref, recipient=alice.did, capability_cid=cap)
        assert exc.value.code == "content_key_revoked"

    def test_wrong_capability_cid_fails_closed(self, store, alice):
        cap = cid_for_obj({"cap": "authz-6"})
        other = cid_for_obj({"cap": "other"})
        ref, _ = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cap,
        )
        with pytest.raises(ConfidentialError) as exc:
            store.open(ref, recipient=alice.did, capability_cid=other)
        assert exc.value.code in {"capability_not_granted", "capability_revoked"}


# ---------------------------------------------------------------------------
# ConfidentialPersistenceReceipt@1
# ---------------------------------------------------------------------------


class TestConfidentialPersistenceReceipt:
    def test_receipt_attests_use_without_disclosure(self, store, alice):
        cap = cid_for_obj({"cap": "receipt-1"})
        ref, receipt = store.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkIssuerTestKey000000001",
            capability_cid=cap,
        )
        assert receipt["schema"] == SCHEMA_MARKER_RECEIPT
        assert receipt["interface"] == INTERFACE_RECEIPT
        assert receipt["ref_cid"] == ref["ref_cid"]
        assert receipt["ciphertext_cid"] == ref["ciphertext_cid"]
        assert receipt["plaintext_written"] is False
        assert receipt["kind"] == "confidential_artifact_persisted"
        assert SECRET_FRAGMENT not in json.dumps(receipt)
        assert receipt["event_cid"]
        # Receipt file on disk is also clean.
        receipt_path = store.root / "primary" / f"{ref['ref_cid']}.receipt.json"
        assert receipt_path.is_file()
        assert SECRET_FRAGMENT not in receipt_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Logging harness safety (conflict policy: do not log plaintext in tests)
# ---------------------------------------------------------------------------


class TestHarnessDoesNotLogPlaintext:
    def test_python_logging_capture_has_no_secret(self, store, alice, caplog):
        cap = cid_for_obj({"cap": "pylog-1"})
        with caplog.at_level(logging.DEBUG):
            logging.getLogger("mcpp.confidential").info(
                "sealing artifact correlation=%s", "corr-no-secret"
            )
            store.seal(
                SECRET_PLAINTEXT,
                recipients=[alice.did],
                issuer="did:key:z6MkIssuerTestKey000000001",
                capability_cid=cap,
            )
        assert SECRET_FRAGMENT not in caplog.text
        assert SECRET_PLAINTEXT not in caplog.text

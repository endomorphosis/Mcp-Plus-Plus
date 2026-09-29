"""Advisory answer cache. Disabled unless a cache directory is configured."""

import hashlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp_pp_system_one.config import SystemOneConfig

STAGE_TOOL_RANK = "tool-rank"
STAGE_POLICY = "policy"

_KEY_SEP = "\x1f"
_MATERIAL_SEP = "\x1e"


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("cache write made no progress")
        view = view[written:]


def cache_key(
    *,
    trust_domain: str,
    model_id: str | None,
    question_set_hash: str,
    stage: str,
    cid_material: str,
) -> str:
    """Join the cache identity. Thresholds are not part of the key."""
    if not isinstance(trust_domain, str) or trust_domain.strip() == "":
        raise ValueError("trust_domain is required when the cache is enabled")
    if not isinstance(stage, str) or stage.strip() == "":
        raise ValueError("stage is required")
    model = "" if model_id is None else model_id
    return _KEY_SEP.join(
        (trust_domain, model, question_set_hash, stage, cid_material)
    )


def descriptor_cid_material(task_hint_cid: str, interface_cid: str) -> str:
    """``task_hint_cid`` plus ``interface_cid`` for a descriptor judgement."""
    return f"{task_hint_cid}{_MATERIAL_SEP}{interface_cid}"


def policy_cid_material(clause_canonical: bytes, content_cid: str | None) -> str:
    """Canonical residual-clause bytes plus ``input_cid`` or ``output_cid``."""
    if not isinstance(clause_canonical, (bytes, bytearray)):
        raise TypeError("clause_canonical must be canonical bytes")
    extra = "" if content_cid is None else content_cid
    # Separator keeps clause bytes from gluing onto the content CID.
    return bytes(clause_canonical).decode("utf-8") + _MATERIAL_SEP + extra


class AnswerCache:
    """File cache of raw answers. One directory, mode ``0600`` entries.

    The stored value is the raw answer map. Callers reapply thresholds.
    """

    def __init__(
        self,
        config: SystemOneConfig | None = None,
        *,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.config = config if config is not None else SystemOneConfig()
        self._now = now or time.time

    @property
    def enabled(self) -> bool:
        return self._directory() is not None

    def ttl_s(self, stage: str) -> int:
        if stage == STAGE_POLICY or stage.startswith("policy"):
            return int(self.config.policy_cache_ttl_s)
        return int(self.config.cache_ttl_s)

    def get(self, key: str) -> Any | None:
        if not self.enabled:
            return None
        path = self._path(key)
        if not path.is_file():
            return None
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            stored_at = float(row["stored_at"])
            stage = row["stage"]
            answers = row["answers"]
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            # A corrupt entry is a miss. The caller still has to recompute.
            self._unlink(path)
            return None
        if row.get("key") != key:
            return None
        parts = key.split(_KEY_SEP)
        if len(parts) == 5 and stage != parts[3]:
            return None
        if self._now() - stored_at >= self.ttl_s(stage):
            self._unlink(path)
            return None
        return answers

    def put(
        self,
        key: str,
        answers: Any,
        *,
        stage: str,
        model_id: str | None = None,
    ) -> bool:
        """Store ``answers``. Returns False when the cache directory is unset."""
        directory = self._directory()
        if directory is None:
            return False
        if not isinstance(stage, str) or stage.strip() == "":
            raise ValueError("stage is required")
        row = {
            "key": key,
            "answers": answers,
            "model_id": model_id,
            "stored_at": self._now(),
            "stage": stage,
        }
        payload = json.dumps(
            row,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        self._write_exclusive(directory / self._filename(key), payload)
        return True

    def _directory(self) -> Path | None:
        raw = self.config.cache_dir
        if not isinstance(raw, str) or raw.strip() == "":
            return None
        return Path(raw.strip())

    def _filename(self, key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        directory = self._directory()
        if directory is None:
            raise RuntimeError("cache directory is unset")
        return directory / self._filename(key)

    def _unlink(self, path: Path) -> None:
        try:
            path.unlink()
        except OSError:
            return

    def _write_exclusive(self, path: Path, payload: bytes) -> None:
        directory = path.parent
        directory.mkdir(parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        temporary = directory / f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            _write_all(fd, payload)
            os.fsync(fd)
        except Exception:
            os.close(fd)
            self._unlink(temporary)
            raise
        os.close(fd)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)

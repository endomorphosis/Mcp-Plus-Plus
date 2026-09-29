"""Process-local flags. Defaults leave the tool ranker unset."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field


def _flag(env: Mapping[str, str], name: str) -> bool:
    raw = env.get(name)
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _optional(env: Mapping[str, str], name: str) -> str | None:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return None
    return raw


@dataclass(frozen=True)
class SystemOneConfig:
    enabled: bool = False
    tool_rank: bool = False
    policy_residual: bool = False
    hazard: bool = False
    api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://api.typesafe.ai"
    model: str = "jev-1.13.0"
    timeout_s: float = 0.35
    retry_budget_s: float = 0.80
    tool_deadline_s: float = 8.0
    policy_deadline_s: float = 0.80
    max_peers: int = 32
    max_descriptors: int = 1024
    chunk: int = 32
    rerank_k: int = 3
    max_exposed: int = 3
    gate: float = 0.30
    fits: float = 0.30
    override_exclude: float = 0.50
    read_confidence: float = 0.60
    write_confidence: float = 0.90
    prohibition_review: float = 0.35
    prohibition_deny: float = 0.70
    permission_allow: float = 0.85
    hazard_action: float = 0.70
    severity_block: float = 2.0
    trust_domain: str | None = None
    cache_dir: str | None = None
    cache_ttl_s: int = 3600
    policy_cache_ttl_s: int = 300
    default_card_tokens: int = 120

    def __post_init__(self) -> None:
        if self.max_exposed > self.rerank_k:
            raise ValueError("max_exposed must be <= rerank_k")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "SystemOneConfig":
        env = os.environ if environ is None else environ
        base_url = _optional(env, "TYPESAFE_BASE_URL")
        if base_url is None:
            # TYPESAFE_ENDPOINT is not the SDK base-url variable. Read it only as a fallback.
            base_url = _optional(env, "TYPESAFE_ENDPOINT") or "https://api.typesafe.ai"
        return cls(
            enabled=_flag(env, "MCPPP_SYSTEM_ONE"),
            tool_rank=_flag(env, "MCPPP_SYSTEM_ONE_TOOL_RANK"),
            policy_residual=_flag(env, "MCPPP_SYSTEM_ONE_POLICY_RESIDUAL"),
            hazard=_flag(env, "MCPPP_SYSTEM_ONE_HAZARD"),
            api_key=_optional(env, "TYPESAFE_API_KEY"),
            base_url=base_url,
            model=env.get("MCPPP_SYSTEM_ONE_MODEL", "jev-1.13.0") or "jev-1.13.0",
            timeout_s=_float(env, "MCPPP_SYSTEM_ONE_TIMEOUT_S", 0.35),
            retry_budget_s=_float(env, "MCPPP_SYSTEM_ONE_RETRY_BUDGET_S", 0.80),
            tool_deadline_s=_float(env, "MCPPP_SYSTEM_ONE_TOOL_DEADLINE_S", 8.0),
            policy_deadline_s=_float(env, "MCPPP_SYSTEM_ONE_POLICY_DEADLINE_S", 0.80),
            max_peers=_int(env, "MCPPP_SYSTEM_ONE_MAX_PEERS", 32),
            max_descriptors=_int(env, "MCPPP_SYSTEM_ONE_MAX_DESCRIPTORS", 1024),
            chunk=_int(env, "MCPPP_SYSTEM_ONE_CHUNK", 32),
            rerank_k=_int(env, "MCPPP_SYSTEM_ONE_RERANK_K", 3),
            max_exposed=_int(env, "MCPPP_SYSTEM_ONE_MAX_EXPOSED", 3),
            gate=_float(env, "MCPPP_SYSTEM_ONE_GATE", 0.30),
            fits=_float(env, "MCPPP_SYSTEM_ONE_FITS", 0.30),
            override_exclude=_float(env, "MCPPP_SYSTEM_ONE_OVERRIDE", 0.50),
            read_confidence=_float(env, "MCPPP_SYSTEM_ONE_READ_CONFIDENCE", 0.60),
            write_confidence=_float(env, "MCPPP_SYSTEM_ONE_WRITE_CONFIDENCE", 0.90),
            prohibition_review=_float(env, "MCPPP_SYSTEM_ONE_PROHIBITION_REVIEW", 0.35),
            prohibition_deny=_float(env, "MCPPP_SYSTEM_ONE_PROHIBITION_DENY", 0.70),
            permission_allow=_float(env, "MCPPP_SYSTEM_ONE_PERMISSION_ALLOW", 0.85),
            hazard_action=_float(env, "MCPPP_SYSTEM_ONE_HAZARD_ACTION", 0.70),
            severity_block=_float(env, "MCPPP_SYSTEM_ONE_SEVERITY_BLOCK", 2.0),
            trust_domain=_optional(env, "MCPPP_SYSTEM_ONE_TRUST_DOMAIN"),
            cache_dir=_optional(env, "MCPPP_SYSTEM_ONE_CACHE_DIR"),
            cache_ttl_s=_int(env, "MCPPP_SYSTEM_ONE_CACHE_TTL_S", 3600),
            policy_cache_ttl_s=_int(env, "MCPPP_SYSTEM_ONE_POLICY_CACHE_TTL_S", 300),
            default_card_tokens=_int(env, "MCPPP_SYSTEM_ONE_DEFAULT_CARD_TOKENS", 120),
        )

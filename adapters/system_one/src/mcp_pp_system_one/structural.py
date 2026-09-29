"""Deterministic structural slicer. It fills a Prior and does not expose tools."""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from mcp_pp_system_one.config import SystemOneConfig
from mcp_pp_system_one.ports import Budget, Prior, SliceReason, ToolSliceRequest, reason

# Case-insensitive substrings on description and method text. A hit only shrinks the pool.
_LEXICAL_DENYLIST = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "you are now",
    "do anything now",
    "reveal your",
    "developer message",
)

_TOKEN = re.compile(r"[a-z0-9]+")
_READ_ABILITIES = frozenset({"read", "read-only", "readonly"})
_WRITE_SEGMENTS = frozenset(
    {
        "write",
        "create",
        "update",
        "patch",
        "delete",
        "drop",
        "rm",
        "spend",
        "sign",
        "admin",
        "*",
    }
)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _hints(desc: Any) -> Mapping[str, Any]:
    hints = _get(desc, "resource_cost_hints", None)
    if isinstance(hints, Mapping):
        return hints
    return {}


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value <= 0:
        return None
    if isinstance(value, int):
        return value
    return math.ceil(value)


def side_effect(desc: Any, *, x402_priced: bool, ucan_write: bool) -> str:
    hint = _hints(desc).get("side_effect")
    if hint == "read" and not x402_priced and not ucan_write:
        return "read"
    return "write"


def _cid(desc: Any) -> str | None:
    value = _get(desc, "interface_cid", None)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _peer_id(desc: Any) -> str:
    value = _get(desc, "peer_id", "")
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", "surrogateescape")
    return ""


def _method_list(desc: Any) -> list[Any] | None:
    methods = _get(desc, "methods", None)
    if not isinstance(methods, (list, tuple)):
        return None
    return list(methods)


def _method_name(method: Any) -> str | None:
    name = _get(method, "name", None)
    if isinstance(name, str) and name.strip():
        return name
    return None


def _schema_ok(desc: Any, methods: list[Any] | None) -> bool:
    name = _get(desc, "name", None)
    namespace = _get(desc, "namespace", None)
    if not isinstance(name, str) or not name.strip():
        return False
    if not isinstance(namespace, str) or not namespace.strip():
        return False
    if _cid(desc) is None:
        return False
    if not methods:
        return False
    return all(_method_name(method) is not None for method in methods)


def _requires(desc: Any) -> list[str] | None:
    value = _get(desc, "requires", [])
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        return None
    entries: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            return None
        entries.append(entry)
    return entries


def _text_blob(desc: Any, methods: list[Any]) -> str:
    parts: list[str] = []
    for key in ("description", "summary"):
        value = _get(desc, key, None)
        if isinstance(value, str):
            parts.append(value)
    for method in methods:
        for key in ("name", "description", "summary"):
            value = _get(method, key, None)
            if isinstance(value, str):
                parts.append(value)
    return "\n".join(parts).lower()


def _lexical_hit(desc: Any, methods: list[Any]) -> bool:
    blob = _text_blob(desc, methods)
    return any(phrase in blob for phrase in _LEXICAL_DENYLIST)


def _interface_cost(desc: Any, methods: list[Any] | None, default_card: int) -> int:
    # A positive hint is the whole-interface total. Otherwise each method is one card.
    hints = _hints(desc)
    hinted = _positive_int(hints.get("tokens"))
    if hinted is None:
        hinted = _positive_int(hints.get("token_cost"))
    if hinted is not None:
        return hinted
    count = len(methods) if methods is not None else 0
    return default_card * count


def _fits(cost: int, budget: Budget) -> bool:
    tokens = budget.tokens
    if tokens is None:
        return True
    if isinstance(tokens, bool) or not isinstance(tokens, (int, float)):
        return False
    if not math.isfinite(float(tokens)):
        return False
    return cost <= tokens


def _descriptor_priced(desc: Any) -> bool:
    if _get(desc, "x402_priced") is True:
        return True
    hints = _hints(desc)
    if hints.get("x402_priced") is True or hints.get("x402") is True:
        return True
    x402 = hints.get("x402")
    if isinstance(x402, Mapping) and len(x402) > 0:
        return True
    for key in ("price", "x402_price", "amount", "amount_atomic"):
        if _positive_int(hints.get(key)) is not None:
            return True
    return False


def _ability_is_read_only(ability: str) -> bool:
    text = ability.strip().lower()
    if not text:
        return False
    if text in _READ_ABILITIES:
        return True
    parts = [part for part in re.split(r"[/:.]", text) if part]
    if any(part in _WRITE_SEGMENTS for part in parts):
        return False
    return bool(parts) and parts[-1] in _READ_ABILITIES


def _ucan_write(cid: str, abilities: Mapping[str, Any]) -> bool:
    raw = abilities.get(cid) if abilities else None
    if raw is None:
        return False
    if isinstance(raw, str):
        values: tuple[Any, ...] = (raw,)
    elif isinstance(raw, (list, tuple, set, frozenset)):
        values = tuple(raw)
    else:
        return True
    saw = False
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        saw = True
        if not _ability_is_read_only(value):
            return True
    return not saw


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def _overlap(hint: str | None, desc: Any, methods: list[Any]) -> int:
    if not hint:
        return 0
    hint_tokens = _tokens(hint)
    if not hint_tokens:
        return 0
    bag: set[str] = set()
    tags = _get(desc, "semantic_tags", None) or []
    if isinstance(tags, (list, tuple)):
        for tag in tags:
            if isinstance(tag, str):
                bag |= _tokens(tag)
    for method in methods:
        name = _method_name(method)
        if name is not None:
            bag |= _tokens(name)
    return len(hint_tokens & bag)


def _candidate_keys(descriptors: tuple[Any, ...]) -> tuple[set[str], set[str]]:
    names: set[str] = set()
    cids: set[str] = set()
    for desc in descriptors:
        name = _get(desc, "name", None)
        if isinstance(name, str) and name.strip():
            names.add(name)
        cid = _cid(desc)
        if cid is not None:
            cids.add(cid)
    return names, cids


@dataclass
class _Eligible:
    order: int
    overlap: int
    cost: int
    cid: str


def _finish(
    pool: tuple[str, ...],
    excluded: set[str],
    reasons: list[SliceReason],
    side: dict[str, str],
    cost: dict[str, int],
) -> Prior:
    return Prior(
        pool=pool,
        excluded=frozenset(excluded),
        reasons=tuple(reasons),
        side_effect=MappingProxyType(dict(side)),
        cost_tokens=MappingProxyType(dict(cost)),
    )


class StructuralSlicer:
    implementation_id = "structural-slicer/v1"

    def __init__(self, config: SystemOneConfig | None = None) -> None:
        self.config = config or SystemOneConfig()

    def filter(self, request: ToolSliceRequest) -> Prior:
        cfg = self.config
        descriptors = tuple(request.descriptors)
        names, cids = _candidate_keys(descriptors)
        capabilities = set(request.capabilities)
        allow = request.ucan_allowlist
        excluded: set[str] = set()
        reasons: list[SliceReason] = []
        side: dict[str, str] = {}
        cost: dict[str, int] = {}

        def record_class(desc: Any, cid: str | None, methods: list[Any] | None) -> None:
            if cid is None or cid in side:
                return
            # Descriptor price flags and validated abilities only ever widen read to write.
            priced = cid in request.x402_priced or _descriptor_priced(desc)
            side[cid] = side_effect(
                desc,
                x402_priced=priced,
                ucan_write=_ucan_write(cid, request.ucan_abilities),
            )
            cost[cid] = _interface_cost(desc, methods, cfg.default_card_tokens)

        def exclude(cid: str | None, code: str) -> None:
            if cid is not None:
                if cid in excluded:
                    return
                excluded.add(cid)
            reasons.append(reason(code, cid))

        if request.ucan_required and allow is None:
            for desc in descriptors:
                cid = _cid(desc)
                record_class(desc, cid, _method_list(desc))
                exclude(cid, "authority_unverified")
            return _finish((), excluded, reasons, side, cost)

        def ucan_code(desc: Any) -> str | None:
            if allow is None:
                return None
            cid = _cid(desc)
            if cid is None or cid not in allow:
                return "excluded_ucan"
            return None

        groups: dict[str, list[Any]] = {}
        order: dict[str, tuple[int, bytes]] = {}
        for index, desc in enumerate(descriptors):
            peer = _peer_id(desc)
            groups.setdefault(peer, []).append(desc)
            if peer not in order:
                order[peer] = (index, peer.encode("utf-8"))

        # UCAN exclusions do not consume a peer slot. Survivors keep caller order, then peer_id bytes.
        peer_keys = sorted(groups, key=lambda peer: order[peer])
        examined: list[str] = []
        ucan_only: list[str] = []
        for peer in peer_keys:
            if any(ucan_code(desc) is None for desc in groups[peer]):
                examined.append(peer)
            else:
                ucan_only.append(peer)

        for peer in ucan_only:
            for desc in groups[peer]:
                cid = _cid(desc)
                record_class(desc, cid, _method_list(desc))
                exclude(cid, ucan_code(desc) or "excluded_ucan")

        eligible: list[_Eligible] = []
        seen_eligible: set[str] = set()
        sequence = 0
        for peer_index, peer in enumerate(examined):
            over_cap = peer_index >= cfg.max_peers
            for desc in groups[peer]:
                methods = _method_list(desc)
                cid = _cid(desc)
                record_class(desc, cid, methods)
                if cid is not None and cid in excluded:
                    continue
                code = ucan_code(desc)
                if code is None and over_cap:
                    code = "not_examined_peer_cap"
                if code is None:
                    code = _admission_failure(
                        desc,
                        methods,
                        names,
                        cids,
                        capabilities,
                        request.budget,
                        cfg.default_card_tokens,
                    )
                if code is not None:
                    exclude(cid, code)
                    continue
                if cid is None or cid in seen_eligible:
                    continue
                seen_eligible.add(cid)
                eligible.append(
                    _Eligible(
                        order=sequence,
                        overlap=_overlap(request.task_hint, desc, methods or []),
                        cost=cost[cid],
                        cid=cid,
                    )
                )
                sequence += 1

        eligible = [item for item in eligible if item.cid not in excluded]
        # Overlap is only the truncation key at the descriptor cap. It never admits a tool.
        ranked = sorted(eligible, key=lambda item: (-item.overlap, item.cost, item.cid))
        keep = {item.cid for item in ranked[: cfg.max_descriptors]}
        for item in ranked[cfg.max_descriptors :]:
            exclude(item.cid, "not_examined_descriptor_cap")
        pool = tuple(
            item.cid
            for item in eligible
            if item.cid in keep and item.cid not in excluded
        )
        return _finish(pool, excluded, reasons, side, cost)


def _admission_failure(
    desc: Any,
    methods: list[Any] | None,
    names: set[str],
    cids: set[str],
    capabilities: set[str],
    budget: Budget,
    default_card: int,
) -> str | None:
    if methods is None or not _schema_ok(desc, methods):
        return "schema_invalid"
    requires = _requires(desc)
    if requires is None:
        return "schema_invalid"
    for entry in requires:
        if entry not in capabilities and entry not in names and entry not in cids:
            return "requires_unsatisfied"
    if _lexical_hit(desc, methods):
        return "descriptor_override_lex"
    if not _fits(_interface_cost(desc, methods, default_card), budget):
        return "budget_exhausted"
    return None

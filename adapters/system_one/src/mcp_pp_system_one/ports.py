"""Local tool-slice types. Callers depend on these, not on a vendor SDK."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class StageKind(str, Enum):
    HALT = "halt"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class SliceReason:
    code: str
    interface_cid: str | None = None


def reason(code: str, interface_cid: str | None = None) -> SliceReason:
    return SliceReason(code=code, interface_cid=interface_cid)


@dataclass(frozen=True)
class Budget:
    """Token budget is the wire number. ``max_bytes`` is local and not a fit check."""

    tokens: float | None = None
    max_bytes: int | None = None


@dataclass(frozen=True)
class ToolSlice:
    interface_cids: tuple[str, ...]
    reasons: tuple[SliceReason, ...]
    implementation_id: str
    budget_tokens_used: float
    abstained: bool


@dataclass(frozen=True)
class Prior:
    pool: tuple[str, ...]
    excluded: frozenset[str]
    reasons: tuple[SliceReason, ...]
    side_effect: Mapping[str, str]
    cost_tokens: Mapping[str, int]


@dataclass(frozen=True)
class StageOutcome:
    kind: StageKind
    slice: ToolSlice | None
    excluded: frozenset[str]
    reasons: tuple[SliceReason, ...]


@dataclass(frozen=True)
class ToolSliceRequest:
    descriptors: Sequence[Any] = ()
    task_hint_cid: str | None = None
    task_hint: str | None = None
    budget: Budget | int | float | None = None
    capabilities: frozenset[str] = frozenset()
    ucan_allowlist: frozenset[str] | None = None
    ucan_required: bool = False
    ucan_abilities: Mapping[str, Any] = field(default_factory=dict)
    x402_priced: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "descriptors", tuple(self.descriptors))
        object.__setattr__(
            self,
            "capabilities",
            _string_set("capabilities", self.capabilities),
        )
        if self.ucan_allowlist is not None:
            object.__setattr__(
                self,
                "ucan_allowlist",
                _string_set("ucan_allowlist", self.ucan_allowlist),
            )
        object.__setattr__(
            self,
            "x402_priced",
            _string_set("x402_priced", self.x402_priced),
        )
        object.__setattr__(self, "budget", _coerce_budget(self.budget))


class ToolSlicePort(Protocol):
    def select(self, request: ToolSliceRequest) -> ToolSlice: ...


def _string_set(name: str, value: Any) -> frozenset[str]:
    if isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be a collection of strings, not text")
    return frozenset(item for item in value if isinstance(item, str))


def _coerce_budget(value: Budget | float | None) -> Budget:
    if value is None:
        return Budget()
    if isinstance(value, Budget):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("budget must be a number or Budget")
    return Budget(tokens=float(value))

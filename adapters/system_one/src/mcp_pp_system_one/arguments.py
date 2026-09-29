"""Closed arguments only. Open strings and numbers are not invented."""

import math
from dataclasses import dataclass, field
from typing import Any

STATED = 0.70


@dataclass
class Dispatch:
    arguments: dict[str, Any] = field(default_factory=dict)
    call_strength: float | None = None
    called: bool = False
    reason: str | None = None
    ucan_budget: Any = None
    x402_amount: Any = None


def _unit(value: Any) -> float | None:
    # bool is an int, and float(True) == 1.0 would clear every floor.
    # Only 0 and 1 are unit-interval ints. float(2**1024) raises OverflowError.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, int) and value not in (0, 1):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        return None
    return number


def _noul(answer: Any) -> float | None:
    if not isinstance(answer, dict) or answer.get("type") != "noul":
        return None
    return _unit(answer.get("noul"))


def _strength(answer: dict[str, Any]) -> float:
    kind = answer.get("type")
    if kind in ("choice", "score"):
        score = _unit(answer.get("confidence"))
        # Do not coerce with `or 0.0`: missing and non-unit scores are not zero.
        if score is None:
            return math.nan
        return score
    if kind == "noul":
        score = _unit(answer.get("noul"))
        if score is None:
            return math.nan
        return max(score, 1.0 - score)
    # Unknown kinds are not model scores. 0.0 fails the call floor.
    return 0.0


def _properties(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    return properties


def _required(schema: Any) -> set[str]:
    if not isinstance(schema, dict):
        return set()
    required = schema.get("required")
    if not isinstance(required, (list, tuple)):
        return set()
    return {name for name in required if isinstance(name, str)}


def _string_enum(prop: Any) -> list[Any] | None:
    """Closed choice. ``type`` may be omitted or a list that includes ``string``."""
    if not isinstance(prop, dict):
        return None
    enum = prop.get("enum")
    if not isinstance(enum, list) or not enum:
        return None
    kind = prop.get("type")
    if kind is None or kind == "string":
        return enum
    if isinstance(kind, list) and "string" in kind:
        return enum
    return None


def _array_enum(prop: Any) -> list[Any] | None:
    if not isinstance(prop, dict) or prop.get("type") != "array":
        return None
    items = prop.get("items")
    if not isinstance(items, dict):
        return None
    enum = items.get("enum")
    if not isinstance(enum, list) or not enum:
        return None
    return enum


def _choice_lookup(enum: list[Any]) -> dict[str, Any] | None:
    """Criterion key to the original item. None when two unequal items share one key."""
    lookup: dict[str, Any] = {}
    for item in enum:
        key = str(item)
        if key in lookup and lookup[key] != item:
            return None
        lookup[key] = item
    return lookup


def _copied(value: Any) -> Any:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value


def questions_for(schema: dict[str, Any]) -> dict[str, Any]:
    questions: dict[str, Any] = {}
    for name, prop in _properties(schema).items():
        if not isinstance(prop, dict):
            continue
        enum = _string_enum(prop)
        lookup = _choice_lookup(enum) if enum is not None else None
        if lookup is not None:
            questions[name] = {
                "type": "choice",
                "instructions": f"Which value of `arguments.{name}` was stated?",
                "criteria": {key: None for key in lookup},
            }
            questions[f"{name}?"] = {
                "type": "noul",
                "instructions": f"Does the task state `arguments.{name}`?",
                "criteria": {"true": "It was stated.", "false": "It was not stated."},
            }
        elif prop.get("type") == "boolean":
            questions[f"{name}?"] = {
                "type": "noul",
                "instructions": f"Does the task state `arguments.{name}`?",
                "criteria": {"true": "It was stated.", "false": "It was not stated."},
            }
            questions[name] = {
                "type": "noul",
                "instructions": f"Is `arguments.{name}` true?",
                "criteria": {"true": "True.", "false": "False."},
            }
        else:
            members = _array_enum(prop)
            if members is None:
                continue
            for option in members:
                questions[f"{name}.{option}"] = {
                    "type": "noul",
                    "instructions": (
                        f"Does the task include `{option}` in `arguments.{name}`?"
                    ),
                    "criteria": {"true": "Included.", "false": "Not included."},
                }
    return questions


def fill(
    schema: dict[str, Any],
    answers: dict[str, Any],
    *,
    side_effect: str,
    ucan_budget: Any = None,
    x402_amount: Any = None,
    read_floor: float = 0.60,
    write_floor: float = 0.90,
) -> Dispatch:
    result = Dispatch(ucan_budget=ucan_budget, x402_amount=x402_amount)
    if not isinstance(schema, dict) or not isinstance(answers, dict):
        result.reason = "closed_argument_unstated"
        return result
    required = _required(schema)
    properties = _properties(schema)
    contributed: list[dict[str, Any]] = []
    for name, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        kind = prop.get("type")
        enum = _string_enum(prop)
        members = _array_enum(prop)
        open_argument = (
            kind in ("number", "integer", "object")
            or (kind == "string" and enum is None)
            or (kind == "array" and members is None)
        )
        if open_argument:
            if name in required:
                if "default" not in prop:
                    result.reason = "open_argument_unset"
                    return result
                # A default fills the gap but is not a model answer, so it cannot call.
                result.arguments[name] = _copied(prop["default"])
            continue
        lookup = _choice_lookup(enum) if enum is not None else None
        if enum is not None:
            # Two unequal items that share one string are not a choice.
            if lookup is None:
                if name in required:
                    result.reason = "closed_argument_unstated"
                    return result
                continue
            stated = _noul(answers.get(f"{name}?"))
            if stated is None or stated < STATED:
                if "default" in prop:
                    result.arguments[name] = _copied(prop["default"])
                elif name in required:
                    result.reason = "closed_argument_unstated"
                    return result
                continue
            choice = answers.get(name)
            picked = choice.get("choice") if isinstance(choice, dict) else None
            # A non-string choice is unstated. Membership on a list would raise.
            if (
                not isinstance(choice, dict)
                or choice.get("type") != "choice"
                or not isinstance(picked, str)
                or picked not in lookup
                or _unit(choice.get("confidence")) is None
            ):
                if name in required:
                    result.reason = "closed_argument_unstated"
                    return result
                continue
            result.arguments[name] = lookup[picked]
            # Stated noul only opens the gate. Confidence is what must clear the floor.
            contributed.append(answers[name])
        elif kind == "boolean":
            stated = _noul(answers.get(f"{name}?"))
            if stated is None or stated < STATED:
                if "default" in prop:
                    result.arguments[name] = _copied(prop["default"])
                elif name in required:
                    result.reason = "closed_argument_unstated"
                    return result
                continue
            value = answers.get(name)
            score = _noul(value)
            if score is None:
                if name in required:
                    result.reason = "closed_argument_unstated"
                    return result
                continue
            if score >= STATED:
                result.arguments[name] = True
            elif score <= 0.30:
                result.arguments[name] = False
            elif name in required:
                result.reason = "closed_argument_unstated"
                result.call_strength = max(score, 1.0 - score)
                return result
            else:
                continue
            contributed.append(value)
        elif members is not None:
            chosen = []
            for option in members:
                answer = answers.get(f"{name}.{option}")
                score = _noul(answer)
                if score is not None and score >= STATED:
                    chosen.append(option)
                    contributed.append(answer)
            if chosen:
                result.arguments[name] = chosen
            elif "default" in prop:
                result.arguments[name] = _copied(prop["default"])
            elif name in required:
                result.reason = "closed_argument_unstated"
                return result
    if any(name not in result.arguments for name in required):
        result.called = False
        result.reason = "closed_argument_unstated"
        return result
    if not contributed:
        result.reason = "closed_argument_unstated"
        return result
    result.call_strength = min(_strength(answer) for answer in contributed)
    floor = read_floor if side_effect == "read" else write_floor
    # NaN < floor is false, so a non-finite strength would otherwise dispatch.
    if not math.isfinite(result.call_strength) or result.call_strength < floor:
        result.reason = "below_call_strength"
        return result
    result.called = True
    return result

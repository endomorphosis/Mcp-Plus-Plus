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
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
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


def questions_for(schema: dict[str, Any]) -> dict[str, Any]:
    questions: dict[str, Any] = {}
    properties = schema.get("properties") or {}
    for name, prop in properties.items():
        kind = prop.get("type")
        if kind == "string" and prop.get("enum"):
            questions[name] = {
                "type": "choice",
                "instructions": f"Which value of `arguments.{name}` was stated?",
                "criteria": {str(option): None for option in prop["enum"]},
            }
            questions[f"{name}?"] = {
                "type": "noul",
                "instructions": f"Does the task state `arguments.{name}`?",
                "criteria": {"true": "It was stated.", "false": "It was not stated."},
            }
        elif kind == "boolean":
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
        elif kind == "array" and (prop.get("items") or {}).get("enum"):
            for option in prop["items"]["enum"]:
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
    required = set(schema.get("required") or [])
    properties = schema.get("properties") or {}
    contributed: list[dict[str, Any]] = []
    for name, prop in properties.items():
        kind = prop.get("type")
        raw_items = prop.get("items")
        items = raw_items if isinstance(raw_items, dict) else {}
        items_enum = items.get("enum")
        open_argument = (
            kind in ("number", "integer", "object")
            or (kind == "string" and not prop.get("enum"))
            or (kind == "array" and not items_enum)
        )
        if open_argument:
            if name in required:
                if "default" not in prop:
                    result.reason = "open_argument_unset"
                    return result
                # A default fills the gap but is not a model answer, so it cannot call.
                result.arguments[name] = prop["default"]
            continue
        if kind == "string" and prop.get("enum"):
            stated = _noul(answers.get(f"{name}?"))
            if stated is None or stated < STATED:
                if "default" in prop:
                    result.arguments[name] = prop["default"]
                elif name in required:
                    result.reason = "closed_argument_unstated"
                    return result
                continue
            choice = answers.get(name)
            picked = choice.get("choice") if isinstance(choice, dict) else None
            options = {str(item) for item in prop["enum"]}
            # A non-string choice is unstated. Membership on a list would raise.
            if (
                not isinstance(choice, dict)
                or choice.get("type") != "choice"
                or not isinstance(picked, str)
                or picked not in options
                or _unit(choice.get("confidence")) is None
            ):
                if name in required:
                    result.reason = "closed_argument_unstated"
                    return result
                continue
            result.arguments[name] = picked
            # Stated noul only opens the gate. Confidence is what must clear the floor.
            contributed.append(answers[name])
        elif kind == "boolean":
            stated = _noul(answers.get(f"{name}?"))
            if stated is None or stated < STATED:
                if "default" in prop:
                    result.arguments[name] = prop["default"]
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
        elif kind == "array" and items_enum:
            chosen = []
            for option in items_enum:
                answer = answers.get(f"{name}.{option}")
                score = _noul(answer)
                if score is not None and score >= STATED:
                    chosen.append(option)
                    contributed.append(answer)
            if chosen:
                result.arguments[name] = chosen
            elif "default" in prop:
                result.arguments[name] = prop["default"]
            elif name in required:
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

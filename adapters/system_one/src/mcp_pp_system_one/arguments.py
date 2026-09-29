"""Closed arguments only. Open strings and numbers are not invented."""

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


def _strength(answer: dict[str, Any]) -> float:
    kind = answer.get("type")
    if kind in ("choice", "score"):
        return float(answer.get("confidence") or 0.0)
    if kind == "noul":
        score = float(answer["noul"])
        return max(score, 1.0 - score)
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
        if kind == "string" and not prop.get("enum"):
            if name in required and "default" not in prop:
                result.reason = "open_argument_unset"
                return result
            continue
        if kind in ("number", "integer", "object"):
            if name in required and "default" not in prop:
                result.reason = "open_argument_unset"
                return result
            continue
        if kind == "array" and not (prop.get("items") or {}).get("enum"):
            if name in required and "default" not in prop:
                result.reason = "open_argument_unset"
                return result
            continue
        if kind == "string" and prop.get("enum"):
            stated = answers.get(f"{name}?")
            if not stated or float(stated["noul"]) < STATED:
                if "default" in prop:
                    result.arguments[name] = prop["default"]
                elif name in required:
                    result.reason = "closed_argument_unstated"
                    return result
                continue
            choice = answers.get(name)
            if not choice or choice.get("choice") not in {str(item) for item in prop["enum"]}:
                result.reason = "closed_argument_unstated"
                return result
            result.arguments[name] = choice["choice"]
            contributed.extend([stated, choice])
        elif kind == "boolean":
            stated = answers.get(f"{name}?")
            value = answers.get(name)
            if not stated or float(stated["noul"]) < STATED:
                if name in required and "default" not in prop:
                    result.reason = "closed_argument_unstated"
                    return result
                continue
            if not value:
                result.reason = "closed_argument_unstated"
                return result
            score = float(value["noul"])
            contributed.append(value)
            if score >= STATED:
                result.arguments[name] = True
            elif score <= 0.30:
                result.arguments[name] = False
            elif name in required:
                result.reason = "closed_argument_unstated"
                result.call_strength = _strength(value)
                return result
        elif kind == "array" and (prop.get("items") or {}).get("enum"):
            chosen = []
            for option in prop["items"]["enum"]:
                answer = answers.get(f"{name}.{option}")
                if answer and float(answer["noul"]) >= STATED:
                    chosen.append(option)
                    contributed.append(answer)
            if chosen:
                result.arguments[name] = chosen
            elif name in required and "default" not in prop:
                result.reason = "closed_argument_unstated"
                return result
    if not contributed:
        result.reason = "closed_argument_unstated"
        return result
    result.call_strength = min(_strength(answer) for answer in contributed)
    floor = read_floor if side_effect == "read" else write_floor
    if result.call_strength < floor:
        result.reason = "below_call_strength"
        return result
    result.called = True
    return result

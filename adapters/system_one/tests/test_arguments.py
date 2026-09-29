"""Closed-argument dispatch. Budgets are not arguments."""

import math

from mcp_pp_system_one.arguments import fill, questions_for


def test_boolean_055_does_not_dispatch_a_read():
    schema = {
        "type": "object",
        "required": ["include_volume"],
        "properties": {"include_volume": {"type": "boolean"}},
    }
    answers = {
        "include_volume?": {"type": "noul", "noul": 0.95},
        "include_volume": {"type": "noul", "noul": 0.55},
    }
    result = fill(schema, answers, side_effect="read", ucan_budget=3, x402_amount=10)
    assert result.called is False
    assert result.call_strength == 0.55
    assert result.ucan_budget == 3
    assert result.x402_amount == 10


def test_open_string_has_no_question_and_blocks_when_required():
    schema = {
        "type": "object",
        "required": ["note"],
        "properties": {
            "note": {"type": "string"},
            "limit": {"type": "integer"},
        },
    }
    questions = questions_for(schema)
    assert questions == {}
    rendered = str(questions)
    assert "invented-note" not in rendered
    result = fill(schema, {}, side_effect="read")
    assert result.called is False
    assert result.reason == "open_argument_unset"


def test_array_enum_includes_members_at_or_above_070():
    schema = {
        "type": "object",
        "properties": {
            "symbols": {"type": "array", "items": {"enum": ["NVDA", "AMD"]}},
        },
    }
    questions = questions_for(schema)
    assert "NVDA" in questions["symbols.NVDA"]["instructions"]
    assert "arguments.symbols" in questions["symbols.NVDA"]["instructions"]
    result = fill(
        schema,
        {
            "symbols.NVDA": {"type": "noul", "noul": 0.91},
            "symbols.AMD": {"type": "noul", "noul": 0.20},
        },
        side_effect="read",
        ucan_budget=1,
        x402_amount=2,
    )
    assert result.called is True
    assert result.arguments["symbols"] == ["NVDA"]
    assert result.ucan_budget == 1
    assert result.x402_amount == 2


def _enum_schema(*, required: bool = True, default: str | None = None) -> dict:
    prop: dict = {"type": "string", "enum": ["NVDA", "AMD"]}
    if default is not None:
        prop["default"] = default
    schema: dict = {"type": "object", "properties": {"symbol": prop}}
    if required:
        schema["required"] = ["symbol"]
    return schema


def _choice(confidence: object = 0.99, choice: object = "NVDA") -> dict:
    return {"type": "choice", "choice": choice, "confidence": confidence}


def test_stated_noul_nan_inf_and_above_one_do_not_dispatch():
    schema = _enum_schema()
    for noul in (float("nan"), float("inf"), 1.5, float("-inf"), -0.1, True, "0.95"):
        result = fill(
            schema,
            {"symbol?": {"type": "noul", "noul": noul}, "symbol": _choice()},
            side_effect="read",
            ucan_budget=3,
            x402_amount=10,
        )
        assert result.called is False
        assert "symbol" not in result.arguments
        assert result.ucan_budget == 3
        assert result.x402_amount == 10


def test_choice_confidence_nan_does_not_dispatch():
    result = fill(
        _enum_schema(),
        {
            "symbol?": {"type": "noul", "noul": 0.95},
            "symbol": _choice(confidence=float("nan")),
        },
        side_effect="read",
        ucan_budget=3,
        x402_amount=10,
    )
    assert result.called is False
    assert result.reason == "closed_argument_unstated"
    assert "symbol" not in result.arguments
    assert result.ucan_budget == 3
    assert result.x402_amount == 10


def test_stated_choice_object_is_not_a_stated_noul():
    result = fill(
        _enum_schema(),
        {
            "symbol?": {
                "type": "choice",
                "choice": "NVDA",
                "confidence": 0.99,
                "noul": 0.99,
            },
            "symbol": _choice(),
        },
        side_effect="read",
    )
    assert result.called is False
    assert result.reason == "closed_argument_unstated"
    assert "symbol" not in result.arguments


def test_optional_mid_boolean_does_not_dispatch_alone():
    schema = {
        "type": "object",
        "properties": {"include_volume": {"type": "boolean"}},
    }
    result = fill(
        schema,
        {
            "include_volume?": {"type": "noul", "noul": 0.95},
            "include_volume": {"type": "noul", "noul": 0.40},
        },
        side_effect="read",
        ucan_budget=3,
        x402_amount=10,
    )
    assert result.called is False
    assert "include_volume" not in result.arguments
    assert result.call_strength is None
    assert result.ucan_budget == 3
    assert result.x402_amount == 10


def test_optional_boolean_gap_does_not_block_a_sibling():
    schema = {
        "type": "object",
        "required": ["symbol"],
        "properties": {
            "include_volume": {"type": "boolean"},
            "symbol": {"type": "string", "enum": ["NVDA"]},
        },
    }
    stated = {"include_volume?": {"type": "noul", "noul": 0.95}}
    sibling = {
        "symbol?": {"type": "noul", "noul": 0.95},
        "symbol": {"type": "choice", "choice": "NVDA", "confidence": 0.91},
    }
    for value in (
        {"include_volume": {"type": "noul", "noul": 0.40}},
        {},
    ):
        result = fill(schema, {**stated, **value, **sibling}, side_effect="read")
        assert result.called is True
        assert "include_volume" not in result.arguments
        assert result.arguments["symbol"] == "NVDA"
        assert result.call_strength == 0.91


def test_required_open_default_is_kept_and_does_not_call_alone():
    for prop, expected in (
        ({"type": "string", "default": "x"}, "x"),
        ({"type": "number", "default": 1.5}, 1.5),
        ({"type": "integer", "default": 2}, 2),
        ({"type": "object", "default": {"a": 1}}, {"a": 1}),
        ({"type": "array", "default": ["z"]}, ["z"]),
    ):
        schema = {
            "type": "object",
            "required": ["note", "symbol"],
            "properties": {
                "note": prop,
                "symbol": {"type": "string", "enum": ["NVDA"]},
            },
        }
        filled = fill(
            schema,
            {
                "symbol?": {"type": "noul", "noul": 0.95},
                "symbol": {"type": "choice", "choice": "NVDA", "confidence": 0.99},
            },
            side_effect="read",
        )
        assert filled.arguments["note"] == expected
        assert filled.arguments["symbol"] == "NVDA"
        assert filled.called is True
        assert filled.call_strength == 0.99
        alone = fill(
            {
                "type": "object",
                "required": ["note"],
                "properties": {"note": prop},
            },
            {},
            side_effect="read",
        )
        assert alone.arguments["note"] == expected
        assert alone.called is False


def test_required_open_without_default_blocks_a_filled_sibling():
    for prop in (
        {"type": "string"},
        {"type": "number"},
        {"type": "integer"},
        {"type": "object"},
        {"type": "array"},
        {"type": "array", "items": {}},
    ):
        schema = {
            "type": "object",
            "required": ["symbol", "note"],
            "properties": {
                "symbol": {"type": "string", "enum": ["NVDA"]},
                "note": prop,
            },
        }
        assert questions_for({"type": "object", "properties": {"note": prop}}) == {}
        result = fill(
            schema,
            {
                "symbol?": {"type": "noul", "noul": 0.95},
                "symbol": {"type": "choice", "choice": "NVDA", "confidence": 0.99},
            },
            side_effect="read",
        )
        assert result.called is False
        assert result.reason == "open_argument_unset"


def test_write_floor_accepts_095_and_rejects_080():
    schema = {
        "type": "object",
        "required": ["include_volume"],
        "properties": {"include_volume": {"type": "boolean"}},
    }
    high = fill(
        schema,
        {
            "include_volume?": {"type": "noul", "noul": 0.95},
            "include_volume": {"type": "noul", "noul": 0.95},
        },
        side_effect="write",
        ucan_budget=3,
        x402_amount=10,
    )
    assert high.called is True
    assert high.arguments["include_volume"] is True
    assert high.call_strength == 0.95
    assert high.ucan_budget == 3
    assert high.x402_amount == 10
    low = fill(
        schema,
        {
            "include_volume?": {"type": "noul", "noul": 0.95},
            "include_volume": {"type": "noul", "noul": 0.80},
        },
        side_effect="write",
        ucan_budget=3,
        x402_amount=10,
    )
    assert low.called is False
    assert low.reason == "below_call_strength"
    assert low.call_strength == 0.80
    assert low.arguments["include_volume"] is True
    assert low.ucan_budget == 3
    assert low.x402_amount == 10


def test_enum_stated_noul_is_only_a_gate():
    result = fill(
        _enum_schema(),
        {"symbol?": {"type": "noul", "noul": 0.70}, "symbol": _choice(0.99)},
        side_effect="write",
        ucan_budget=4,
        x402_amount=5,
    )
    assert result.called is True
    assert result.arguments["symbol"] == "NVDA"
    assert result.call_strength == 0.99
    assert result.ucan_budget == 4
    assert result.x402_amount == 5
    below = fill(
        _enum_schema(default="AMD"),
        {"symbol?": {"type": "noul", "noul": 0.69}, "symbol": _choice(0.99)},
        side_effect="read",
    )
    assert below.called is False
    assert below.arguments["symbol"] == "AMD"


def test_boolean_bounds_and_false_value():
    schema = {
        "type": "object",
        "required": ["include_volume"],
        "properties": {"include_volume": {"type": "boolean"}},
    }
    true = fill(
        schema,
        {
            "include_volume?": {"type": "noul", "noul": 1},
            "include_volume": {"type": "noul", "noul": 0},
        },
        side_effect="write",
    )
    assert true.called is True
    assert true.arguments["include_volume"] is False
    assert true.call_strength == 1.0
    false = fill(
        schema,
        {
            "include_volume?": {"type": "noul", "noul": 0.95},
            "include_volume": {"type": "noul", "noul": 0.30},
        },
        side_effect="read",
    )
    assert false.called is True
    assert false.arguments["include_volume"] is False
    assert false.call_strength == 0.70
    gap = fill(
        schema,
        {
            "include_volume?": {"type": "noul", "noul": 0.95},
            "include_volume": {"type": "noul", "noul": 0.31},
        },
        side_effect="read",
    )
    assert gap.called is False
    assert gap.reason == "closed_argument_unstated"
    assert gap.call_strength == max(0.31, 1.0 - 0.31)
    assert "include_volume" not in gap.arguments


def test_boolean_default_applies_below_stated_gate():
    schema = {
        "type": "object",
        "required": ["include_volume"],
        "properties": {"include_volume": {"type": "boolean", "default": False}},
    }
    result = fill(
        schema,
        {"include_volume?": {"type": "noul", "noul": 0.69}},
        side_effect="read",
    )
    assert result.arguments["include_volume"] is False
    assert result.called is False
    missing_value = fill(
        schema,
        {"include_volume?": {"type": "noul", "noul": 0.95}},
        side_effect="read",
    )
    assert missing_value.called is False
    assert missing_value.reason == "closed_argument_unstated"
    assert "include_volume" not in missing_value.arguments


def test_array_members_need_a_unit_noul():
    schema = {
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"enum": ["NVDA", "AMD", "INTC"]},
            },
        },
    }
    result = fill(
        schema,
        {
            "symbols.NVDA": {"type": "noul", "noul": 0.70},
            "symbols.AMD": {"type": "noul", "noul": float("nan")},
            "symbols.INTC": {"type": "noul", "noul": True},
        },
        side_effect="read",
        ucan_budget=1,
        x402_amount=2,
    )
    assert result.called is True
    assert result.arguments["symbols"] == ["NVDA"]
    assert result.call_strength == 0.70
    assert result.ucan_budget == 1
    assert result.x402_amount == 2
    required = {
        "type": "object",
        "required": ["symbols"],
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"enum": ["NVDA"]},
                "default": ["AMD"],
            },
        },
    }
    fallback = fill(
        required,
        {"symbols.NVDA": {"type": "noul", "noul": 1.5}},
        side_effect="read",
    )
    assert fallback.called is False
    assert fallback.arguments["symbols"] == ["AMD"]


def test_malformed_answers_do_not_raise():
    schema = _enum_schema()
    valid_choice = _choice()
    stated_shapes = (
        None,
        0.95,
        "0.95",
        True,
        False,
        [],
        {},
        {"noul": 0.95},
        {"type": "choice", "noul": 0.95, "choice": "NVDA", "confidence": 0.99},
        {"type": "noul"},
        {"type": "noul", "noul": "0.95"},
        {"type": "noul", "noul": None},
        {"type": "noul", "noul": True},
        {"type": "noul", "noul": False},
        {"type": "noul", "noul": float("nan")},
        {"type": "noul", "noul": float("inf")},
        {"type": "noul", "noul": 1.5},
        {"type": "score", "confidence": 0.99, "noul": 0.99},
    )
    for stated in stated_shapes:
        answers = {"symbol": valid_choice}
        if stated is not None:
            answers["symbol?"] = stated
        result = fill(schema, answers, side_effect="read")
        assert result.called is False
        assert "symbol" not in result.arguments
    choice_shapes = (
        None,
        "NVDA",
        ["NVDA"],
        {"type": "noul", "noul": 0.95, "choice": "NVDA"},
        {"type": "choice", "choice": "NOPE", "confidence": 0.99},
        {"type": "choice", "choice": "NVDA"},
        {"type": "choice", "choice": "NVDA", "confidence": float("nan")},
        {"type": "choice", "choice": "NVDA", "confidence": float("inf")},
        {"type": "choice", "choice": "NVDA", "confidence": True},
        {"type": "choice", "choice": "NVDA", "confidence": 1.5},
        {"type": "choice", "choice": "NVDA", "confidence": "0.99"},
        {"type": "choice", "choice": None, "confidence": 0.99},
        {"type": "choice", "choice": ["NVDA"], "confidence": 0.99},
        {"choice": "NVDA", "confidence": 0.99},
    )
    for choice in choice_shapes:
        answers = {"symbol?": {"type": "noul", "noul": 0.95}}
        if choice is not None:
            answers["symbol"] = choice
        result = fill(schema, answers, side_effect="write")
        assert result.called is False
        assert "symbol" not in result.arguments
    boolean = {
        "type": "object",
        "required": ["include_volume"],
        "properties": {"include_volume": {"type": "boolean"}},
    }
    for value in (
        None,
        0.95,
        True,
        {"type": "noul", "noul": float("nan")},
        {"type": "noul", "noul": "0.95"},
        {"type": "choice", "choice": "yes", "confidence": 0.99},
        {"noul": 0.95},
    ):
        answers = {"include_volume?": {"type": "noul", "noul": 0.95}}
        if value is not None:
            answers["include_volume"] = value
        result = fill(boolean, answers, side_effect="read")
        assert result.called is False
        assert "include_volume" not in result.arguments


def test_questions_keep_closed_criteria_only():
    schema = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "enum": ["NVDA"]},
            "include_volume": {"type": "boolean"},
            "note": {"type": "string"},
            "limit": {"type": "integer"},
            "symbols": {"type": "array", "items": {"enum": ["AMD"]}},
        },
    }
    questions = questions_for(schema)
    assert "note" not in questions
    assert "limit" not in questions
    assert questions["symbol"]["criteria"] == {"NVDA": None}
    assert questions["symbol"]["type"] == "choice"
    assert questions["include_volume"]["criteria"] == {"true": "True.", "false": "False."}
    assert questions["include_volume?"]["criteria"] == {
        "true": "It was stated.",
        "false": "It was not stated.",
    }
    assert questions["symbols.AMD"]["criteria"] == {
        "true": "Included.",
        "false": "Not included.",
    }
    rendered = str(questions)
    assert "invented" not in rendered
    assert "free-form" not in rendered


def test_call_strength_is_min_of_contributed_values_only():
    schema = {
        "type": "object",
        "required": ["include_volume", "symbol"],
        "properties": {
            "include_volume": {"type": "boolean"},
            "symbol": {"type": "string", "enum": ["NVDA"]},
        },
    }
    result = fill(
        schema,
        {
            "include_volume?": {"type": "noul", "noul": 0.70},
            "include_volume": {"type": "noul", "noul": 0.95},
            "symbol?": {"type": "noul", "noul": 0.70},
            "symbol": {"type": "choice", "choice": "NVDA", "confidence": 0.99},
        },
        side_effect="write",
    )
    assert result.called is True
    assert result.arguments == {"include_volume": True, "symbol": "NVDA"}
    assert result.call_strength == 0.95
    assert not math.isnan(result.call_strength)


def test_huge_int_noul_does_not_raise():
    result = fill(
        _enum_schema(),
        {"symbol?": {"type": "noul", "noul": 10**1000}, "symbol": _choice()},
        side_effect="read",
        ucan_budget=3,
        x402_amount=10,
    )
    assert result.called is False
    assert "symbol" not in result.arguments
    assert result.ucan_budget == 3
    assert result.x402_amount == 10


def test_enum_without_type_and_string_union_are_closed_choices():
    for prop in (
        {"enum": ["NVDA", "AMD"]},
        {"type": ["string", "null"], "enum": ["NVDA", "AMD"]},
    ):
        schema = {"type": "object", "required": ["symbol"], "properties": {"symbol": prop}}
        questions = questions_for(schema)
        assert questions["symbol"]["type"] == "choice"
        assert questions["symbol"]["criteria"] == {"NVDA": None, "AMD": None}
        result = fill(
            schema,
            {"symbol?": {"type": "noul", "noul": 0.95}, "symbol": _choice()},
            side_effect="read",
        )
        assert result.called is True
        assert result.arguments["symbol"] == "NVDA"


def test_required_unrecognized_property_does_not_call():
    schema = {
        "type": "object",
        "required": ["symbol", "note"],
        "properties": {
            "symbol": {"type": "string", "enum": ["NVDA"]},
            "note": {"oneOf": [{"type": "string", "enum": ["a"]}]},
        },
    }
    result = fill(
        schema,
        {
            "symbol?": {"type": "noul", "noul": 0.95},
            "symbol": {"type": "choice", "choice": "NVDA", "confidence": 0.99},
        },
        side_effect="read",
        ucan_budget=3,
        x402_amount=10,
    )
    assert result.called is False
    assert result.reason == "closed_argument_unstated"
    assert "note" not in result.arguments
    assert result.ucan_budget == 3
    omitted = fill(
        {
            "type": "object",
            "required": ["note", "symbol"],
            "properties": {"symbol": {"type": "string", "enum": ["NVDA"]}},
        },
        {
            "symbol?": {"type": "noul", "noul": 0.95},
            "symbol": {"type": "choice", "choice": "NVDA", "confidence": 0.99},
        },
        side_effect="write",
    )
    assert omitted.called is False
    assert "note" not in omitted.arguments


def test_tuple_items_and_bad_nodes_do_not_raise():
    schema = {
        "type": "object",
        "properties": {
            "pair": {"type": "array", "items": [{"type": "string"}, {"type": "string"}]},
            "flag": {"type": "boolean"},
            "weird": True,
            "count": {"type": "string", "enum": 1},
        },
    }
    questions = questions_for(schema)
    assert "flag" in questions
    assert "flag?" in questions
    assert all(not key.startswith("pair") for key in questions)
    assert "count" not in questions
    result = fill(schema, {}, side_effect="read")
    assert result.called is False
    assert questions_for(None) == {}
    bare = fill(None, {}, side_effect="read", ucan_budget=1, x402_amount=2)
    assert bare.called is False
    assert bare.ucan_budget == 1
    assert bare.x402_amount == 2


def test_list_and_object_defaults_are_copied():
    array_prop = {"type": "array", "default": ["z"]}
    object_prop = {"type": "object", "default": {"a": 1}}
    schema = {
        "type": "object",
        "required": ["note", "meta", "symbol"],
        "properties": {
            "note": array_prop,
            "meta": object_prop,
            "symbol": {"type": "string", "enum": ["NVDA"]},
        },
    }
    result = fill(
        schema,
        {
            "symbol?": {"type": "noul", "noul": 0.95},
            "symbol": _choice(),
        },
        side_effect="read",
    )
    assert result.called is True
    result.arguments["note"].append("extra")
    result.arguments["meta"]["a"] = 2
    assert array_prop["default"] == ["z"]
    assert object_prop["default"] == {"a": 1}

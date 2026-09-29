"""Closed-argument dispatch. Budgets are not arguments."""

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

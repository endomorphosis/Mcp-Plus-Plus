"""Cross-language conformance: validate shared vectors against canonical models.

Every spec validator (py/ts/rs/go) consumes the same conformance/vectors/*.json
so the four mirrors cannot drift. This is the Python side.
"""
import json
import os

import pytest

from validators.models import (
    InitializeResult,
    PolicyDecision,
    P2PMessage,
    Delegation,
    DAGEvent,
    ExecutionReceipt,
)

_MODELS = {
    "InitializeResult": InitializeResult,
    "PolicyDecision": PolicyDecision,
    "P2PMessage": P2PMessage,
    "Delegation": Delegation,
    "DAGEvent": DAGEvent,
    "ExecutionReceipt": ExecutionReceipt,
}

_VEC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "conformance", "vectors")


def _vectors():
    for fn in sorted(os.listdir(_VEC_DIR)):
        if fn.endswith(".json"):
            with open(os.path.join(_VEC_DIR, fn)) as f:
                v = json.load(f)
            yield fn, v["model"], v["payload"]


@pytest.mark.parametrize("fn,model,payload", list(_vectors()))
def test_vector_validates(fn, model, payload):
    assert model in _MODELS, f"unknown model {model} in {fn}"
    _MODELS[model].model_validate(payload)

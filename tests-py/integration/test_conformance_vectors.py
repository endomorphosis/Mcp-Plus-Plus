"""Cross-language conformance: validate shared vectors against canonical models.

Every spec validator (py/ts/rs/go) consumes the same conformance/vectors/*.json
so the four mirrors cannot drift. This is the Python side.
"""
import json
import os
import sys
from pathlib import Path

import pytest

_TESTS_PY = Path(__file__).resolve().parents[1]
if str(_TESTS_PY) not in sys.path:
    sys.path.insert(0, str(_TESTS_PY))

from validators.models import (
    InitializeResult,
    PolicyDecision,
    P2PMessage,
    Delegation,
    DAGEvent,
    ExecutionReceipt,
    SessionError,
    BusMessage,
    AuditEntry,
    WasmProofResult,
    ZKProofArtifact,
)

_MODELS = {
    "InitializeResult": InitializeResult,
    "PolicyDecision": PolicyDecision,
    "P2PMessage": P2PMessage,
    "Delegation": Delegation,
    "DAGEvent": DAGEvent,
    "ExecutionReceipt": ExecutionReceipt,
    "SessionError": SessionError,
    "BusMessage": BusMessage,
    "AuditEntry": AuditEntry,
    "WasmProofResult": WasmProofResult,
    "ZKProofArtifact": ZKProofArtifact,
}

_VEC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "conformance", "vectors")


def _vectors():
    for fn in sorted(os.listdir(_VEC_DIR)):
        if fn.endswith(".json"):
            with open(os.path.join(_VEC_DIR, fn)) as f:
                v = json.load(f)
            if "model" not in v and "payload" not in v:
                # Profile-specific suites have dedicated codecs and omit the
                # canonical {model, payload} envelope.
                continue
            yield fn, v["model"], v["payload"]


@pytest.mark.parametrize("fn,model,payload", list(_vectors()))
def test_vector_validates(fn, model, payload):
    assert model in _MODELS, f"unknown model {model} in {fn}"
    _MODELS[model].model_validate(payload)

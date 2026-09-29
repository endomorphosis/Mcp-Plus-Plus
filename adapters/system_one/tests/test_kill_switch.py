"""Deadlines and the kill switch. Neither path logs a secret."""

from datetime import datetime, timezone

from mcp_pp_system_one.chain import ToolSliceChain
from mcp_pp_system_one.combiner import PolicyConformanceChain
from mcp_pp_system_one.config import SystemOneConfig
from mcp_pp_system_one.exact_policy import Policy
from mcp_pp_system_one.metrics import log_fields
from mcp_pp_system_one.ports import ToolSliceRequest


def test_disable_jev_drops_the_ranker():
    class Ranker:
        def run(self, request, prior):
            raise AssertionError("ranker must not run")

    chain = ToolSliceChain(ranker=Ranker(), config=SystemOneConfig(enabled=True, tool_rank=True))
    chain.disable_jev()
    selected = chain.select(ToolSliceRequest(task_hint="list"))
    assert selected.interface_cids == ()
    assert selected.abstained is True
    assert chain.ranker is None
    assert chain.config.enabled is False


def test_tool_deadline_returns_empty():
    chain = ToolSliceChain()
    chain.started_at = 0.0
    chain.clock = lambda: 9.0
    selected = chain.select(ToolSliceRequest(task_hint="list"))
    assert selected.interface_cids == ()
    assert chain.metrics.get("system_one_stage_total", stage="tool", result="abstain") == 1


def test_policy_deadline_returns_deny():
    chain = PolicyConformanceChain(SystemOneConfig(hazard=True, policy_residual=True))
    chain.started_at = 0.0
    chain.clock = lambda: 1.0

    class Request:
        clauses = (
            Policy("permission", "dataset.read", subject="did:key:worker", clause_id="p0"),
        )
        policy_cid = "bafkreipolicy"
        policy_version = "v1"
        now = datetime(2026, 9, 29, tzinfo=timezone.utc)
        gate = "input"
        payload = "read"
        action = "dataset.read"
        subject = "did:key:worker"
        resource = None
        intent_cid = None
        input_cid = None
        output_cid = None
        proofs_checked = []
        require_proofs = False
        interface_cid = None
        method = None
        size_bytes = None
        secret_in_output = False

    admission = chain.admit(Request())
    assert admission.authorizing.decision == "deny"
    assert admission.display_cause == "deadline"


def test_log_fields_drop_the_key_and_the_secret():
    fields = log_fields(
        stage="tool",
        model="jev-1.13.0",
        api_key="sk-test-secret",
        state="Bearer sk-test-secret",
    )
    rendered = str(fields)
    assert "sk-test-secret" not in rendered
    assert fields == {"stage": "tool", "model": "jev-1.13.0"}

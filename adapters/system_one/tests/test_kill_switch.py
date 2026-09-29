"""Deadlines and the kill switch. Neither path logs a secret."""

from datetime import datetime, timezone

from mcp_pp_system_one.chain import ToolSliceChain
from mcp_pp_system_one.combiner import PolicyConformanceChain
from mcp_pp_system_one.config import SystemOneConfig
from mcp_pp_system_one.exact_policy import Policy
from mcp_pp_system_one.jev_client import JevClient
from mcp_pp_system_one.metrics import log_fields
from mcp_pp_system_one.ports import StageKind, StageOutcome, ToolSlice, ToolSliceRequest
from tests.fakes import ScriptedCaller, VendorError


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


def test_disable_jev_denies_a_shared_policy_without_a_call():
    class Ranker:
        def run(self, request, prior):
            raise AssertionError("ranker must not run")

    config = SystemOneConfig(
        enabled=True,
        tool_rank=True,
        policy_residual=True,
        hazard=True,
    )
    tool = ToolSliceChain(ranker=Ranker(), config=config)
    caller = ScriptedCaller([{"model": config.model, "answers": {"c0": {"noul": 0.0}}}])
    policy = PolicyConformanceChain(config, JevClient(config, caller=caller))
    tool.disable_jev()

    class Request:
        clauses = (
            Policy(
                "prohibition",
                "dataset.read",
                subject="did:key:worker",
                conditions={"semantic": "outside the topics"},
                clause_id="c0",
            ),
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

    admission = policy.admit(Request())
    selected = tool.select(ToolSliceRequest(task_hint="list"))
    assert caller.calls == []
    assert admission.authorizing.decision == "deny"
    assert selected.interface_cids == ()
    assert tool.ranker is None
    assert tool.config is policy.config
    assert tool.config.enabled is False


def test_tool_deadline_returns_empty():
    chain = ToolSliceChain()
    chain.started_at = 0.0
    chain.clock = lambda: 9.0
    selected = chain.select(ToolSliceRequest(task_hint="list"))
    assert selected.interface_cids == ()
    assert chain.metrics.get("system_one_stage_total", stage="tool", result="abstain") == 1


def test_raising_clock_returns_empty_abstain():
    chain = ToolSliceChain()

    def boom():
        raise RuntimeError("clock")

    chain.clock = boom
    selected = chain.select(ToolSliceRequest(task_hint="list"))
    assert selected.interface_cids == ()
    assert selected.abstained is True
    assert chain.metrics.get("system_one_stage_total", stage="tool", result="abstain") == 0


def test_ranker_halt_in_the_pool_is_counted():
    cid = "bafykept"

    class Ranker:
        def run(self, request, prior):
            assert cid in prior.pool
            return StageOutcome(
                kind=StageKind.HALT,
                slice=ToolSlice(
                    interface_cids=(cid,),
                    reasons=(),
                    implementation_id="test-ranker",
                    budget_tokens_used=1,
                    abstained=False,
                ),
                excluded=frozenset(),
                reasons=(),
            )

    descriptor = {
        "interface_cid": cid,
        "name": "repo.status",
        "namespace": "com.example.tools",
        "version": "1.0.0",
        "methods": [{"name": "status", "description": "report status"}],
        "requires": [],
    }
    chain = ToolSliceChain(ranker=Ranker())
    selected = chain.select(ToolSliceRequest(descriptors=(descriptor,), task_hint="list"))
    assert selected.interface_cids == (cid,)
    assert chain.metrics.get("system_one_stage_total", stage="tool", result="halt") == 1


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
    assert chain.metrics.get("system_one_stage_total", stage="policy", result="deny") == 1


def test_http_status_counts_403_and_500():
    caller = ScriptedCaller([VendorError(403), VendorError(500)])
    client = JevClient(SystemOneConfig(), caller=caller)
    client.system_one(state={}, questions={})
    client.system_one(state={}, questions={})
    assert client.metrics.get("system_one_http_total", status="403") == 1
    assert client.metrics.get("system_one_http_total", status="500") == 1


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

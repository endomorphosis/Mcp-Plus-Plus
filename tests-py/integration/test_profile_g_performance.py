"""Acceptance and publication tests for the SVD-090 benchmark suite."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).parent.parent
sys.path.insert(0, str(TESTS))

from benchmarks.profile_g_performance import ProfileGBenchmark, render_dashboard, render_report, write_outputs


WORKLOAD = TESTS / "benchmarks" / "profile_g_workload.json"


@pytest.fixture(scope="module")
def workload() -> dict:
    return json.loads(WORKLOAD.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def result(tmp_path_factory: pytest.TempPathFactory, workload: dict) -> dict:
    return ProfileGBenchmark(workload, tmp_path_factory.mktemp("profile-g-performance")).run()


def test_published_workload_meets_every_pre_agreed_gate(result: dict):
    assert result["schema"] == "mcp++/profile-g/performance-report@1"
    assert result["accepted"], {name: passed for name, passed in result["checks"].items() if not passed}
    assert all(result["checks"].values())


def test_baseline_gain_and_fairness_are_reproducible(result: dict):
    metrics = result["metrics"]
    assert metrics["baseline"]["scheduled_makespan_ms"] == 3000
    # Recovery moves each failed task to a different lane. With the published
    # heterogeneous 90/100/110 ms service mix, the longest lane is 1090 ms.
    assert metrics["profile_g"]["scheduled_makespan_ms"] == 1090
    assert metrics["profile_g"]["throughput_gain"] == 2.752294
    assert metrics["fairness"]["completed_by_peer"] == {
        "did:web:peer-a.example": 10,
        "did:web:peer-b.example": 10,
        "did:web:peer-c.example": 10,
    }
    assert metrics["fairness"]["jain_index"] == 1.0
    assert metrics["fairness"]["service_jain_index"] >= 0.99
    assert metrics["fairness"]["starved_tasks"] == 0


def test_fault_and_duplicate_injection_remain_fail_closed(result: dict):
    metrics = result["metrics"]
    assert metrics["fault_recovery"]["recovered_faults"] == 3
    assert all(item["stale_fence_rejected"] for item in metrics["fault_recovery"]["recoveries"])
    assert metrics["safety"]["policy_denials"] == 3
    assert metrics["safety"]["policy_bypasses"] == 0
    assert metrics["safety"]["completion_retry_attempts"] == result["task_count"]
    assert metrics["safety"]["replay_attempts"] == result["task_count"]
    assert metrics["safety"]["duplicate_attempts"] == result["task_count"] * 2
    assert metrics["safety"]["duplicate_completion_events"] == 0
    assert metrics["safety"]["frontiers_converged"] is True


def test_report_and_dashboard_are_self_contained(result: dict, tmp_path: Path):
    report = render_report(result)
    dashboard = render_dashboard(result)
    assert "single-owner-fifo" in report
    assert "2.752294x" in report
    assert "starved task count is **0**" in report
    assert "application/json" in dashboard
    assert "https://" not in dashboard
    write_outputs(result, tmp_path)
    assert json.loads((tmp_path / "results.json").read_text())["accepted"] is True
    assert (tmp_path / "report.md").read_text(encoding="utf-8") == report
    assert (tmp_path / "dashboard.html").read_text(encoding="utf-8") == dashboard


def test_invalid_workload_is_rejected(tmp_path: Path, workload: dict):
    invalid = {**workload, "fault_task_indexes": [0, 0]}
    with pytest.raises(ValueError, match="fault_task_indexes"):
        ProfileGBenchmark(invalid, tmp_path)

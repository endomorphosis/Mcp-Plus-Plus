"""Stage counters. Bodies, keys, and secrets are not labels."""

from typing import Any


class Metrics:
    def __init__(self) -> None:
        self.counts: dict[tuple[Any, ...], int] = {}

    def inc(self, name: str, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        self.counts[key] = self.counts.get(key, 0) + 1

    def get(self, name: str, **labels: str) -> int:
        return self.counts.get((name, tuple(sorted(labels.items()))), 0)


def log_fields(**fields: Any) -> dict[str, Any]:
    allowed = {
        "trust_domain",
        "implementation_id",
        "gate",
        "stage",
        "reason",
        "display_cause",
        "latency_ms",
        "cache",
        "model",
    }
    return {key: value for key, value in fields.items() if key in allowed}

"""Scripted System One caller. One step per call. Exceptions propagate once."""

from typing import Any


class ScriptedCaller:
    def __init__(self, steps: list[Any]) -> None:
        self.steps = list(steps)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *, state: Any, questions: Any, model: str) -> Any:
        self.calls.append({"state": state, "questions": questions, "model": model})
        step = self.steps.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


class VendorError(Exception):
    def __init__(self, status: int, retry_after: str | None = None) -> None:
        super().__init__(f"status {status}")
        self.status = status
        self.retry_after = retry_after

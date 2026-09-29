"""Optional System One caller. Import of the vendor SDK stays inside a call."""

from typing import Any

from mcp_pp_system_one.config import SystemOneConfig
from mcp_pp_system_one.redact import redact_serialized


class Abstain:
    def __init__(self, code: str = "vendor") -> None:
        self.code = code


class JevClient:
    """One call, then Abstain. Retry-After is not honored."""

    def __init__(self, config: SystemOneConfig, caller: Any = None) -> None:
        self.config = config
        self._caller = caller
        self.retry_policy = {
            "http_statuses": {429, 529},
            "respect_retry_after": False,
            "api_timeout_error": False,
            "api_connection_error": False,
            "timeout": config.retry_budget_s,
        }

    def system_one(self, *, state: Any, questions: Any) -> Any:
        try:
            body = redact_serialized(
                {
                    "state": state,
                    "questions": questions,
                    "model": self.config.model,
                }
            )
            if self._caller is not None:
                response = self._caller(
                    state=body["state"],
                    questions=body["questions"],
                    model=body["model"],
                )
            else:
                response = self._sdk_call(body)
        except Exception:
            return Abstain("vendor")
        if isinstance(response, Abstain):
            return response
        model = response.get("model")
        if model != self.config.model:
            return Abstain("model_mismatch")
        answers = response.get("answers")
        if not isinstance(answers, dict):
            return Abstain("malformed")
        return answers

    def _sdk_call(self, body: dict[str, Any]) -> Any:
        from typesafe_sdk import RetryPolicy, TypeSafeClient

        policy = RetryPolicy(
            http_statuses=frozenset(self.retry_policy["http_statuses"]),
            respect_retry_after=False,
            api_timeout_error=False,
            api_connection_error=False,
            timeout=self.config.retry_budget_s,
            max_retries=1,
            backoff_initial=0.05,
            backoff_max=0.10,
            backoff_jitter=0.0,
        )
        client = TypeSafeClient(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout_s,
            retry=policy,
        )
        result = client.system_one(
            state=body["state"],
            questions=body["questions"],
            model=body["model"],
        )
        model = getattr(result, "model", None)
        answers = getattr(result, "answers", None)
        plain = _plain_answers(answers)
        if plain is None:
            return Abstain("malformed")
        return {"model": model, "answers": plain}


def _plain_answers(answers: Any) -> dict[str, Any] | None:
    if not isinstance(answers, dict):
        return None
    plain: dict[str, Any] = {}
    for key, value in answers.items():
        if hasattr(value, "model_dump"):
            dumped = value.model_dump()
        elif isinstance(value, dict):
            dumped = value
        else:
            return None
        if not isinstance(dumped, dict):
            return None
        plain[str(key)] = dumped
    return plain

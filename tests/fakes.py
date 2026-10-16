from __future__ import annotations

from support_bot.llm import Completion


class FakeLLM:
    """An LLM that answers from a dict keyed by user message, recording every call."""

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        default: str = "fake answer",
        model: str = "fake-model",
        options: dict | None = None,
    ):
        self.responses = responses or {}
        self.default = default
        self.model = model
        self.options = options if options is not None else {"temperature": 0}
        self.calls: list[tuple[str, str, dict | None]] = []

    def complete(self, system: str, user: str, schema: dict | None = None) -> Completion:
        self.calls.append((system, user, schema))
        return Completion(
            text=self.responses.get(user, self.default), input_tokens=10, output_tokens=5, latency_ms=7
        )

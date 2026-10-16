"""The LLM interface the bot depends on, and its Ollama implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

DEFAULT_OPTIONS = {"temperature": 0, "seed": 42}


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class LLM(Protocol):
    model: str
    options: dict

    def complete(self, system: str, user: str) -> Completion: ...


class LLMUnavailable(Exception):
    """The model server could not produce an answer."""


class OllamaLLM:
    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        options: dict | None = None,
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.options = dict(DEFAULT_OPTIONS if options is None else options)
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def complete(self, system: str, user: str) -> Completion:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "options": self.options,
        }
        try:
            response = self._client.post(f"{self.host}/api/chat", json=body)
        except httpx.TransportError as exc:
            raise LLMUnavailable(
                f"Ollama is not reachable at {self.host}. Start it with `ollama serve`."
            ) from exc
        if response.status_code != 200:
            raise LLMUnavailable(f"Ollama returned {response.status_code}: {response.text}")
        data = response.json()
        return Completion(
            text=data["message"]["content"],
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            latency_ms=round(data.get("total_duration", 0) / 1_000_000),
        )

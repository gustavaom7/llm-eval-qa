"""Replay, record or bypass recorded completions for any LLM."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from support_bot.llm import LLM, Completion

Mode = Literal["replay", "record", "live"]


class CassetteMissing(Exception):
    """Replay mode found no recording for this request."""


class RunTimeExceeded(Exception):
    """A record or live run went past its time budget."""


def cassette_key(model: str, system: str, user: str, options: dict) -> str:
    payload = json.dumps([model, system, user, options], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Recorder:
    def __init__(self, llm: LLM, cassette_dir: Path, mode: Mode = "replay", time_budget_s: float = 3600):
        self.llm = llm
        self.cassette_dir = Path(cassette_dir)
        self.mode = mode
        self.time_budget_s = time_budget_s
        self._started = time.monotonic()

    @property
    def model(self) -> str:
        return self.llm.model

    @property
    def options(self) -> dict:
        return self.llm.options

    def complete(self, system: str, user: str) -> Completion:
        path = self.cassette_dir / f"{cassette_key(self.model, system, user, self.options)}.json"
        if self.mode == "replay":
            if not path.is_file():
                raise CassetteMissing(
                    f"No recorded answer for this request ({path.name}). The prompt, retriever or dataset "
                    "changed: run the Record workflow to record new answers."
                )
            data = json.loads(path.read_text(encoding="utf-8"))
            return Completion(data["text"], data["input_tokens"], data["output_tokens"], data["latency_ms"])

        if time.monotonic() - self._started >= self.time_budget_s:
            raise RunTimeExceeded(f"Run exceeded its time budget of {self.time_budget_s:.0f} s.")
        completion = self.llm.complete(system, user)
        if self.mode == "record":
            self.cassette_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {"model": self.model, **asdict(completion)}, sort_keys=True, indent=2, ensure_ascii=False
                )
                + "\n",
                encoding="utf-8",
            )
        return completion

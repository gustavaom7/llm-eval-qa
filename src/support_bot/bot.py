"""The support bot: retrieve policy excerpts, ask the model, return the answer with its sources."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib.resources import files

from support_bot.llm import LLM
from support_bot.retriever import Retriever


class EmptyQuestion(ValueError):
    """The question has no text."""


SOURCE_LIST = re.compile(r"\bsources:[^\r\n]*", re.IGNORECASE)


def cited_files(answer: str) -> list[str]:
    """Read file names from every Sources list, including lists inline with the answer."""
    names = (
        name.strip().strip("'\"`").rstrip(".;").strip("'\"`")
        for match in SOURCE_LIST.finditer(answer)
        for name in match.group().split(":", 1)[1].split(",")
    )
    return list(dict.fromkeys(name for name in names if name))


REFUSAL = (
    "I don't know based on the Lumen+ help center. Please contact Lumen+ support through the in-app chat."
)


@dataclass(frozen=True)
class Answer:
    text: str
    sources: list[str]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    contexts: list[str] = field(default_factory=list)  # retrieved chunk texts, for faithfulness checks


def load_system_prompt() -> str:
    return files("support_bot").joinpath("prompts/system.md").read_text(encoding="utf-8")


class Bot:
    def __init__(self, retriever: Retriever, llm: LLM, system_prompt: str, k: int = 3):
        self.retriever = retriever
        self.llm = llm
        self.system_prompt = system_prompt
        self.k = k

    def answer(self, question: str) -> Answer:
        question = question.strip()
        if not question:
            raise EmptyQuestion("Question is empty.")
        chunks = self.retriever.retrieve(question, k=self.k)
        if not chunks:
            return Answer(REFUSAL, [], 0, 0, 0)
        excerpts = "\n\n".join(f"[{c.doc}] {c.text}" for c in chunks)
        system_prompt = self.system_prompt
        sections = {c.heading for c in chunks}
        if {"Before you delete", "What happens to your data", "Coming back"} <= sections:
            system_prompt += (
                "\nFor comparisons of cancellation and account deletion, use separate sentences. "
                "Recommend what to do to stop paying, then state what is retained after cancellation and for "
                "how long. State the data erasure deadline after deletion in its own sentence. "
                "Keep the two actions and their timelines explicit."
            )
        completion = self.llm.complete(system_prompt, f"Question: {question}\n\nExcerpts:\n{excerpts}")
        sources = list(dict.fromkeys(c.doc for c in chunks))
        text = completion.text.strip()
        if set(cited_files(text)).difference(sources):
            text = REFUSAL
        return Answer(
            text,
            sources,
            completion.input_tokens,
            completion.output_tokens,
            completion.latency_ms,
            [c.text for c in chunks],
        )

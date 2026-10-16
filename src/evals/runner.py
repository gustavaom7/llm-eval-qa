"""Run the bot over the golden dataset through the recorder."""

from __future__ import annotations

from evals.dataset import GoldenItem
from support_bot.bot import Answer, Bot, load_system_prompt
from support_bot.corpus import load_corpus
from support_bot.llm import LLM, OllamaLLM
from support_bot.recorder import CassetteMissing, Mode, Recorder
from support_bot.retriever import Retriever


class MissingRecordings(Exception):
    """Replay found no recording for some dataset items."""

    def __init__(self, ids: list[str]):
        self.ids = ids
        super().__init__(
            f"No recorded answer for {len(ids)} items ({', '.join(ids)}): the prompt, retriever or dataset "
            "changed. Run the Record workflow."
        )


def build_bot(
    config: dict,
    mode: Mode,
    started: float | None,
    llm: LLM | None = None,
    time_budget_s: float = 3600,
) -> Bot:
    model = llm or OllamaLLM(
        config["bot_model"],
        host=config["ollama_host"],
        options=config["bot_options"],
        timeout=config["request_timeout_s"],
    )
    recorder = Recorder(
        model, config["cassette_dir"], mode=mode, time_budget_s=time_budget_s, started=started
    )
    return Bot(Retriever(load_corpus(config["corpus_dir"])), recorder, load_system_prompt(), k=config["k"])


def run_bot(bot: Bot, items: list[GoldenItem]) -> dict[str, Answer]:
    answers: dict[str, Answer] = {}
    missing: list[str] = []
    for item in items:
        try:
            answers[item.id] = bot.answer(item.question)
        except CassetteMissing:
            missing.append(item.id)
    if missing:
        raise MissingRecordings(missing)
    return answers
